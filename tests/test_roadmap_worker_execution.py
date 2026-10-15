import json
import pytest
from nablamath.coordination.local import LocalCoordinator
from services.worker.executor import ExactExecutor, ExecutionBudget, ExecutionCancelled
from services.coordinator.task_leases import LeaseWorker
from services.coordinator.telemetry import AggregateTelemetry


def test_durable_leases_and_consensus(tmp_path):
    path = tmp_path/'queue.sqlite'
    queue = LocalCoordinator(path)
    task_id = queue.add('x+x', {'x': '1/3'})
    telemetry = AggregateTelemetry()
    first = LeaseWorker(queue, 'alice', ExactExecutor(), telemetry=telemetry).run_once()
    assert first['status'] == 'awaiting_second_worker'
    recovered = LocalCoordinator(path)
    assert recovered.submit('alice', task_id, first['result_id']) == 'awaiting_second_worker'
    second = LeaseWorker(recovered, 'bob', ExactExecutor(), telemetry=telemetry).run_once()
    assert second['status'] == 'verified'
    assert second['result_id'] == first['result_id']
    assert recovered.submit('alice', task_id, first['result_id']) == 'verified'
    assert recovered.status(task_id) == 'verified'
    snapshot = telemetry.snapshot()
    assert snapshot['counts']['verified'] == 1
    serialized = json.dumps(snapshot)
    assert 'alice' not in serialized and 'bob' not in serialized and task_id not in serialized
    assert 'x+x' not in serialized


def test_cancelled_work_never_submitted(tmp_path):
    queue = LocalCoordinator(tmp_path/'queue.sqlite')
    task_id = queue.add('1+1', {})
    class CancellingExecutor(ExactExecutor):
        def execute(self, task, **kwargs):
            queue.cancel(task_id)
            return super().execute(task, **kwargs)
    executor = CancellingExecutor()
    worker = LeaseWorker(queue, 'worker', executor)
    assert worker.run_once()['status'] == 'cancelled'
    assert queue.status(task_id) == 'cancelled'
    assert executor.completed == 0
    assert worker.telemetry.snapshot()['counts']['cancelled'] == 1


def test_quota_before_new_lease_and_idle(tmp_path):
    queue = LocalCoordinator(tmp_path/'queue.sqlite')
    executor = ExactExecutor(ExecutionBudget(max_tasks=1))
    worker = LeaseWorker(queue, 'worker', executor)
    assert worker.run_once()['status'] == 'idle'
    queue.add('1+1', {})
    assert worker.run_once()['status'] == 'awaiting_second_worker'
    with pytest.raises(RuntimeError, match='before acquiring'):
        worker.run_once()


def test_executor_contract_budget_and_cancel_boundaries():
    executor = ExactExecutor(ExecutionBudget(max_tasks=1))
    with pytest.raises(ExecutionCancelled):
        executor.execute({'expression': '1+1', 'values': {}}, cancelled=lambda: True)
    assert executor.attempted == 0
    with pytest.raises(ValueError):
        executor.execute({'expression': '1+1', 'values': {}, 'code': 'shell'})
    with pytest.raises(ValueError):
        executor.execute({'expression': 'x', 'values': {'x': True}})
    assert executor.execute({'expression': '1/3+1/3', 'values': {}})['value'] == '2/3'
    with pytest.raises(RuntimeError):
        executor.execute({'expression': '1', 'values': {}})
    with pytest.raises(ValueError):
        ExecutionBudget(max_tasks=True)


def test_post_calculation_cancellation_discards_result():
    checks = iter([False, True])
    executor = ExactExecutor()
    with pytest.raises(ExecutionCancelled):
        executor.execute({'expression': '1+1', 'values': {}}, cancelled=lambda: next(checks))
    assert executor.attempted == 1 and executor.completed == 0


def test_telemetry_rejects_unbounded_labels_and_is_detached():
    telemetry = AggregateTelemetry()
    with pytest.raises(ValueError):
        telemetry.record('participant-alice')
    with pytest.raises(ValueError):
        telemetry.record('failed', duration_seconds=float('nan'))
    telemetry.record('failed', duration_seconds=2)
    snapshot = telemetry.snapshot()
    snapshot['counts']['failed'] = 200
    assert telemetry.snapshot()['counts']['failed'] == 1
    assert sum(telemetry.snapshot()['duration_buckets'].values()) == 1


def test_cooperative_timeout_discards_completed_calculation(monkeypatch):
    from services.worker import executor as module
    times = iter([0, 2])
    monkeypatch.setattr(module.time, 'monotonic', lambda: next(times))
    executor = ExactExecutor(ExecutionBudget(timeout_seconds=1))
    with pytest.raises(TimeoutError):
        executor.execute({'expression': '1+1', 'values': {}})
    assert executor.attempted == 1 and executor.completed == 0


def test_arithmetic_growth_rejected_before_evaluation(monkeypatch):
    from services.worker import executor as module
    def forbidden_calculate(*args, **kwargs):
        raise AssertionError('Unbounded arithmetic reached evaluator')
    monkeypatch.setattr(module, 'calculate', forbidden_calculate)
    executor = ExactExecutor()
    for source in ('2**(2**16)', '2**1000000000', '(((x**16)**16)**16)**16'):
        with pytest.raises(ValueError):
            executor.execute({'expression': source, 'values': {'x': 2}})
    assert executor.attempted == 0
