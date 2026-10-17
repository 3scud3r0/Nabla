"""Exact Gaussian-rational holomorphic polynomial maps and Jacobians (32)."""
from dataclasses import dataclass
from fractions import Fraction
from itertools import permutations
from ._polynomial import parse_polynomial
from ._area_utils import scalar,rref,calculate as _calculate


@dataclass(frozen=True)
class Gaussian:
    real: Fraction
    imag: Fraction = Fraction(0)

    @classmethod
    def of(cls,value):
        if isinstance(value,cls):return value
        if isinstance(value,(list,tuple)) and len(value)==2:return cls(scalar(value[0]),scalar(value[1]))
        return cls(scalar(value))

    def __bool__(self):return bool(self.real or self.imag)
    def __add__(self,other):
        other = self.of(other);return Gaussian(self.real+other.real,self.imag+other.imag)
    __radd__ = __add__
    def __neg__(self):return Gaussian(-self.real,-self.imag)
    def __sub__(self,other):return self+-self.of(other)
    def __mul__(self,other):
        other = self.of(other)
        return Gaussian(self.real*other.real-self.imag*other.imag,self.real*other.imag+self.imag*other.real)
    __rmul__ = __mul__
    def __truediv__(self,other):
        other = self.of(other);den = other.real**2+other.imag**2
        if not den:raise ZeroDivisionError('Zero Gaussian rational divisor')
        return self*Gaussian(other.real/den,-other.imag/den)
    def __pow__(self,exponent):
        result = Gaussian(Fraction(1))
        for _ in range(exponent):result = result*self
        return result
    def data(self):return [str(self.real),str(self.imag)]


def several_complex_variables(sources, variables, point):
    if not isinstance(sources,list) or not 1<=len(sources)<=4:
        raise ValueError('Require 1–4 holomorphic polynomial components')
    polynomials = [parse_polynomial(source,variables) for source in sources]
    if not isinstance(point,list) or len(point)!=len(variables):raise ValueError('Point and variables differ')
    point = [Gaussian.of(value) for value in point]
    values = [Gaussian.of(p.evaluate(point)) for p in polynomials]
    jacobian = [[Gaussian.of(p.derivative(j).evaluate(point)) for j in range(len(variables))] for p in polynomials]
    rank = len(rref(jacobian)[1]);determinant = None
    if len(sources)==len(variables):
        n = len(variables);determinant = Gaussian(Fraction(0))
        for perm in permutations(range(n)):
            term = Gaussian(Fraction((-1)**sum(perm[i]>perm[j] for i in range(n) for j in range(i+1,n))))
            for i,j in enumerate(perm):term = term*jacobian[i][j]
            determinant += term
    return {'values':[v.data() for v in values],'jacobian':[[v.data() for v in row] for row in jacobian],
            'complex_rank':rank,'jacobian_determinant':determinant.data() if determinant is not None else None,
            'locally_biholomorphic':bool(determinant) if determinant is not None else None,
            'scope':'Holomorphic rational-coefficient polynomial maps; exact local inverse criterion, no global invertibility claim.'}


def calculate(**arguments):return _calculate('several_complex_variables',**arguments)


def holomorphic_jet(sources,variables,point,order=2):
    from itertools import product
    from ..math._structured import expression,sympy
    sp=sympy()
    if type(order) is not int or not 0<=order<=6 or not 1<=len(variables)<=4 or len(point)!=len(variables) or not 1<=len(sources)<=4:raise ValueError('Holomorphic jet budget exceeded')
    values=[expression(v,variables)[0] for v in sources];symbols=tuple(map(sp.Symbol,variables))
    coordinates=[]
    for raw in point:
        if isinstance(raw,list) and len(raw)==2:coordinates.append(sp.Rational(str(raw[0]))+sp.I*sp.Rational(str(raw[1])))
        else:coordinates.append(sp.Rational(str(raw)))
    subs=dict(zip(symbols,coordinates));result=[]
    for value in values:
        derivatives={}
        for powers in product(range(order+1),repeat=len(variables)):
            if sum(powers)>order:continue
            derivative=value
            for s,n in zip(symbols,powers):derivative=sp.diff(derivative,s,n)
            coefficient=sp.simplify(derivative.subs(subs)/sp.prod(sp.factorial(n) for n in powers))
            if coefficient.has(sp.zoo,sp.oo,-sp.oo,sp.nan):raise ValueError('Point outside the declared analytic expression domain')
            derivatives[','.join(map(str,powers))]=str(coefficient)
        result.append(derivatives)
    return {'taylor_coefficients':result,'order':order,'scope':'Local expression jets on principal branches, conditional on holomorphy near the supplied point; no convergence-radius certificate.'}
