"""Consent-aware process worker for the durable approved scientific DAG.

Only three fixed repository-owned tools execute. Spawned subprocesses provide
killable time/transport bounds, not hostile-code filesystem/network isolation.
Memory/CPU reservations are cooperative admission, not measured OS enforcement.
The coordinator independently replays each result before committing its receipt.
"""
from dataclasses import replace
import math
from threading import RLock
import time

from nablamath.agents.dag_contracts import permissions_from_data
from nablamath.agents.durable_dag import DagStore, LeaseConflict
from nablamath.agents.tool_registry import Tool, ToolRegistry, _solve, _verify, _world
from nablamath.core.resource_profiles import ResourceProfile, ResourceReservations
from nablamath.forge.task_spec import TaskSpec
from nablamath.node.consent import ConsentStore
from nablamath.worlds.model_spec import ModelSpec


def _solve_task(task):
    TaskSpec.from_data(task)
    return _solve(task)


def _verify_task(task, candidate):
    TaskSpec.from_data(task)
    return _verify(task, candidate)


def _simulate_task(name, initial, rate=1., duration=1., steps=100):
    # References are already resolved. Validate every field again here so a
    # reference cannot bypass the static graph preflight's scientific budgets.
    ModelSpec(name, tuple(initial), rate, duration)
    if type(steps) is not int or not 2 <= steps <= 10000:
        raise ValueError('DAG worker simulation requires 2–10000 steps')
    return _world(name, initial, rate, duration, steps)


def _registry():
    return ToolRegistry((
        Tool('solve', _solve_task, frozenset({'task'})),
        Tool('verify', _verify_task, frozenset({'task', 'candidate'})),
        Tool('simulate', _simulate_task, frozenset({'name', 'initial'}),
             frozenset({'rate', 'duration', 'steps'})),
    ))


def local_worker_profile():
    return ResourceProfile('local-approved-scientific-worker', cpu_slots=1,
                           memory_bytes=268435456, gpu_memory_bytes=0,
                           max_tasks=1, max_task_seconds=60, distributed=False)


