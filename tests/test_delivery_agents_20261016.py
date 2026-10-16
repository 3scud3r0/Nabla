"""Durable DAG integration, concurrency, revocation and recovery regressions."""
from dataclasses import replace
import copy
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
from threading import Barrier

import pytest

from nablamath.agents.dag_contracts import DagBudget
from nablamath.agents.dag_replay import verify_dag_snapshot
from nablamath.agents.durable_dag import DagStore, LeaseConflict
from nablamath.agents.experiment_planner import plan_experiment
from nablamath.agents.human_approval import ApprovalLedger
from nablamath.agents.permissions import Permissions
from nablamath.agents.tool_registry import scientific_registry
from nablamath.core.resource_profiles import ResourceProfile, ResourceReservations
from nablamath.core.semantic_ir import fingerprint
from nablamath.node.consent import Consent, ConsentStore
from services.worker.dag_executor import DagWorker


class Clock:
    def __init__(self):
        self.value = 1000.
    def __call__(self):
        return self.value
    def advance(self, seconds):
        self.value += seconds


def simulation(action_id, depends_on=(), initial=None):
    return dict(id=action_id, tool='simulate', depends_on=depends_on,
                arguments=dict(name='exponential_decay', initial=[1] if initial is None else initial, steps=2))


def graph(tmp_path, trials=None, *, budget=None, clock=None):
    trials = trials or [simulation('first'), simulation('second', ('first',))]
    permissions = Permissions(frozenset({'simulate', 'solve', 'verify'}), max_calls=20, timeout_seconds=10)
    plan = plan_experiment(question='Replay finite scientific graph', owner='author', hypothesis='Finite decay',
                          expected_observation='Independent exact replay and bounded trajectories', trials=trials,
                          registry=scientific_registry(), permissions=permissions)
    ledger = ApprovalLedger()
    for action in plan.proposal.actions:
        ledger.record(plan, action.action_id, reviewer='human', decision='approve', reason='Reviewed scientific action', expected_head=ledger.head)
    clock = clock or Clock()
    store = DagStore(tmp_path/'dag.sqlite', clock=clock)
    budget = budget or DagBudget(max_parallel_actions=2, lease_seconds=20)
    run_id = store.create(plan, permissions, budget, ledger)
    return store, run_id, plan, ledger, permissions, clock


def contribution_store(tmp_path):
    consent = ConsentStore(tmp_path/'consent.json')
    consent.save(Consent(contribute=True))
    return consent


def complete_lease(store, lease):
    result = scientific_registry().execute(lease['tool'], lease['arguments'],
                                          Permissions(frozenset({lease['tool']}), timeout_seconds=10))
    return store.complete(lease['run_id'], lease['action_id'], lease['worker'], lease['token'],
                          result, consent=Consent(contribute=True))


def test_process_worker_completes_dependency_graph_and_reopens(tmp_path):
    store, run_id, plan, ledger, permissions, clock = graph(tmp_path)
    worker = DagWorker(store, 'worker-one', contribution_store(tmp_path))
    first = worker.run_one(run_id)
    assert first['status'] == 'completed' and first['run_status'] == 'ready'
    reopened = DagStore(store.path, clock=clock)
    worker2 = DagWorker(reopened, 'worker-two', contribution_store(tmp_path))
    second = worker2.run_one(run_id)
    assert second['status'] == 'completed' and second['run_status'] == 'completed'
    assert reopened.verify(run_id)
    snapshot = reopened.snapshot(run_id)
    assert snapshot['total_attempts'] == 2
    assert [row['status'] for row in snapshot['tasks']] == ['completed', 'completed']
    assert 'token' not in json.dumps(snapshot)
    assert store.create(plan, permissions, DagBudget(max_parallel_actions=2, lease_seconds=20), ledger) == run_id
    assert store.snapshot(run_id)['total_attempts'] == 2


def test_result_reference_uses_committed_output(tmp_path):
    initial = {'$result': {'action': 'first', 'path': ['trajectory', 0, 1]}}
    store, run_id, *_ = graph(tmp_path, [simulation('first'), simulation('second', ('first',), initial)])
    worker = DagWorker(store, 'worker', contribution_store(tmp_path))
    result = worker.drain(run_id)
    assert result['run_status'] == 'completed', result
    assert store.verify(run_id)
    receipt = store.snapshot(run_id)['tasks'][1]['receipt']
    assert receipt['arguments']['initial'] == [1.0]


def test_atomic_claim_only_one_owner_per_task(tmp_path):
    store, run_id, _, _, _, clock = graph(tmp_path, [simulation('one')])
    barrier = Barrier(8)
    def claim(index):
        local = DagStore(store.path, clock=clock)
        barrier.wait()
        return local.claim(run_id, f'worker-{index}', consent=Consent(contribute=True))
    with ThreadPoolExecutor(max_workers=8) as pool:
        leases = list(pool.map(claim, range(8)))
    winners = [lease for lease in leases if lease]
    assert len(winners) == 1
    assert store.snapshot(run_id)['total_attempts'] == 1
    assert store.verify(run_id)


