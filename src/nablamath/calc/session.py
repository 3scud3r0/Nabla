"""Auditable scientific operations, exact bindings and explicit numerical approximations."""
from dataclasses import asdict,dataclass,is_dataclass
from fractions import Fraction
import math
import copy
import json
from concurrent.futures import ThreadPoolExecutor, CancelledError
from functools import cached_property
from threading import BoundedSemaphore, RLock, Condition

from ..core.semantic_ir import SemanticExpression,canonical_json,fingerprint,rational
from ..core.types import ScientificType
from ..core.units import ONE,Unit,Quantity
from ..core.precision import PrecisionPolicy
from ..core.obligations import require_obligations
from ..expression import Symbol,evaluate,parse_expr,to_data

AREAS={'evaluate':'algebra','simplify':'algebra','factor':'algebra','solve_linear':'linear_algebra',
       'lu':'linear_algebra','orthogonal_basis':'linear_algebra','condition':'numerical',
       'differentiate':'calculus','integrate':'calculus','limit':'calculus','series':'calculus',
       'binomial':'discrete','topological_sort':'discrete','markov':'probability','statistics':'statistics',
       'optimize':'optimization','quadratic_optimize':'optimization','geometry':'geometry','conic':'geometry','approximate':'numerical','ode':'calculus'}


REQUIRED={
    'evaluate':{'source'},'simplify':{'source'},'factor':{'coefficients'},
    'solve_linear':{'matrix','rhs'},'lu':{'matrix'},'orthogonal_basis':{'vectors'},'condition':{'matrix'},
    'differentiate':{'source'},'integrate':{'source'},'limit':{'numerator','denominator','point'},
    'series':{'source'},'binomial':{'n','k'},'topological_sort':{'vertices','edges'},
    'markov':{'transition','distribution'},'statistics':{'values'},'approximate':{'value'},
    'optimize':{'objective','x_bounds','y_bounds'},'quadratic_optimize':{'hessian','linear'},
    'geometry':{'points'},'conic':{'coefficients'},'ode':{'model','initial'}}
OPTIONAL={
    'evaluate':{'values'},'simplify':{'nonzero'},'differentiate':{'variable'},
    'integrate':{'variable','start','end'},'limit':{'variable'},'series':{'variable','center','order'},
    'markov':{'steps'},'statistics':{'sample','median','window','population_variance','radius'},
    'optimize':{'constraints'},'quadratic_optimize':{'constraints','upper','constant'},
    'ode':{'rate','duration','steps','method'}}

AREAS['ode_adaptive'] = 'calculus'
REQUIRED['ode_adaptive'] = {'model', 'initial'}
OPTIONAL['ode_adaptive'] = {'rate', 'duration', 'atol', 'rtol', 'max_attempts', 'initial_step'}


from .catalog import OPERATIONS as EXTENDED_OPERATIONS
for _name, (_area, _required, _optional, _contract) in EXTENDED_OPERATIONS.items():
    AREAS[_name], REQUIRED[_name], OPTIONAL[_name] = _area, _required, _optional

