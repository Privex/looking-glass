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
import argparse
from lg import base
from lg.lookingglass.runner import Runner
from privex.helpers import ErrHelpParser

log = logging.getLogger('lookingglass.managedotpy')

PEERAPP_HELP = textwrap.dedent('''\
        --------------------
        The peer information app is disabled. Please set ENABLE_PEERAPP=true to enable
        management commands for the peer application (peerapp).
        --------------------
    ''')

if base.ENABLE_PEERAPP:
    from lg.peerapp.management import PEERS_HELP
    PEERAPP_HELP = PEERS_HELP

help_text = textwrap.dedent('''\

    Commands:

        runserver         - Run the flask dev server (DO NOT USE IN PRODUCTION. USE GUNICORN)
        queue             - Start the message queue runner, for running pings/traces in background

''') + PEERAPP_HELP

parser = ErrHelpParser(
    description='Privex Bandwidth Tracker',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=help_text
)


subparser = parser.add_subparsers()


def runserver(opt):
    from lg.lookingglass.views import flask

    flask.run(
        host=opt.host,
        port=opt.port,
        debug=flask.config.get('DEBUG', False)
    )


def queue_handler(opt):
    r = Runner(mq_conn=base.get_rmq(), queue=base.RMQ_QUEUE, redis=base.get_redis())
    r.run()


def queue_test(opt):
    queue = base.RMQ_QUEUE
    log.debug('Getting channel with queue %s and routing key %s', queue, queue)
    chan = base.get_rmq_chan()
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

# If ENABLE_PEERAPP is true, add additional commands for that application.
if base.ENABLE_PEERAPP:
    from lg.peerapp.management import add_parsers
    add_parsers(subparser)

args = parser.parse_args()

if 'func' in args:
    args.func(args)
else:
    parser.print_help()

