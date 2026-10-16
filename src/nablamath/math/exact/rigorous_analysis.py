"""Rigorous interval analysis, rational Padé systems and polynomial enclosures.

All interval endpoints are fractions, not guessed float error bars. A bracketing
result establishes existence by continuity, but does NOT establish uniqueness.
The subdivision enclosure explicitly exposes a finite error certificate.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import factorial

from .laboratory import (
    Polynomial, RationalMatrix, bernstein_range, rational, ZERO, ONE, X,
)


MAX_SEGMENTS = 1024


@dataclass(frozen=True)
class ExactInterval:
    """Closed rational interval, with outward exact interval arithmetic."""
    lower: Fraction
    upper: Fraction

    def __post_init__(self) -> None:
        lower, upper = rational(self.lower), rational(self.upper)
        if lower > upper:
            raise ValueError("Interval bounds are reversed")
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)

    @property
    def width(self) -> Fraction:
        return self.upper - self.lower

    @property
    def midpoint(self) -> Fraction:
        return (self.lower + self.upper) / 2

    @property
    def contains_zero(self) -> bool:
        return self.lower <= 0 <= self.upper

    def contains(self, value: object) -> bool:
        return self.lower <= rational(value) <= self.upper

    def _coerce(self, other: object) -> ExactInterval:
        return other if isinstance(other, ExactInterval) else ExactInterval(
            rational(other), rational(other)
        )

    def __add__(self, other: object) -> ExactInterval:
        other = self._coerce(other)
        return ExactInterval(self.lower + other.lower, self.upper + other.upper)

    __radd__ = __add__

    def __neg__(self) -> ExactInterval:
        return ExactInterval(-self.upper, -self.lower)

    def __sub__(self, other: object) -> ExactInterval:
        return self + -self._coerce(other)

    def __rsub__(self, other: object) -> ExactInterval:
        return self._coerce(other) - self

    def __mul__(self, other: object) -> ExactInterval:
        other = self._coerce(other)
        products = (self.lower * other.lower, self.lower * other.upper,
                    self.upper * other.lower, self.upper * other.upper)
        return ExactInterval(min(products), max(products))

    __rmul__ = __mul__

    def reciprocal(self) -> ExactInterval:
        if self.contains_zero:
            raise ZeroDivisionError("Cannot divide by an interval containing zero")
        return ExactInterval(1 / self.upper, 1 / self.lower)

    def __truediv__(self, other: object) -> ExactInterval:
        return self * self._coerce(other).reciprocal()

    def __rtruediv__(self, other: object) -> ExactInterval:
        return self._coerce(other) * self.reciprocal()

    def __pow__(self, exponent: int) -> ExactInterval:
        if type(exponent) is not int or not -64 <= exponent <= 64:
            raise ValueError("Interval exponent must be an integer in [-64,64]")
        if exponent < 0:
            return (self.reciprocal()) ** (-exponent)
        if exponent == 0:
            return ExactInterval(1, 1)
        if exponent % 2:
            return ExactInterval(self.lower ** exponent, self.upper ** exponent)
        lower = 0 if self.contains_zero else min(self.lower ** exponent,
                                                   self.upper ** exponent)
        upper = max(self.lower ** exponent, self.upper ** exponent)
        return ExactInterval(lower, upper)

    def intersection(self, other: ExactInterval) -> ExactInterval | None:
        other = self._coerce(other)
        lower, upper = max(self.lower, other.lower), min(self.upper, other.upper)
        return ExactInterval(lower, upper) if lower <= upper else None

    def hull(self, other: ExactInterval) -> ExactInterval:
        other = self._coerce(other)
        return ExactInterval(min(self.lower, other.lower), max(self.upper, other.upper))

    def bisect(self) -> tuple[ExactInterval, ExactInterval]:
        middle = self.midpoint
        return ExactInterval(self.lower, middle), ExactInterval(middle, self.upper)

    def to_data(self) -> dict:
        return {"lower": str(self.lower), "upper": str(self.upper),
                "width": str(self.width)}


def interval_horner(polynomial: Polynomial, domain: ExactInterval) -> ExactInterval:
    """Inclusion-valid Horner interval evaluation; may be overly conservative."""
    if not isinstance(polynomial, Polynomial) or not isinstance(domain, ExactInterval):
        raise TypeError("Expected Polynomial and ExactInterval")
    result = ExactInterval(0, 0)
    for c in reversed(polynomial.coefficients):
        result = result * domain + c
    return result


def bernstein_enclosure(polynomial: Polynomial,
                        domain: ExactInterval) -> ExactInterval:
    """Range enclosure from Bernstein convex hull, often sharper than Horner."""
    if not isinstance(polynomial, Polynomial) or not isinstance(domain, ExactInterval):
        raise TypeError("Expected Polynomial and ExactInterval")
    if domain.width == 0:
        value = polynomial(domain.lower)
        return ExactInterval(value, value)
    lo, hi = bernstein_range(polynomial, domain.lower, domain.upper)
    return ExactInterval(lo, hi)


def subdivision_extrema(
    polynomial: Polynomial, domain: ExactInterval, *,
    tolerance: object = Fraction(1, 64), max_segments: int = 128,
) -> dict:
    """Certified enclosures of minimum and maximum over a closed interval.

    Every interval's Bernstein range is valid. Refine the widest *local*
    enclosure until its width <= tolerance. If the budget cannot establish
    the requested guarantee, raise rather than silently returning success.
    """
    if not isinstance(polynomial, Polynomial) or not isinstance(domain, ExactInterval):
        raise TypeError("Expected Polynomial and ExactInterval")
    tolerance = rational(tolerance)
    if tolerance <= 0 or type(max_segments) is not int or not 1 <= max_segments <= MAX_SEGMENTS:
        raise ValueError("Expected positive rational tolerance and 1..1024 segments")
    intervals = [(domain, bernstein_enclosure(polynomial, domain))]
    while True:
        worst = max(range(len(intervals)), key=lambda i: intervals[i][1].width)
        if intervals[worst][1].width <= tolerance:
            break
        if len(intervals) >= max_segments:
            raise ArithmeticError("Certified extrema segment budget exhausted")
        segment, _ = intervals.pop(worst)
        if segment.width == 0:
            raise ArithmeticError("Nonconverging interval subdivision")
        for half in segment.bisect():
            intervals.append((half, bernstein_enclosure(polynomial, half)))
    lo = min(enclosure.lower for _, enclosure in intervals)
    lo_upper = min(enclosure.upper for _, enclosure in intervals)
    hi_lower = max(enclosure.lower for _, enclosure in intervals)
    hi = max(enclosure.upper for _, enclosure in intervals)
    if lo_upper - lo > tolerance or hi - hi_lower > tolerance:
        raise ArithmeticError("Extremum enclosure invariant failed")
    return {
        "minimum": ExactInterval(lo, lo_upper).to_data(),
        "maximum": ExactInterval(hi_lower, hi).to_data(),
        "segments": len(intervals),
        "tolerance": str(tolerance),
        "certificate": "Exact Bernstein interval cover of a compact domain",
    }


def certified_root_bisection(
    polynomial: Polynomial, domain: ExactInterval, *,
    steps: int = 64,
) -> dict:
    """Exact sign-changing root bracket; existence but not uniqueness."""
    if not isinstance(polynomial, Polynomial) or not isinstance(domain, ExactInterval):
        raise TypeError("Expected Polynomial and ExactInterval")
    if type(steps) is not int or not 0 <= steps <= 256 or domain.width == 0:
        raise ValueError("Expected a non-degenerate domain and 0..256 bisections")
    a, b = domain.lower, domain.upper
    fa, fb = polynomial(a), polynomial(b)
    if fa == 0:
        return {"interval": ExactInterval(a, a).to_data(), "exact_root": True,
                "existence": True, "uniqueness": False}
    if fb == 0:
        return {"interval": ExactInterval(b, b).to_data(), "exact_root": True,
                "existence": True, "uniqueness": False}
    if fa * fb >= 0:
        raise ValueError("Root bracketing requires opposite nonzero endpoint signs")
    for _ in range(steps):
        m = (a + b) / 2
        fm = polynomial(m)
        if fm == 0:
            return {"interval": ExactInterval(m, m).to_data(), "exact_root": True,
                    "existence": True, "uniqueness": False}
        if fm * fa < 0:
            b, fb = m, fm
        else:
            a, fa = m, fm
    if polynomial(a) * polynomial(b) >= 0:
        raise ArithmeticError("Bisection lost the certified sign change")
    return {
        "interval": ExactInterval(a, b).to_data(),
        "exact_root": False,
        "existence": True,
        "uniqueness": False,
        "proof": "Intermediate value theorem with exact opposite signs",
    }


def exact_polynomial_integral(polynomial: Polynomial,
                              domain: ExactInterval) -> Fraction:
    """Fundamental theorem of calculus for rational polynomials."""
    if not isinstance(polynomial, Polynomial) or not isinstance(domain, ExactInterval):
        raise TypeError("Expected Polynomial and ExactInterval")
    anti = polynomial.integral()
    return rational(anti(domain.upper) - anti(domain.lower))


def shifted_taylor_polynomial(polynomial: Polynomial, center: object) -> Polynomial:
    """Expand f(center + h) as polynomial in h, without approximation."""
    if not isinstance(polynomial, Polynomial):
        raise TypeError("Expected Polynomial")
    center = rational(center)
    return polynomial.compose(Polynomial((center, 1)))


def pade_exponential(numerator_degree: int, denominator_degree: int
                     ) -> tuple[Polynomial, Polynomial]:
    """Rational [m/n] Padé approximant to exp(x), about the origin.

    Q(0)=1 and Q*exp-P vanishes through order m+n. This is an algebraic
    Taylor matching statement, NOT a globally certified exp approximation.
    """
    m, n = numerator_degree, denominator_degree
    if type(m) is not int or type(n) is not int or not 0 <= m <= 16 or not 0 <= n <= 16:
        raise ValueError("Padé degrees must be integers in [0,16]")
    c = [Fraction(1, factorial(k)) for k in range(m+n+1)]
    if n == 0:
        return Polynomial(tuple(c)), ONE
    rows, rhs = [], []
    for k in range(m+1, m+n+1):
        rows.append(tuple(c[k-j] if k >= j else 0 for j in range(1, n+1)))
        rhs.append(-c[k])
    solution = RationalMatrix(tuple(rows)).solve(rhs)
    if solution.nullspace:
        raise ArithmeticError("Padé normalization did not determine denominator")
    q = Polynomial((1,) + solution.particular)
    p = Polynomial(tuple(
        sum((q.coefficients[j] * c[k-j] for j in range(min(n, k)+1)),
            Fraction(0))
        for k in range(m+1)
    ))
    for k in range(m+1, m+n+1):
        residual = sum((q.coefficients[j] * c[k-j]
                        for j in range(min(n, k)+1)), Fraction(0))
        if residual:
            raise ArithmeticError("Padé Taylor matching residual is nonzero")
    return p, q


def newton_divided_differences(
    nodes: tuple[tuple[object, object], ...]
) -> tuple[Fraction, ...]:
    """Newton-form coefficients for distinct rational interpolation nodes."""
    if not 1 <= len(nodes) <= 64:
        raise ValueError("Interpolation requires 1..64 nodes")
    x = [rational(node[0]) for node in nodes]
    data = [rational(node[1]) for node in nodes]
    if len(set(x)) != len(x):
        raise ValueError("Nodes must have distinct abscissae")
    answer = [data[0]]
    for j in range(1, len(x)):
        for i in range(len(x)-1, j-1, -1):
            data[i] = (data[i] - data[i-1]) / (x[i] - x[i-j])
        answer.append(rational(data[j]))
    return tuple(answer)


def newton_to_polynomial(
    nodes: tuple[object, ...], divided_differences: tuple[object, ...]
) -> Polynomial:
    """Reconstruct canonical coefficient-form polynomial from Newton basis."""
    if len(nodes) != len(divided_differences) or not 1 <= len(nodes) <= 64:
        raise ValueError("Newton nodes and coefficients must have equal lengths")
    result, basis = ZERO, ONE
    for x, coefficient in zip(nodes, divided_differences):
        result += basis * rational(coefficient)
        basis *= X - rational(x)
    return result


__all__ = [
    "ExactInterval", "interval_horner", "bernstein_enclosure",
    "subdivision_extrema", "certified_root_bisection",
    "exact_polynomial_integral", "shifted_taylor_polynomial",
    "pade_exponential", "newton_divided_differences",
    "newton_to_polynomial",
]
