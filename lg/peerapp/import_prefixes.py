#!/usr/bin/env python3
import asyncio

import grpc
import grpc._channel
import logging

from asyncpg import Record
from flask_sqlalchemy import SQLAlchemy
from google.protobuf.pyext._message import RepeatedCompositeContainer
from typing import List, Union, Dict, Optional
from ipaddress import IPv4Address, IPv6Address, IPv4Network, IPv6Network, ip_address, ip_network
import asyncpg
from psycopg2.extras import Inet
from redis import Redis

from gobgp import gobgp_pb2, gobgp_pb2_grpc, attribute_pb2
from gobgp.attribute_pb2 import LargeCommunity
from gobgp.gobgp_pb2 import ListPathRequest, ListPathResponse, Family
from datetime import datetime
from lg import base
from lg.models import ASN, Prefix, Community
from lg.peerapp.settings import OUR_ASN, OUR_ASN_NAME, LOCAL_IPS, BLACKLIST_ROUTES, CHUNK_SIZE
from lg.base import get_redis, get_pg_pool
from lg.exceptions import GoBGPException
from privex.helpers import empty, asn_to_name, r_cache, FO, convert_datetime, DictObject

from lg.peerapp.types import AddrFamily, SanePath

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
    pg_conn: Optional[asyncpg.connection.Connection]
    
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
        
        self.path_tasks = {}
        
        self.loop = asyncio.get_event_loop()

        self.pg_conn = None
        self.pg_pool = self.loop.run_until_complete(get_pg_pool())

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
    def _get_as_name(self, asn: Union[int, str]) -> str:
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

    async def get_as_name(self, asn) -> Union[ASN, dict]:
        # Check if AS name is present in class memory cache
        if empty(asn):
            return dict(asn=None, as_name="Invalid ASN", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        if asn not in self._cache['asn_in_db']:
            async with self.pg_pool.acquire() as conn:
                as_name = await conn.fetchrow("SELECT * FROM asn WHERE asn.asn = $1 LIMIT 1;", asn)
                # If AS name not found in DB, then look it up and store it in the DB
                if as_name is None:
                    as_name = dict(
                        asn=asn, as_name=self._get_as_name(asn), created_at=datetime.utcnow(), updated_at=datetime.utcnow()
                    )
                    await conn.execute(
                        "INSERT INTO asn (asn, as_name, created_at, updated_at) VALUES ($1, $2, $3, $3);",
                        asn, self._get_as_name(asn), as_name['created_at']
                    )
            # Store AS name into memory cache
            self._cache['asn_in_db'][asn] = as_name
        return self._cache['asn_in_db'][asn]
    
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

    async def _store_path_task(self, task_id: int, path: SanePath):
        log.debug("[_store_path_task ID %d] Storing path %s", task_id, path)
        task = self.path_tasks['tasks'][task_id]
        res = False
        try:
            await self._store_path(path)
            res = True
            task['status'], task['message'] = 'success', f'Successfully stored {path}'
        except Exception as e:
            log.exception("[_store_path_task ID %d] Failed to store path %s", task_id, path)
            task['status'], task['message'] = 'fail', f'Failed to store path {path} - Exception: {type(e)} {str(e)}'
            self.path_tasks['failed_tasks'].append(dict(task))
        
        t = self.path_tasks['success_tasks'] if res else self.path_tasks['failed_tasks']
        t.append(dict(task))
        del self.path_tasks['tasks'][task_id]
        return res
    
    async def store_paths(self, family='v4'):
        """
        Iterates over :py:attr:`.sane_paths` and inserts/updates the appropriate prefix/asn/community objects
        into the database.

        :return:
        """
        db = self.db
        # session = db.session
        
        # loop = asyncio.get_running_loop()
        loop = self.loop
        # self.pg_conn = await get_pg()

        log.info(' >>> Importing IP%s prefixes from GoBGP into PostgreSQL', family)

        # total_prefixes = len(self.sane_paths)
        log.info('Creating AsyncIO task queue for importing prefixes...')
        i = 0
        
        pt = self.path_tasks = DictObject(tasks={}, failed_tasks=[], success_tasks=[])
        
        for path in self.parse_paths(family):
            if (i % 10000) == 0:
                log.info('Queued %s prefixes for import', i)
                # session.commit()
            pt.tasks[i] = dict(
                id=i,
                task=asyncio.create_task(self._store_path_task(i, path)),
                status='started',
                message=''
            )
            # tasks.append(asyncio.create_task(self._store_path(p)))
            # self.path_tasks.append(loop.call_soon(self._store_path, p))
            i += 1

            # session.add(pfx)

        # i = 0
        log.info('Saving %s paths to Postgres... this may take time (awaiting AsyncIO task queue)', len(pt.tasks))
        # await asyncio.gather(*tasks, return_exceptions=True)
        while len(pt.tasks) > 0:
            log.info(
                "Import Status ::: %d paths pending, %d paths imported, %d paths failed",
                len(pt.tasks), len(pt.success_tasks), len(pt.failed_tasks)
            )
            await asyncio.sleep(10)
        log.info("")
        
        for task in pt.failed_tasks:
            log.warning("[Failed Task %d] Message %s", task['id'], task['message'])
        # for i, t in enumerate(pt):
        #     if (i % CHUNK_SIZE) == 0:
        #         log.info('Saved %s out of %s prefixes.', i, len(pt))
        #     t.
        #     i += 1

        # loop.close()
        # session.commit()
        log.info(" >>> Finished. Imported %d IP%s paths - Failed to import %d paths",
                 len(pt.success_tasks), family, len(pt.failed_tasks))

        # log.info(' >>> Finished saving %s IP%s paths.', len(pt), family)

    async def _store_path(self, p: SanePath) -> Prefix:
        p_dic = dict(p)
        # Obtain AS name via in-memory cache, database cache, or DNS lookup
        await self.get_as_name(p.source_asn)
        asn_id = p.source_asn
        communities = list(p_dic['communities'])
        del p_dic['family']
        del p_dic['source_asn']
        del p_dic['first_hop']
        del p_dic['communities']
        for x, nh in enumerate(p_dic['next_hops']):
            p_dic['next_hops'][x] = Inet(nh)

        async with self.pg_pool.acquire() as conn:
            pfx = await conn.fetchrow(
                "SELECT * FROM prefix WHERE asn_id = $1 AND prefix.prefix = $2 LIMIT 1;",
                asn_id, p_dic['prefix']
            )   # type: Record
            
            # pfx = Prefix.query.filter_by(source_asn=asn_id, prefix=p_dic['prefix']).first()  # type: Prefix
            # new_pfx = dict(**p_dic, asn_id=asn_id, last_seen=datetime.utcnow())
            age = convert_datetime(p_dic.get('age'), fail_empty=False, if_empty=None)
            if age is not None:
                age = age.replace(tzinfo=None)
            if not pfx:
                await conn.execute(
                    "INSERT INTO prefix ("
                    "  asn_id, asn_path, prefix, next_hops, neighbor, ixp, last_seen, "
                    "  age, created_at, updated_at"
                    ")"
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10);",
                    asn_id, p_dic.get('asn_path', []), p_dic['prefix'], p_dic.get('next_hops', []),
                    p_dic.get('neighbor'), p_dic.get('ixp'), datetime.utcnow(), age,
                    datetime.utcnow(), datetime.utcnow()
                )
                
                pfx = await conn.fetchrow(
                    "SELECT * FROM prefix WHERE asn_id = $1 AND prefix.prefix = $2 LIMIT 1;",
                    asn_id, p_dic['prefix']
                )
            else:
                await conn.execute(
                    "UPDATE prefix SET asn_path = $1, next_hops = $2, neighbor = $3, ixp = $4, last_seen = $5, "
                    "age = $6, updated_at = $7 WHERE prefix = $8 AND asn_id = $9;",
                    p_dic.get('asn_path', []), p_dic.get('next_hops', []),
                    p_dic.get('neighbor'), p_dic.get('ixp'), datetime.utcnow(), age,
                    datetime.utcnow(), p_dic['prefix'], asn_id
                )
                # for k, v in p_dic.items():
                #     setattr(pfx, k, v)
            
            for c in communities:   # type: LargeCommunity
                if c not in self._cache['community_in_db']:
                    try:
                        await conn.execute(
                            "insert into community (id, created_at, updated_at) values ($1, $2, $2);",
                            c, datetime.utcnow()
                        )
                    except asyncpg.UniqueViolationError:
                        pass
                
                try:
                    await conn.execute(
                        "insert into prefix_communities (prefix_id, community_id) values ($1, $2);",
                        pfx['id'], c
                    )
                except asyncpg.UniqueViolationError:
                    pass
                # pfx.communities.append(comm)
        return pfx

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
        segments = r_asn.segments
        return [] if len(segments) < 1 else list(segments[0].numbers)
    
    @property
    def communities(self) -> List[int]:
        c = find_attr(self.path.pattrs, 'communities')
        return [] if not c else list(c.communities)
    
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
        if empty(self.path.source_asn, zero=True):
            if len(self.asn_path) > 0:
                return int(self.asn_path[0])
            return OUR_ASN
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

    def __str__(self):
        return f"<PathParser prefix='{self.prefix}' source_asn='{self.source_asn}'" \
               f" communities='{self.communities}' asn_path='{self.asn_path}' >"
    
    def __repr__(self):
        return self.__str__()

