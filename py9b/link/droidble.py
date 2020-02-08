"""BLE link using ABLE"""

from __future__ import absolute_import

try:
    from able import GATT_SUCCESS, Advertisement, BluetoothDispatcher
except ImportError:
    exit("error importing able")
try:
    from .base import BaseLink, LinkTimeoutException, LinkOpenException
except ImportError:
    exit("error importing .base")
from binascii import hexlify
from kivy.logger import Logger
from kivy.clock import mainthread
from kivy.properties import StringProperty

try:
    import queue
except ImportError:
    import Queue as queue

from threading import Event

try:
    from kivymd.toast import toast
except:
    print('no toast for you')


device_ids = {
"esx": bytearray(
    [
        0x4E, 0x42, 0x21, 0x00, 0x00, 0x00, 0x00, 0xDE,  # Ninebot ESx Bluetooth ID 424E2100000000DE
    ]
),
"esxclone": bytearray(
    [
        0x4E, 0x42, 0x21, 0x02, 0x00, 0x00, 0x00, 0xDC,  # Ninebot ESx Clone? Bluetooth ID 424E2100000000DE
    ]
),
"m365": bytearray(
    [
        0x4E, 0x42, 0x21, 0x00, 0x00, 0x00, 0x00, 0xDF,  # Xiaomi M365 Bluetooth ID 424E2100000000DF
    ]
),
"m365pro": bytearray(
    [
        0x4E, 0x42, 0x22, 0x01, 0x00, 0x00, 0x00, 0xDC,  # Xiaomi M365 Pro Bluetooth ID 424E2201000000DC
    ]
),
"max": bytearray(
    [
        0x4E, 0x42, 0x24, 0x02, 0x00, 0x00, 0x00, 0xD9,  # Ninebot Max Bluetooth ID 424E2401000000D9
    ]
),
"max555": bytearray(
    [
        0x4E, 0x42, 0x24, 0x00, 0x00, 0x00, 0x00, 0xDB,  # Ninebot Max BLE555 Bluetooth ID 424E2201000000DC
    ]
)
} #manufacturer data dictionary for identifying scooter dashboards

service_ids = {"retail": "6e400001-b5a3-f393-e0a9-e50e24dcca9e"}  # service UUID dictionary

receive_ids = {
    "retail": "6e400002-b5a3-f393-e0a9-e50e24dcca9e"# receive characteristic UUID dictionary
}

transmit_ids = {
    "retail": "6e400003-b5a3-f393-e0a9-e50e24dcca9e"# transmit characteristic UUID dictionary
}

key_ids = {
    '_pro_keys_char_uuid': "00000014-0000-1000-8000-00805f9b34fb",
    '_max_keys_char_uuid': "0000fe95-0000-1000-8000-00805f9b34fb"
} #key characteristic UUID dictionary

SCAN_TIMEOUT = 3
_write_chunk_size = 20

class Fifo:
    def __init__(self):
        self.q = queue.Queue()

    def write(self, data):  # put bytes
        for b in data:
            self.q.put(b)

    def read(self, size=1, timeout=None):  # but read string
        res = bytearray()
        for i in range(size):
            res.append(self.q.get(True, timeout))
        return res


