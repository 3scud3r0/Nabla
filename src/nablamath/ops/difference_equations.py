"""Exact affine constant-coefficient recurrences, with bounded growth (39)."""
from collections import deque
from ._area_utils import vector,scalar,calculate as _calculate


def difference_equations(coefficients, initial, index, *, forcing=0):
    coefficients,initial = vector(coefficients,maximum=32),vector(initial,maximum=32)
    if len(coefficients)!=len(initial) or type(index) is not int or not 0<=index<=10000:
        raise ValueError('Recurrence order/initial values differ or index exceeds 10000')
    forcing = scalar(forcing);state = deque(initial,maxlen=len(initial))
    for _ in range(len(initial),index+1):
        value = sum(a*b for a,b in zip(coefficients,reversed(state)))+forcing
        if max(value.numerator.bit_length(),value.denominator.bit_length())>16384:
            raise ValueError('Recurrence exceeds its 16384-bit arithmetic budget')
        state.append(value)
    return {'index':index,'value':initial[index] if index<len(initial) else state[-1],
            'last_state':list(state) if index>=len(initial) else initial[:index+1],
            'order':len(initial),'arithmetic':'exact_rational',
            'convention':'a[n] = sum(c[j]*a[n-1-j]) + forcing'}


def calculate(**arguments):return _calculate('difference_equations',**arguments)


def variable_recurrence(coefficients,initial,forcing=0,variable='n'):
    from ..math._structured import expression,sympy
    sp=sympy();initial=vector(initial,maximum=32)
    if not isinstance(coefficients,list) or not 2<=len(coefficients)<=33:raise ValueError('One coefficient for each shift required')
    n=sp.Symbol(variable,integer=True);polynomials=[]
    for raw in coefficients:
        p,(symbol,)=expression(raw,[variable],functions=False);p=p.subs(symbol,n);sp.Poly(p,n);polynomials.append(p)
    force,(symbol,)=expression(forcing,[variable],functions=False);force=force.subs(symbol,n)
    if len(initial)!=len(polynomials)-1:raise ValueError('Initial state differs from recurrence order')
    y=sp.Function('y');equation=sum(p*y(n+i) for i,p in enumerate(polynomials))-force
    solution=sp.rsolve(equation,y(n),{y(i):sp.Rational(str(v)) for i,v in enumerate(initial)})
    return {'solution':str(solution) if solution is not None else None,'solved':solution is not None,
            'equation':str(equation),'scope':'Linear polynomial-coefficient recurrence; unsolved cases remain explicit.'}


def discrete_system(expressions,variables,initial,steps):
    from ..math._structured import expression,sympy
    import numpy as np
    if len(expressions)!=len(variables) or len(initial)!=len(variables) or type(steps) is not int or not 0<=steps<=10000:raise ValueError('Invalid discrete system dimensions')
    funcs=[expression(f,variables)[0] for f in expressions];symbols=tuple(map(sympy().Symbol,variables));state=[float(v) for v in initial];trajectory=[state]
    for _ in range(steps):
        substitution=dict(zip(symbols,state));state=[float(f.subs(substitution)) for f in funcs]
        if not all(np.isfinite(v) and abs(v)<1e100 for v in state):raise ArithmeticError('Discrete trajectory escaped the numerical budget')
        trajectory.append(state)
    jacobian=sympy().Matrix(funcs).jacobian(symbols).subs(dict(zip(symbols,state)))
    eig=np.linalg.eigvals(np.array(jacobian,dtype=float))
    return {'trajectory':trajectory,'jacobian_final':[[float(v) for v in row] for row in jacobian.tolist()],
            'spectral_radius_final':float(max(abs(v) for v in eig)),
            'scope':'Finite numerical orbit; Jacobian stability diagnostic applies to a fixed point only.'}
