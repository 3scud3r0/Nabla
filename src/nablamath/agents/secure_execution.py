"""Human-gated sessions for a fixed scientific tool registry.

Only repository-owned scientific tools run. Their subprocesses have wall-time
and transport limits but are not an OS sandbox. Session snapshots are diagnostic
records, not authenticated authority to resume work. Each advance rechecks live
approvals; revocation applies before the next action, not retroactively to a
running trusted tool.
"""
import copy
from dataclasses import replace
from threading import RLock
import time

from ..core.semantic_ir import fingerprint
from ..forge.task_spec import TaskSpec
from ..worlds.model_spec import ModelSpec
from .experiment_planner import ExperimentPlan
from .human_approval import ApprovalLedger
from .planner import Planner, verify_run
from .tool_registry import scientific_registry


class SessionCancelled(RuntimeError):
    pass


def deny_untrusted_code(source):
    raise PermissionError('Generated code is never executed by a scientific session')


def preflight_actions(plan, permissions):
    """Validate every static scientific payload before the first tool invocation."""
    from .bindings import references
    registry = scientific_registry()
    plan.preflight(registry, permissions)
    for action in plan.proposal.actions:
        if references(action.arguments):
            # Bound references already have a typed data grammar; runtime resolved
            # payloads are checked again by the trusted function in the subprocess.
            continue
        arguments = action.arguments
        if action.tool in {'solve', 'verify'}:
            TaskSpec.from_data(arguments['task'])
        elif action.tool == 'simulate':
            ModelSpec(arguments['name'], tuple(arguments['initial']),
                      arguments.get('rate', 1.), arguments.get('duration', 1.))
            steps = arguments.get('steps', 100)
            if type(steps) is not int or not 2 <= steps <= 10000:
                raise ValueError('Invalid simulation step budget')
    return registry


class _MemoryCheckpoint:
    """Private detached CAS checkpoint. No caller-controlled resume import."""
    def __init__(self):
        self._report = None

    def load(self, proposal_id):
        if self._report is None:
            return None
        if self._report['proposal_id'] != proposal_id or not verify_run(self._report):
            raise ValueError('Session checkpoint failed scientific replay')
        return copy.deepcopy(self._report)

    def save(self, report, *, expected_head):
        head = self._report['final_receipt'] if self._report else None
        if head != expected_head or not verify_run(report):
            raise ValueError('Session checkpoint CAS or replay mismatch')
        self._report = copy.deepcopy(report)


class SecureSession:
    """One serialized run with a total deadline and no automatic failed retries."""
    def __init__(self, plan, ledger, permissions):
        if not isinstance(plan, ExperimentPlan) or not isinstance(ledger, ApprovalLedger):
            raise ValueError('Typed experiment and approval ledger required')
        self._plan = plan
        self._ledger = ledger
        self._permissions = permissions
        self._registry = preflight_actions(plan, permissions)
        self._checkpoint = _MemoryCheckpoint()
        self._lock = RLock()
        self._started = time.monotonic()
        self._status = 'ready'
        self._attempts = 0
        self._cancel_reason = None
        self._events = []
        self._record('created')

    def _record(self, kind):
        event = dict(kind=kind, index=len(self._events), status=self._status,
                     attempts=self._attempts, plan_id=self._plan.content_id,
                     previous=self._events[-1]['event_id'] if self._events else None)
        self._events.append(dict(event, event_id=fingerprint(event)))

    @property
    def status(self):
        with self._lock:
            return self._status

    def cancel(self, reason):
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1024:
            raise ValueError('Explicit bounded cancellation reason required')
        with self._lock:
            if self._status == 'cancelled':
                return
            if self._status in {'completed', 'failed', 'expired'}:
                raise ValueError('Terminal scientific session cannot be cancelled')
            self._cancel_reason = reason
            self._status = 'cancelled'
            self._record('cancelled')

    def advance(self):
        """Execute at most one action after checking current approval and budget."""
        with self._lock:
            if self._status == 'cancelled':
                raise SessionCancelled(self._cancel_reason)
            if self._status in {'completed', 'failed', 'expired'}:
                raise ValueError('Terminal session; a new reviewed plan is required')
            remaining = self._permissions.timeout_seconds-(time.monotonic()-self._started)
            if remaining <= 0:
                self._status = 'expired'
                self._record('deadline')
                raise TimeoutError('Whole-session deadline expired')
            if self._attempts >= self._permissions.max_calls:
                self._status = 'failed'
                self._record('budget')
                raise ValueError('Whole-session action budget exhausted')
            self._ledger.require(self._plan)
            self._attempts += 1
            self._status = 'running'
            self._record('started_action')
            planner = Planner(self._registry, replace(self._permissions, timeout_seconds=remaining))
            try:
                report = planner.run(self._plan.proposal, store=self._checkpoint, stop_after=1)
            except Exception:
                self._status = 'failed'
                self._record('execution_error')
                raise
            if time.monotonic()-self._started >= self._permissions.timeout_seconds:
                self._status = 'expired'
                self._record('deadline')
                raise TimeoutError('Whole-session deadline expired before accepting checkpoint')
            self._status = 'completed' if report['completed'] else 'paused'
            if any(r['status'] != 'completed' for r in report['receipts']):
                self._status = 'failed'
            self._record('checkpoint')
            return copy.deepcopy(report)

    def snapshot(self):
        with self._lock:
            data = dict(schema_version=1, plan_id=self._plan.content_id,
                        status=self._status, attempts=self._attempts,
                        proposal_id=self._plan.proposal.content_id,
                        report=copy.deepcopy(self._checkpoint._report),
                        events=copy.deepcopy(self._events),
                        limitations='Trusted tools only; no arbitrary code or authenticated resume import')
            return dict(data, snapshot_id=fingerprint(data))


def verify_session_snapshot(snapshot):
    """Check diagnostic integrity; this never grants execution authority."""
    try:
        data = {k: v for k, v in snapshot.items() if k != 'snapshot_id'}
        if fingerprint(data) != snapshot['snapshot_id']:
            return False
        if (data.get('schema_version') != 1
                or data.get('status') not in {'ready', 'running', 'paused', 'completed', 'failed', 'expired', 'cancelled'}
                or type(data.get('attempts')) is not int or not 0 <= data['attempts'] <= 100
                or not isinstance(data.get('events'), list) or not 1 <= len(data['events']) <= 305):
            return False
        previous = None
        attempts = 0
        for index, event in enumerate(data['events']):
            body = {k: v for k, v in event.items() if k != 'event_id'}
            if (event['index'] != index or event['previous'] != previous
                    or event['plan_id'] != data['plan_id'] or fingerprint(body) != event['event_id']):
                return False
            if event['kind'] == 'started_action':
                attempts += 1
            if event['attempts'] != attempts:
                return False
            previous = event['event_id']
        if data['events'][-1]['status'] != data['status'] or attempts != data['attempts']:
            return False
        report = data['report']
        return bool(data['events']) and (report is None or (verify_run(report) and report['proposal_id'] == data['proposal_id']))
    except (ValueError, TypeError, KeyError):
        return False
