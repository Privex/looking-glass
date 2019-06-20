import ipaddress
import re
import socket
import dns.resolver
import logging
from ipaddress import ip_address, IPv6Address, IPv4Address
from typing import Union
from lookingglass.core import DISALLOW_SUBNETS

log = logging.getLogger(__name__)


def empty(v, zero=False, itr=False) -> bool:
    """
    Quickly check if a variable is empty or not. By default only '' and None are checked, use `itr` and `zero` to
    test for empty iterable's and zeroed variables.

    Returns True if a variable is None or '', returns False if variable passes the tests

    :param v:    The variable to check if it's empty
    :param zero: if zero=True, then return True if the variable is 0
    :param itr:  if itr=True, then return True if the variable is ``[]``, ``{}``, or is an iterable and has 0 length
    :return bool is_blank: True if a variable is blank (``None``, ``''``, ``0``, ``[]`` etc.)
    :return bool is_blank: False if a variable has content (or couldn't be checked properly)
    """

    _check = [None, '']
    if zero: _check.append(0)
    if v in _check: return True
    if itr:
        if v == [] or v == {}: return True
        if hasattr(v, '__len__') and len(v) == 0: return True

    return False


def is_valid_hostname(hostname: str) -> bool:
    """
    Returns True if a given `hostname` is a valid internet hostname.

    Taken from this StackOverflow post: https://stackoverflow.com/a/2532344

    :param hostname: Hostname to validate as a string
    :return bool is_valid: True if the hostname is valid, False if not.
    """

    if len(hostname) > 255 or len(hostname) == 0:
        return False
    if hostname[-1] == ".":
        hostname = hostname[:-1]  # strip exactly one dot from the right, if present
    allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in hostname.split("."))


def ip_is_v6(ip: str) -> bool:
    """
    Determines whether an IP address is IPv6 or not

    :param ip: IP address to check
    :raises ValueError: When IP address is invalid
    :return bool: True if IPv6, False if not
    """
    return type(ip_address(ip)) == IPv6Address


def ip_is_v4(ip: str) -> bool:
    """
    Determines whether an IP address is IPv4 or not

    :param ip: IP address to check
    :raises ValueError: When IP address is invalid
    :return bool: True if IPv4, False if not
    """
    return type(ip_address(ip)) == IPv4Address


def is_ip(host: str) -> bool:
    """Returns True if a given host is a valid IPv4 or IPv6 address"""
    try:
        return type(ip_address(host)) in [IPv4Address, IPv6Address]
    except ValueError:
        return False


v4_protos = ['ipv4', 'v4', '4', 'IPv4', 4]
v6_protos = ['ipv6', 'v6', '6', 'IPv6', 6]

recs = {
    **dict(zip(v6_protos, ['AAAA'] * len(v6_protos))),
    **dict(zip(v4_protos, ['A'] * len(v6_protos))),
}
"""A dictionary mapping protocol names (v4, v6, ipv4 etc.) to record types ``A`` and ``AAAA`` """


def proto_check(ip: Union[str, IPv4Address, IPv6Address], proto=None):
    """Verify an IP address is of the protocol (v4, v6) specified"""
    try:
        # No protocol specified,
        if not proto or proto in [None, False, 'any', '']:
            return is_ip(ip)

        if proto in v4_protos: return ip_is_v4(ip)
        if proto in v6_protos: return ip_is_v6(ip)
    except ValueError:
        return False

    raise AttributeError('`proto` is not valid')


def get_host_ip(host: str, proto='ipv4'):
    try:
        dnsq = list(dns.resolver.query(host, recs[proto]))
        return dnsq[0]
    except (dns.resolver.NoAnswer, AttributeError, KeyError):
        return None


def validate_host(host: str, proto: str = None) -> bool:
    """
    Returns True if a given host (hostname/ipv4/ipv6) is a valid hostname or IP address, and is not blacklisted
    ( blacklisted means part of ``DISALLOW_SUBNETS`` )

    ``proto`` is optional, can be one of: "ipv4", "ipv6", "v4", "v6", 4, 6, "IPv4" or "IPv6"

    If proto is one of the above values,

    :param str host: A string network host, as a hostname, IPv4 address, or IPv6 address.
    :param bool proto: If set, then this will return False if ``host`` is an IP, and does not match the passed version
    :return bool is_valid: True if a host is valid, False if it's not.
    """
    if proto == 'any' or not proto:
        proto = None

    # First check if it's an IP address
    log.debug('Checking if host "%s" is an IP address', host)
    if is_ip(host):
        return proto_check(host, proto) and ip_allowed(host)

    # If it's not an IP, check if it's a hostname, look up it's IP, and compare to our disallowed subnets to be safe.
    log.debug('Checking if host "%s" is a valid hostname', host)
    if is_valid_hostname(host):
        log.debug('Looking up IP for host "%s"', host)

        # Protocol is specified, if protocol is v4, check for an A record, and AAAA for IPv6 etc.
        if proto is not None:
            if proto not in recs: raise Exception('Invalid `proto` "{}"'.format(proto))
            ip = get_host_ip(host, proto)
            return False if ip is None else ip_allowed(ip)
        # Protocol is not specified, try getting the AAAA record first, then fallback to A
        v6_ip = get_host_ip(host, 'ipv6')
        if v6_ip is not None: return ip_allowed(v6_ip)
        v4_ip = get_host_ip(host, 'ipv4')
        if v4_ip is not None: return ip_allowed(v4_ip)

    log.warning('Host "%s" is neither an IP nor a valid hostname.', host)
    return False


def ip_allowed(ip: Union[str, IPv6Address, IPv4Address]) -> bool:
    """
    Check if an IP address should be accepted (True), or if it's blacklisted (False).

    Checks if an IP address is part of a network listed in ``DISALLOW_SUBNETS`` - if it is, this will return False.
    If the IP address is not present in any of the networks listed there, then it will return True.

    :param ip: An IPv4 / IPv6 address to check. Can be in string form, or IPv4Address/IPv6Address object.
    :return bool is_allowed: True if an IP is safe to use, False if it's part of the blacklisted subnets.
    """
    ip = ipaddress.ip_address(ip)
    for net in DISALLOW_SUBNETS:
        if ip in net:
            return False
    return True
