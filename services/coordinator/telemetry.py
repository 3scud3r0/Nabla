"""Bounded aggregate counters; never accept expressions or participant labels.

Aggregates are not differential privacy. Deployments must decide when and to whom
counts may be released. No identifiers, raw event stream, or exact timings kept.
"""
from threading import Lock
import math


class AggregateTelemetry:
    OUTCOMES = frozenset({'verified', 'awaiting_second_worker', 'cancelled', 'failed', 'idle'})

    def __init__(self):
        self._counts = {name: 0 for name in self.OUTCOMES}
        self._duration_buckets = [0, 0, 0, 0]
        self._lock = Lock()

    def record(self, outcome, *, duration_seconds=0.0):
        if outcome not in self.OUTCOMES:
            raise ValueError('Fixed outcome label required')
        if (isinstance(duration_seconds, bool) or not isinstance(duration_seconds, (int, float))
                or not math.isfinite(duration_seconds) or duration_seconds < 0):
            raise ValueError('Finite nonnegative duration required')
        bucket = 0 if duration_seconds < .1 else 1 if duration_seconds < 1 else 2 if duration_seconds < 10 else 3
        with self._lock:
            self._counts[outcome] += 1
            self._duration_buckets[bucket] += 1

    def snapshot(self):
        with self._lock:
            return dict(schema_version=1, counts=dict(self._counts),
                        duration_buckets=dict(zip(('<0.1s', '0.1–1s', '1–10s', '>=10s'), self._duration_buckets)),
                        privacy='Aggregate counts only; no differential privacy guarantee')
