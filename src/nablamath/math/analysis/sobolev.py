"""Exact polynomial H^k interval norms, traces and Poincare certificates."""
from .._structured import expression,sympy
from ...ops._area_utils import scalar


def polynomial_norm(source,lower=0,upper=1,order=1,variable='x'):
    sp=sympy();f,(x,)=expression(source,[variable],functions=False);p=sp.Poly(f,x,domain=sp.QQ)
    if p.degree()>32 or type(order) is not int or not 0<=order<=8:raise ValueError('Sobolev polynomial/order budget exceeded')
    a,b=(sp.Rational(str(scalar(v))) for v in (lower,upper))
    if a>=b:raise ValueError('Increasing interval required')
    energies=[sp.integrate(sp.diff(f,x,j)**2,(x,a,b)) for j in range(order+1)]
    zero_trace=f.subs(x,a)==0 and f.subs(x,b)==0
    return {'norm_squared':str(sum(energies)),'derivative_energies':list(map(str,energies)),
            'endpoint_traces':[str(f.subs(x,a)),str(f.subs(x,b))],
            'zero_trace':bool(zero_trace),'poincare_constant':str((b-a)/sp.pi) if zero_trace and order>=1 else None,
            'scope':'Polynomial representative in H^k of a finite interval; exact squared norm, symbolic square root.'}


def truncation_bound(coefficients,tail_l2_bound,derivative_weights):
    from fractions import Fraction
    c=[scalar(v) for v in coefficients];w=[scalar(v) for v in derivative_weights];tail=scalar(tail_l2_bound)
    if len(c)!=len(w) or len(c)>4096 or any(v<0 for v in w) or tail<0:raise ValueError('Invalid orthogonal truncation data')
    return {'resolved_norm_squared':str(sum((a*a*b for a,b in zip(c,w)),Fraction(0))),
            'tail_norm_upper_bound':str(tail),'conditional_on':'Caller-supplied orthogonality, weights and certified tail estimate'}
