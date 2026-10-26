"""Batch workflow, finite queue with reservations, and safe state transitions."""
import asyncio
from collections import deque
from .config import BatchConfig
from .protocol import Op, Result


class Controller:
    def __init__(self, a, b, defaults, evidence):
        self.a, self.b, self.config, self.evidence = a, b, defaults, evidence
        self.state, self.outcome, self.fault = "Idle", None, None
        self.queue = deque()
        self.batch_id = 0
        self.next_part = 1
        self.produced = self.accepted = self.rejected = 0
        self.producing = self.inspecting = None
        self.blocked = False
        self.stopping = False
        self.tasks = []
        self.generations = (0, 0)
        self.discarded = 0

    def snapshot(self):
        return dict(state=self.state, outcome=self.outcome, fault=self.fault, batch_id=self.batch_id,
                    config=self.config.as_dict(), produced=self.produced, accepted=self.accepted,
                    rejected=self.rejected, queued=list(self.queue), producing=self.producing,
                    inspecting=self.inspecting, blocked=self.blocked, stopping=self.stopping,
                    discarded=self.discarded, station_a=self.a.healthy, station_b=self.b.healthy,
                    simulation=self.evidence.simulated, evidence_directory=str(self.evidence.path))

    def set_state(self, state):
        previous, self.state = self.state, state
        self.evidence.record("state_changed", previous=previous, state=state, batch_id=self.batch_id)

    async def start(self, config: BatchConfig):
        if self.state != "Idle" or self.stopping:
            raise ValueError("Start requires Idle; Stop first to acknowledge a fault")
        if not self.a.healthy or not self.b.healthy:
            raise ValueError("Both stations must be connected before Start")
        if self.next_part + config.target_parts > 0xFFFFFFFF:
            raise ValueError("Part ID space exhausted; restart the system")
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.config = config
        self.batch_id += 1
        self.queue.clear()
        self.produced = self.accepted = self.rejected = self.discarded = 0
        self.fault = self.outcome = None
        self.producing = self.inspecting = None
        self.blocked = False
        try:
            await self.a.command(Op.CONFIG, arg0=config.production_ms)
            await self.b.command(Op.CONFIG, arg0=config.inspection_ms,
                                 arg1=config.reject_modulus, arg2=config.reject_offset)
        except Exception as error:
            self.fail(str(error))
            raise
        self.generations = (self.a.generation, self.b.generation)
        self.evidence.record("batch_started", batch_id=self.batch_id, config=config.as_dict())
        self.set_state("Running")
        self.tasks = [asyncio.create_task(self._produce()), asyncio.create_task(self._inspect()),
                      asyncio.create_task(self._watch())]

    def pause(self):
        if self.state != "Running":
            raise ValueError("Pause requires Running")
        self.set_state("Paused")

    def resume(self):
        if self.state != "Paused" or self.stopping:
            raise ValueError("Resume requires Paused")
        if not self.a.healthy or not self.b.healthy:
            raise ValueError("Both stations must be connected")
        self.set_state("Running")

    async def stop(self):
        if self.stopping:
            raise ValueError("Stop already in progress")
        self.stopping = True
        if self.state == "Running":
            self.set_state("Paused")
        # Do not cancel station commands in flight. Finish them or reach their
        # bounded failure deadline; never report this partial batch completed.
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.discarded = self.produced - self.accepted - self.rejected
        self.queue.clear()
        self.producing = self.inspecting = None
        self.outcome = "stopped"
        self.fault = None
        self.blocked = self.stopping = False
        self.set_state("Idle")
        self.evidence.record("batch_stopped", **self.snapshot())

    def fail(self, reason):
        if self.state != "Fault":
            self.fault = reason
            self.outcome = "faulted"
            self.set_state("Fault")
            self.evidence.record("fault", reason=reason)

    def _finished(self):
        if self.produced == self.config.target_parts and self.accepted + self.rejected == self.config.target_parts:
            if not self.stopping and self.state in ("Running", "Paused"):
                self.outcome = "completed"
                self.set_state("Idle")
                self.evidence.record("batch_completed", **self.snapshot())

    async def _produce(self):
        try:
            while self.state in ("Running", "Paused") and not self.stopping:
                if self.produced >= self.config.target_parts:
                    return
                full = len(self.queue) >= self.config.queue_capacity
                if full != self.blocked:
                    self.blocked = full
                    self.evidence.record("production_blocked" if full else "production_unblocked", queued=len(self.queue))
                if self.state == "Paused" or full:
                    await asyncio.sleep(0.01)
                    continue
                # Reserve one free queue slot before issuing production. Only
                # this coroutine appends; consumption can only free more space.
                part = self.next_part
                self.next_part += 1
                self.producing = part
                result = await self.a.command(Op.PRODUCE, part=part, duration_ms=self.config.production_ms)
                if self.state == "Fault":
                    return
                if result.arg0 != Result.OK:
                    raise RuntimeError("invalid production completion result")
                self.produced += 1
                self.queue.append(part)
                self.producing = None
                self.evidence.record("part_produced", part_id=part, batch_id=self.batch_id)
        except Exception as error:
            self.fail(str(error))
        finally:
            self.producing = None

    async def _inspect(self):
        try:
            while self.state in ("Running", "Paused") and not self.stopping:
                if self.state == "Paused" or not self.queue:
                    await asyncio.sleep(0.01)
                    continue
                part = self.queue.popleft()
                self.inspecting = part
                result = await self.b.command(Op.INSPECT, part=part, duration_ms=self.config.inspection_ms)
                if self.state == "Fault":
                    return
                if result.arg0 not in (Result.PASS, Result.FAIL):
                    raise RuntimeError("invalid inspection verdict")
                verdict = "PASS" if result.arg0 == Result.PASS else "FAIL"
                self.accepted += verdict == "PASS"
                self.rejected += verdict == "FAIL"
                self.evidence.part(self.batch_id, part, verdict, result.command)
                self.evidence.record("part_inspected", batch_id=self.batch_id, part_id=part,
                                     job_id=result.command, verdict=verdict)
                self.inspecting = None
                self._finished()
        except Exception as error:
            self.fail(str(error))
        finally:
            self.inspecting = None

    async def _watch(self):
        while self.state in ("Running", "Paused") and not self.stopping:
            if not self.a.healthy or not self.b.healthy or self.generations != (self.a.generation, self.b.generation):
                self.fail("Station disconnected, rebooted, or heartbeat expired; Stop to acknowledge")
                return
            await asyncio.sleep(0.05)

    async def close(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
