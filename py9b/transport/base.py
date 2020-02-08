"""Transport abstract class"""

import time

def checksum(data):
    s = 0
    for c in data:
        s += c
    return (s & 0xFFFF) ^ 0xFFFF


class BaseTransport(object):
    MOTOR = 0x01
    ESC = 0x20
    BLE = 0x21
    BMS = 0x22
    EXTBMS = 0x23
    HOST = 0x3D

    DeviceNames = {
        MOTOR: "MOTOR",
        ESC: "ESC",
        BLE: "BLE",
        BMS: "BMS",
        EXTBMS: "EXTBMS",
        HOST: "HOST",
    }

    def __init__(self, link):
        self.link = link
        self.retries = 10

    def recv(self):
        raise NotImplementedError()

    def send(self, src, dst, cmd, arg, data=bytearray()):
        raise NotImplementedError()

    def execute(self, command, retries=None):
        exc = None
        self.send(command.request)
        try:
            rsp = self.recv()
            return command.handle_response(rsp)
        except Exception as e:
            exc = e
            for n in range(retries or self.retries):
                try:
                    rsp = self.recv()
                    return command.handle_response(rsp)
                except Exception as e:
                    exc = e
                if command.has_response:
                    exc = None
                    self.retries = 0
                if exc is not None:
                    raise exc
        self.retries = 10

    @staticmethod
    def GetDeviceName(dev):
        return BaseTransport.DeviceNames.get(dev, "%02X" % (dev))


__all__ = ["checksum", "BaseTransport"]
