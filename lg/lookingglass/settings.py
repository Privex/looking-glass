import ipaddress
from os import getenv as env

DISALLOW_SUBNETS = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('fe80::/10'),
    ipaddress.ip_network('fc00::/7'),
    ipaddress.ip_network('ff00::/8'),
]
"""
DISALLOW_SUBNETS is a list of subnets which users may not access, as to prevent any reconnaissance of your
local network by users.

By default, IPv4 and IPv6 LAN IPs are disallowed. 

To block additional subnets, simply set the environment var ``DISALLOWED_SUBNETS`` to a comma separated 
list of CIDR networks (both IPv4 and IPv6 will work).

Example::


    DISALLOW_SUBNETS=12.34.0.0/16,2a07:e00:1:2::/64,233.32.40.0/24


"""

# If the env var DISALLOW_SUBNETS is set, split it by commas, convert each prefix into an ip_network,
# then combine them into DISALLOW_SUBNETS
__dis_subs = env('DISALLOW_SUBNETS', None)
if __dis_subs is not None:
    __dis_subs = str(__dis_subs).split(',')
    _dis_nets = [ipaddress.ip_network(net, strict=False) for net in __dis_subs]
    DISALLOW_SUBNETS = DISALLOW_SUBNETS + _dis_nets
