# When this script is run for the first time, it might prompt you for
# permission. Accept the permission and run this script again, then it should
# send the data as expected.

# Kivy is needed for pyjnius behind the scene.
import kivy
from usb4a import usb
from usbserial4a import serial4a
import serial
from binascii import hexlify
from .base import BaseLink, LinkTimeoutException, LinkOpenException
from threading import Event

class SerialLink(BaseLink):
    def __init__(self, *args, **kwargs):
        super(SerialLink, self).__init__(*args, **kwargs)
        self.device = None
        self.usb_device_name_list = None
        self.timeout = 1
        self.connected = Event()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def scan(self):
        usb_device_list = usb.get_usb_device_list()
        res = []
        self.usb_device_name_list = [device.getDeviceName() for device in usb_device_list]
        usb_device_dict = {
        device.getDeviceName():[            # Device name
        device.getVendorId(),           # Vendor ID
        device.getManufacturerName(),   # Manufacturer name
        device.getProductId(),          # Product ID
        device.getProductName()         # Product name
        ] for device in usb_device_list
        }
        res = self.usb_device_name_list
        print(res)
        return res


    def open(self, port):
        if port:
            try:
                self.device = serial4a.get_serial_port(
                    port,
                    115200,   # Baudrate
                    8,      # Number of data bits(5, 6, 7 or 8)
                    'N',    # Parity('N', 'E', 'O', 'M' or 'S')
                    1)      # Number of stop bits(1, 1.5 or 2)

                if not usb.has_usb_permission(self.device):
                    usb.request_usb_permission(self.device)
                    return
            except:
                print('Failed to open Serial device')
        else:
            try:
                self.device = serial4a.get_serial_port(
                    usb_device_list[0].getDeviceName(),
                    115200,   # Baudrate
                    8,      # Number of data bits(5, 6, 7 or 8)
                    'N',    # Parity('N', 'E', 'O', 'M' or 'S')
                    1)      # Number of stop bits(1, 1.5 or 2)

                if not usb.has_usb_permission(self.device):
                    usb.request_usb_permission(self.device)
                    return
            except:
                print('Failed to open Serial device')

        if self.device is not None:
            self.connected.set()
            return self.device
        else:
            print('failed to open SerialLink')
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
