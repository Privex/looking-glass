#!/usr/bin/env python3
import grpc
import grpc._channel
import logging
from flask_sqlalchemy import SQLAlchemy
from google.protobuf.pyext._message import RepeatedCompositeContainer
from dataclasses import dataclass, field
from typing import List, Union, Dict
from ipaddress import IPv4Address, IPv6Address, IPv4Network, IPv6Network, ip_address, ip_network

from psycopg2.extras import Inet
from redis import Redis

from gobgp import gobgp_pb2, gobgp_pb2_grpc, attribute_pb2
from gobgp.gobgp_pb2 import ListPathRequest, ListPathResponse, Family
from enum import Enum
from datetime import datetime
from lg import base
from lg.models import ASN, Prefix, Community
from lg.peerapp.settings import OUR_ASN, OUR_ASN_NAME, LOCAL_IPS, IX_NET_VER, BLACKLIST_ROUTES, CHUNK_SIZE
from lg.base import get_redis
from lg.exceptions import GoBGPException
from privex.helpers import empty, asn_to_name, r_cache, FO

log = logging.getLogger(__name__)


class PathLoader:
    """

    :ivar grpc._channel.Channel channel: GRPC Channel for use by GoBGP API
    :ivar gobgp_pb2_grpc.GobgpApiStub stub: Instance of :py:class:`gobgp_pb2_grpc.GobgpApiStub`
    :ivar list paths: List of GoBGP path objects as instances of :py:class:`gobgp.gobgp_pb2.ListPathResponse`
    :ivar List[SanePath] sane_paths: A list of prefixes as :class:`.SanePath` instances
    :ivar Dict[str, Dict[str, int]] as_counts: Contains a total of v4 and v6 prefixes for each ASN
    """
    asn_cache = {}
    # _couch = None
    _redis = None    # type: Redis
    _db = None       # type: SQLAlchemy
    asn_in_db = {}   # type: Dict[int, ASN]

    _cache = dict(
        asn_in_db={},  # type: Dict[int, ASN]
        community_in_db={},   # type: Dict[int, Community]
    )

    def __init__(self, host: str = 'localhost:50051', db: SQLAlchemy = None, auto_load=True, **kwargs):
        """
        Constructor for PathLoader, sets up GoBGP

        :param str host: `host:port` of a GoBGP RPC server (default: `localhost:50051`)
        :param SQLAlchemy db: An instance of :py:class:`flask_sqlalchemy.SQLAlchemy`
        :param bool auto_load: Automatically populate :py:attr:`.paths` with v4/v6 prefixes during __init__ (def: True)
        :raises GoBGPException: Generally raised when we can't connect to GoBGP's RPC (may only be raised if auto_load)
        """
        self.quiet = kwargs.get('quiet', False)
        self.verbose = kwargs.get('verbose', False)
        if db is not None:
            PathLoader._db = self._db = db
        self.host = host
        self.paths = dict(v6=[], v4=[])  # type: Dict[str, List[ListPathResponse]]
        self.as_counts = dict(v4={}, v6={})   # type: Dict[str, Dict[str, int]]
        self.sane_paths = []  # type: List[SanePath]

        try:
            self.channel = channel = grpc.insecure_channel(host)
            self.stub = gobgp_pb2_grpc.GobgpApiStub(channel)
            # if auto_load:
            #     self.paths['v4'], self.paths['v6'] = self.load_paths(), self.load_paths(family=Family.AFI_IP6)
        except grpc._channel._Rendezvous as e:
            raise GoBGPException(f'Failed to connect to GoBGP server at {host} - reason: {type(e)} {str(e.details())}')
        except GoBGPException as e:
            raise e

    @property
    def db(self) -> SQLAlchemy:
        """Obtain an SQLAlchemy instance from :py:attr:`._db` or init SQLAlchemy if it's `None`"""
        if not PathLoader._db:
            _, db, _ = base.get_app()
            PathLoader._db = db
        return PathLoader._db

    @property
    def redis(self) -> Redis:
        """Obtain a Redis instance from :py:attr:`._redis` or init Redis if it's `None`"""
        if not self._redis:
            self._redis = get_redis()
        return self._redis

    def set_db(self, db: SQLAlchemy):
        """Sets the private :py:attr:`._db` to the instance passed in `db`"""
        PathLoader._db = self._db = db

    def load_paths(self, family=Family.AFI_IP, safi=Family.SAFI_UNICAST) -> List[ListPathResponse]:
        """
        Queries GoBGP (via :py:attr:`.stub`) to obtain a list of paths matching the given `family` and `safi` params.

        Usage:

            >>> paths_v4 = PathLoader().load_paths()
            >>> paths_v6 = PathLoader().load_paths(family=Family.AFI_IP6)
            >>> paths_v4[0].destination.paths[0].source_asn
            210083


        :param Family family:  The IP version, e.g. `Family.AFI_IP` for IPv4 or `Family.AFI_IP6` for IPv6
        :param Family safi:    The type of IP prefix, e.g. `Family.SAFI_UNICAST` or `Family.SAFI_MULTICAST`
        :raises GoBGPException: Generally raised when we can't connect to GoBGP's RPC
        :return List[gobgp_pb2.ListPathResponse] paths: A list of GoBGP paths
        """

        try:
            return self.stub.ListPath(
                ListPathRequest(family=Family(afi=family, safi=safi))
            )
        except grpc._channel._Rendezvous as e:
            raise GoBGPException(f'Failed to connect to GoBGP server at {self.host} - '
                                 f'reason: {type(e)} {str(e.details())}')

    @r_cache('asn:{}', format_args=[1, 'asn'], format_opt=FO.POS_AUTO)
    def get_as_name(self, asn: Union[int, str]) -> str:
        """
        Get the human name for a given AS Number (ASN), with local memory caching + redis caching.

        Uses :py:attr:`peerapp.settings.OUR_ASN` and :py:attr:`peerapp.settings.OUR_ASN_NAME` to return correct
        information about our own autonomous system, and uses :py:func:`privex.helpers.net.asn_to_name` to find
        the name of unknown ASNs.

        Uses both a local memory cache of ASN names in :py:attr:`.asn_cache` , as well as storing them in Redis
        for persistence between runs.

        Usage:

            >>> PathLoader().get_as_name(210083)
            'Privex Inc.'

        :param int asn: An AS Number such as 210083 (as int or str)
        :return str as_name: Human name of the ASN
        """
        try:
            # r = self.redis
            asn = int(asn)
            if asn == int(OUR_ASN): return OUR_ASN_NAME
            if asn in self.asn_cache: return self.asn_cache[asn]

            n = self.asn_cache[asn] = str(asn_to_name(asn))
            return n
        except Exception as e:
            log.warning('Failed to look up ASN %s - exception: %s %s', asn, type(e), str(e))
            return f'Unknown ({asn})'

    def parse_paths(self, family='v4'):
        verbose = self.verbose
        for path in self.load_paths(Family.AFI_IP if family == 'v4' else Family.AFI_IP6):
            try:
                _p = PathParser(path)
                p = dict(_p)
                del p['source_asn']
                np = SanePath(**p)
                if ip_network(np.prefix) in BLACKLIST_ROUTES:
                    log.debug('Skipping path %s as it is blacklisted.', np.prefix)
                    continue

                # self.sane_paths.append(np)
                srcas = str(np.source_asn)
                if empty(srcas):
                    log.warning('AS for path %s is empty. Not adding to count.', srcas)
                    continue
                ct_as = self.as_counts[family]            
                ct_as[srcas] = 1 if srcas not in ct_as else ct_as[srcas] + 1
                if verbose:
                    print(f'Prefix: {np.prefix}, Source ASN: {srcas}, Next Hop: {np.first_hop}')
                
                yield np
            except Exception:
                log.exception('Unexpected exception while processing path %s', path)
    
    def _make_id(self, path: dict):
        return f"{path['prefix']}-{path['first_hop']}-{path['source_asn']}"

    def store_paths(self):
        """
        Iterates over :py:attr:`.sane_paths` and inserts/updates the appropriate prefix/asn/community objects
        into the database.

        :return:
        """
        db = self.db
        session = db.session
        log.info('Saving sane paths to Postgres.')
        # total_prefixes = len(self.sane_paths)
        i = 0
        for p in self.parse_paths():
            if (i % CHUNK_SIZE) == 0:
                log.info('Saved %s prefixes.', i)
                session.commit()
            p_dic = dict(p)
            if p.source_asn in self._cache['asn_in_db']:
                asn = self._cache['asn_in_db'][p.source_asn]
            else:
                asn = ASN.query.filter_by(asn=p.source_asn).first()
                if not asn:
                    asn = ASN(asn=p.source_asn, as_name=self.get_as_name(p.source_asn))
                    session.add(asn)
                self._cache['asn_in_db'][p.source_asn] = asn

            communities = list(p_dic['communities'])

            del p_dic['family']
            del p_dic['source_asn']
            del p_dic['first_hop']
            del p_dic['communities']

            for x, nh in enumerate(p_dic['next_hops']):
                p_dic['next_hops'][x] = Inet(nh)

            pfx = Prefix.query.filter_by(source_asn=asn, prefix=p_dic['prefix']).first()   # type: Prefix
            if not pfx:
                pfx = Prefix(**p_dic, source_asn=asn, last_seen=datetime.utcnow())
            for k, v in p_dic.items():
                setattr(pfx, k, v)
            pfx.last_seen = datetime.utcnow()

            for c in communities:
                if c in self._cache['community_in_db']:
                    comm = self._cache['community_in_db'][c]
                else:
                    comm = Community.query.filter_by(id=c).first()
                    if not comm: comm = Community(id=c)
                pfx.communities.append(comm)

            session.add(pfx)
            
            i += 1

        session.commit()
        log.info('Finished saving paths.')

    def summary(self):
        if self.quiet:
            return
        print('--- v4 paths ---')
        total_v4 = total_v6 = 0
        for asn, num in self.as_counts['v4'].items():
            asname = self.get_as_name(asn)
            print(f'ASN: {asn:9} Name: {asname:20.20}     Prefixes: {num}')
            total_v4 += num

        print('--- v6 paths ---')
        for asn, num in self.as_counts['v6'].items():
            asname = self.get_as_name(asn)
            print(f'ASN: {asn:9} Name: {asname:20.20}     Prefixes: {num}')
            total_v6 += num

        print('--- summary ---')
        print(f'total v4: {total_v4} -- total v6: {total_v6}')


