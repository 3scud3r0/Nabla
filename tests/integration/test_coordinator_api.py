from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from http.client import HTTPConnection
import json
from threading import Barrier
from unittest.mock import patch

import pytest

from nablamath.coordination import LocalCoordinator
from nablamath.research import calculate
from services.coordinator.app import CoordinatorService
from services.coordinator.auth import token_for
from services.coordinator.events import EventLog


@pytest.fixture
def api(tmp_path):
    service = CoordinatorService(tmp_path / "api.db", secret="test-only-secret", max_pending_tasks=2,
        http_permissions={"owner": {"create", "read", "cancel"},
                          "worker-a": {"lease", "heartbeat", "submit"},
                          "worker-b": {"lease", "heartbeat", "submit"}})
    server = service.start_http()

    def request(method, path, payload=None, participant="owner", *, raw=None, extra_headers=None):
        headers = {}
        if participant is not None:
            headers = {"X-Nabla-Participant": participant,
                       "Authorization": "Bearer " + token_for("test-only-secret", participant)}
        headers.update(extra_headers or {})
        body = raw if raw is not None else json.dumps(payload) if payload is not None else None
        connection = HTTPConnection(*server.server_address, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    yield service, request
    server.shutdown()
    server.server_close()


def test_http_two_workers_replay_heartbeats_and_idempotent_submission(api):
    service, request = api
    assert request("GET", "/health", participant=None)[0] == 200
    status, result = request("POST", "/tasks", {"expression": "(x+x)/x", "values": {"x": 3}})
    assert status == 200
    identifier = result["task_id"]
    for worker in ("worker-a", "worker-b"):
        status, result = request("POST", "/leases", {"seconds": 60}, worker)
        assert status == 200 and result["lease"]["task_id"] == identifier
        assert request("POST", f"/tasks/{identifier}/heartbeat", {"seconds": 120}, worker)[0] == 200
    result_id = calculate("(x+x)/x", {"x": 3}).content_id
    assert request("POST", f"/tasks/{identifier}/submit", {"result_id": result_id}, "worker-a")[1]["status"] == "awaiting_second_worker"
    assert request("POST", f"/tasks/{identifier}/submit", {"result_id": result_id}, "worker-a")[1]["status"] == "awaiting_second_worker"
    assert request("POST", f"/tasks/{identifier}/submit", {"result_id": result_id}, "worker-b")[1]["status"] == "verified"
    assert request("POST", f"/tasks/{identifier}/submit", {"result_id": result_id}, "worker-a")[1]["status"] == "verified"
    assert request("GET", f"/tasks/{identifier}")[1]["status"] == "verified"
    assert service.events.verify()


def test_http_authentication_capabilities_malformed_requests_and_quotas(api):
    service, request = api
    body = {"expression": "1+1", "values": {}}
    assert request("POST", "/tasks", body, participant=None)[0] == 401
    assert request("POST", "/tasks", body, extra_headers={"Authorization": "Bearer wrong"})[0] == 403
    assert request("POST", "/tasks", body, participant="worker-a")[0] == 403
    assert request("POST", "/tasks", body, participant="unregistered")[0] == 403
    for raw in ['{"expression":"1","expression":"2","values":{}}', '{"x":NaN}', '[]']:
        assert request("POST", "/tasks", raw=raw)[0] == 400
    assert request("POST", "/tasks", raw=" "*65537)[0] == 413
    for expression, values in [(1, {}), ("1", []), ("__import__('os')", {}),
                                ("((((2**16)**16)**16)**16)", {}), ("x", {"x": True})]:
        assert request("POST", "/tasks", {"expression": expression, "values": values})[0] == 400
    assert request("GET", "/unknown")[0] == 404
    assert request("POST", "/tasks", body)[0] == 200
    assert request("POST", "/tasks", body)[0] == 200  # duplicate does not consume quota
    assert request("POST", "/tasks", {"expression": "2+2", "values": {}})[0] == 200
    assert request("POST", "/tasks", {"expression": "3+3", "values": {}})[0] == 400


def test_http_cancellation_and_default_deny(api, tmp_path):
    _, request = api
    _, result = request("POST", "/tasks", {"expression": "1+1", "values": {}})
    key = result["task_id"]
    request("POST", "/leases", {"seconds": 60}, "worker-a")
    assert request("POST", f"/tasks/{key}/cancel", {}, "worker-a")[0] == 403
    assert request("POST", f"/tasks/{key}/cancel", {})[1]["status"] == "cancelled"
    assert request("POST", f"/tasks/{key}/cancel", {})[0] == 200
    assert request("POST", f"/tasks/{key}/heartbeat", {"seconds": 60}, "worker-a")[0] == 400
    assert request("POST", f"/tasks/{key}/submit", {"result_id": calculate("1+1", {}).content_id}, "worker-a")[0] == 400
    service = CoordinatorService(tmp_path / "default.db", secret="test-only-secret")
    from services.coordinator.api import dispatch
    with pytest.raises(PermissionError):
        dispatch(service, "POST", "/tasks", "owner", token_for("test-only-secret", "owner"), {"expression": "1", "values": {}})


def test_expired_leases_recover_across_reopen_and_heartbeat_checks(tmp_path):
    path = tmp_path / "queue.db"
    queue = LocalCoordinator(path)
    key = queue.add("1+1", {})
    with patch("nablamath.coordination.local.time.time", return_value=1000):
        assert queue.lease("worker", 1)
        assert queue.lease("worker") is None
    queue = LocalCoordinator(path)
    with patch("nablamath.coordination.local.time.time", return_value=1002):
        with pytest.raises(ValueError):
            queue.heartbeat("worker", key)
        assert queue.lease("worker", 10)["lease_expires_unix"] == 1012
        assert queue.heartbeat("worker", key, 20) == 1022
        with pytest.raises(ValueError):
            queue.heartbeat("other", key)
    with pytest.raises(ValueError):
        queue.lease("worker", True)
    with pytest.raises(ValueError):
        queue.submit("worker", key, None)


def test_sqlite_concurrent_leases_and_atomic_pending_quota(tmp_path):
    queue = LocalCoordinator(tmp_path / "queue.db")
    queue.add("1+1", {})
    barrier = Barrier(12)
    def lease(index):
        barrier.wait(timeout=10)
        return queue.lease(f"worker-{index}")
    with ThreadPoolExecutor(max_workers=12) as executor:
        leases = list(executor.map(lease, range(12)))
    assert sum(lease is not None for lease in leases) == 2
    queue = LocalCoordinator(tmp_path / "quota.db")
    def add(index):
        try:
            return queue.add(f"{index}+1", {}, max_pending=1)
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(add, range(8)))
    assert sum(result is not None for result in results) == 1


def test_event_log_concurrency_snapshot_and_previous_hash_tampering():
    log = EventLog()
    payload = {"value": [1]}
    log.append("first", payload)
    payload["value"].append(2)
    assert log.events[0].payload == {"value": [1]}
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda i: log.append("concurrent", {"i": i}), range(100)))
    assert len(log.events) == 101 and log.verify()
    log.events[-1] = replace(log.events[-1], previous_hash="f"*64)
    assert not log.verify()
