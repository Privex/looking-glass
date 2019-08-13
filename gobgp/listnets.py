
import grpc
from google.protobuf.any_pb2 import Any
import gobgp_pb2
import gobgp_pb2_grpc
import attribute_pb2

channel = grpc.insecure_channel('localhost:50051')

stub = gobgp_pb2_grpc.GobgpApiStub(channel)
# stub.GetTable(gobgp_pb2.GetTableRequest())
# k = stub.ListPath(gobgp_pb2.ListPathRequest('ipv4'))

k = stub.ListPath(
    gobgp_pb2.ListPathRequest(
        family=gobgp_pb2.Family(
            afi=gobgp_pb2.Family.AFI_IP,
            safi=gobgp_pb2.Family.SAFI_UNICAST
        )
    )
)

z = k.next()

print(z.destination.ListFields())

l = z.destination.paths[0]

print( l.ListFields())
print(l.ListFields()[1][1][1].value)