def test_parallel_limit_and_dependencies(tmp_path):
    trials = [simulation('one'), simulation('two'), simulation('three', ('one', 'two'))]
    store, run_id, *_ = graph(tmp_path, trials, budget=DagBudget(max_parallel_actions=1))
    first = store.claim(run_id, 'first', consent=Consent(contribute=True))
    assert first['action_id'] == 'one'
    assert store.claim(run_id, 'second', consent=Consent(contribute=True)) is None
    complete_lease(store, first)
    second = store.claim(run_id, 'second', consent=Consent(contribute=True))
    assert second['action_id'] == 'two'
    complete_lease(store, second)
    third = store.claim(run_id, 'third', consent=Consent(contribute=True))
    assert third['action_id'] == 'three'


def test_wrong_worker_token_and_expired_fencing(tmp_path):
    store, run_id, _, _, _, clock = graph(tmp_path, [simulation('one')])
    lease = store.claim(run_id, 'alice', consent=Consent(contribute=True))
    for worker, token in (('bob', lease['token']), ('alice', '0'*64)):
        with pytest.raises(LeaseConflict):
            store.heartbeat(run_id, 'one', worker, token, consent=Consent(contribute=True))
    clock.advance(21)
    replacement = store.claim(run_id, 'bob', consent=Consent(contribute=True))
    assert replacement['attempt'] == 2
    assert replacement['token'] != lease['token']
    with pytest.raises(LeaseConflict):
        complete_lease(store, lease)
    complete_lease(store, replacement)
    assert store.verify(run_id)


def test_heartbeat_is_durable_and_capped_by_run_deadline(tmp_path):
    budget = DagBudget(max_parallel_actions=1, lease_seconds=20, run_timeout_seconds=25)
    store, run_id, _, _, _, clock = graph(tmp_path, [simulation('one')], budget=budget)
    lease = store.claim(run_id, 'worker', consent=Consent(contribute=True))
    clock.advance(10)
    expiry = store.heartbeat(run_id, 'one', 'worker', lease['token'], consent=Consent(contribute=True))
    assert expiry == 1025
    reopened = DagStore(store.path, clock=clock)
    assert reopened.snapshot(run_id)['tasks'][0]['expires'] == expiry
    assert reopened.verify(run_id)


def test_lease_expiry_retries_then_blocks_transitive_descendants(tmp_path):
    trials = [simulation('one'), simulation('two', ('one',)), simulation('three', ('two',))]
    store, run_id, _, _, _, clock = graph(tmp_path, trials,
        budget=DagBudget(max_parallel_actions=1, lease_seconds=1, max_attempts_per_action=2))
    store.claim(run_id, 'crashed-one', consent=Consent(contribute=True))
    clock.advance(2)
    store.claim(run_id, 'crashed-two', consent=Consent(contribute=True))
    clock.advance(2)
    assert store.maintain(run_id) == 'failed'
    assert [row['status'] for row in store.snapshot(run_id)['tasks']] == ['failed', 'blocked', 'blocked']
    assert store.verify(run_id)


def test_retry_delay_and_total_attempt_limit(tmp_path):
    store, run_id, _, _, _, clock = graph(tmp_path, [simulation('one')],
        budget=DagBudget(max_parallel_actions=1, max_total_attempts=2, retry_delay_seconds=5))
    lease = store.claim(run_id, 'worker', consent=Consent(contribute=True))
    store.fail(run_id, 'one', 'worker', lease['token'], 'tool_timeout')
    assert store.claim(run_id, 'other', consent=Consent(contribute=True)) is None
    clock.advance(5)
    second = store.claim(run_id, 'other', consent=Consent(contribute=True))
    assert second['attempt'] == 2
    store.fail(run_id, 'one', 'other', second['token'], 'tool_error')
    assert store.snapshot(run_id)['status'] == 'failed'
    assert store.verify(run_id)


def test_explicit_failure_code_and_terminal_cancel(tmp_path):
    store, run_id, *_ = graph(tmp_path)
    lease = store.claim(run_id, 'worker', consent=Consent(contribute=True))
    with pytest.raises(ValueError):
        store.fail(run_id, 'first', 'worker', lease['token'], 'arbitrary secret-bearing message')
    assert store.cancel(run_id, reason='Human stopped experiment') == 'cancelled'
    assert store.cancel(run_id, reason='Idempotent stop') == 'cancelled'
    with pytest.raises(LeaseConflict):
        complete_lease(store, lease)
    assert store.claim(run_id, 'other', consent=Consent(contribute=True)) is None
    assert store.verify(run_id)


def test_action_cancel_blocks_only_its_descendants(tmp_path):
    trials = [simulation('one'), simulation('two', ('one',)), simulation('independent')]
    store, run_id, *_ = graph(tmp_path, trials)
    store.cancel(run_id, reason='Cancel branch', action_id='one')
    snapshot = store.snapshot(run_id)
    assert [row['status'] for row in snapshot['tasks']] == ['cancelled', 'blocked', 'queued']
    lease = store.claim(run_id, 'worker', consent=Consent(contribute=True))
    assert lease['action_id'] == 'independent'
    complete_lease(store, lease)
    assert store.snapshot(run_id)['status'] == 'failed'
    assert store.verify(run_id)


