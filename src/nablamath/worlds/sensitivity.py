"""Central finite-difference parameter sensitivity, with step convergence evidence."""
from dataclasses import replace
import math
from .model_spec import HeatModelSpec
from .pde import solve_heat
from .validation import simulate


def sensitivity(model, parameter='rate', *, relative_step=1e-3, **solver_options):
    allowed = {'diffusivity', 'length', 'amplitude'} if isinstance(model, HeatModelSpec) else {'rate'}
    if parameter not in allowed or not math.isfinite(relative_step) or not 1e-8 <= relative_step <= 0.1:
        raise ValueError('Parâmetro ou passo de sensibilidade inválido')
    solver = solve_heat if isinstance(model, HeatModelSpec) else simulate
    value = getattr(model, parameter)
    step = (abs(value) if value else 1.0)*relative_step
    derivatives = []
    for h in (step, step/2):
        left = solver(replace(model, **{parameter: value-h}), **solver_options)['final']
        right = solver(replace(model, **{parameter: value+h}), **solver_options)['final']
        derivatives.append(tuple((b-a)/(2*h) for a,b in zip(left,right)))
    return {'parameter': parameter, 'step': step/2, 'derivative': derivatives[-1],
            'step_change': max(abs(a-b) for a,b in zip(*derivatives)),
            'method': 'central_finite_difference', 'experimental_validation': False}
