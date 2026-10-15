"""Log append-only encadeado por hash; não é uma blockchain nem consenso distribuído."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
from threading import RLock


@dataclass(frozen=True)
class Event:
    kind: str
    payload: dict
    previous_hash: str = ""
    created_at: str = ""
    event_hash: str = ""


class EventLog:
    def __init__(self):
        self.events: list[Event] = []
        self._lock = RLock()

    def append(self, kind: str, payload: dict) -> Event:
        with self._lock:
            return self._append(kind, json.loads(json.dumps(payload, allow_nan=False)))

    def _append(self, kind, payload):
        now = datetime.now(timezone.utc).isoformat()
        previous = self.events[-1].event_hash if self.events else "0" * 64
        body = {"kind": kind, "payload": payload, "previous_hash": previous, "created_at": now}
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        event = Event(kind, payload, previous, now, digest)
        self.events.append(event)
        return event

    def verify(self) -> bool:
        with self._lock:
            return self._verify()

    def _verify(self):
        previous = "0" * 64
        for event in self.events:
            if event.previous_hash != previous:
                return False
            body = {"kind": event.kind, "payload": event.payload,
                    "previous_hash": previous, "created_at": event.created_at}
            expected = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            if expected != event.event_hash:
                return False
            previous = expected
        return True

    def to_data(self) -> list[dict]:
        with self._lock:
            return [asdict(event) for event in self.events]
