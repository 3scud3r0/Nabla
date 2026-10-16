"""Independent 2D conservation, Fourier analysis, manufactured convergence and replay.

These checks validate bounded numerical contracts, not empirical adequacy of
shallow-water or passive-scalar models. No production field data are used.
"""
from dataclasses import replace
from itertools import repeat
import json
import math

import pytest

from nablamath.physics.fluids.shallow_water_2d import (
    WaterState, WaterGrid, WaterField, physical_flux, rusanov_flux,
    reflected, stable_timestep, face_fluxes, advance_water, simulate_water,
    replay_water_steps, field_error, water_cfl_numbers,
)
from nablamath.numeric.transport_2d import (
    TransportGrid, ScalarField2D, scalar_flux, transport_faces,
    advance_transport, simulate_transport, fourier_profile, scalar_error,
    convergence_orders, discrete_fourier_multiplier, replay_transport_steps,
)
from nablamath.worlds.mesh.adaptive import Mesh1D


def water_uniform(grid, depth=1, u=0, v=0):
    return WaterField.sample(grid, lambda x, y: WaterState.primitive(depth, u, v))


def scalar_uniform(grid, value=1):
    return ScalarField2D.sample(grid, lambda x, y: value)


def assert_balance(residual, tolerance=2e-12):
    assert max(abs(x) for x in residual) < tolerance


def test_water_primitive_conserved_energy_known_values():
    state = WaterState.primitive(2, 3, -4)
    assert state.vector == (2, 6, -8)
    assert state.velocity_x == 3
    assert state.velocity_y == -4
    assert state.energy(10) == 45
    assert WaterState.from_data(state.to_data()) == state
    assert WaterState.primitive(1).energy(10) == 5


@pytest.mark.parametrize('depth,u,v', [(1e-13, 0, 0), (1e10, 0, 0), (1, 1e9, 0),
                                      (math.nan, 0, 0), (1, math.inf, 0), (True, 0, 0)])
def test_water_state_rejects_unbounded_or_nonfinite(depth, u, v):
    with pytest.raises(ValueError):
        WaterState.primitive(depth, u, v)


@pytest.mark.parametrize('axis,expected', [
    ('x', (6, 38, -24)), ('y', (-8, -24, 52)),
])
def test_physical_water_flux_independent_formula(axis, expected):
    # h=2, u=3, v=-4, g=10 -> hydrostatic pressure=20.
    state = WaterState.primitive(2, 3, -4)
    assert physical_flux(state, axis, 10) == expected
    assert rusanov_flux(state, state, axis, 10) == expected


@pytest.mark.parametrize('axis', ['x', 'y'])
def test_rusanov_jump_against_explicit_reference(axis):
    left = WaterState.primitive(1.2, .4, -.2)
    right = WaterState.primitive(.7, -.3, .5)
    gravity = 9.81
    fl, fr = physical_flux(left, axis, gravity), physical_flux(right, axis, gravity)
    velocities = ((left.velocity_x, right.velocity_x) if axis == 'x'
                  else (left.velocity_y, right.velocity_y))
    speed = max(abs(velocities[0])+math.sqrt(gravity*left.depth),
                abs(velocities[1])+math.sqrt(gravity*right.depth))
    expected = tuple((fl[k]+fr[k])/2-speed*(right.vector[k]-left.vector[k])/2 for k in range(3))
    assert rusanov_flux(left, right, axis, gravity) == pytest.approx(expected)


def test_wall_reflection_flips_only_normal_momentum():
    state = WaterState.primitive(2, 3, -4)
    assert reflected(state, 'x').vector == (2, -6, -8)
    assert reflected(state, 'y').vector == (2, 6, 8)
    assert reflected(reflected(state, 'x'), 'x') == state
    flux = rusanov_flux(reflected(state, 'x'), state, 'x')
    assert flux[0] == 0
    assert flux[2] == 0
    with pytest.raises(ValueError):
        reflected(state, 'z')