# found on this gist
# https://gist.github.com/iwaseyusuke/df1e0300221b0c6aa1a98fc346621fdc
def unmarshal_any(any_msg):
    """
    Unpacks an `Any` message.

    If need to unpack manually, the following is a simple example::

        if any_msg.Is(attribute_pb2.IPAddressPrefix.DESCRIPTOR):
            ip_addr_prefix = attribute_pb2.IPAddressPrefix()
            any_msg.Unpack(ip_addr_prefix)
            return ip_addr_prefix
    """
    if any_msg is None:
        return None

    # Extract 'name' of message from the given type URL like
    # 'type.googleapis.com/type.name'.
    msg_name = any_msg.type_url.split('.')[-1]

    for pb in (gobgp_pb2, attribute_pb2):
        msg_cls = getattr(pb, msg_name, None)
        if msg_cls is not None:
            break
    assert msg_cls is not None

    msg = msg_cls()
    any_msg.Unpack(msg)
    return msg


def find_attr(obj: RepeatedCompositeContainer, type_url: str, unmarshal=True):
    type_url = type_url.lower().strip()
    for x in obj:
        tu = str(x.type_url).lower().strip()
        if tu == type_url or type_url in tu:
            return unmarshal_any(x) if unmarshal else x
    return None


class AddrFamily(Enum):
    IPV4 = IPv4Network
    IPV6 = IPv6Network


