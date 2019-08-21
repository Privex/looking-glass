"""

lg.base - Shared settings between all sub-apps

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
import functools
import ipaddress
import logging
import os
import pickle
from enum import Enum
from typing import Tuple, Any

import pika
import redis
import json
from dotenv import load_dotenv
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from getenv import env
from pika.adapters.blocking_connection import BlockingChannel
from privex.loghelper import LogHelper
from privex.helpers import env_bool, empty, settings as hlp_settings

load_dotenv()


cf = {}

DEBUG = cf['DEBUG'] = env_bool('DEBUG', False)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENABLE_LG = env_bool('ENABLE_LG', True)
"""Enable the looking glass (mtr / ping) application (lookingglass) - Default: True (enabled)"""

ENABLE_PEERAPP = env_bool('ENABLE_PEERAPP', True)
"""Enable the peer information application (peerapp) - Default: True (enabled)"""

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

lh = LogHelper('lg')

CONSOLE_LOG_LEVEL = env('LOG_LEVEL', None)
CONSOLE_LOG_LEVEL = logging.getLevelName(str(CONSOLE_LOG_LEVEL).upper()) if CONSOLE_LOG_LEVEL is not None else None

if CONSOLE_LOG_LEVEL is None:
    CONSOLE_LOG_LEVEL = logging.DEBUG if cf['DEBUG'] else logging.INFO

lh.add_console_handler(level=CONSOLE_LOG_LEVEL)

DBG_LOG, ERR_LOG = os.path.join(BASE_DIR, 'logs', 'debug.log'), os.path.join(BASE_DIR, 'logs', 'error.log')
lh.add_timed_file_handler(DBG_LOG, when='D', interval=1, backups=14, level=logging.INFO)
lh.add_timed_file_handler(ERR_LOG, when='D', interval=1, backups=14, level=logging.WARNING)

log = lh.get_logger()
lh.copy_logger('privex')

#######################################
#
# RabbitMQ, Redis, and CouchDB Configuration
#
#######################################

RMQ_HOST = cf['RMQ_HOST'] = env('RMQ_HOST', 'localhost')
RMQ_PORT = cf['RMQ_PORT'] = env('RMQ_PORT', pika.ConnectionParameters._DEFAULT)
RMQ_QUEUE = cf['RMQ_QUEUE'] = env('RMQ_QUEUE', 'privexlg')

hlp_settings.REDIS_HOST = REDIS_HOST = env('REDIS_HOST', 'localhost')
hlp_settings.REDIS_PORT = REDIS_PORT = int(env('REDIS_PORT', 6379))
hlp_settings.REDIS_DB = REDIS_DB = int(env('REDIS_DB', 0))

COUCH_USER = env('COUCH_USER', 'admin')
COUCH_PASS = env('COUCH_PASS', '')

COUCH_URL = cf['COUCH_URL'] = env('COUCH_URL', 'http://127.0.0.1:5984')
"""Full URL for where CouchDB server is running.`"""

COUCH_DB = cf['COUCH_DB'] = env('COUCH_DB', 'peersapp')
"""Name of the database to use for CouchDB. Will automatically be created if it doesn't exist."""

COUCH_VIEWS = os.path.join(BASE_DIR, 'lg', 'peerapp', 'couch_views')

PG_CONF = pg = dict(
    user=env('PSQL_USER', 'lg'),
    dbname=env('PSQL_DB', 'lookingglass'),
    password=env('PSQL_PASS', ''),
    host=env('PSQL_HOST', 'localhost'),
    port=int(env('PSQL_PORT', 5432)),
)

if empty(pg['password']):
    pgc = f"postgresql://{pg['user']}@{pg['host']}:{pg['port']}/{pg['dbname']}"
else:
    pgc = f"postgresql://{pg['user']}:{pg['password']}@{pg['host']}:{pg['port']}/{pg['dbname']}"

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
        __STORE['rmq'] = pika.BlockingConnection(pika.ConnectionParameters(RMQ_HOST))
    return __STORE['rmq']


def get_rmq_chan() -> BlockingChannel:
    """Get a RabbitMQ channel object. Create one if it doesn't exist."""
    # if 'rmq_chan' not in __STORE:
    chan = get_rmq().channel()  # type: BlockingChannel
    chan.queue_declare(queue=RMQ_QUEUE)
    return chan


def get_app() -> Tuple[Flask, SQLAlchemy, Migrate]:
    """
    Initialise Flask, SQLAlchemy and Flask-Migrate, and/or return their instances from :py:attr:`__STORE`

    >>> from lg.base import get_app
    >>> app, db, migrate = get_app()
    """
    if 'flask' not in __STORE:
        flask = __STORE['flask'] = Flask(__name__)
        log.debug('Configuring SQLAlchemy for app: %s', flask.name)
        flask.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        flask.config['SQLALCHEMY_DATABASE_URI'] = pgc
    flask = __STORE['flask']

    if 'sqlalchemy' not in __STORE:
        log.debug('Connecting to Postgres database "%s" with user "%s" on host "%s"',
                  pg['dbname'], pg['user'], pg['host'])
        db = __STORE['sqlalchemy'] = SQLAlchemy(flask)
        __STORE['flask-migrate'] = Migrate(flask, db)

    return flask, __STORE['sqlalchemy'], __STORE['flask-migrate']


