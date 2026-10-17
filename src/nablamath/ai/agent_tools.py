"""JSON Schema tool contracts generated from the live calculation catalog."""
from functools import partial
import json
from threading import Lock, BoundedSemaphore
from contextlib import contextmanager

from ..agents.permissions import Permissions
from ..agents.tool_registry import Tool, ToolRegistry
from ..calc.catalog import catalog
from ..calc.session import CalculationSession
from ..core.semantic_ir import canonical_json

from .tool_schemas import schema_for


def tool_schemas():
    return [{'name':operation['name'],'description':operation['contract'],
             'inputSchema':schema_for(operation)} for operation in catalog()['operations']]


def openai_tools():
    return [{'type':'function','function':{'name':t['name'],'description':t['description'],
                                         'parameters':t['inputSchema']}} for t in tool_schemas()]


def execute_calculation(operation, **arguments):
    return CalculationSession().execute(operation, **arguments).to_data()


class AgentTools:
    """Bounded calls in killable subprocesses; only registered catalog operations run."""
    def __init__(self, permissions=None, *, max_concurrent=4):
        if type(max_concurrent) is not int or not 1 <= max_concurrent <= 32:
            raise ValueError('max_concurrent must be between 1 and 32')
        self.schemas = {t['name']:t for t in tool_schemas()}
        self.permissions = permissions or Permissions(frozenset(self.schemas),max_calls=100)
        self.calls = 0
        self._lock = Lock()
        self._capacity = BoundedSemaphore(max_concurrent)
        entries = catalog()['operations']
        self.registry = ToolRegistry(Tool(row['name'],partial(execute_calculation,row['name']),
                                    frozenset(row['required']),frozenset(row['optional']),row['contract'])
                                    for row in entries)

    @contextmanager
    def _execution_slot(self):
        if not self._capacity.acquire(blocking=False):
            raise RuntimeError('Scientific tool capacity exhausted; retry after a running call completes')
        try:
            with self._lock:
                if self.calls >= self.permissions.max_calls:
                    raise PermissionError('Tool call budget exhausted')
                self.calls += 1
            yield
        finally:
            self._capacity.release()

    def call(self, name, arguments):
        self.registry.validate(name,arguments,self.permissions)
        # Structural JSON Schema validation uses a small, standard dependency.
        try:
            from jsonschema import Draft202012Validator
        except ImportError as exc:
            raise ImportError('Install nablamath[ai] for tool schema validation') from exc
        Draft202012Validator(self.schemas[name]['inputSchema']).validate(json.loads(canonical_json(arguments)))
        with self._execution_slot():
            return self.registry.execute(name,arguments,self.permissions)

    def verify_conjecture(self, arguments):
        if 'verify_conjecture' not in self.permissions.allowed_tools:
            raise PermissionError('Conjecture verification was not enabled for this client')
        if len(canonical_json(arguments).encode()) > self.permissions.max_input_bytes:
            raise ValueError('Conjecture exceeds input byte budget')
        from .sandbox_verifier import AIVerifier
        with self._execution_slot():
            result = AIVerifier(timeout_seconds=min(5,self.permissions.timeout_seconds)).verify(arguments)
            from ..calc.receipt import receipt
            audited = receipt('ai.verify_conjecture',arguments,result.to_data(),backend='z3')
            if len(canonical_json(audited).encode()) > self.permissions.max_output_bytes:
                raise ValueError('Conjecture result exceeds the output byte budget')
            return result
