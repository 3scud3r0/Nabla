"""Contract 1: first-order conservative shallow water on a flat Cartesian bed.

Rusanov shared-face fluxes, explicit Euler, bounded wet states, and periodic,
reflecting-wall or zero-gradient outflow boundaries. This is a bounded numerical
model, not a wetting/drying, topography, dispersive-wave or turbulence solver.
Positivity violations reject/subdivide a step; depths are never silently clipped.
Units must be consistent: h and coordinates in metres, time in seconds, g in m/s².
No experimental validation or rigorous accumulated error enclosure is claimed.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
import math
from typing import Callable, Iterable, Mapping

CONTRACT_VERSION = 1
MAX_CELLS = 4096
MAX_STEPS = 10000


def finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite real number")
    return float(value)


@dataclass(frozen=True)
class WaterState:
    """Conserved depth and two depth-integrated momenta."""
    depth: float
    momentum_x: float = 0
    momentum_y: float = 0

    def __post_init__(self):
        for name in ('depth', 'momentum_x', 'momentum_y'):
            object.__setattr__(self, name, finite(getattr(self, name), name))
        if not 1e-12 <= self.depth <= 1e9:
            raise ValueError("wet depth must lie in [1e-12, 1e9]")
        if max(abs(self.velocity_x), abs(self.velocity_y)) > 1e8:
            raise ValueError("velocity exceeds bounded model")

    @property
    def velocity_x(self):
        return self.momentum_x/self.depth

    @property
    def velocity_y(self):
        return self.momentum_y/self.depth

    @property
    def vector(self):
        return self.depth, self.momentum_x, self.momentum_y

    @classmethod
    def primitive(cls, depth, velocity_x=0, velocity_y=0):
        h = finite(depth, 'depth')
        return cls(h, h*finite(velocity_x, 'velocity x'), h*finite(velocity_y, 'velocity y'))

    def energy(self, gravity=9.81):
        g = finite(gravity, 'gravity')
        if g <= 0:
            raise ValueError("gravity must be positive")
        return (self.momentum_x**2+self.momentum_y**2)/(2*self.depth) + .5*g*self.depth**2

    def to_data(self):
        return dict(depth=self.depth, momentum_x=self.momentum_x, momentum_y=self.momentum_y)

    @classmethod
    def from_data(cls, data):
        if not isinstance(data, dict) or set(data) != {'depth', 'momentum_x', 'momentum_y'}:
            raise ValueError("invalid water state schema")
        return cls(**data)


@dataclass(frozen=True)
class WaterGrid:
    nx: int
    ny: int
    length_x: float = 1
    length_y: float = 1
    boundary_x: str = 'periodic'
    boundary_y: str = 'periodic'
    gravity: float = 9.81
    minimum_depth: float = 1e-10

    def __post_init__(self):
        if (type(self.nx) is not int or type(self.ny) is not int
                or min(self.nx, self.ny) < 2 or self.nx*self.ny > MAX_CELLS):
            raise ValueError("grid requires >=2 cells per axis and <=4096 total")
        for name in ('length_x', 'length_y', 'gravity', 'minimum_depth'):
            object.__setattr__(self, name, finite(getattr(self, name), name))
        if not all(1e-9 <= v <= 1e9 for v in (self.length_x, self.length_y, self.gravity)):
            raise ValueError("positive bounded lengths and gravity required")
        if not 1e-12 <= self.minimum_depth <= 1:
            raise ValueError("minimum wet depth outside model range")
        if any(b not in ('periodic', 'wall', 'outflow') for b in (self.boundary_x, self.boundary_y)):
            raise ValueError("unsupported boundary type")

    @property
    def dx(self):
        return self.length_x/self.nx

    @property
    def dy(self):
        return self.length_y/self.ny

    @property
    def area(self):
        return self.dx*self.dy

    def center(self, i, j):
        if type(i) is not int or type(j) is not int or not 0 <= i < self.nx or not 0 <= j < self.ny:
            raise ValueError("invalid cell index")
        return (i+.5)*self.dx, (j+.5)*self.dy

    def to_data(self):
        return dict(version=CONTRACT_VERSION, nx=self.nx, ny=self.ny,
                    length_x=self.length_x, length_y=self.length_y,
                    boundary_x=self.boundary_x, boundary_y=self.boundary_y,
                    gravity=self.gravity, minimum_depth=self.minimum_depth)

    @classmethod
    def from_data(cls, data):
        keys = {'version', 'nx', 'ny', 'length_x', 'length_y', 'boundary_x', 'boundary_y', 'gravity', 'minimum_depth'}
        if (not isinstance(data, dict) or set(data) != keys
                or type(data['version']) is not int or data['version'] != CONTRACT_VERSION):
            raise ValueError("invalid water grid schema")
        return cls(**{k: v for k, v in data.items() if k != 'version'})


@dataclass(frozen=True)
class WaterField:
    grid: WaterGrid
    rows: tuple[tuple[WaterState, ...], ...]

    def __post_init__(self):
        if not isinstance(self.grid, WaterGrid):
            raise ValueError("WaterGrid required")
        rows = tuple(tuple(islice(row, self.grid.nx+1)) for row in islice(self.rows, self.grid.ny+1))
        if len(rows) != self.grid.ny or any(len(row) != self.grid.nx for row in rows):
            raise ValueError("water field dimensions do not match grid")
        if any(not isinstance(state, WaterState) or state.depth < self.grid.minimum_depth
               for row in rows for state in row):
            raise ValueError("water field requires bounded wet states")
        object.__setattr__(self, 'rows', rows)

    @classmethod
    def sample(cls, grid, profile):
        return cls(grid, tuple(tuple(profile(*grid.center(i, j)) for i in range(grid.nx))
                               for j in range(grid.ny)))

    def integrals(self):
        return tuple(math.fsum(s.vector[k] for row in self.rows for s in row)*self.grid.area for k in range(3))

    def total_energy(self):
        return math.fsum(s.energy(self.grid.gravity) for row in self.rows for s in row)*self.grid.area

    @property
    def depth_range(self):
        depths = [s.depth for row in self.rows for s in row]
        return min(depths), max(depths)

    @property
    def maximum_froude(self):
        return max(math.hypot(s.velocity_x, s.velocity_y)/math.sqrt(self.grid.gravity*s.depth)
                   for row in self.rows for s in row)

    def to_data(self):
        return dict(version=CONTRACT_VERSION, grid=self.grid.to_data(),
                    rows=[[s.to_data() for s in row] for row in self.rows])

    @classmethod
    def from_data(cls, data):
        if (not isinstance(data, dict) or set(data) != {'version', 'grid', 'rows'}
                or type(data['version']) is not int or data['version'] != CONTRACT_VERSION):
            raise ValueError("invalid water field schema")
        grid = WaterGrid.from_data(data['grid'])
        if not isinstance(data['rows'], list) or len(data['rows']) != grid.ny:
            raise ValueError("invalid water field rows")
        if any(not isinstance(row, list) or len(row) != grid.nx for row in data['rows']):
            raise ValueError("invalid water field columns")
        return cls(grid, tuple(tuple(WaterState.from_data(s) for s in row) for row in data['rows']))


def physical_flux(state, axis, gravity=9.81):
    if not isinstance(state, WaterState) or axis not in ('x', 'y'):
        raise ValueError("state and axis x/y required")
    g = finite(gravity, 'gravity')
    if g <= 0:
        raise ValueError("gravity must be positive")
    h, hu, hv = state.vector
    pressure = .5*g*h*h
    if axis == 'x':
        return hu, hu*hu/h+pressure, hu*hv/h
    return hv, hu*hv/h, hv*hv/h+pressure


def rusanov_flux(left, right, axis, gravity=9.81):
    """Shared numerical face flux, oriented in the positive coordinate axis."""
    fl, fr = physical_flux(left, axis, gravity), physical_flux(right, axis, gravity)
    velocities = (left.velocity_x, right.velocity_x) if axis == 'x' else (left.velocity_y, right.velocity_y)
    speed = max(abs(velocities[0])+math.sqrt(gravity*left.depth),
                abs(velocities[1])+math.sqrt(gravity*right.depth))
    flux = tuple(.5*(a+b)-.5*speed*(ur-ul)
                 for a, b, ul, ur in zip(fl, fr, left.vector, right.vector, strict=True))
    if not all(math.isfinite(v) for v in flux):
        raise ArithmeticError("nonfinite numerical flux")
    return flux


def reflected(state, axis):
    if axis == 'x':
        return WaterState(state.depth, -state.momentum_x, state.momentum_y)
    if axis == 'y':
        return WaterState(state.depth, state.momentum_x, -state.momentum_y)
    raise ValueError("axis must be x or y")


def stable_timestep(field, cfl=.4):
    """Global conservative bound using both directional wave speeds."""
    cfl = finite(cfl, 'CFL')
    if not 0 < cfl <= .45:
        raise ValueError("CFL must lie in (0,.45]")
    grid = field.grid
    maximum_x = max(abs(s.velocity_x)+math.sqrt(grid.gravity*s.depth) for row in field.rows for s in row)
    maximum_y = max(abs(s.velocity_y)+math.sqrt(grid.gravity*s.depth) for row in field.rows for s in row)
    dt = cfl/(maximum_x/grid.dx+maximum_y/grid.dy)
    if not math.isfinite(dt) or dt <= 0:
        raise ArithmeticError("time step not representable")
    return dt


def face_fluxes(field):
    """Return x faces [ny][nx+1], y faces [ny+1][nx].

    Periodic end faces share exactly the same tuple, ensuring cancellation.
    Wall ghosts reflect normal momentum. Outflow ghosts copy edge states.
    """
    grid, rows = field.grid, field.rows
    xfaces = []
    for j in range(grid.ny):
        row = rows[j]
        interior = [rusanov_flux(row[i-1], row[i], 'x', grid.gravity) for i in range(1, grid.nx)]
        if grid.boundary_x == 'periodic':
            low = high = rusanov_flux(row[-1], row[0], 'x', grid.gravity)
        else:
            low_ghost = reflected(row[0], 'x') if grid.boundary_x == 'wall' else row[0]
            high_ghost = reflected(row[-1], 'x') if grid.boundary_x == 'wall' else row[-1]
            low = rusanov_flux(low_ghost, row[0], 'x', grid.gravity)
            high = rusanov_flux(row[-1], high_ghost, 'x', grid.gravity)
        xfaces.append((low, *interior, high))
    yfaces = []
    for j in range(grid.ny+1):
        line = []
        for i in range(grid.nx):
            if 0 < j < grid.ny:
                bottom, top = rows[j-1][i], rows[j][i]
            elif grid.boundary_y == 'periodic':
                bottom, top = rows[-1][i], rows[0][i]
            elif j == 0:
                top = rows[0][i]
                bottom = reflected(top, 'y') if grid.boundary_y == 'wall' else top
            else:
                bottom = rows[-1][i]
                top = reflected(bottom, 'y') if grid.boundary_y == 'wall' else bottom
            line.append(rusanov_flux(bottom, top, 'y', grid.gravity))
        yfaces.append(tuple(line))
    if grid.boundary_y == 'periodic':
        yfaces[-1] = yfaces[0]
    return tuple(xfaces), tuple(yfaces)


@dataclass(frozen=True)
class WaterStep:
    field: WaterField
    dt: float
    boundary_change: tuple[float, float, float]
    conservation_residual: tuple[float, float, float]


def advance_water(field, dt, *, enforce_cfl=True):
    """One Euler step and the signed outward boundary-flux balance.

    Failure is atomic: the immutable input field remains unchanged. For each
    conserved component, new_total-old_total equals boundary_change up to roundoff.
    """
    if not isinstance(field, WaterField) or type(enforce_cfl) is not bool:
        raise ValueError("typed field and explicit CFL policy required")
    dt = finite(dt, 'time step')
    if dt <= 0:
        raise ValueError("time step must be positive")
    if enforce_cfl and dt > stable_timestep(field, .45)*(1+1e-12):
        raise ValueError("time step exceeds model CFL bound")
    grid = field.grid
    fx, fy = face_fluxes(field)
    new_rows = []
    for j in range(grid.ny):
        new_row = []
        for i in range(grid.nx):
            old = field.rows[j][i]
            values = tuple(old.vector[k]-dt/grid.dx*(fx[j][i+1][k]-fx[j][i][k])
                           -dt/grid.dy*(fy[j+1][i][k]-fy[j][i][k]) for k in range(3))
            if values[0] < grid.minimum_depth:
                raise ArithmeticError("step violates minimum wet depth; reduce time step")
            try:
                new_row.append(WaterState(*values))
            except ValueError as exc:
                raise ArithmeticError("step left bounded wet-state model") from exc
        new_rows.append(tuple(new_row))
    updated = WaterField(grid, tuple(new_rows))
    boundary = tuple(-dt*(grid.dy*math.fsum(fx[j][-1][k]-fx[j][0][k] for j in range(grid.ny))
                         +grid.dx*math.fsum(fy[-1][i][k]-fy[0][i][k] for i in range(grid.nx))) for k in range(3))
    old_total, new_total = field.integrals(), updated.integrals()
    residual = tuple(new_total[k]-old_total[k]-boundary[k] for k in range(3))
    return WaterStep(updated, dt, boundary, residual)


@dataclass(frozen=True)
class WaterRun:
    initial: WaterField
    final: WaterField
    start: float
    end: float
    steps: int
    rejected_steps: int
    boundary_change: tuple[float, float, float]
    conservation_residual: tuple[float, float, float]
    energy_change: float
    minimum_depth_seen: float
    snapshots: tuple[tuple[float, WaterField], ...]

    def to_data(self):
        return dict(version=CONTRACT_VERSION, method='flat-bed-2d-rusanov-euler',
                    initial=self.initial.to_data(), final=self.final.to_data(),
                    start=self.start, end=self.end, steps=self.steps, rejected_steps=self.rejected_steps,
                    boundary_change=list(self.boundary_change), conservation_residual=list(self.conservation_residual),
                    energy_change=self.energy_change, minimum_depth_seen=self.minimum_depth_seen,
                    snapshots=[dict(time=t, field=f.to_data()) for t, f in self.snapshots],
                    experimental_validation=False, global_error_certified=False)


def simulate_water(initial, end, *, start=0, cfl=.4, max_steps=MAX_STEPS,
                   max_retries=12, snapshot_stride=0):
    """Integrate a wet-state field, with rejection and bounded retained outputs.

    Reaching a resource limit raises an error instead of returning a successful
    run with an unfulfilled requested end time. snapshot_stride=0 stores no
    intermediate fields. Retained snapshot cells are capped at one million.
    """
    if not isinstance(initial, WaterField):
        raise ValueError("WaterField required")
    start, end = finite(start, 'start time'), finite(end, 'end time')
    if end <= start or not math.isfinite(end-start):
        raise ValueError("finite ordered time interval required")
    if type(max_steps) is not int or not 1 <= max_steps <= MAX_STEPS:
        raise ValueError("invalid step budget")
    if type(max_retries) is not int or not 0 <= max_retries <= 30:
        raise ValueError("invalid positivity retry budget")
    if type(snapshot_stride) is not int or not 0 <= snapshot_stride <= max_steps:
        raise ValueError("invalid snapshot stride")
    field, t, rejected, steps = initial, start, 0, 0
    ledger = [0., 0., 0.]
    snapshots = []
    minimum = initial.depth_range[0]
    while t < end:
        if steps >= max_steps:
            raise ArithmeticError("water integration step budget exhausted")
        dt = min(stable_timestep(field, cfl), end-t)
        for retry in range(max_retries+1):
            if t+dt <= t:
                raise ArithmeticError("water time step cannot advance floating time")
            try:
                result = advance_water(field, dt)
                break
            except ArithmeticError:
                if retry == max_retries:
                    raise
                rejected += 1
                dt /= 2
        t = end if dt == end-t else t+dt
        steps += 1
        field = result.field
        minimum = min(minimum, field.depth_range[0])
        ledger = [a+b for a, b in zip(ledger, result.boundary_change, strict=True)]
        if snapshot_stride and (steps % snapshot_stride == 0 or t == end):
            if (len(snapshots)+1)*initial.grid.nx*initial.grid.ny > 1000000:
                raise ArithmeticError("snapshot retention budget exhausted")
            snapshots.append((t, field))
    before, after = initial.integrals(), field.integrals()
    residual = tuple(after[k]-before[k]-ledger[k] for k in range(3))
    return WaterRun(initial, field, start, end, steps, rejected, tuple(ledger), residual,
                    field.total_energy()-initial.total_energy(), minimum, tuple(snapshots))


def field_error(field, reference):
    """Cell-center L1/L2/Linf diagnostics against an independent reference.

    These are discrete diagnostics; they do not include cell-average quadrature
    uncertainty or assert a continuous norm enclosure.
    """
    totals = [[], [], []]
    squares = [[], [], []]
    maximum = [0., 0., 0.]
    for j, row in enumerate(field.rows):
        for i, value in enumerate(row):
            target = reference(*field.grid.center(i, j))
            if not isinstance(target, WaterState):
                raise ValueError("reference must return WaterState")
            for k in range(3):
                error = abs(value.vector[k]-target.vector[k])
                totals[k].append(error)
                squares[k].append(error*error)
                maximum[k] = max(maximum[k], error)
    area = field.grid.length_x*field.grid.length_y
    return dict(l1=tuple(math.fsum(v)*field.grid.area/area for v in totals),
                l2=tuple(math.sqrt(math.fsum(v)*field.grid.area/area) for v in squares),
                linf=tuple(maximum), continuous_norm_certified=False)


def replay_water_steps(initial, timesteps, *, start=0, expected=None):
    """Reexecute a bounded accepted-step schedule, with all CFL/positivity checks.

    This is a deterministic numerical replay, not evidence of experimental
    validation. Rejected proposals are not represented in an accepted schedule.
    """
    if not isinstance(initial, WaterField):
        raise ValueError("initial WaterField required")
    schedule = tuple(islice(timesteps, MAX_STEPS+1))
    if not schedule or len(schedule) > MAX_STEPS:
        raise ValueError("bounded nonempty water replay schedule required")
    field, time = initial, finite(start, 'start time')
    changes = [[], [], []]
    for value in schedule:
        dt = finite(value, 'replay timestep')
        if dt <= 0 or time+dt <= time:
            raise ValueError("water replay cannot advance time")
        result = advance_water(field, dt)
        field = result.field
        for k in range(3):
            changes[k].append(result.boundary_change[k])
        time += dt
    if expected is not None and (not isinstance(expected, WaterField) or expected != field):
        raise ValueError("water replay differs from expected state")
    ledger = tuple(math.fsum(values) for values in changes)
    old, new = initial.integrals(), field.integrals()
    return dict(final=field, end=time, steps=len(schedule), boundary_change=ledger,
                conservation_residual=tuple(new[k]-old[k]-ledger[k] for k in range(3)),
                physical_validation=False)


def water_cfl_numbers(field, dt):
    """Directional maximum Courant numbers, based on local gravity-wave speeds."""
    if not isinstance(field, WaterField):
        raise ValueError("WaterField required")
    dt = finite(dt, 'diagnostic timestep')
    if dt <= 0:
        raise ValueError("positive diagnostic timestep required")
    grid = field.grid
    x = max((abs(s.velocity_x)+math.sqrt(grid.gravity*s.depth))*dt/grid.dx
            for row in field.rows for s in row)
    y = max((abs(s.velocity_y)+math.sqrt(grid.gravity*s.depth))*dt/grid.dy
            for row in field.rows for s in row)
    return dict(x=x, y=y, sum=x+y, positivity_cfl_limit=.45)
