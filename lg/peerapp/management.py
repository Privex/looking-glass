from lg import base
from lg.peerapp import settings
from lg.peerapp.import_prefixes import PathLoader
import logging
import textwrap

log = logging.getLogger('peerapp.managedotpy')

PEERS_HELP = textwrap.dedent('''\
    
    Peer Application Commands (peerapp):
        prefixes          - Load prefixes from gobgp
        reset_views       - Delete and re-create the included CouchDB views from ./peersapp/couch_views
        clear_db          - Deletes and re-creates the CouchDB database (NO CONFIRMATION!)
    
''')


def load_prefixes(opt):
    pl = PathLoader(settings.GBGP_HOST)
    sane4 = pl.parse_paths()
    sane6 = pl.parse_paths('v6')
    pl.summary()
    pl.store_paths()


def clear_db(opt):
    dbname = base.COUCH_DB
    couch = base.get_couch()
    if dbname not in couch:
        print(f'The database {dbname} does not exist. Will now just re-create it.')
        couch.create_database(dbname)
        print('Done.')
        return
    print(f'Removing database {dbname} ...')
    couch.delete_database(dbname)
    print(f'Re-creating database {dbname} ...')
    couch.create_database(dbname)
    print('Done.')


def reset_views(opt):
    print('Forcing re-creation of CouchDB views...')
    base.create_couch_views(couch=base.get_couch(), destroy=True)
    print('Done.')


def add_parsers(subparser):
    p_qr = subparser.add_parser('prefixes', description='Load prefixes from gobgp')
    p_qr.set_defaults(func=load_prefixes)

    p_clear = subparser.add_parser('clear_db', description='Deletes and re-creates the CouchDB '
                                                        'database (NO CONFIRMATION!)')
    p_clear.set_defaults(func=clear_db)

    p_reset = subparser.add_parser('reset_views', description='Delete and re-create the included CouchDB views from ./peersapp/couch_views')
    p_reset.set_defaults(func=reset_views)

    return dict(p_qr=p_qr, p_clear=p_clear, p_reset=p_reset)
