"""Weighted reaction and reaction-transport verification against analytic systems.

All validation is mathematical/numerical. No chemical or ecological parameter
inference, thermodynamic consistency or experimental validation is implied.
"""
from copy import deepcopy
from dataclasses import replace
from itertools import repeat
import json
import math

import pytest

from nablamath.numeric.transport_2d import TransportGrid, ScalarField2D, fourier_profile, scalar_error
from nablamath.numeric.reaction_diffusion_2d import (
    ReactionEdge, ReactionNetwork, implicit_reaction, verify_reaction_step,
    integrate_reactions, SpeciesField2D, react_field,
    advance_reaction_transport, simulate_reaction_transport, replay_split_run,
)


def conversion(rate=2, weights=(1, 1)):
    return ReactionNetwork(('A', 'B'), weights, (ReactionEdge('A', 'B', rate),))


def reversible(forward=3, reverse=1, weights=(1, 1)):
    return ReactionNetwork(('A', 'B'), weights,
                           (ReactionEdge('A', 'B', forward), ReactionEdge('B', 'A', reverse)))


def reversible_exact(network, initial, time):
    # The exact invariant is weighted mass, not the unweighted concentration sum.
    kf, kr = network.edges[0].rate, network.edges[1].rate
    ma, mb = network.mass_vector(initial)
    total = ma+mb
    equilibrium_a = total*kr/(kf+kr)
    a = equilibrium_a+(ma-equilibrium_a)*math.exp(-(kf+kr)*time)
    return a/network.weights[0], (total-a)/network.weights[1]


def test_mass_generator_metzler_columns_and_named_edges():
    network = ReactionNetwork(('A', 'B', 'C'), (2, 3, 5), (
        ReactionEdge('A', 'B', 2), ReactionEdge('B', 'C', 3), ReactionEdge('C', 'A', 4)))
    matrix = network.mass_generator()
    assert matrix == ((-2, 0, 4), (2, -3, 0), (0, 3, -4))
    assert all(sum(matrix[i][j] for i in range(3)) == 0 for j in range(3))
    assert all(matrix[i][j] >= 0 for i in range(3) for j in range(3) if i != j)
    derivative = network.derivative((1, 2, 3))
    assert sum(w*d for w, d in zip(network.weights, derivative)) == pytest.approx(0, abs=1e-13)
    assert derivative == pytest.approx((28, -14/3, -42/5))


@pytest.mark.parametrize('rate,dt', [(0, .1), (2, .3), (1000, 10), (1e6, .01)])
def test_oneway_implicit_stage_closed_form_and_weighted_ledger(rate, dt):
    network = conversion(rate, weights=(2, 5))
    initial = (3., .2)
    step = implicit_reaction(network, initial, dt)
    expected_a = 3/(1+rate*dt)
    transferred_mass = 2*(3-expected_a)
    expected_b = .2+transferred_mass/5
    assert step.new == pytest.approx((expected_a, expected_b), rel=1e-10, abs=1e-14)
    assert step.mass_transfers == pytest.approx((transferred_mass,))
    assert network.total_mass(step.new) == pytest.approx(network.total_mass(initial), rel=1e-12)
    assert verify_reaction_step(network, step)
    assert max(abs(v) for v in step.species_mass_residual) < 1e-9
    assert abs(step.total_mass_residual) < 1e-9


def test_reversible_implicit_stage_independent_two_by_two_formula():
    network = reversible(3, 2, (2, 7))
    initial = (1.4, .6)
    dt = .4
    ma, mb = network.mass_vector(initial)
    # Solve mass equations explicitly; determinant=1+(kf+kr)dt.
    expected_a = ((1+2*dt)*ma+2*dt*mb)/(1+5*dt)
    expected_b = (3*dt*ma+(1+3*dt)*mb)/(1+5*dt)
    step = implicit_reaction(network, initial, dt)
    assert step.new == pytest.approx((expected_a/2, expected_b/7))
    assert verify_reaction_step(network, step)


def test_stiff_reversible_stage_approaches_equilibrium_without_explicit_reaction_cfl():
    network = reversible(30000, 10000)
    step = implicit_reaction(network, (1, 0), 10)
    assert step.new == pytest.approx((.25, .75), abs=2e-6)
    assert all(v >= 0 for v in step.new)
    assert abs(step.total_mass_residual) < 1e-10
    assert verify_reaction_step(network, step)


