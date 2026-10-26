"""HTTP control and WebSocket observation. One gateway process, one worker."""
import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
from pathlib import Path
import secrets
from uuid import UUID
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .client import StationClient
from .config import BatchConfig
from .controller import Controller
from .evidence import Evidence
from .simulation import SimulatedTransport
from .transports import SerialTransport, TcpTransport


def create_app(config, simulated=False):
    evidence = Evidence(config["logging"]["directory"], simulated)
    link = config["communication"]
    session = secrets.randbits(64) or 1
    def factory(station):
        if simulated:
            return lambda: SimulatedTransport(station, evidence)
        if station == 1:
            return lambda: SerialTransport(link["serial_port"], link["baud_rate"], evidence)
        return lambda: TcpTransport(link["inspection_host"], link["inspection_port"], evidence)
    a = StationClient(1, session, factory(1), link, evidence)
    b = StationClient(2, session, factory(2), link, evidence)
    controller = Controller(a, b, BatchConfig(**config["production"]), evidence)
    control_lock = asyncio.Lock()
    commands = {}

    @asynccontextmanager
    async def lifespan(app):
        a.start()
        b.start()
        yield
        await controller.close()
        for record in commands.values():
            if "task" in record:
                record["task"].cancel()
        await asyncio.gather(*(r["task"] for r in commands.values() if "task" in r), return_exceptions=True)
        await a.close()
        await b.close()
        evidence.close()

    app = FastAPI(title="MCT431 Milestone 1", lifespan=lifespan)
    app.state.controller = controller
    app.state.evidence = evidence
    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/")
    async def index():
        return FileResponse(static / "index.html")

    @app.get("/api/status")
    async def status():
        return controller.snapshot()

    @app.get("/api/commands/{cmd_id}")
    async def command_status(cmd_id: str):
        record = commands.get(cmd_id)
        return JSONResponse({k: v for k, v in record.items() if k not in ("task", "fingerprint")} if record
                            else {"error": "unknown command"}, status_code=200 if record else 404)

    async def execute(cmd_id, action, batch):
        record = commands[cmd_id]
        try:
            async with control_lock:
                if action == "start":
                    await controller.start(batch)
                elif action == "pause":
                    controller.pause()
                elif action == "resume":
                    controller.resume()
                else:
                    await controller.stop()
            record["phase"] = "completed"
            record["result"] = {"action": action, "state": controller.state}
            evidence.record("operator_completion", cmd_id=cmd_id, result=record["result"])
        except Exception as error:
            record["phase"], record["error"] = "failed", str(error)
            evidence.record("operator_failure", cmd_id=cmd_id, reason=str(error))

    @app.post("/api/commands")
    async def command(request: Request):
        if int(request.headers.get("content-length", "0")) > 4096:
            return JSONResponse({"error": "request too large"}, status_code=413)
        raw = await request.body()
        if len(raw) > 4096:
            return JSONResponse({"error": "request too large"}, status_code=413)
        try:
            body = json.loads(raw)
            if not isinstance(body, dict) or set(body) - {"cmd_id", "action", "config"}:
                raise ValueError("expected cmd_id, action, and optional config")
            cmd_id = str(UUID(body["cmd_id"]))
            action = body["action"]
            if action not in ("start", "pause", "resume", "stop"):
                raise ValueError("unknown action")
            if action != "start" and "config" in body:
                raise ValueError("configuration belongs only on Start")
            batch = BatchConfig(**body.get("config", controller.config.as_dict())) if action == "start" else None
            fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            evidence.record("operator_rejected", reason=str(error))
            return JSONResponse({"error": str(error)}, status_code=400)
        evidence.record("operator_delivery", cmd_id=cmd_id, action=action)
        if cmd_id in commands:
            previous = commands[cmd_id]
            if fingerprint != previous["fingerprint"]:
                return JSONResponse({"error": "identifier reused with different content"}, status_code=409)
            return {k: v for k, v in previous.items() if k not in ("task", "fingerprint")}
        if len(commands) >= 4096:
            return JSONResponse({"error": "command history full; restart between demonstrations"}, status_code=409)
        record = dict(cmd_id=cmd_id, phase="accepted", fingerprint=fingerprint)
        commands[cmd_id] = record
        evidence.record("operator_acceptance", cmd_id=cmd_id, action=action)
        record["task"] = asyncio.create_task(execute(cmd_id, action, batch))
        return JSONResponse({"cmd_id": cmd_id, "phase": "accepted"}, status_code=202)

    @app.websocket("/ws")
    async def websocket(socket: WebSocket):
        await socket.accept()
        try:
            while True:
                await socket.send_json({"status": controller.snapshot(), "events": evidence.recent[-20:]})
                await asyncio.sleep(0.25)
        except (WebSocketDisconnect, RuntimeError):
            pass

    return app
