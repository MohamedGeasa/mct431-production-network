"""Diagnostic station model. Never presented as physical ESP32 validation."""
import asyncio
from dataclasses import replace
import secrets
from .protocol import Kind, Message, Op, Result, atr_pack, atr_unpack, slip_encode, SlipDecoder


class SimulatedTransport:
    def __init__(self, station, evidence):
        self.station, self.evidence = station, evidence
        self.boot = secrets.randbits(32) or 1
        self.session = 0
        self.last = None
        self.result = None
        self.configured = False
        self.duration = 1
        self.n, self.k = 5, 0
        self.responses = asyncio.Queue()
        self.worker = None
        self.heartbeat = None
        self.executions = 0

    async def open(self):
        self.heartbeat = asyncio.create_task(self._greetings())

    async def _greetings(self):
        while True:
            await self.responses.put(Message(Kind.HELLO, 0, self.station, self.session, boot=self.boot))
            await asyncio.sleep(0.25)

    def _wire_roundtrip(self, message):
        if self.station == 1:
            wire = slip_encode(atr_pack(message.pack(), message.command))
            return Message.unpack(atr_unpack(SlipDecoder().feed(wire)[0])[2])
        wire = len(message.pack()).to_bytes(2, "big") + message.pack()
        return Message.unpack(wire[2:2 + int.from_bytes(wire[:2], "big")])

    async def send(self, message):
        message = self._wire_roundtrip(message)
        if message.kind == Kind.PING:
            return
        await self.responses.put(message.reply(Kind.DELIVERED))
        valid_binding = message.boot == self.boot and message.session != 0 and (
            self.session == message.session or (not self.session and message.op == Op.BIND))
        if not valid_binding or message.station != self.station or not message.command:
            await self.responses.put(message.reply(Kind.REJECTED, 1))
            return
        if self.last and message.command <= self.last.command:
            if message == self.last:
                await self.responses.put(message.reply(Kind.ACCEPTED))
                if self.result:
                    await self.responses.put(self.result)
            else:
                await self.responses.put(message.reply(Kind.REJECTED, 2))
            return
        if self.worker and not self.worker.done():
            await self.responses.put(message.reply(Kind.REJECTED, 3))
            return
        if message.op == Op.CONFIG:
            valid = 1 <= message.arg0 <= 60000 and (self.station == 1 or
                    (1 <= message.arg1 <= 1000000 and message.arg2 <= 1000000))
        elif message.op == Op.BIND:
            valid = True
        else:
            valid = self.configured and message.part > 0 and message.op == (Op.PRODUCE if self.station == 1 else Op.INSPECT)
        if not valid:
            await self.responses.put(message.reply(Kind.REJECTED, 4))
            return
        self.last, self.result = message, None
        self.session = message.session
        await self.responses.put(message.reply(Kind.ACCEPTED))
        if message.op == Op.CONFIG:
            self.duration, self.n, self.k = message.arg0, message.arg1, message.arg2
            self.configured = True
        if message.op in (Op.BIND, Op.CONFIG):
            self.result = message.reply(Kind.COMPLETED, Result.OK)
            await self.responses.put(self.result)
        else:
            self.executions += 1
            self.worker = asyncio.create_task(self._finish(message))

    async def _finish(self, message):
        await asyncio.sleep(self.duration / 1000)
        verdict = Result.OK
        if self.station == 2:
            verdict = Result.FAIL if (message.part + self.k) % self.n == 0 else Result.PASS
        self.result = message.reply(Kind.COMPLETED, verdict)
        await self.responses.put(self.result)

    async def receive(self):
        return self._wire_roundtrip(await self.responses.get())

    async def close(self):
        tasks = [t for t in (self.worker, self.heartbeat) if t]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
