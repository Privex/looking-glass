import ipaddress
import re
import dns.resolver
import logging
from ipaddress import ip_address, IPv6Address, IPv4Address
from typing import Union
# from lg.peerapp.settings import DISALLOW_SUBNETS

log = logging.getLogger(__name__)


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
