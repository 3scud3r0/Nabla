"""Closed registry with argument contracts and killable tool subprocesses.

Registered functions are trusted application code, not an OS sandbox. Resource
budgets bound calls, wall time and transport size; arbitrary code is never a tool.
"""
from dataclasses import dataclass
import json
import multiprocessing
from queue import Empty
from ..core.semantic_ir import canonical_json


@dataclass(frozen=True)
class Tool:
    name: str
    function: object
    required: frozenset[str]
    optional: frozenset[str] = frozenset()
    description: str = ''

    def __post_init__(self):
        object.__setattr__(self, 'required', frozenset(self.required))
        object.__setattr__(self, 'optional', frozenset(self.optional))
        if not self.name or not callable(self.function) or self.required & self.optional:
            raise ValueError('Contrato de ferramenta inválido')


def _worker(function, arguments, queue, max_output):
    try:
        result = canonical_json(function(**arguments))
        if len(result.encode()) > max_output:
            raise ValueError('Resultado excede orçamento')
        queue.put(('ok', result))
    except Exception as exc:
        queue.put(('error', str(exc)[:1000]))


class ToolRegistry:
    def __init__(self, tools):
        tools = tuple(tools)
        self._tools = {tool.name: tool for tool in tools}
        if len(self._tools) != len(tools):
            raise ValueError('Ferramenta duplicada')

    def describe(self):
        return tuple({'name': t.name, 'required': sorted(t.required), 'optional': sorted(t.optional),
                      'description': t.description} for t in self._tools.values())

    def validate(self, name, arguments, permissions):
        if name not in permissions.allowed_tools or name not in self._tools:
            raise PermissionError('Ferramenta não autorizada: '+name)
        tool = self._tools[name]
        if not isinstance(arguments, dict) or not tool.required <= set(arguments) <= tool.required | tool.optional:
            raise ValueError('Argumentos não correspondem ao contrato')
        if len(canonical_json(arguments).encode()) > permissions.max_input_bytes:
            raise ValueError('Entrada excede orçamento')

    def execute(self, name, arguments, permissions):
        self.validate(name, arguments, permissions)
        context = multiprocessing.get_context('spawn')
        queue = context.Queue(maxsize=1)
        process = context.Process(target=_worker, args=(self._tools[name].function, arguments, queue, permissions.max_output_bytes))
        try:
            process.start()
            try:
                status, payload = queue.get(timeout=permissions.timeout_seconds)
            except Empty as exc:
                raise TimeoutError('Ferramenta excedeu tempo ou terminou sem resultado') from exc
            if status != 'ok':
                raise ValueError(payload)
            return json.loads(payload)
        finally:
            if process.pid is not None:
                process.join(timeout=0.1)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=1)
                if process.is_alive():
                    process.kill()
                    process.join()
            queue.close()


def _solve(task):
    from ..forge.task_spec import TaskSpec
    from ..forge.solvers import solve_task
    from ..verify.trace import build_trace
    task = TaskSpec.from_data(task)
    return build_trace(task, solve_task(task)).to_data()


def _world(name, initial, rate=1., duration=1., steps=100):
    from ..worlds.model_spec import ModelSpec
    from ..worlds.validation import simulate
    return simulate(ModelSpec(name, tuple(initial), rate, duration), steps=steps)


def _verify(task,candidate):
    from ..forge.task_spec import TaskSpec
    from ..verify.trace import build_trace
    return build_trace(TaskSpec.from_data(task),candidate).to_data()


def scientific_registry():
    return ToolRegistry((Tool('verify', _verify, frozenset({'task','candidate'}), description='Independent candidate verification'),
                         Tool('solve', _solve, frozenset({'task'}), description='Solve and independently verify exact tasks'),
                         Tool('simulate', _world, frozenset({'name','initial'}), frozenset({'rate','duration','steps'}),
                              'Bounded Euler/RK4 models; no experimental claim')))
