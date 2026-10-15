"""Bounded exact-rational worker; cancellation checked at computation boundaries.

This runs trusted application code in-process. Deadlines are cooperative and do
not provide OS isolation or interruption of an already-running calculation.
"""
from dataclasses import dataclass
from threading import Lock
import math
import time
from nablamath.core.semantic_ir import SemanticExpression, canonical_json, rational
from nablamath.research import calculate


class ExecutionCancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class ExecutionBudget:
    max_tasks: int = 10
    max_input_bytes: int = 65536
    max_expression_chars: int = 4096
    timeout_seconds: float = 10.0

    def __post_init__(self):
        for value, limit in ((self.max_tasks, 10000), (self.max_input_bytes, 1048576),
                             (self.max_expression_chars, 4096)):
            if type(value) is not int or not 1 <= value <= limit:
                raise ValueError('Invalid worker budget')
        if (isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float))
                or not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 60):
            raise ValueError('Invalid cooperative deadline')


class ExactExecutor:
    def __init__(self, budget=None):
        self.budget = budget or ExecutionBudget()
        self.attempted = 0
        self.completed = 0
        self._lock = Lock()

    def execute(self, task, *, cancelled=lambda: False):
        if not isinstance(task, dict) or set(task) != {'expression', 'values'}:
            raise ValueError('Exact task requires expression and values only')
        expression, values = task['expression'], task['values']
        if (not isinstance(expression, str) or not expression.strip()
                or len(expression) > self.budget.max_expression_chars
                or not isinstance(values, dict) or len(values) > 128):
            raise ValueError('Invalid bounded exact task')
        for name, value in values.items():
            if not isinstance(name, str) or not name or len(name) > 128:
                raise ValueError('Invalid symbol')
            rational(value)
        if len(canonical_json(task).encode()) > self.budget.max_input_bytes:
            raise ValueError('Worker input quota exceeded')
        # Bound arithmetic growth before reaching the trusted evaluator: source
        # length alone does not bound nested exponentiation or rational size.
        SemanticExpression.parse(expression)
        if cancelled():
            raise ExecutionCancelled('Cancelled before calculation')
        with self._lock:
            if self.attempted >= self.budget.max_tasks:
                raise RuntimeError('Worker task quota exhausted')
            self.attempted += 1
        start = time.monotonic()
        result = calculate(expression, values)
        if cancelled():
            raise ExecutionCancelled('Cancelled before publication')
        if time.monotonic()-start > self.budget.timeout_seconds:
            raise TimeoutError('Cooperative calculation deadline exceeded; result discarded')
        with self._lock:
            self.completed += 1
        return dict(result_id=result.content_id, value=str(result.value))
