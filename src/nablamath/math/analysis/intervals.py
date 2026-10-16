"""Closed rational intervals with bounded, exact endpoint arithmetic.

These enclosures have no floating rounding error. Dependency overestimation is
still possible: evaluating x-x on [0,1] by interval arithmetic gives [-1,1].
Empty intersections and division across zero are explicit errors rather than
infinities, NaNs, or fabricated bounded answers.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import comb, isqrt

from ...core.semantic_ir import canonical_json, fingerprint
from ..polynomials.univariate import Polynomial


MAX_BITS = 4096
MAX_DEGREE = 32


def exact(value):
    """Accept exact scalar inputs only, bounding both parsing and arithmetic."""
    if isinstance(value, bool) or not isinstance(value, (int, str, Fraction)):
        raise ValueError('Exact rational scalar required; floats are unsupported')
    if isinstance(value, str) and len(value) > 2500:
        raise ValueError('Rational representation exceeds budget')
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError('Invalid rational scalar') from error
    if max(abs(result.numerator).bit_length(), result.denominator.bit_length()) > MAX_BITS:
        raise ValueError('Rational arithmetic exceeds bit budget')
    return result


@dataclass(frozen=True)
class RationalInterval:
    lower: Fraction
    upper: Fraction

    def __post_init__(self):
        lower, upper = exact(self.lower), exact(self.upper)
        if lower > upper:
            raise ValueError('Interval lower endpoint exceeds upper endpoint')
        object.__setattr__(self, 'lower', lower)
        object.__setattr__(self, 'upper', upper)

    @classmethod
    def point(cls, value):
        value = exact(value)
        return cls(value, value)

    @classmethod
    def from_data(cls, data):
        if not isinstance(data, dict) or set(data) != {'lower', 'upper'}:
            raise ValueError('Invalid rational interval schema')
        return cls(data['lower'], data['upper'])

    def to_data(self):
        return {'lower': str(self.lower), 'upper': str(self.upper)}

    @property
    def width(self):
        return exact(self.upper-self.lower)

    @property
    def midpoint(self):
        return exact((self.lower+self.upper)/2)

    @property
    def radius(self):
        return exact(self.width/2)

    @property
    def is_point(self):
        return self.lower == self.upper

    def contains(self, value):
        if isinstance(value, RationalInterval):
            return self.lower <= value.lower and value.upper <= self.upper
        value = exact(value)
        return self.lower <= value <= self.upper

    def overlaps(self, other):
        other = as_interval(other)
        return max(self.lower, other.lower) <= min(self.upper, other.upper)

    def intersection(self, other):
        other = as_interval(other)
        return RationalInterval(max(self.lower, other.lower), min(self.upper, other.upper))

    def hull(self, other):
        other = as_interval(other)
        return RationalInterval(min(self.lower, other.lower), max(self.upper, other.upper))

    def bisect(self):
        if self.is_point:
            raise ValueError('Cannot bisect a point interval')
        middle = self.midpoint
        return RationalInterval(self.lower, middle), RationalInterval(middle, self.upper)

    def __neg__(self):
        return RationalInterval(-self.upper, -self.lower)

    def __add__(self, other):
        other = as_interval(other)
        return RationalInterval(exact(self.lower+other.lower), exact(self.upper+other.upper))

    __radd__ = __add__

    def __sub__(self, other):
        return self + (-as_interval(other))

    def __rsub__(self, other):
        return as_interval(other) + (-self)

    def __mul__(self, other):
        other = as_interval(other)
        products = [exact(a*b) for a in (self.lower, self.upper)
                    for b in (other.lower, other.upper)]
        return RationalInterval(min(products), max(products))

    __rmul__ = __mul__

    def reciprocal(self):
        if self.contains(0):
            raise ValueError('Cannot invert an interval containing zero')
        return RationalInterval(exact(1/self.upper), exact(1/self.lower))

    def __truediv__(self, other):
        return self * as_interval(other).reciprocal()

    def __rtruediv__(self, other):
        return as_interval(other) * self.reciprocal()

    def __pow__(self, exponent):
        if type(exponent) is not int or not -64 <= exponent <= 64:
            raise ValueError('Interval power requires an integer in [-64,64]')
        if exponent <= 0 and self.contains(0):
            raise ValueError('Nonpositive power requires a nonzero interval')
        if exponent < 0:
            return self.reciprocal() ** (-exponent)
        if exponent == 0:
            return RationalInterval.point(1)
        first, last = exact(self.lower**exponent), exact(self.upper**exponent)
        if exponent % 2:
            return RationalInterval(first, last)
        lower = Fraction(0) if self.contains(0) else min(first, last)
        return RationalInterval(lower, max(first, last))

    def absolute(self):
        if self.lower >= 0:
            return self
        if self.upper <= 0:
            return -self
        return RationalInterval(0, max(-self.lower, self.upper))

    def sqrt(self, *, precision_bits=32):
        if self.lower < 0:
            raise ValueError('Real square root requires nonnegative interval')
        if type(precision_bits) is not int or not 0 <= precision_bits <= 512:
            raise ValueError('Square-root precision must be in [0,512]')
        scale = 1 << precision_bits

        def bracket(value):
            # floor(sqrt(q)*scale), using only integer arithmetic.
            floor = isqrt((value.numerator*scale*scale)//value.denominator)
            lower = Fraction(floor, scale)
            upper = lower if lower*lower == value else Fraction(floor+1, scale)
            return exact(lower), exact(upper)

        lower, _ = bracket(self.lower)
        _, upper = bracket(self.upper)
        return RationalInterval(lower, upper)


def as_interval(value):
    return value if isinstance(value, RationalInterval) else RationalInterval.point(value)


def checked_polynomial(coefficients):
    if isinstance(coefficients, Polynomial):
        coefficients = coefficients.coefficients
    if not isinstance(coefficients, (list, tuple)) or not 1 <= len(coefficients) <= MAX_DEGREE+1:
        raise ValueError('Polynomial requires 1–33 exact coefficients')
    return Polynomial(tuple(exact(value) for value in coefficients))


def horner_interval(coefficients, interval):
    polynomial = checked_polynomial(coefficients)
    if not isinstance(interval, RationalInterval):
        raise ValueError('RationalInterval required')
    result = RationalInterval.point(0)
    for coefficient in reversed(polynomial.coefficients):
        result = result*interval + coefficient
    return result


def bernstein_coefficients(coefficients, interval):
    """Convert p(a+(b-a)t) to Bernstein basis on t in [0,1]."""
    polynomial = checked_polynomial(coefficients)
    if not isinstance(interval, RationalInterval):
        raise ValueError('RationalInterval required')
    degree = max(0, polynomial.degree)
    a, width = interval.lower, interval.width
    shifted = []
    for power in range(degree+1):
        value = Fraction(0)
        for index in range(power, degree+1):
            term = exact(polynomial.coefficients[index]*comb(index, power)*a**(index-power)*width**power)
            value = exact(value+term)
        shifted.append(value)
    result = []
    for index in range(degree+1):
        value = Fraction(0)
        for power in range(index+1):
            value = exact(value + shifted[power]*Fraction(comb(index, power), comb(degree, power)))
        result.append(value)
    return tuple(result)


def polynomial_range(coefficients, lower, upper, *, subdivisions=1):
    """Enclose a polynomial range by Bernstein convex hulls on a partition.

    This need not be its sharp minimum/maximum. Subdivision can improve the
    enclosure without sampling or dropping unsampled extrema.
    """
    polynomial = checked_polynomial(coefficients)
    interval = RationalInterval(lower, upper)
    if type(subdivisions) is not int or not 1 <= subdivisions <= 256:
        raise ValueError('Subdivision count must be in [1,256]')
    width = exact(interval.width/subdivisions)
    rows = []
    combined = None
    for index in range(subdivisions):
        piece = RationalInterval(exact(interval.lower+index*width), exact(interval.lower+(index+1)*width))
        coefficients_b = bernstein_coefficients(polynomial, piece)
        enclosure = RationalInterval(min(coefficients_b), max(coefficients_b))
        combined = enclosure if combined is None else combined.hull(enclosure)
        rows.append({'interval': piece.to_data(),
                     'bernstein': [str(value) for value in coefficients_b],
                     'enclosure': enclosure.to_data()})
    payload = {
        'profile': 'rational-bernstein-range-v1',
        'request': {'coefficients': [str(v) for v in polynomial.coefficients],
                    'lower': str(interval.lower), 'upper': str(interval.upper),
                    'subdivisions': subdivisions},
        'enclosure': combined.to_data(), 'partition': rows,
        'formal_proof': False,
        'scope': 'Exact Bernstein convex-hull enclosure, not necessarily sharp extrema',
    }
    return {**payload, 'certificate_id': fingerprint(payload)}


def verify_polynomial_range(certificate):
    try:
        if not isinstance(certificate, dict) or len(canonical_json(certificate)) > 2_000_000:
            return False
        expected = polynomial_range(**certificate['request'])
        return canonical_json(certificate) == canonical_json(expected)
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return False
