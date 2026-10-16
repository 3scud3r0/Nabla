"""Exact analytic invariants, independent oracles and adversarial certificates."""

from copy import deepcopy
from fractions import Fraction
from itertools import product

import pytest

from nablamath.core.semantic_ir import fingerprint
from nablamath.math.analysis.intervals import (
    RationalInterval as I, bernstein_coefficients, horner_interval,
    polynomial_range, verify_polynomial_range,
)
from nablamath.math.analysis.quadrature import certified_polynomial_integral, verify_polynomial_integral
from nablamath.math.analysis.certified_functions import certified_function, verify_certified_function


@pytest.mark.parametrize('lower,upper', [(-3, -1), (-2, 4), (0, 0), ('1/3','5/7')])
def test_interval_arithmetic_encloses_every_rational_grid_point(lower, upper):
    interval = I(lower, upper)
    other = I('-5/4', '7/3')
    for i, j in product(range(9), repeat=2):
        x = interval.lower+interval.width*Fraction(i,8)
        y = other.lower+other.width*Fraction(j,8)
        assert (interval+other).contains(x+y)
        assert (interval-other).contains(x-y)
        assert (interval*other).contains(x*y)
        assert (interval**2).contains(x*x)
        assert (interval**3).contains(x*x*x)
        assert interval.absolute().contains(abs(x))


def test_interval_exact_geometry_and_domains():
    interval = I(-2, 3)
    assert interval.midpoint == Fraction(1,2)
    assert interval.radius == Fraction(5,2)
    assert interval.width == 5
    left, right = interval.bisect()
    assert left.hull(right) == interval
    assert left.intersection(right) == I.point('1/2')
    assert I.from_data(interval.to_data()) == interval
    assert 2-I(1,3) == I(-1,1)
    assert 2/I(1,4) == I('1/2',2)
    assert I(-4,-2).reciprocal() == I('-1/2','-1/4')
    assert I(2,4)**-2 == I('1/16','1/4')
    assert I(2,4)**0 == I.point(1)
    assert not I(0,1).overlaps(I(2,3))
    for operation in (lambda: interval.reciprocal(), lambda: interval**0,
                      lambda: interval**-1, lambda: I(2,1),
                      lambda: I.point(0).bisect(), lambda: I(0,1).intersection(I(2,3))):
        with pytest.raises(ValueError):
            operation()


@pytest.mark.parametrize('value', [True, 0.5, float('nan'), '1/0', 2**4097])
def test_exact_endpoints_reject_unsupported_inputs(value):
    with pytest.raises(ValueError):
        I.point(value)


@pytest.mark.parametrize('value', ['0','1/7','2','4','81/49'])
def test_square_root_bounds_are_rational_and_certified(value):
    q = Fraction(value)
    enclosure = I.point(q).sqrt(precision_bits=40)
    assert enclosure.lower**2 <= q <= enclosure.upper**2
    assert enclosure.width <= Fraction(1,2**40)
    if value in ('0','4','81/49'):
        # Non-dyadic exact roots need not have zero width.
        assert enclosure.contains(Fraction(9,7) if value == '81/49' else (0 if value == '0' else 2))
    with pytest.raises(ValueError):
        I(-1,1).sqrt()


def test_bernstein_dependency_and_subdivision():
    assert bernstein_coefficients([0,0,1], I(-1,1)) == (1,-1,1)
    coarse = polynomial_range([0,0,1], -1, 1)
    fine = polynomial_range([0,0,1], -1, 1, subdivisions=2)
    assert I.from_data(coarse['enclosure']) == I(-1,1)
    assert I.from_data(fine['enclosure']) == I(0,1)
    assert I.from_data(coarse['enclosure']).contains(I.from_data(fine['enclosure']))
    assert verify_polynomial_range(fine)
    assert horner_interval([0,0,1], I(-1,1)).contains(I(0,1))


