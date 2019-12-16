"""Manufacturer commands"""

from struct import pack
from .base import BaseCommand, InvalidResponse


def CalcSNAuth(oldsn, newsn, uid3):
    s = 0
    for i in range(0x0E):
        s += ord(oldsn[i])
        s *= ord(newsn[i])
    s += uid3 + (uid3 << 4)
    s &= 0xFFFFFFFF
    if (s & 0x80000000) != 0:
        s = 0x100000000 - s

    return s % 1000000

class AuthError(Exception):
    pass


class WriteSN(BaseCommand):
    def __init__(self, dev, sn, auth):
        super(WriteSN, self).__init__(
            dst=dev, cmd=0x18, arg=0x10, data=pack("<14sL", sn, auth), has_response=False
        )
        self.dev = dev

    def handle_response(self, response):
        if len(response.data) != 0:
            raise InvalidResponse("WriteSN {0:X}".format(self.dev))
        if response.arg != 1:
            raise AuthError("WriteSN {0:X}".format(self.dev))
        self.has_response = True
        return True


__all__ = ["AuthError", "WriteSN", "CalcSNAuth"]
