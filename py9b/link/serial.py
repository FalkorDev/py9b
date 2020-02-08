"""Direct serial link"""

from __future__ import absolute_import
import serial
import serial.tools.list_ports as lp
from binascii import hexlify
from .base import BaseLink, LinkTimeoutException, LinkOpenException
from threading import Event


class SerialLink(BaseLink):
    def __init__(self, *args, **kwargs):
        super(SerialLink, self).__init__(*args, **kwargs)
        self.device = None
        self.timeout = 1
        self.connected = Event()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def scan(self):
        ports = lp.comports()
        res = [
            ("%s %04X:%04X" % (port.device, port.vid, port.pid), port.device)
            for port in ports
        ]
        return res

    def open(self, port):
        try:
            self.device = serial.Serial(
                port,
                115200,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
            )
            self.connected.set()
        except serial.SerialException:
            raise LinkOpenException

    def close(self):
        if self.device:
            if self.connected.is_set():
                self.connected.clear()
            self.device.close()
            self.device = None

    def read(self, size):
        try:
            data = self.device.read(size)
        except serial.SerialTimeoutException:
            raise LinkTimeoutException
        if len(data) < size:
            raise LinkTimeoutException
        if self.dump:
            print("<", hexlify(data).upper())
        return data

    def write(self, data):
        if self.dump:
            print(">", hexlify(data).upper())
        self.device.write(data)


__all__ = ["SerialLink"]