def test_three_species_irreversible_chain_mass_positivity_and_stage_formula():
    network = ReactionNetwork(('A', 'B', 'C'), (1, 1, 1),
                              (ReactionEdge('A', 'B', 2), ReactionEdge('B', 'C', 3)))
    dt = .2
    step = implicit_reaction(network, (1, 0, 0), dt)
    a = 1/(1+2*dt)
    b = 2*dt*a/(1+3*dt)
    c = 3*dt*b
    assert step.new == pytest.approx((a, b, c))
    assert sum(step.new) == pytest.approx(1)
    assert verify_reaction_step(network, step)


def test_reaction_cycle_uniform_equilibrium_exactly_stationary():
    network = ReactionNetwork(('A', 'B', 'C'), (1, 2, 4), (
        ReactionEdge('A', 'B', 5), ReactionEdge('B', 'C', 5), ReactionEdge('C', 'A', 5)))
    initial = (1, .5, .25)  # Equal weighted masses.
    step = implicit_reaction(network, initial, 2)
    assert step.new == pytest.approx(initial, abs=2e-15)
    assert verify_reaction_step(network, step)


def test_zero_state_and_edge_free_species_stay_zero_or_constant():
    network = conversion()
    assert implicit_reaction(network, (0, 0), 100).new == (0, 0)
    inert = ReactionNetwork(('inert',), (7,), ())
    step = implicit_reaction(inert, (3,), 20)
    assert step.new == (3,)
    assert step.mass_transfers == ()
    assert verify_reaction_step(inert, step)


def test_duplicate_edges_add_rates_and_zero_edge_does_not_change_dynamics():
    split = ReactionNetwork(('A', 'B'), (1, 1),
                            (ReactionEdge('A', 'B', 1), ReactionEdge('A', 'B', 2), ReactionEdge('B', 'A', 0)))
    merged = conversion(3)
    assert split.mass_generator() == merged.mass_generator()
    assert implicit_reaction(split, (1, 0), .4).new == implicit_reaction(merged, (1, 0), .4).new


def test_independent_stage_checker_rejects_forged_state_and_flux():
    network = conversion()
    stage = implicit_reaction(network, (1, 0), .1)
    assert verify_reaction_step(network, stage)
    assert not verify_reaction_step(network, replace(stage, new=(.5, .5)))
    assert not verify_reaction_step(network, replace(stage, mass_transfers=(99,)))
    assert not verify_reaction_step(network, replace(stage, mass_transfers=()))
    assert not verify_reaction_step(network, replace(stage, dt=-.1))
    assert not verify_reaction_step(network, stage, tolerance=0)
    # Stored residual summaries are diagnostic only; the checker recomputes the
    # actual equations rather than trusting them as proof of conservation.
    assert verify_reaction_step(network, replace(stage, total_mass_residual=999))


def test_adaptive_reaction_against_analytic_weighted_reversible_solution():
    network = reversible(3, 1, (2, 5))
    initial = (1, .2)
    result = integrate_reactions(network, initial, 1, atol=1e-10, rtol=1e-6)
    assert result.times[-1] == 1
    assert result.final == pytest.approx(reversible_exact(network, initial, 1), abs=7e-5)
    assert abs(result.total_mass_residual) < 1e-11
    assert result.maximum_local_error_ratio <= 1
    assert result.linear_solves == 3*(result.accepted_steps+result.rejected_steps)
    assert len(result.times) == len(result.states) == result.accepted_steps+1
    assert all(b > a for a, b in zip(result.times, result.times[1:]))


def test_adaptive_tolerance_refinement_reduces_analytic_error():
    network = conversion(2)
    errors = []
    steps = []
    for tolerance in (1e-2, 1e-3, 1e-4):
        run = integrate_reactions(network, (1, 0), 1, atol=tolerance/100, rtol=tolerance)
        errors.append(abs(run.final[0]-math.exp(-2)))
        steps.append(run.accepted_steps)
    assert errors[2] < errors[1] < errors[0]
    assert steps[2] > steps[1] > steps[0]


def test_adaptive_initial_generator_not_reconsumed():
    network = conversion(1)
    result = integrate_reactions(network, iter((1., 0.)), .1, rtol=1e-3)
    assert abs(result.total_mass_residual) < 1e-12
    assert result.final[0] == pytest.approx(math.exp(-.1), abs=.001)


def test_adaptive_rejects_large_initial_error_then_completes():
    result = integrate_reactions(conversion(10), (1, 0), .1, initial_step=.1,
                                 atol=1e-7, rtol=1e-3)
    assert result.rejected_steps > 0
    assert result.accepted_steps > 1
    assert result.final[0] == pytest.approx(math.exp(-1), abs=.004)


