"""

Background runner/worker for looking glass, handles incoming ping/mtr requests from the queue.

Copyright::
    +===================================================+
    |                 © 2019 Privex Inc.                |
    |               https://www.privex.io               |
    +===================================================+
    |                                                   |
    |        Flask Network Looking Glass                |
    |                                                   |
    |        Core Developer(s):                         |
    |                                                   |
    |          (+)  Chris (@someguy123) [Privex]        |
    |                                                   |
    +===================================================+

"""
import json
import logging
import subprocess
from json import JSONDecodeError

from pika import spec
from pika.adapters.blocking_connection import BlockingChannel, BlockingConnection
from redis import Redis

from lg.exceptions import InvalidHostException, MissingArgsException
from lg.lookingglass.helpers import validate_host, v4_protos, v6_protos

log = logging.getLogger(__name__)


class Runner:

    def __init__(self, mq_conn: BlockingConnection, queue: str, redis: Redis):
        log.debug('Runner initialising...')
        self.mq_conn, self.queue, self.redis = mq_conn, queue, redis

        self.ACTIONS = {
            'trace': self.trace,
            'ping': self.ping
        }

        chan = self.chan = mq_conn.channel()   # type: BlockingChannel
        chan.queue_declare(queue=queue)

    def run(self, msg_count: int = 1):
        log.debug('Preparing to consume from queue %s', self.queue)

        chan = self.chan
        chan.basic_qos(prefetch_count=msg_count)
        chan.basic_consume(queue=self.queue, on_message_callback=self.callback, auto_ack=False)
        log.debug('Starting consuming for queue %s', self.queue)
        chan.start_consuming()

    def callback(self, ch: BlockingChannel, method: spec.Basic.Deliver, properties: spec.BasicProperties, body: bytes):
        log.debug(' -> Received ch: %s meth: %s props: %s body: %s', ch, method, properties, body)
        b = body.decode()
        try:
            # General format: {req_id, action, host}
            act = json.loads(b)   # type: dict
            log.debug(' -> Decoded to %s', act)

            if 'action' not in act:
                raise ValueError('"action" was not in decoded json object...')
            if act['action'] not in self.ACTIONS:
                raise ValueError('Action "{}" is not a valid action...'.format(act['action']))
        except (JSONDecodeError, TypeError, ValueError, AttributeError):
            log.exception('Error decoding json for %s', b)
            return ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        try:
            run_act = self.ACTIONS[act['action']](**act)
            if run_act:
                log.debug('Acknowledging success to MQ')
                return ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                log.debug('Acknowledging failure (try later) to MQ')
                return ch.basic_nack(delivery_tag=method.delivery_tag)
        except (InvalidHostException, AttributeError, ValueError) as e:
            log.warning('Invalid host... Type: %s Msg: %s', type(e), str(e))
            return ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception:
            log.exception('Unknown exception while handling action call...')
            return ch.basic_nack(delivery_tag=method.delivery_tag)

    def trace(self, **act):
        try:
            # Extract the request ID, protocol, and host from the ``act`` dict
            req_id, proto, host = act['req_id'], act.get('proto', 'any'), str(act['host'])
            log.debug('Request ID: %s, Action: %s, IP/Host: %s', req_id, 'trace', host)
        except (AttributeError, KeyError):
            raise MissingArgsException('Data is missing `req_id` or `host` - cannot trace.')
        # Default arguments for MTR (b = show IPs + hostnames, z = show ASNs, w = wide report)
        args = ['mtr', '-bzw']
        data = dict(action='trace', host=host, result=None, status='failed')

        try:
            if not validate_host(host, proto):
                raise InvalidHostException
        except (BaseException, ValueError, TypeError, AttributeError, InvalidHostException) as e:
            if type(e) != InvalidHostException:
                log.exception('Unknown exception while validating host "%s" ...', host)
            self.redis.hset('lg_results', req_id, json.dumps(data))
            raise InvalidHostException('Host {} is not valid, or is disallowed.'.format(host))

        # If a protocol is specified, add the flag ``4`` or ``6`` to force a trace using IPv4/IPv6
        if proto in v4_protos + v6_protos:
            args[1] = args[1] + '6' if proto in v6_protos else args[1] + '4'
        # Now that we've set the protocol flag (if needed), we append the host to the arguments
        args.append(host)
        log.debug('Host "%s" is valid. Calling MTR......', host)
        # Finally run mtr with the arguments, and wait for the report
        mtr_handle = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = mtr_handle.communicate()

        log.debug('stdout: %s', stdout)
        log.debug('stderr: %s', stderr)

        log.debug('Saving results for request ID %s', req_id)
        # Store the results in the redis hash set under the request ID.
        result = stdout.decode()
        data['result'], data['status'] = result, 'finished'
        self.redis.hset('lg_results', req_id, json.dumps(data))

        return True

    def ping(self, **act):
        try:
            # Extract the request ID, protocol, and host from the ``act`` dict
            req_id, proto, host = act['req_id'], act.get('proto', 'any'), str(act['host'])
            log.debug('Request ID: %s, Action: %s, IP/Host: %s', req_id, 'ping', host)
        except (AttributeError, KeyError):
            raise MissingArgsException('Data is missing `req_id` or `host` - cannot ping.')
        # Default arguments for MTR (b = show IPs + hostnames, z = show ASNs, w = wide report)
        args = ['ping', '-c', '5']
        data = dict(action='ping', host=host, result=None, status='failed')

        try:
            if not validate_host(host, proto):
                raise InvalidHostException
        except (BaseException, ValueError, TypeError, AttributeError, InvalidHostException) as e:
            if type(e) != InvalidHostException:
                log.exception('Unknown exception while validating host "%s" ...', host)
            self.redis.hset('lg_results', req_id, json.dumps(data))
            raise InvalidHostException('Host {} is not valid, or is disallowed.'.format(host))

        # If a protocol is specified, add the flag ``4`` or ``6`` to force a trace using IPv4/IPv6
        if proto in v4_protos + v6_protos:
            args = args + (['-6'] if proto in v6_protos else ['-4'])
        # Now that we've set the protocol flag (if needed), we append the host to the arguments
        args.append(host)
        log.debug('Host "%s" is valid. Calling ping......', host)
        # Finally run mtr with the arguments, and wait for the report
        mtr_handle = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = mtr_handle.communicate()

        log.debug('stdout: %s', stdout)
        log.debug('stderr: %s', stderr)

        log.debug('Saving results for request ID %s', req_id)
        # Store the results in the redis hash set under the request ID.
        result = stdout.decode()
        data['result'], data['status'] = result, 'finished'
        self.redis.hset('lg_results', req_id, json.dumps(data))

        return True




