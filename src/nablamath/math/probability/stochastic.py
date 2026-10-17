"""Reproducible Brownian paths and Euler–Maruyama Itô SDE integration."""

from __future__ import annotations
from dataclasses import dataclass
import math
import random
from typing import Callable


@dataclass(frozen=True)
class StochasticPath:
    times: tuple[float, ...]
    values: tuple[float, ...]
    brownian: tuple[float, ...]
    seed: int


def euler_maruyama(initial: float, duration: float, steps: int,
                    drift: Callable[[float, float], float],
                    diffusion: Callable[[float, float], float], *, seed: int = 0) -> StochasticPath:
    if not math.isfinite(initial) or not math.isfinite(duration) or duration <= 0:
        raise ValueError("Estado e duração inválidos")
    if type(steps) is not int or not 1 <= steps <= 10_000_000:
        raise ValueError("steps fora do orçamento")
    generator, delta = random.Random(seed), duration / steps
    times, values, brownian = [0.0], [initial], [0.0]
    for index in range(steps):
        increment = math.sqrt(delta) * generator.gauss(0.0, 1.0)
        time, value = times[-1], values[-1]
        next_value = value + float(drift(time, value)) * delta + float(diffusion(time, value)) * increment
        if not math.isfinite(next_value):
            raise ArithmeticError(f"SDE produziu estado não finito no passo {index + 1}")
        times.append((index + 1) * delta)
        values.append(next_value)
        brownian.append(brownian[-1] + increment)
    return StochasticPath(tuple(times), tuple(values), tuple(brownian), seed)


def brownian_motion(duration: float, steps: int, *, seed: int = 0) -> StochasticPath:
    return euler_maruyama(0.0, duration, steps, lambda _t, _x: 0.0,
                          lambda _t, _x: 1.0, seed=seed)


__all__ = ["StochasticPath", "brownian_motion", "euler_maruyama"]
def sde_system(drift,diffusion,variables,initial,*,duration=1.,steps=100,seed=0,method='euler',jump_rate=0.,jump=None,increments=None):
    """Vector Euler–Maruyama or diagonal Milstein; optional compound Poisson jumps."""
    import numpy as np
    from .._structured import expression,sympy,numeric_array
    sp=sympy();n=len(variables)
    if not 1<=n<=8 or 't' in variables or len(drift)!=n or len(diffusion)!=n or len(initial)!=n or type(steps) is not int or not 1<=steps<=100000 or not 0<duration<=1e5 or type(seed) is not int or not 0<=seed<2**64 or method not in {'euler','milstein'}:raise ValueError('Invalid SDE dimensions/budget')
    m=len(diffusion[0])
    if not 1<=m<=8 or any(len(row)!=m for row in diffusion):raise ValueError('Diffusion matrix is ragged')
    names=['t']+list(variables);symbols=(sp.Symbol('t'),)+tuple(map(sp.Symbol,variables));a=[expression(v,names)[0] for v in drift];b=[[expression(v,names)[0] for v in row] for row in diffusion]
    if method=='milstein' and (m!=n or any(b[i][j]!=0 for i in range(n) for j in range(m) if i!=j) or any(sp.diff(b[i][i],symbols[j+1])!=0 for i in range(n) for j in range(n) if i!=j)):raise ValueError('Milstein profile requires independent scalar diagonal diffusions')
    if not np.isfinite(jump_rate) or not 0<=jump_rate<=1e4:raise ValueError('Invalid jump intensity')
    jump=np.zeros(n) if jump is None else numeric_array(jump,ndim=1,maximum=8)
    if len(jump)!=n:raise ValueError('Jump-vector dimension mismatch')
    rng=np.random.default_rng(seed);h=duration/steps
    dw=rng.normal(0,np.sqrt(h),(steps,m)) if increments is None else numeric_array(increments,ndim=2,maximum=800000)
    if dw.shape!=(steps,m):raise ValueError('Brownian increment shape mismatch')
    state=numeric_array(initial,ndim=1,maximum=8);trajectory=[state.tolist()]
    for k in range(steps):
        sub=dict(zip(symbols,[k*h]+list(state)));av=np.array([float(v.subs(sub)) for v in a]);bv=np.array([[float(v.subs(sub)) for v in row] for row in b]);new=state+av*h+bv@dw[k]
        if method=='milstein':
            new+=np.array([.5*bv[i,i]*float(sp.diff(b[i][i],symbols[i+1]).subs(sub))*(dw[k,i]**2-h) for i in range(n)])
        if jump_rate:new+=jump*rng.poisson(jump_rate*h)
        if not np.isfinite(new).all() or np.max(abs(new))>1e100:raise ArithmeticError('SDE path escaped its numerical budget')
        state=new;trajectory.append(state.tolist())
    return {'trajectory':trajectory,'steps':steps,'seed':seed,'method':method,'scope':'One seeded numerical Ito path; no inferred pathwise or distributional accuracy.'}


def sde_refinement(drift,diffusion,variables,initial,*,duration=1.,steps=32,seed=0,method='euler'):
    import numpy as np
    if type(steps) is not int or not 1<=steps<=50000:raise ValueError('Refinement budget exceeded')
    rng=np.random.default_rng(seed);m=len(diffusion[0]);fine=rng.normal(0,np.sqrt(duration/(2*steps)),(2*steps,m));coarse=fine.reshape(steps,2,m).sum(axis=1)
    common=dict(drift=drift,diffusion=diffusion,variables=variables,initial=initial,duration=duration,seed=seed,method=method)
    a=sde_system(**common,steps=steps,increments=coarse.tolist());b=sde_system(**common,steps=2*steps,increments=fine.tolist())
    return {'coarse_final':a['trajectory'][-1],'fine_final':b['trajectory'][-1],
            'coupled_final_difference':float(np.linalg.norm(np.array(a['trajectory'][-1])-b['trajectory'][-1])),
            'scope':'Coupled Brownian refinement diagnostic for one sample; not an estimate of expected strong/weak error without an ensemble.'}


def adaptive_sde(drift,diffusion,variables,initial,*,duration=1.,tolerance=1e-3,max_steps=1024,seed=0,method='euler'):
    """Nested Brownian-grid step doubling, using one fixed finest-grid path."""
    import numpy as np
    if type(max_steps) is not int or not 8<=max_steps<=65536 or max_steps&(max_steps-1) or not np.isfinite([duration,tolerance]).all() or min(duration,tolerance)<=0:raise ValueError('Power-of-two SDE grid and positive tolerance required')
    m=len(diffusion[0]);rng=np.random.default_rng(seed);finest=rng.normal(0,np.sqrt(duration/max_steps),(max_steps,m));common=dict(drift=drift,diffusion=diffusion,variables=variables,initial=initial,duration=duration,seed=seed,method=method)
    steps=4;previous=None;difference=None
    while steps<=max_steps:
        increments=finest.reshape(steps,max_steps//steps,m).sum(axis=1)
        result=sde_system(**common,steps=steps,increments=increments.tolist())
        if previous is not None:
            difference=float(np.max(np.linalg.norm(np.array(result['trajectory'])[::2]-previous,axis=1)))
            if difference<=tolerance:return {**result,'refinement_difference':difference,'requested_estimator_reached':True}
        previous=np.array(result['trajectory']);steps*=2
    return {**result,'refinement_difference':difference,'requested_estimator_reached':False,
            'scope':'Nested Brownian refinement estimator only; no pathwise certificate or expected-error guarantee.'}
