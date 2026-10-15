"""Compare existing ODE integrators against independent analytic solutions."""
from dataclasses import dataclass
import math

from ..math.equations.ode import integrate


from .model_spec import ModelSpec


def simulate(model: ModelSpec, *, steps: int = 100, method: str = 'rk4') -> dict:
    if type(steps) is not int or not 2 <= steps <= 100_000:
        raise ValueError('Simulacao requer de 2 a 100000 passos')
    trajectory = integrate(model.derivative, model.initial, 0.0, model.duration, steps, method)
    reference = model.reference(model.duration)
    errors = tuple(abs(a-b) for a, b in zip(trajectory[-1][1], reference))
    drift = None
    if model.name == 'harmonic_oscillator':
        def energy(state):
            return (state[1]**2 + (model.rate*state[0])**2)/2
        initial_energy = energy(model.initial)
        drift = max(abs(energy(state)-initial_energy) for _, state in trajectory)
    return {'model': model.name, 'method': method, 'steps': steps, 'time_unit': 's',
            'state_units': model.units, 'rate_unit': '1/s', 'rate': model.rate,
            'duration': model.duration, 'initial': model.initial, 'final': trajectory[-1][1],
            'reference': reference, 'component_absolute_errors': errors,
            'max_component_error': max(errors), 'energy_drift_per_unit_mass': drift,
            'energy_drift_unit': 'm^2/s^2' if drift is not None else None,
            'trajectory': trajectory, 'model_spec': model.to_data(), 'model_id': model.content_id, 'evidence': 'comparison_with_analytic_reference',
            'limitations': 'EDO ideal; sem dados observados ou validacao experimental.'}


def convergence_study(model: ModelSpec, *, steps: int = 20, method: str = 'rk4', tolerance: float = 1e-5) -> dict:
    if type(steps) is not int or not 2 <= steps <= 50_000:
        raise ValueError('Refinamento requer de 2 a 50000 passos')
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('Tolerancia deve ser finita e positiva')
    coarse, fine = simulate(model, steps=steps, method=method), simulate(model, steps=2*steps, method=method)
    a, b = coarse['max_component_error'], fine['max_component_error']
    order = math.log2(a/b) if a > 1e-14 and b > 1e-14 else None
    return {'coarse_error': a, 'fine_error': b, 'observed_order': order, 'steps': [steps, 2*steps],
            'method': method, 'tolerance': tolerance, 'within_tolerance': b <= tolerance,
            'improves': b < a, 'reference': 'analytic', 'experimental_validation': False}


def compare_observations(result, observations, *, provenance, state_units, time_unit='s',
                         absolute_tolerance=1e-3, relative_tolerance=1e-3):
    """Compare supplied measurements to interpolated simulated states, retaining residuals.

    Provenance is a caller declaration; this function does not authenticate an
    instrument or establish independence of measurements.
    """
    expected_units = tuple(result.get('state_units', ('K',)*len(result['final'])))
    if not provenance.strip() or time_unit != 's' or tuple(state_units) != expected_units:
        raise ValueError('Origem e unidades compatíveis obrigatórias')
    if any(not math.isfinite(v) or v < 0 for v in (absolute_tolerance, relative_tolerance)):
        raise ValueError('Tolerância inválida')
    if absolute_tolerance == relative_tolerance == 0:
        raise ValueError('Tolerância não pode ser nula')
    trajectory = result['trajectory']
    rows = []
    if not observations:
        raise ValueError('Observações vazias')
    for observation in observations:
        if set(observation) != {'time', 'values', 'uncertainties'}:
            raise ValueError('Contrato de observação inválido')
        time = observation['time']
        values, uncertainties = observation['values'], observation['uncertainties']
        if (not math.isfinite(time) or not trajectory[0][0] <= time <= trajectory[-1][0]+1e-12
                or len(values) != len(expected_units) or len(uncertainties) != len(values)
                or any(not math.isfinite(v) for v in values)
                or any(not math.isfinite(v) or v < 0 for v in uncertainties)):
            raise ValueError('Observação fora do domínio')
        index = next((i for i in range(1,len(trajectory)) if trajectory[i][0]+1e-12 >= time), len(trajectory)-1)
        t0, a = trajectory[index-1]; t1, b = trajectory[index]
        fraction = min(1.0, max(0.0, (time-t0)/(t1-t0)))
        predicted = tuple(x+fraction*(y-x) for x,y in zip(a,b))
        residuals = tuple(abs(x-y) for x,y in zip(predicted,values))
        limits = tuple(absolute_tolerance+relative_tolerance*abs(v)+u for v,u in zip(values,uncertainties))
        rows.append({'time': time, 'predicted': predicted, 'observed': tuple(values),
                     'absolute_residuals': residuals, 'limits': limits,
                     'within_tolerance': all(e <= limit for e,limit in zip(residuals,limits))})
    return {'provenance': provenance, 'count': len(rows), 'comparisons': rows,
            'within_tolerance': all(row['within_tolerance'] for row in rows),
            'evidence': 'comparison_with_supplied_observations', 'independent_provenance_verified': False}


def simulate_adaptive(model: ModelSpec, *, atol=1e-9, rtol=1e-6, max_attempts=100000,
                      initial_step=None):
    """Adaptive trajectory with actual analytic errors for supported ideal models."""
    from .integrators.adaptive import integrate_adaptive
    report = integrate_adaptive(model.derivative, model.initial, 0., model.duration,
                                atol=atol, rtol=rtol, max_attempts=max_attempts,
                                initial_step=initial_step)
    errors = [tuple(abs(a-b) for a,b in zip(state, model.reference(time)))
              for time,state in report['trajectory']]
    return {**report, 'model_spec': model.to_data(), 'model_id': model.content_id,
            'state_units': model.units, 'time_unit': 's',
            'reference': model.reference(model.duration),
            'max_trajectory_reference_error': max(max(row) for row in errors),
            'component_absolute_errors': errors[-1],
            'max_component_error': max(errors[-1]), 'experimental_validation': False}