def test_approval_revocation_pause_reapproval_and_prefix_cas(tmp_path):
    store, run_id, plan, ledger, _, _ = graph(tmp_path)
    lease = store.claim(run_id, 'worker', consent=Consent(contribute=True))
    old_head = ledger.head
    ledger.record(plan, 'second', reviewer='human', decision='revoke', reason='Review required', expected_head=ledger.head)
    assert store.update_approvals(run_id, ledger, expected_head=old_head) == 'paused'
    with pytest.raises((PermissionError, LeaseConflict)):
        complete_lease(store, lease)
    assert store.claim(run_id, 'other', consent=Consent(contribute=True)) is None
    with pytest.raises(ValueError, match='Stale'):
        store.update_approvals(run_id, ledger, expected_head=old_head)
    old_head = ledger.head
    ledger.record(plan, 'second', reviewer='human', decision='approve', reason='Reviewed revision', expected_head=ledger.head)
    assert store.update_approvals(run_id, ledger, expected_head=old_head) == 'running'
    complete_lease(store, lease)
    assert store.verify(run_id)


def test_approval_history_replacement_is_refused(tmp_path):
    store, run_id, plan, ledger, _, _ = graph(tmp_path)
    other = ApprovalLedger()
    for action in plan.proposal.actions:
        other.record(plan, action.action_id, reviewer='other', decision='approve', reason='Different history', expected_head=other.head)
    with pytest.raises(ValueError, match='replacement'):
        store.update_approvals(run_id, other, expected_head=ledger.head)


@pytest.mark.parametrize('consent,battery', [
    (Consent(), False), (Consent(contribute=True, expires_unix=1000), False),
    (Consent(contribute=True), True), (Consent(contribute='yes'), False),
])
def test_claim_requires_active_typed_consent(tmp_path, consent, battery):
    store, run_id, *_ = graph(tmp_path)
    with pytest.raises((PermissionError, ValueError)):
        store.claim(run_id, 'worker', consent=consent, on_battery=battery)
    assert store.snapshot(run_id)['total_attempts'] == 0


def test_missing_node_consent_dispatches_nothing(tmp_path):
    store, run_id, *_ = graph(tmp_path)
    worker = DagWorker(store, 'worker', ConsentStore(tmp_path/'missing-consent'))
    with pytest.raises(PermissionError):
        worker.run_one(run_id)
    assert worker.attempted == 0
    assert store.snapshot(run_id)['total_attempts'] == 0


def test_worker_resource_admission_precedes_lease(tmp_path):
    store, run_id, *_ = graph(tmp_path)
    reservations = ResourceReservations(ResourceProfile('tiny', 1, 10, 0, 1, 10))
    worker = DagWorker(store, 'worker', contribution_store(tmp_path), reservations=reservations, memory_bytes=11)
    with pytest.raises(ValueError, match='reservation'):
        worker.run_one(run_id)
    assert store.snapshot(run_id)['total_attempts'] == 0
    assert reservations.used == (0, 0, 0, 0)


def test_worker_quota_checked_before_leasing(tmp_path):
    store, run_id, *_ = graph(tmp_path)
    worker = DagWorker(store, 'worker', contribution_store(tmp_path), max_actions=1)
    assert worker.run_one(run_id)['status'] == 'completed'
    with pytest.raises(ValueError, match='quota'):
        worker.run_one(run_id)
    assert store.snapshot(run_id)['total_attempts'] == 1


def test_global_deadline_fences_running_task(tmp_path):
    store, run_id, _, _, _, clock = graph(tmp_path, budget=DagBudget(max_parallel_actions=1, run_timeout_seconds=2))
    lease = store.claim(run_id, 'worker', consent=Consent(contribute=True))
    clock.advance(3)
    assert store.maintain(run_id) == 'expired'
    with pytest.raises(LeaseConflict):
        complete_lease(store, lease)
    assert store.verify(run_id)


def test_idempotent_completion_has_one_receipt_and_event(tmp_path):
    store, run_id, *_ = graph(tmp_path, [simulation('one')])
    lease = store.claim(run_id, 'worker', consent=Consent(contribute=True))
    first = complete_lease(store, lease)
    second = complete_lease(store, lease)
    assert first == second
    events = store.snapshot(run_id)['events']
    assert sum(e['kind'] == 'completed' for e in events) == 1
    assert store.snapshot(run_id)['total_attempts'] == 1


def test_forged_worker_result_is_not_committed(tmp_path):
    store, run_id, *_ = graph(tmp_path, [simulation('one')])
    lease = store.claim(run_id, 'worker', consent=Consent(contribute=True))
    with pytest.raises(ValueError, match='replay'):
        store.complete(run_id, 'one', 'worker', lease['token'], {'fake': True}, consent=Consent(contribute=True))
    assert store.snapshot(run_id)['tasks'][0]['status'] == 'leased'