def encode(value):
    if isinstance(value,Fraction):
        return str(value)
    if is_dataclass(value):
        return {k:encode(v) for k,v in asdict(value).items()}
    if isinstance(value,dict):
        return {k:encode(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):
        return [encode(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value):
        raise ValueError('Resultado numerico nao finito')
    return value


@dataclass(frozen=True)
class Calculation:
    request_json: str
    result_json: str
    limitations: str

    @cached_property
    def _receipt_json(self):
        payload={'schema_version':1,'request':json.loads(self.request_json),'result':json.loads(self.result_json),
                 'limitations':self.limitations,'formal_proof':False}
        return canonical_json({**payload,'content_id':fingerprint(payload)})

    def to_data(self):
        return json.loads(self._receipt_json)


class PendingCalculation:
    """An already computed result whose immutable receipt is being packaged.

    Reading receipt fields or calling to_data waits for packaging, not for math.
    The result property is a detached snapshot, so callers cannot rewrite history.
    """
    def __init__(self, result, future):
        self._result, self._future = result, future

    @property
    def result(self):
        return copy.deepcopy(self._result)

    @property
    def request_json(self):
        return self._future.result().request_json

    @property
    def result_json(self):
        return self._future.result().result_json

    @property
    def limitations(self):
        return self._future.result().limitations

    def to_data(self):
        return self._future.result().to_data()

    def done(self):
        return self._future.done()


class CalculationSession:
    def __init__(self,*,precision=34,background_receipts=False,max_pending=128,receipt_sink=None):
        if type(background_receipts) is not bool or type(max_pending) is not int or not 1<=max_pending<=65536:
            raise ValueError('Invalid background receipt configuration')
        if receipt_sink is not None and not callable(receipt_sink):
            raise TypeError('receipt_sink must be callable')
        self.precision=PrecisionPolicy(precision)
        self._bindings={}
        self.background_receipts=background_receipts
        self._sink=receipt_sink
        self._executor=None
        self._slots=BoundedSemaphore(max_pending)
        self._pending=set()
        self._receipt_error=None
        self._lock=RLock()
        self._completion=Condition(self._lock)
        self._closed=False

    def _submit_receipt(self, function, *args):
        # Backpressure is explicit: an audit record is never silently dropped.
        with self._lock:
            if self._closed:
                raise RuntimeError('Calculation session is closed')
            if not self._slots.acquire(blocking=False):
                raise BufferError('Receipt buffer full; flush before continuing')
            try:
                if self._executor is None:
                    self._executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='nabla-receipts')
                future=self._executor.submit(function,*args)
                self._pending.add(future)
                def completed(done):
                    with self._completion:
                        self._pending.discard(done)
                        error=CancelledError('Accepted audit record was cancelled') if done.cancelled() else done.exception()
                        if error is not None and self._receipt_error is None:
                            self._receipt_error=error
                        self._slots.release()
                        self._completion.notify_all()
                future.add_done_callback(completed)
                return future
            except BaseException:
                self._slots.release()
                raise

    def flush(self):
        """Wait for every accepted record; expose worker/sink errors to the caller."""
        with self._lock:
            pending=list(self._pending)
        errors=[]
        results=[]
        for future in pending:
            try:
                results.append(future.result())
            except Exception as error:
                errors.append(error)
        with self._completion:
            # Future.result() may return before its done callbacks finish.
            # Wait for slot release and error bookkeeping before reporting flush.
            self._completion.wait_for(lambda:not any(future in self._pending for future in pending))
            if self._receipt_error is not None:
                errors.insert(0,self._receipt_error)
                self._receipt_error=None
        if errors:
            raise errors[0]
        return results

    def close(self):
        with self._lock:
            self._closed=True
        try:
            self.flush()
        finally:
            if self._executor is not None:
                self._executor.shutdown(wait=True)

    def __enter__(self):
        return self

    def __exit__(self,*exception):
        self.close()

    def record_observation(self,operation,inputs,result,*,backend='python',metadata=None,parents=()):
        """Queue metadata-only native executions; tensor contents are never inspected here."""
        from .receipt import receipt
        if type(operation) is not str or not operation.strip() or type(backend) is not str or not backend.strip():
            raise ValueError('Observation operation/backend must be nonempty strings')
        if not isinstance(parents,(list,tuple)) or any(type(p) is not str or len(p)!=64 or any(c not in '0123456789abcdef' for c in p) for p in parents):
            raise ValueError('Observation parents must be SHA-256 content IDs')
        stack=[(inputs,0),(result,0),(metadata,0)]
        visited=0
        while stack:
            value,depth=stack.pop(); visited+=1
            if depth>64 or visited>1000000:
                raise ValueError('Observation JSON structure exceeds budget')
            if value is None or type(value) in (str,bool,int,float):
                continue
            if type(value) in (list,tuple):
                stack.extend((item,depth+1) for item in value)
            elif type(value) is dict and all(type(key) is str for key in value):
                stack.extend((item,depth+1) for item in value.values())
            else:
                raise TypeError('Observation values must be JSON metadata; native tensors must remain on their backend')
        snapshot=copy.deepcopy((inputs,result,metadata,tuple(parents)))
        def package():
            record=receipt(operation,snapshot[0],snapshot[1],backend=backend,
                           metadata=snapshot[2],parents=snapshot[3])
            if self._sink is not None:
                self._sink(copy.deepcopy(record))
            return record
        return self._submit_receipt(package)

    def execute_accelerated(self,operation,*,dispatcher=None,capture_values=False,require_cuda=True,**arguments):
        """Explicit approximate/native execution; the exact execute() path is unchanged."""
        if self._closed:
            raise RuntimeError('Calculation session is closed')
        if dispatcher is None:
            from ..backends.cuda_dispatcher import CudaDispatcher
            dispatcher=CudaDispatcher(require_cuda=require_cuda)
        return dispatcher.execute(operation,audit_session=self,capture_values=capture_values,**arguments)

    def bind(self,name,value,unit=ONE):
        Symbol(name)
        self._bindings[name]=value if isinstance(value,Quantity) else Quantity(value,unit)
        return self

    def execute(self,operation,**arguments):
        if self._closed:
            raise RuntimeError('Calculation session is closed')
        if operation not in AREAS:
            raise ValueError('Operacao nao suportada')
        if not REQUIRED[operation]<=arguments.keys() or set(arguments)-(REQUIRED[operation]|OPTIONAL.get(operation,set())):
            raise ValueError('Argumentos obrigatorios ausentes ou campos desconhecidos')
        if operation=='integrate' and ('start' in arguments)!=('end' in arguments):
            raise ValueError('Integral definida requer start e end')
        if operation=='statistics' and ('population_variance' in arguments)!=('radius' in arguments):
            raise ValueError('Intervalo requer variancia populacional conhecida e raio')
        if operation=='quadratic_optimize' and ('constraints' in arguments)!=('upper' in arguments):
            raise ValueError('Restricoes requerem limites upper')
        arguments=encode(arguments)
        request={'operation':operation,'arguments':arguments,'precision':self.precision.digits,
                 'bindings':{n:{'value':str(q.value),'unit':q.unit.to_data()} for n,q in sorted(self._bindings.items())}}
        request_json=canonical_json(request)
        if len(request_json)>100000:
            raise ValueError('Requisicao excede o limite')
        # Freeze mutable arguments before math; the request and execution see one snapshot.
        arguments=json.loads(request_json)['arguments']
        result=self._execute(operation,arguments)
        limitations='Dominio limitado declarado; evidencia computacional, sem prova formal ou validacao externa.'
        snapshot=encode(result)
        def package():
            calculation=Calculation(request_json,canonical_json(snapshot),limitations)
            # Cache the canonical body/hash once, on the packaging thread when enabled.
            if self.background_receipts or self._sink is not None:
                data=calculation.to_data()
                if self._sink is not None:
                    self._sink(data)
            return calculation
        if self.background_receipts:
            frozen=copy.deepcopy(snapshot)
            return PendingCalculation(frozen,self._submit_receipt(package))
        return package()

    def evaluate(self,source,values=None):
        return self.execute('evaluate',source=source,values=values or {})

    def _execute(self,operation,a):
        if operation in EXTENDED_OPERATIONS:
            from .catalog import execute
            return execute(operation,a)
        from ..math.linear_algebra import Matrix,solve_linear,lu_decomposition,orthogonal_basis,condition_number_inf
        from ..math.calculus import derivative,primitive,definite_integral,limit,series
        from ..symbolic import saturate,AssumptionSet
        if operation=='evaluate':
            bindings=dict(self._bindings)
            bindings.update({n:Quantity(v) for n,v in a.get('values',{}).items()})
            expression=parse_expr(a['source'])
            def symbols(node):
                from ..expression import Binary
                if isinstance(node,Symbol):
                    return {node.name}
                return symbols(node.left)|symbols(node.right) if isinstance(node,Binary) else set()
            names=symbols(expression)
            if not names<=bindings.keys():
                raise ValueError('Simbolo sem valor')
            semantic=SemanticExpression(expression,tuple((n,ScientificType(unit=bindings[n].unit)) for n in names))
            values={n:bindings[n].value*bindings[n].unit.scale for n in names}
            require_obligations(semantic.obligations,values)
            value=evaluate(expression,values)
            return {'value':str(value),'unit':semantic.result_type.unit.to_data(),'semantic_id':semantic.content_id,
                    'obligations':[o.to_data() for o in semantic.obligations],'approximation':self.precision.approximate(value)}
        if operation in {'differentiate','integrate','series','simplify'}:
            semantic=SemanticExpression.parse(a['source'])
            variable=a.get('variable','x')
            if operation=='differentiate':
                result=derivative(a['source'],variable)
                return {'expression':to_data(result.derivative),'required_nonzero':[to_data(v) for v in result.required_nonzero]}
            if operation=='integrate':
                if 'start' in a or 'end' in a:
                    return {'value':str(definite_integral(a['source'],rational(a['start']),rational(a['end']),variable))}
                return primitive(a['source'],variable).to_data()
            if operation=='series':
                result=series(a['source'],rational(a.get('center',0)),a.get('order',4),variable)
                return {'coefficients':encode(result.coefficients),'remainder_order':result.remainder_order,'polynomial':to_data(result.polynomial)}
            result=saturate(semantic.expression,node_limit=2000,iteration_limit=8,
                            assumptions=AssumptionSet.from_nonzero(*a.get('nonzero',[])))
            return result.to_data()
        if operation=='limit':
            SemanticExpression.parse(a['numerator'])
            SemanticExpression.parse(a['denominator'])
            return encode(limit(a['numerator'],a['denominator'],rational(a['point']),a.get('variable','x')))
        if operation in {'solve_linear','lu','condition'}:
            matrix=Matrix(tuple(tuple(rational(v) for v in row) for row in a['matrix']))
            if operation=='solve_linear':
                return encode(solve_linear(matrix,tuple(rational(v) for v in a['rhs'])))
            if operation=='lu':
                return encode(lu_decomposition(matrix))
            return {'condition_inf':str(condition_number_inf(matrix))}
        if operation=='orthogonal_basis':
            return encode(orthogonal_basis(a['vectors']))
        if operation=='factor':
            from ..math.polynomials.univariate import Polynomial
            from ..math.polynomials.factorization import factor_rational
            return encode(factor_rational(Polynomial(tuple(rational(v) for v in a['coefficients']))))
        if operation=='binomial':
            from ..math.combinatorics.enumerative import binomial
            if any(type(a[n]) is not int or not 0<=a[n]<=10000 for n in ('n','k')):
                raise ValueError('Combinatoria limitada a inteiros de 0 a 10000')
            return {'value':binomial(a['n'],a['k'])}
        if operation=='topological_sort':
            from ..math.graph_theory import topological_sort
            if len(a['vertices'])>1000 or len(a['edges'])>10000:
                raise ValueError('Grafo excede o limite')
            return {'order':list(topological_sort(frozenset(a['vertices']),frozenset(tuple(e) for e in a['edges'])))}
        if operation=='markov':
            from ..math.probability.markov import MarkovChain
            rows=a['transition'];n=len(rows)
            if not 1<=n<=16 or any(len(row)!=n for row in rows) or len(a['distribution'])!=n:
                raise ValueError('Cadeia incompativel')
            steps=a.get('steps',1)
            if type(steps) is not int or not 0<=steps<=1000:
                raise ValueError('Evolucao limitada a 1000 passos')
            names=tuple(str(i) for i in range(n))
            chain=MarkovChain(names,{(str(i),str(j)):rational(rows[i][j]) for i in range(n) for j in range(n)})
            distribution={str(i):rational(v) for i,v in enumerate(a['distribution'])}
            return {'distribution':encode(chain.evolve(distribution,steps))}
        if operation=='statistics':
            from ..math.statistics.descriptive import mean,variance
            values=tuple(rational(v) for v in a['values'])
            if not 1<=len(values)<=10000:
                raise ValueError('Amostra fora do limite')
            result={'mean':str(mean(values)),'variance':str(variance(values,sample=a.get('sample',False))),'count':len(values)}
            from ..math.statistics.inference import sign_test,mean_confidence_bound,exact_moving_average
            if 'median' in a:
                result['sign_test']=encode(sign_test(values,rational(a['median'])))
            if 'population_variance' in a:
                result['confidence_bound']=encode(mean_confidence_bound(values,rational(a['population_variance']),rational(a['radius'])))
            if 'window' in a:
                result['moving_average']=encode(exact_moving_average(values,a['window']))
            return result
        if operation=='approximate':
            return self.precision.approximate(a['value'])
        if operation=='geometry':
            from ..math.geometry.euclidean import Point2,orientation,squared_distance,polygon_twice_signed_area
            points=tuple(Point2(*(rational(v) for v in p)) for p in a['points'])
            if len(points)!=3:
                raise ValueError('Geometria requer tres pontos')
            return {'orientation':orientation(*points),'twice_signed_area':str(polygon_twice_signed_area(points)),
                    'squared_distance_ab':str(squared_distance(*points[:2]))}
        if operation=='conic':
            from ..math.geometry.conics import Conic
            conic=Conic(tuple(rational(v) for v in a['coefficients']))
            return {'classification':conic.classify()}
        if operation=='quadratic_optimize':
            from ..math.optimization.quadratic import minimize_quadratic
            matrix=Matrix(tuple(tuple(rational(v) for v in row) for row in a['hessian']))
            return encode(minimize_quadratic(matrix,tuple(rational(v) for v in a['linear']),
                tuple(tuple(rational(v) for v in row) for row in a.get('constraints',[])),
                tuple(rational(v) for v in a.get('upper',[])),rational(a.get('constant',0))))
        if operation=='optimize':
            from ..math.optimization.linear import Constraint2,maximize_2d
            if len(a.get('constraints',[]))>64:
                raise ValueError('Muitas restricoes')
            point,value=maximize_2d(tuple(rational(v) for v in a['objective']),
                tuple(Constraint2(*(rational(v) for v in row)) for row in a.get('constraints',[])),
                x_bounds=tuple(rational(v) for v in a['x_bounds']),y_bounds=tuple(rational(v) for v in a['y_bounds']))
            return {'point':encode(point),'value':str(value)}
        if operation=='ode_adaptive':
            from ..worlds.model_spec import ModelSpec
            from ..worlds.validation import simulate_adaptive
            model = ModelSpec(a['model'], tuple(a['initial']), a.get('rate', 1), a.get('duration', 1))
            options = {k: a[k] for k in ('atol', 'rtol', 'max_attempts', 'initial_step') if k in a}
            return simulate_adaptive(model, **options)
        if operation=='ode':
            from ..worlds import ModelSpec,simulate
            return simulate(ModelSpec(a['model'],tuple(a['initial']),a.get('rate',1),a.get('duration',1)),
                            steps=a.get('steps',100),method=a.get('method','rk4'))
        raise ValueError('Operacao nao implementada')

    @classmethod
    def replay_request(cls,request):
        from ..core.semantic_contracts import require_fields
        require_fields(request,{'operation','arguments','precision','bindings'})
        if not isinstance(request['bindings'],dict) or len(request['bindings'])>128:
            raise ValueError('Bindings de replay invalidos')
        session=cls(precision=request['precision'])
        for name,row in request['bindings'].items():
            require_fields(row,{'value','unit'})
            unit=row['unit']
            require_fields(unit,{'dimensions','scale'})
            session.bind(name,row['value'],Unit(tuple(unit['dimensions']),rational(unit['scale'])))
        return session.execute(request['operation'],**request['arguments'])