@pytest.mark.parametrize('boundary_x,boundary_y', [
    ('periodic', 'periodic'), ('wall', 'wall'), ('wall', 'periodic'),
    ('outflow', 'outflow'),
])
def test_lake_at_rest_exactly_preserved(boundary_x, boundary_y):
    grid = WaterGrid(6, 4, 2, 1, boundary_x, boundary_y)
    initial = water_uniform(grid, depth=1.75)
    run = simulate_water(initial, .1)
    assert run.final == initial
    assert_balance(run.conservation_residual)
    assert run.energy_change == 0
    assert run.minimum_depth_seen == 1.75
    assert run.final.maximum_froude == 0


def test_periodic_uniform_oblique_flow_preserved():
    grid = WaterGrid(5, 7, length_x=2, length_y=3)
    initial = water_uniform(grid, depth=.9, u=1.3, v=-.4)
    run = simulate_water(initial, .03)
    assert run.final == initial
    assert run.boundary_change == (0, 0, 0)
    assert_balance(run.conservation_residual)
    assert run.final.maximum_froude == pytest.approx(math.hypot(1.3, -.4)/math.sqrt(9.81*.9))


def test_periodic_shared_faces_and_telescoping_conservation():
    grid = WaterGrid(7, 5)
    initial = WaterField.sample(grid, lambda x, y: WaterState.primitive(
        1+.05*math.cos(2*math.pi*x)*math.sin(2*math.pi*y),
        .2*math.sin(2*math.pi*y), -.1*math.cos(2*math.pi*x)))
    fx, fy = face_fluxes(initial)
    assert len(fx) == grid.ny and len(fx[0]) == grid.nx+1
    assert len(fy) == grid.ny+1 and len(fy[0]) == grid.nx
    assert all(row[0] is row[-1] for row in fx)
    assert fy[0] is fy[-1]
    step = advance_water(initial, stable_timestep(initial))
    assert step.boundary_change == (0, 0, 0)
    assert_balance(step.conservation_residual)
    assert step.field.depth_range[0] > 0


def test_wall_mass_and_boundary_momentum_pressure_balance():
    grid = WaterGrid(8, 5, boundary_x='wall', boundary_y='wall')
    initial = WaterField.sample(grid, lambda x, y: WaterState.primitive(1+.1*x, .15, -.05))
    dt = stable_timestep(initial)
    fx, fy = face_fluxes(initial)
    assert all(row[0][0] == row[-1][0] == 0 for row in fx)
    assert all(flux[0] == 0 for flux in (*fy[0], *fy[-1]))
    step = advance_water(initial, dt)
    assert step.field.integrals()[0] == pytest.approx(initial.integrals()[0], abs=1e-13)
    assert step.boundary_change[0] == 0
    expected_x = -dt*(grid.dy*sum(row[-1][1]-row[0][1] for row in fx)
                       +grid.dx*sum(fy[-1][i][1]-fy[0][i][1] for i in range(grid.nx)))
    assert step.boundary_change[1] == pytest.approx(expected_x)
    assert_balance(step.conservation_residual)


def test_outflow_mass_ledger_matches_boundary_flux():
    grid = WaterGrid(8, 4, boundary_x='outflow', boundary_y='wall')
    initial = WaterField.sample(grid, lambda x, y: WaterState.primitive(1+x/4, .3, 0))
    run = simulate_water(initial, .01)
    assert run.boundary_change[0] < 0
    assert run.final.integrals()[0]-initial.integrals()[0] == pytest.approx(run.boundary_change[0], abs=1e-12)
    assert_balance(run.conservation_residual)


def test_water_two_dimensional_dam_release_wet_positive_conservative():
    grid = WaterGrid(16, 12, boundary_x='wall', boundary_y='wall')
    initial = WaterField.sample(grid, lambda x, y: WaterState.primitive(2 if x < .4 and y < .6 else .8))
    run = simulate_water(initial, .025, snapshot_stride=2)
    assert run.steps > 1
    assert run.minimum_depth_seen >= grid.minimum_depth
    assert run.final.depth_range[1] <= initial.depth_range[1]+1e-12
    assert run.final.integrals()[0] == pytest.approx(initial.integrals()[0], abs=1e-12)
    assert run.energy_change <= 1e-10
    assert_balance(run.conservation_residual)
    assert run.snapshots[-1][0] == run.end
    assert run.snapshots[-1][1] == run.final