def test_snapshot_hash_chain_and_database_corruption_are_detected(tmp_path):
    store, run_id, *_ = graph(tmp_path)
    worker = DagWorker(store, 'worker', contribution_store(tmp_path))
    worker.run_one(run_id)
    snapshot = store.snapshot(run_id)
    assert verify_dag_snapshot(snapshot)
    changed = copy.deepcopy(snapshot)
    changed['tasks'][0]['result'] = {'fake': True}
    changed['snapshot_id'] = fingerprint({k:v for k,v in changed.items() if k != 'snapshot_id'})
    assert not verify_dag_snapshot(changed)
    with sqlite3.connect(store.path) as db:
        db.execute('UPDATE dag_tasks SET result_json=? WHERE run_id=? AND action_id=?', ('{"fake":true}', run_id, 'first'))
    assert not store.verify(run_id)
    with pytest.raises(ValueError):
        store.claim(run_id, 'other', consent=Consent(contribute=True))


def test_unknown_run_and_action_do_not_mutate_database(tmp_path):
    store, run_id, *_ = graph(tmp_path)
    with pytest.raises(LookupError):
        store.snapshot('0'*64)
    with pytest.raises(LookupError):
        store.cancel(run_id, reason='Unknown action', action_id='unknown')
    assert store.snapshot(run_id)['revision'] == 1


def pooled_scheduler(store, *, cpu=2, memory=100, tasks=2, tools=None):
    from nablamath.agents.dag_scheduler import FairDagScheduler
    scheduler = FairDagScheduler(store)
    profile = ResourceProfile('persistent-pool', cpu, memory, 0, tasks, 60)
    scheduler.register_pool('science', profile, tool_limits=tools or {'simulate': 2})
    return scheduler, profile


def test_persistent_cpu_memory_and_tool_reservations_share_task_lease(tmp_path):
    store, run_id, *_ = graph(tmp_path, [simulation('one'), simulation('two'), simulation('three')])
    scheduler, _ = pooled_scheduler(store, cpu=2, memory=10, tasks=2)
    scheduler.enroll('science', run_id)
    first = scheduler.claim_next('science', 'one', consent=Consent(contribute=True), memory_bytes=6)
    assert first is not None
    assert scheduler.claim_next('science', 'two', consent=Consent(contribute=True), memory_bytes=6) is None
    usage = scheduler.snapshot('science')['usage']
    assert (usage['cpu_slots'], usage['memory_bytes'], usage['active_tasks']) == (1, 6, 1)
    complete_lease(store, first)
    assert scheduler.snapshot('science')['usage']['active_tasks'] == 0
    second = scheduler.claim_next('science', 'two', consent=Consent(contribute=True), memory_bytes=10)
    assert second['action_id'] == 'two'
    assert scheduler.snapshot('science')['usage']['memory_bytes'] == 10
    assert scheduler.verify('science')
    assert store.verify(run_id)


def test_persistent_tool_limit_blocks_even_when_cpu_memory_available(tmp_path):
    store, run_id, *_ = graph(tmp_path, [simulation('one'), simulation('two')])
    scheduler, _ = pooled_scheduler(store, cpu=10, memory=100, tasks=10, tools={'simulate': 1})
    scheduler.enroll('science', run_id)
    first = scheduler.claim_next('science', 'one', consent=Consent(contribute=True))
    assert scheduler.claim_next('science', 'two', consent=Consent(contribute=True)) is None
    complete_lease(store, first)
    assert scheduler.claim_next('science', 'two', consent=Consent(contribute=True)) is not None
    assert scheduler.verify('science')


def test_expiry_recovery_releases_persistent_reservations(tmp_path):
    store, run_id, _, _, _, clock = graph(tmp_path, [simulation('one'), simulation('two')],
        budget=DagBudget(max_parallel_actions=2, lease_seconds=1))
    scheduler, _ = pooled_scheduler(store, cpu=1, memory=1, tasks=1)
    scheduler.enroll('science', run_id)
    lease = scheduler.claim_next('science', 'crashed', consent=Consent(contribute=True))
    assert scheduler.snapshot('science')['usage']['active_tasks'] == 1
    clock.advance(2)
    from nablamath.agents.dag_scheduler import FairDagScheduler
    reopened = FairDagScheduler(DagStore(store.path, clock=clock))
    recovered = reopened.recover('science')
    assert recovered['usage']['active_tasks'] == 0
    replacement = reopened.claim_next('science', 'replacement', consent=Consent(contribute=True))
    assert replacement['attempt'] == 2
    with pytest.raises(LeaseConflict):
        complete_lease(store, lease)
    complete_lease(store, replacement)
    assert reopened.verify('science')


def test_cancel_and_failure_release_capacity_without_double_release(tmp_path):
    store, first_id, *_ = graph(tmp_path, [simulation('first')])
    _, second_id, *_ = graph(tmp_path, [simulation('second')])
    scheduler, _ = pooled_scheduler(store, cpu=1, memory=1, tasks=1)
    scheduler.enroll('science', first_id)
    scheduler.enroll('science', second_id)
    lease = scheduler.claim_next('science', 'one', consent=Consent(contribute=True))
    assert lease['run_id'] == first_id
    store.cancel(first_id, reason='Stop occupied experiment')
    assert scheduler.snapshot('science')['usage']['active_tasks'] == 0
    second = scheduler.claim_next('science', 'two', consent=Consent(contribute=True))
    assert second['run_id'] == second_id
    with pytest.raises(LeaseConflict):
        store.fail(first_id, 'first', 'one', lease['token'], 'tool_error')
    assert scheduler.snapshot('science')['usage']['active_tasks'] == 1
    store.fail(second_id, 'second', 'two', second['token'], 'tool_error')
    assert scheduler.snapshot('science')['usage']['active_tasks'] == 0
    assert scheduler.verify('science')


