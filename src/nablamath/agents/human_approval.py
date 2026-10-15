"""Explicit local review ledger, not authentication or permission to use external APIs.

The caller supplies the authenticated reviewer identity. Hashes detect accidental
changes; they are not signatures. A decision binds the whole versioned experiment
and one exact action, including dependencies and arguments.
"""
from dataclasses import dataclass
from threading import RLock
from ..core.semantic_ir import fingerprint


@dataclass(frozen=True)
class Approval:
    plan_id: str
    action_id: str
    reviewer: str
    decision: str
    reason: str
    revision: int

    def __post_init__(self):
        if self.decision not in {'approve', 'reject', 'revoke'}:
            raise ValueError('Invalid approval decision')
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError('Positive revision required')
        if any(not isinstance(v, str) or not v.strip() or len(v) > 4096
               for v in (self.plan_id, self.action_id, self.reviewer, self.reason)):
            raise ValueError('Explicit review metadata required')

    def to_data(self):
        return dict(self.__dict__)


class ApprovalLedger:
    """Append-only in-memory decisions with replay validation and CAS revisions."""
    def __init__(self):
        self._events = []
        self._lock = RLock()

    @property
    def head(self):
        with self._lock:
            return self._events[-1]['event_id'] if self._events else None

    def record(self, plan, action_id, *, reviewer, decision, reason, expected_head):
        with self._lock:
            if len(self._events) >= 10000:
                raise ValueError('Approval history limit exceeded')
            if self.head != expected_head:
                raise ValueError('Stale approval head')
            if action_id not in {a.action_id for a in plan.proposal.actions}:
                raise ValueError('Unknown action')
            approval = Approval(plan.content_id, action_id, reviewer, decision, reason, len(self._events)+1)
            event = dict(approval=approval.to_data(), previous=self.head)
            self._events.append(dict(event, event_id=fingerprint(event)))
            return self.head

    def approved(self, plan, action_id):
        with self._lock:
            for event in reversed(self._events):
                item = event['approval']
                if item['plan_id'] == plan.content_id and item['action_id'] == action_id:
                    return item['decision'] == 'approve'
            return False

    def require(self, plan):
        with self._lock:
            if any(not self.approved(plan, a.action_id) for a in plan.proposal.actions):
                raise PermissionError('Every action requires current explicit human approval')

    def to_data(self):
        with self._lock:
            import copy
            return copy.deepcopy(self._events)

    @classmethod
    def from_data(cls, events):
        ledger = cls()
        if not isinstance(events, list) or len(events) > 10000:
            raise ValueError('Invalid approval history')
        for index, event in enumerate(events, 1):
            if set(event) != {'approval', 'previous', 'event_id'}:
                raise ValueError('Invalid event fields')
            approval = Approval(**event['approval'])
            body = dict(approval=approval.to_data(), previous=ledger.head)
            if (approval.revision != index or event['previous'] != ledger.head
                    or fingerprint(body) != event['event_id']):
                raise ValueError('Approval history mismatch')
            ledger._events.append(dict(body, event_id=event['event_id']))
        return ledger


def run_approved(plan, ledger, planner, *, store=None, stop_after=None):
    """Check the complete current decision set before invoking trusted tools."""
    plan.preflight(planner.registry, planner.permissions)
    ledger.require(plan)
    return planner.run(plan.proposal, store=store, stop_after=stop_after)
