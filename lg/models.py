import datetime
import logging
from enum import Enum
from ipaddress import ip_network, IPv4Network
from typing import Union

from flask_sqlalchemy import BaseQuery
from privex.helpers import empty, ip_is_v4, r_cache
from sqlalchemy.dialects import postgresql

from lg.base import get_app
from lg.peerapp.settings import PREFIX_TIMEOUT_WARN

log = logging.getLogger(__name__)

_, db, _ = get_app()

Session = db.sessionmaker()


class ASN(db.Model):
    __tablename__ = 'asn'
    asn = db.Column(db.Integer, primary_key=True, nullable=False, autoincrement=False)
    as_name = db.Column(db.String(255), nullable=True)

    prefixes = db.relationship('Prefix', backref='source_asn')

    created_at = db.Column(db.DateTime(), default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime(), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def __repr__(self):
        return f'<ASN {self.asn} // {self.as_name}>'


prefix_communities = db.Table(
    'prefix_communities',
    db.Column('prefix_id', db.Integer, db.ForeignKey('prefix.id'), primary_key=True),
    db.Column('community_id', db.Integer, db.ForeignKey('community.id'), primary_key=True),
)


class IPFilter(Enum):
    EQUAL = "="
    WITHIN = "<<"
    WITHIN_EQUAL = "<<="
    CONTAINS = ">>"
    CONTAINS_EQUAL = ">>="
    NOT_EQUAL = "<>"


class Prefix(db.Model):
    PREFIX_FILTER = IPFilter
    
    id = db.Column(db.Integer, primary_key=True)
    asn_id = db.Column(db.Integer, db.ForeignKey('asn.asn'), nullable=False)
    asn_path = db.Column(postgresql.ARRAY(db.Integer, dimensions=1), nullable=True)
    prefix = db.Column(postgresql.CIDR(), nullable=False)
    next_hops = db.Column(postgresql.ARRAY(postgresql.INET(), dimensions=1), nullable=True)
    neighbor = db.Column(postgresql.INET(), nullable=True)
    ixp = db.Column(db.String(255), default='N/A', server_default='N/A')
    last_seen = db.Column(db.DateTime, nullable=True)
    age = db.Column(db.DateTime, nullable=True)
    communities = db.relationship('Community', secondary=prefix_communities, lazy='subquery',
                                  backref=db.backref('prefixes', lazy=True))

    @property
    def is_stale(self):
        latest_prefix_seen = Prefix.latest_seen_prefixes().last_seen
        if (latest_prefix_seen - self.last_seen) > datetime.timedelta(seconds=PREFIX_TIMEOUT_WARN):
            return True
        return False

    @classmethod
    def filter_prefix(cls, prefix: str, exact=True, op: IPFilter = IPFilter.WITHIN_EQUAL, asn=None):
        """
        
        Find an exact prefix::
            >>> Prefix.filter_prefix('218.101.128.0/20').first()
            <Prefix id=4551 asn_id=6939 prefix='218.101.128.0/20' last_seen='2020-04-24 21:40:12.676119' >
        
        Find ``prefix`` or prefixes within that prefix::
        
            >>> Prefix.filter_prefix('1.255.0.0/16', exact=False).all()
            [<Prefix id=80611 asn_id=6939 prefix='1.255.3.0/24' last_seen='2020-04-24 21:39:07.360731' >,
             <Prefix id=58224 asn_id=6939 prefix='1.255.6.0/24' last_seen='2020-04-24 21:41:17.712987' >,
             <Prefix id=17079 asn_id=6939 prefix='1.255.30.0/24' last_seen='2020-04-24 21:38:52.963183' >,
             <Prefix id=41095 asn_id=6939 prefix='1.255.48.0/22' last_seen='2020-02-19 04:28:54.447422' >,
             <Prefix id=19733 asn_id=6939 prefix='1.255.48.0/23' last_seen='2020-02-19 04:30:00.292189' >,
            ]
        
        Find the prefix(es) that contain the IP ``prefix``::
        
            >>> Prefix.filter_prefix('1.255.78.50', exact=False, op=IPFilter.CONTAINS).all()
            [
                <Prefix id=19339 asn_id=6939 prefix='1.255.78.0/24' last_seen='2020-04-24 21:40:05.828405' >
            ]
        
        :param asn:
        :param prefix:
        :param exact:
        :param op:
        :return:
        """
        # return cls.query.filter(cls.prefix.op('>>')(prefix))
        q = cls.query if empty(asn, zero=True) else cls.query.filter_by(asn_id=asn)
        
        if exact:
            return q.filter(cls.prefix == prefix).order_by('prefix')
        
        op = op.value
        return q.filter(cls.prefix.op(op)(prefix)).order_by('prefix')

    @classmethod
    @r_cache(lambda cls, limit=1, single=True: f'lg_latest_seen:{limit}:{single}', 60)
    def latest_seen_prefixes(cls, limit=1, single=True) -> Union["Prefix", BaseQuery]:
        """
        
        With no args, returns a :class:`.Prefix` with the newest :attr:`.last_seen` time::
        
            >>> Prefix.latest_seen_prefixes()
            <Prefix id=4422 asn_id=394354 prefix='2620:10a:80ec::/48' last_seen='2020-04-24 21:54:01.691170' >
        
        With ``limit`` arg, returns a query output object, allowing for additional query options to be added::
            
            >>> pf = Prefix.latest_seen_prefixes(limit=100)
            >>> q = pf.from_self().filter(Prefix.asn_id == 6939)
            >>> q.all()
            [<Prefix id=156992 asn_id=6939 prefix='2402:2700:32::/48' last_seen='2020-04-24 21:54:01.645590' >,
             <Prefix id=177851 asn_id=6939 prefix='2401:4900:5190::/48' last_seen='2020-04-24 21:54:01.641850' >,
             <Prefix id=139661 asn_id=6939 prefix='2a0e:b107:96::/48' last_seen='2020-04-24 21:54:01.640545' >,
            ]
        
        
        :param int limit:   Number of results to retrieve
        :param bool single: If True, and ``limit`` is ``1``, will return the first :class:`.Prefix` directly, instead of a query object.
        
        :return flask_sqlalchemy.BaseQuery q: When ``limit`` is more than 1 (or ``single`` is False), a :class:`.BaseQuery`
                                              object is returned.
        
        :return Prefix p: When ``limit`` is 1 and ``single`` is True, a :class:`.Prefix` object is returned.
        """
        if limit == 1 and single:
            return cls.query.order_by(cls.last_seen.desc()).first()
        return cls.query.order_by(cls.last_seen.desc()).limit(limit)

    created_at = db.Column(db.DateTime(), default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime(), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def to_dict(self) -> dict:
        z = self
        is_v4 = isinstance(ip_network(z.prefix), IPv4Network)
        
        return dict(
            id=z.id, prefix=z.prefix, age=z.age, source_asn=z.source_asn.asn, as_name=z.source_asn.as_name,
            communities=[c.id for c in z.communities], family='v4' if is_v4 else 'v6', first_hop=z.next_hops[0],
            next_hops=z.next_hops, ixp=z.ixp, last_seen=z.last_seen, neighbor=z.neighbor, asn_path=z.asn_path,
            created_at=z.created_at, stale=z.is_stale
        )
    
    def __str__(self):
        return f"<Prefix id={self.id} asn_id={self.asn_id} prefix='{self.prefix}' last_seen='{self.last_seen}' >"
    
    def __repr__(self):
        return self.__str__()


class Community(db.Model):
    id = db.Column(db.Integer(), primary_key=True, autoincrement=False)
    name = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime(), default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime(), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


