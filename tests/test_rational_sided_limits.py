"""Analytic, independent-oracle, domain and adversarial replay checks."""

from copy import deepcopy
from fractions import Fraction

import pytest

from nablamath.calc.notebook import Notebook
from nablamath.calc.session import CalculationSession
from nablamath.core.semantic_ir import fingerprint
from nablamath.math.calculus.limits import rational_sided_limit, verify_rational_limit


@pytest.mark.parametrize("source,point,status,value,left,right", [
    ("1/x", 0, "does_not_exist", None, "negative_infinity", "positive_infinity"),
    ("-1/x", 0, "does_not_exist", None, "positive_infinity", "negative_infinity"),
    ("1/x**2", 0, "positive_infinity", None, "positive_infinity", "positive_infinity"),
    ("-1/x**4", 0, "negative_infinity", None, "negative_infinity", "negative_infinity"),
    ("(x**2-1)/(x-1)", 1, "finite", "2", "finite", "finite"),
    ("(x-2)**3/(x-2)**2", 2, "finite", "0", "finite", "finite"),
    ("(2*x-1)/(3*x+2)", "1/2", "finite", "0", "finite", "finite"),
    ("0/x", 0, "finite", "0", "finite", "finite"),
    ("3", "-2/7", "finite", "3", "finite", "finite"),
    ("1/(x-2)**3", 2, "does_not_exist", None, "negative_infinity", "positive_infinity"),
])
def test_analytic_finite_limits(source, point, status, value, left, right):
    receipt = rational_sided_limit(source, point)
    assert receipt['result'] == {'status': status, 'value': value}
    assert receipt['left']['status'] == left
    assert receipt['right']['status'] == right
    assert verify_rational_limit(receipt)


@pytest.mark.parametrize("source,point,status,value", [
    ("x**3", "+infinity", "positive_infinity", None),
    ("x**3", "-infinity", "negative_infinity", None),
    ("-x**4", "-infinity", "negative_infinity", None),
    ("(3*x**2+1)/(2*x**2-5)", "+infinity", "finite", "3/2"),
    ("(3*x**2+1)/(2*x**2-5)", "-infinity", "finite", "3/2"),
    ("(x+1)/(x**2+1)", "-infinity", "finite", "0"),
    ("0/x", "+infinity", "finite", "0"),
    ("1/(1/x)", "-infinity", "negative_infinity", None),
])
def test_analytic_infinite_limits(source, point, status, value):
    receipt = rational_sided_limit(source, point)
    assert receipt['result'] == {'status': status, 'value': value}
    assert receipt['defined_at_point'] is None
    assert receipt['left'] is receipt['right'] is None
    assert verify_rational_limit(receipt)


@pytest.mark.parametrize("source", ["x/x", "0/x", "(x**2-1)/(x-1)", "(1/(x-1))**0"])
def test_removable_holes_retain_original_domain(source):
    point = 0 if source in ('x/x', '0/x') else 1
    receipt = rational_sided_limit(source, point)
    assert receipt['result']['status'] == 'finite'
    assert receipt['defined_at_point'] is False
    assert receipt['witness']['domain_guards']
    assert rational_sided_limit(source, point+2)['defined_at_point'] is True


@pytest.mark.parametrize("source", ["1/0", "1/(x-x)", "(x-x)**0", "0*(1/0)"])
def test_empty_domains_are_not_finite_limits(source):
    with pytest.raises(ValueError):
        rational_sided_limit(source, 0)


@pytest.mark.parametrize("direction,status", [('left','negative_infinity'), ('right','positive_infinity')])
def test_explicit_direction(direction, status):
    result = rational_sided_limit('1/x', 0, direction=direction)
    assert result['result']['status'] == status
    assert verify_rational_limit(result)


@pytest.mark.parametrize("source,point,direction", [
    ('sin(x)', 0, 'both'), ('x+y', 0, 'both'), ('x**(1/2)', 0, 'both'),
    ('x', 0.5, 'both'), ('x', True, 'both'), ('x', 'infinity', 'both'),
    ('x', '+infinity', 'left'), ('x', 0, 'up'), ('x', [], 'both'),
    ('x**65', 0, 'both'), ('', 0, 'both'), (None, 0, 'both'),
])
def test_outside_profile_rejected(source, point, direction):
    with pytest.raises(ValueError):
        rational_sided_limit(source, point, direction=direction)


def rehash(receipt):
    receipt['limit_id'] = fingerprint({k: v for k, v in receipt.items() if k != 'limit_id'})
    return receipt


@pytest.mark.parametrize("mutation", [
    lambda r: r['result'].update(value='123'),
    lambda r: r['left'].update(status='positive_infinity'),
    lambda r: r['witness'].update(denominator_order=7),
    lambda r: r['witness'].update(domain_guards=[]),
    lambda r: r.update(defined_at_point=True),
    lambda r: r.update(formal_proof=True),
    lambda r: r.update(schema_version=True),
    lambda r: r.update(profile='unrestricted'),
    lambda r: r.update(extra='ignored?'),
    lambda r: r['request'].update(direction='right'),
])
def test_rehashed_forgery_is_rejected(mutation):
    receipt = deepcopy(rational_sided_limit('1/x', 0))
    mutation(receipt)
    with pytest.raises(ValueError):
        verify_rational_limit(rehash(receipt))


@pytest.mark.parametrize('receipt', [None, [], {}, {'request': []}, {'request': {'source': 'x'}}])
def test_malformed_receipt(receipt):
    with pytest.raises(ValueError):
        verify_rational_limit(receipt)


def test_point_must_fit_serialized_replay_budget():
    point = Fraction(2**255-1, 2**255-3)
    with pytest.raises(ValueError, match='representação'):
        rational_sided_limit('1', point)
    valid_point = Fraction(2**120-1, 2**119-1)
    assert verify_rational_limit(rational_sided_limit('1', valid_point))


def test_session_and_notebook_replay(tmp_path):
    session = CalculationSession()
    notebook = Notebook('Sided rational limits')
    for point, direction in [(0, 'left'), (0, 'right'), ('-infinity', 'both')]:
        notebook.append(session.execute('rational_limit', source='1/x', point=point, direction=direction))
    assert notebook.replay() == 3
    path = tmp_path/'limits.json'
    notebook.save(path)
    assert Notebook.load(path).to_data() == notebook.to_data()


def test_independent_sympy_oracle():
    sympy = pytest.importorskip('sympy')
    x = sympy.Symbol('x')
    # Deterministic Cartesian corpus: signed coefficients, shifted poles,
    # multiplicities, cancellations and both directions. No sampled holdout.
    count = 0
    for center in (-2, Fraction(1, 3), 3):
        for coefficient in (-3, 2):
            for top_power in range(4):
                for bottom_power in range(4):
                    source = f'{coefficient}*(x-({center}))**{top_power}/(x-({center}))**{bottom_power}'
                    expression = coefficient*(x-sympy.Rational(str(center)))**(top_power-bottom_power)
                    for direction, oracle_direction in [('left','-'), ('right','+')]:
                        actual = rational_sided_limit(source, str(center), direction=direction)['result']
                        expected = sympy.limit(expression, x, sympy.Rational(str(center)), dir=oracle_direction)
                        if expected in (sympy.oo, -sympy.oo):
                            assert actual['status'] == ('positive_infinity' if expected == sympy.oo else 'negative_infinity')
                        else:
                            assert actual == {'status':'finite', 'value':str(expected)}
                        count += 1
    assert count == 192
