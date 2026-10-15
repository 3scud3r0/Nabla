"""Bounded JSON contracts; no coercion, duplicate keys or nonfinite numbers."""
from __future__ import annotations

import json
import math

from .semantic_ir import canonical_json

MAX_BYTES = 1_000_000


def require_text(value: object, name: str, *, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{name} requires nonempty text of at most {limit} characters")
    return value


def require_digest(value: object) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("Expected lowercase SHA-256")
    return value


def require_fields(value: object, fields: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"Expected exactly these fields: {sorted(fields)}")
    return value


def validate_json(value: object) -> None:
    """Accept only JSON-native values within depth, node and encoded-size budgets."""
    remaining = 20000

    def visit(node: object, depth: int) -> None:
        nonlocal remaining
        remaining -= 1
        if depth > 32 or remaining < 0:
            raise ValueError("JSON structural budget exceeded")
        if node is None or type(node) in (bool, str):
            return
        if type(node) is int:
            if node.bit_length() > 4096:
                raise ValueError("JSON integer budget exceeded")
            return
        if type(node) is float and math.isfinite(node):
            return
        if type(node) is list:
            for child in node:
                visit(child, depth + 1)
            return
        if type(node) is dict and all(type(key) is str for key in node):
            for child in node.values():
                visit(child, depth + 1)
            return
        raise ValueError("Only finite JSON-native values are supported")

    visit(value, 0)
    if len(canonical_json(value).encode("utf-8")) > MAX_BYTES:
        raise ValueError("JSON byte budget exceeded")


def canonical_payload(value: object) -> str:
    validate_json(value)
    return canonical_json(value)


def load_json(raw: str) -> object:
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_BYTES:
        raise ValueError("JSON byte budget exceeded")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=pairs)
        validate_json(value)
        return value
    except (RecursionError, OverflowError) as error:
        raise ValueError("JSON structural budget exceeded") from error
