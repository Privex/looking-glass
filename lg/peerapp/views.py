import logging
import traceback
from ipaddress import ip_network, IPv4Network
from typing import Tuple
from flask import Response, request, Blueprint
from flask.json import jsonify
from privex.helpers import empty, r_cache
from sqlalchemy.orm import Query
from lg import base
from lg.models import Prefix

flask = Blueprint('peerapp', __name__, template_folder='templates')

log = logging.getLogger(__name__)

# format: (err_code, (message, status_code))
API_ERRORS = (
    ('NO_REQUEST', ("No request was sent.", 400)),
    ('INV_HOST', ("IP address / Hostname is invalid", 400)),
    ('INV_PROTO', ("Invalid IP protocol, choose one of 'any', 'ipv4', 'ipv6'", 400)),
    ('NOT_FOUND', ("No records could be found for that object", 404)),
    ('NO_HOST', ('No IP Address / Hostname specified', 400)),
    ('UNKNOWN', ("Something went wrong and we don't know why...", 500)),
)

_, db, migration = base.get_app()


def json_err(err_code: str) -> Tuple[Response, int]:
    """
    Helper function, looks up err_code in `API_ERRORS`, generates json error and returns error code
    Can be used in flask views like this:

        >>> # Would return an error generated from jsonify(), and set the status code too.
        >>> return json_err('NO_HOST')

    :param err_code: The string error code as defined in `API_ERRORS` that you want to return
    :return: (jsonify(), status_code)
    """
    err_dict = dict(API_ERRORS)
    if err_code not in err_dict or err_code == "UNKNOWN":
        log.error('An json_err was called, but it is not in the API_ERRORS list...')
        log.error(traceback.format_exc())
        err_code = 'UNKNOWN'
    err = err_dict[err_code]

    return jsonify(error=True, message=err[0], err_code=err_code), err[1]


@flask.route('/api/v1/asn_prefixes')
@flask.route('/api/v1/asn_prefixes/')
@r_cache('lg_asn_aggr')
def asn_prefixes():
    """
    Endpoint /api/v1/asn_prefixes/ - count the number of prefixes advertised by each ASN,
    aggregating them by family (v4 and v6).

    Example:

        GET https://lg.privex.io/api/v1/asn_prefixes/

    **Response:**

    .. code-block:: json

        {
          "8896": {
            "as_name": "XFIBER-AS, NO",
            "asn": 8896,
            "prefixes": 41,
            "v4": 41,
            "v6": 0
          },
          "210083": {
            "as_name": "Privex Inc.",
            "asn": 210083,
            "prefixes": 5,
            "v4": 1,
            "v6": 4
          }
        }


    """

    asn_map = {}

    query = 'SELECT a.asn, a.as_name, COUNT(p.prefix) as total_prefixes ' \
            'FROM prefix p INNER JOIN asn a ON a.asn = p.asn_id ' \
            'WHERE p.prefix << :pfx GROUP BY a.asn ORDER BY total_prefixes DESC;'

    pfxs_v4 = db.session.execute(query, dict(pfx='0.0.0.0/0'))
    pfxs_v6 = db.session.execute(query, dict(pfx='::/0'))

    for asn, asname, total_prefixes in pfxs_v4:
        if asn not in asn_map: asn_map[asn] = dict(v4=0, v6=0)
        asn_map[asn]['asn'] = asn
        asn_map[asn]['as_name'] = asname
        asn_map[asn]['v4'] = int(total_prefixes)

    for asn, asname, total_prefixes in pfxs_v6:
        if asn not in asn_map: asn_map[asn] = dict(v4=0, v6=0)
        asn_map[asn]['asn'] = asn
        asn_map[asn]['as_name'] = asname
        asn_map[asn]['v6'] = int(total_prefixes)
    for k, a in asn_map.items():
        a['prefixes'] = a['v6'] + a['v4']

    # return asn_map

    return jsonify(asn_map)


@flask.route('/api/v1/prefixes')
@flask.route('/api/v1/prefixes/')
@r_cache(lambda: f'lg_prefixes:{request.values.get("asn")}:{request.values.get("family")}')
def list_prefixes():
    """
    Endpoint /api/v1/prefixes/ - list all known prefixes, or filter by ASN / Family

    GET options::

        - `asn` (int) - An AS number to filter prefixes by, e.g. `210083` to see prefixes by Privex
        - `family` (str) - Either `v4` or `v6` to only show v4 or v6 prefixes

    **Example::**

        # Get ALL prefixes stored in the prefix DB
        GET https://lg.privex.io/api/v1/prefixes/

        # Get both IPv4 and v6 prefixes that have a source_asn of `210083` (Privex's ASN)
        GET https://lg.privex.io/api/v1/prefixes/?asn=210083

        # Get only IPv6 prefixes with a source_asn of `210083` (Privex's ASN)
        GET https://lg.privex.io/api/v1/prefixes/?asn=210083&family=v6

    **Response:**

    .. code-block:: json

        [
            {
                "age": "Tue, 20 Aug 2019 22:48:32 GMT",
                "as_name": "Privex Inc.",
                "asn_path": [210083],
                "communities": [300, 400],
                "family": "v4",
                "first_hop": "185.130.44.1",
                "ixp": "N/A",
                "last_seen": "Wed, 21 Aug 2019 02:30:00 GMT",
                "neighbor": null,
                "next_hops": ["185.130.44.1"],
                "prefix": "185.130.44.0/24",
                "source_asn": 210083
            },
        ]

    """
    v = request.values
    asn = v.get('asn')
    family = v.get('family')
    # selector = {}

    p = Prefix.query   # type: Query

    if not empty(asn):
        p = p.filter_by(asn_id=int(asn))

    if not empty(family):
        pfx = '0.0.0.0/0' if family == 'v4' else '::/0'
        p = p.filter(Prefix.prefix.op('<<')(pfx))

    p = p.join(Prefix.communities, Prefix.source_asn).all()

    res = []
    for z in p:    # type: Prefix
        ntw = ip_network(z.prefix)
        is_v4 = isinstance(ntw, IPv4Network)
        res.append(
            dict(
                prefix=z.prefix, age=z.age, source_asn=z.source_asn.asn, as_name=z.source_asn.as_name,
                communities=[c.id for c in z.communities], family='v4' if is_v4 else 'v6', first_hop=z.next_hops[0],
                next_hops=z.next_hops, ixp=z.ixp, last_seen=z.last_seen, neighbor=z.neighbor, asn_path=z.asn_path
            )
        )

    return jsonify(res)