def test_water_exact_stationary_shear_spatial_convergence():
    # h=1, u=.2*sin(2*pi*y), v=0 solves the flat-bed 2D equations exactly.
    profile = lambda x, y: WaterState.primitive(1, .2*math.sin(2*math.pi*y), 0)
    errors, spacings = [], []
    for ny in (8, 16, 32):
        grid = WaterGrid(4, ny)
        initial = WaterField.sample(grid, profile)
        run = simulate_water(initial, .02)
        error = field_error(run.final, profile)
        assert error['l1'][0] < 1e-13
        errors.append(error['l1'][1])
        spacings.append(grid.dy)
    rates = convergence_orders(errors, spacings)
    assert all(.7 < rate < 1.2 for rate in rates)
    assert errors[2] < errors[1] < errors[0]


def test_water_cfl_uses_both_directions_and_anisotropic_cells():
    grid = WaterGrid(8, 4, length_x=2, length_y=3)
    field = water_uniform(grid, 2, 3, -1)
    c = math.sqrt(grid.gravity*2)
    expected = .4/((3+c)/grid.dx+(1+c)/grid.dy)
    assert stable_timestep(field) == pytest.approx(expected)
    numbers = water_cfl_numbers(field, expected)
    assert numbers['sum'] == pytest.approx(.4)
    with pytest.raises(ValueError, match='CFL'):
        advance_water(field, stable_timestep(field, .45)*1.01)


def test_water_positivity_violation_is_atomic_and_unclipped():
    grid = WaterGrid(4, 4, minimum_depth=.1)
    initial = WaterField.sample(grid, lambda x, y: WaterState.primitive(.2 if x < .5 else 3))
    snapshot = initial.to_data()
    with pytest.raises(ArithmeticError):
        advance_water(initial, 10, enforce_cfl=False)
    assert initial.to_data() == snapshot


def test_water_replay_exact_roundtrip_and_tamper_rejection():
    grid = WaterGrid(6, 5)
    initial = WaterField.sample(grid, lambda x, y: WaterState.primitive(1+.03*math.sin(2*math.pi*x), .1, -.1))
    state = initial
    schedule = []
    for _ in range(4):
        dt = stable_timestep(state)*.7
        schedule.append(dt)
        state = advance_water(state, dt).field
    result = replay_water_steps(initial, schedule, expected=state)
    assert result['final'] == state
    assert result['physical_validation'] is False
    assert_balance(result['conservation_residual'])
    restored = WaterField.from_data(json.loads(json.dumps(state.to_data())))
    assert restored == state
    assert replay_water_steps(initial, schedule, expected=restored)['final'] == state
    with pytest.raises(ValueError, match='differs'):
        replay_water_steps(initial, schedule, expected=initial)
    with pytest.raises(ValueError):
        replay_water_steps(initial, repeat(.001))


def test_water_run_receipt_explicit_limits():
    grid = WaterGrid(3, 3)
    initial = water_uniform(grid)
    run = simulate_water(initial, .01)
    data = json.loads(json.dumps(run.to_data()))
    assert data['experimental_validation'] is False
    assert data['global_error_certified'] is False
    assert data['method'] == 'flat-bed-2d-rusanov-euler'
    assert WaterField.from_data(data['initial']) == initial
    assert WaterField.from_data(data['final']) == run.final


@pytest.mark.parametrize('kwargs', [
    {'nx': 1, 'ny': 4}, {'nx': True, 'ny': 4}, {'nx': 100, 'ny': 100},
    {'nx': 4, 'ny': 4, 'gravity': -1}, {'nx': 4, 'ny': 4, 'length_x': math.inf},
    {'nx': 4, 'ny': 4, 'boundary_x': 'open'}, {'nx': 4, 'ny': 4, 'minimum_depth': 0},
])
def test_invalid_water_grid(kwargs):
    with pytest.raises(ValueError):
        WaterGrid(**kwargs)