class DagWorker:
    def __init__(self, coordinator, worker_id, consent_store, *, reservations=None,
                 memory_bytes=67108864, max_actions=100, on_battery=lambda: False,
                 scheduler=None, pool_id=None):
        from nablamath.agents.dag_contracts import validate_worker
        if not isinstance(coordinator, DagStore) or not isinstance(consent_store, ConsentStore):
            raise ValueError('Durable coordinator and local ConsentStore required')
        validate_worker(worker_id)
        if type(memory_bytes) is not int or memory_bytes < 1:
            raise ValueError('Positive declared working-memory reservation required')
        if type(max_actions) is not int or not 1 <= max_actions <= 10000:
            raise ValueError('Worker action quota must be 1–10000')
        if reservations is not None and not isinstance(reservations, ResourceReservations):
            raise ValueError('Typed resource reservations required')
        if scheduler is not None:
            from nablamath.agents.dag_scheduler import FairDagScheduler
            if not isinstance(scheduler, FairDagScheduler) or scheduler.store.path != coordinator.path or not pool_id:
                raise ValueError('Fair scheduler must share this coordinator and an explicit pool')
        elif pool_id is not None:
            raise ValueError('A resource pool requires its persistent scheduler')
        self.scheduler, self.pool_id = scheduler, pool_id
        self.coordinator = coordinator
        self.worker_id = worker_id
        self.consent_store = consent_store
        self.reservations = reservations or ResourceReservations(local_worker_profile())
        self.memory_bytes = memory_bytes
        self.max_actions = max_actions
        self.on_battery = on_battery
        self.attempted = 0
        self.completed = 0
        self._lock = RLock()

    def _consent(self):
        consent = self.consent_store.load()
        battery = self.on_battery()
        if type(battery) is not bool:
            raise ValueError('Power-state provider must return a boolean')
        return consent, battery

    def _abandon(self, lease, code):
        try:
            return self.coordinator.fail(lease['run_id'], lease['action_id'], self.worker_id, lease['token'], code)
        except (LeaseConflict, PermissionError):
            # Global cancellation, lease expiry or a concurrent operator action
            # can invalidate our lease first. Never resurrect or overwrite it.
            return self.coordinator.snapshot(lease['run_id'])['status']

    def run_one(self, run_id, *, cancelled=lambda: False):
        """Lease and execute one action; return idle without polling or sleeping."""
        with self._lock:
            if cancelled():
                return dict(status='cancelled', dispatched=False)
            if self.attempted >= self.max_actions:
                raise ValueError('Local worker action quota exhausted before leasing')
            consent, battery = self._consent()
            self.coordinator._require_consent(consent, self.coordinator._now(), battery)
            if run_id is not None and not self.coordinator.verify(run_id):
                raise ValueError('Durable DAG checkpoint failed replay before worker admission')
            profile = self.reservations.profile
            # Reserve before acquiring a lease so unavailable local capacity does
            # not consume a graph attempt or hold work away from another worker.
            with self.reservations.reserve(cpu_slots=1, memory_bytes=self.memory_bytes,
                                           seconds=min(60, profile.max_task_seconds)):
                if run_id is None:
                    if self.scheduler is None:
                        raise ValueError('Fair dispatch requires a persistent scheduler')
                    lease = self.scheduler.claim_next(self.pool_id, self.worker_id, consent=consent,
                                                       on_battery=battery, memory_bytes=self.memory_bytes)
                else:
                    lease = self.coordinator.claim(run_id, self.worker_id, consent=consent, on_battery=battery,
                                                    pool_id=self.pool_id, memory_bytes=self.memory_bytes)
                if lease is None:
                    return dict(status='idle', dispatched=False,
                                run_status=self.coordinator.snapshot(run_id)['status'] if run_id else 'idle')
                run_id = lease['run_id']
                if not self.coordinator.verify(run_id):
                    self._abandon(lease, 'invalid_result')
                    raise ValueError('Selected DAG checkpoint failed replay; no tool was executed')
                self.attempted += 1
                if cancelled():
                    state = self._abandon(lease, 'worker_cancelled')
                    return dict(status='cancelled', dispatched=False, run_status=state)
                remaining = lease['expires']-self.coordinator._now()
                permissions = permissions_from_data(lease['permissions'])
                timeout = min(permissions.timeout_seconds, float(profile.max_task_seconds), remaining*.8)
                if timeout <= 0:
                    state = self._abandon(lease, 'tool_timeout')
                    return dict(status='failed', code='tool_timeout', dispatched=False, run_status=state)
                permissions = replace(permissions, timeout_seconds=timeout,
                                      max_output_bytes=min(permissions.max_output_bytes,
                                                           lease['budget']['max_result_bytes']))
                started = time.monotonic()
                try:
                    result = _registry().execute(lease['tool'], lease['arguments'], permissions)
                except TimeoutError:
                    state = self._abandon(lease, 'tool_timeout')
                    return dict(status='failed', code='tool_timeout', dispatched=True, run_status=state)
                except (ValueError, TypeError, ArithmeticError, OSError, PermissionError):
                    state = self._abandon(lease, 'tool_error')
                    return dict(status='failed', code='tool_error', dispatched=True, run_status=state)
                if cancelled():
                    state = self._abandon(lease, 'worker_cancelled')
                    return dict(status='cancelled', dispatched=True, run_status=state)
                consent, battery = self._consent()
                try:
                    self.coordinator._require_consent(consent, self.coordinator._now(), battery)
                except PermissionError:
                    state = self._abandon(lease, 'consent_revoked')
                    return dict(status='denied', code='consent_revoked', dispatched=True, run_status=state)
                try:
                    receipt = self.coordinator.complete(run_id, lease['action_id'], self.worker_id,
                                                        lease['token'], result, consent=consent, on_battery=battery)
                except PermissionError:
                    state = self._abandon(lease, 'consent_revoked')
                    return dict(status='denied', code='approval_revoked', dispatched=True, run_status=state)
                except LeaseConflict:
                    return dict(status='discarded', code='stale_lease', dispatched=True,
                                run_status=self.coordinator.snapshot(run_id)['status'])
                except ValueError:
                    state = self._abandon(lease, 'invalid_result')
                    return dict(status='failed', code='invalid_result', dispatched=True, run_status=state)
                self.completed += 1
                return dict(status='completed', dispatched=True, action_id=lease['action_id'],
                            receipt_id=receipt['receipt_id'], elapsed_seconds=time.monotonic()-started,
                            run_status=self.coordinator.snapshot(run_id)['status'])

    def run_next(self, *, cancelled=lambda: False):
        """Execute the next fairly selected pooled action across enrolled runs."""
        return self.run_one(None, cancelled=cancelled)

    def drain(self, run_id, *, limit=100, cancelled=lambda: False):
        """Run a finite local batch; deferred retries return idle for a later call."""
        if type(limit) is not int or not 1 <= limit <= 10000:
            raise ValueError('Bounded drain limit required')
        outcomes = []
        for _ in range(limit):
            outcome = self.run_one(run_id, cancelled=cancelled)
            outcomes.append(outcome)
            if outcome['status'] in {'idle', 'cancelled', 'denied', 'discarded'}:
                break
            if outcome.get('run_status') in {'completed', 'failed', 'cancelled', 'expired'}:
                break
        return dict(outcomes=outcomes, completed=sum(o['status'] == 'completed' for o in outcomes),
                    attempted=self.attempted, run_status=self.coordinator.snapshot(run_id)['status'])
