"""Validated SI model contracts for bounded ODE and PDE experiments."""
from dataclasses import dataclass
import math

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
        if any(isinstance(v, bool) for v in self.initial) or any(isinstance(v, bool) for v in (self.rate,self.duration)):
            raise ValueError('Booleano não é parâmetro físico')
        initial = tuple(float(v) for v in self.initial)
        if not all(math.isfinite(v) and abs(v) <= 1e6 for v in initial):
            raise ValueError('Estado inicial fora do limite')
        if not math.isfinite(self.rate) or not 0 < self.rate <= 100:
            raise ValueError('Taxa fora do limite')
        if not math.isfinite(self.duration) or not 0 < self.duration <= 100 or self.duration*self.rate > 100:
            raise ValueError('Intervalo fora do limite')
        object.__setattr__(self, 'initial', initial)
        object.__setattr__(self, 'rate', float(self.rate))
        object.__setattr__(self, 'duration', float(self.duration))

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


    def to_data(self):
        from dataclasses import asdict
        return {'schema_version': 1, **asdict(self), 'time_unit': 's', 'state_units': list(self.units), 'rate_unit': '1/s'}

    @property
    def content_id(self):
        from ..core.semantic_ir import fingerprint
        return fingerprint(self.to_data())


@dataclass(frozen=True)
class HeatModelSpec:
    length: float = 1.0
    diffusivity: float = 0.1
    duration: float = 0.1
    amplitude: float = 1.0
    mode: int = 1

    def __post_init__(self):
        for name in ('length', 'diffusivity', 'duration', 'amplitude'):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or abs(value) > 1e6:
                raise ValueError('Parâmetro térmico não finito ou fora dos limites')
        if min(self.length, self.diffusivity, self.duration) < 1e-6:
            raise ValueError('Comprimento, difusividade e duração devem ser >= 1e-6')
        for name in ('length', 'diffusivity', 'duration', 'amplitude'):
            object.__setattr__(self, name, float(getattr(self, name)))
        if type(self.mode) is not int or not 1 <= self.mode <= 16:
            raise ValueError('Modo entre 1 e 16')

    def reference(self, time, position):
        wave = self.mode * math.pi / self.length
        return self.amplitude * math.exp(-self.diffusivity * wave**2 * time) * math.sin(wave * position)

    def to_data(self):
        from dataclasses import asdict
        return {'schema_version': 1, 'name': 'heat_1d', **asdict(self),
                'units': {'length': 'm', 'diffusivity': 'm^2/s', 'duration': 's', 'amplitude': 'K'},
                'boundary': 'homogeneous_dirichlet', 'initial': 'sine_mode',
                'limitations': 'Ideal linear heat equation; no experimental validation.'}

    @property
    def content_id(self):
        from ..core.semantic_ir import fingerprint
        return fingerprint(self.to_data())
