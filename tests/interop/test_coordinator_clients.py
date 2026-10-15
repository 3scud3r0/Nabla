import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import pytest
from services.coordinator.app import CoordinatorService
from services.coordinator.auth import token_for
from nablamath.research import calculate

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('coordinator_sdk', ROOT/'sdk/python/client.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
Client, Error = module.CoordinatorClient, module.CoordinatorError


@pytest.fixture
def coordinator(tmp_path):
    permissions = {p: {'create', 'read', 'lease', 'submit', 'heartbeat', 'cancel'} for p in ('alice', 'bob')}
    service = CoordinatorService(tmp_path/'queue.db', secret='test-secret', http_permissions=permissions)
    server = service.start_http()
    endpoint = f'http://127.0.0.1:{server.server_port}'
    yield endpoint, {p: token_for('test-secret', p) for p in permissions}
    server.shutdown(); server.server_close()


def test_python_end_to_end_consensus_and_cancellation(coordinator):
    endpoint, tokens = coordinator
    alice = Client(endpoint, 'alice', tokens['alice']); bob = Client(endpoint, 'bob', tokens['bob'])
    task = alice.create_task('x+1', {'x': '2'})
    assert alice.status(task) == 'pending'
    assert alice.lease()['task_id'] == task
    assert bob.lease()['task_id'] == task
    assert alice.heartbeat(task) > 0
    result = calculate('x+1', {'x': '2'}).content_id
    assert alice.submit(task, result) == 'awaiting_second_worker'
    assert bob.submit(task, result) == 'verified'
    assert alice.status(task) == 'verified'
    assert alice.lease() is None
    pending = alice.create_task('x+2', {'x': '2'})
    assert alice.cancel(pending) == 'cancelled'
    assert alice.status(pending) == 'cancelled'
    with pytest.raises(Error, match='403'):
        Client(endpoint, 'alice', 'invalid').status(task)


@pytest.mark.parametrize('endpoint', ['http://example.com', 'http://127.0.0.1/path', 'https://u:p@example.com',
                                      'ftp://localhost', 'http://127.0.0.1?x=1'])
def test_unsafe_endpoints_rejected(endpoint):
    with pytest.raises(ValueError): Client(endpoint, 'alice', 'token')


@pytest.fixture
def malformed_server():
    class Handler(BaseHTTPRequestHandler):
        body = b'{}'; content_type = 'application/json'; redirect = False
        def do_POST(self):
            self.send_response(302 if self.redirect else 200)
            self.send_header('Content-Type', self.content_type)
            self.send_header('Location', 'http://127.0.0.1:1/steal')
            self.end_headers(); self.wfile.write(self.body)
        def log_message(self, *_): pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{server.server_port}', Handler
    server.shutdown(); server.server_close()


@pytest.mark.parametrize('body', [b'{}', b'{"task_id":"bad"}', b'[]', b'not json',
                                     b'{"task_id":NaN}', b'{"task_id":"a","task_id":"b"}', b'\xff'])
def test_invalid_python_responses_rejected(malformed_server, body):
    endpoint, handler = malformed_server; handler.body = body
    with pytest.raises(Error): Client(endpoint, 'a', 'secret').create_task('1', {})


def test_python_bounds_content_type_and_redirect(malformed_server):
    endpoint, handler = malformed_server
    client = Client(endpoint, 'a', 'secret', max_response_bytes=32)
    handler.body = b' '*33
    with pytest.raises(Error): client.create_task('1', {})
    handler.body = b'{}'; handler.content_type = 'text/plain'
    with pytest.raises(Error): client.create_task('1', {})
    handler.content_type = 'application/json'; handler.redirect = True
    with pytest.raises(Error, match='302'): client.create_task('1', {})


def _node():
    node = shutil.which('node')
    if node is None: pytest.skip('Node unavailable; TypeScript runtime interop not executed')
    probe = subprocess.run([node, '--input-type=module', '-e',
                            "import {CoordinatorClient} from './sdk/typescript/client.ts';"],
                           cwd=ROOT, capture_output=True, text=True)
    if probe.returncode:
        version = subprocess.run([node, '--version'], capture_output=True, text=True).stdout.strip()
        if int(version.lstrip('v').split('.')[0]) < 22:
            pytest.skip('Node runtime lacks native TypeScript support; actual TS test not executed')
        pytest.fail(probe.stderr)
    return node


def test_typescript_actual_coordinator_interop(coordinator):
    node = _node(); endpoint, tokens = coordinator
    script = """
import assert from 'node:assert/strict';
import {CoordinatorClient} from './sdk/typescript/client.ts';
const [endpoint, aliceToken, bobToken, result] = JSON.parse(process.env.NABLA_SDK_TEST);
const alice = new CoordinatorClient(endpoint, 'alice', aliceToken);
const bob = new CoordinatorClient(endpoint, 'bob', bobToken);
const task = await alice.createTask('x+1', {x:'2'});
assert.equal(await alice.status(task), 'pending');
assert.equal((await alice.lease()).task_id, task);
assert.equal((await bob.lease()).task_id, task);
assert.ok(await alice.heartbeat(task) > 0);
assert.equal(await alice.submit(task, result), 'awaiting_second_worker');
assert.equal(await bob.submit(task, result), 'verified');
assert.equal(await alice.status(task), 'verified');
assert.equal(await alice.lease(), null);
await assert.rejects(() => new CoordinatorClient(endpoint, 'alice', 'invalid').status(task));
const pending = await alice.createTask('2+2', {});
assert.equal(await alice.cancel(pending), 'cancelled');
assert.throws(() => new CoordinatorClient('http://example.com', 'alice', 'x'));
"""
    import os
    env = dict(os.environ, NABLA_SDK_TEST=json.dumps([endpoint, tokens['alice'], tokens['bob'], calculate('x+1', {'x':'2'}).content_id]))
    result = subprocess.run([node, '--input-type=module', '-e', script], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


def test_typescript_invalid_response_bound_and_redirect(malformed_server):
    node = _node(); endpoint, handler = malformed_server
    import os
    script = """
import assert from 'node:assert/strict';
import {CoordinatorClient} from './sdk/typescript/client.ts';
await assert.rejects(() => new CoordinatorClient(process.env.NABLA_SDK_ENDPOINT,'a','secret',1000,32).createTask('1', {}));
"""
    for body, content, redirect in [(b'{}','application/json',False), (b' '*33,'application/json',False),
                                     (b'{}','text/plain',False), (b'{}','application/json',True)]:
        handler.body, handler.content_type, handler.redirect = body, content, redirect
        result = subprocess.run([node, '--input-type=module', '-e', script], cwd=ROOT,
                                env=dict(os.environ, NABLA_SDK_ENDPOINT=endpoint), capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
