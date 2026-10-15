"""API local opcional, apenas loopback por padrão, usando a biblioteca padrão."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from .auth import authenticate
from .api import dispatch, SCOPES
from nablamath.core.semantic_contracts import load_json
from .events import EventLog
from .scheduler import Scheduler


class CoordinatorService:
    def __init__(self, database: str | Path, *, secret: str, http_permissions=None, max_pending_tasks=1000):
        if not isinstance(secret, str) or not secret or len(secret) > 4096:
            raise ValueError("Secret required")
        if type(max_pending_tasks) is not int or not 1 <= max_pending_tasks <= 10000:
            raise ValueError("Invalid pending task quota")
        if http_permissions is not None and not isinstance(http_permissions, dict):
            raise ValueError("Explicit HTTP permission mapping required")
        self.http_permissions = {}
        for participant, scopes in (http_permissions or {}).items():
            if (not isinstance(participant, str) or not participant.strip() or len(participant) > 128
                    or not isinstance(scopes, (set, frozenset, list, tuple))
                    or any(not isinstance(scope, str) or scope not in SCOPES for scope in scopes)):
                raise ValueError("Invalid participant capabilities")
            self.http_permissions[participant] = frozenset(scopes)
        self.max_pending_tasks = max_pending_tasks
        self.scheduler = Scheduler(database)
        self.secret = secret
        self.events = EventLog()

    def create_task(self, participant_id: str, token: str, expression: str, values: dict) -> str:
        principal = authenticate(self.secret, participant_id, token, frozenset({"write"}))
        task_id = self.scheduler.queue.add(expression, values, max_pending=self.max_pending_tasks)
        self.events.append("task.created", {"task_id": task_id, "participant": principal.participant_id})
        return task_id

    def lease(self, participant_id: str, token: str) -> dict | None:
        authenticate(self.secret, participant_id, token)
        return self.scheduler.lease(participant_id)

    def start_http(self, host: str = "127.0.0.1", port: int = 0):
        service = self
        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(5)

            def respond(self, status, payload):
                body = json.dumps(payload, allow_nan=False).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def handle_api(self, method):
                participant = self.headers.get("X-Nabla-Participant", "")
                authorization = self.headers.get("Authorization", "")
                if not participant or not authorization.startswith("Bearer "):
                    self.respond(401, {"error": "authentication_required"})
                    return
                try:
                    payload = {}
                    if method == "POST":
                        length = self.headers.get("Content-Length", "")
                        if (self.headers.get("Transfer-Encoding") or not length.isdecimal()
                                or len(self.headers.get_all("Content-Length", [])) != 1):
                            self.respond(400, {"error": "bounded_content_length_required"})
                            return
                        if int(length) > 65536:
                            self.respond(413, {"error": "request_too_large"})
                            return
                        payload = load_json(self.rfile.read(int(length)).decode("utf-8"))
                    result = dispatch(service, method, self.path, participant, authorization[7:], payload)
                    self.respond(200, result)
                except PermissionError:
                    self.respond(403, {"error": "forbidden"})
                except LookupError:
                    self.respond(404, {"error": "not_found"})
                except (ValueError, TypeError, ArithmeticError):
                    self.respond(400, {"error": "invalid_request"})

            def do_GET(self):  # noqa: N802
                if self.path == "/health":
                    self.respond(200, {"ok": True, "events": len(service.events.events)})
                else:
                    self.handle_api("GET")

            def do_POST(self):  # noqa: N802
                self.handle_api("POST")
            def log_message(self, *_args):
                return
        server = ThreadingHTTPServer((host, port), Handler)
        Thread(target=server.serve_forever, daemon=True).start()
        return server


__all__ = ["CoordinatorService"]
