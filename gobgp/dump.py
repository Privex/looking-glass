#!/usr/bin/env python3
import grpc
from  google.protobuf.any_pb2 import Any
from dns.resolver import Resolver
import gobgp.gobgp_pb2
import gobgp.gobgp_pb2_grpc
import gobgp.attribute_pb2

channel = grpc.insecure_channel('localhost:50051')
stub = gobgp_pb2_grpc.GobgpApiStub(channel)

k = stub.ListPath(
    gobgp_pb2.ListPathRequest(
        family=gobgp_pb2.Family(
            afi=gobgp_pb2.Family.AFI_IP, 
            safi=gobgp_pb2.Family.SAFI_UNICAST
        )
    )
)
k6 = stub.ListPath(
    gobgp_pb2.ListPathRequest(
        family=gobgp_pb2.Family(
            afi=gobgp_pb2.Family.AFI_IP6, 
            safi=gobgp_pb2.Family.SAFI_UNICAST
        )
    )
)

paths = list(k)
paths6 = list(k6)

def asn_to_name(as_number: int):
    d = Resolver()
    res = d.query(f'AS{as_number}.asn.cymru.com', "TXT")
    if len(res) > 0:
        # res[0] is formatted like such: "15169 | US | arin | 2000-03-30 | GOOGLE - Google LLC, US"
        # with literal quotes. we need to strip them, split by pipe, extract the last element, then strip spaces.
        asname = str(res[0]).strip('"').split('|')[-1:][0].strip()
        return str(asname)
    return 'Unknown ASN'

# found on this gist
# https://gist.github.com/iwaseyusuke/df1e0300221b0c6aa1a98fc346621fdc
def unmarshal_any(any_msg):
    """
    Unpacks an `Any` message.

    If need to unpack manually, the following is a simple example::

        if any_msg.Is(attribute_pb2.IPAddressPrefix.DESCRIPTOR):
            ip_addr_prefix = attribute_pb2.IPAddressPrefix()
            any_msg.Unpack(ip_addr_prefix)
            return ip_addr_prefix
    """
    if any_msg is None:
        return None

    # Extract 'name' of message from the given type URL like
    # 'type.googleapis.com/type.name'.
    msg_name = any_msg.type_url.split('.')[-1]

    for pb in (gobgp_pb2, attribute_pb2):
        msg_cls = getattr(pb, msg_name, None)
        if msg_cls is not None:
            break
    assert msg_cls is not None

    msg = msg_cls()
    any_msg.Unpack(msg)
    return msg

as_counts = {}
as_counts6 = {}

for path in paths:
    d = path.destination
    p = d.paths[0]
    z = unmarshal_any(p.pattrs[1])

    zz = z.segments[0].numbers
    if len(zz) > 1:
        zz = zz[1]
    else:
        zz = zz[0]
    if zz not in as_counts:
        as_counts[zz] = 1
    else:
        as_counts[zz] += 1
    print('Prefix: {}, Source ASN: {}'.format(d.prefix, zz))

for path in paths6:
    d = path.destination
    p = d.paths[0]
    z = unmarshal_any(p.pattrs[1])

    zz = z.segments[0].numbers
    if len(zz) > 1:
        zz = zz[1]
    else:
        zz = zz[0]
    if zz not in as_counts6:
        as_counts6[zz] = 1
    else:
        as_counts6[zz] += 1
    print('Prefix: {}, Source ASN: {}'.format(d.prefix, zz))

print('--- v4 paths ---')
total_v4 = total_v6 = 0
for asn,num in as_counts.items():
    #print('ASN: {}   Prefixes: {}'.format(asn,num))
    asname = asn_to_name(asn)
    print(f'ASN: {asn:9} Name: {asname:20.20}     Prefixes: {num}')
    total_v4 += num

print('--- v6 paths ---')
for asn,num in as_counts6.items():
    asname = asn_to_name(asn)
    print(f'ASN: {asn:9} Name: {asname:20.20}     Prefixes: {num}')
    total_v6 += num

print('--- summary ---')
print(f'total v4: {total_v4} -- total v6: {total_v6}')
