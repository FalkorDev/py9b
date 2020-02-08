from ..transport.packet import BasePacket as PKT
from ..transport.base import BaseTransport as BT


class InvalidResponse(Exception):
    pass


class BaseCommand(object):
    def __init__(self, src=BT.HOST, dst=0, cmd=0, arg=0, data=bytearray(), has_response=False):
        self.has_response = has_response
        self.request = PKT(src, dst, cmd, arg, data)

    def handle_response(self, response):
        self.has_response = True
        return True


__all__ = ["BaseCommand", "InvalidResponse"]
