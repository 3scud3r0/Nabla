"""Exact forward-mode value, gradient and Hessian for closed symbolic models.

Derivatives are evaluated only where every original expression is defined.
These diagnostics concern a fitted expression, not identification of a real
causal mechanism. No automatic differentiation package or eval is required.
"""
from dataclasses import dataclass
from fractions import Fraction
from ..core.semantic_ir import fingerprint
from ._bounded import bounded_tuple
from .symbolic_beam import Term,SymbolicModel,_number
from .sparse_symbolic import SparseModel


@dataclass(frozen=True)
class Differential:
    value: Fraction
    gradient: tuple
    hessian: tuple

    def __post_init__(self):
        value=_number(self.value)
        gradient=tuple(_number(v) for v in bounded_tuple(self.gradient,8,label='gradient entries'))
        rows=bounded_tuple(self.hessian,8,label='Hessian rows')
        matrix=tuple(tuple(_number(v) for v in bounded_tuple(row,8,label='Hessian columns')) for row in rows)
        n=len(gradient)
        if not n or len(matrix)!=n or any(len(row)!=n for row in matrix):raise ValueError('Differential dimensions disagree')
        if any(matrix[i][j]!=matrix[j][i] for i in range(n) for j in range(n)):
            raise ValueError('Exact smooth Hessian must be symmetric')
        object.__setattr__(self,'value',value);object.__setattr__(self,'gradient',gradient);object.__setattr__(self,'hessian',matrix)

    def to_data(self):
        return {'value':str(self.value),'gradient':[str(v) for v in self.gradient],
                'hessian':[[str(v) for v in row] for row in self.hessian]}

    def add(self,other):
        n=len(self.gradient)
        if len(other.gradient)!=n:raise ValueError('Differential schema mismatch')
        return Differential(self.value+other.value,tuple(a+b for a,b in zip(self.gradient,other.gradient)),
                            tuple(tuple(self.hessian[i][j]+other.hessian[i][j] for j in range(n)) for i in range(n)))

    def scale(self,factor):
        factor=_number(factor)
        return Differential(factor*self.value,tuple(factor*v for v in self.gradient),
                            tuple(tuple(factor*v for v in row) for row in self.hessian))

    def multiply(self,other):
        n=len(self.gradient)
        if len(other.gradient)!=n:raise ValueError('Differential schema mismatch')
        gradient=tuple(self.gradient[i]*other.value+self.value*other.gradient[i] for i in range(n))
        hessian=tuple(tuple(self.hessian[i][j]*other.value+self.gradient[i]*other.gradient[j]+
                            self.gradient[j]*other.gradient[i]+self.value*other.hessian[i][j]
                            for j in range(n)) for i in range(n))
        return Differential(self.value*other.value,gradient,hessian)

    def reciprocal(self):
        if not self.value:raise ValueError('Reciprocal derivative excludes zero')
        n=len(self.gradient); value=1/self.value
        gradient=tuple(-v/self.value**2 for v in self.gradient)
        hessian=tuple(tuple(2*self.gradient[i]*self.gradient[j]/self.value**3-self.hessian[i][j]/self.value**2
                            for j in range(n)) for i in range(n))
        return Differential(value,gradient,hessian)


def _constant(value,dimension):
    return Differential(value,(Fraction(0),)*dimension,tuple((Fraction(0),)*dimension for _ in range(dimension)))


def term_differential(term,features):
    if not isinstance(term,Term):raise ValueError('Typed symbolic term required')
    features=tuple(_number(x) for x in bounded_tuple(features,8,label='differential features'))
    if not features:raise ValueError('Nonempty feature schema required')
    n=len(features)
    def visit(node):
        if node.operation=='one':return _constant(Fraction(1),n)
        if node.operation=='variable':
            if node.variable>=n:raise ValueError('Differential variable outside feature schema')
            gradient=tuple(Fraction(i==node.variable) for i in range(n))
            return Differential(features[node.variable],gradient,tuple((Fraction(0),)*n for _ in range(n)))
        values=[visit(a) for a in node.arguments]
        if node.operation=='negate':return values[0].scale(-1)
        if node.operation=='reciprocal':return values[0].reciprocal()
        if node.operation=='add':return values[0].add(values[1])
        return values[0].multiply(values[1])
    return visit(term)


def model_differential(model,features):
    features=tuple(_number(x) for x in bounded_tuple(features,8,label='differential features'))
    if not features:raise ValueError('Nonempty feature schema required')
    if isinstance(model,SymbolicModel):
        return term_differential(model.term,features).scale(model.slope).add(_constant(model.intercept,len(features)))
    if isinstance(model,SparseModel):
        result=_constant(model.intercept,len(features))
        for term,weight in zip(model.terms,model.weights):
            result=result.add(term_differential(term,features).scale(weight))
        return result
    raise ValueError('Known declarative model required')


def differential_report(model,points):
    if not isinstance(model,(SymbolicModel,SparseModel)):raise ValueError('Known declarative symbolic model required')
    points=bounded_tuple(points,128,label='differential points')
    if not points:raise ValueError('Nonempty differential probe required')
    rows=[]; dimension=None
    for point in points:
        values=tuple(_number(x) for x in bounded_tuple(point,8,label='differential features'))
        if not values or (dimension is not None and len(values)!=dimension):raise ValueError('Inconsistent probe feature schema')
        dimension=len(values)
        try:
            result=model_differential(model,values)
            row={'point':[str(x) for x in values],'status':'differentiated',**result.to_data()}
        except ValueError as exc:
            row={'point':[str(x) for x in values],'status':'domain_or_arithmetic_failure','reason':str(exc)}
        rows.append(row)
    data={'version':'symbolic-exact-differentials-v1','model_id':model.content_id,'dimension':dimension,'points':rows,
          'failures':sum(r['status']!='differentiated' for r in rows),
          'scope':'exact derivatives of fitted expression on stated domain; no causal or physical identification'}
    return {**data,'differential_id':fingerprint(data)}


def replay_differentials(report,model):
    try:return differential_report(model,[r['point'] for r in report['points']])==report
    except (ValueError,TypeError,KeyError):return False
