import argparse
from lg import base
from lg.peerapp import settings
from lg.peerapp.import_prefixes import PathLoader
import logging
import textwrap
import asyncio

log = logging.getLogger('peerapp.managedotpy')

PEERS_HELP = textwrap.dedent('''\
    
    Peer Application Commands (peerapp):
        prefixes          - Load prefixes from gobgp
    
''')


def load_prefixes(opt):
    loop = asyncio.get_event_loop()
    
    pl = PathLoader(settings.GBGP_HOST)
    # pl.parse_paths()
    # pl.parse_paths('v6')
    if opt.verbose:
        pl.summary()
    loop.run_until_complete(pl.store_paths('v4'))
    loop.run_until_complete(pl.store_paths('v6'))


def add_parsers(subparser: argparse._SubParsersAction):
    p_qr = subparser.add_parser('prefixes', description='Load prefixes from gobgp')
    p_qr.add_argument('-q', dest='quiet', action='store_true', default=False,
                      help='Quiet mode - only log start and finish')
    p_qr.add_argument('-v', dest='verbose', action='store_true', default=False,
                      help='Verbose mode - show detailed output while loading prefixes')
    p_qr.set_defaults(func=load_prefixes)

    return dict(p_qr=p_qr)
