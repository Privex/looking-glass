import json
import logging
import traceback
from typing import Tuple
from uuid import uuid4

from flask import Response, request, render_template
from flask.json import jsonify

from lookingglass.core import flask, RMQ_QUEUE, get_rmq_chan, get_redis
from lookingglass.helpers import validate_host

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


@flask.route('/')
def index():
    return render_template('index.html')


@flask.route('/api/v1/trace', defaults=dict(proto='any'), methods=['POST'])
@flask.route('/api/v1/trace/<proto>', methods=['POST'])
def api_trace(proto):
    """

    Example::

        POST /api/v1/trace
        host=8.8.4.4

        HTTP/1.1 200 OK

        {
            "error": false,
            "result": { "req_id": "abcd123-defa", "action": "trace", "host": "8.8.4.4", "proto": "any" }
        }


    :return: JSON dict()

    Result::

        {
            error: bool - True if there's an error ( check ``message`` ),
            result: dict = {
                req_id: str = The UUID for this request to check the status of it
                action: str = The action you requested on the given host,
                host: str = The IP / hostname you requested to trace,
                proto: str = The protocol that will be used for the trace
            }
        }


    """
    host = request.values.get('host', None)
    host = host.strip() if host is not None else None

    # Validate the passed data before sending it to redis + rabbitmq
    validators = (
        ('NO_HOST', not host), ('INV_HOST', not validate_host(host, proto)),
        ('INV_PROTO', proto not in ['any', 'ipv4', 'ipv6'])
    )
    for err, check in validators:
        if check: return json_err(err)

    # Generate a unique request ID, and an action object to send via rabbitmq + store in redis
    req_id = str(uuid4())
    _data = dict(req_id=req_id, action='trace', host=host, proto=proto, status='waiting')
    data = json.dumps(_data)
    log.debug('/api/v1/trace - host: %s req_id: %s', host, req_id)

    # Store the JSON action details in Redis under the request ID
    r = get_redis()
    r.hset('lg_requests', req_id, data)

    # Send the action details via RabbitMQ for processing by background workers
    chan = get_rmq_chan()
    chan.queue_declare(RMQ_QUEUE)
    chan.basic_publish(exchange='', routing_key=RMQ_QUEUE, body=data)

    # Return the action details to the client for status querying
    return jsonify(error=False, result=_data)


@flask.route('/api/v1/ping', defaults=dict(proto='any'), methods=['POST'])
@flask.route('/api/v1/ping/<proto>', methods=['POST'])
def api_ping(proto):
    """

    Example::

        POST /api/v1/trace
        host=8.8.4.4

        HTTP/1.1 200 OK

        {
            "error": false,
            "result": { "req_id": "abcd123-defa", "action": "trace", "host": "8.8.4.4", "proto": "any" }
        }


    :return: JSON dict()

    Result::

        {
            error: bool - True if there's an error ( check ``message`` ),
            result: dict = {
                req_id: str = The UUID for this request to check the status of it
                action: str = The action you requested on the given host,
                host: str = The IP / hostname you requested to trace,
                proto: str = The protocol that will be used for the trace
            }
        }


    """
    host = request.values.get('host', None)
    host = host.strip() if host is not None else None

    # Validate the passed data before sending it to redis + rabbitmq
    validators = (
        ('NO_HOST', not host), ('INV_HOST', not validate_host(host, proto)),
        ('INV_PROTO', proto not in ['any', 'ipv4', 'ipv6'])
    )
    for err, check in validators:
        if check: return json_err(err)

    # Generate a unique request ID, and an action object to send via rabbitmq + store in redis
    req_id = str(uuid4())
    _data = dict(req_id=req_id, action='ping', host=host, proto=proto, status='waiting')
    data = json.dumps(_data)
    log.debug('/api/v1/ping - host: %s req_id: %s', host, req_id)

    # Store the JSON action details in Redis under the request ID
    r = get_redis()
    r.hset('lg_requests', req_id, data)

    # Send the action details via RabbitMQ for processing by background workers
    chan = get_rmq_chan()
    chan.queue_declare(RMQ_QUEUE)
    chan.basic_publish(exchange='', routing_key=RMQ_QUEUE, body=data)

    # Return the action details to the client for status querying
    return jsonify(error=False, result=_data)


@flask.route('/api/v1/status/<req_id>')
def api_status(req_id):
    """

    Example::

        GET /api/v1/status/3aff7567-8766-44d4-8c1a-d6c33c1e1ca2

        HTTP/1.1 200 OK

        {
          "error": false,
          "result": {
            "action": "trace",
            "host": "2a07:e00::666",
            "proto": "any",
            "req_id": "3aff7567-8766-44d4-8c1a-d6c33c1e1ca2",
            "result": "Very Long String Containing Results of trace/ping etc.",
            "status": "finished"
          }
        }

    :param req_id:
    :return:

    Result format::

        {
            error: bool - True if there's an error ( check ``message`` ),
            result: dict = {
                req_id: str = The UUID for this request to check the status of it
                action: str = The action you requested on the given host,
                host: str = The IP / hostname you requested to trace,
                proto: str = The protocol that was used for the trace,
                status: str = Either ``waiting`` or ``finished`` ,
                result: str = A long multi-line string containing the results of the trace/ping etc.
            }
        }


    """
    # Look up the original request details in the lg_requests hash set
    r = get_redis()
    req_attempt = r.hget('lg_requests', req_id)
    if not req_attempt:
        return json_err('NOT_FOUND')

    req_attempt = json.loads(req_attempt)
    # If there are no results for this request, just return the request details
    data = req_attempt

    # If there are results, merge them with the original request information
    results = r.hget('lg_results', req_id)
    if results is not None:
        results = json.loads(results)
        data = {**req_attempt, 'status': 'finished', **results}

    return jsonify(error=False, result=data)

