from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from ipaddress import IPv4Network, IPv6Network, IPv4Address, IPv6Address, ip_network, ip_address
from typing import Union, List

from lg.peerapp.settings import IX_NET_VER, OUR_ASN


class AddrFamily(Enum):
    IPV4 = IPv4Network
    IPV6 = IPv6Network


@dataclass
class SanePath:
    prefix: Union[IPv4Network, IPv6Network]
    family: AddrFamily
    next_hops: List[Union[IPv4Address, IPv6Address]] = field(default_factory=list)
    asn_path: List[int] = field(default_factory=list)
    communities: List[int] = field(default_factory=list)
    neighbor: Union[IPv4Address, IPv6Address] = None
    source_id: str = ""
    age: datetime = None

    @property
    def source_asn(self):
        return self.asn_path[0] if len(self.asn_path) > 0 else OUR_ASN
    
    @property
    def first_hop(self):
        return self.next_hops[0] if len(self.next_hops) > 0 else None
    
    @property
    def ixp(self):
        ix_nets = IX_NET_VER[type(self.first_hop)]
        for subnet, ixname in ix_nets:
            subnet = ip_network(subnet)
            if ip_address(self.first_hop) in subnet:
                # log.debug('First hop %s is in subnet %s (IXP: %s)', self.first_hop, subnet, ixname)
                return ixname
            # log.debug('Hop %s is NOT in subnet %s (IXP: %s)', self.first_hop, subnet, ixname)
        return 'N/A'
    
    def __iter__(self):
        d = {
            'prefix': str(self.prefix),
            'family': 'v4' if self.family == AddrFamily.IPV4 else 'v6',
            'next_hops': [str(hop) for hop in self.next_hops],
            'first_hop': str(self.first_hop),
            'asn_path': self.asn_path,
            'source_asn': self.source_asn,
            'communities': self.communities,
            'neighbor': str(self.neighbor),
            'age': str(self.age),
            'ixp': self.ixp
        }
        for k, v in d.items():
            yield (k, v,)
