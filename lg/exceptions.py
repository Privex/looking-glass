from privex.helpers import PrivexException


class IPNotFound(PrivexException):
    """Raised when a given IP address cannot be found (e.g. in a dict/list)"""


class InvalidHostException(PrivexException):
    pass


class MissingArgsException(PrivexException):
    pass


class DatabaseConnectionFail(PrivexException):
    """Raised when there's a connectivity problem with some form of database"""
    pass


class GoBGPException(PrivexException):
    """Raised to wrap certain GoBGP / grpc library exceptions"""
    pass
