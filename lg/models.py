import datetime
import logging
from sqlalchemy.dialects import postgresql

from lg.base import get_app

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


class Prefix(db.Model):
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

    created_at = db.Column(db.DateTime(), default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime(), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class Community(db.Model):
    id = db.Column(db.Integer(), primary_key=True, autoincrement=False)
    name = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime(), default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime(), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


