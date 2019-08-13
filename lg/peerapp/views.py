import logging
import traceback
from typing import Tuple

from flask import Response, request, render_template, Blueprint
from flask.json import jsonify
from privex.helpers import empty
from lg.base import get_couch, cf
# from peerapp.helpers import validate_host
from lg.exceptions import DatabaseConnectionFail

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

try:
    couch = get_couch()
    db = couch[cf['COUCH_DB']]
except (Exception, ConnectionRefusedError):
    raise DatabaseConnectionFail('ERROR: Cannot connect to CouchDB. Refusing to start peerapp.')


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


@flask.route('/api/v1/asn_prefixes/<method>')
def asn_prefixes(method):
    if method not in ['by_family', 'all']:
        return json_err('NOT_FOUND')
    data = db.get_view_result(f'_design/asn_prefixes', method, reduce=True, group=True)
    res = {}

    for r in data:
        if method == 'by_family':
            asn, asname, family = tuple(r['key'])
            if asn not in res:
                res[asn] = dict(asn=asn, as_name=asname, v4=0, v6=0)
            res[asn][family] = r['value']
        else:
            asn, asname = tuple(r['key'])
            res[asn] = dict(asn=asn, as_name=asname, prefixes=r['value'])

    return jsonify(res)


@flask.route('/api/v1/prefixes')
def list_prefixes():
    v = request.values
    asn = v.get('asn')
    family = v.get('family')
    selector = {}
    if not empty(family):
        selector['family'] = family
    if not empty(asn):
        selector['source_asn'] = int(asn)
    if empty(selector, itr=True):
        selector = {"_id": { "$gt": None }}
    return jsonify(list(db.get_query_result(selector)))
