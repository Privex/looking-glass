#######################################
#
# Register apps
#
#######################################
from lg import base, api
from flask import render_template, jsonify
from lg.exceptions import DatabaseConnectionFail, InvalidIP
import logging
import lg.models

log = logging.getLogger(__name__)
flask, db, migration = base.get_app()


@flask.route('/')
def index():
    return render_template(
        'index.html', hot_loader=base.HOT_LOADER, hot_loader_url=base.HOT_LOADER_URL,
        debug=base.DEBUG
    )


log.debug('Checking if BGP Peer Info app is enabled... (ENABLE_PEERAPP)')
if base.ENABLE_PEERAPP:
    log.debug('ENABLE_PEERAPP is True. Initialising BGP Peer Info app')
    try:
        from lg.peerapp.views import flask as peer_flask, setup_api_routes as peer_api_setup
        flask.register_blueprint(peer_flask)
        peer_api_setup()
    except DatabaseConnectionFail:
        log.exception('Cannot register "peerapp" - is your CouchDB and Redis running?')

log.debug('Checking if Ping/Trace app is enabled... (ENABLE_LG)')
if base.ENABLE_LG:
    log.debug('ENABLE_LG is True. Initialising Ping/Trace app...')
    from lg.lookingglass.views import flask as lg_flask

    flask.register_blueprint(lg_flask)


@flask.route('/api/')
@flask.route('/api/v1/')
def api_list():
    res = {}
    for n, a in base.API_ROUTES.items():
        res[n] = dict(a)
        res[n]['full_url'] = a.full_url
    
    return jsonify(
        error=False,
        result=res
    )


@flask.errorhandler(404)
def handle_404(exc=None):
    return api.handle_error('NOT_FOUND', exc=exc)


@flask.errorhandler(InvalidIP)
def handle_404(exc=None):
    return api.handle_error('INV_ADDRESS', exc=exc)


@flask.errorhandler(Exception)
def app_error_handler(exc=None, *args, **kwargs):
    log.warning("app_error_handler exception type / msg: %s / %s", type(exc), str(exc))
    log.warning("app_error_handler *args: %s", args)
    log.warning("app_error_handler **kwargs: %s", kwargs)
    return api.handle_error('UNKNOWN_ERROR', exc=exc)

