#######################################
#
# Register apps
#
#######################################
from lg import base
from flask import render_template
from lg.exceptions import DatabaseConnectionFail
import logging
import lg.models

log = logging.getLogger(__name__)
flask, db, migration = base.get_app()


@flask.route('/')
def index():
    return render_template('index.html')


log.debug('Checking if BGP Peer Info app is enabled... (ENABLE_PEERAPP)')
if base.ENABLE_PEERAPP:
    log.debug('ENABLE_PEERAPP is True. Initialising BGP Peer Info app')
    try:
        from lg.peerapp.views import flask as peer_flask
        flask.register_blueprint(peer_flask)
    except DatabaseConnectionFail:
        log.exception('Cannot register "peerapp" - is your CouchDB and Redis running?')

log.debug('Checking if Ping/Trace app is enabled... (ENABLE_LG)')
if base.ENABLE_LG:
    log.debug('ENABLE_LG is True. Initialising Ping/Trace app...')
    from lg.lookingglass.views import flask as lg_flask

    flask.register_blueprint(lg_flask)




