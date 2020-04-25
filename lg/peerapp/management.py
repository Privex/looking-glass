import argparse
import pstats

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


def dump_profile_stats(opt):
    profile_file = opt.filename[0]
    output_file = opt.output
    sort = opt.sort_stats
    if output_file is None:
        stats = pstats.Stats(profile_file)
        stats.sort_stats(sort)
        return stats.print_stats()

    with open(output_file, 'w') as stream:
        stats = pstats.Stats(profile_file, stream=stream)
        stats.sort_stats(sort)
        return stats.print_stats()


def add_parsers(subparser: argparse._SubParsersAction):
    p_qr = subparser.add_parser('prefixes', description='Load prefixes from gobgp')
    p_qr.add_argument('-q', dest='quiet', action='store_true', default=False,
                      help='Quiet mode - only log start and finish')
    p_qr.add_argument('-v', dest='verbose', action='store_true', default=False,
                      help='Verbose mode - show detailed output while loading prefixes')
    p_qr.set_defaults(func=load_prefixes)

    p_dump_prof = subparser.add_parser('dump_profile', description='(DEBUGGING) Dump stats from a cProfile binary file')
    p_dump_prof.add_argument('filename', help='Binary profile data to generate stats from', nargs=1)
    p_dump_prof.add_argument('output', help='Output stats to this file (if not passed, defaults to stdout)', nargs='?', default=None)
    p_dump_prof.add_argument('--sort', dest='sort_stats', default='cumtime',
                             help="Sort stats by this key (default: 'cumtime' - total time used by function)")
    p_dump_prof.set_defaults(func=dump_profile_stats)

    return dict(p_qr=p_qr, p_dump_prof=p_dump_prof)
