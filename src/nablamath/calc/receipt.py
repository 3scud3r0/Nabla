"""Canonical receipts for integrations outside the replayable calculation catalog."""
import json

from ..core.semantic_ir import canonical_json, fingerprint

# Public spelling used by amalgamated integrations.
canonical = canonical_json

MAX_BYTES = 16 * 1024 * 1024


def receipt(operation, inputs, result, *, backend="python", metadata=None, parents=()):
    """Snapshot JSON values. An observation receipt is never a proof or a replay recipe."""
    if not isinstance(operation, str) or not operation.strip():
        raise ValueError("An operation name is required")
    if not isinstance(backend, str) or not backend.strip():
        raise ValueError("A backend name is required")
    parents = list(parents)
    if any(not isinstance(p, str) or len(p) != 64 or any(c not in '0123456789abcdef' for c in p) for p in parents):
        raise ValueError("Parents must be SHA-256 content IDs")
    body = dict(schema_version=1, kind="execution_observation", operation=operation,
                inputs=inputs, result=result, backend=backend, metadata=metadata or {},
                parents=parents, formal_proof=False, replayable=False)
    raw = canonical_json(body)
    if len(raw.encode()) > MAX_BYTES:
        raise ValueError("Receipt exceeds 16 MiB")
    return {**json.loads(raw), "content_id": fingerprint(body)}


def verify_receipt(data):
    """Verify structure and digest without executing external code."""
    try:
        if not isinstance(data, dict) or len(canonical_json(data).encode()) > MAX_BYTES:
            return False
        body = dict(data)
        identifier = body.pop("content_id")
        if body.get('kind') == 'execution_observation':
            rebuilt = receipt(body['operation'], body['inputs'], body['result'],
                              backend=body['backend'], metadata=body['metadata'], parents=body['parents'])
            return rebuilt == data
        from .session import CalculationSession
        # Catalog receipts have an executable, closed request contract.
        return (fingerprint(body) == identifier
                and CalculationSession.replay_request(body['request']).to_data() == data)
    except (ValueError, TypeError, KeyError, ArithmeticError, RecursionError):
        return False