def test_water_shapes_and_infinite_inputs_bounded():
    grid = WaterGrid(2, 2)
    state = WaterState(1)
    with pytest.raises(ValueError):
        WaterField(grid, repeat((state, state)))
    with pytest.raises(ValueError):
        WaterField(grid, (repeat(state), repeat(state)))
    with pytest.raises(ValueError):
        WaterField(grid, ((state,), (state,)))
    with pytest.raises(ValueError):
        WaterField(grid, ((1, 1), (1, 1)))


def test_water_budget_time_and_policy_validation():
    initial = water_uniform(WaterGrid(4, 4))
    with pytest.raises(ArithmeticError, match='budget'):
        simulate_water(initial, 1, max_steps=1)
    for kwargs in ({'cfl': 0}, {'cfl': .5}, {'max_steps': 0}, {'max_retries': 31},
                   {'snapshot_stride': -1}, {'start': 2}):
        with pytest.raises(ValueError):
            simulate_water(initial, 1, **kwargs)
    with pytest.raises(ValueError):
        advance_water(initial, -.1)
    with pytest.raises(ValueError):
        advance_water(initial, .001, enforce_cfl=1)
    with pytest.raises(ArithmeticError, match='floating time'):
        simulate_water(initial, 1e16+2, start=1e16)


def test_water_replay_and_schema_negative_cases():
    initial = water_uniform(WaterGrid(2, 2))
    for schedule in ((), (0,), (-1,), (math.nan,)):
        with pytest.raises(ValueError):
            replay_water_steps(initial, schedule)
    for data in ({}, {'version': True}, {**initial.to_data(), 'version': 2}):
        with pytest.raises(ValueError):
            WaterField.from_data(data)
    with pytest.raises(ValueError):
        WaterState.from_data({'depth': 1})
    bad = initial.to_data()
    bad['rows'][0][0]['depth'] = 0
    with pytest.raises(ValueError):
        WaterField.from_data(bad)


@pytest.mark.parametrize('velocity,expected', [(2, 5), (-2, -9), (0, -1)])
def test_scalar_flux_upwind_direction_and_diffusion(velocity, expected):
    # left=3, right=4, D=.5, dx=.5 -> diffusive flux=-1.
    assert scalar_flux(3, 4, velocity, .5, .5) == expected


def test_transport_stationary_constant_and_exact_mass():
    grid = TransportGrid(8, 6, velocity_x=.5, velocity_y=-.2, diffusivity=.03)
    initial = scalar_uniform(grid, 2.5)
    run = simulate_transport(initial, .1)
    assert run.final == initial
    assert run.conservation_residual == 0
    assert run.boundary_change == 0
    assert run.source_change == 0
    assert run.minimum_seen == run.maximum_seen == 2.5


def test_zero_transport_finishes_in_one_step_without_infinite_dt_artifact():
    grid = TransportGrid(3, 4)
    initial = ScalarField2D.sample(grid, lambda x, y: x+y)
    assert math.isinf(grid.stable_dt())
    run = simulate_transport(initial, 12)
    assert run.steps == 1
    assert run.final == initial
    assert run.end == 12


@pytest.mark.parametrize('boundary_x,boundary_y', [
    ('periodic', 'periodic'), ('no_flux', 'no_flux'), ('periodic', 'no_flux'),
])
def test_transport_shared_fluxes_conservation_all_boundaries(boundary_x, boundary_y):
    grid = TransportGrid(7, 5, velocity_x=.3, velocity_y=-.1, diffusivity=.02,
                         boundary_x=boundary_x, boundary_y=boundary_y)
    initial = ScalarField2D.sample(grid, lambda x, y: 1+x*x+.1*math.sin(3*y))
    fx, fy = transport_faces(initial)
    assert all(row[0] == row[-1] for row in fx)
    assert fy[0] == fy[-1]
    if boundary_x == 'no_flux':
        assert all(row[0] == row[-1] == 0 for row in fx)
    if boundary_y == 'no_flux':
        assert all(v == 0 for v in (*fy[0], *fy[-1]))
    run = simulate_transport(initial, .03, require_nonnegative=True)
    assert run.final.mass == pytest.approx(initial.mass, abs=1e-12)
    assert abs(run.conservation_residual) < 1e-12
    assert run.minimum_seen >= 0


