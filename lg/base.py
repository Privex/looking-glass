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
import ipaddress
import logging
import os

import pika
import redis
import json
from dotenv import load_dotenv
from flask import Flask
from getenv import env
from cloudant import CouchDB
from pika.adapters.blocking_connection import BlockingChannel
from privex.loghelper import LogHelper
from privex.helpers import env_bool

load_dotenv()
flask = Flask(__name__)

cf = flask.config

DEBUG = flask.config['DEBUG'] = env_bool('DEBUG', False)
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

lh = LogHelper('lg.base')

CONSOLE_LOG_LEVEL = env('LOG_LEVEL', None)
CONSOLE_LOG_LEVEL = logging.getLevelName(str(CONSOLE_LOG_LEVEL).upper()) if CONSOLE_LOG_LEVEL is not None else None

if CONSOLE_LOG_LEVEL is None:
    CONSOLE_LOG_LEVEL = logging.DEBUG if flask.config['DEBUG'] else logging.INFO

lh.add_console_handler(level=CONSOLE_LOG_LEVEL)

DBG_LOG, ERR_LOG = os.path.join(BASE_DIR, 'logs', 'debug.log'), os.path.join(BASE_DIR, 'logs', 'error.log')
lh.add_timed_file_handler(DBG_LOG, when='D', interval=1, backups=14, level=logging.INFO)
lh.add_timed_file_handler(ERR_LOG, when='D', interval=1, backups=14, level=logging.WARNING)

log = lh.get_logger()
lh.copy_logger('lg', 'privex')

#######################################
#
# RabbitMQ, Redis, and CouchDB Configuration
#
#######################################

RMQ_HOST = cf['RMQ_HOST'] = env('RMQ_HOST', 'localhost')
RMQ_PORT = cf['RMQ_PORT'] = env('RMQ_PORT', pika.ConnectionParameters._DEFAULT)
RMQ_QUEUE = cf['RMQ_QUEUE'] = env('RMQ_QUEUE', 'privexlg')

REDIS_HOST = cf['REDIS_HOST'] = env('REDIS_HOST', 'localhost')
REDIS_PORT = cf['REDIS_PORT'] = int(env('REDIS_PORT', 6379))
REDIS_DB = cf['REDIS_DB'] = int(env('REDIS_DB', 0))

COUCH_USER = env('COUCH_USER', 'admin')
COUCH_PASS = env('COUCH_PASS', '')

COUCH_URL = cf['COUCH_URL'] = env('COUCH_URL', 'http://127.0.0.1:5984')
"""Full URL for where CouchDB server is running.`"""

COUCH_DB = cf['COUCH_DB'] = env('COUCH_DB', 'peersapp')
"""Name of the database to use for CouchDB. Will automatically be created if it doesn't exist."""

COUCH_VIEWS = os.path.join(BASE_DIR, 'lg', 'peerapp', 'couch_views')

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


def create_couch_views(couch: CouchDB, destroy=False):
    view_files = []
    for (_, _, filenames) in os.walk(COUCH_VIEWS):
        view_files.extend(filenames)
        break
    db = couch[COUCH_DB]
    view_files = [os.path.join(COUCH_VIEWS, fn) for fn in view_files]
    for f in view_files:
        view_data = None
        with open(f) as fh:
            view_data = fh.read()
            view_data = json.loads(view_data)
        v_id = view_data['_id']

        if v_id in db:
            if not destroy:
                log.debug('View %s exists but "destroy" is False. Not touching existing view.', v_id)
                continue
            log.info('View %s exists. Destroying it before re-insertion.', v_id)
            db.delete(db[v_id])
        db.create_document(view_data)
        # db.save(view_data)
        log.info('Saved view "%s".', v_id)


def get_couch() -> CouchDB:
    """Get a CouchDB connection object. Create one if it doesn't exist. Auto-create database if needed."""
    if 'couch' not in __STORE:
        log.debug('Creating CouchDB instance with URL %s', COUCH_URL)
        __STORE['couch'] = couch = CouchDB(COUCH_USER, COUCH_PASS, url=COUCH_URL, connect=True, auto_renew=True)

        # __STORE['couch'] = couch = couchdb.Server(COUCH_URL)
        if COUCH_DB not in couch:
            log.debug("Creating CouchDB database %s as it doesn't exist.", COUCH_DB)
            couch.create_database(COUCH_DB)
        create_couch_views(couch)
    return __STORE['couch']
