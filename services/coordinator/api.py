"""Scoped JSON API for the trusted local coordinator; never executes submitted code."""
from nablamath.core.semantic_contracts import require_fields, require_digest, require_text
from nablamath.core.semantic_ir import SemanticExpression, rational
from .auth import authenticate

SCOPES = frozenset({"create", "read", "lease", "submit", "heartbeat", "cancel"})


def dispatch(service, method, path, participant, token, payload):
    authenticate(service.secret, participant, token)
    paths = path.strip("/").split("/")
    if path == "/tasks" and method == "POST":
        scope = "create"
    elif path == "/leases" and method == "POST":
        scope = "lease"
    elif len(paths) == 2 and paths[0] == "tasks" and method == "GET":
        scope = "read"
    elif len(paths) == 3 and paths[0] == "tasks" and paths[2] in {"submit", "heartbeat", "cancel"} and method == "POST":
        scope = paths[2]
    else:
        raise LookupError("Unknown API route")
    if scope not in service.http_permissions.get(participant, frozenset()):
        raise PermissionError("Missing capability")
    if scope == "create":
        require_fields(payload, {"expression", "values"})
        require_text(payload["expression"], "expression")
        if not isinstance(payload["values"], dict) or len(payload["values"]) > 128:
            raise ValueError("Bounded rational bindings required")
        SemanticExpression.parse(payload["expression"])
        for name, value in payload["values"].items():
            require_text(name, "symbol", limit=128)
            rational(value)
        task_id = service.scheduler.queue.add(payload["expression"], payload["values"], max_pending=service.max_pending_tasks)
        response = {"task_id": task_id}
    elif scope == "lease":
        require_fields(payload, {"seconds"})
        response = {"lease": service.scheduler.lease(participant, payload["seconds"])}
    else:
        task_id = require_digest(paths[1])
        if scope == "read":
            status = service.scheduler.status(task_id)
            if status is None:
                raise LookupError("Unknown task")
            response = {"task_id": task_id, "status": status}
        elif scope == "submit":
            require_fields(payload, {"result_id"})
            result_id = require_digest(payload["result_id"])
            response = {"status": service.scheduler.submit(participant, task_id, result_id)}
        elif scope == "heartbeat":
            require_fields(payload, {"seconds"})
            response = {"lease_expires_unix": service.scheduler.queue.heartbeat(participant, task_id, payload["seconds"])}
        else:
            require_fields(payload, set())
            response = {"status": service.scheduler.queue.cancel(task_id)}
    service.events.append("api." + scope, {"participant": participant})
    return response