def test_source_free_periodic_discrete_maximum_and_l2_principles():
    grid = TransportGrid(12, 9, velocity_x=.4, velocity_y=-.2, diffusivity=.01)
    initial = ScalarField2D.sample(grid, lambda x, y: .5+.4*math.sin(2*math.pi*x)*math.cos(2*math.pi*y))
    run = simulate_transport(initial, .1, require_nonnegative=True)
    lo, hi = initial.range
    assert run.minimum_seen >= lo-1e-14
    assert run.maximum_seen <= hi+1e-14
    assert run.final.squared_norm <= initial.squared_norm+1e-12


@pytest.mark.parametrize('u,v,diffusivity', [(.4, -.2, 0), (-.3, .5, .02), (0, 0, .1)])
def test_discrete_fourier_symbol_independent_of_face_update(u, v, diffusivity):
    import cmath
    grid = TransportGrid(11, 7, velocity_x=u, velocity_y=v, diffusivity=diffusivity)
    mode_x, mode_y = 2, -1
    kx, ky = 2*math.pi*mode_x, 2*math.pi*mode_y
    initial = ScalarField2D.sample(grid, lambda x, y: math.cos(kx*x+ky*y+.37))
    dt = grid.stable_dt(.65)
    factor = discrete_fourier_multiplier(grid, dt, mode_x, mode_y)
    step = advance_transport(initial, dt)
    for j, row in enumerate(step.field.rows):
        for i, value in enumerate(row):
            x, y = grid.center(i, j)
            expected = (factor*cmath.exp(1j*(kx*x+ky*y+.37))).real
            assert value == pytest.approx(expected, abs=3e-15)
    assert abs(factor) <= 1+1e-14


def test_fourier_continuum_reference_known_phase_decay_and_averaging():
    grid = TransportGrid(10, 8, velocity_x=.3, velocity_y=-.1, diffusivity=.02)
    t, x, y = .2, .13, .37
    profile = fourier_profile(grid, t, offset=2, amplitude=.4, mode_x=2, mode_y=-1, phase=.3)
    kx, ky = 4*math.pi, -2*math.pi
    expected = 2+.4*math.exp(-.02*(kx*kx+ky*ky)*t)*math.cos(kx*(x-.3*t)+ky*(y+.1*t)+.3)
    assert profile(x, y) == pytest.approx(expected)
    average = fourier_profile(grid, 0, offset=0, amplitude=1, mode_x=1, mode_y=0, cell_average=True)
    a, b = 0., grid.dx
    exact = (math.sin(2*math.pi*b)-math.sin(2*math.pi*a))/(2*math.pi*(b-a))
    assert average(grid.dx/2, grid.dy/2) == pytest.approx(exact)


@pytest.mark.parametrize('u,v,diffusivity,minimum_order', [
    (.4, -.2, .0, .7), (.0, .0, .05, 1.7), (.2, .1, .01, .6),
])
def test_transport_manufactured_fourier_grid_convergence(u, v, diffusivity, minimum_order):
    errors, spacings = [], []
    for cells in (8, 16, 32):
        grid = TransportGrid(cells, cells, velocity_x=u, velocity_y=v, diffusivity=diffusivity)
        initial = ScalarField2D.sample(grid, fourier_profile(grid, 0, cell_average=True))
        run = simulate_transport(initial, .1)
        reference = fourier_profile(grid, run.end, cell_average=True)
        errors.append(scalar_error(run.final, reference)['l2'])
        spacings.append(grid.dx)
    orders = convergence_orders(errors, spacings)
    assert errors[2] < errors[1] < errors[0]
    assert all(order > minimum_order for order in orders)