def test_concurrent_schedulers_cannot_overreserve_pool(tmp_path):
    store, run_id, _, _, _, clock = graph(tmp_path, [simulation(f'task{i}') for i in range(8)],
                                          budget=DagBudget(max_parallel_actions=8))
    scheduler, _ = pooled_scheduler(store, cpu=2, memory=2, tasks=2)
    scheduler.enroll('science', run_id)
    barrier = Barrier(8)
    def claim(index):
        from nablamath.agents.dag_scheduler import FairDagScheduler
        local = FairDagScheduler(DagStore(store.path, clock=clock))
        barrier.wait()
        return local.claim_next('science', f'worker{index}', consent=Consent(contribute=True))
    with ThreadPoolExecutor(max_workers=8) as pool:
        leases = list(pool.map(claim, range(8)))
    assert sum(lease is not None for lease in leases) == 2
    assert scheduler.snapshot('science')['usage']['active_tasks'] == 2
    assert store.snapshot(run_id)['total_attempts'] == 2
    assert scheduler.verify('science')


def test_weighted_fair_dispatch_persists_across_scheduler_restart(tmp_path):
    store, fast_id, _, _, _, clock = graph(tmp_path, [simulation(f'fast{i}') for i in range(8)])
    _, slow_id, *_ = graph(tmp_path, [simulation(f'slow{i}') for i in range(8)])
    scheduler, _ = pooled_scheduler(store, cpu=1, memory=1, tasks=1)
    scheduler.enroll('science', fast_id, weight=2)
    scheduler.enroll('science', slow_id, weight=1)
    chosen = []
    for index in range(6):
        if index == 3:
            from nablamath.agents.dag_scheduler import FairDagScheduler
            scheduler = FairDagScheduler(DagStore(store.path, clock=clock))
        lease = scheduler.claim_next('science', f'worker{index}', consent=Consent(contribute=True))
        chosen.append(lease['run_id'])
        complete_lease(store, lease)
    assert chosen.count(fast_id) == 4
    assert chosen.count(slow_id) == 2
    queue = {row['run_id']: row for row in scheduler.snapshot('science')['queue']}
    assert queue[fast_id]['dispatches'] == 4 and queue[slow_id]['dispatches'] == 2
    assert scheduler.verify('science')


def test_suspension_preserves_fairness_debt_and_existing_leases(tmp_path):
    store, run_id, *_ = graph(tmp_path, [simulation('one'), simulation('two')])
    scheduler, _ = pooled_scheduler(store)
    scheduler.enroll('science', run_id)
    lease = scheduler.claim_next('science', 'worker', consent=Consent(contribute=True))
    before = scheduler.snapshot('science')['queue'][0]['virtual_finish']
    scheduler.suspend('science', run_id)
    assert scheduler.claim_next('science', 'other', consent=Consent(contribute=True)) is None
    complete_lease(store, lease)
    scheduler.enroll('science', run_id)
    assert scheduler.snapshot('science')['queue'][0]['virtual_finish'] == before
    assert scheduler.claim_next('science', 'other', consent=Consent(contribute=True))['action_id'] == 'two'


def test_pool_resize_requires_cas_and_preserves_active_reservations(tmp_path):
    store, run_id, *_ = graph(tmp_path, [simulation('one')])
    scheduler, profile = pooled_scheduler(store, cpu=2, memory=10)
    scheduler.enroll('science', run_id)
    lease = scheduler.claim_next('science', 'worker', consent=Consent(contribute=True), memory_bytes=8)
    original = scheduler.snapshot('science')['configuration_id']
    with pytest.raises(ValueError, match='Stale'):
        scheduler.resize_pool('science', profile, tool_limits={'simulate': 2}, expected_configuration_id='0'*64)
    with pytest.raises(ValueError, match='strand'):
        scheduler.resize_pool('science', replace(profile, memory_bytes=7), tool_limits={'simulate': 2}, expected_configuration_id=original)
    complete_lease(store, lease)
    updated = scheduler.resize_pool('science', replace(profile, memory_bytes=7), tool_limits={'simulate': 1}, expected_configuration_id=original)
    assert updated != original
    assert scheduler.snapshot('science')['configuration_id'] == updated
    assert scheduler.verify('science')


def test_pool_reweight_has_cas_without_resetting_history(tmp_path):
    store, run_id, *_ = graph(tmp_path)
    scheduler, _ = pooled_scheduler(store)
    scheduler.enroll('science', run_id, weight=1)
    with pytest.raises(ValueError, match='reweight'):
        scheduler.enroll('science', run_id, weight=2)
    with pytest.raises(ValueError, match='Stale'):
        scheduler.reweight('science', run_id, weight=2, expected_weight=3)
    scheduler.reweight('science', run_id, weight=2, expected_weight=1)
    queue = scheduler.snapshot('science')['queue'][0]
    assert queue['weight'] == 2 and queue['dispatches'] == 0
    assert scheduler.verify('science')


