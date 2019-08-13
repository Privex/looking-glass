#######################################
#
# Register apps
#
#######################################
from lg import base
from flask import Flask, render_template
from lg.exceptions import DatabaseConnectionFail
import logging

log = logging.getLogger(__name__)
flask = Flask(__name__)


@flask.route('/')
def index():
    return render_template('index.html')


if base.ENABLE_PEERAPP:
    try:
        from lg.peerapp.views import flask as peer_flask
        flask.register_blueprint(peer_flask)
    except DatabaseConnectionFail:
        log.exception('Cannot register "peerapp" - is your CouchDB and Redis running?')

if base.ENABLE_LG:
    from lg.lookingglass.views import flask as lg_flask

    flask.register_blueprint(lg_flask)
