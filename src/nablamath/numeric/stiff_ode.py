"""Version 1: scalar backward Euler with explicit Newton failures.

Fixed steps, analytic Jacobian, optional terminal event. Event times use linear
interpolation between step endpoints and are approximations, not root bounds.
"""
from dataclasses import dataclass
from math import isfinite
from typing import Callable
CONTRACT_VERSION = 1


def solve_stiff_system(expressions,variables,initial,*,duration=1.,method='Radau',rtol=1e-8,atol=1e-10,steps=100,events=()):
    """Adaptive vector BDF/Radau with generated Jacobian and event localization."""
    import numpy as np
    from scipy.integrate import solve_ivp
    from scipy.sparse import csr_matrix
    from ..math._structured import expression,sympy,numeric_array,names
    sp=sympy();variables=names(variables,16)
    if 't' in variables or len(expressions)!=len(variables) or len(initial)!=len(variables) or method not in {'Radau','BDF'} or type(steps) is not int or not 1<=steps<=10000 or not 0<duration<=100000 or not 0<atol<=rtol<1 or len(events)>16:raise ValueError('Invalid stiff-system contract')
    symbols=(sp.Symbol('t'),)+tuple(map(sp.Symbol,variables));functions=[expression(v,['t']+list(variables))[0] for v in expressions]
    jacobian=sp.Matrix(functions).jacobian(symbols[1:])
    def sub(t,y):return dict(zip(symbols,[t]+list(y)))
    def rhs(t,y):return np.array([float(f.subs(sub(t,y))) for f in functions])
    def jac(t,y):return csr_matrix(np.array(jacobian.subs(sub(t,y)),dtype=float))
    callbacks=[]
    for record in events:
        if set(record)-{'source','terminal','direction'} or 'source' not in record:raise ValueError('Closed event specification required')
        value=expression(record['source'],['t']+list(variables))[0]
        def event(t,y,value=value):return float(value.subs(sub(t,y)))
        event.terminal=bool(record.get('terminal',False));event.direction=float(record.get('direction',0))
        if event.direction not in (-1,0,1):raise ValueError('Event direction must be -1,0,1')
        callbacks.append(event)
    solution=solve_ivp(rhs,(0,duration),numeric_array(initial,ndim=1),method=method,jac=jac,t_eval=np.linspace(0,duration,steps+1),rtol=rtol,atol=atol,events=callbacks)
    if not solution.success or not np.isfinite(solution.y).all():raise ArithmeticError('Stiff integration failed: '+solution.message)
    return {'times':solution.t.tolist(),'values':solution.y.T.tolist(),'event_times':[v.tolist() for v in solution.t_events] if callbacks else [],
            'evaluations':solution.nfev,'jacobian_evaluations':solution.njev,'method':method,
            'scope':'Adaptive local-error-controlled floating point solution; event times are numerical roots, not certified bounds.'}


@dataclass(frozen=True)
class ImplicitSolution:
    times: tuple[float, ...]
    values: tuple[float, ...]
    event_time: float | None = None


def backward_euler(f: Callable[[float, float], float],
                   jacobian: Callable[[float, float], float], y0: float,
                   t0: float, t1: float, steps: int, *, tolerance: float = 1e-10,
                   max_iterations: int = 50,
                   event: Callable[[float, float], float] | None = None) -> ImplicitSolution:
    """Solve scalar implicit steps; reject nonfinite values or nonconvergence."""
    if type(steps) is not int or not 1 <= steps <= 1000000:
        raise ValueError("invalid step budget")
    if type(max_iterations) is not int or not 1 <= max_iterations <= 1000:
        raise ValueError("invalid Newton budget")
    if not all(isfinite(v) for v in (y0, t0, t1, tolerance)) or t1 <= t0 or tolerance <= 0:
        raise ValueError("invalid initial condition, times or tolerance")
    times, values = [t0], [y0]
    previous_event = event(t0, y0) if event else None
    if previous_event is not None and not isfinite(previous_event):
        raise ValueError("nonfinite event")
    if previous_event == 0:
        return ImplicitSolution(tuple(times), tuple(values), t0)
    h = (t1 - t0) / steps
    for k in range(1, steps + 1):
        t = t1 if k == steps else t0 + k * h
        if t <= times[-1]:
            raise ValueError("time grid is not representable at this floating precision")
        old, y = values[-1], values[-1]
        for iteration in range(max_iterations + 1):
            derivative = f(t, y)
            if not isfinite(derivative):
                raise ValueError("nonfinite derivative")
            residual = y - old - h * derivative
            if abs(residual) <= tolerance * max(1, abs(y)):
                break
            if iteration == max_iterations:
                raise ArithmeticError("Newton iteration budget exhausted")
            slope = 1 - h * jacobian(t, y)
            if not isfinite(slope) or slope == 0:
                raise ArithmeticError("singular or nonfinite implicit Jacobian")
            y -= residual / slope
            if not isfinite(y):
                raise ArithmeticError("nonfinite Newton iterate")
        else:
            raise ArithmeticError("Newton iteration budget exhausted")
        current_event = event(t, y) if event else None
        if current_event is not None:
            if not isfinite(current_event):
                raise ValueError("nonfinite event")
            if current_event == 0 or (current_event < 0) != (previous_event < 0):
                weight = abs(previous_event) / (abs(previous_event) + abs(current_event))
                root = times[-1] + h * weight
                root_y = old + weight * (y - old)
                return ImplicitSolution(tuple(times + [root]), tuple(values + [root_y]), root)
        times.append(t)
        values.append(y)
        previous_event = current_event
    return ImplicitSolution(tuple(times), tuple(values))
