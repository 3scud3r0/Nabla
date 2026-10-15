"""Version 1: exact splitting fields and Galois groups of rational quadratics.

This deliberately bounded API makes no claims about general polynomials.
"""
from dataclasses import dataclass
from fractions import Fraction
from math import isqrt

CONTRACT_VERSION = 1


def _rational_sqrt(value: Fraction) -> Fraction | None:
    if value < 0:
        return None
    numerator, denominator = isqrt(value.numerator), isqrt(value.denominator)
    if numerator**2 == value.numerator and denominator**2 == value.denominator:
        return Fraction(numerator, denominator)
    return None


@dataclass(frozen=True)
class QuadraticGaloisResult:
    discriminant: Fraction
    splitting_degree: int
    group: str
    rational_roots: tuple[Fraction, ...]
    root_center: Fraction
    radical_scale: Fraction

    def verify(self, a: Fraction, b: Fraction, c: Fraction) -> bool:
        """Recompute exact discriminant and root formula independently of metadata."""
        a, b, c = Fraction(a), Fraction(b), Fraction(c)
        if not a or self.discriminant != b*b - 4*a*c:
            return False
        square = _rational_sqrt(self.discriminant)
        if self.root_center != -b / (2*a) or self.radical_scale != 1 / (2*a):
            return False
        if square is None:
            return self.splitting_degree == 2 and self.group == "C2" and not self.rational_roots
        expected = tuple(sorted(set(((-b + square)/(2*a), (-b - square)/(2*a)))))
        return (self.splitting_degree == 1 and self.group == "trivial"
                and self.rational_roots == expected
                and all(a*r*r + b*r + c == 0 for r in self.rational_roots))


def quadratic_galois(a: Fraction | int, b: Fraction | int,
                      c: Fraction | int) -> QuadraticGaloisResult:
    """Classify ax²+bx+c over Q; roots are center ± scale*sqrt(discriminant).

    Square discriminants split over Q, including the repeated-root case.
    Nonsquares (also negative ones) give a separable quadratic extension and C2.
    Coefficients are limited to 4096 bits each to bound integer arithmetic.
    """
    values = tuple(Fraction(x) for x in (a, b, c))
    if any(max(abs(x.numerator).bit_length(), x.denominator.bit_length()) > 4096 for x in values):
        raise ValueError("coefficient bit budget exceeded")
    a, b, c = values
    if not a:
        raise ValueError("leading coefficient must be nonzero")
    d = b*b - 4*a*c
    square = _rational_sqrt(d)
    roots = () if square is None else tuple(sorted(set(((-b+square)/(2*a), (-b-square)/(2*a)))))
    return QuadraticGaloisResult(d, 2 if square is None else 1,
                                "C2" if square is None else "trivial", roots, -b/(2*a), 1/(2*a))


@dataclass(frozen=True)
class QuadraticElement:
    """a+b sqrt(d) in Q(sqrt(d)), where d is a rational nonsquare."""
    a: Fraction
    b: Fraction
    d: Fraction

    def __post_init__(self) -> None:
        for name in ("a", "b", "d"):
            object.__setattr__(self, name, Fraction(getattr(self, name)))
        if _rational_sqrt(self.d) is not None:
            raise ValueError("radicand must define a genuine quadratic field")

    def _check(self, other: "QuadraticElement") -> None:
        if self.d != other.d:
            raise ValueError("field presentations differ")

    def __add__(self, other: "QuadraticElement") -> "QuadraticElement":
        self._check(other)
        return QuadraticElement(self.a+other.a, self.b+other.b, self.d)

    def __mul__(self, other: "QuadraticElement") -> "QuadraticElement":
        self._check(other)
        return QuadraticElement(self.a*other.a+self.b*other.b*self.d,
                                self.a*other.b+self.b*other.a, self.d)

    def conjugate(self) -> "QuadraticElement":
        return QuadraticElement(self.a, -self.b, self.d)

    @property
    def norm(self) -> Fraction:
        return self.a*self.a-self.d*self.b*self.b

    def inverse(self) -> "QuadraticElement":
        if not self.norm:
            raise ZeroDivisionError("zero has no inverse")
        return QuadraticElement(self.a/self.norm, -self.b/self.norm, self.d)