def test_source_only_uniform_growth_exact_ledger_and_snapshots():
    grid = TransportGrid(5, 3, length_x=2, length_y=3)
    initial = scalar_uniform(grid, .5)
    run = simulate_transport(initial, .3, max_timestep=.05, source=lambda t, x, y: 2,
                             snapshot_stride=2, require_nonnegative=True)
    assert all(v == pytest.approx(1.1) for row in run.final.rows for v in row)
    assert run.source_change == pytest.approx(3.6)
    assert run.final.mass-initial.mass == pytest.approx(run.source_change)
    assert abs(run.conservation_residual) < 1e-12
    assert run.snapshots[-1] == (run.end, run.final)


def test_time_dependent_source_uses_old_time_and_first_order_convergence():
    errors = []
    for step in (.1, .05, .025):
        initial = scalar_uniform(TransportGrid(2, 2), 0)
        run = simulate_transport(initial, 1, max_timestep=step, source=lambda t, x, y: 2*t)
        errors.append(abs(run.final.rows[0][0]-1))
    assert convergence_orders(errors, (.1, .05, .025)) == pytest.approx((1, 1), abs=1e-12)


def test_negative_source_positivity_failure_never_clips():
    initial = scalar_uniform(TransportGrid(2, 2), .1)
    original = initial.to_data()
    with pytest.raises(ArithmeticError, match='positivity'):
        advance_transport(initial, 1, source=lambda t, x, y: -1, require_nonnegative=True)
    assert initial.to_data() == original
    unconstrained = advance_transport(initial, 1, source=lambda t, x, y: -1)
    assert unconstrained.field.range == pytest.approx((-.9, -.9))
    assert unconstrained.source_change == pytest.approx(-1)


def test_transport_exact_accepted_schedule_replay_and_source_binding():
    grid = TransportGrid(5, 4, velocity_x=.2, diffusivity=.01)
    initial = ScalarField2D.sample(grid, lambda x, y: 1+x*y)
    schedule = (grid.stable_dt(.5),)*3
    state = initial
    time = 0.
    source = lambda t, x, y: t+x
    for dt in schedule:
        state = advance_transport(state, dt, time=time, source=source).field
        time += dt
    replay = replay_transport_steps(initial, schedule, source=source, expected=state)
    assert replay['final'] == state
    assert replay['end'] == time
    assert abs(replay['conservation_residual']) < 1e-12
    assert replay['physical_validation'] is False
    with pytest.raises(ValueError, match='differs'):
        replay_transport_steps(initial, schedule, source=lambda t, x, y: 0, expected=state)


def test_transport_serialization_strict_schema_and_finite_values():
    initial = ScalarField2D.sample(TransportGrid(4, 3), lambda x, y: x+y)
    payload = json.loads(json.dumps(initial.to_data()))
    assert ScalarField2D.from_data(payload) == initial
    for change in ({'version': True}, {'extra': 0}, {'rows': [[1]]}):
        bad = dict(payload)
        bad.update(change)
        with pytest.raises(ValueError):
            ScalarField2D.from_data(bad)
    payload['rows'][0][0] = math.nan
    with pytest.raises(ValueError):
        ScalarField2D.from_data(payload)


def test_transport_receipt_explicit_numerical_scope():
    initial = scalar_uniform(TransportGrid(2, 2))
    run = simulate_transport(initial, .5)
    payload = json.loads(json.dumps(run.to_data()))
    assert payload['experimental_validation'] is False
    assert payload['global_error_certified'] is False
    assert payload['method'] == 'upwind-centered-2d-euler'
    assert ScalarField2D.from_data(payload['final']) == run.final


def test_transport_cfl_matches_nonnegative_stencil_weights():
    grid = TransportGrid(10, 5, length_x=2, length_y=3, velocity_x=.4, velocity_y=-.2, diffusivity=.01)
    inverse = .4/grid.dx+.2/grid.dy+2*.01*(1/grid.dx**2+1/grid.dy**2)
    assert grid.inverse_timescale == pytest.approx(inverse)
    assert grid.stable_dt(.9) == pytest.approx(.9/inverse)
    initial = scalar_uniform(grid)
    with pytest.raises(ValueError, match='CFL'):
        advance_transport(initial, grid.stable_dt(1)*1.01)