@pytest.mark.parametrize('coefficients', [[0],[3],[-1,2,-3,4],[0,0,0,0,1],[1,0,-2,0,1]])
def test_polynomial_range_against_exact_critical_points(coefficients):
    sympy = pytest.importorskip('sympy')
    x = sympy.Symbol('x')
    expression = sum(sympy.Rational(c)*x**i for i,c in enumerate(coefficients))
    points = [-2,3]+[r for r in sympy.solve(sympy.diff(expression,x),x)
                     if r.is_real and -2 <= r <= 3]
    receipt = polynomial_range(coefficients,-2,3,subdivisions=8)
    enclosure = I.from_data(receipt['enclosure'])
    for point in points:
        value = expression.subs(x,point)
        assert sympy.Rational(str(enclosure.lower)) <= value <= sympy.Rational(str(enclosure.upper))
    assert verify_polynomial_range(receipt)


@pytest.mark.parametrize('method', ['midpoint','trapezoid','simpson'])
@pytest.mark.parametrize('bounds', [(0,1),(1,0),(-1,2),(2,2)])
def test_quadrature_against_exact_antiderivative(method,bounds):
    coefficients = [1,-2,3,0,1]
    lower, upper = map(Fraction,bounds)
    target = sum((Fraction(c,i+1)*(upper**(i+1)-lower**(i+1))
                  for i,c in enumerate(coefficients)),Fraction())
    receipt = certified_polynomial_integral(coefficients,lower,upper,method=method,
                                           tolerance='1/10',max_pieces=1024)
    assert I.from_data(receipt['enclosure']).contains(target)
    assert abs(Fraction(receipt['estimate'])-target) <= Fraction(receipt['error_bound'])
    assert Fraction(receipt['error_bound']) <= Fraction(1,10)
    assert verify_polynomial_integral(receipt)


def test_simpson_is_exact_on_cubics_and_budget_failure_is_explicit():
    receipt = certified_polynomial_integral([1,2,3,4],-2,3,tolerance=0)
    assert receipt['error_bound'] == '0'
    assert I.from_data(receipt['enclosure']).is_point
    with pytest.raises(ArithmeticError,match='budget'):
        certified_polynomial_integral([0,0,0,0,1],0,1,tolerance=0,max_pieces=2)


@pytest.mark.parametrize('kind', ['exp','log','sin','cos'])
@pytest.mark.parametrize('value', ['1/8','1/3','1','3','8'])
def test_transcendental_enclosure_against_high_precision_reference(kind,value):
    mp = pytest.importorskip('mpmath')
    with mp.workdps(90):
        q = Fraction(value)
        argument = mp.mpf(q.numerator)/q.denominator
        reference = Fraction(str(getattr(mp,kind)(argument)))
    receipt = certified_function(kind,value,tolerance='1/100000000')
    enclosure = I.from_data(receipt['enclosure'])
    assert enclosure.contains(reference)
    assert enclosure.width <= Fraction(1,100000000)
    assert verify_certified_function(receipt)


@pytest.mark.parametrize('kind,expected', [('sin','0'),('cos','1'),('exp','1')])
def test_transcendental_exact_origin(kind,expected):
    assert I.from_data(certified_function(kind,0)['enclosure']) == I.point(expected)


@pytest.mark.parametrize('kind', ['exp','sin','cos'])
def test_negative_arguments(kind):
    mp = pytest.importorskip('mpmath')
    with mp.workdps(90):
        reference = Fraction(str(getattr(mp,kind)(-3)))
    assert I.from_data(certified_function(kind,-3)['enclosure']).contains(reference)


@pytest.mark.parametrize('kind,value', [('log',0),('log',-1),('log','1/9'),('exp',9),('unknown',0)])
def test_transcendental_outside_profile(kind,value):
    with pytest.raises(ValueError):
        certified_function(kind,value)
    with pytest.raises(ArithmeticError):
        certified_function('exp',1,tolerance='1/1000000000',max_terms=1)


@pytest.mark.parametrize('factory,verifier,field', [
    (lambda: polynomial_range([0,0,1],-1,1),verify_polynomial_range,'enclosure'),
    (lambda: certified_polynomial_integral([0,0,1],0,1),verify_polynomial_integral,'enclosure'),
    (lambda: certified_function('exp',1),verify_certified_function,'enclosure'),
])
def test_rehashed_enclosure_cannot_fabricate_a_result(factory,verifier,field):
    receipt = deepcopy(factory())
    receipt[field] = {'lower':'0','upper':'0'}
    receipt['certificate_id'] = fingerprint({k:v for k,v in receipt.items() if k != 'certificate_id'})
    assert not verifier(receipt)
    assert not verifier({})
    assert not verifier(None)
