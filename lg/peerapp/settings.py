import ipaddress
from ipaddress import ip_network, IPv4Address, IPv6Address, IPv4Network, IPv6Network, _BaseNetwork
from typing import Union, Tuple

from privex.helpers import env_keyval, env_csv, env_int
from os import getenv as env

#######################################
#
# App Configuration
#
#######################################


# In-case of issues resolving ASNs, OUR_ASN / LOCAL_IPs will be used as a fallback.
# This is useful in the case of Cisco route servers, as your own ASN will most likely be removed
# from the AS path of the route advertisement.
from lg.exceptions import IPNotFound

OUR_ASN = env('OUR_ASN', 210083)
OUR_ASN_NAME = env('OUR_ASN_NAME', 'Privex Inc.')

LOCAL_IPS = env_csv('LOCAL_IPS', ['185.130.44.0/22', '2a07:e00::/29'])
LOCAL_IPS = [ip_network(ip) for ip in LOCAL_IPS]

BLACKLIST_ROUTES = env_csv('BLACKLIST_ROUTES', [
    '0.0.0.0/0',
    '::/0',
    '2000::/3'
])
"""Ignore any route in this list"""

IX_RANGES = env_keyval('IX_RANGES', [
    ('SOL-IX STH', '193.110.13.0/24'),
    ('SOL-IX STH', '2001:7F8:21:9::/64'),
    ('SOL-IX STH (MTU 4470)', '2001:7F8:21:10::/64'),
    ('SOL-IX STH (MTU 4470)', '193.110.12.0/24'),
    ('STHIX Stockholm', '2001:7F8:3E:0::/64'),
    ('STHIX Stockholm', '192.121.80.0/24'),
], valsplit='|')
"""
To override the above subnets for exchanges, set the env var IX_RANGES in .env like so::

    IX_RANGES=Some Exchange|192.168.1.0/24,Other Exchange|2a07:e05:1:2::/64

The above would be parsed and result in the following python object::

    [
        ('Some Exchange', '192.168.1.0/24', ),
        ('Other Exchange', '2a07:e05:1:2::/64', ),
    ]

"""

# GoBGP protobuf host + port to connect to
GBGP_HOST = env('GBGP_HOST', 'localhost:50051')

CHUNK_SIZE = int(env('CHUNK_SIZE', 300))
"""
Amount of prefixes to commit as a chunk while running `./manage.py prefixes`

Affects how often it displays the current progress, i.e. `Saved 1200 out of 4548 prefixes` as well as how many
prefixes are committed per each TX. Numbers lower than 20 may result in performance issues.
"""

PREFIX_TIMEOUT = env_int('PREFIX_TIMEOUT', 1800)
"""
Prefixes with a ``last_seen`` more than PREFIX_TIMEOUT seconds ago from the newest prefix in the database
will be considered stale, and thus not shown on the ASN summary page, nor the individual prefix list for an ASN.

Default: ``3600`` seconds = 60 minutes.

We compare against the newest last_seen timestamp in the database, allowing you to run import_prefixes
as often as you like, e.g. once per 30-60 mins, without having prefixes go stale due to import_prefixes
being ran occasionally.
"""

PREFIX_TIMEOUT_WARN = env_int('PREFIX_TIMEOUT_WARN', 1800)
"""
Prefixes with a ``last_seen`` more than PREFIX_TIMEOUT_WARN seconds ago from the newest prefix in the database
will be marked in yellow, to signify that they're potentially stale / no longer being advertised.

Default: ``1800`` seconds = 30 minutes
"""

BLACKLIST_ROUTES = [ip_network(ip) for ip in BLACKLIST_ROUTES]

IX_NET_MAP = {
    subnet: ixp for ixp, subnet in IX_RANGES
}

IX_NET_VER = {
    IPv4Address: [(k, v,) for k, v in IX_NET_MAP.items() if type(ip_network(k)) is IPv4Network],
    IPv6Address: [(k, v,) for k, v in IX_NET_MAP.items() if type(ip_network(k)) is IPv6Network],
}


def find_ixp(ip: Union[str, IPv4Address, IPv6Address]) -> Tuple[str, _BaseNetwork]:
    """
    Looks up a given IP address (as either a str, or ip_address object) in :py:attr:`.IX_NET_MAP` and
    returns either a tuple containing two ``fail_val`` items (if it's not found) or if found, a tuple
    containing the name of the IXP, and the subnet which contains this IP.

    Example usage::

        >>> from lg.peerapp.settings import find_ixp
        >>> try:
        ...     ix, subnet = find_ixp('192.168.1.5')
        ...     print(f'{ix}, {subnet}')
        >>> except (IPNotFound, AddressValueError):
        ...     print('Error! IP not found, or is invalid.')

        On success, outputs:

        EXMPL-IX, 192.168.1.0/24

    :param str ip: An IP address, either as a ``str``, or a :py:func:`ipaddress.ip_address` object.
    :raises AddressValueError: When the given ``ip`` is not a valid IPv4/IPv6 address
    :raises IPNotFound: When the given ``ip`` was not found in :py:attr:`.IX_NET_MAP`
    :return tuple result: If the IP is found, will return a tuple ``(ixp_name: str, subnet: IPv4/v6Network, )``
    """
    ip = ipaddress.ip_address(ip)
    if not isinstance(ip, IPv4Address) and not isinstance(ip, IPv6Address):
        raise ipaddress.AddressValueError(f'Excepted IPv4/IPv6Address. Got {type(ip)}...')

    for l_net, l_ixp in IX_NET_VER[type(ip)]:
        l_net = ip_network(l_net)
        if ip in l_net:
            return l_ixp, l_net

    raise IPNotFound(f'IP Address "{ip}" was not found in the IXP network list.')

