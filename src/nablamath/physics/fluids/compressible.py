"""First-order finite-volume Euler gas dynamics in one Cartesian dimension.

Contract version 1 uses ideal-gas pressure, cell averages, uniform cell widths,
and local Lax--Friedrichs (Rusanov) interface fluxes. SI units are required.
It excludes viscosity, chemistry, gravity, multidimensional effects and vacuum.
The positivity guard rejects or subdivides a step; it never clips conserved
quantities. Analytic jump checks are mathematical validation, not experiments.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

CONTRACT_VERSION = 1


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite real number')
    return float(value)


def _gamma(value: float) -> float:
    value = _finite(value, 'gamma')
    if not 1.0 < value <= 3.0:
        raise ValueError('gamma must be in (1, 3]')
    return value


@dataclass(frozen=True)
class PrimitiveState:
    """Density kg/m^3, velocity m/s and thermodynamic pressure Pa."""

    density: float
    velocity: float
    pressure: float

    def __post_init__(self) -> None:
        for name in ('density', 'velocity', 'pressure'):
            object.__setattr__(self, name, _finite(getattr(self, name), name))
        if not 1e-12 <= self.density <= 1e12:
            raise ValueError('density outside [1e-12, 1e12] kg/m^3')
        if not 1e-12 <= self.pressure <= 1e18:
            raise ValueError('pressure outside [1e-12, 1e18] Pa')
        if abs(self.velocity) > 1e8:
            raise ValueError('velocity outside bounded nonrelativistic model')

    def conservative(self, gamma: float = 1.4) -> ConservativeState:
        gamma = _gamma(gamma)
        return ConservativeState(
            self.density,
            self.density * self.velocity,
            self.pressure / (gamma - 1) + self.density * self.velocity**2 / 2,
        )

    def sound_speed(self, gamma: float = 1.4) -> float:
        return math.sqrt(_gamma(gamma) * self.pressure / self.density)

    def to_data(self) -> dict:
        return {
            'schema_version': CONTRACT_VERSION,
            'density_kg_m3': self.density,
            'velocity_m_s': self.velocity,
            'pressure_pa': self.pressure,
        }


@dataclass(frozen=True)
class ConservativeState:
    """Density, momentum density and total energy density; no clipping."""

    density: float
    momentum: float
    energy: float

    def __post_init__(self) -> None:
        for name in ('density', 'momentum', 'energy'):
            object.__setattr__(self, name, _finite(getattr(self, name), name))
        if self.density <= 0:
            raise ValueError('strictly positive density required')
        if self.internal_energy <= 0:
            raise ValueError('strictly positive internal energy required')

    @property
    def internal_energy(self) -> float:
        return self.energy - (self.momentum / self.density) * self.momentum / 2

    def primitive(self, gamma: float = 1.4) -> PrimitiveState:
        gamma = _gamma(gamma)
        return PrimitiveState(
            self.density,
            self.momentum / self.density,
            (gamma - 1) * self.internal_energy,
        )

    def components(self) -> tuple[float, float, float]:
        return self.density, self.momentum, self.energy


def physical_flux(state: ConservativeState, gamma: float = 1.4) -> tuple[float, float, float]:
    """Return inviscid mass, momentum and total-energy flux in +x direction."""
    p = state.primitive(gamma)
    return (
        state.momentum,
        state.momentum * p.velocity + p.pressure,
        (state.energy + p.pressure) * p.velocity,
    )


def rusanov_flux(
    left: ConservativeState,
    right: ConservativeState,
    gamma: float = 1.4,
) -> tuple[float, float, float]:
    """Consistent two-state Rusanov flux with ideal-gas acoustic wave speed."""
    gamma = _gamma(gamma)
    pl, pr = left.primitive(gamma), right.primitive(gamma)
    speed = max(abs(pl.velocity) + pl.sound_speed(gamma), abs(pr.velocity) + pr.sound_speed(gamma))
    fl, fr = physical_flux(left, gamma), physical_flux(right, gamma)
    flux = tuple(
        (a + b - speed * (v - u)) / 2
        for a, b, u, v in zip(fl, fr, left.components(), right.components())
    )
    if not all(math.isfinite(v) for v in flux):
        raise ArithmeticError('nonfinite Rusanov flux')
    return flux


@dataclass(frozen=True)
class Euler1DConfig:
    length_m: float = 1.0
    gamma: float = 1.4
    cfl: float = 0.4
    boundary: str = 'outflow'
    max_steps: int = 100000
    max_cell_updates: int = 10000000
    max_halvings: int = 20

    def __post_init__(self) -> None:
        length = _finite(self.length_m, 'length')
        cfl = _finite(self.cfl, 'cfl')
        if not 1e-9 <= length <= 1e9:
            raise ValueError('length outside [1e-9, 1e9] m')
        if not 0 < cfl <= 0.5:
            raise ValueError('CFL must be in (0, 0.5]')
        if self.boundary not in ('outflow', 'periodic', 'reflecting'):
            raise ValueError('unsupported boundary')
        for name, maximum in (('max_steps', 1000000), ('max_cell_updates', 100000000), ('max_halvings', 40)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f'invalid {name} budget')
        object.__setattr__(self, 'length_m', length)
        object.__setattr__(self, 'gamma', _gamma(self.gamma))
        object.__setattr__(self, 'cfl', cfl)


@dataclass(frozen=True)
class Euler1DResult:
    """Final cell averages plus integrated conservative boundary accounting."""

    cell_centers_m: tuple[float, ...]
    states: tuple[ConservativeState, ...]
    duration_s: float
    steps: int
    attempted_cell_updates: int
    rejected_steps: int
    initial_integrals: tuple[float, float, float]
    final_integrals: tuple[float, float, float]
    boundary_transport: tuple[float, float, float]
    gamma: float
    boundary: str

    @property
    def conservation_residual(self) -> tuple[float, float, float]:
        """Final minus initial minus accumulated left-in/right-out transport."""
        return tuple(b - a - transport for a, b, transport in zip(
            self.initial_integrals, self.final_integrals, self.boundary_transport,
        ))

    @property
    def primitive_states(self) -> tuple[PrimitiveState, ...]:
        return tuple(s.primitive(self.gamma) for s in self.states)

    def to_data(self) -> dict:
        return {
            'schema_version': CONTRACT_VERSION,
            'model': 'ideal_gas_euler_1d',
            'method': 'first_order_rusanov_finite_volume',
            'cell_centers_m': list(self.cell_centers_m),
            'states': [s.to_data() for s in self.primitive_states],
            'duration_s': self.duration_s,
            'steps': self.steps,
            'attempted_cell_updates': self.attempted_cell_updates,
            'rejected_steps': self.rejected_steps,
            'conservation_residual': list(self.conservation_residual),
            'gamma': self.gamma,
            'boundary': self.boundary,
            'experimental_validation': False,
            'limitations': 'Uniform 1D ideal gas; numerical diffusion; no vacuum, viscosity or experimental validation.',
        }


def _integrals(states: Sequence[ConservativeState], dx: float) -> tuple[float, float, float]:
    return tuple(math.fsum(s.components()[j] for s in states) * dx for j in range(3))


def _reflected(state: ConservativeState) -> ConservativeState:
    return ConservativeState(state.density, -state.momentum, state.energy)


def _interfaces(states: Sequence[ConservativeState], config: Euler1DConfig) -> tuple:
    if config.boundary == 'periodic':
        edge = rusanov_flux(states[-1], states[0], config.gamma)
        left, right = edge, edge
    elif config.boundary == 'reflecting':
        left = rusanov_flux(_reflected(states[0]), states[0], config.gamma)
        right = rusanov_flux(states[-1], _reflected(states[-1]), config.gamma)
    else:
        left = physical_flux(states[0], config.gamma)
        right = physical_flux(states[-1], config.gamma)
    middle = tuple(rusanov_flux(a, b, config.gamma) for a, b in zip(states, states[1:]))
    return (left, *middle, right)


def solve_euler_1d(
    initial: Sequence[PrimitiveState],
    duration_s: float,
    *,
    config: Euler1DConfig | None = None,
) -> Euler1DResult:
    """Advance bounded positive cell averages with CFL and work-budget checks.

    ``initial`` contains between two and 4096 cell averages. Positivity failures
    trigger time-step halving under a separate bounded budget. Every attempted
    update is charged to the cell-update budget, including rejected steps.
    Outflow boundaries copy the adjacent state and are only approximate open
    boundaries. Reflecting walls retain pressure forces in momentum accounting.
    """
    config = Euler1DConfig() if config is None else config
    if not isinstance(config, Euler1DConfig):
        raise ValueError('Euler1DConfig required')
    if not isinstance(initial, (list, tuple)) or not 2 <= len(initial) <= 4096:
        raise ValueError('two to 4096 initial cell averages required')
    if any(not isinstance(s, PrimitiveState) for s in initial):
        raise ValueError('PrimitiveState cell averages required')
    duration = _finite(duration_s, 'duration')
    if not 0 <= duration <= 1e6:
        raise ValueError('duration outside [0, 1e6] s')
    n = len(initial)
    dx = config.length_m / n
    states = tuple(s.conservative(config.gamma) for s in initial)
    start = _integrals(states, dx)
    transport = [0.0, 0.0, 0.0]
    time = 0.0
    steps = updates = rejected = 0
    while time < duration:
        if steps >= config.max_steps:
            raise ArithmeticError('Euler step budget exhausted')
        primitives = tuple(s.primitive(config.gamma) for s in states)
        speed = max(abs(p.velocity) + p.sound_speed(config.gamma) for p in primitives)
        dt = min(config.cfl * dx / speed, duration - time)
        fluxes = _interfaces(states, config)
        for halving in range(config.max_halvings + 1):
            if updates + n > config.max_cell_updates:
                raise ArithmeticError('Euler cell-update budget exhausted')
            if dt <= 0 or time + dt <= time:
                raise ArithmeticError('Euler time step is not representable')
            updates += n
            try:
                candidate = tuple(ConservativeState(*(
                    u - dt / dx * (fr - fl)
                    for u, fl, fr in zip(state.components(), fluxes[i], fluxes[i+1])
                )) for i, state in enumerate(states))
                for state in candidate:
                    state.primitive(config.gamma)
            except (ValueError, OverflowError):
                rejected += 1
                if halving == config.max_halvings:
                    raise ArithmeticError('Euler positivity halving budget exhausted') from None
                dt /= 2
                continue
            break
        for j in range(3):
            transport[j] += dt * (fluxes[0][j] - fluxes[-1][j])
        states = candidate
        time = duration if dt == duration - time else time + dt
        steps += 1
    return Euler1DResult(
        tuple((i + 0.5) * dx for i in range(n)), states, duration, steps, updates,
        rejected, start, _integrals(states, dx), tuple(transport), config.gamma,
        config.boundary,
    )


def shock_tube_initial(
    cells: int,
    left: PrimitiveState,
    right: PrimitiveState,
    *,
    discontinuity_fraction: float = 0.5,
) -> tuple[PrimitiveState, ...]:
    """Two piecewise-constant cell-average states with a face-aligned jump."""
    if type(cells) is not int or not 2 <= cells <= 4096:
        raise ValueError('two to 4096 cells required')
    if not isinstance(left, PrimitiveState) or not isinstance(right, PrimitiveState):
        raise ValueError('PrimitiveState endpoints required')
    fraction = _finite(discontinuity_fraction, 'discontinuity fraction')
    face = round(cells * fraction)
    if not 1 <= face < cells or abs(cells * fraction - face) > 1e-10:
        raise ValueError('discontinuity must align with an interior cell face')
    return (left,) * face + (right,) * (cells - face)


def normal_shock_downstream(upstream: PrimitiveState, gamma: float = 1.4) -> PrimitiveState:
    """Stationary normal shock jump for a supersonic upstream flow in +x.

    This closed-form reference is restricted to a perfect ideal gas with the
    same gamma on both sides. It is not an experimental shock validation.
    """
    if not isinstance(upstream, PrimitiveState):
        raise ValueError('PrimitiveState required')
    gamma = _gamma(gamma)
    mach = upstream.velocity / upstream.sound_speed(gamma)
    if not 1 < mach <= 100:
        raise ValueError('upstream Mach number must be in (1,100]')
    ratio = (gamma + 1) * mach**2 / ((gamma - 1) * mach**2 + 2)
    pressure_ratio = 1 + 2 * gamma / (gamma + 1) * (mach**2 - 1)
    return PrimitiveState(upstream.density * ratio, upstream.velocity / ratio,
                          upstream.pressure * pressure_ratio)


def rankine_hugoniot_residual(
    left: PrimitiveState,
    right: PrimitiveState,
    shock_speed: float = 0.0,
    gamma: float = 1.4,
) -> tuple[float, float, float]:
    """Return F(right)-F(left)-s*(U(right)-U(left)), in SI flux units."""
    speed = _finite(shock_speed, 'shock speed')
    if not isinstance(left, PrimitiveState) or not isinstance(right, PrimitiveState):
        raise ValueError('PrimitiveState endpoints required')
    ul, ur = left.conservative(gamma), right.conservative(gamma)
    fl, fr = physical_flux(ul, gamma), physical_flux(ur, gamma)
    return tuple(b-a-speed*(v-u) for a,b,u,v in zip(fl,fr,ul.components(),ur.components()))
