"""JSON Schema tool contracts generated from the live calculation catalog."""
from functools import partial
import json
from threading import Lock

from ..agents.permissions import Permissions
from ..agents.tool_registry import Tool, ToolRegistry
from ..calc.catalog import catalog
from ..calc.session import CalculationSession
from ..core.semantic_ir import canonical_json

SCALAR = {'anyOf':[{'type':'integer'},{'type':'number'},{'type':'string','maxLength':4096}]}
JSON_VALUE = {'anyOf':[{'type':'null'},{'type':'boolean'},{'type':'integer'},
                       {'type':'number'},{'type':'string','maxLength':100000},
                       {'type':'array','maxItems':10000,'items':{'$ref':'#/$defs/json'}},
                       {'type':'object','maxProperties':10000,'additionalProperties':{'$ref':'#/$defs/json'}}]}
INTEGER_FIELDS = set('n k steps window order lag decision_limit max_attempts max_pieces max_terms subdivisions numerator_degree denominator_degree max_segments modulus prime trials successes draws seed samples burn_in thin output qubits shots'.split())
BOOLEAN_FIELDS = {'intercept','sample','density_matrix'}
TEXT_FIELDS = {'kind','method','model','variable','direction','nonzero','numerator','denominator'}
ARRAY_FIELDS = set('matrix rhs vectors coefficients transition distribution objective constraints x_bounds y_bounds points hessian linear upper lower predictors response x y vertices edges clauses targets rewards probabilities counts population costs observed gates nodes shape axes bounds integrality'.split())
OBJECT_FIELDS = {'prior','likelihood','parameters','inputs'}


def argument_schema(name):
    if name in INTEGER_FIELDS:
        return {'type':'integer'}
    if name in BOOLEAN_FIELDS:
        return {'type':'boolean'}
    if name in TEXT_FIELDS:
        # nonzero is a sequence of expressions in the legacy simplify operation.
        if name == 'nonzero':
            return {'type':'array','maxItems':10000,'items':{'type':'string','maxLength':4096}}
        return {'type':'string','maxLength':4096}
    if name in ARRAY_FIELDS:
        return {'type':'array','maxItems':10000,'items':{'$ref':'#/$defs/json'}}
    if name in OBJECT_FIELDS:
        return {'type':'object','maxProperties':10000,'additionalProperties':{'$ref':'#/$defs/json'}}
    # Catalog operations intentionally overload source/values/first/second/point etc.
    return {'$ref':'#/$defs/json'}


def tool_schemas():
    result = []
    for operation in catalog()['operations']:
        names = operation['required'] + operation['optional']
        properties = {n:argument_schema(n) for n in sorted(names)}
        # These names have different shapes in different catalog operations.
        for name in set(names) & {'upper','lower','modulus','population','observed','initial','alpha'}:
            properties[name] = {'$ref':'#/$defs/json'}
        schema = {'type':'object', 'properties':properties,
                  'required':operation['required'], 'additionalProperties':False,
                  '$defs':{'json':JSON_VALUE}}
        result.append({'name':operation['name'],'description':operation['contract'],'inputSchema':schema})
    return result


def openai_tools():
    return [{'type':'function','function':{'name':t['name'],'description':t['description'],
                                         'parameters':t['inputSchema']}} for t in tool_schemas()]


def execute_calculation(operation, **arguments):
    return CalculationSession().execute(operation, **arguments).to_data()


class AgentTools:
    """Bounded calls in killable subprocesses; only registered catalog operations run."""
    def __init__(self, permissions=None):
        self.schemas = {t['name']:t for t in tool_schemas()}
        self.permissions = permissions or Permissions(frozenset(self.schemas),max_calls=100)
        self.calls = 0
        self._lock = Lock()
        entries = catalog()['operations']
        self.registry = ToolRegistry(Tool(row['name'],partial(execute_calculation,row['name']),
                                    frozenset(row['required']),frozenset(row['optional']),row['contract'])
                                    for row in entries)

    def call(self, name, arguments):
        self.registry.validate(name,arguments,self.permissions)
        # Structural JSON Schema validation uses a small, standard dependency.
        try:
            from jsonschema import Draft202012Validator
        except ImportError as exc:
            raise ImportError('Install nablamath[ai] for tool schema validation') from exc
        Draft202012Validator(self.schemas[name]['inputSchema']).validate(json.loads(canonical_json(arguments)))
        with self._lock:
            if self.calls >= self.permissions.max_calls:
                raise PermissionError('Tool call budget exhausted')
            self.calls += 1
        return self.registry.execute(name,arguments,self.permissions)
