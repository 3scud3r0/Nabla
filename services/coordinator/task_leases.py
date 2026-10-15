"""Lease lifecycle adapter over the durable local exact-task coordinator."""
import time
from nablamath.core.semantic_contracts import require_text
from services.worker.executor import ExecutionCancelled
from .telemetry import AggregateTelemetry


class LeaseWorker:
    def __init__(self, coordinator, participant, executor, *, lease_seconds=60, telemetry=None):
        require_text(participant, 'participant', limit=128)
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
            raise ValueError('Invalid lease duration')
        self.coordinator, self.participant, self.executor = coordinator, participant, executor
        self.lease_seconds = lease_seconds
        self.telemetry = telemetry if telemetry is not None else AggregateTelemetry()

    def heartbeat(self, task_id):
        return self.coordinator.heartbeat(self.participant, task_id, self.lease_seconds)

    def run_once(self, *, cancelled=lambda: False):
        start = time.monotonic()
        if cancelled():
            self.telemetry.record('cancelled')
            return dict(status='cancelled')
        if self.executor.attempted >= self.executor.budget.max_tasks:
            raise RuntimeError('Worker task quota exhausted before acquiring lease')
        lease = self.coordinator.lease(self.participant, self.lease_seconds)
        if lease is None:
            self.telemetry.record('idle')
            return dict(status='idle')
        def stopped():
            return (cancelled() or self.coordinator.status(lease['task_id']) != 'pending'
                    or time.time() >= lease['lease_expires_unix'])
        try:
            lease['lease_expires_unix'] = self.heartbeat(lease['task_id'])
            result = self.executor.execute(dict(expression=lease['expression'], values=lease['values']), cancelled=stopped)
            if stopped():
                raise ExecutionCancelled('Lease no longer active')
            status = self.coordinator.submit(self.participant, lease['task_id'], result['result_id'])
            self.telemetry.record(status, duration_seconds=time.monotonic()-start)
            return dict(status=status, task_id=lease['task_id'], result_id=result['result_id'])
        except ExecutionCancelled:
            self.telemetry.record('cancelled', duration_seconds=time.monotonic()-start)
            return dict(status='cancelled', task_id=lease['task_id'])
        except Exception:
            self.telemetry.record('failed', duration_seconds=time.monotonic()-start)
            raise
