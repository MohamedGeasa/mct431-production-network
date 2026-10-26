import asyncio
from dataclasses import replace
import json
from pathlib import Path
import time
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from gateway.app import create_app
from gateway.client import StationClient
from gateway.config import load_config
from gateway.evidence import Evidence
from gateway.protocol import Kind, Message, Op, Result
from gateway.simulation import SimulatedTransport
from gateway.transports import TcpTransport


def wait_until(fn, timeout=8):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = fn()
        if result:
            return result
        time.sleep(.015)
    raise AssertionError("condition did not become true before deadline")


@pytest.fixture
def application(tmp_path):
    config = load_config(Path(__file__).parents[1] / "config/design.toml")
    config["logging"]["directory"] = str(tmp_path)
    app = create_app(config, simulated=True)
    with TestClient(app) as client:
        wait_until(lambda: all(client.get('/api/status').json()[key] for key in ('station_a','station_b')))
        yield app, client


def command(client, action, config=None, cmd_id=None):
    body = {"cmd_id": cmd_id or str(uuid4()), "action": action}
    if config is not None:
        body["config"] = config
    response = client.post('/api/commands', json=body)
    assert response.status_code in (200,202), response.text
    record = wait_until(lambda: (r if (r := client.get('/api/commands/' + body['cmd_id']).json())['phase'] != 'accepted' else None))
    assert record['phase'] == 'completed', record
    return body


def settings(**updates):
    return dict(target_parts=12, queue_capacity=2, production_ms=10, inspection_ms=45,
                reject_modulus=3, reject_offset=1, **{}) | updates


@pytest.mark.parametrize("production_ms,inspection_ms,capacity",[(10,45,1),(10,45,4),(50,5,2)])
def test_batches_backpressure_rule_and_csv(application, production_ms, inspection_ms, capacity):
    app, client = application
    command(client,'start', settings(production_ms=production_ms, inspection_ms=inspection_ms, queue_capacity=capacity))
    maximum = 0
    until = time.monotonic() + 8
    while time.monotonic() < until:
        status = client.get('/api/status').json()
        maximum = max(maximum, len(status['queued']))
        assert len(status['queued']) + (status['producing'] is not None) <= capacity
        if status['outcome'] == 'completed':
            break
        time.sleep(.005)
    assert status['state'] == 'Idle'
    assert status['produced'] == 12
    assert status['accepted'] == 8 and status['rejected'] == 4
    lines = (app.state.evidence.path / 'parts.csv').read_text().splitlines()
    assert len(lines) == 13
    events = [json.loads(x) for x in (app.state.evidence.path / 'events.jsonl').read_text().splitlines()]
    if production_ms < inspection_ms:
        assert any(e['event'] == 'production_blocked' for e in events)
    for name in ('delivered','accepted','completed'):
        assert any(e['event'] == name for e in events)
    assert all(e['simulation'] for e in events)


def test_pause_resume_stop_and_idempotent_http(application):
    app, client = application
    request = command(client,'start',settings(target_parts=50,production_ms=30,inspection_ms=60))
    batch = client.get('/api/status').json()['batch_id']
    assert client.post('/api/commands',json=request).status_code == 200
    assert client.get('/api/status').json()['batch_id'] == batch
    conflict = request | {'config':settings(target_parts=2)}
    assert client.post('/api/commands',json=conflict).status_code == 409
    command(client,'pause')
    time.sleep(.15)
    before = client.get('/api/status').json()
    time.sleep(.15)
    after = client.get('/api/status').json()
    assert before['state'] == after['state'] == 'Paused'
    assert before['produced'] == after['produced']
    assert before['accepted'] == after['accepted']
    command(client,'resume')
    wait_until(lambda: client.get('/api/status').json()['produced'] > before['produced'])
    command(client,'stop')
    stopped = client.get('/api/status').json()
    assert stopped['state'] == 'Idle' and stopped['outcome'] == 'stopped'
    assert stopped['accepted'] + stopped['rejected'] < 50
    assert stopped['queued'] == []


def test_websocket_and_bad_configuration(application):
    app, client = application
    with client.websocket_connect('/ws') as ws:
        assert ws.receive_json()['status']['simulation'] is True
    response = client.post('/api/commands',json={'cmd_id':str(uuid4()),'action':'start','config':settings(queue_capacity=0)})
    assert response.status_code == 400
    assert client.get('/api/status').json()['state'] == 'Idle'
    assert client.post('/api/commands',json={'cmd_id':'bad','action':'start'}).status_code == 400


def test_disconnect_faults_and_does_not_complete_batch(application):
    app, client = application
    command(client,'start',settings(target_parts=100))
    client.portal.call(app.state.controller.b.close)
    status = wait_until(lambda: (s if (s := client.get('/api/status').json())['state'] == 'Fault' else None))
    assert status['outcome'] == 'faulted'
    command(client,'stop')
    assert client.get('/api/status').json()['state'] == 'Idle'


def test_retry_lost_result_stale_reply_and_single_execution(tmp_path):
    async def scenario():
        log = Evidence(tmp_path, True)
        config = load_config(Path(__file__).parents[1] / 'config/design.toml')['communication']
        config |= dict(ack_timeout_s=.03, completion_grace_s=.02)
        class Lossy(SimulatedTransport):
            dropped = False
            async def receive(self):
                while True:
                    message = await super().receive()
                    if message.op == Op.INSPECT and message.kind == Kind.COMPLETED and not self.dropped:
                        self.dropped = True
                        # Inject a stale result for another session; client must ignore it.
                        return replace(message, session=message.session + 1)
                    return message
        transport = Lossy(2, log)
        station = StationClient(2, 123, lambda:transport, config, log)
        station.start()
        try:
            for _ in range(200):
                if station.healthy: break
                await asyncio.sleep(.01)
            await station.command(Op.CONFIG,arg0=10,arg1=3,arg2=1)
            result = await station.command(Op.INSPECT,part=2,duration_ms=10)
            assert result.arg0 == Result.FAIL
            assert transport.executions == 1
            assert any(e['event'] == 'command_timeout' for e in log.recent)
            assert any(e['event'] == 'stale_reply' for e in log.recent)
        finally:
            await station.close(); log.close()
    asyncio.run(scenario())


def test_tcp_stream_fragmentation_and_coalescing(tmp_path):
    async def scenario():
        log = Evidence(tmp_path, True)
        message = Message(Kind.HELLO,0,2,123,boot=42)
        wire = b'\x00\x24' + message.pack()
        finished = asyncio.Event()
        async def serve(reader, writer):
            try:
                writer.write(wire[:1]); await writer.drain(); await asyncio.sleep(.01)
                writer.write(wire[1:] + wire); await writer.drain()
                await reader.read(1)
            finally:
                writer.close(); await writer.wait_closed(); finished.set()
        server = await asyncio.start_server(serve,'127.0.0.1',0)
        transport = TcpTransport('127.0.0.1',server.sockets[0].getsockname()[1],log)
        try:
            await transport.open()
            assert await transport.receive() == message
            assert await transport.receive() == message
        finally:
            await transport.close(); await asyncio.wait_for(finished.wait(),2)
            server.close(); await server.wait_closed(); log.close()
    asyncio.run(scenario())