@pytest.mark.parametrize('kwargs', [
    {'nx': 1, 'ny': 4}, {'nx': 1000, 'ny': 1000}, {'nx': 4, 'ny': True},
    {'nx': 4, 'ny': 4, 'diffusivity': -1}, {'nx': 4, 'ny': 4, 'velocity_x': math.inf},
    {'nx': 4, 'ny': 4, 'length_x': 0}, {'nx': 4, 'ny': 4, 'boundary_y': 'dirichlet'},
])
def test_invalid_transport_grid(kwargs):
    with pytest.raises(ValueError):
        TransportGrid(**kwargs)


def test_transport_resource_shape_and_callback_validation():
    grid = TransportGrid(2, 2)
    initial = scalar_uniform(grid)
    with pytest.raises(ValueError):
        ScalarField2D(grid, repeat((1, 1)))
    with pytest.raises(ValueError):
        ScalarField2D(grid, (repeat(1), repeat(1)))
    with pytest.raises(ValueError):
        replay_transport_steps(initial, repeat(.01))
    with pytest.raises(ValueError):
        simulate_transport(initial, 1, source=lambda t, x, y: 1)
    with pytest.raises(ValueError):
        advance_transport(initial, .1, source=lambda t, x, y: math.inf)
    with pytest.raises(ValueError):
        simulate_transport(initial, 1, max_timestep=0)
    with pytest.raises(ValueError):
        advance_transport(ScalarField2D.sample(grid, lambda x, y: -1), .1, require_nonnegative=True)
    with pytest.raises(ArithmeticError, match='budget'):
        simulate_transport(initial, 1, max_timestep=.1, max_steps=1)


def test_transport_time_and_replay_budget_validation():
    initial = scalar_uniform(TransportGrid(2, 2, velocity_x=1))
    with pytest.raises(ArithmeticError, match='floating time'):
        simulate_transport(initial, 1e16+2, start=1e16)
    for kwargs in ({'max_steps': 0}, {'snapshot_stride': -1}, {'cfl': 0}, {'cfl': 1.1}):
        with pytest.raises(ValueError):
            simulate_transport(initial, 1, **kwargs)
    for schedule in ((), (0,), (-1,), (math.nan,)):
        with pytest.raises(ValueError):
            replay_transport_steps(initial, schedule)


def test_reference_and_error_diagnostics_validation():
    periodic = TransportGrid(4, 4, velocity_x=1)
    no_flux = replace(periodic, boundary_x='no_flux')
    with pytest.raises(ValueError):
        fourier_profile(no_flux, 0)
    with pytest.raises(ValueError):
        fourier_profile(periodic, -1)
    with pytest.raises(ValueError):
        fourier_profile(periodic, 0, mode_x=101)
    with pytest.raises(ValueError):
        discrete_fourier_multiplier(no_flux, .001)
    with pytest.raises(ValueError):
        convergence_orders((1, 0), (.1, .05))
    with pytest.raises(ValueError):
        convergence_orders((1, .5), (.1, .2))
    with pytest.raises(ValueError):
        convergence_orders(repeat(1), repeat(.1))
    field = scalar_uniform(periodic)
    error = scalar_error(field, lambda x, y: 1)
    assert error == dict(l1=0, l2=0, linf=0, continuous_norm_certified=False)
    with pytest.raises(ValueError):
        scalar_error(field, lambda x, y: math.nan)


def test_mesh_trapezoid_short_cell_avoids_large_endpoint_sum_overflow():
    mesh = Mesh1D((0, 1e-100), (1e308, 1e308))
    assert mesh.integrate() == pytest.approx(1e208)
    assert math.isfinite(mesh.integrate())


def test_mesh_wide_cell_slope_avoids_large_difference_overflow():
    mesh = Mesh1D((0, 1e308), (-1e308, 1e308))
    assert mesh.slope(0) == pytest.approx(2)
    assert mesh.interpolate(5e307) == pytest.approx(0)
