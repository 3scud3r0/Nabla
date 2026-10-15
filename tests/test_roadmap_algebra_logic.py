"""Exact quadratic identities and combined-theory counterexamples."""
from dataclasses import replace
from fractions import Fraction as F
import builtins
import pytest
from nablamath.math.algebra.galois import quadratic_galois, QuadraticElement
from nablamath.math.logic.smt_linear import LinearInequality, equality
from nablamath.math.logic.smt_combination import (
    FunctionApplication as App, solve_combined_rational, verify_combined_model,
)


@pytest.mark.parametrize('coefficients,degree,group,roots', [
    ((1, 0, -2), 2, 'C2', ()), ((1, 0, 1), 2, 'C2', ()),
    ((1, -3, 2), 1, 'trivial', (F(1), F(2))),
    ((1, -2, 1), 1, 'trivial', (F(1),)),
    ((F(1, 2), F(-1, 2), F(-1)), 1, 'trivial', (F(-1), F(2))),
])
def test_quadratic_classification(coefficients, degree, group, roots):
    result = quadratic_galois(*coefficients)
    assert (result.splitting_degree, result.group, result.rational_roots) == (degree, group, roots)
    assert result.verify(*coefficients)
    assert not replace(result, discriminant=result.discriminant+1).verify(*coefficients)
    if degree == 2:
        d, center, scale = result.discriminant, result.root_center, result.radical_scale
        root = QuadraticElement(center, scale, d)
        a, b, c = coefficients
        value = QuadraticElement(a, 0, d)*root*root + QuadraticElement(b, 0, d)*root + QuadraticElement(c, 0, d)
        assert (value.a, value.b) == (0, 0)


def test_quadratic_field_galois_automorphism():
    x, y = QuadraticElement(1, 2, 3), QuadraticElement(F(3, 2), -1, 3)
    one = QuadraticElement(1, 0, 3)
    assert x * x.inverse() == one
    assert x.conjugate().conjugate() == x
    assert (x+y).conjugate() == x.conjugate()+y.conjugate()
    assert (x*y).conjugate() == x.conjugate()*y.conjugate()
    assert x*x.conjugate() == QuadraticElement(x.norm, 0, 3)
    assert (x*y).norm == x.norm*y.norm
    with pytest.raises(ZeroDivisionError):
        QuadraticElement(0, 0, 3).inverse()
    with pytest.raises(ValueError):
        QuadraticElement(1, 2, 4)
    with pytest.raises(ValueError):
        x + QuadraticElement(1, 2, 2)
    with pytest.raises(ValueError):
        quadratic_galois(0, 1, 1)
    with pytest.raises(ValueError):
        quadratic_galois(2**4096, 1, 1)


def _backend():
    pytest.importorskip('z3')


def test_combination_inconsistency_requires_both_theories():
    _backend()
    constraints = (*equality({'x': 1, 'y': -1}, 0),
                   LinearInequality({'a': 1, 'b': -1}, -1))
    applications = (App('f', ('x',), 'a'), App('f', ('y',), 'b'))
    assert solve_combined_rational(constraints).status == 'sat'
    assert solve_combined_rational((), applications).status == 'sat'
    result = solve_combined_rational(constraints, applications)
    assert result.status == 'unsat'
    assert 'no independent' in result.reason


def test_combined_exact_rational_model():
    _backend()
    constraints = (*equality({'x': 3}, 1), *equality({'y': 1}, F(1, 3)),
                   *equality({'a': 1}, F(2, 7)))
    applications = (App('f', ('x',), 'a'), App('f', ('y',), 'b'), App('g', ('b', 'x'), 'z'))
    result = solve_combined_rational(constraints, applications)
    assert result.status == 'sat'
    assert dict(result.model)['x'] == F(1, 3)
    assert dict(result.model)['b'] == F(2, 7)
    assert verify_combined_model(constraints, applications, result.model)


def test_independent_model_checker_rejects_forgery():
    apps = (App('f', ('x',), 'a'), App('f', ('y',), 'b'))
    good = (('x', F(1)), ('y', F(1)), ('a', F(2)), ('b', F(2)))
    bad = good[:-1] + (('b', F(3)),)
    assert verify_combined_model((), apps, good)
    assert not verify_combined_model((), apps, bad)
    assert not verify_combined_model((), apps, good[:-1])
    assert not verify_combined_model((), apps, good + (good[0],))
    assert not verify_combined_model((LinearInequality({'x': 1}, 0),), apps, good)
    assert not verify_combined_model((), (App('f', ('x',), 'a'), App('f', ('x', 'y'), 'b')), good)


def test_solver_empty_and_false_constant():
    _backend()
    assert solve_combined_rational(()).status == 'sat'
    assert solve_combined_rational((LinearInequality({}, -1),)).status == 'unsat'


def test_invalid_contracts():
    with pytest.raises(ValueError):
        App('f', (), 'x')
    with pytest.raises(ValueError):
        solve_combined_rational((), (App('f', ('x',), 'a'), App('f', ('x', 'y'), 'b')))
    with pytest.raises(ValueError):
        solve_combined_rational((), timeout_ms=0)
    with pytest.raises(ValueError):
        solve_combined_rational((LinearInequality({'x': 2**4096}, 0),))


def test_missing_backend_explicit_status(monkeypatch):
    original = builtins.__import__
    def without_z3(name, *args, **kwargs):
        if name == 'z3':
            raise ImportError('simulated absent optional dependency')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', without_z3)
    result = solve_combined_rational(())
    assert result.status == 'unavailable'
    assert not result.model


def test_infinite_inputs_are_bounded():
    from itertools import repeat
    constraint = LinearInequality({'x': 1}, 1)
    call = App('f', ('x',), 'a')
    with pytest.raises(ValueError, match='invalid function application'):
        App('f', repeat('x'), 'a')
    with pytest.raises(ValueError, match='budget'):
        solve_combined_rational(repeat(constraint))
    with pytest.raises(ValueError, match='budget'):
        solve_combined_rational((), repeat(call))
    assert not verify_combined_model(repeat(constraint), (), ())
    assert not verify_combined_model((), repeat(call), ())
    assert not verify_combined_model((), (), repeat(('x', F(1))))
