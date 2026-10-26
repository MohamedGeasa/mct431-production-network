"""One outstanding command per station; explicit delivery/acceptance/completion."""
import asyncio
from dataclasses import asdict
import time
from .protocol import Kind, Message, Op


class StationClient:
    def __init__(self, station, session, factory, config, evidence):
        self.station, self.session = station, session
        self.factory, self.config, self.evidence = factory, config, evidence
        self.transport = None
        self.boot = 0
        self.sequence = 0
        self.last_seen = 0.0
        self.ready = False
        self.pending = None
        self.request = None
        self.accepted = False
        self.delivered = False
        self.lock = asyncio.Lock()
        self.send_lock = asyncio.Lock()
        self.task = None
        self.generation = 0

    def start(self):
        self.task = asyncio.create_task(self._run())

    async def close(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    @property
    def healthy(self):
        return self.ready and time.monotonic() - self.last_seen < self.config["heartbeat_timeout_s"]

    async def _send(self, message):
        async with self.send_lock:
            await self.transport.send(message)

    async def _reader(self):
        while True:
            message = await asyncio.wait_for(self.transport.receive(), self.config["heartbeat_timeout_s"])
            if message.station != self.station:
                raise ConnectionError("unexpected station identity")
            if message.kind == Kind.HELLO:
                if self.boot and message.boot != self.boot:
                    raise ConnectionError("station rebooted; previous results are invalid")
                self.boot = message.boot
                if message.session not in (0, self.session):
                    raise ConnectionError("station bound to another gateway; wait for watchdog/reset")
                self.last_seen = time.monotonic()
                continue
            if message.session != self.session or message.boot != self.boot:
                self.evidence.record("stale_reply", station=self.station, message=asdict(message))
                continue
            self.last_seen = time.monotonic()
            if not self.request or message.command != self.request.command or message.part != self.request.part or message.op != self.request.op:
                self.evidence.record("unmatched_reply", station=self.station, message=asdict(message))
                continue
            if not self.pending or self.pending.done():
                continue
            self.evidence.record(Kind(message.kind).name.lower(), station=self.station,
                                 command_id=message.command, part_id=message.part,
                                 session=message.session, boot=message.boot, result=message.arg0)
            if message.kind == Kind.DELIVERED:
                self.delivered = True
            elif message.kind == Kind.ACCEPTED:
                self.accepted = self.delivered
            elif message.kind == Kind.REJECTED:
                self.pending.set_exception(RuntimeError(f"station {self.station} rejected command: code {message.arg0}"))
            elif message.kind == Kind.COMPLETED:
                if not self.accepted:
                    self.pending.set_exception(RuntimeError("completion without delivery and acceptance"))
                else:
                    self.pending.set_result(message)

    async def _heartbeat(self):
        while True:
            if self.boot:
                await self._send(Message(Kind.PING, 0, self.station, self.session, boot=self.boot))
            await asyncio.sleep(1)

    async def _run(self):
        while True:
            reader = heartbeat = None
            try:
                self.boot = 0
                self.transport = self.factory()
                await self.transport.open()
                reader = asyncio.create_task(self._reader())
                until = time.monotonic() + self.config["heartbeat_timeout_s"]
                while not self.boot:
                    if reader.done():
                        await reader
                    if time.monotonic() > until:
                        raise TimeoutError("no station greeting")
                    await asyncio.sleep(0.02)
                heartbeat = asyncio.create_task(self._heartbeat())
                await self.command(Op.BIND, allow_unready=True)
                self.generation += 1
                self.ready = True
                self.evidence.record("connected", station=self.station, boot=self.boot)
                done, _ = await asyncio.wait([reader, heartbeat], return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    await task
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.evidence.record("disconnected", station=self.station, reason=str(error))
            finally:
                self.ready = False
                if self.pending and not self.pending.done():
                    self.pending.set_exception(ConnectionError("station link lost"))
                for task in (reader, heartbeat):
                    if task:
                        task.cancel()
                await asyncio.gather(*(t for t in (reader, heartbeat) if t), return_exceptions=True)
                if self.transport:
                    await self.transport.close()
            await asyncio.sleep(self.config["reconnect_s"])

    async def command(self, op, part=0, arg0=0, arg1=0, arg2=0, duration_ms=0, allow_unready=False):
        async with self.lock:
            if not allow_unready and not self.healthy:
                raise ConnectionError(f"station {self.station} is not ready")
            self.sequence += 1
            if self.sequence > 0xFFFFFFFF:
                raise RuntimeError("command ID space exhausted; restart gateway and stations")
            request = Message(Kind.COMMAND, op, self.station, self.session,
                              self.sequence, part, arg0, arg1, arg2, self.boot)
            self.request = request
            self.pending = asyncio.get_running_loop().create_future()
            self.accepted = self.delivered = False
            timeout = self.config["ack_timeout_s"] + duration_ms / 1000 + self.config["completion_grace_s"]
            try:
                for attempt in range(1, self.config["max_attempts"] + 1):
                    self.evidence.record("command_sent", attempt=attempt, message=asdict(request))
                    await self._send(request)
                    try:
                        return await asyncio.wait_for(asyncio.shield(self.pending), timeout)
                    except asyncio.TimeoutError:
                        self.evidence.record("command_timeout", station=self.station, command_id=request.command, attempt=attempt)
                raise TimeoutError(f"station {self.station}: command {request.command} exhausted retries")
            finally:
                if self.pending and not self.pending.done():
                    self.pending.cancel()
                self.request = None
