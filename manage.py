#!/usr/bin/env python3
"""

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
import textwrap
import sys
import argparse
from lookingglass.runner import Runner
from lookingglass import core

log = logging.getLogger('lookingglass.managedotpy')


class ErrHelpParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2)


help_text = textwrap.dedent('''\

    Commands:

        runserver         - Run the flask dev server (DO NOT USE IN PRODUCTION. USE GUNICORN)
        queue             - Start the message queue runner, for running pings/traces in background
 
''')

parser = ErrHelpParser(
    description='Privex Bandwidth Tracker',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=help_text
)


subparser = parser.add_subparsers()


def runserver(opt):
    from lookingglass.views import flask

    flask.run(
        host=opt.host,
        port=opt.port,
        debug=flask.config.get('DEBUG', False)
    )


def queue_handler(opt):
    r = Runner(mq_conn=core.get_rmq(), queue=core.cf['RMQ_QUEUE'], redis=core.get_redis())
    r.run()


def queue_test(opt):
    queue = core.RMQ_QUEUE
    log.debug('Getting channel with queue %s and routing key %s', queue, queue)
    chan = core.get_rmq_chan()
    chan.queue_declare(queue)
    data = dict(req_id='abcd-efgh-1234', action='trace', ip='8.8.4.4')
    chan.basic_publish(exchange='', routing_key=queue, body=json.dumps(data))


p_qr = subparser.add_parser('queue', description='Start message queue runner')
p_qr.set_defaults(func=queue_handler)

p_qr_test = subparser.add_parser('qtest', description='queue testing')
p_qr_test.set_defaults(func=queue_test)

p_run = subparser.add_parser('runserver', description='Run flask dev server (DO NOT USE IN PRODUCTION. USE GUNICORN)')
p_run.add_argument('--port', help='Port to listen on', default=5222, type=int)
p_run.add_argument('--host', help='IP/Hostname to listen on', default='127.0.0.1')
p_run.set_defaults(func=runserver)

args = parser.parse_args()

if 'func' in args:
    args.func(args)
else:
    parser.print_help()