def test_reaction_network_strict_portable_roundtrip():
    network = reversible(3, 1, (2, 5))
    payload = json.loads(json.dumps(network.to_data()))
    assert ReactionNetwork.from_data(payload) == network
    for change in ({'version': True}, {'model': 'general-chemistry'}, {'extra': 1}):
        bad = dict(payload)
        bad.update(change)
        with pytest.raises(ValueError):
            ReactionNetwork.from_data(bad)
    bad = deepcopy(payload)
    bad['edges'][0]['rate'] = -1
    with pytest.raises(ValueError):
        ReactionNetwork.from_data(bad)


@pytest.mark.parametrize('source,target,rate', [
    ('A', 'A', 1), ('A', 'B', -1), ('A', 'B', 1e10),
    ('A', 'B', math.nan), ('invalid name', 'B', 1), ('A', 'B', True),
])
def test_invalid_edges(source, target, rate):
    with pytest.raises(ValueError):
        ReactionEdge(source, target, rate)


def test_network_and_stage_resource_bounds():
    with pytest.raises(ValueError):
        ReactionNetwork(repeat('A'), repeat(1), ())
    with pytest.raises(ValueError):
        ReactionNetwork(('A', 'B'), (1, 1), repeat(ReactionEdge('A', 'B', 1)))
    with pytest.raises(ValueError):
        ReactionNetwork(('A', 'A'), (1, 1), ())
    with pytest.raises(ValueError):
        ReactionNetwork(('A',), (0,), ())
    with pytest.raises(ValueError):
        ReactionNetwork(('A',), (1,), (ReactionEdge('A', 'B', 1),))
    network = conversion()
    for initial in (repeat(1), (1,), (-1, 2), (math.inf, 0)):
        with pytest.raises(ValueError):
            implicit_reaction(network, initial, .1)
    for dt in (0, -1, 1e7, math.nan, True):
        with pytest.raises(ValueError):
            implicit_reaction(network, (1, 0), dt)


def test_adaptive_reaction_budget_and_nonadvancing_time():
    network = conversion()
    with pytest.raises(ArithmeticError, match='budget'):
        integrate_reactions(network, (1, 0), 1, max_attempts=1, initial_step=1, atol=1e-15)
    with pytest.raises(ArithmeticError, match='collapsed'):
        integrate_reactions(network, (1, 0), 1e16+2, start=1e16, initial_step=.01)
    for options in ({'atol': 0}, {'rtol': -1}, {'max_attempts': 0}, {'initial_step': 0}):
        with pytest.raises(ValueError):
            integrate_reactions(network, (1, 0), 1, **options)


def test_cellwise_reactions_preserve_weighted_mass_and_have_nontrivial_species_exchange():
    network = conversion(1000, (2, 5))
    grid = TransportGrid(5, 4)
    initial = SpeciesField2D.sample(network, grid, lambda x, y: (1+x*y, .1))
    final, change = react_field(initial, .2)
    assert final.total_mass == pytest.approx(initial.total_mass, abs=1e-11)
    assert change[0] < 0 < change[1]
    assert sum(change) == pytest.approx(0, abs=1e-11)
    for j in range(grid.ny):
        for i in range(grid.nx):
            old = initial.concentrations(i, j)
            expected = implicit_reaction(network, old, .2).new
            assert final.concentrations(i, j) == expected


@pytest.mark.parametrize('method', ['reaction_first', 'transport_first', 'symmetric'])
def test_split_uniform_reaction_matches_analytic_discrete_stage_order(method):
    network = conversion(2)
    initial = SpeciesField2D.sample(network, TransportGrid(3, 4), lambda x, y: (1, 0))
    dt = .2
    step = advance_reaction_transport(initial, dt, method=method)
    expected_a = (1+2*dt/2)**-2 if method == 'symmetric' else (1+2*dt)**-1
    for row in step.field.layers[0].rows:
        assert row == pytest.approx((expected_a,)*initial.grid.nx)
    assert abs(step.mass_residual) < 1e-12
    assert sum(step.reaction_species_change) == pytest.approx(0, abs=1e-12)
    assert step.transport_boundary_change == (0, 0)