def test_real_process_worker_uses_fair_scheduler_and_both_resource_layers(tmp_path):
    store, first_id, *_ = graph(tmp_path, [simulation('one')])
    _, second_id, *_ = graph(tmp_path, [simulation('two')])
    scheduler, _ = pooled_scheduler(store, memory=134217728)
    scheduler.enroll('science', first_id)
    scheduler.enroll('science', second_id)
    worker = DagWorker(store, 'worker', contribution_store(tmp_path), scheduler=scheduler, pool_id='science')
    assert worker.run_next()['status'] == 'completed'
    assert worker.run_next()['status'] == 'completed'
    assert worker.run_next()['status'] == 'idle'
    assert scheduler.snapshot('science')['usage']['active_tasks'] == 0
    assert worker.reservations.used == (0, 0, 0, 0)
    assert store.verify(first_id) and store.verify(second_id) and scheduler.verify('science')


@pytest.mark.parametrize('cpu,memory', [(True, 1), (0, 1), (1, 0), (1, True)])
def test_invalid_persistent_resource_request_consumes_no_attempt(tmp_path, cpu, memory):
    store, run_id, *_ = graph(tmp_path)
    scheduler, _ = pooled_scheduler(store)
    scheduler.enroll('science', run_id)
    with pytest.raises(ValueError):
        scheduler.claim_next('science', 'worker', consent=Consent(contribute=True), cpu_slots=cpu, memory_bytes=memory)
    assert store.snapshot(run_id)['total_attempts'] == 0


def test_unknown_pool_and_unavailable_tool_do_not_dispatch(tmp_path):
    store, run_id, *_ = graph(tmp_path)
    scheduler, profile = pooled_scheduler(store, tools={'solve': 1})
    scheduler.enroll('science', run_id)
    assert scheduler.claim_next('science', 'worker', consent=Consent(contribute=True)) is None
    with pytest.raises(LookupError):
        scheduler.claim_next('missing', 'worker', consent=Consent(contribute=True))
    assert store.snapshot(run_id)['total_attempts'] == 0


def test_checkpoint_archive_roundtrip_requires_external_commitment(tmp_path):
    from nablamath.agents.dag_recovery import export_checkpoint, load_checkpoint
    store, run_id, *_ = graph(tmp_path)
    worker = DagWorker(store, 'worker', contribution_store(tmp_path))
    worker.run_one(run_id)
    target = tmp_path/'checkpoint.json'
    manifest = export_checkpoint(store, run_id, target)
    loaded = load_checkpoint(target, expected_archive_id=manifest['archive_id'])
    assert loaded['snapshot_id'] == manifest['snapshot_id']
    assert verify_dag_snapshot(loaded)
    with pytest.raises(ValueError, match='expected commitment'):
        load_checkpoint(target, expected_archive_id='0'*64)
    with pytest.raises(FileExistsError):
        export_checkpoint(store, run_id, target)
    assert load_checkpoint(target, expected_archive_id=manifest['archive_id']) == loaded
    assert list(tmp_path.glob('.dag-checkpoint-*')) == []


def test_checkpoint_archive_rejects_tampered_and_duplicate_json(tmp_path):
    from nablamath.agents.dag_recovery import export_checkpoint, load_checkpoint
    store, run_id, *_ = graph(tmp_path)
    target = tmp_path/'checkpoint.json'
    manifest = export_checkpoint(store, run_id, target)
    data = json.loads(target.read_text())
    data['checkpoint']['total_attempts'] = 1
    target.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_checkpoint(target, expected_archive_id=manifest['archive_id'])
    target.write_text('{"schema_version":1,"schema_version":1}')
    with pytest.raises(ValueError, match='Duplicate'):
        load_checkpoint(target, expected_archive_id=manifest['archive_id'])


def test_restore_preserves_completed_receipts_and_fences_old_lease(tmp_path):
    from nablamath.agents.dag_recovery import restore_checkpoint
    store, run_id, plan, ledger, _, clock = graph(tmp_path)
    first = store.claim(run_id, 'worker', consent=Consent(contribute=True))
    complete_lease(store, first)
    stale = store.claim(run_id, 'crashed', consent=Consent(contribute=True))
    before = store.snapshot(run_id)
    destination = DagStore(tmp_path/'restored.sqlite', clock=clock)
    assert restore_checkpoint(destination, before, ledger, expected_snapshot_id=before['snapshot_id']) == run_id
    recovered = destination.snapshot(run_id)
    assert recovered['tasks'][0]['receipt'] == before['tasks'][0]['receipt']
    assert recovered['tasks'][1]['status'] == 'retry_wait'
    assert recovered['total_attempts'] == before['total_attempts']
    assert recovered['deadline'] == before['deadline']
    with pytest.raises(LeaseConflict):
        complete_lease(destination, stale)
    fresh = destination.claim(run_id, 'replacement', consent=Consent(contribute=True))
    assert fresh['attempt'] == stale['attempt']+1
    complete_lease(destination, fresh)
    assert destination.snapshot(run_id)['status'] == 'completed'
    assert destination.verify(run_id)


