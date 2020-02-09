import asyncio

from bleak import discover, BleakClient
from py9b.link.base import BaseLink, LinkTimeoutException
from threading import Thread
from threading import Event

_rx_char_uuid = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
_tx_char_uuid = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
_keys_char_uuid = "00000014-0000-1000-8000-00805f9b34fb"

_manuf_id = 0x424e
_manuf_data_ninebot = [33, 0, 0, 0, 0, 222]
_manuf_data_xiaomi =  [33, 0, 0, 0, 0, 223]
_manuf_data_xiaomi_pro =  [34, 1, 0, 0, 0, 220]

_write_chunk_size = 20  # as in android dumps

try:
    import queue
except ImportError:
    import Queue as queue


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


def run_worker(loop):
    print("Starting event loop", loop)
    asyncio.set_event_loop(loop)
    loop.run_forever()


_write_chunk_size = 20


class BLELink(BaseLink):
    def __init__(self, device="hci0", loop=None, *args, **kwargs):
        self.adapter = device
        self.timeout = 2
        self.loop = loop or asyncio.get_event_loop()
        self._rx_fifo = Fifo()
        self.device = None
        self._th = None
        self.scanned = Event()
        self.connected = Event()

    def __enter__(self):
        self.start()
        return self

    def start(self):
        if self._th or self.loop.is_running():
            return

        self._th = Thread(target=run_worker, args=(self.loop,))
        self._th.daemon = True
        self._th.start()

    def __exit__(self, exc_type, exc_value, traceback):
        if self.device:
            self.close()

    def close(self):
        asyncio.run_coroutine_threadsafe(self.device.disconnect(), self.loop).result(
            10
        )
        if self.scanned.is_set():
            self.scanned.clear()
        if self.connected.is_set():
            self.connected.clear()

    def scan(self, timeout=1):
        devices = asyncio.run_coroutine_threadsafe(
            discover(timeout=timeout, device=self.adapter), self.loop
        ).result(timeout*3)
        self.scanned.set()

        # We need to keep scanning going for connect() to properly work
        asyncio.run_coroutine_threadsafe(
            discover(timeout=timeout, device=self.adapter), self.loop
        )

        return [
            (dev.name, dev.address)
            for dev in devices
            if dev.metadata.get('manufacturer_data', {}).get(_manuf_id, [])
                in [_manuf_data_xiaomi, _manuf_data_xiaomi_pro, _manuf_data_ninebot]
        ]

    def open(self, port):
        fut = asyncio.run_coroutine_threadsafe(self._connect(port), self.loop)
        fut.result(10)

    async def _connect(self, port):
        if isinstance(port, tuple):
            port = port[1]
        self.device = BleakClient(port, device=self.adapter)
        await self.device.connect()
        print("connected")
        self.connected.set()
        await self.device.start_notify(_tx_char_uuid, self._data_received)
        print("services:", list(await self.device.get_services()))

    def _data_received(self, sender, data):
        self._rx_fifo.write(data)

    def write(self, data):
        size = len(data)
        ofs = 0
        while size:
            chunk_sz = min(size, _write_chunk_size)
            self._write_chunk(bytearray(data[ofs : ofs + chunk_sz]))
            ofs += chunk_sz
            size -= chunk_sz

    def _write_chunk(self, data):
        fut = asyncio.run_coroutine_threadsafe(
            self.device.write_gatt_char(_rx_char_uuid, bytearray(data), True),
            self.loop,
        )
        return fut.result(3)

    def read(self, size):
        try:
            data = self._rx_fifo.read(size, timeout=self.timeout)
        except queue.Empty:
            raise LinkTimeoutException
        return data

    def fetch_keys(self):
        return asyncio.run_coroutine_threadsafe(
            self.device.read_gatt_char(_keys_char_uuid), self.loop
        ).result(5)