@pytest.mark.parametrize('boundary', ['periodic', 'no_flux'])
def test_coupled_2d_stiff_conversion_conserves_mass_and_nonnegative_cells(boundary):
    network = reversible(300, 100, (2, 5))
    grid = TransportGrid(8, 6, velocity_x=.2, velocity_y=-.1, diffusivity=.02,
                         boundary_x=boundary, boundary_y=boundary)
    initial = SpeciesField2D.sample(network, grid, lambda x, y: (1+.1*math.cos(2*math.pi*x), .2*y))
    run = simulate_reaction_transport(initial, .1, max_timestep=.01)
    assert run.final.total_mass == pytest.approx(initial.total_mass, abs=2e-11)
    assert abs(run.mass_residual) < 2e-11
    assert all(layer.range[0] >= 0 for layer in run.final.layers)
    assert sum(run.reaction_species_change) == pytest.approx(0, abs=2e-11)
    assert all(v == 0 for v in run.transport_boundary_change)


def test_coupled_reaction_transport_analytic_fourier_mode():
    # A_t=L A-k A, B_t=L B+k A, with the same constant transport L.
    # Thus A=e^-kt Q and B=(1-e^-kt)Q for Q_t=LQ and B(0)=0.
    network = conversion(2)
    errors = []
    for cells in (8, 16, 32):
        grid = TransportGrid(cells, cells, diffusivity=.03)
        q0 = fourier_profile(grid, 0, cell_average=True)
        initial = SpeciesField2D.sample(network, grid, lambda x, y: (q0(x, y), 0))
        run = simulate_reaction_transport(initial, .1, max_timestep=grid.dx**2/4)
        qt = fourier_profile(grid, .1, cell_average=True)
        expected_a = lambda x, y: math.exp(-.2)*qt(x, y)
        expected_b = lambda x, y: (1-math.exp(-.2))*qt(x, y)
        error_a = scalar_error(run.final.layers[0], expected_a)['l2']
        error_b = scalar_error(run.final.layers[1], expected_b)['l2']
        errors.append(max(error_a, error_b))
        assert abs(run.mass_residual) < 2e-11
    assert errors[2] < errors[1]/3
    assert errors[1] < errors[0]/3


def test_symmetric_splitting_declares_first_order_and_temporal_refinement():
    network = conversion(2)
    initial = SpeciesField2D.sample(network, TransportGrid(2, 2), lambda x, y: (1, 0))
    errors = []
    for dt in (.1, .05, .025):
        run = simulate_reaction_transport(initial, 1, max_timestep=dt, method='symmetric')
        errors.append(abs(run.final.layers[0].rows[0][0]-math.exp(-2)))
        payload = run.to_data()
        assert payload['global_order'] == 1
        assert payload['energy_model_present'] is False
        assert payload['experimental_validation'] is False
    assert 1.8 < errors[0]/errors[1] < 2.2
    assert 1.8 < errors[1]/errors[2] < 2.2


def test_species_field_and_complete_run_portable_replay():
    network = reversible(3, 1, (2, 5))
    grid = TransportGrid(5, 4, velocity_x=.2, diffusivity=.01)
    initial = SpeciesField2D.sample(network, grid, lambda x, y: (1+x*y, .2))
    payload = json.loads(json.dumps(initial.to_data()))
    assert SpeciesField2D.from_data(payload) == initial
    run = simulate_reaction_transport(initial, .07, max_timestep=.01)
    saved = json.loads(json.dumps(run.to_data()))
    assert replay_split_run(saved)
    restored = SpeciesField2D.from_data(saved['final'])
    assert restored == run.final
    assert run.steps == len(run.timesteps)


def test_split_replay_rejects_field_ledger_order_schedule_and_claim_forgery():
    initial = SpeciesField2D.sample(conversion(), TransportGrid(3, 3), lambda x, y: (1+x, 0))
    run = simulate_reaction_transport(initial, .03, max_timestep=.01)
    payload = run.to_data()
    modifications = (
        ('experimental_validation', True), ('global_order', 2), ('energy_model_present', True),
        ('method', 'unrestricted-chemistry'), ('steps', 999), ('mass_residual', 1),
        ('end', .04), ('reaction_species_change', [0, 0]),
    )
    for key, replacement in modifications:
        bad = deepcopy(payload)
        bad[key] = replacement
        with pytest.raises((ValueError, ArithmeticError)):
            replay_split_run(bad)
    bad = deepcopy(payload)
    bad['final']['layers'][0]['rows'][0][0] += .1
    with pytest.raises(ValueError, match='differs'):
        replay_split_run(bad)
    bad = deepcopy(payload)
    bad['timesteps'][0] = 0
    with pytest.raises(ValueError):
        replay_split_run(bad)


