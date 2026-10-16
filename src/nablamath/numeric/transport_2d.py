"""Contract 1: conservative scalar advection-diffusion on uniform 2D grids.

Shared first-order upwind advective fluxes and centered diffusive fluxes, forward
Euler time integration, constant velocities and isotropic diffusivity. Periodic
or zero-total-flux boundaries are supported independently per axis. The CFL bound
makes a source-free update a convex combination of old cell averages. Optional
forcing is evaluated explicitly at cell centers and old time. Negative source
terms can destroy positivity and are rejected when positivity is requested.
The solver is not high-resolution, unstructured, implicit, or experimentally
validated. Fourier profiles provide independent mathematical reference solutions.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
import math
from typing import Callable, Mapping

CONTRACT_VERSION = 1
MAX_CELLS = 16384
MAX_STEPS = 20000


def _real(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite real")
    return float(value)


@dataclass(frozen=True)
class TransportGrid:
    nx: int
    ny: int
    length_x: float = 1
    length_y: float = 1
    velocity_x: float = 0
    velocity_y: float = 0
    diffusivity: float = 0
    boundary_x: str = 'periodic'
    boundary_y: str = 'periodic'

    def __post_init__(self):
        if (type(self.nx) is not int or type(self.ny) is not int or min(self.nx, self.ny) < 2
                or self.nx*self.ny > MAX_CELLS):
            raise ValueError("2D grid requires >=2 cells per axis and <=16384 cells")
        for name in ('length_x', 'length_y', 'velocity_x', 'velocity_y', 'diffusivity'):
            object.__setattr__(self, name, _real(getattr(self, name), name))
        if not 1e-6 <= self.length_x <= 1e6 or not 1e-6 <= self.length_y <= 1e6:
            raise ValueError("bounded positive grid lengths required")
        if not 0 <= self.diffusivity <= 1e6 or max(abs(self.velocity_x), abs(self.velocity_y)) > 1e6:
            raise ValueError("transport coefficient outside model bounds")
        if any(b not in ('periodic', 'no_flux') for b in (self.boundary_x, self.boundary_y)):
            raise ValueError("unsupported transport boundary")

    @property
    def dx(self):
        return self.length_x/self.nx

    @property
    def dy(self):
        return self.length_y/self.ny

    @property
    def cell_area(self):
        return self.dx*self.dy

    @property
    def inverse_timescale(self):
        return (abs(self.velocity_x)/self.dx+abs(self.velocity_y)/self.dy
                +2*self.diffusivity*(1/self.dx**2+1/self.dy**2))

    def stable_dt(self, cfl=.9):
        cfl = _real(cfl, 'CFL')
        if not 0 < cfl <= 1:
            raise ValueError("CFL must lie in (0,1]")
        return math.inf if self.inverse_timescale == 0 else cfl/self.inverse_timescale

    def center(self, i, j):
        if type(i) is not int or type(j) is not int or not 0 <= i < self.nx or not 0 <= j < self.ny:
            raise ValueError("invalid transport cell")
        return (i+.5)*self.dx, (j+.5)*self.dy

    def to_data(self):
        return dict(version=CONTRACT_VERSION, nx=self.nx, ny=self.ny, length_x=self.length_x,
                    length_y=self.length_y, velocity_x=self.velocity_x, velocity_y=self.velocity_y,
                    diffusivity=self.diffusivity, boundary_x=self.boundary_x, boundary_y=self.boundary_y)

    @classmethod
    def from_data(cls, data):
        keys = {'version', 'nx', 'ny', 'length_x', 'length_y', 'velocity_x', 'velocity_y',
                'diffusivity', 'boundary_x', 'boundary_y'}
        if (not isinstance(data, dict) or set(data) != keys or type(data['version']) is not int
                or data['version'] != CONTRACT_VERSION):
            raise ValueError("invalid transport grid schema")
        return cls(**{k: v for k, v in data.items() if k != 'version'})


@dataclass(frozen=True)
class ScalarField2D:
    grid: TransportGrid
    rows: tuple[tuple[float, ...], ...]

    def __post_init__(self):
        if not isinstance(self.grid, TransportGrid):
            raise ValueError("TransportGrid required")
        rows = tuple(tuple(islice(row, self.grid.nx+1)) for row in islice(self.rows, self.grid.ny+1))
        if len(rows) != self.grid.ny or any(len(row) != self.grid.nx for row in rows):
            raise ValueError("scalar field shape mismatch")
        values = tuple(tuple(_real(v, 'scalar cell') for v in row) for row in rows)
        if any(abs(v) > 1e100 for row in values for v in row):
            raise ValueError("scalar magnitude budget exceeded")
        object.__setattr__(self, 'rows', values)

    @classmethod
    def sample(cls, grid, profile):
        return cls(grid, tuple(tuple(profile(*grid.center(i, j)) for i in range(grid.nx))
                               for j in range(grid.ny)))

    @property
    def mass(self):
        return math.fsum(v for row in self.rows for v in row)*self.grid.cell_area

    @property
    def range(self):
        values = [v for row in self.rows for v in row]
        return min(values), max(values)

    @property
    def squared_norm(self):
        return math.fsum(v*v for row in self.rows for v in row)*self.grid.cell_area

    def to_data(self):
        return dict(version=CONTRACT_VERSION, grid=self.grid.to_data(), rows=[list(row) for row in self.rows])

    @classmethod
    def from_data(cls, data):
        if (not isinstance(data, dict) or set(data) != {'version', 'grid', 'rows'}
                or type(data['version']) is not int or data['version'] != CONTRACT_VERSION):
            raise ValueError("invalid scalar field schema")
        grid = TransportGrid.from_data(data['grid'])
        if (not isinstance(data['rows'], list) or len(data['rows']) != grid.ny
                or any(not isinstance(row, list) or len(row) != grid.nx for row in data['rows'])):
            raise ValueError("invalid scalar row dimensions")
        return cls(grid, data['rows'])


def scalar_flux(left, right, velocity, diffusivity, spacing):
    """Positive-axis flux u*q_upwind - D*(q_right-q_left)/dx."""
    left, right = _real(left, 'left value'), _real(right, 'right value')
    velocity = _real(velocity, 'velocity')
    diffusivity, spacing = _real(diffusivity, 'diffusivity'), _real(spacing, 'spacing')
    if diffusivity < 0 or spacing <= 0:
        raise ValueError("nonnegative diffusion and positive spacing required")
    upwind = left if velocity >= 0 else right
    result = velocity*upwind-diffusivity*(right-left)/spacing
    if not math.isfinite(result):
        raise ArithmeticError("transport flux overflow")
    return result


def transport_faces(field):
    """Shared oriented face arrays; no-flux boundary faces are exactly zero."""
    grid, rows = field.grid, field.rows
    xfaces = []
    for row in rows:
        interior = [scalar_flux(row[i-1], row[i], grid.velocity_x, grid.diffusivity, grid.dx)
                    for i in range(1, grid.nx)]
        edge = (scalar_flux(row[-1], row[0], grid.velocity_x, grid.diffusivity, grid.dx)
                if grid.boundary_x == 'periodic' else 0.)
        xfaces.append((edge, *interior, edge))
    yfaces = []
    for j in range(grid.ny+1):
        line = []
        for i in range(grid.nx):
            if 0 < j < grid.ny:
                low, high = rows[j-1][i], rows[j][i]
            elif grid.boundary_y == 'periodic':
                low, high = rows[-1][i], rows[0][i]
            else:
                line.append(0.)
                continue
            line.append(scalar_flux(low, high, grid.velocity_y, grid.diffusivity, grid.dy))
        yfaces.append(tuple(line))
    if grid.boundary_y == 'periodic':
        yfaces[-1] = yfaces[0]
    return tuple(xfaces), tuple(yfaces)


@dataclass(frozen=True)
class TransportStep:
    field: ScalarField2D
    dt: float
    source_change: float
    boundary_change: float
    conservation_residual: float


def advance_transport(field, dt, *, time=0, source=None, require_nonnegative=False):
    """One conservative explicit step, enforcing the monotonicity CFL bound.

    The signed source ledger uses the same samples as the update. Source calls
    are bounded by grid cells per step and must be pure deterministic callbacks.
    """
    if not isinstance(field, ScalarField2D) or type(require_nonnegative) is not bool:
        raise ValueError("typed field and explicit positivity policy required")
    dt, time = _real(dt, 'time step'), _real(time, 'source time')
    if dt <= 0 or dt > field.grid.stable_dt(1)*(1+1e-12):
        raise ValueError("time step exceeds transport CFL or is nonpositive")
    if require_nonnegative and field.range[0] < 0:
        raise ValueError("positivity policy requires nonnegative initial cells")
    grid = field.grid
    fx, fy = transport_faces(field)
    rows, forcing = [], []
    for j in range(grid.ny):
        row = []
        for i in range(grid.nx):
            rate = 0. if source is None else _real(source(time, *grid.center(i, j)), 'source rate')
            value = (field.rows[j][i]-dt/grid.dx*(fx[j][i+1]-fx[j][i])
                     -dt/grid.dy*(fy[j+1][i]-fy[j][i])+dt*rate)
            if not math.isfinite(value):
                raise ArithmeticError("transport update is nonfinite")
            if require_nonnegative and value < 0:
                raise ArithmeticError("forcing/update violates positivity; no clipping applied")
            row.append(value)
            forcing.append(rate)
        rows.append(tuple(row))
    updated = ScalarField2D(grid, tuple(rows))
    source_change = dt*grid.cell_area*math.fsum(forcing)
    boundary = -dt*(grid.dy*math.fsum(row[-1]-row[0] for row in fx)
                    +grid.dx*math.fsum(fy[-1][i]-fy[0][i] for i in range(grid.nx)))
    residual = updated.mass-field.mass-source_change-boundary
    return TransportStep(updated, dt, source_change, boundary, residual)


@dataclass(frozen=True)
class TransportRun:
    initial: ScalarField2D
    final: ScalarField2D
    start: float
    end: float
    steps: int
    source_change: float
    boundary_change: float
    conservation_residual: float
    minimum_seen: float
    maximum_seen: float
    snapshots: tuple[tuple[float, ScalarField2D], ...]

    def to_data(self):
        return dict(version=CONTRACT_VERSION, method='upwind-centered-2d-euler',
                    initial=self.initial.to_data(), final=self.final.to_data(), start=self.start, end=self.end,
                    steps=self.steps, source_change=self.source_change, boundary_change=self.boundary_change,
                    conservation_residual=self.conservation_residual, minimum_seen=self.minimum_seen,
                    maximum_seen=self.maximum_seen,
                    snapshots=[dict(time=t, field=f.to_data()) for t, f in self.snapshots],
                    experimental_validation=False, global_error_certified=False)


def simulate_transport(initial, end, *, start=0, cfl=.9, max_steps=MAX_STEPS,
                       max_timestep=None, source=None, require_nonnegative=False,
                       snapshot_stride=0):
    """Complete a bounded integration or raise; no partial success artifacts."""
    if not isinstance(initial, ScalarField2D):
        raise ValueError("ScalarField2D required")
    start, end = _real(start, 'start'), _real(end, 'end')
    if end <= start or not math.isfinite(end-start):
        raise ValueError("finite ordered time interval required")
    if type(max_steps) is not int or not 1 <= max_steps <= MAX_STEPS:
        raise ValueError("invalid transport step budget")
    if type(snapshot_stride) is not int or not 0 <= snapshot_stride <= max_steps:
        raise ValueError("invalid snapshot stride")
    if max_timestep is not None:
        max_timestep = _real(max_timestep, 'maximum step')
        if max_timestep <= 0:
            raise ValueError("maximum step must be positive")
    bound = initial.grid.stable_dt(cfl)
    if max_timestep is not None:
        bound = min(bound, max_timestep)
    if source is not None and not math.isfinite(bound):
        raise ValueError("source-only problems require explicit maximum timestep")
    field, time, steps = initial, start, 0
    source_ledger, boundary_ledger = [], []
    minimum, maximum = initial.range
    snapshots = []
    while time < end:
        if steps >= max_steps:
            raise ArithmeticError("transport step budget exhausted")
        dt = min(bound, end-time)
        if time+dt <= time:
            raise ArithmeticError("transport step cannot advance floating time")
        result = advance_transport(field, dt, time=time, source=source,
                                   require_nonnegative=require_nonnegative)
        field = result.field
        time = end if dt == end-time else time+dt
        steps += 1
        source_ledger.append(result.source_change)
        boundary_ledger.append(result.boundary_change)
        lo, hi = field.range
        minimum, maximum = min(minimum, lo), max(maximum, hi)
        if snapshot_stride and (steps % snapshot_stride == 0 or time == end):
            if (len(snapshots)+1)*initial.grid.nx*initial.grid.ny > 1000000:
                raise ArithmeticError("transport snapshot budget exhausted")
            snapshots.append((time, field))
    source_change, boundary_change = math.fsum(source_ledger), math.fsum(boundary_ledger)
    residual = field.mass-initial.mass-source_change-boundary_change
    return TransportRun(initial, field, start, end, steps, source_change, boundary_change,
                        residual, minimum, maximum, tuple(snapshots))


def fourier_profile(grid, time, *, offset=1, amplitude=.25, mode_x=1, mode_y=1,
                    phase=0, cell_average=False):
    """Exact periodic Fourier solution of constant-coefficient transport PDE.

    q=offset+amplitude*exp(-D|k|²t)*cos(kx(x-ux*t)+ky(y-uy*t)+phase).
    cell_average=True applies exact rectangular-cell sinc factors, avoiding
    ambiguity between a finite-volume cell average and a center sample.
    """
    if not isinstance(grid, TransportGrid) or (grid.boundary_x, grid.boundary_y) != ('periodic', 'periodic'):
        raise ValueError("Fourier reference requires periodic TransportGrid")
    time, offset, amplitude, phase = (_real(v, n) for v, n in
                                     ((time, 'time'), (offset, 'offset'), (amplitude, 'amplitude'), (phase, 'phase')))
    if time < 0 or type(mode_x) is not int or type(mode_y) is not int or max(abs(mode_x), abs(mode_y)) > 100:
        raise ValueError("nonnegative time and bounded integer Fourier modes required")
    if type(cell_average) is not bool:
        raise ValueError("explicit averaging policy required")
    kx, ky = 2*math.pi*mode_x/grid.length_x, 2*math.pi*mode_y/grid.length_y
    scale = amplitude*math.exp(-grid.diffusivity*(kx*kx+ky*ky)*time)
    if cell_average:
        def sinc(x):
            return 1. if x == 0 else math.sin(x)/x
        scale *= sinc(kx*grid.dx/2)*sinc(ky*grid.dy/2)
    return lambda x, y: offset+scale*math.cos(kx*(x-grid.velocity_x*time)+ky*(y-grid.velocity_y*time)+phase)


def scalar_error(field, reference):
    """Discrete area-normalized errors; no global continuous error certificate."""
    absolute, squared = [], []
    for j, row in enumerate(field.rows):
        for i, value in enumerate(row):
            difference = abs(value-_real(reference(*field.grid.center(i, j)), 'reference'))
            absolute.append(difference)
            squared.append(difference*difference)
    count = field.grid.nx*field.grid.ny
    return dict(l1=math.fsum(absolute)/count, l2=math.sqrt(math.fsum(squared)/count),
                linf=max(absolute), continuous_norm_certified=False)


def convergence_orders(errors, spacings):
    """Observed pairwise rates; reject zero errors and nonrefining grids."""
    errors = tuple(islice(errors, 17))
    spacings = tuple(islice(spacings, 17))
    if not 2 <= len(errors) == len(spacings) <= 16:
        raise ValueError("2..16 matched error/spacing observations required")
    errors = tuple(_real(v, 'error') for v in errors)
    spacings = tuple(_real(v, 'spacing') for v in spacings)
    if any(v <= 0 for v in (*errors, *spacings)) or any(b >= a for a, b in zip(spacings, spacings[1:])):
        raise ValueError("positive errors and decreasing positive spacings required")
    return tuple(math.log(a/b)/math.log(h/k)
                 for a, b, h, k in zip(errors, errors[1:], spacings, spacings[1:]))


def discrete_fourier_multiplier(grid, dt, mode_x=1, mode_y=1):
    """Independent Fourier symbol of one periodic source-free Euler update.

    This predicts the numerical scheme, not the continuum PDE. Comparing it
    against the flux update catches indexing, sign, anisotropy and diffusion
    errors separately from spatial truncation error against fourier_profile.
    """
    import cmath
    if not isinstance(grid, TransportGrid) or (grid.boundary_x, grid.boundary_y) != ('periodic', 'periodic'):
        raise ValueError("periodic grid required for discrete Fourier analysis")
    dt = _real(dt, 'time step')
    if dt <= 0 or dt > grid.stable_dt(1)*(1+1e-12):
        raise ValueError("invalid Fourier analysis timestep")
    if type(mode_x) is not int or type(mode_y) is not int:
        raise ValueError("integer modes required")
    angles = (2*math.pi*(mode_x % grid.nx)/grid.nx, 2*math.pi*(mode_y % grid.ny)/grid.ny)
    rate = 0j
    for velocity, spacing, angle in zip((grid.velocity_x, grid.velocity_y), (grid.dx, grid.dy), angles):
        direction = 1 if velocity >= 0 else -1
        rate -= abs(velocity)/spacing*(1-cmath.exp(-1j*direction*angle))
        rate += 2*grid.diffusivity/spacing**2*(math.cos(angle)-1)
    return 1+dt*rate


def replay_transport_steps(initial, timesteps, *, source=None, start=0,
                            require_nonnegative=False, expected=None):
    """Reexecute an explicit bounded accepted-step schedule from an initial field.

    Callback identity is caller-controlled. A matching final state establishes
    reproducibility under the supplied callback, never authenticity or physical
    truth. Infinite schedules are rejected after at most MAX_STEPS+1 entries.
    """
    if not isinstance(initial, ScalarField2D):
        raise ValueError("initial ScalarField2D required")
    schedule = tuple(islice(timesteps, MAX_STEPS+1))
    if not schedule or len(schedule) > MAX_STEPS:
        raise ValueError("bounded nonempty replay schedule required")
    field, time = initial, _real(start, 'start time')
    source_changes, boundary_changes = [], []
    for step in schedule:
        dt = _real(step, 'replay timestep')
        if dt <= 0 or time+dt <= time:
            raise ValueError("replay time cannot advance")
        result = advance_transport(field, dt, time=time, source=source,
                                   require_nonnegative=require_nonnegative)
        field = result.field
        source_changes.append(result.source_change)
        boundary_changes.append(result.boundary_change)
        time += dt
    if expected is not None and (not isinstance(expected, ScalarField2D) or expected != field):
        raise ValueError("replayed transport state differs from expected state")
    source_change, boundary_change = math.fsum(source_changes), math.fsum(boundary_changes)
    return dict(final=field, end=time, steps=len(schedule), source_change=source_change,
                boundary_change=boundary_change,
                conservation_residual=field.mass-initial.mass-source_change-boundary_change,
                physical_validation=False)
