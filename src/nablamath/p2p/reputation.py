"""Bounded local antiabuse observations; never a scientific truth score."""
from collections import OrderedDict
from threading import RLock


class Reputation:
    def __init__(self, *, max_events=10000, block_threshold=3):
        if type(max_events) is not int or max_events < 1 or type(block_threshold) is not int or block_threshold < 1:
            raise ValueError('Invalid reputation limits')
        self.max_events, self.block_threshold = max_events, block_threshold
        self._events = OrderedDict()
        self._lock = RLock()

    def record(self, peer_id, event_id, *, violation, reason):
        if not all(isinstance(value, str) and value.strip() and len(value) <= 512 for value in (peer_id, event_id, reason)) or type(violation) is not bool:
            raise ValueError('Invalid abuse observation')
        event = dict(peer_id=peer_id, event_id=event_id, violation=violation, reason=reason)
        with self._lock:
            if event_id in self._events:
                if self._events[event_id] != event:
                    raise ValueError('Conflicting event identifier')
                return False
            if len(self._events) >= self.max_events:
                raise ValueError('Observation capacity exhausted; archive required')
            self._events[event_id] = event
        return True

    def report(self, peer_id):
        with self._lock:
            events = [dict(event) for event in self._events.values() if event['peer_id'] == peer_id]
        violations = sum(event['violation'] for event in events)
        return dict(peer_id=peer_id, observations=len(events), violations=violations,
                    blocked=violations >= self.block_threshold, scientific_truth_score=None)

    def audit(self):
        with self._lock:
            return tuple(dict(event) for event in self._events.values())