@dataclass
class SanePath:
    prefix: Union[IPv4Network, IPv6Network]
    family: AddrFamily
    next_hops: List[Union[IPv4Address, IPv6Address]] = field(default_factory=list)
    asn_path: List[int] = field(default_factory=list)
    communities: List[int] = field(default_factory=list)
    neighbor: Union[IPv4Address, IPv6Address] = None
    source_id: str = ""
    age: datetime = None

    @property
    def source_asn(self):
        return self.asn_path[0] if len(self.asn_path) > 0 else None
    
    @property
    def first_hop(self):
        return self.next_hops[0] if len(self.next_hops) > 0 else None
    
    @property
    def ixp(self):
        ix_nets = IX_NET_VER[type(self.first_hop)]
        for subnet, ixname in ix_nets:
            subnet = ip_network(subnet)
            if ip_address(self.first_hop) in subnet:
                # log.debug('First hop %s is in subnet %s (IXP: %s)', self.first_hop, subnet, ixname)
                return ixname
            # log.debug('Hop %s is NOT in subnet %s (IXP: %s)', self.first_hop, subnet, ixname)
        return 'N/A'
    
    def __iter__(self):
        d = {
            'prefix': str(self.prefix),
            'family': 'v4' if self.family == AddrFamily.IPV4 else 'v6',
            'next_hops': [str(hop) for hop in self.next_hops],
            'first_hop': str(self.first_hop),
            'asn_path': self.asn_path,
            'source_asn': self.source_asn,
            'communities': self.communities,
            'neighbor': str(self.neighbor),
            'age': str(self.age),
            'ixp': self.ixp
        }
        for k, v in d.items():
            yield (k, v,)


