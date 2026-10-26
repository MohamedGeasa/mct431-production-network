"""Serial ATR/SLIP and TCP length-prefix transports, both carrying Message."""
import asyncio
from collections import deque
from .protocol import Message, SlipDecoder, atr_pack, atr_unpack, slip_encode


class TcpTransport:
    def __init__(self, host, port, evidence):
        self.host, self.port, self.evidence = host, port, evidence
        self.writer = None

    async def open(self):
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), 3)

    async def send(self, message):
        payload = message.pack()
        wire = len(payload).to_bytes(2, "big") + payload
        self.writer.write(wire)
        await self.writer.drain()
        self.evidence.record("wire_tx", link="tcp", hex=wire.hex())

    async def receive(self):
        prefix = await self.reader.readexactly(2)
        size = int.from_bytes(prefix, "big")
        if size != 36:
            raise ConnectionError(f"invalid TCP frame length: {size}")
        payload = await self.reader.readexactly(size)
        self.evidence.record("wire_rx", link="tcp", hex=(prefix + payload).hex())
        return Message.unpack(payload)

    async def close(self):
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except OSError:
                pass


class SerialTransport:
    def __init__(self, port, baud, evidence):
        self.port, self.baud, self.evidence = port, baud, evidence
        self.serial = None
        self.decoder, self.pending = SlipDecoder(), deque()
        self.sequence = 0

    async def open(self):
        import serial
        # Set these BEFORE opening to avoid intentionally pulsing board reset.
        self.serial = serial.Serial(port=None, baudrate=self.baud, timeout=0.1, write_timeout=1)
        self.serial.dtr = False
        self.serial.rts = False
        self.serial.port = self.port
        await asyncio.to_thread(self.serial.open)

    async def send(self, message):
        wire = slip_encode(atr_pack(message.pack(), self.sequence))
        self.sequence = (self.sequence + 1) & 0xFFFFFFFF
        count = await asyncio.to_thread(self.serial.write, wire)
        if count != len(wire):
            raise ConnectionError("short serial write")
        self.evidence.record("wire_tx", link="serial", hex=wire.hex())

    async def receive(self):
        while True:
            if not self.pending:
                data = await asyncio.to_thread(self.serial.read, 256)
                if data:
                    self.evidence.record("wire_rx", link="serial", hex=data.hex())
                    self.pending.extend(self.decoder.feed(data))
            while self.pending:
                try:
                    test, seq, payload = atr_unpack(self.pending.popleft())
                    if test != 1:
                        raise ValueError("unexpected serial ATR test_id")
                    self.evidence.record("atr_rx", sequence=seq)
                    return Message.unpack(payload)
                except ValueError as error:
                    self.evidence.record("frame_rejected", link="serial", reason=str(error))

    async def close(self):
        if self.serial:
            await asyncio.to_thread(self.serial.close)
