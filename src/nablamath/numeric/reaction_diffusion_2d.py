"""Bounded conservative first-order reaction networks and 2D split transport.

Species undergo linear unimolecular conversions. Each edge transfers weighted
mass from one species to another; supplied positive molecular weights determine
concentration conversion ratios. Implicit Euler solves stiff reaction stages
without explicit reaction CFL restrictions. Common scalar transport coefficients
apply to all species. No nonlinear mass action, detailed-balance thermodynamics,
chemistry database, arbitrary stoichiometry, energy equation or empirical model
validation is implied. Symmetric splitting still has first-order global accuracy
because its implicit reaction and explicit transport substeps are first order.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
import math

from .transport_2d import TransportGrid, ScalarField2D, advance_transport

CONTRACT_VERSION = 1
MAX_SPECIES = 12
MAX_REACTIONS = 144
MAX_ATTEMPTS = 20000


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be finite real")
    return float(value)


def _vector(values, dimension):
    result = tuple(islice(values, dimension+1))
    if len(result) != dimension:
        raise ValueError("species concentration dimension mismatch")
    converted = tuple(_finite(v, 'concentration') for v in result)
    if any(not 0 <= v <= 1e100 for v in converted):
        raise ValueError("nonnegative bounded species concentrations required")
    return converted


@dataclass(frozen=True)
class ReactionEdge:
    source: str
    target: str
    rate: float

    def __post_init__(self):
        if (not isinstance(self.source, str) or not self.source.isidentifier()
                or not isinstance(self.target, str) or not self.target.isidentifier()
                or self.source == self.target):
            raise ValueError("distinct named source/target species required")
        rate = _finite(self.rate, 'reaction rate')
        if not 0 <= rate <= 1e9:
            raise ValueError("reaction rate outside [0,1e9]")
        object.__setattr__(self, 'rate', rate)

    def to_data(self):
        return dict(source=self.source, target=self.target, rate=self.rate)


@dataclass(frozen=True)
class ReactionNetwork:
    species: tuple[str, ...]
    weights: tuple[float, ...]
    edges: tuple[ReactionEdge, ...]

    def __post_init__(self):
        species = tuple(islice(self.species, MAX_SPECIES+1))
        weights = tuple(islice(self.weights, MAX_SPECIES+1))
        edges = tuple(islice(self.edges, MAX_REACTIONS+1))
        if (not 1 <= len(species) <= MAX_SPECIES or len(species) != len(weights)
                or any(not isinstance(name, str) or not name.isidentifier() or len(name) > 128 for name in species)
                or len(set(species)) != len(species)):
            raise ValueError("1..12 distinct named species and matched weights required")
        weights = tuple(_finite(w, 'species weight') for w in weights)
        if any(not 1e-6 <= w <= 1e6 for w in weights):
            raise ValueError("positive bounded species weights required")
        if (len(edges) > MAX_REACTIONS or any(not isinstance(e, ReactionEdge) for e in edges)
                or any(e.source not in species or e.target not in species for e in edges)):
            raise ValueError("invalid reaction edge list")
        object.__setattr__(self, 'species', species)
        object.__setattr__(self, 'weights', weights)
        object.__setattr__(self, 'edges', edges)

    @property
    def dimension(self):
        return len(self.species)

    def mass_vector(self, concentrations):
        values = _vector(concentrations, self.dimension)
        return tuple(w*c for w, c in zip(self.weights, values, strict=True))

    def total_mass(self, concentrations):
        return math.fsum(self.mass_vector(concentrations))

    def mass_generator(self):
        """Metzler generator with zero column sums: dm/dt=K*m."""
        size = self.dimension
        matrix = [[0.]*size for _ in range(size)]
        positions = {name: i for i, name in enumerate(self.species)}
        for edge in self.edges:
            i, j = positions[edge.source], positions[edge.target]
            matrix[i][i] -= edge.rate
            matrix[j][i] += edge.rate
        return tuple(tuple(row) for row in matrix)

    def derivative(self, concentrations):
        mass = self.mass_vector(concentrations)
        generator = self.mass_generator()
        return tuple(math.fsum(generator[i][j]*mass[j] for j in range(self.dimension))/self.weights[i]
                     for i in range(self.dimension))

    def to_data(self):
        return dict(version=CONTRACT_VERSION, species=list(self.species), weights=list(self.weights),
                    edges=[e.to_data() for e in self.edges], model='weighted-linear-conversions')

    @classmethod
    def from_data(cls, data):
        keys = {'version', 'species', 'weights', 'edges', 'model'}
        if (not isinstance(data, dict) or set(data) != keys or type(data['version']) is not int
                or data['version'] != CONTRACT_VERSION or data['model'] != 'weighted-linear-conversions'):
            raise ValueError("invalid reaction network schema")
        if (not isinstance(data['species'], list) or not isinstance(data['weights'], list)
                or not isinstance(data['edges'], list) or len(data['edges']) > MAX_REACTIONS):
            raise ValueError("invalid network payload arrays")
        edges = []
        for edge in data['edges']:
            if not isinstance(edge, dict) or set(edge) != {'source', 'target', 'rate'}:
                raise ValueError("invalid edge schema")
            edges.append(ReactionEdge(**edge))
        return cls(data['species'], data['weights'], tuple(edges))


def _m_matrix_solve(matrix, rhs):
    """Gaussian elimination for a nonsingular M-matrix, without positivity clipping.

    Off-diagonal elements stay nonpositive. Positive pivots and nonnegative
    transformed right-hand sides are checked. Ill-conditioned floating-point
    regimes are rejected rather than assigned a misleading success artifact.
    """
    size = len(rhs)
    data = [list(row)+[rhs[i]] for i, row in enumerate(matrix)]
    for k in range(size):
        pivot = data[k][k]
        if not math.isfinite(pivot) or pivot <= 0:
            raise ArithmeticError("implicit reaction matrix lost positive pivot")
        for i in range(k+1, size):
            factor = data[i][k]/pivot
            if factor > 0:
                raise ArithmeticError("implicit matrix lost M-matrix sign structure")
            data[i][k] = 0.
            for j in range(k+1, size+1):
                data[i][j] -= factor*data[k][j]
    result = [0.]*size
    for i in range(size-1, -1, -1):
        numerator = data[i][-1]-math.fsum(data[i][j]*result[j] for j in range(i+1, size))
        result[i] = numerator/data[i][i]
        if not math.isfinite(result[i]) or result[i] < 0:
            raise ArithmeticError("implicit reaction solve lost nonnegativity")
    return tuple(result)


@dataclass(frozen=True)
class ReactionStep:
    old: tuple[float, ...]
    new: tuple[float, ...]
    dt: float
    mass_transfers: tuple[float, ...]
    species_mass_residual: tuple[float, ...]
    total_mass_residual: float

    def to_data(self):
        return dict(old=list(self.old), new=list(self.new), dt=self.dt,
                    mass_transfers=list(self.mass_transfers),
                    species_mass_residual=list(self.species_mass_residual),
                    total_mass_residual=self.total_mass_residual,
                    method='implicit-euler-linear-m-matrix')


def implicit_reaction(network, concentrations, dt):
    """One conservative stiff stage with a per-edge transferred-mass ledger."""
    if not isinstance(network, ReactionNetwork):
        raise ValueError("ReactionNetwork required")
    old = _vector(concentrations, network.dimension)
    dt = _finite(dt, 'reaction timestep')
    if not 0 < dt <= 1e6:
        raise ValueError("reaction timestep outside (0,1e6]")
    mass = network.mass_vector(old)
    generator = network.mass_generator()
    size = network.dimension
    matrix = tuple(tuple((1. if i == j else 0.)-dt*generator[i][j] for j in range(size))
                   for i in range(size))
    updated_mass = _m_matrix_solve(matrix, mass)
    positions = {name: i for i, name in enumerate(network.species)}
    transfers = tuple(dt*edge.rate*updated_mass[positions[edge.source]] for edge in network.edges)
    net = [[] for _ in range(size)]
    for edge, value in zip(network.edges, transfers, strict=True):
        net[positions[edge.source]].append(-value)
        net[positions[edge.target]].append(value)
    residual = tuple(updated_mass[i]-mass[i]-math.fsum(net[i]) for i in range(size))
    scale = max(1., math.fsum(mass))
    if max(abs(v) for v in residual) > 1e-8*scale:
        raise ArithmeticError("implicit reaction equation residual exceeds floating tolerance")
    new = tuple(m/w for m, w in zip(updated_mass, network.weights, strict=True))
    _vector(new, size)
    return ReactionStep(old, new, dt, transfers, residual, math.fsum(updated_mass)-math.fsum(mass))


def verify_reaction_step(network, step, *, tolerance=1e-9):
    """Check the defining implicit equations and edge ledger independently."""
    try:
        tolerance = _finite(tolerance, 'verification tolerance')
        if tolerance <= 0 or not isinstance(step, ReactionStep) or not isinstance(network, ReactionNetwork):
            return False
        old = network.mass_vector(step.old)
        new = network.mass_vector(step.new)
        if len(step.mass_transfers) != len(network.edges) or not 0 < step.dt <= 1e6:
            return False
        positions = {name: i for i, name in enumerate(network.species)}
        balance = [0.]*network.dimension
        for edge, transfer in zip(network.edges, step.mass_transfers, strict=True):
            expected = step.dt*edge.rate*new[positions[edge.source]]
            if not math.isfinite(transfer) or abs(transfer-expected) > tolerance*max(1, abs(expected)):
                return False
            balance[positions[edge.source]] -= transfer
            balance[positions[edge.target]] += transfer
        scale = max(1, math.fsum(old))
        return all(abs(new[i]-old[i]-balance[i]) <= tolerance*scale for i in range(network.dimension))
    except (ValueError, TypeError, ArithmeticError):
        return False


@dataclass(frozen=True)
class ReactionTrajectory:
    times: tuple[float, ...]
    states: tuple[tuple[float, ...], ...]
    accepted_steps: int
    rejected_steps: int
    linear_solves: int
    maximum_local_error_ratio: float
    total_mass_residual: float

    @property
    def final(self):
        return self.states[-1]


def integrate_reactions(network, initial, end, *, start=0, atol=1e-9, rtol=1e-6,
                        initial_step=None, max_attempts=MAX_ATTEMPTS):
    """Adaptive first-order implicit integration by full-vs-two-half step estimates.

    Accepted states use two half steps. Error estimates are local indicators,
    not a certified bound on accumulated error. Very stiff initial layers may
    need many accepted steps despite unconditional implicit stage stability.
    """
    if not isinstance(network, ReactionNetwork):
        raise ValueError("ReactionNetwork required")
    state = _vector(initial, network.dimension)
    initial_mass = network.total_mass(state)
    start, end, atol, rtol = (_finite(v, n) for v, n in
                              ((start, 'start'), (end, 'end'), (atol, 'atol'), (rtol, 'rtol')))
    if end <= start or not math.isfinite(end-start) or atol <= 0 or rtol < 0:
        raise ValueError("ordered finite times and positive mixed tolerances required")
    if type(max_attempts) is not int or not 1 <= max_attempts <= MAX_ATTEMPTS:
        raise ValueError("invalid adaptive reaction budget")
    h = (end-start)/10 if initial_step is None else _finite(initial_step, 'initial step')
    if not 0 < h <= 1e6:
        raise ValueError("invalid initial reaction step")
    t, times, states = start, [start], [state]
    accepted, rejected, worst = 0, 0, 0.
    for attempt in range(max_attempts):
        dt = min(h, end-t)
        if t+dt <= t or dt/2 == 0:
            raise ArithmeticError("adaptive reaction time grid collapsed")
        coarse = implicit_reaction(network, state, dt)
        middle = implicit_reaction(network, state, dt/2)
        fine = implicit_reaction(network, middle.new, dt/2)
        error = max(abs(a-b)/(atol+rtol*max(abs(a), abs(b), abs(c)))
                    for a, b, c in zip(coarse.new, fine.new, state, strict=True))
        if not math.isfinite(error):
            raise ArithmeticError("reaction error estimate overflow")
        if error <= 1:
            t = end if dt == end-t else t+dt
            state = fine.new
            times.append(t)
            states.append(state)
            accepted += 1
            worst = max(worst, error)
            if t == end:
                return ReactionTrajectory(tuple(times), tuple(states), accepted, rejected, 3*(attempt+1), worst,
                                          network.total_mass(state)-initial_mass)
        else:
            rejected += 1
        factor = 5. if error == 0 else min(5., max(.1, .9/math.sqrt(error)))
        h = min(1e6, dt*factor)
    raise ArithmeticError("adaptive reaction attempt budget exhausted")


@dataclass(frozen=True)
class SpeciesField2D:
    network: ReactionNetwork
    layers: tuple[ScalarField2D, ...]

    def __post_init__(self):
        if not isinstance(self.network, ReactionNetwork):
            raise ValueError("ReactionNetwork required")
        layers = tuple(islice(self.layers, self.network.dimension+1))
        if (len(layers) != self.network.dimension or any(not isinstance(l, ScalarField2D) for l in layers)
                or any(l.grid != layers[0].grid or l.range[0] < 0 for l in layers)):
            raise ValueError("one nonnegative common-grid layer per species required")
        if layers[0].grid.nx*layers[0].grid.ny*self.network.dimension > 65536:
            raise ValueError("species-cell memory budget exceeded")
        object.__setattr__(self, 'layers', layers)

    @property
    def grid(self):
        return self.layers[0].grid

    @classmethod
    def sample(cls, network, grid, profile):
        rows = [[_vector(profile(*grid.center(i, j)), network.dimension)
                 for i in range(grid.nx)] for j in range(grid.ny)]
        return cls(network, tuple(ScalarField2D(grid, tuple(tuple(rows[j][i][k] for i in range(grid.nx))
                                                           for j in range(grid.ny)))
                                  for k in range(network.dimension)))

    @property
    def species_masses(self):
        return tuple(layer.mass*w for layer, w in zip(self.layers, self.network.weights, strict=True))

    @property
    def total_mass(self):
        return math.fsum(self.species_masses)

    def concentrations(self, i, j):
        self.grid.center(i, j)
        return tuple(layer.rows[j][i] for layer in self.layers)

    def to_data(self):
        return dict(version=CONTRACT_VERSION, network=self.network.to_data(),
                    layers=[layer.to_data() for layer in self.layers])

    @classmethod
    def from_data(cls, data):
        if (not isinstance(data, dict) or set(data) != {'version', 'network', 'layers'}
                or type(data['version']) is not int or data['version'] != CONTRACT_VERSION):
            raise ValueError("invalid species field schema")
        network = ReactionNetwork.from_data(data['network'])
        if not isinstance(data['layers'], list) or len(data['layers']) != network.dimension:
            raise ValueError("invalid species layer count")
        return cls(network, tuple(ScalarField2D.from_data(layer) for layer in data['layers']))


def react_field(field, dt):
    """Cellwise implicit conversions; return integrated per-species mass change."""
    if not isinstance(field, SpeciesField2D):
        raise ValueError("SpeciesField2D required")
    grid, network = field.grid, field.network
    updated = [[implicit_reaction(network, field.concentrations(i, j), dt).new
                for i in range(grid.nx)] for j in range(grid.ny)]
    result = SpeciesField2D(network, tuple(ScalarField2D(grid, tuple(tuple(updated[j][i][k] for i in range(grid.nx))
                                                                    for j in range(grid.ny)))
                                           for k in range(network.dimension)))
    before, after = field.species_masses, result.species_masses
    return result, tuple(b-a for a, b in zip(before, after, strict=True))


@dataclass(frozen=True)
class SplitStep:
    field: SpeciesField2D
    dt: float
    method: str
    reaction_species_change: tuple[float, ...]
    transport_boundary_change: tuple[float, ...]
    mass_residual: float


def advance_reaction_transport(field, dt, *, method='symmetric'):
    """Combine stiff local conversion with positivity-preserving 2D transport.

    symmetric = reaction half / transport full / reaction half. Both subsolvers
    are first order, so this name describes ordering only, not second-order
    Strang accuracy. All weighted internal reaction mass cancels in the ledger.
    """
    if not isinstance(field, SpeciesField2D) or method not in ('reaction_first', 'transport_first', 'symmetric'):
        raise ValueError("typed species field and supported splitting order required")
    dt = _finite(dt, 'split timestep')
    if dt <= 0 or dt > field.grid.stable_dt(1)*(1+1e-12):
        raise ValueError("split timestep violates transport CFL")
    initial_mass = field.total_mass
    reaction_change = [0.]*field.network.dimension
    boundary_change = [0.]*field.network.dimension
    current = field
    stages = (('r', dt), ('t', dt)) if method == 'reaction_first' else (
        (('t', dt), ('r', dt)) if method == 'transport_first' else (('r', dt/2), ('t', dt), ('r', dt/2)))
    for kind, step in stages:
        if kind == 'r':
            current, changes = react_field(current, step)
            reaction_change = [a+b for a, b in zip(reaction_change, changes, strict=True)]
        else:
            steps = tuple(advance_transport(layer, step, require_nonnegative=True) for layer in current.layers)
            boundary_change = [a+s.boundary_change*w for a, s, w in
                               zip(boundary_change, steps, current.network.weights, strict=True)]
            current = SpeciesField2D(current.network, tuple(s.field for s in steps))
    residual = current.total_mass-initial_mass-math.fsum(boundary_change)
    return SplitStep(current, dt, method, tuple(reaction_change), tuple(boundary_change), residual)


@dataclass(frozen=True)
class SplitRun:
    initial: SpeciesField2D
    final: SpeciesField2D
    start: float
    end: float
    steps: int
    method: str
    reaction_species_change: tuple[float, ...]
    transport_boundary_change: tuple[float, ...]
    mass_residual: float
    timesteps: tuple[float, ...]

    def to_data(self):
        return dict(version=CONTRACT_VERSION, initial=self.initial.to_data(), final=self.final.to_data(),
                    start=self.start, end=self.end, steps=self.steps, method=self.method,
                    reaction_species_change=list(self.reaction_species_change),
                    transport_boundary_change=list(self.transport_boundary_change),
                    mass_residual=self.mass_residual, timesteps=list(self.timesteps),
                    global_order=1, experimental_validation=False, energy_model_present=False)


def simulate_reaction_transport(initial, end, *, start=0, max_timestep=.01,
                                 cfl=.8, method='symmetric', max_steps=10000):
    """Fixed maximum splitting steps; transport CFL and reaction solves enforced."""
    if not isinstance(initial, SpeciesField2D):
        raise ValueError("SpeciesField2D required")
    start, end = _finite(start, 'start'), _finite(end, 'end')
    limit = _finite(max_timestep, 'maximum splitting step')
    if end <= start or not math.isfinite(end-start) or not 0 < limit <= 1e6:
        raise ValueError("finite ordered times and bounded positive step required")
    if type(max_steps) is not int or not 1 <= max_steps <= 10000:
        raise ValueError("invalid splitting step budget")
    step_bound = min(limit, initial.grid.stable_dt(cfl))
    field, time, schedule = initial, start, []
    reaction_change = [0.]*initial.network.dimension
    boundary_change = [0.]*initial.network.dimension
    while time < end:
        if len(schedule) >= max_steps:
            raise ArithmeticError("reaction-transport step budget exhausted")
        dt = min(step_bound, end-time)
        if time+dt <= time:
            raise ArithmeticError("splitting time grid collapsed")
        result = advance_reaction_transport(field, dt, method=method)
        field = result.field
        schedule.append(dt)
        time = end if dt == end-time else time+dt
        reaction_change = [a+b for a, b in zip(reaction_change, result.reaction_species_change, strict=True)]
        boundary_change = [a+b for a, b in zip(boundary_change, result.transport_boundary_change, strict=True)]
    residual = field.total_mass-initial.total_mass-math.fsum(boundary_change)
    return SplitRun(initial, field, start, end, len(schedule), method,
                    tuple(reaction_change), tuple(boundary_change), residual, tuple(schedule))


def replay_split_run(payload):
    """Strict deterministic accepted-step replay of a complete saved split run."""
    keys = {'version', 'initial', 'final', 'start', 'end', 'steps', 'method',
            'reaction_species_change', 'transport_boundary_change', 'mass_residual',
            'timesteps', 'global_order', 'experimental_validation', 'energy_model_present'}
    if (not isinstance(payload, dict) or set(payload) != keys or type(payload['version']) is not int
            or payload['version'] != CONTRACT_VERSION or payload['global_order'] != 1
            or payload['experimental_validation'] is not False or payload['energy_model_present'] is not False):
        raise ValueError("invalid split run schema or unsupported physical claim")
    initial, expected = SpeciesField2D.from_data(payload['initial']), SpeciesField2D.from_data(payload['final'])
    schedule = payload['timesteps']
    if (not isinstance(schedule, list) or type(payload['steps']) is not int
            or not 1 <= len(schedule) == payload['steps'] <= 10000):
        raise ValueError("invalid split replay schedule")
    time, end = _finite(payload['start'], 'start'), _finite(payload['end'], 'end')
    if end <= time:
        raise ValueError("invalid split replay interval")
    field = initial
    reaction_change, boundary_change = [0.]*initial.network.dimension, [0.]*initial.network.dimension
    for value in schedule:
        dt = _finite(value, 'replay step')
        if dt <= 0 or time+dt <= time or dt > end-time:
            raise ValueError("split replay schedule cannot meet declared interval")
        result = advance_reaction_transport(field, dt, method=payload['method'])
        field = result.field
        time = end if dt == end-time else time+dt
        reaction_change = [a+b for a, b in zip(reaction_change, result.reaction_species_change, strict=True)]
        boundary_change = [a+b for a, b in zip(boundary_change, result.transport_boundary_change, strict=True)]
    if time != end or field != expected:
        raise ValueError("split replay final state/time differs")
    residual = field.total_mass-initial.total_mass-math.fsum(boundary_change)
    if (list(reaction_change) != payload['reaction_species_change']
            or list(boundary_change) != payload['transport_boundary_change']
            or residual != payload['mass_residual']):
        raise ValueError("split replay ledger differs")
    return True


def compare_species_fields(left, right):
    """Area-normalized concentration and weighted-mass differences on one grid.

    These diagnostics compare two approximations. Without an independent exact
    solution, a small difference is refinement evidence, not a truth certificate.
    """
    if (not isinstance(left, SpeciesField2D) or not isinstance(right, SpeciesField2D)
            or left.network != right.network or left.grid != right.grid):
        raise ValueError("matching species networks and grids required")
    count = left.grid.nx*left.grid.ny
    l1, l2, maximum = [], [], []
    for a, b in zip(left.layers, right.layers, strict=True):
        differences = [abs(u-v) for ar, br in zip(a.rows, b.rows, strict=True)
                       for u, v in zip(ar, br, strict=True)]
        l1.append(math.fsum(differences)/count)
        l2.append(math.sqrt(math.fsum(d*d for d in differences)/count))
        maximum.append(max(differences))
    weighted = tuple(w*e for w, e in zip(left.network.weights, l1, strict=True))
    return dict(concentration_l1=tuple(l1), concentration_l2=tuple(l2),
                concentration_linf=tuple(maximum), weighted_mass_l1=weighted,
                combined_weighted_mass_l1=math.fsum(weighted),
                total_mass_difference=right.total_mass-left.total_mass,
                continuous_error_certified=False)


@dataclass(frozen=True)
class SplitRefinementRecord:
    level: int
    maximum_timestep: float
    accepted_steps: int
    mass_residual: float
    change_from_previous: float | None
    observed_temporal_order: float | None

    def to_data(self):
        return dict(level=self.level, maximum_timestep=self.maximum_timestep,
                    accepted_steps=self.accepted_steps, mass_residual=self.mass_residual,
                    change_from_previous=self.change_from_previous,
                    observed_temporal_order=self.observed_temporal_order)


@dataclass(frozen=True)
class SplitRefinement:
    final: SplitRun
    records: tuple[SplitRefinementRecord, ...]
    final_comparison: dict

    def to_data(self):
        return dict(version=CONTRACT_VERSION, finest_run=self.final.to_data(),
                    records=[r.to_data() for r in self.records],
                    final_comparison=self.final_comparison,
                    interpretation='same-grid timestep refinement differences; spatial error unchanged',
                    global_error_certified=False, experimental_validation=False)


def refine_reaction_transport(initial, end, *, initial_max_timestep=.1, levels=3,
                               start=0, cfl=.8, method='symmetric', max_steps=10000):
    """Run bounded same-grid step halving and report weighted-mass differences.

    The configured maximum step is halved, but the transport CFL can dominate
    early levels and yield identical schedules. Such levels report no observed
    order instead of inventing convergence. Spatial discretization remains
    unchanged. The total retained solution memory is one previous and one
    current run, independent of the number of refinement levels.
    """
    if type(levels) is not int or not 2 <= levels <= 6:
        raise ValueError("two to six temporal refinement levels required")
    step = _finite(initial_max_timestep, 'initial refinement timestep')
    if not 0 < step <= 1e6:
        raise ValueError("positive bounded refinement timestep required")
    previous = None
    previous_change = None
    records = []
    comparison = None
    for level in range(levels):
        current = simulate_reaction_transport(initial, end, start=start,
                                              max_timestep=step/(2**level), cfl=cfl,
                                              method=method, max_steps=max_steps)
        change, order = None, None
        if previous is not None:
            comparison = compare_species_fields(previous.final, current.final)
            change = comparison['combined_weighted_mass_l1']
            if previous_change is not None and previous_change > 0 and change > 0:
                order = math.log(previous_change/change, 2)
            previous_change = change
        records.append(SplitRefinementRecord(level, step/(2**level), current.steps,
                                              current.mass_residual, change, order))
        previous = current
    return SplitRefinement(current, tuple(records), comparison)
