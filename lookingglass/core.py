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
import ipaddress
import logging
import os

import pika
import redis
from dotenv import load_dotenv
from flask import Flask
from getenv import env
from pika.adapters.blocking_connection import BlockingChannel
from privex.loghelper import LogHelper

load_dotenv()
flask = Flask(__name__)

cf = flask.config

DEBUG = flask.config['DEBUG'] = str(env('DEBUG', 'false')).lower() in ['true', '1', 'yes']
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#######################################
#
# Logging Configuration
#
#######################################

# Log to console with CONSOLE_LOG_LEVEL, as well as output logs >=info / >=warning to respective files
# with automatic daily log rotation (up to 14 days of logs)
# Due to the amount of output from logging.DEBUG, we only log INFO and higher to a file.
# Valid environment log levels (from least to most severe) are:
# DEBUG, INFO, WARNING, ERROR, FATAL, CRITICAL

lh = LogHelper('lookingglass')

CONSOLE_LOG_LEVEL = env('LOG_LEVEL', None)
CONSOLE_LOG_LEVEL = logging.getLevelName(str(CONSOLE_LOG_LEVEL).upper()) if CONSOLE_LOG_LEVEL is not None else None

if CONSOLE_LOG_LEVEL is None:
    CONSOLE_LOG_LEVEL = logging.DEBUG if flask.config['DEBUG'] else logging.INFO

lh.add_console_handler(level=CONSOLE_LOG_LEVEL)

DBG_LOG, ERR_LOG = os.path.join(BASE_DIR, 'logs', 'debug.log'), os.path.join(BASE_DIR, 'logs', 'error.log')
lh.add_timed_file_handler(DBG_LOG, when='D', interval=1, backups=14, level=logging.INFO)
lh.add_timed_file_handler(ERR_LOG, when='D', interval=1, backups=14, level=logging.WARNING)

log = lh.get_logger()

#######################################
#
# RabbitMQ + Redis Configuration
#
#######################################

RMQ_HOST = cf['RMQ_HOST'] = env('RMQ_HOST', 'localhost')
RMQ_PORT = cf['RMQ_PORT'] = env('RMQ_PORT', pika.ConnectionParameters._DEFAULT)
RMQ_QUEUE = cf['RMQ_QUEUE'] = env('RMQ_QUEUE', 'privexlg')

REDIS_HOST = cf['REDIS_HOST'] = env('REDIS_HOST', 'localhost')
REDIS_PORT = cf['REDIS_PORT'] = int(env('REDIS_PORT', 6379))
REDIS_DB = cf['REDIS_DB'] = int(env('REDIS_DB', 0))

#######################################
#
# Application config
#
#######################################


DISALLOW_SUBNETS = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('fe80::/10'),
    ipaddress.ip_network('fc00::/7'),
    ipaddress.ip_network('ff00::/8'),
]
"""
DISALLOW_SUBNETS is a list of subnets which users may not access, as to prevent any reconnaissance of your
local network by users.

By default, IPv4 and IPv6 LAN IPs are disallowed. 

To block additional subnets, simply set the environment var ``DISALLOWED_SUBNETS`` to a comma separated 
list of CIDR networks (both IPv4 and IPv6 will work).

Example::

    
    DISALLOW_SUBNETS=12.34.0.0/16,2a07:e00:1:2::/64,233.32.40.0/24
    

"""

# If the env var DISALLOW_SUBNETS is set, split it by commas, convert each prefix into an ip_network,
# then combine them into DISALLOW_SUBNETS
__dis_subs = env('DISALLOW_SUBNETS', None)
if __dis_subs is not None:
    __dis_subs = str(__dis_subs).split(',')
    _dis_nets = [ipaddress.ip_network(net, strict=False) for net in __dis_subs]
    DISALLOW_SUBNETS = DISALLOW_SUBNETS + _dis_nets

#######################################
#
# Initialise various connections
#
#######################################

__STORE = {}


def get_redis() -> redis.Redis:
    """Get a Redis connection object. Create one if it doesn't exist."""
    if 'redis' not in __STORE:
        __STORE['redis'] = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    return __STORE['redis']


def get_rmq() -> pika.BlockingConnection:
    """Get a RabbitMQ connection object. Create one if it doesn't exist."""
    if 'rmq' not in __STORE:
        __STORE['r_mq'] = pika.BlockingConnection(pika.ConnectionParameters(RMQ_HOST))
    return __STORE['r_mq']


def get_rmq_chan() -> BlockingChannel:
    """Get a RabbitMQ channel object. Create one if it doesn't exist."""
    # if 'rmq_chan' not in __STORE:
    chan = get_rmq().channel()  # type: BlockingChannel
    chan.queue_declare(queue=RMQ_QUEUE)
    return chan
    # __STORE['rmq_chan'] = chan
    # return __STORE['rmq_chan']




