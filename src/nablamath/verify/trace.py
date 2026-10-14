"""Independent checks for every inverse family and portable replayable trace receipts."""
from dataclasses import dataclass
from fractions import Fraction
from itertools import product
import json
import math

from ..core.semantic_ir import canonical_json,fingerprint,rational,PolynomialSpec
from ..expression import evaluate
from ..schema.expression import from_data
from ..forge.task_spec import TaskSpec
from ..math.linear_algebra import Matrix
from .certificate import verify as verify_legacy

VERIFIER_VERSION='forge-exact-v2'


@dataclass(frozen=True)
class TaskVerification:
    valid: bool
    method: str
    checks: tuple[str,...]
    errors: tuple[str,...]=()
    formal_proof: bool=False

    def to_data(self):
        return {'valid':self.valid,'method':self.method,'checks':list(self.checks),'errors':list(self.errors),
                'formal_proof':False,'verifier_version':VERIFIER_VERSION}


def verify_candidate(task: TaskSpec,candidate) -> TaskVerification:
    checks=[]
    method=task.family
    def check(condition,description):
        checks.append(description)
        if not condition:
            raise ValueError(description)
    def values(row,n):
        check(isinstance(row,list) and len(row)==n,'candidate_dimension')
        return tuple(rational(v) for v in row)
    try:
        p=task.problem;n=task.size
        if not isinstance(candidate,dict):
            raise ValueError('candidate_not_object')
        if task.family in {'linear_system','polynomial_integral'}:
            key='solution' if task.family=='linear_system' else 'coefficients'
            row=values(candidate[key],n if key=='solution' else n+1)
            report=verify_legacy(task.legacy(),row)
            check(report.valid,report.method)
        elif task.family=='factored_polynomial':
            roots=values(candidate['roots'],n)
            polynomial=PolynomialSpec(tuple(p['coefficients']))
            # n+1 exact evaluations certify equality of polynomials of degree n.
            for x in range(n+1):
                expected=rational(p['coefficients'][-1])
                for root in roots:
                    expected*=x-root
                check(polynomial.evaluate(x)==expected,f'polynomial_identity_at:{x}')
        elif task.family=='prescribed_spectrum':
            eigenvalues=values(candidate['eigenvalues'],n)
            vectors=candidate['eigenvectors']
            check(isinstance(vectors,list) and len(vectors)==n,'basis_dimension')
            v=Matrix(tuple(values(row,n) for row in vectors))
            a=Matrix(tuple(tuple(rational(x) for x in row) for row in p['matrix']))
            check(v.determinant()!=0,'basis_invertible')
            left=a@v
            check(all(left.rows[i][j]==v.rows[i][j]*eigenvalues[j] for i in range(n) for j in range(n)),
                  'all_eigenvector_residuals_zero')
        elif task.family=='convex_quadratic':
            x=values(candidate['solution'],n)
            a=[[rational(v) for v in row] for row in p['matrix']]
            b=tuple(rational(v) for v in p['linear'])
            check(all(a[i][j]==a[j][i] for i in range(n) for j in range(n)),'hessian_symmetric')
            for k in range(1,n+1):
                check(Matrix(tuple(tuple(row[:k]) for row in a[:k])).determinant()>0,f'sylvester_minor:{k}')
            check(all(sum(v*y for v,y in zip(row,x))+target==0 for row,target in zip(a,b)),'stationarity')
        elif task.family=='stationary_markov':
            stationary=values(candidate['stationary'],n)
            transition=[[rational(v) for v in row] for row in p['transition']]
            check(all(v>0 for row in transition for v in row),'strict_positive_transition_unique_stationary')
            check(all(v>=0 for v in stationary) and sum(stationary)==1,'probability_simplex')
            check(all(sum(stationary[i]*transition[i][j] for i in range(n))==stationary[j] for j in range(n)),'stationary_residual')
        elif task.family=='polynomial_identity':
            from ..math.algebra.groebner import polynomial_from_expr
            expressions=[from_data(p['left']),from_data(p['right']),from_data(candidate['expression'])]
            polynomials=[polynomial_from_expr(expr,tuple(p['variables'])) for expr in expressions]
            degrees=[max((m[j] for poly in polynomials for m,_ in poly.terms),default=0) for j in range(len(p['variables']))]
            if any(d>16 for d in degrees) or math.prod(d+1 for d in degrees)>50000:
                raise ValueError('verification_grid_budget')
            for point in product(*(range(d+1) for d in degrees)):
                mapping={name:Fraction(value) for name,value in zip(p['variables'],point)}
                evaluated=[evaluate(expr,mapping) for expr in expressions]
                check(evaluated[0]==evaluated[1]==evaluated[2],'degree_bounded_grid:'+','.join(map(str,point)))
        elif task.family=='counterexample':
            assignment=candidate['assignment']
            check(isinstance(assignment,dict) and set(assignment)==set(p['variables']),'assignment_variables')
            mapping={name:rational(value) for name,value in assignment.items()}
            check(all(v.denominator==1 and abs(v)<=p['radius'] for v in mapping.values()),'integer_domain')
            check(evaluate(from_data(p['left']),mapping)!=evaluate(from_data(p['right']),mapping),'exact_inequality')
        else:
            raise ValueError('unsupported_family')
        return TaskVerification(True,method,tuple(checks))
    except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
        return TaskVerification(False,method,tuple(checks),(str(exc),))


@dataclass(frozen=True)
class VerificationTrace:
    payload_json: str

    def to_data(self):
        payload=json.loads(self.payload_json)
        return {**payload,'trace_id':fingerprint(payload)}

    def replay(self):
        data=json.loads(self.payload_json)
        task=TaskSpec.from_data(data['task'])
        return data['task_id']==task.content_id and data['verification']==verify_candidate(task,data['candidate']).to_data()

    @classmethod
    def from_data(cls,data):
        if not isinstance(data,dict) or set(data)!={'schema_version','task','task_id','candidate','verification','trace_id'}:
            raise ValueError('Contrato de rastro invalido')
        row=dict(data);digest=row.pop('trace_id')
        if row['schema_version']!=1 or digest!=fingerprint(row):
            raise ValueError('Hash ou versao do rastro invalido')
        trace=cls(canonical_json(row))
        if not trace.replay():
            raise ValueError('Reexecucao do rastro divergiu')
        return trace


def build_trace(task,candidate):
    payload={'schema_version':1,'task':task.to_data(),'task_id':task.content_id,'candidate':candidate,
             'verification':verify_candidate(task,candidate).to_data()}
    return VerificationTrace(canonical_json(payload))