def test_species_shape_common_grid_and_positive_layer_requirements():
    network = conversion()
    grid = TransportGrid(2, 2)
    positive = ScalarField2D.sample(grid, lambda x, y: 1)
    negative = ScalarField2D.sample(grid, lambda x, y: -1)
    other = ScalarField2D.sample(TransportGrid(3, 2), lambda x, y: 1)
    for layers in ((positive,), (positive, negative), (positive, other), repeat(positive)):
        with pytest.raises(ValueError):
            SpeciesField2D(network, layers)
    with pytest.raises(ValueError):
        SpeciesField2D.sample(network, grid, lambda x, y: (1,))
    field = SpeciesField2D(network, (positive, positive))
    with pytest.raises(ValueError):
        field.concentrations(-1, 0)


def test_split_budget_policy_and_time_validation():
    initial = SpeciesField2D.sample(conversion(), TransportGrid(2, 2, velocity_x=1), lambda x, y: (1, 0))
    with pytest.raises(ValueError):
        advance_reaction_transport(initial, 1)
    with pytest.raises(ValueError):
        advance_reaction_transport(initial, .01, method='strang-second-order')
    with pytest.raises(ArithmeticError, match='budget'):
        simulate_reaction_transport(initial, 1, max_timestep=.01, max_steps=1)
    with pytest.raises(ArithmeticError, match='collapsed'):
        simulate_reaction_transport(initial, 1e16+2, start=1e16)
    for options in ({'max_timestep': 0}, {'max_steps': 0}, {'cfl': 1.1}, {'start': 2}):
        with pytest.raises(ValueError):
            simulate_reaction_transport(initial, 1, **options)


def test_weighted_field_difference_diagnostics_against_hand_computation():
    from nablamath.numeric.reaction_diffusion_2d import compare_species_fields
    network = conversion(weights=(2, 5))
    grid = TransportGrid(2, 2)
    left = SpeciesField2D.sample(network, grid, lambda x, y: (1, 2))
    right = SpeciesField2D.sample(network, grid, lambda x, y: (1.5, 1.8))
    comparison = compare_species_fields(left, right)
    assert comparison['concentration_l1'] == pytest.approx((.5, .2))
    assert comparison['concentration_l2'] == pytest.approx((.5, .2))
    assert comparison['concentration_linf'] == pytest.approx((.5, .2))
    assert comparison['weighted_mass_l1'] == pytest.approx((1, 1))
    assert comparison['combined_weighted_mass_l1'] == pytest.approx(2)
    assert comparison['total_mass_difference'] == pytest.approx(0)
    assert comparison['continuous_error_certified'] is False
    with pytest.raises(ValueError):
        compare_species_fields(left, SpeciesField2D.sample(network, TransportGrid(3, 2), lambda x, y: (1, 2)))


def test_temporal_refinement_reports_first_order_without_global_error_claim():
    from nablamath.numeric.reaction_diffusion_2d import refine_reaction_transport
    initial = SpeciesField2D.sample(conversion(2), TransportGrid(2, 2), lambda x, y: (1, 0))
    result = refine_reaction_transport(initial, 1, initial_max_timestep=.1, levels=4)
    assert len(result.records) == 4
    changes = [r.change_from_previous for r in result.records[1:]]
    assert changes[2] < changes[1] < changes[0]
    assert result.records[-1].observed_temporal_order == pytest.approx(1, abs=.1)
    assert abs(result.final.mass_residual) < 1e-12
    payload = result.to_data()
    assert payload['global_error_certified'] is False
    assert payload['experimental_validation'] is False
    assert replay_split_run(json.loads(json.dumps(payload['finest_run'])))


def test_refinement_does_not_invent_order_when_cfl_controls_identical_schedules():
    from nablamath.numeric.reaction_diffusion_2d import refine_reaction_transport
    network = ReactionNetwork(('inert',), (1,), ())
    grid = TransportGrid(2, 2, velocity_x=100)
    initial = SpeciesField2D.sample(network, grid, lambda x, y: (1,))
    result = refine_reaction_transport(initial, .01, initial_max_timestep=1, levels=3)
    assert all(record.change_from_previous in (None, 0) for record in result.records)
    assert all(record.observed_temporal_order is None for record in result.records)
    for levels in (1, 7, True):
        with pytest.raises(ValueError):
            refine_reaction_transport(initial, .01, levels=levels)