class PathParser:
    def __init__(self, path: gobgp_pb2.ListPathResponse):
        self.orig_path = path    # type: gobgp_pb2.ListPathResponse
        self.path = path.destination.paths[0]   # type: gobgp_pb2.Path
    
    @property
    def prefix(self) -> Union[IPv4Network, IPv6Network]:
        _pfx = unmarshal_any(self.path.nlri)
        pfx = f'{_pfx.prefix}/{_pfx.prefix_len}'
        return ip_network(pfx, strict=False)

    @property
    def asn_path(self) -> List[int]:
        p = self.path.pattrs
        r_asn = find_attr(p, 'AsPathAttribute')
        return list(r_asn.segments[0].numbers)
    
    @property
    def communities(self) -> List[int]:
        return list(find_attr(self.path.pattrs, 'communities').communities)
    
    @property
    def neighbor(self) -> Union[IPv4Address, IPv6Address]:
        return ip_address(self.path.neighbor_ip)
    
    @property
    def family(self) -> AddrFamily:
        pfx = self.prefix
        if isinstance(pfx, IPv4Network):
            return AddrFamily.IPV4
        if isinstance(pfx, IPv6Network):
            return AddrFamily.IPV6

        raise TypeError(f'Expected prefix to be IPv4/v6Network but was type "{type(pfx)}"')
    
    @property
    def source_asn(self) -> int:
        return int(self.path.source_asn)
    
    @property
    def source_id(self) -> str:
        return str(self.path.source_id)
    
    @property
    def age(self) -> datetime:
        ts = int(self.path.age.seconds)
        return datetime.utcfromtimestamp(ts)
    
    @property
    def next_hops(self) -> List[Union[IPv4Address, IPv6Address]]:
        p = self.path.pattrs
        if find_attr(p, 'MpReachNLRI') is not None:
            h = list(find_attr(p, 'MpReachNLRI').next_hops)
            return [ip_address(hop) for hop in h]
        nh = find_attr(p, 'NextHopAttribute').next_hop
        return [ip_address(nh)]

    @staticmethod
    def find_in_local(subnet):
        subnet = ip_network(subnet)
        for l in LOCAL_IPS:
            if not isinstance(subnet, type(l)): # Ignore non-matching IP versions
                continue
            if subnet > l:
                return l
        return None

    def __iter__(self):
        d = {}
        d['prefix'] = self.prefix
        d['family'] = self.family
        d['source_id'] = self.source_id
        d['source_asn'] = self.source_asn
        d['neighbor'] = self.neighbor
        try:
            d['next_hops'] = self.next_hops
        except Exception as e:
            log.warning(f'Could not get next_hops due to exception: {type(e)} {str(e)}')
            d['next_hops'] = []
        try:
            d['asn_path'] = self.asn_path
        except Exception as e:
            log.warning(f'Could not get asn_path due to exception: {type(e)} {str(e)}')
            if self.find_in_local(d['prefix']) is not None:
                d['asn_path'] = [int(OUR_ASN)]
            else:
                d['asn_path'] = []
        try:
            d['communities'] = self.communities
        except Exception as e:
            log.warning(f'Could not get communities due to exception: {type(e)} {str(e)}')
            d['communities'] = []
        try:
            d['age'] = self.age
        except Exception as e:
            log.warning(f'Could not get age due to exception: {type(e)} {str(e)}')
            d['age'] = None
        
        for k, v in d.items():
            yield (k, v,)