def test_restore_attempt_exhaustion_blocks_descendants_and_never_resets_budget(tmp_path):
    from nablamath.agents.dag_recovery import restore_checkpoint
    store, run_id, _, ledger, _, clock = graph(tmp_path,
        budget=DagBudget(max_parallel_actions=1, max_attempts_per_action=1))
    store.claim(run_id, 'crashed', consent=Consent(contribute=True))
    before = store.snapshot(run_id)
    destination = DagStore(tmp_path/'restored.sqlite', clock=clock)
    restore_checkpoint(destination, before, ledger, expected_snapshot_id=before['snapshot_id'])
    after = destination.snapshot(run_id)
    assert after['status'] == 'failed'
    assert [row['status'] for row in after['tasks']] == ['failed', 'blocked']
    assert after['total_attempts'] == 1
    assert destination.verify(run_id)


def test_restore_elapsed_run_deadline_stays_expired(tmp_path):
    from nablamath.agents.dag_recovery import restore_checkpoint
    store, run_id, _, ledger, _, clock = graph(tmp_path,
        budget=DagBudget(max_parallel_actions=1, run_timeout_seconds=1))
    before = store.snapshot(run_id)
    clock.advance(2)
    destination = DagStore(tmp_path/'restored.sqlite', clock=clock)
    restore_checkpoint(destination, before, ledger, expected_snapshot_id=before['snapshot_id'])
    assert destination.snapshot(run_id)['status'] == 'expired'
    assert destination.claim(run_id, 'worker', consent=Consent(contribute=True)) is None
    assert destination.verify(run_id)


def test_restore_requires_current_approval_and_refuses_existing_run(tmp_path):
    from nablamath.agents.dag_recovery import restore_checkpoint
    store, run_id, _, ledger, _, clock = graph(tmp_path)
    before = store.snapshot(run_id)
    destination = DagStore(tmp_path/'restored.sqlite', clock=clock)
    with pytest.raises(PermissionError):
        restore_checkpoint(destination, before, ApprovalLedger(), expected_snapshot_id=before['snapshot_id'])
    with pytest.raises(LookupError):
        destination.snapshot(run_id)
    restore_checkpoint(destination, before, ledger, expected_snapshot_id=before['snapshot_id'])
    with pytest.raises(ValueError, match='exists'):
        restore_checkpoint(destination, before, ledger, expected_snapshot_id=before['snapshot_id'])
    with pytest.raises(ValueError, match='commitment'):
        restore_checkpoint(DagStore(tmp_path/'other.sqlite', clock=clock), before, ledger, expected_snapshot_id='0'*64)


def test_comparing_checkpoints_reports_progress_without_merging_authority(tmp_path):
    from nablamath.agents.dag_recovery import compare_checkpoints
    store, run_id, *_ = graph(tmp_path)
    before = store.snapshot(run_id)
    worker = DagWorker(store, 'worker', contribution_store(tmp_path))
    worker.run_one(run_id)
    after = store.snapshot(run_id)
    comparison = compare_checkpoints(before, after)
    assert comparison['right_only_completed'] == ['first']
    assert comparison['left_only_completed'] == []
    assert comparison['conflicting_receipts'] == []
    assert not comparison['automatic_merge']
    assert compare_checkpoints(after, after)['same_scientific_progress']


def test_inspection_explains_dependencies_without_raw_scientific_data(tmp_path):
    store, run_id, *_ = graph(tmp_path)
    report = store.inspect(run_id, consent=Consent(contribute=True))
    assert report['ready_actions'] == ['first']
    assert report['graph_depth'] == 2 and report['remaining_critical_path_actions'] == 2
    assert report['completion_possible']
    assert report['actions'][1]['waiting_on'] == ['first']
    assert 'dependencies_not_completed' in report['actions'][1]['reasons']
    serialized = json.dumps(report)
    assert 'initial' not in serialized and 'trajectory' not in serialized and 'author' not in serialized
    assert store.snapshot(run_id)['revision'] == 1


def test_inspection_tracks_committed_progress_and_remaining_work(tmp_path):
    store, run_id, *_ = graph(tmp_path)
    worker = DagWorker(store, 'worker', contribution_store(tmp_path))
    worker.run_one(run_id)
    report = store.inspect(run_id)
    assert report['completed_actions'] == 1
    assert report['ready_actions'] == ['second']
    assert report['remaining_critical_path_actions'] == 1
    assert not report['consent_checked']
    worker.run_one(run_id)
    completed = store.inspect(run_id)
    assert completed['ready_actions'] == [] and completed['remaining_critical_path_actions'] == 0
    assert completed['counts'] == {'completed': 2}


def test_inspection_distinguishes_backoff_recovery_and_review_pause(tmp_path):
    store, run_id, plan, ledger, _, clock = graph(tmp_path,
        budget=DagBudget(max_parallel_actions=1, retry_delay_seconds=5, lease_seconds=1))
    lease = store.claim(run_id, 'worker', consent=Consent(contribute=True))
    clock.advance(2)
    expired = store.inspect(run_id)
    assert 'lease_needs_recovery' in expired['actions'][0]['reasons']
    store.maintain(run_id)
    delayed = store.inspect(run_id)
    assert 'retry_backoff' in delayed['actions'][0]['reasons']
    assert delayed['actions'][0]['retry_after_seconds'] == 5
    head = ledger.head
    ledger.record(plan, 'first', reviewer='human', decision='revoke', reason='Stop review', expected_head=head)
    store.update_approvals(run_id, ledger, expected_head=head)
    paused = store.inspect(run_id)
    assert paused['ready_actions'] == []
    assert 'human_review_required' in paused['actions'][0]['reasons']


