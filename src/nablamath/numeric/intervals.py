"""Exact rational interval extensions; no binary floating-point rounding claims."""
from fractions import Fraction
from math import isqrt

from ..core.precision import RationalInterval


def subtract(left: RationalInterval, right: RationalInterval) -> RationalInterval:
    return RationalInterval(left.lower - right.upper, left.upper - right.lower)


def square(value: RationalInterval) -> RationalInterval:
    upper = max(value.lower**2, value.upper**2)
    lower = 0 if value.lower <= 0 <= value.upper else min(value.lower**2, value.upper**2)
    return RationalInterval(lower, upper)


def sqrt_enclosure(value: RationalInterval, *, digits: int = 16) -> RationalInterval:
    """Outward decimal-grid enclosure, using integer inequalities, not float sqrt."""
    if type(digits) is not int or not 1 <= digits <= 32 or value.lower < 0:
        raise ValueError("Nonnegative interval and 1–32 decimal digits required")
    scale = 10**digits

    def bounds(endpoint):
        integer = isqrt(endpoint.numerator * scale**2 // endpoint.denominator)
        lower = Fraction(integer, scale)
        upper = lower if lower**2 == endpoint else Fraction(integer + 1, scale)
        return lower, upper

    return RationalInterval(bounds(value.lower)[0], bounds(value.upper)[1])


def intersect(left: RationalInterval, right: RationalInterval) -> RationalInterval:
    lower, upper = max(left.lower, right.lower), min(left.upper, right.upper)
    if lower > upper:
        raise ValueError("Disjoint intervals")
    return RationalInterval(lower, upper)
