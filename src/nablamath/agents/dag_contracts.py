"""Immutable contracts for durable, approved, data-only scientific DAG runs.

The graph is the existing Proposal: a finite topological list with explicit
result references. Resource accounting here is admission and bounded attempts;
it does not assert that trusted Python has an OS memory or network sandbox.
"""
from dataclasses import asdict, dataclass
import math

from ..core.semantic_contracts import require_fields, require_text
from ..core.semantic_ir import canonical_json, fingerprint
from .experiment_planner import ExperimentPlan
from .permissions import Permissions
from .proposals import Proposal

SCIENTIFIC_TOOLS = frozenset({'solve', 'verify', 'simulate'})
TASK_STATES = frozenset({'queued', 'leased', 'retry_wait', 'completed', 'failed', 'blocked', 'cancelled'})
RUN_STATES = frozenset({'ready', 'running', 'paused', 'completed', 'failed', 'cancelled', 'expired'})
FAILURE_CODES = frozenset({'tool_error', 'tool_timeout', 'lease_expired', 'output_budget',
                           'consent_revoked', 'worker_cancelled', 'invalid_result'})
TERMINAL_TASKS = frozenset({'completed', 'failed', 'blocked', 'cancelled'})


def finite_time(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f'Finite nonnegative {name} required')
    return float(value)


@dataclass(frozen=True)
class DagBudget:
    max_attempts_per_action: int = 2
    max_total_attempts: int = 100
    max_parallel_actions: int = 4
    max_result_bytes: int = 1048576
    max_total_result_bytes: int = 16777216
    run_timeout_seconds: float = 600.0
    lease_seconds: float = 30.0
    retry_delay_seconds: float = 0.0

    def __post_init__(self):
        for name, maximum in (('max_attempts_per_action', 8), ('max_total_attempts', 800),
                              ('max_parallel_actions', 100), ('max_result_bytes', 1048576),
                              ('max_total_result_bytes', 33554432)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f'Invalid {name}')
        for name, maximum, positive in (('run_timeout_seconds', 3600, True),
                                        ('lease_seconds', 120, True),
                                        ('retry_delay_seconds', 3600, False)):
            value = finite_time(getattr(self, name), name)
            if value > maximum or positive and value <= 0:
                raise ValueError(f'Invalid {name}')
            object.__setattr__(self, name, value)
        if self.max_result_bytes > self.max_total_result_bytes:
            raise ValueError('Per-action output budget exceeds whole-run output budget')

    def to_data(self):
        return asdict(self)

    @classmethod
    def from_data(cls, data):
        require_fields(data, set(cls.__dataclass_fields__))
        return cls(**data)


def permissions_data(permissions):
    if not isinstance(permissions, Permissions):
        raise ValueError('Typed scientific permissions required')
    if not permissions.allowed_tools <= SCIENTIFIC_TOOLS:
        raise PermissionError('Durable DAGs only accept fixed scientific tools')
    return dict(allowed_tools=sorted(permissions.allowed_tools), max_calls=permissions.max_calls,
                timeout_seconds=permissions.timeout_seconds, max_input_bytes=permissions.max_input_bytes,
                max_output_bytes=permissions.max_output_bytes)


def permissions_from_data(data):
    require_fields(data, {'allowed_tools', 'max_calls', 'timeout_seconds', 'max_input_bytes', 'max_output_bytes'})
    result = Permissions(**data)
    permissions_data(result)
    return result


def experiment_from_data(data):
    require_fields(data, {'proposal', 'owner', 'hypothesis', 'expected_observation', 'protocol_version'})
    return ExperimentPlan(Proposal.from_data(data['proposal']), data['owner'], data['hypothesis'],
                          data['expected_observation'], data['protocol_version'])


def preflight_dag(plan, permissions, budget):
    """Validate graph-wide limits before any durable record or tool execution."""
    from .secure_execution import preflight_actions
    if not isinstance(plan, ExperimentPlan) or not isinstance(budget, DagBudget):
        raise ValueError('Typed experiment and DAG budget required')
    permissions_data(permissions)
    if len(plan.proposal.actions) > budget.max_total_attempts:
        raise ValueError('Total attempt budget cannot cover even one pass of the graph')
    if budget.max_parallel_actions > permissions.max_calls:
        raise ValueError('Parallel action budget exceeds scientific call budget')
    if budget.max_result_bytes > permissions.max_output_bytes:
        raise ValueError('DAG output budget exceeds tool transport output budget')
    # Referenced payloads are checked again after resolving committed dependencies.
    preflight_actions(plan, permissions)
    return fingerprint(dict(plan=plan.to_data(), permissions=permissions_data(permissions), budget=budget.to_data()))


def validate_worker(worker):
    return require_text(worker, 'worker', limit=128)


def result_receipt(*, run_id, action, arguments, result, dependencies):
    """The scientific receipt is independent of lease expiry and retry history."""
    body = dict(schema_version=1, run_id=run_id, action_id=action.action_id, tool=action.tool,
                arguments=arguments, result=result, dependencies=dict(sorted(dependencies.items())))
    return dict(body, receipt_id=fingerprint(body))


def replay_scientific_result(tool, arguments, result):
    """Replay only the fixed repository-owned mathematical implementations."""
    from .tool_registry import _solve, _verify, _world
    operations = {'solve': _solve, 'verify': _verify, 'simulate': _world}
    if tool not in operations:
        return False
    try:
        return canonical_json(operations[tool](**arguments)) == canonical_json(result)
    except (ValueError, TypeError, ArithmeticError, KeyError, OverflowError):
        return False
