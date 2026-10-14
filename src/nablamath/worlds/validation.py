"""Compare existing ODE integrators against independent analytic solutions."""
from dataclasses import dataclass
import math

from ..math.equations.ode import integrate


@dataclass(frozen=True)
class ModelSpec:
    name: str
    initial: tuple[float, ...]
    rate: float = 1.0
    duration: float = 1.0

    def __post_init__(self) -> None:
        if self.name not in {'exponential_decay', 'harmonic_oscillator'}:
            raise ValueError('Modelo nao suportado')
        expected = 1 if self.name == 'exponential_decay' else 2
        if len(self.initial) != expected:
            raise ValueError('Dimensao inicial invalida')
        initial = tuple(float(v) for v in self.initial)
        if not all(math.isfinite(v) and abs(v) <= 1e6 for v in initial):
            raise ValueError('Estado inicial fora do limite')
        if not math.isfinite(self.rate) or not 0 < self.rate <= 100:
            raise ValueError('Taxa fora do limite')
        if not math.isfinite(self.duration) or not 0 < self.duration <= 100 or self.duration*self.rate > 100:
            raise ValueError('Intervalo fora do limite')
        object.__setattr__(self, 'initial', initial)

    @property
    def units(self) -> tuple[str, ...]:
        return ('dimensionless',) if self.name == 'exponential_decay' else ('m', 'm/s')

    def derivative(self, time, state):
        if self.name == 'exponential_decay':
            return (-self.rate*state[0],)
        return state[1], -self.rate**2*state[0]

    def reference(self, time):
        if self.name == 'exponential_decay':
            return (self.initial[0]*math.exp(-self.rate*time),)
        x, v = self.initial
        c, s = math.cos(self.rate*time), math.sin(self.rate*time)
        return x*c + v/self.rate*s, -x*self.rate*s + v*c


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
            'trajectory': trajectory, 'evidence': 'comparison_with_analytic_reference',
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
