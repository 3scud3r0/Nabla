"""Immutable problems for all eight inverse families; witnesses never enter task IDs."""
from dataclasses import dataclass
import json
from ..core.semantic_ir import ScientificTask,PolynomialSpec,canonical_json,fingerprint,rational,SemanticExpression
from ..schema.expression import from_data

FAMILIES=('polynomial_integral','factored_polynomial','linear_system','prescribed_spectrum',
          'convex_quadratic','stationary_markov','polynomial_identity','counterexample')
FIELDS={'polynomial_integral':{'coefficients'},'factored_polynomial':{'coefficients'},
        'linear_system':{'matrix','rhs'},'prescribed_spectrum':{'matrix'},
        'convex_quadratic':{'matrix','linear','constant'},'stationary_markov':{'transition'},
        'polynomial_identity':{'left','right','variables'},'counterexample':{'left','right','variables','radius'}}


@dataclass(frozen=True,init=False)
class TaskSpec:
    family: str
    problem_json: str
    size: int
    schema_version: int=1

    def __init__(self,family,problem,size=3,schema_version=1):
        if family not in FAMILIES or type(size) is not int or not 1<=size<=8 or type(schema_version) is not int or schema_version!=1:
            raise ValueError('Familia, tamanho ou versao invalida')
        if not isinstance(problem,dict) or set(problem)!=FIELDS[family]:
            raise ValueError('Campos do problema invalidos')
        serialized=canonical_json(problem)
        if len(serialized)>32000:
            raise ValueError('Problema excede 32 KB')
        data=json.loads(serialized)
        def vector(values,n):
            if not isinstance(values,list) or len(values)!=n:
                raise ValueError('Dimensao de vetor invalida')
            return [str(rational(v)) for v in values]
        def matrix(rows):
            if not isinstance(rows,list) or len(rows)!=size:
                raise ValueError('Dimensao de matriz invalida')
            return [vector(row,size) for row in rows]
        if family in {'polynomial_integral','factored_polynomial'}:
            expected=size if family=='polynomial_integral' else size+1
            values=vector(data['coefficients'],expected)
            coefficients=PolynomialSpec(tuple(values))
            if len(coefficients.coefficients)!=expected:
                raise ValueError('Grau declarado diverge dos coeficientes')
            data['coefficients']=coefficients.to_data()
        if 'matrix' in data:
            data['matrix']=matrix(data['matrix'])
        if family=='linear_system':
            data['rhs']=vector(data['rhs'],size)
        if family=='convex_quadratic':
            data['linear']=vector(data['linear'],size)
            data['constant']=str(rational(data['constant']))
        if family=='stationary_markov':
            data['transition']=matrix(data['transition'])
            rows=[[rational(v) for v in row] for row in data['transition']]
            if any(any(v<0 for v in row) or sum(row)!=1 for row in rows):
                raise ValueError('Transicao nao estocastica')
        if family in {'polynomial_identity','counterexample'}:
            variables=data['variables']
            if not isinstance(variables,list) or not 1<=len(variables)<=3 or len(set(variables))!=len(variables):
                raise ValueError('Variaveis invalidas')
            from ..expression import Symbol
            from ..math.algebra.groebner import polynomial_from_expr
            for v in variables:
                Symbol(v)
            for side in ('left','right'):
                expr=from_data(data[side])
                SemanticExpression(expr)
                polynomial=polynomial_from_expr(expr,tuple(variables))
                if any(sum(m)>16 for m,_ in polynomial.terms) or len(polynomial.terms)>128:
                    raise ValueError('Identidade excede limites polinomiais')
            data['variables']=sorted(variables)
            if family=='counterexample' and (type(data['radius']) is not int or not 1<=data['radius']<=16):
                raise ValueError('Dominio do contraexemplo invalido')
        object.__setattr__(self,'family',family)
        object.__setattr__(self,'problem_json',canonical_json(data))
        object.__setattr__(self,'size',size)
        object.__setattr__(self,'schema_version',1)

    @property
    def problem(self):
        return json.loads(self.problem_json)

    def to_data(self):
        return {'schema_version':1,'family':self.family,'size':self.size,'domain':'rational','problem':self.problem}

    @property
    def content_id(self):
        return fingerprint(self.to_data())

    @property
    def family_key(self):
        return f'{self.family}:size={self.size}'

    def legacy(self):
        if self.family=='polynomial_integral':
            return ScientificTask(self.family,coefficients=tuple(self.problem['coefficients']))
        if self.family=='linear_system':
            p=self.problem
            return ScientificTask(self.family,matrix=tuple(tuple(r) for r in p['matrix']),rhs=tuple(p['rhs']))
        raise ValueError('Familia sem contrato legado')

    @classmethod
    def from_data(cls,data):
        if not isinstance(data,dict) or set(data)!={'schema_version','family','size','domain','problem'} or data['domain']!='rational':
            raise ValueError('Contrato Forge invalido')
        return cls(data['family'],data['problem'],data['size'],data['schema_version'])


@dataclass(frozen=True)
class GeneratedProblem:
    task: TaskSpec
    witness_json: str
    seed: int
    generator_version: str='inverse-v2'

    @property
    def witness(self):
        return json.loads(self.witness_json)
