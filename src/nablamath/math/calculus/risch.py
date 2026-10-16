"""Bounded rational integration with exact derivative certificates (contract 1).

This is a rational partial-fraction integration subset, not the Risch algorithm.
It handles polynomials and denominators split into supplied rational linear
factors. Degree-two denominators can be factored automatically when their roots
are rational. Irreducible quadratics and transcendental towers are unsupported.
Original denominator exclusions survive cancellation, including removable holes.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import islice
import math
from typing import Iterable, Mapping

from ..polynomials.univariate import Polynomial

CONTRACT_VERSION = 1
MAX_DEGREE = 24
MAX_BITS = 1024


def _fraction(value: object) -> Fraction:
    if not isinstance(value, (int, Fraction, str)) or isinstance(value, bool):
        raise ValueError("exact rational coefficient required")
    if isinstance(value, str) and len(value) > 2048:
        raise ValueError("rational text budget exceeded")
    result = Fraction(value)
    if max(abs(result.numerator).bit_length(), result.denominator.bit_length()) > MAX_BITS:
        raise ValueError("rational coefficient bit budget exceeded")
    return result


def _bounded(poly: Polynomial) -> Polynomial:
    if not isinstance(poly, Polynomial) or poly.degree > MAX_DEGREE:
        raise ValueError("polynomial degree budget exceeded")
    for coefficient in poly.coefficients:
        _fraction(coefficient)
    return poly


def _scale(poly: Polynomial, value: Fraction) -> Polynomial:
    return Polynomial(tuple(c * value for c in poly.coefficients))


def _power(poly: Polynomial, exponent: int) -> Polynomial:
    result = Polynomial((1,))
    for _ in range(exponent):
        result = result * poly
    return result


def _primitive(poly: Polynomial) -> Polynomial:
    return Polynomial((0,) + tuple(c / (i + 1) for i, c in enumerate(poly.coefficients)))


@dataclass(frozen=True)
class LinearFactor:
    """A monic factor (x-root)**multiplicity, represented over Q."""
    root: Fraction
    multiplicity: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", _fraction(self.root))
        if type(self.multiplicity) is not int or not 1 <= self.multiplicity <= MAX_DEGREE:
            raise ValueError("invalid factor multiplicity")

    @property
    def polynomial(self) -> Polynomial:
        return _power(Polynomial((-self.root, 1)), self.multiplicity)


@dataclass(frozen=True)
class PrimitiveTerm:
    """coefficient*log|x-root| or coefficient*(x-root)**power.

    power=0 denotes the logarithm; negative powers denote rational terms.
    """
    coefficient: Fraction
    root: Fraction
    power: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "coefficient", _fraction(self.coefficient))
        object.__setattr__(self, "root", _fraction(self.root))
        if type(self.power) is not int or not -MAX_DEGREE <= self.power <= 0:
            raise ValueError("primitive power outside supported fragment")

    def evaluate(self, x: float) -> float:
        distance = x - float(self.root)
        if distance == 0:
            raise ValueError("primitive undefined at an excluded root")
        value = math.log(abs(distance)) if self.power == 0 else distance**self.power
        result = float(self.coefficient) * value
        if not math.isfinite(result):
            raise ArithmeticError("nonfinite primitive term")
        return result

    def derivative_pair(self) -> tuple[Polynomial, Polynomial]:
        """Exact numerator/denominator of the derivative of this term."""
        base = Polynomial((-self.root, 1))
        if self.power == 0:
            return Polynomial((self.coefficient,)), base
        numerator = Polynomial((self.coefficient * self.power,))
        return numerator, _power(base, 1 - self.power)


def _factor_quadratic(denominator: Polynomial) -> tuple[LinearFactor, ...]:
    """Automatic factorization is intentionally limited to degree two."""
    if denominator.degree <= 0:
        return ()
    if denominator.degree == 1:
        return (LinearFactor(-denominator.coefficients[0] / denominator.leading),)
    if denominator.degree != 2:
        raise NotImplementedError("provide rational linear factors for degree above two")
    c, b, a = denominator.coefficients
    discriminant = b*b - 4*a*c
    if discriminant < 0:
        raise NotImplementedError("irreducible quadratic denominator is unsupported")
    numerator = math.isqrt(discriminant.numerator)
    divisor = math.isqrt(discriminant.denominator)
    if numerator*numerator != discriminant.numerator or divisor*divisor != discriminant.denominator:
        raise NotImplementedError("quadratic denominator does not split over Q")
    square = Fraction(numerator, divisor)
    roots = sorted(((-b-square)/(2*a), (-b+square)/(2*a)))
    if roots[0] == roots[1]:
        return (LinearFactor(roots[0], 2),)
    return tuple(LinearFactor(root) for root in roots)


def _validated_factors(denominator: Polynomial,
                       factors: Iterable[LinearFactor] | None) -> tuple[LinearFactor, ...]:
    result = _factor_quadratic(denominator) if factors is None else tuple(islice(factors, MAX_DEGREE + 1))
    if len(result) > MAX_DEGREE or any(not isinstance(f, LinearFactor) for f in result):
        raise ValueError("invalid or excessive factor list")
    if len({factor.root for factor in result}) != len(result):
        raise ValueError("combine repeated roots into one multiplicity")
    if sum(f.multiplicity for f in result) != max(0, denominator.degree):
        raise ValueError("factor degrees do not match denominator")
    product = Polynomial((1,))
    for factor in result:
        product = product * factor.polynomial
    if product != denominator.monic():
        raise ValueError("supplied factors do not certify the denominator")
    return tuple(sorted(result, key=lambda f: f.root))


def _solve_exact(columns: list[Polynomial], rhs: Polynomial) -> tuple[Fraction, ...]:
    """Small exact Gaussian elimination; bounded by denominator degree."""
    size = len(columns)
    if not size:
        return ()
    rows = []
    for i in range(size):
        row = [column.coefficients[i] if i < len(column.coefficients) else Fraction()
               for column in columns]
        row.append(rhs.coefficients[i] if i < len(rhs.coefficients) else Fraction())
        rows.append(row)
    for pivot in range(size):
        candidate = next((i for i in range(pivot, size) if rows[i][pivot]), None)
        if candidate is None:
            raise ArithmeticError("partial fraction system is singular")
        rows[pivot], rows[candidate] = rows[candidate], rows[pivot]
        scale = rows[pivot][pivot]
        rows[pivot] = [value / scale for value in rows[pivot]]
        for i in range(size):
            if i == pivot:
                continue
            factor = rows[i][pivot]
            rows[i] = [value - factor*base
                       for value, base in zip(rows[i], rows[pivot], strict=True)]
        for row in rows:
            for value in row:
                if max(abs(value.numerator).bit_length(), value.denominator.bit_length()) > 32768:
                    raise ArithmeticError("exact elimination intermediate bit budget exceeded")
    return tuple(row[-1] for row in rows)


@dataclass(frozen=True)
class RationalIntegral:
    """Primitive and an exact derivative identity, with original domain guards."""
    numerator: Polynomial
    denominator: Polynomial
    polynomial_part: Polynomial
    terms: tuple[PrimitiveTerm, ...]
    factors: tuple[LinearFactor, ...]
    version: int = CONTRACT_VERSION

    def verify(self) -> bool:
        """Independently check the derivative by polynomial cross multiplication.

        Verification does not rerun partial-fraction elimination. It also checks
        every original denominator root remains in the domain exclusions.
        """
        try:
            if self.version != CONTRACT_VERSION:
                return False
            _bounded(self.numerator)
            _bounded(self.denominator)
            if self.denominator.is_zero or self.polynomial_part.degree > MAX_DEGREE + 1:
                return False
            if len(self.terms) > MAX_DEGREE:
                return False
            factors = _validated_factors(self.denominator, self.factors)
            known = {f.root: f.multiplicity for f in factors}
            derivative_numerator = self.polynomial_part.derivative() * self.denominator
            for term in self.terms:
                if term.root not in known or 1 - term.power > known[term.root]:
                    return False
                n, d = term.derivative_pair()
                quotient, remainder = self.denominator.divmod(d)
                if not remainder.is_zero:
                    return False
                derivative_numerator = derivative_numerator + n * quotient
            return derivative_numerator == self.numerator
        except (ValueError, ArithmeticError, TypeError, AttributeError):
            return False

    @property
    def excluded_roots(self) -> tuple[Fraction, ...]:
        return tuple(f.root for f in self.factors)

    def evaluate(self, x: float) -> float:
        """Approximate primitive on a connected component of its original domain."""
        if not math.isfinite(x):
            raise ValueError("finite evaluation point required")
        if any(x == float(root) for root in self.excluded_roots):
            raise ValueError("evaluation point excluded by original denominator")
        value = float(self.polynomial_part(Fraction(x)))
        value += math.fsum(term.evaluate(x) for term in self.terms)
        if not math.isfinite(value):
            raise ArithmeticError("nonfinite primitive value")
        return value

    def definite(self, left: float, right: float) -> float:
        """Approximate proper integral; reject poles and removable original holes.

        This does not calculate improper integrals or Cauchy principal values.
        """
        if not all(math.isfinite(x) for x in (left, right)):
            raise ValueError("finite integration endpoints required")
        lo, hi = sorted((left, right))
        if any(lo <= float(root) <= hi for root in self.excluded_roots):
            raise ValueError("integration interval crosses an original domain exclusion")
        return self.evaluate(right) - self.evaluate(left)

    def to_data(self) -> dict:
        """Portable exact payload: rationals use numerator/denominator strings."""
        return {
            "version": self.version,
            "numerator": [str(c) for c in self.numerator.coefficients],
            "denominator": [str(c) for c in self.denominator.coefficients],
            "polynomial_part": [str(c) for c in self.polynomial_part.coefficients],
            "terms": [{"coefficient": str(t.coefficient), "root": str(t.root), "power": t.power}
                      for t in self.terms],
            "factors": [{"root": str(f.root), "multiplicity": f.multiplicity} for f in self.factors],
        }

    @classmethod
    def from_data(cls, data: Mapping) -> RationalIntegral:
        """Read bounded data and reject any certificate whose identity fails."""
        expected = {"version", "numerator", "denominator", "polynomial_part", "terms", "factors"}
        if (not isinstance(data, Mapping) or set(data) != expected
                or type(data["version"]) is not int or data["version"] != CONTRACT_VERSION):
            raise ValueError("invalid integral payload schema")
        def polynomial(key: str, limit: int) -> Polynomial:
            values = data[key]
            if not isinstance(values, list) or not 1 <= len(values) <= limit:
                raise ValueError("invalid polynomial payload")
            return Polynomial(tuple(_fraction(v) for v in values))
        raw_terms, raw_factors = data["terms"], data["factors"]
        if (not isinstance(raw_terms, list) or not isinstance(raw_factors, list)
                or len(raw_terms) > MAX_DEGREE or len(raw_factors) > MAX_DEGREE):
            raise ValueError("invalid integral term count")
        terms, factors = [], []
        for term in raw_terms:
            if not isinstance(term, dict) or set(term) != {"coefficient", "root", "power"}:
                raise ValueError("invalid primitive term schema")
            terms.append(PrimitiveTerm(_fraction(term["coefficient"]), _fraction(term["root"]), term["power"]))
        for factor in raw_factors:
            if not isinstance(factor, dict) or set(factor) != {"root", "multiplicity"}:
                raise ValueError("invalid factor schema")
            factors.append(LinearFactor(_fraction(factor["root"]), factor["multiplicity"]))
        result = cls(polynomial("numerator", MAX_DEGREE + 1),
                     polynomial("denominator", MAX_DEGREE + 1),
                     polynomial("polynomial_part", MAX_DEGREE + 2), tuple(terms), tuple(factors))
        if not result.verify():
            raise ValueError("integral derivative certificate failed verification")
        return result


def integrate_rational(numerator: Polynomial, denominator: Polynomial,
                       factors: Iterable[LinearFactor] | None = None) -> RationalIntegral:
    """Integrate a bounded rational function with exact derivative verification.

    Factor certificates must multiply to the original monic denominator. Input
    numerator and denominator are deliberately not canceled before recording
    exclusions. Unsupported factorization is an explicit error, never a guess.
    """
    _bounded(numerator)
    _bounded(denominator)
    if denominator.is_zero:
        raise ValueError("zero denominator")
    certified_factors = _validated_factors(denominator, factors)
    quotient, remainder = numerator.divmod(denominator)
    columns, labels = [], []
    for factor in certified_factors:
        base = Polynomial((-factor.root, 1))
        for power in range(1, factor.multiplicity + 1):
            divisor = _power(base, power)
            column, rest = denominator.divmod(divisor)
            if not rest.is_zero:
                raise ArithmeticError("factor certificate division failed")
            columns.append(column)
            labels.append((factor.root, power))
    coefficients = _solve_exact(columns, remainder)
    terms = []
    for (root, power), coefficient in zip(labels, coefficients, strict=True):
        if not coefficient:
            continue
        if power == 1:
            terms.append(PrimitiveTerm(coefficient, root, 0))
        else:
            terms.append(PrimitiveTerm(coefficient / (1-power), root, 1-power))
    result = RationalIntegral(numerator, denominator, _primitive(quotient),
                              tuple(terms), certified_factors)
    if not result.verify():
        raise ArithmeticError("generated derivative certificate failed")
    return result