class BLELink(BaseLink, BluetoothDispatcher):
    def __init__(self):
        super(BLELink, self).__init__()
        BluetoothDispatcher.__init__(self)
        self.rx_fifo = Fifo()
        self.addr = ''
        self.device = None
        self.device_list = []
        self.scoot_found = False
        self.state = StringProperty()
        self.tx_characteristic = None
        self.rx_characteristic = None
        self.keys_characteristic = None
        self.iotimeout = 2
        self.timeout = SCAN_TIMEOUT
        self.dump = True
        self.keys = None
        self.scanned = Event()
        self.keys_recovered = Event()
        self.connected = Event()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def discover(self, timeout):
        mainthread(self.start_scan)()
        self.state = "scan"
        try:
            toast(self.state)
        except:
            print(self.state)
        self.scanned.wait(timeout)
        mainthread(self.stop_scan)()


    def on_device(self, device, rssi, advertisement):
        Logger.debug("on_device event {}".format(list(advertisement)))
        res = []
        for ad in advertisement:
            print(ad)
            address = device.getAddress()
            name = device.getName()
            if self.addr is not '':
                if address.startswith(self.addr):
                    self.scoot_found = True
                if name and name.startswith(self.addr):
                    self.scoot_found = True
            elif ad.ad_type == Advertisement.ad_types.manufacturer_specific_data:
                for uuid in device_ids.values():
                    if ad.data.startswith(uuid):
                        self.scoot_found = True
                    else:
                        break
            if self.scoot_found:
                self.state = "found"
                try:
                    toast(self.state)
                except:
                    print(self.state)
                res.append((name, address))
                Logger.debug("Scooter detected: {}".format(name))
                self.device_list = res
                self.device = device
                self.scanned.set()
                self.stop_scan()

    def on_connection_state_change(self, status, state):
        if status == GATT_SUCCESS and state:  # connection established
            self.discover_services()  # discover what services a device offer
            self.connected.set()
            self.state = "connected"
            try:
                toast(self.state)
            except:
                print(self.state)
        else:  # disconnection or error
            self.close()

    def on_services(self, status, services):
        self.services = services
        for uuid in receive_ids.values():
            self.rx_characteristic = self.services.search(uuid)
            print("RX: " + uuid)
        for uuid in transmit_ids.values():
            self.tx_characteristic = self.services.search(uuid)
            print("TX: " + uuid)
        for uuid in key_ids.values():
            self.keys_characteristic = self.services.search(uuid)
            print("K: " + uuid)
        if self.tx_characteristic and self.rx_characteristic:
            self.enable_notifications(self.tx_characteristic, enable=True)
        else:
            return

    def on_characteristic_changed(self, tx_characteristic):
        if self.tx_characteristic:
            data = self.tx_characteristic.getValue()
            self.rx_fifo.write(data)
            return

    def on_characteristic_read(self, chara, data):
        if chara.getUuid().toString() == self.keys_characteristic:
            self.keys = bytearray(chara.getValue())
            self.keys_recovered.set()


    def open(self, port):
        self.addr = port
        if self.device:
            self.connect_gatt(self.device)
        else:
            self.close()

    def close(self):
        if self.device:
            self.close_gatt()
        self.services = None
        self.rx_characteristic = None
        self.tx_characteristic = None
        self.device = None
        self.addr = ''
        self.device_list = []
        if self.scanned.is_set():
            self.scanned.clear()
        if self.connected.is_set():
            self.connected.clear()
        self.state = "close"
        try:
            toast(self.state)
        except:
            print(self.state)

    def read(self, size):
        if self.device and self.connected.is_set():
            try:
                data = self.rx_fifo.read(size, timeout=self.iotimeout)
            except queue.Empty:
                raise LinkTimeoutException
            if self.dump:
                print("<", hexlify(data).upper())
            return data

    def write(self, data):
        if self.device and self.connected.is_set():
            if self.dump:
                print(">", hexlify(data).upper())
            size = len(data)
            ofs = 0
            while size:
                chunk_sz = min(size, _write_chunk_size)
                self.write_characteristic(
                    self.rx_characteristic, bytearray(data[ofs : ofs + chunk_sz])
                )
                ofs += chunk_sz
                size -= chunk_sz

    def scan(self):
        self.discover(self.timeout)
        return self.device_list

    def fetch_keys(self):
        self.read_characteristic(self.keys_characteristic)
        self.keys_recovered.wait(self.iotimeout)
        print('got keys!')
        return self.keys

    def on_error(self):
        print('error')
        if self.device:
            self.close()


__all__ = ["BLELink"]
