"""Explicit forward-only semantic migrations, never implicit reinterpretation."""
from __future__ import annotations

from collections.abc import Callable

from .semantic_contracts import canonical_payload, load_json


class MigrationRegistry:
    def __init__(self):
        self._steps: dict[int, Callable[[dict], dict]] = {}

    def register(self, source: int, migration: Callable[[dict], dict]) -> None:
        if type(source) is not int or source < 1 or not callable(migration):
            raise ValueError("Expected positive source version and migration function")
        if source in self._steps:
            raise ValueError("Migration already registered")
        self._steps[source] = migration

    def migrate(self, data: dict, target: int) -> dict:
        if not isinstance(data, dict) or type(data.get("schema_version")) is not int:
            raise ValueError("Explicit integer schema version required")
        source = data["schema_version"]
        if type(target) is not int or not 1 <= source <= target or target - source > 32:
            raise ValueError("Unsupported migration direction or budget")
        # Detect missing steps before any user-supplied migration is executed.
        if any(version not in self._steps for version in range(source, target)):
            raise ValueError("Missing migration step")
        result = load_json(canonical_payload(data))
        for version in range(source, target):
            result = self._steps[version](result)
            if (not isinstance(result, dict) or type(result.get("schema_version")) is not int
                    or result["schema_version"] != version + 1):
                raise ValueError("Migration must explicitly produce the next version")
            result = load_json(canonical_payload(result))
        return result
