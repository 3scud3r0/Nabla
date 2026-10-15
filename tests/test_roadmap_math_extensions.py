"""Independent analytic identities and reference results for bounded APIs."""
import math
from dataclasses import replace
from fractions import Fraction
import pytest
from nablamath.math.calculus.transcendentals import lambert_w
from nablamath.math.linear_algebra.matrices import Matrix, identity
from nablamath.math.linear_algebra.exact_decompositions import pivoted_lu
from nablamath.math.number_theory.factorization_advanced import (
    is_prime64, factorize64, verify_factorization,
)
from nablamath.numeric.stiff_ode import backward_euler


@pytest.mark.parametrize('w,branch', [(-20., -1), (-2., -1), (-.8, 0), (-.01, 0),
                                      (1., 0), (10., 0), (500., 0)])
def test_lambert_inverse_known_values(w, branch):
    assert lambert_w(w * math.exp(w), branch) == pytest.approx(w, rel=1e-11)


@pytest.mark.parametrize('x', [1e-300, -1e-300, 1e300])
def test_lambert_extreme_finite_domains(x):
    w = lambert_w(x)
    assert w * math.exp(w) == pytest.approx(x, rel=1e-10, abs=0)


def test_lambert_domains_and_budget():
    assert lambert_w(-1 / math.e) == -1
    assert lambert_w(-1 / math.e, -1) == -1
    assert lambert_w(0) == 0
    for x, branch in [(-1, 0), (0, -1), (1, -1), (math.inf, 0)]:
        with pytest.raises(ValueError):
            lambert_w(x, branch)
    with pytest.raises(ArithmeticError):
        lambert_w(3, max_iterations=1)


@pytest.mark.parametrize('rows', [((0, 2), (3, 4)), ((0, 1, 1), (2, 0, 3), (4, 5, 6)),
                                    ((0, 1), (0, 2)), ((1, 2), (2, 4)),
                                    ((Fraction(1, 3), 2), (3, Fraction(7, 2)))])
def test_exact_lu_certificate(rows):
    a = Matrix(rows)
    result = pivoted_lu(a)
    assert result.verify(a)
    assert result.permutation @ a == result.lower @ result.upper
    if a.shape[0] == 2 and a.rows[0][0] == 0 and a.rows[1][0]:
        assert result.permutation != identity(2)
    assert not replace(result, upper=identity(a.shape[0])).verify(a)


def test_lu_reject_rectangular():
    with pytest.raises(ValueError):
        pivoted_lu(Matrix(((1, 2, 3),)))


@pytest.mark.parametrize('n,factors', [(1, ()), (2, (2,)), (81, (3, 3, 3, 3)),
    (600851475143, (71, 839, 1471, 6857)), (1000003 * 1000033, (1000003, 1000033)),
    (2**63, (2,) * 63)])
def test_factorization_known_reference(n, factors):
    assert factorize64(n) == factors
    assert verify_factorization(n, factors)
    assert not verify_factorization(n, factors + (2,))


def test_primality_trial_division_independent():
    for n in range(2000):
        reference = n >= 2 and all(n % p for p in range(2, math.isqrt(n) + 1))
        assert is_prime64(n) == reference
    assert is_prime64(18446744073709551557)
    assert not is_prime64(341550071728321)
    with pytest.raises(ValueError):
        is_prime64(2**64)
    with pytest.raises(ArithmeticError):
        factorize64(1000003 * 1000033, max_iterations=1)


def test_backward_euler_stiff_decay_reference():
    result = backward_euler(lambda t, y: -1000 * y, lambda t, y: -1000,
                            1., 0., .5, 5, tolerance=1e-16)
    assert result.values[-1] == pytest.approx(101**-5, rel=1e-4, abs=1e-16)
    assert all(abs(y) <= 1 for y in result.values)


def test_backward_euler_refines_against_analytic_solution():
    errors = []
    for steps in (20, 40, 80):
        result = backward_euler(lambda t, y: -y, lambda t, y: -1, 1., 0., 1., steps)
        errors.append(abs(result.values[-1] - math.exp(-1)))
    assert errors[2] < errors[1] < errors[0]


def test_implicit_event_linear_trajectory():
    result = backward_euler(lambda t, y: -1, lambda t, y: 0, 1., 0., 2., 8,
                            event=lambda t, y: y - .3)
    assert result.event_time == pytest.approx(.7)
    assert result.values[-1] == pytest.approx(.3)
    initial = backward_euler(lambda t, y: 1, lambda t, y: 0, 0., 0., 2., 8,
                             event=lambda t, y: y)
    assert initial.event_time == 0


def test_implicit_failure_paths():
    with pytest.raises(ArithmeticError):
        backward_euler(lambda t, y: y + 1, lambda t, y: 1, 0., 0., 1., 1)
    with pytest.raises(ValueError):
        backward_euler(lambda t, y: math.nan, lambda t, y: 0, 0., 0., 1., 1)
    with pytest.raises(ArithmeticError):
        backward_euler(lambda t, y: -y*y, lambda t, y: -2*y, 1., 0., 1., 1,
                       max_iterations=1)


@pytest.mark.parametrize('branch', [0, -1])
def test_lambert_branchpoint_independent_decimal_newton(branch):
    from decimal import Decimal, localcontext
    x = math.nextafter(-1 / math.e, 0)
    with localcontext() as context:
        context.prec = 70
        dx = Decimal.from_float(x)
        offset = (2 * (1 + dx * Decimal(1).exp())).sqrt()
        reference = -1 + offset if branch == 0 else -1 - offset
        for _ in range(20):
            exp = reference.exp()
            reference -= (reference*exp-dx)/(exp*(reference+1))
        assert abs(lambert_w(x, branch) - float(reference)) < 1e-13


def test_implicit_last_newton_update_is_checked():
    result = backward_euler(lambda t, y: -y, lambda t, y: -1,
                            1., 0., 1., 1, max_iterations=1)
    assert result.values[-1] == .5


def test_implicit_rejects_unrepresentable_time_grid():
    with pytest.raises(ValueError, match='not representable'):
        backward_euler(lambda t, y: -y, lambda t, y: -1,
                       1., 1e16, 1e16+2, 100)
