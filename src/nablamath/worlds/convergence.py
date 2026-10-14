"""Joint temporal/spatial refinement for a bounded parabolic equation."""
import math
from .validation import convergence_study
from .pde import solve_heat


def heat_convergence(model, *, cells=10, steps=100, tolerance=1e-3):
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('Tolerância positiva obrigatória')
    if cells > 1000 or steps > 25000:
        raise ValueError('Refinamento excede limites')
    coarse = solve_heat(model, cells=cells, steps=steps, snapshot_stride=steps)
    fine = solve_heat(model, cells=2*cells, steps=4*steps, snapshot_stride=4*steps)
    a, b = coarse['max_component_error'], fine['max_component_error']
    return {'reference': 'analytic_sine_mode', 'coarse_error': a, 'fine_error': b,
            'observed_order': math.log2(a/b) if min(a,b) > 1e-14 else None,
            'cells': [cells, 2*cells], 'steps': [steps, 4*steps], 'expected_order': 2,
            'tolerance': tolerance, 'within_tolerance': b <= tolerance,
            'improves': b < a, 'experimental_validation': False}
