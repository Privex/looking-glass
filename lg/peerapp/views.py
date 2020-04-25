import logging
import traceback
from datetime import datetime, timedelta
from ipaddress import ip_network, IPv4Network
from typing import Tuple, Union, List
from flask import Response, request, Blueprint
from flask.json import jsonify
from flask_sqlalchemy import BaseQuery
from privex.helpers import empty, r_cache, is_true, Git, empty_if, ip_is_v4, ip_is_v6
from sqlalchemy.orm import Query
from lg import base
from lg.exceptions import InvalidIP
from lg.models import Prefix, IPFilter
from getenv import env

from lg.peerapp.settings import PREFIX_TIMEOUT, PREFIX_TIMEOUT_WARN

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


@flask.route('/api/v1/info')
@flask.route('/api/v1/info/')
@r_cache('lg_api_info', 30)
def lg_info():
    last_prefix = Prefix.latest_seen_prefixes()
    
    data = dict(
        message="This is an instance of Privex Looking Glass. Released open source under GNU AGPL v3. "
                "(C) 2020 Privex Inc. - https://github.com/Privex/looking-glass",
        git_commit=base.GIT_COMMIT,
        git_tag=base.GIT_TAG,
        git_branch=base.GIT_BRANCH,
        latest_prefix_time=last_prefix.last_seen,
        latest_prefix=last_prefix.to_dict(),
        prefix_timeout=PREFIX_TIMEOUT,
        prefix_timeout_warn=PREFIX_TIMEOUT_WARN,
        total_prefixes=Prefix.query.count(),

    )
    return jsonify(data)


