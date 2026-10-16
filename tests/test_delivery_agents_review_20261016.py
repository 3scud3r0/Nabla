"""Independent adversarial timing checks at SQLite transaction boundaries.

Advancing the injected wall clock after acquisition models time spent waiting
for SQLite's write lock. Admission must use the capability state at acquisition,
not a timestamp collected before contention began.
"""
from contextlib import contextmanager

import pytest

from nablamath.agents.dag_contracts import DagBudget
from nablamath.agents.durable_dag import DagStore, LeaseConflict
from nablamath.agents.dag_scheduler import FairDagScheduler
from nablamath.agents.experiment_planner import plan_experiment
from nablamath.agents.human_approval import ApprovalLedger
from nablamath.agents.permissions import Permissions
from nablamath.agents.tool_registry import scientific_registry
from nablamath.core.resource_profiles import ResourceProfile
from nablamath.node.consent import Consent


class Clock:
    def __init__(self):
        self.time = 1000.

    def __call__(self):
        return self.time


def make_graph(tmp_path, *, timeout=5, lease_seconds=4, calls=5):
    clock = Clock()
    permissions = Permissions(frozenset({'simulate'}), max_calls=calls)
    plan = plan_experiment(question='Time-fenced admission', owner='operator',
                           hypothesis='Only live capabilities admit work',
                           expected_observation='No expired leases admitted',
                           trials=[dict(id='task', tool='simulate', depends_on=(),
                                        arguments=dict(name='exponential_decay', initial=[1], steps=2))],
                           registry=scientific_registry(), permissions=permissions)
    ledger = ApprovalLedger()
    ledger.record(plan, 'task', reviewer='operator', decision='approve',
                  reason='Bounded pure computation', expected_head=ledger.head)
    store = DagStore(tmp_path/'timing.sqlite', clock=clock)
    budget = DagBudget(max_parallel_actions=1, run_timeout_seconds=timeout,
                       lease_seconds=lease_seconds, max_total_attempts=2)
    run_id = store.create(plan, permissions, budget, ledger)
    return store, run_id, clock, plan, permissions, budget, ledger


def simulate_lock_wait(monkeypatch, store, clock, new_time):
    original = store._transaction
    @contextmanager
    def delayed_transaction():
        with original() as db:
            clock.time = new_time
            yield db
    monkeypatch.setattr(store, '_transaction', delayed_transaction)


def test_claim_does_not_admit_after_deadline_elapsed_during_lock_wait(tmp_path, monkeypatch):
    store, run_id, clock, *_ = make_graph(tmp_path)
    simulate_lock_wait(monkeypatch, store, clock, 1010)
    lease = store.claim(run_id, 'worker', consent=Consent(contribute=True))
    assert lease is None
    snapshot = store.snapshot(run_id)
    assert snapshot['status'] == 'expired'
    assert snapshot['total_attempts'] == 0


def test_claim_rechecks_contribution_consent_after_lock_wait(tmp_path, monkeypatch):
    store, run_id, clock, *_ = make_graph(tmp_path, timeout=60)
    consent = Consent(contribute=True, expires_unix=1005)
    simulate_lock_wait(monkeypatch, store, clock, 1010)
    with pytest.raises(PermissionError):
        store.claim(run_id, 'worker', consent=consent)
    assert store.snapshot(run_id)['total_attempts'] == 0


def test_heartbeat_cannot_resurrect_expired_lease_after_lock_wait(tmp_path, monkeypatch):
    store, run_id, clock, *_ = make_graph(tmp_path, timeout=60)
    lease = store.claim(run_id, 'worker', consent=Consent(contribute=True))
    simulate_lock_wait(monkeypatch, store, clock, 1010)
    with pytest.raises(LeaseConflict):
        store.heartbeat(run_id, lease['action_id'], lease['worker'], lease['token'],
                        consent=Consent(contribute=True))
    assert store.snapshot(run_id)['tasks'][0]['expires'] <= clock.time


def test_heartbeat_rechecks_consent_after_lock_wait(tmp_path, monkeypatch):
    store, run_id, clock, *_ = make_graph(tmp_path, timeout=60, lease_seconds=30)
    lease = store.claim(run_id, 'worker', consent=Consent(contribute=True))
    simulate_lock_wait(monkeypatch, store, clock, 1010)
    with pytest.raises(PermissionError):
        store.heartbeat(run_id, lease['action_id'], lease['worker'], lease['token'],
                        consent=Consent(contribute=True, expires_unix=1005))


def test_failure_report_cannot_replace_expired_lease_outcome_after_lock_wait(tmp_path, monkeypatch):
    store, run_id, clock, *_ = make_graph(tmp_path, timeout=60)
    lease = store.claim(run_id, 'worker', consent=Consent(contribute=True))
    simulate_lock_wait(monkeypatch, store, clock, 1010)
    with pytest.raises(LeaseConflict):
        store.fail(run_id, lease['action_id'], lease['worker'], lease['token'], 'tool_error')


def enroll_scheduler(store, run_id):
    scheduler = FairDagScheduler(store)
    profile = ResourceProfile('single-worker', 1, 1024, 0, 1, 60)
    scheduler.register_pool('pool', profile, tool_limits={'simulate': 1})
    scheduler.enroll('pool', run_id)
    return scheduler


def test_fair_scheduler_uses_post_lock_deadline_and_releases_admission(tmp_path, monkeypatch):
    store, run_id, clock, *_ = make_graph(tmp_path)
    scheduler = enroll_scheduler(store, run_id)
    simulate_lock_wait(monkeypatch, store, clock, 1010)
    assert scheduler.claim_next('pool', 'worker', consent=Consent(contribute=True)) is None
    snapshot = scheduler.snapshot('pool')
    assert snapshot['usage']['active_tasks'] == 0
    assert snapshot['queue'][0]['dispatches'] == 0
    assert store.snapshot(run_id)['status'] == 'expired'


def test_fair_scheduler_rechecks_expired_consent_after_lock_wait(tmp_path, monkeypatch):
    store, run_id, clock, *_ = make_graph(tmp_path, timeout=60)
    scheduler = enroll_scheduler(store, run_id)
    simulate_lock_wait(monkeypatch, store, clock, 1010)
    with pytest.raises(PermissionError):
        scheduler.claim_next('pool', 'worker', consent=Consent(contribute=True, expires_unix=1005))
    assert scheduler.snapshot('pool')['usage']['active_tasks'] == 0


def test_creation_deadline_begins_at_actual_atomic_creation(tmp_path, monkeypatch):
    store, _, clock, plan, permissions, budget, ledger = make_graph(tmp_path)
    other = DagStore(tmp_path/'other.sqlite', clock=clock)
    simulate_lock_wait(monkeypatch, other, clock, 1010)
    run_id = other.create(plan, permissions, budget, ledger)
    snapshot = other.snapshot(run_id)
    assert snapshot['created'] == 1010
    assert snapshot['deadline'] == 1015
