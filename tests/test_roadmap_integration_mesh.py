"""Manufactured integrals and independent mesh validation grids."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from itertools import repeat
import json
import math

import pytest

from nablamath.math.polynomials.univariate import Polynomial as P
from nablamath.math.calculus.risch import (
    LinearFactor, PrimitiveTerm, RationalIntegral, integrate_rational,
)
from nablamath.worlds.mesh.adaptive import (
    Mesh1D, adaptive_interpolate, estimate_cells, refine_mesh,
    sampled_error, uniform_mesh,
)


def polynomial_power(poly, exponent):
    result = P((1,))
    for _ in range(exponent):
        result = result*poly
    return result


def denominator_from_factors(factors, scale=1):
    result = P((scale,))
    for factor in factors:
        result = result*polynomial_power(P((-factor.root, 1)), factor.multiplicity)
    return result


@pytest.mark.parametrize('coefficients', [(0,), (1,), (2, 3, -4), (F(1, 3), F(-2, 7), F(5, 9))])
def test_polynomial_integration_exact(coefficients):
    numerator = P(coefficients)
    result = integrate_rational(numerator, P((1,)))
    assert result.verify()
    assert result.polynomial_part.derivative() == numerator
    assert result.terms == ()
    assert result.excluded_roots == ()
    expected = sum(float(c)/(i+1) for i, c in enumerate(coefficients))
    assert result.definite(0, 1) == pytest.approx(expected)


@pytest.mark.parametrize('root', [F(0), F(-2), F(3, 7)])
@pytest.mark.parametrize('multiplicity', [1, 2, 3, 5])
def test_single_pole_known_partial_fraction(root, multiplicity):
    factors = (LinearFactor(root, multiplicity),)
    denominator = denominator_from_factors(factors)
    coefficient = F(7, 3)
    result = integrate_rational(P((coefficient,)), denominator, factors)
    assert result.verify()
    assert len(result.terms) == 1
    term = result.terms[0]
    assert term.root == root
    if multiplicity == 1:
        assert (term.coefficient, term.power) == (coefficient, 0)
    else:
        assert (term.coefficient, term.power) == (coefficient/(1-multiplicity), 1-multiplicity)
    left, right = float(root)+1, float(root)+2
    expected = float(coefficient)*math.log(2) if multiplicity == 1 else float(coefficient)*(2**(1-multiplicity)-1)/(1-multiplicity)
    assert result.definite(left, right) == pytest.approx(expected)


def test_three_distinct_poles_known_decomposition():
    # 1/x + 2/(x-1) - 3/(x+2) = (8x-2)/(x(x-1)(x+2)).
    factors = (LinearFactor(0), LinearFactor(1), LinearFactor(-2))
    denominator = denominator_from_factors(factors)
    result = integrate_rational(P((-2, 8)), denominator, factors)
    assert result.verify()
    assert {(t.root, t.coefficient, t.power) for t in result.terms} == {
        (F(0), F(1), 0), (F(1), F(2), 0), (F(-2), F(-3), 0),
    }


def test_mixed_repeated_factors_and_polynomial_part():
    factors = (LinearFactor(-1, 3), LinearFactor(2, 2))
    denominator = denominator_from_factors(factors, scale=F(5, 3))
    # Manufacture integrand from independently specified primitive derivative.
    polynomial = P((3, -2, F(1, 2)))
    terms = (PrimitiveTerm(F(4, 7), -1, 0), PrimitiveTerm(-2, -1, -2),
             PrimitiveTerm(3, 2, -1))
    numerator = polynomial.derivative()*denominator
    for term in terms:
        n, d = term.derivative_pair()
        quotient, rest = denominator.divmod(d)
        assert rest.is_zero
        numerator = numerator+n*quotient
    result = integrate_rational(numerator, denominator, reversed(factors))
    assert result.verify()
    assert result.polynomial_part.derivative() == polynomial.derivative()
    assert set(result.terms) == set(terms)
    # Constants of integration differ, but primitive differences must match.
    for left, right in [(3., 4.), (-4., -3.), (0., 1.)]:
        expected = float(polynomial(F(right))-polynomial(F(left)))
        expected += sum(term.evaluate(right)-term.evaluate(left) for term in terms)
        assert result.definite(left, right) == pytest.approx(expected)


@pytest.mark.parametrize('denominator,factors', [
    (P((-2, 1)), (LinearFactor(2),)),
    (P((1, -2, 1)), (LinearFactor(1, 2),)),
    (P((-2, 1, 1)), (LinearFactor(-2), LinearFactor(1))),
    (P((F(1, 4), -1, 1)), (LinearFactor(F(1, 2), 2),)),
])
def test_automatic_low_degree_factorization(denominator, factors):
    automatic = integrate_rational(P((1,)), denominator)
    explicit = integrate_rational(P((1,)), denominator, factors)
    assert automatic == explicit


def test_preserve_removable_domain_exclusions():
    denominator = P((-1, 1))
    result = integrate_rational(denominator, denominator)
    assert result.terms == ()
    assert result.excluded_roots == (F(1),)
    assert result.verify()
    with pytest.raises(ValueError, match='excluded'):
        result.evaluate(1)
    with pytest.raises(ValueError, match='exclusion'):
        result.definite(0, 2)
    assert result.definite(2, 3) == pytest.approx(1)
    assert result.definite(3, 2) == pytest.approx(-1)
    assert result.definite(2, 2) == 0


def test_integral_replay_roundtrip_and_tampering():
    result = integrate_rational(P((2, 1)), P((-2, 1, 1)))
    payload = json.loads(json.dumps(result.to_data()))
    replay = RationalIntegral.from_data(payload)
    assert replay == result
    assert replay.definite(2, 3) == result.definite(2, 3)
    for key, replacement in [('version', 2), ('version', True), ('numerator', ['999']),
                             ('terms', []), ('factors', [])]:
        bad = deepcopy(payload)
        bad[key] = replacement
        with pytest.raises(ValueError):
            RationalIntegral.from_data(bad)
    extra = deepcopy(payload)
    extra['unexpected'] = 1
    with pytest.raises(ValueError):
        RationalIntegral.from_data(extra)
    bad_term = deepcopy(payload)
    bad_term['terms'][0]['root'] = '999'
    with pytest.raises(ValueError):
        RationalIntegral.from_data(bad_term)


def test_derivative_verifier_does_not_trust_metadata():
    result = integrate_rational(P((1,)), P((0, 1)))
    assert not replace(result, polynomial_part=P((0, 1))).verify()
    assert not replace(result, terms=(PrimitiveTerm(2, 0, 0),)).verify()
    assert not replace(result, factors=(LinearFactor(1),)).verify()
    assert not replace(result, version=123).verify()


@pytest.mark.parametrize('numerator,denominator', [
    (P((1,)), P((0,))), (P((1,)), P((1, 0, 1))),
    (P((1,)), P((-2, 0, 1))), (P((1,)), P((1, 0, 0, 1))),
])
def test_unsupported_or_invalid_integrals_explicit(numerator, denominator):
    with pytest.raises((ValueError, NotImplementedError)):
        integrate_rational(numerator, denominator)


def test_factor_and_coefficient_budgets():
    with pytest.raises(ValueError):
        integrate_rational(P((1,)), P((0, 1)), repeat(LinearFactor(0)))
    with pytest.raises(ValueError):
        integrate_rational(P((1,)), P((0, 0, 1)), (LinearFactor(0), LinearFactor(0)))
    with pytest.raises(ValueError):
        integrate_rational(P((1,)), P((0, 1)), (LinearFactor(1),))
    with pytest.raises(ValueError):
        integrate_rational(P((1,)*26), P((1,)))
    with pytest.raises(ValueError):
        integrate_rational(P((2**1024,)), P((1,)))
    with pytest.raises(ValueError):
        LinearFactor(0, True)
    with pytest.raises(ValueError):
        PrimitiveTerm(1, 0, 1)
    with pytest.raises(ValueError):
        LinearFactor(0.5)


def test_primitive_evaluation_domain_and_nonfinite():
    result = integrate_rational(P((1,)), P((0, 1)))
    for value in (math.inf, math.nan):
        with pytest.raises(ValueError):
            result.evaluate(value)
        with pytest.raises(ValueError):
            result.definite(value, 1)
    with pytest.raises(ValueError):
        PrimitiveTerm(1, 0, 0).evaluate(0)


def test_mesh_linear_profile_exact_interpolation_integration():
    mesh = uniform_mesh(lambda x: 3*x-2, -2, 4, cells=5)
    assert mesh.cell_count == 5
    assert mesh.domain == (-2, 4)
    for x in (-2, -.7, 0, 1.25, 4):
        assert mesh.interpolate(x) == pytest.approx(3*x-2)
    assert all(mesh.slope(i) == pytest.approx(3) for i in range(mesh.cell_count))
    assert mesh.integrate() == pytest.approx(6)
    assert mesh.integrate(-1, 2) == pytest.approx(-1.5)
    assert mesh.integrate(2, -1) == pytest.approx(1.5)
    assert mesh.integrate(1, 1) == 0


def test_nonuniform_mesh_localization_and_trapezoid():
    mesh = Mesh1D((0, .1, .4, 1), (0, 1, 0, 2))
    assert mesh.locate(0) == 0
    assert mesh.locate(.1) == 1
    assert mesh.locate(1) == 2
    assert mesh.widths == pytest.approx((.1, .3, .6))
    assert mesh.interpolate(.7) == pytest.approx(1)
    assert mesh.integrate() == pytest.approx(.8)


def test_quadratic_error_indicator_matches_analytic_bound():
    mesh = uniform_mesh(lambda x: x*x, 0, 1, cells=4)
    indicators = estimate_cells(mesh, lambda x: x*x, absolute_tolerance=.001,
                                second_derivative_bound=lambda a, b: 2)
    for indicator in indicators:
        exact_error = (indicator.right-indicator.left)**2 / 4
        assert indicator.sampled_error == pytest.approx(exact_error)
        assert indicator.curvature_bound == pytest.approx(exact_error)
        assert indicator.needs_refinement


def test_refinement_preserves_original_nodes_and_values():
    mesh = uniform_mesh(lambda x: x*x, 0, 1, cells=4)
    refined = refine_mesh(mesh, (1, 3, 1), lambda x: x*x)
    assert refined.cell_count == 6
    assert refined.nodes == (0, .25, .375, .5, .75, .875, 1)
    for x, value in zip(mesh.nodes, mesh.values):
        assert refined.interpolate(x) == value
    assert refine_mesh(mesh, (), lambda x: 99) == mesh


@pytest.mark.parametrize('profile,left,right', [
    (lambda x: x*x, -1, 1), (math.exp, 0, 1),
    (math.sin, 0, math.pi), (lambda x: 1/(1+25*x*x), -1, 1),
])
def test_adaptive_profiles_against_independent_dense_grid(profile, left, right):
    result = adaptive_interpolate(profile, left, right, absolute_tolerance=1e-4,
                                  max_cells=2048, max_evaluations=100000)
    assert result.converged
    assert result.reason == 'sampled_tolerance'
    assert all(not i.needs_refinement for i in result.indicators)
    # Irrational-looking validation offsets differ from estimator quarter-points.
    validation = [left+(right-left)*(i+.173205)/(2001) for i in range(2001)]
    assert sampled_error(result.mesh, profile, validation) < 1.1e-4
    assert result.evaluations >= len(result.mesh.nodes)
    assert result.history[-1].cells == result.mesh.cell_count


def test_refinement_localizes_narrow_feature():
    profile = lambda x: math.exp(-80*(x-.25)**2)
    result = adaptive_interpolate(profile, 0, 1, absolute_tolerance=1e-3)
    assert result.converged
    near = [b-a for a, b in zip(result.mesh.nodes, result.mesh.nodes[1:]) if .1 <= a <= .4]
    far = [b-a for a, b in zip(result.mesh.nodes, result.mesh.nodes[1:]) if a >= .75]
    assert max(near) < max(far)


def test_adaptive_cache_determinism_and_replay():
    calls = []
    def profile(x):
        calls.append(x)
        return x*x
    result = adaptive_interpolate(profile, 0, 1, absolute_tolerance=.001)
    assert len(calls) == len(set(calls)) == result.evaluations
    rerun = adaptive_interpolate(lambda x: x*x, 0, 1, absolute_tolerance=.001)
    assert result == rerun
    payload = json.loads(json.dumps(result.to_data()))
    mesh = Mesh1D.from_data(payload['mesh'])
    assert mesh == result.mesh
    assert mesh.interpolate(.333) == result.mesh.interpolate(.333)


@pytest.mark.parametrize('options,reason', [
    ({'max_iterations': 0}, 'iteration_budget'),
    ({'max_cells': 4}, 'cell_budget'),
    ({'max_evaluations': 5}, 'evaluation_budget'),
])
def test_budget_statuses_are_explicit(options, reason):
    result = adaptive_interpolate(lambda x: x*x, 0, 1, absolute_tolerance=1e-8, **options)
    assert not result.converged
    assert result.reason == reason
    assert result.mesh.cell_count == 4


def test_relative_tolerance_scale_invariance():
    small = adaptive_interpolate(lambda x: math.exp(x), 0, 1,
                                  absolute_tolerance=0, relative_tolerance=.001)
    large = adaptive_interpolate(lambda x: 1000*math.exp(x), 0, 1,
                                  absolute_tolerance=0, relative_tolerance=.001)
    assert small.mesh.nodes == large.mesh.nodes
    assert small.converged and large.converged


def test_sampled_estimators_do_not_claim_global_bounds():
    # This profile vanishes at all initial estimator samples but not between.
    profile = lambda x: math.sin(16*math.pi*x)
    result = adaptive_interpolate(profile, 0, 1, initial_cells=4, absolute_tolerance=1e-10)
    assert result.converged
    assert sampled_error(result.mesh, profile, [.03125]) > .99
    assert all(i.curvature_bound is None for i in result.indicators)


@pytest.mark.parametrize('nodes,values', [
    ((0,), (0,)), ((0, 0), (1, 2)), ((1, 0), (1, 2)),
    ((0, 1), (1,)), ((0, math.inf), (0, 1)), ((0, 1), (0, math.nan)),
    ((-1e308, 1e308), (0, 1)),
])
def test_invalid_mesh_shapes_and_values(nodes, values):
    with pytest.raises(ValueError):
        Mesh1D(nodes, values)


def test_invalid_mesh_queries_and_refinement():
    mesh = Mesh1D((0, 1), (0, 1))
    for x in (-1, 2, math.nan):
        with pytest.raises(ValueError):
            mesh.interpolate(x)
    with pytest.raises(ValueError):
        mesh.slope(1)
    with pytest.raises(ValueError):
        refine_mesh(mesh, repeat(0), lambda x: x)
    with pytest.raises(ValueError):
        refine_mesh(mesh, (1,), lambda x: x)
    with pytest.raises(ValueError):
        refine_mesh(mesh, (0,), lambda x: x, max_cells=1)
    with pytest.raises(ValueError):
        sampled_error(mesh, lambda x: x, repeat(.5))
    with pytest.raises(ValueError):
        sampled_error(mesh, lambda x: x, ())


def test_invalid_adaptation_inputs_and_callbacks():
    for options in ({'absolute_tolerance': 0}, {'relative_tolerance': -1},
                    {'max_iterations': -1}, {'max_cells': 0},
                    {'initial_cells': 5, 'max_cells': 4}, {'max_evaluations': 1}):
        with pytest.raises(ValueError):
            adaptive_interpolate(lambda x: x*x, 0, 1, **options)
    with pytest.raises(ValueError):
        adaptive_interpolate(lambda x: math.nan, 0, 1)
    with pytest.raises(ValueError):
        uniform_mesh(lambda x: x, 1e16, 1e16+2, cells=4)
    with pytest.raises(ValueError):
        estimate_cells(Mesh1D((0, 1), (0, 1)), lambda x: x,
                       second_derivative_bound=lambda a, b: -1)


def test_mesh_payload_rejects_unknown_version_and_keys():
    payload = Mesh1D((0, 1), (0, 1)).to_data()
    for change in ({'version': 2}, {'version': True}, {'extra': 1}, {'nodes': [0, 0]}):
        bad = dict(payload)
        bad.update(change)
        with pytest.raises(ValueError):
            Mesh1D.from_data(bad)