@flask.route('/api/v1/asn_prefixes')
@flask.route('/api/v1/asn_prefixes/')
@r_cache(lambda: f'lg_asn_aggr:{request.values.get("asn")}')
def asn_prefixes():
    """
    Endpoint /api/v1/asn_prefixes/ - count the number of prefixes advertised by each ASN,
    aggregating them by family (v4 and v6).

    GET options::

        - `asn` (int) - Fetch results for just one particular ASN number, e.g. `210083`
                        to see data for Privex. If not supplied, fetches data for all ASNs.

    **Example:**

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

    v = request.values
    asn = v.get('asn')
    asn_map = {}
    last_seen = (Prefix.latest_seen_prefixes().last_seen - timedelta(seconds=PREFIX_TIMEOUT))
    
    if empty(asn):
        query = 'SELECT a.asn, a.as_name, COUNT(p.prefix) as total_prefixes ' \
                'FROM prefix p INNER JOIN asn a ON a.asn = p.asn_id ' \
                'WHERE p.prefix << :pfx AND p.last_seen > :last_seen GROUP BY a.asn ORDER BY total_prefixes DESC;'
        pfxs_v4 = db.session.execute(query, dict(pfx='0.0.0.0/0', last_seen=last_seen))
        pfxs_v6 = db.session.execute(query, dict(pfx='::/0', last_seen=last_seen))
    else:
        query = 'SELECT a.asn, a.as_name, COUNT(p.prefix) as total_prefixes ' \
                'FROM prefix p INNER JOIN asn a ON a.asn = p.asn_id ' \
                'WHERE p.prefix << :pfx AND p.last_seen > :last_seen AND a.asn = :asn GROUP BY a.asn;'
        pfxs_v4 = db.session.execute(query, dict(pfx='0.0.0.0/0', asn=asn, last_seen=last_seen))
        pfxs_v6 = db.session.execute(query, dict(pfx='::/0', asn=asn, last_seen=last_seen))

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

    return jsonify(asn_map)


@flask.route('/api/v1/prefix/<prefix>/')
@flask.route('/api/v1/prefix/<prefix>/<cidr>')
@flask.route('/api/v1/prefix/<prefix>/<cidr>/')
@r_cache(
    lambda prefix, cidr=None: f'lg_prefix:{prefix}:{cidr}:{request.values.get("asn")}:{request.values.get("exact")}'
                              f':{request.values.get("limit")}:{request.values.get("skip")}'
)
def get_prefix(prefix: str, cidr: int = None):
    # If there's no CIDR number, then we treat 'prefix' as a singular IP address
    is_single = False
    if empty(cidr):
        try:
            cidr = 32 if ip_is_v4(prefix) else 128
        except ValueError:
            raise InvalidIP(f"IP / Prefix '{prefix}' is invalid.")
        is_single = True
    
    v = request.values
    exact, asn = is_true(v.get('exact', True)), v.get('asn', None)
    asn = int(asn) if not empty(asn, zero=True) else None
    limit, skip = validate_limits(v.get('limit'), v.get('skip'))
    
    # For individual IPs, we search for the prefix(es) that contains the IP.
    # For normal CIDR subnets, we search for the matching prefix and any sub-prefixes within that subnet.
    _filter = IPFilter.CONTAINS_EQUAL if is_single else IPFilter.WITHIN_EQUAL
    _pfx = f"{prefix}" if is_single else f"{prefix}/{cidr}"
    
    p: Union[Prefix, BaseQuery] = Prefix.filter_prefix(_pfx, exact=exact, asn=asn, op=_filter)
    
    # If the 'exact' parameter is set to True (default), we return just the matching prefix, if it's found.
    if exact:
        p = p.first()
        if not p:
            return json_err('NOT_FOUND')
        return jsonify(error=False, result=p.to_dict())

    latest_prefix: Prefix = Prefix.latest_seen_prefixes(limit=1, single=True)
    latest_last_seen = latest_prefix.last_seen

    p = p.filter(Prefix.last_seen > (latest_last_seen - timedelta(seconds=PREFIX_TIMEOUT)))
    # For non-exact searches, we return a list of prefixes that match the query
    total = p.count()
    p: List[Prefix] = list(p.slice(skip, skip + limit))
    return jsonify(
        error=False,
        count=len(p),
        total=total,
        pages=int(total / limit),
        result=[k.to_dict() for k in p]
    )


@flask.route('/api/v1/prefixes')
@flask.route('/api/v1/prefixes/')
@r_cache(lambda: f'lg_prefixes:{request.values.get("asn")}:{request.values.get("family")}:{request.values.get("limit")}:{request.values.get("skip")}')
def list_prefixes():
    """
    Endpoint /api/v1/prefixes/ - list all known prefixes, or filter by ASN / Family

    GET options::

        - `asn` (int) - An ASN number to filter prefixes by, e.g. `210083` to see prefixes by Privex
        - `family` (str) - Either `v4` or `v6` to only show v4 or v6 prefixes
        - `limit` (int) - Limit result set to this many prefixes. If not supplied, defaults to the
                          VUE_APP_DEFAULT_API_LIMIT .env setting. Cannot be more than the VUE_APP_MAX_API_LIMIT
                          .env setting.
        - `skip` (int) - Skips this amount of prefixes before returning results. Can be used in
                         combination with limit to paginate large data sets.

    **Example::**

        # Get ALL prefixes stored in the prefix DB
        GET https://lg.privex.io/api/v1/prefixes/

        # Get both IPv4 and v6 prefixes that have a source_asn of `210083` (Privex's ASN)
        GET https://lg.privex.io/api/v1/prefixes/?asn=210083

        # Get only IPv6 prefixes with a source_asn of `210083` (Privex's ASN)
        GET https://lg.privex.io/api/v1/prefixes/?asn=210083&family=v6

        # Get both IPv4 and v6 prefixes that have a source_asn of `210083` (Privex's ASN), limiting
        # results to the first 50 prefixes
        GET https://lg.privex.io/api/v1/prefixes/?asn=210083&limit=50

        # Get both IPv4 and v6 prefixes that have a source_asn of `210083` (Privex's ASN), showing
        # the second batch of 50 prefixes
        GET https://lg.privex.io/api/v1/prefixes/?asn=210083&limit=50&skip=50

    **Response:**

        There will be a `pages` object at the start of the response, to support pagination. This
        object indicates how many pages are necessary to retrieve all data depending on the `limit`
        GET option.

    .. code-block:: json

        {
            "pages":
                {
                    "all": 1,
                    "v4": 1,
                    "v6": 1,
                },

            "prefixes":
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
        }

    """
    v = request.values
    asn, family = v.get('asn'), v.get('family')
    limit, skip = validate_limits(v.get('limit'), v.get('skip'))

    latest_prefix: Prefix = Prefix.latest_seen_prefixes(limit=1, single=True)
    latest_last_seen = latest_prefix.last_seen
    
    p = Prefix.query   # type: Query

    if not empty(asn):
        p = p.filter_by(asn_id=int(asn))

    if not empty(family):
        pfx = '0.0.0.0/0' if family == 'v4' else '::/0'
        p = p.filter(Prefix.prefix.op('<<')(pfx))

    p = p.filter(Prefix.last_seen > (latest_last_seen - timedelta(seconds=PREFIX_TIMEOUT)))

    p = p.order_by(Prefix.id).slice(skip, skip + limit).from_self()
    p = p.join(Prefix.communities, Prefix.source_asn).order_by(Prefix.id).all()

    res = []
    for z in p:    # type: Prefix
        # ntw = ip_network(z.prefix)
        # is_v4 = isinstance(ntw, IPv4Network)
        res.append(z.to_dict())

    asn_data = asn_prefixes().get_json()

    v4_count = 0
    v6_count = 0
    for value in asn_data.values():
        v4_count += value['v4']
        v6_count += value['v6']

    response = {}
    response['pages'] = {
            'all': int((v4_count + v6_count) / limit) + ((v4_count + v6_count) % limit > 0),
            'v4': int(v4_count / limit) + (v4_count % limit > 0),
            'v6': int(v6_count / limit) + (v6_count % limit > 0)
        }
    response['prefixes'] = res

    return jsonify(response)


def validate_limits(limit, skip) -> Tuple[int, int]:
    limit, skip = int(empty_if(limit, base.DEFAULT_API_LIMIT)), int(empty_if(skip, 0))
    limit = base.MAX_API_LIMIT if limit > base.MAX_API_LIMIT else limit
    limit = 1 if limit < 1 else limit
    skip = 0 if skip < 0 else skip
    return limit, skip


def setup_api_routes():
    base.add_api_route(
        'info',
        base.APIRoute(
            endpoint='/api/v1/info/',
            description="Returns basic status/version information about the running Privex Looking Glass instance"
        )
    )
    base.add_api_route(
        'asn_prefixes',
        base.APIRoute(
            endpoint='/api/v1/asn_prefixes/',
            description="Calculates the number of v4, v6 and total prefixes for all ASNs, or a singular ASN",
            get_params=dict(
                asn=base.APIParam(value_type='int', required=False, description="Display stats for just this ASN instead of all ASNs.")
            )
        )
    )
    base.add_api_route(
        'get_prefix',
        base.APIRoute(
            endpoint='/api/v1/get_prefix/<address>/<cidr>',
            description="Calculates the number of v4, v6 and total prefixes for all ASNs, or a singular ASN",
            get_params=dict(
                asn=base.APIParam(value_type='int', required=False, description="Match only prefixes for this ASN"),
                exact=base.APIParam(
                    value_type='bool', required=False,
                    description="(Default: true) true = find this specific prefix. false = find this prefix and any sub-prefixes"
                                "contained within the CIDR subnet."
                ),
            ),
            url_params=dict(
                address=base.APIParam(
                    value_type='str', required=True, description="The IP portion of the prefix being looked up"
                ),
                cidr=base.APIParam(
                    value_type='int', required=True, description="The CIDR subnet divider (1-32 for IPv4, 1-128 for IPv6)"
                )
            )
        )
    )
    
    base.add_api_route(
        'list_prefixes',
        base.APIRoute(
            endpoint='/api/v1/prefixes/',
            description="Calculates the number of v4, v6 and total prefixes for all ASNs, or a singular ASN",
            get_params=dict(
                asn=base.APIParam(value_type='int', required=False, description="Match only prefixes for this ASN"),
                family=base.APIParam(value_type='str', required=False, description="Either `v4` or `v6` to only show v4 or v6 prefixes"),
                limit=base.APIParam(value_type='int', required=False,
                                    description=f"Limit result set to this many prefixes (max: {base.MAX_API_LIMIT})"),
                skip=base.APIParam(value_type='int', required=False,
                                   description=f"Skips this amount of prefixes before returning results (for pagination)"),
            )
        )
    )