def test_inspection_reports_node_and_persistent_pool_admission_reasons(tmp_path):
    store, run_id, *_ = graph(tmp_path, [simulation('one'), simulation('two')])
    scheduler, _ = pooled_scheduler(store, cpu=1, memory=1, tasks=1, tools={'simulate': 1})
    scheduler.enroll('science', run_id)
    scheduler.claim_next('science', 'worker', consent=Consent(contribute=True))
    report = store.inspect(run_id, consent=Consent(), on_battery=True,
                           pool_snapshot=scheduler.snapshot('science'), memory_bytes=1)
    second = report['actions'][1]
    for reason in ('node_consent_inactive', 'node_battery_disallowed', 'pool_tool_quota',
                   'pool_cpu_quota', 'pool_memory_quota', 'pool_task_quota'):
        assert reason in second['reasons']
    assert report['ready_actions'] == []


def test_inspection_reports_failed_branch_cannot_complete(tmp_path):
    store, run_id, *_ = graph(tmp_path)
    store.cancel(run_id, reason='Cancel prerequisite', action_id='first')
    report = store.inspect(run_id)
    assert not report['completion_possible']
    assert report['counts'] == {'blocked': 1, 'cancelled': 1}
    assert report['actions'][1]['remaining_path_actions'] is None


def test_scheduler_replay_detects_persistent_fairness_debt_tampering(tmp_path):
    store, run_id, *_ = graph(tmp_path)
    scheduler, _ = pooled_scheduler(store)
    scheduler.enroll('science', run_id)
    scheduler.claim_next('science', 'worker', consent=Consent(contribute=True))
    assert scheduler.verify('science')
    with sqlite3.connect(store.path) as db:
        db.execute('UPDATE dag_schedule SET virtual_finish=99 WHERE pool_id=? AND run_id=?', ('science', run_id))
    assert not scheduler.verify('science')


def test_solve_then_verify_data_dependency_is_replayed_end_to_end(tmp_path):
    from nablamath.forge.task_spec import TaskSpec
    task = TaskSpec('linear_system', {'matrix': [['2']], 'rhs': ['6']}, size=1).to_data()
    trials = [dict(id='solve', tool='solve', arguments=dict(task=task)),
              dict(id='verify', tool='verify', depends_on=['solve'],
                   arguments=dict(task=task, candidate={'$result': {'action': 'solve', 'path': ['candidate']}}))]
    store, run_id, *_ = graph(tmp_path, trials)
    worker = DagWorker(store, 'worker', contribution_store(tmp_path))
    outcomes = worker.drain(run_id)
    assert outcomes['run_status'] == 'completed', outcomes
    snapshot = store.snapshot(run_id)
    assert snapshot['tasks'][1]['result']['verification']['valid']
    assert snapshot['tasks'][1]['receipt']['arguments']['candidate']['solution'] == ['3']
    assert store.verify(run_id)


def test_worker_timeout_consumes_bounded_retry_and_releases_resources(tmp_path, monkeypatch):
    from services.worker import dag_executor as module
    store, run_id, *_ = graph(tmp_path, [simulation('one')])
    scheduler, _ = pooled_scheduler(store, memory=67108864)
    scheduler.enroll('science', run_id)
    class TimeoutRegistry:
        def execute(self, *args, **kwargs):
            raise TimeoutError('No output within process deadline')
    monkeypatch.setattr(module, '_registry', lambda: TimeoutRegistry())
    worker = DagWorker(store, 'worker', contribution_store(tmp_path), scheduler=scheduler, pool_id='science')
    first = worker.run_next()
    second = worker.run_next()
    assert first['code'] == second['code'] == 'tool_timeout'
    assert store.snapshot(run_id)['status'] == 'failed'
    assert scheduler.snapshot('science')['usage']['active_tasks'] == 0
    assert worker.reservations.used == (0, 0, 0, 0)
    assert store.verify(run_id) and scheduler.verify('science')


def test_node_consent_revoked_during_tool_execution_discards_result(tmp_path, monkeypatch):
    from services.worker import dag_executor as module
    from nablamath.agents.tool_registry import _world
    store, run_id, *_ = graph(tmp_path, [simulation('one')])
    consent_store = contribution_store(tmp_path)
    class RevokingRegistry:
        def execute(self, name, arguments, permissions):
            result = _world(**arguments)
            consent_store.save(Consent())
            return result
    monkeypatch.setattr(module, '_registry', lambda: RevokingRegistry())
    worker = DagWorker(store, 'worker', consent_store)
    result = worker.run_one(run_id)
    assert result['status'] == 'denied' and result['code'] == 'consent_revoked'
    snapshot = store.snapshot(run_id)
    assert snapshot['tasks'][0]['result'] is None and snapshot['tasks'][0]['status'] == 'retry_wait'
    assert worker.completed == 0
    assert store.verify(run_id)
