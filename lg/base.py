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
from collections import namedtuple
from enum import Enum
from typing import Tuple, Any, Dict, List

import asyncpg
import attr
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
from privex.helpers import env_bool, empty, settings as hlp_settings, Git, AttribDictable, env_int

load_dotenv()


cf = {}

DEBUG = cf['DEBUG'] = env_bool('DEBUG', False)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENABLE_LG = env_bool('ENABLE_LG', True)
"""Enable the looking glass (mtr / ping) application (lookingglass) - Default: True (enabled)"""

ENABLE_PEERAPP = env_bool('ENABLE_PEERAPP', True)
"""Enable the peer information application (peerapp) - Default: True (enabled)"""

DEFAULT_API_LIMIT = env_int('VUE_APP_DEFAULT_API_LIMIT', 1000)
"""Default for ``limit`` field on API queries."""

MAX_API_LIMIT = env_int('VUE_APP_MAX_API_LIMIT', 10000)
"""Max value allowed for ``limit`` field on API queries."""

HOT_LOADER = env_bool('HOT_LOADER', False)
HOT_LOADER_URL = env('HOT_LOADER_URL', 'http://localhost:8080')

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

LOG_FORMATTER = logging.Formatter('[%(asctime)s]: %(name)-25s -> %(funcName)-20s : %(levelname)-8s:: %(message)s')

lh = LogHelper('lg', formatter=LOG_FORMATTER)

CONSOLE_LOG_LEVEL = env('LOG_LEVEL', None)
CONSOLE_LOG_LEVEL = logging.getLevelName(str(CONSOLE_LOG_LEVEL).upper()) if CONSOLE_LOG_LEVEL is not None else None

if CONSOLE_LOG_LEVEL is None:
    CONSOLE_LOG_LEVEL = logging.DEBUG if cf['DEBUG'] else logging.INFO

lh.add_console_handler(level=CONSOLE_LOG_LEVEL)

DBG_LOG, ERR_LOG = os.path.join(BASE_DIR, 'logs', 'debug.log'), os.path.join(BASE_DIR, 'logs', 'error.log')
lh.add_timed_file_handler(DBG_LOG, when='D', interval=1, backups=14, level=CONSOLE_LOG_LEVEL)
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

AppError = namedtuple('AppError', 'code message status', defaults=['', 500])

_ERRORS: List[AppError] = [
    AppError('UNKNOWN_ERROR', "An unknown error has occurred. Please contact the administrator of this site.", 500),
    AppError('METHOD_NOT_ALLOWED', "This API endpoint does not allow the requested HTTP method (GET/POST/PUT etc.)", 405),
    AppError('NO_REQUEST', "No request was sent.", 400),
    AppError('INV_HOST', "IP address / Hostname is invalid", 400),
    AppError('INV_ADDRESS', "IP address / Prefix is invalid", 400),
    AppError('INV_PROTO', "Invalid IP protocol, choose one of 'any', 'ipv4', 'ipv6'", 400),
    AppError('NOT_FOUND', "No records could be found for that object", 404),
    AppError('NO_HOST', 'No IP Address / Hostname specified', 400),
]
ERRORS: Dict[str, AppError] = {err.code: err for err in _ERRORS}
ERRORS['UNKNOWN'] = ERRORS['UNKNOWN_ERROR']
DEFAULT_ERR: AppError = ERRORS['UNKNOWN_ERROR']

SHOW_VERSION = env_bool('SHOW_VERSION', True)

GIT_COMMIT, GIT_TAG, GIT_BRANCH = '', '', ''

if SHOW_VERSION:
    try:
        GIT_COMMIT = Git(BASE_DIR).get_current_commit()
    except Exception:
        log.warning("Failed to get current Git commit")
    try:
        GIT_TAG = Git(BASE_DIR).get_current_tag()
    except Exception:
        log.warning("Failed to get current Git tag")
    try:
        GIT_BRANCH = Git(BASE_DIR).get_current_branch()
    except Exception:
        log.warning("Failed to get current Git branch")


@attr.s
class APIParam(AttribDictable):
    value_type = attr.ib(type=str)
    required = attr.ib(type=bool, default=False)
    description = attr.ib(type=str, default="")


@attr.s
class APIRoute(AttribDictable):
    endpoint = attr.ib(type=str)
    alt_endpoints = attr.ib(type=List[str], factory=list)
    url_params = attr.ib(type=Dict[str, APIParam], factory=dict)
    get_params = attr.ib(type=Dict[str, APIParam], factory=dict)
    post_params = attr.ib(type=Dict[str, APIParam], factory=dict)
    description = attr.ib(type=str, default="")
    
    @property
    def full_url(self) -> str:
        from flask import request
        return f"{request.host_url.strip('/')}/{self.endpoint.lstrip('/')}"


API_ROUTES: Dict[str, APIRoute] = {
    # "example": APIRoute(
    #   endpoint="/api/v1/example/",
    #   alt_endpoints=['/api/v1/example/<lorem>'],
    #   description="Returns all X's and Y's",
    #   url_params=dict(lorem=APIParam('string', False, 'A Lorem as a string'))
    # )
}


def add_api_route(name: str, api_route: APIRoute):
    API_ROUTES[name] = api_route
    return API_ROUTES[name]


PG_CONF = pg = dict(
    user=env('PSQL_USER', 'lg'),
    dbname=env('PSQL_DB', 'lookingglass'),
    password=env('PSQL_PASS', ''),
    host=env('PSQL_HOST', 'localhost'),
    port=int(env('PSQL_PORT', 5432)),
)


async def get_pg_pool(loop=None) -> asyncpg.pool.Pool:
    return await asyncpg.create_pool(
        host=PG_CONF['host'], port=PG_CONF['port'], user=PG_CONF['user'], password=PG_CONF['password'],
        database=PG_CONF['dbname'], loop=loop
    )


async def get_pg() -> asyncpg.connection.Connection:
    return await asyncpg.connect(
        host=PG_CONF['host'], port=PG_CONF['port'], user=PG_CONF['user'], password=PG_CONF['password'],
        database=PG_CONF['dbname']
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


