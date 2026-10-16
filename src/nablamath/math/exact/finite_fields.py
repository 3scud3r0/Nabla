"""Finite prime fields and polynomial quotient extensions, with exact certificates.

Rabin's finite-field irreducibility test and extended Euclid make extension
field division constructive. No external computer algebra or randomness is used.
This is distinct from the repository's pre-existing symbolic Q[x] APIs.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import gcd

from .advanced_number_theory import is_prime_64


MAX_MOD_DEGREE = 128
MAX_FIELD_SIZE = 10**9


@dataclass(frozen=True)
class ModPolynomial:
    """Polynomial over F_p in ascending coefficient order."""
    coefficients: tuple[int, ...]
    p: int

    def __post_init__(self) -> None:
        if type(self.p) is not int or not 2 <= self.p <= 257 or not is_prime_64(self.p):
            raise ValueError("Coefficient modulus must be prime in [2,257]")
        if not isinstance(self.coefficients, (tuple, list)) or not 1 <= len(self.coefficients) <= MAX_MOD_DEGREE + 1:
            raise ValueError("Polynomial coefficient budget exceeded")
        if any(type(c) is not int for c in self.coefficients):
            raise TypeError("Finite-field coefficients must be integers")
        coeffs = tuple(c % self.p for c in self.coefficients)
        while len(coeffs) > 1 and coeffs[-1] == 0:
            coeffs = coeffs[:-1]
        object.__setattr__(self, "coefficients", coeffs)

    @property
    def degree(self) -> int:
        return -1 if self.is_zero else len(self.coefficients) - 1

    @property
    def is_zero(self) -> bool:
        return self.coefficients == (0,)

    @property
    def leading(self) -> int:
        return self.coefficients[-1]

    @classmethod
    def zero(cls, p: int) -> ModPolynomial:
        return cls((0,), p)

    @classmethod
    def one(cls, p: int) -> ModPolynomial:
        return cls((1,), p)

    @classmethod
    def x(cls, p: int) -> ModPolynomial:
        return cls((0, 1), p)

    def _coerce(self, other: object) -> ModPolynomial:
        if isinstance(other, ModPolynomial):
            if self.p != other.p:
                raise ValueError("Prime fields must match")
            return other
        if type(other) is int:
            return ModPolynomial((other,), self.p)
        raise TypeError("Expected a finite-field polynomial or integer")

    def __add__(self, other: object) -> ModPolynomial:
        other = self._coerce(other)
        n = max(len(self.coefficients), len(other.coefficients))
        return ModPolynomial(tuple(
            (self.coefficients[i] if i < len(self.coefficients) else 0)
            + (other.coefficients[i] if i < len(other.coefficients) else 0)
            for i in range(n)), self.p)

    __radd__ = __add__

    def __neg__(self) -> ModPolynomial:
        return ModPolynomial(tuple(-c for c in self.coefficients), self.p)

    def __sub__(self, other: object) -> ModPolynomial:
        return self + -self._coerce(other)

    def __rsub__(self, other: object) -> ModPolynomial:
        return self._coerce(other) - self

    def __mul__(self, other: object) -> ModPolynomial:
        other = self._coerce(other)
        if self.is_zero or other.is_zero:
            return ModPolynomial.zero(self.p)
        if self.degree + other.degree > MAX_MOD_DEGREE:
            raise ValueError("Finite-field product exceeds polynomial budget")
        result = [0] * (self.degree + other.degree + 1)
        for i, x in enumerate(self.coefficients):
            for j, y in enumerate(other.coefficients):
                result[i + j] = (result[i + j] + x * y) % self.p
        return ModPolynomial(tuple(result), self.p)

    __rmul__ = __mul__

    def __pow__(self, exponent: int) -> ModPolynomial:
        if type(exponent) is not int or not 0 <= exponent <= 100000:
            raise ValueError("Polynomial exponent outside bounded domain")
        result, base = ModPolynomial.one(self.p), self
        while exponent:
            if exponent & 1:
                result *= base
            exponent >>= 1
            if exponent:
                base *= base
        return result

    def __call__(self, x: int) -> int:
        if type(x) is not int:
            raise TypeError("Evaluation requires a field integer")
        value = 0
        for c in reversed(self.coefficients):
            value = (value * x + c) % self.p
        return value

    def divmod(self, divisor: ModPolynomial) -> tuple[ModPolynomial, ModPolynomial]:
        divisor = self._coerce(divisor)
        if divisor.is_zero:
            raise ZeroDivisionError("Division by the zero polynomial")
        quotient = [0] * max(1, self.degree - divisor.degree + 1)
        remainder = list(self.coefficients)
        inverse = pow(divisor.leading, -1, self.p)
        while len(remainder) - 1 >= divisor.degree and any(remainder):
            shift = len(remainder) - 1 - divisor.degree
            scale = remainder[-1] * inverse % self.p
            quotient[shift] = scale
            for i, coefficient in enumerate(divisor.coefficients):
                remainder[shift+i] = (remainder[shift+i] - scale * coefficient) % self.p
            while len(remainder) > 1 and remainder[-1] == 0:
                remainder.pop()
        return ModPolynomial(tuple(quotient), self.p), ModPolynomial(tuple(remainder), self.p)

    def __mod__(self, divisor: ModPolynomial) -> ModPolynomial:
        return self.divmod(divisor)[1]

    def __floordiv__(self, divisor: ModPolynomial) -> ModPolynomial:
        quotient, remainder = self.divmod(divisor)
        if not remainder.is_zero:
            raise ValueError("Non-exact polynomial quotient")
        return quotient

    def derivative(self) -> ModPolynomial:
        return ModPolynomial(tuple(
            i * self.coefficients[i] for i in range(1, len(self.coefficients))
        ) or (0,), self.p)

    def monic(self) -> ModPolynomial:
        if self.is_zero:
            raise ZeroDivisionError("Zero polynomial cannot be made monic")
        return self * pow(self.leading, -1, self.p)

    def powmod(self, exponent: int, modulus: ModPolynomial) -> ModPolynomial:
        """Binary polynomial modular exponentiation without degree blowup."""
        modulus = self._coerce(modulus)
        if modulus.is_zero or type(exponent) is not int or not 0 <= exponent <= 10**20:
            raise ValueError("Invalid modulus or exponent outside 10**20")
        result = ModPolynomial.one(self.p) % modulus
        base = self % modulus
        while exponent:
            if exponent & 1:
                result = (result * base) % modulus
            exponent >>= 1
            if exponent:
                base = (base * base) % modulus
        return result

    def to_data(self) -> dict:
        return {"prime": self.p, "coefficients": list(self.coefficients)}


def mod_poly_gcd(a: ModPolynomial, b: ModPolynomial) -> ModPolynomial:
    if a.p != b.p:
        raise ValueError("Prime fields must match")
    while not b.is_zero:
        a, b = b, a % b
    return a if a.is_zero else a.monic()


def mod_poly_extended_gcd(a: ModPolynomial, b: ModPolynomial
                          ) -> tuple[ModPolynomial, ModPolynomial, ModPolynomial]:
    """Monic Bézout polynomial identity g=s*a+t*b."""
    if a.p != b.p:
        raise ValueError("Prime fields must match")
    p = a.p
    r0, r1 = a, b
    s0, s1 = ModPolynomial.one(p), ModPolynomial.zero(p)
    t0, t1 = ModPolynomial.zero(p), ModPolynomial.one(p)
    if a.is_zero and b.is_zero:
        return r0, ModPolynomial.zero(p), ModPolynomial.zero(p)
    while not r1.is_zero:
        q, r = r0.divmod(r1)
        r0, r1 = r1, r
        s0, s1 = s1, s0 - q * s1
        t0, t1 = t1, t0 - q * t1
    scale = pow(r0.leading, -1, p)
    return r0 * scale, s0 * scale, t0 * scale


def is_irreducible(poly: ModPolynomial) -> bool:
    """Rabin test: x^(p^n)=x and gcd(x^(p^(n/q))-x,f)=1 per prime q|n."""
    if not isinstance(poly, ModPolynomial):
        raise TypeError("Expected ModPolynomial")
    n, p = poly.degree, poly.p
    if n < 1:
        return False
    if n == 1:
        return True
    if n > 12 or p**n > MAX_FIELD_SIZE:
        raise ValueError("Irreducibility test limited to degree<=12 and p^n<=1e9")
    f = poly.monic()
    x = ModPolynomial.x(p) % f
    powers = [x]
    for _ in range(n):
        powers.append(powers[-1].powmod(p, f))
    if powers[n] != x:
        return False
    factors = [q for q in range(2, n+1) if n % q == 0
               and all(q % d for d in range(2, int(q**0.5)+1))]
    for q in factors:
        if mod_poly_gcd(powers[n//q] - x, f).degree > 0:
            return False
    return True


@dataclass(frozen=True)
class FiniteField:
    """F_(p^n)=F_p[x]/(f), f monic irreducible of degree n."""
    modulus: ModPolynomial

    def __post_init__(self) -> None:
        if not is_irreducible(self.modulus):
            raise ValueError("Field defining polynomial must be irreducible")
        object.__setattr__(self, "modulus", self.modulus.monic())

    @property
    def size(self) -> int:
        return self.modulus.p ** self.modulus.degree

    @property
    def characteristic(self) -> int:
        return self.modulus.p

    @property
    def degree(self) -> int:
        return self.modulus.degree

    def element(self, coefficients: int | tuple[int, ...] | ModPolynomial) -> FieldElement:
        if type(coefficients) is int:
            coefficients = (coefficients,)
        if not isinstance(coefficients, ModPolynomial):
            coefficients = ModPolynomial(tuple(coefficients), self.characteristic)
        if coefficients.p != self.characteristic:
            raise ValueError("Element is from a different prime field")
        return FieldElement(self, coefficients % self.modulus)

    def zero(self) -> FieldElement:
        return self.element(0)

    def one(self) -> FieldElement:
        return self.element(1)


@dataclass(frozen=True)
class FieldElement:
    """A canonical residue class in a finite field; no implicit cross-field cast."""
    field: FiniteField
    representative: ModPolynomial

    def __post_init__(self) -> None:
        if self.representative.p != self.field.characteristic:
            raise ValueError("Element characteristic mismatch")
        object.__setattr__(self, "representative",
                           self.representative % self.field.modulus)

    def _coerce(self, other: object) -> FieldElement:
        if isinstance(other, FieldElement):
            if other.field != self.field:
                raise ValueError("Finite field mismatch")
            return other
        if type(other) is int:
            return self.field.element(other)
        raise TypeError("Expected finite field element or integer")

    def __add__(self, other: object) -> FieldElement:
        return self.field.element(self.representative + self._coerce(other).representative)

    __radd__ = __add__

    def __neg__(self) -> FieldElement:
        return self.field.element(-self.representative)

    def __sub__(self, other: object) -> FieldElement:
        return self + -self._coerce(other)

    def __rsub__(self, other: object) -> FieldElement:
        return self._coerce(other) - self

    def __mul__(self, other: object) -> FieldElement:
        return self.field.element(self.representative * self._coerce(other).representative)

    __rmul__ = __mul__

    def inverse(self) -> FieldElement:
        if self.representative.is_zero:
            raise ZeroDivisionError("Field zero has no multiplicative inverse")
        g, s, _ = mod_poly_extended_gcd(self.representative, self.field.modulus)
        if g != ModPolynomial.one(self.field.characteristic):
            raise ArithmeticError("Irreducible quotient failed field inverse identity")
        inverse = self.field.element(s)
        if self * inverse != self.field.one():
            raise ArithmeticError("Finite-field inverse verification failed")
        return inverse

    def __truediv__(self, other: object) -> FieldElement:
        return self * self._coerce(other).inverse()

    def __pow__(self, exponent: int) -> FieldElement:
        if type(exponent) is not int or abs(exponent) > 10**20:
            raise ValueError("Exponent outside finite field budget")
        if exponent < 0:
            return self.inverse() ** (-exponent)
        result, base = self.field.one(), self
        while exponent:
            if exponent & 1:
                result *= base
            exponent >>= 1
            if exponent:
                base *= base
        return result

    def frobenius(self) -> FieldElement:
        return self ** self.field.characteristic

    def trace(self) -> int:
        """Trace to F_p computed through all Frobenius conjugates."""
        total, current = self.field.zero(), self
        for _ in range(self.field.degree):
            total += current
            current = current.frobenius()
        if current != self or total.representative.degree > 0:
            raise ArithmeticError("Field trace identity failed")
        return total.representative.coefficients[0]

    def norm(self) -> int:
        """Norm to F_p via product of Frobenius conjugates."""
        product, current = self.field.one(), self
        for _ in range(self.field.degree):
            product *= current
            current = current.frobenius()
        if current != self or product.representative.degree > 0:
            raise ArithmeticError("Field norm identity failed")
        return product.representative.coefficients[0]

    def to_data(self) -> dict:
        return {"field_prime": self.field.characteristic,
                "field_degree": self.field.degree,
                "coefficients": list(self.representative.coefficients)}


def field_profile(prime: int, modulus: tuple[int, ...],
                  element: tuple[int, ...]) -> dict:
    """JSON-safe trace/norm/inverse report with a verified field modulus."""
    field = FiniteField(ModPolynomial(modulus, prime))
    value = field.element(element)
    inverse = None if value == field.zero() else value.inverse().to_data()
    return {
        "field_size": field.size,
        "irreducible": True,
        "element": value.to_data(),
        "inverse": inverse,
        "trace": value.trace(),
        "norm": value.norm(),
        "arithmetic": "exact finite field",
    }


__all__ = [
    "ModPolynomial", "mod_poly_gcd", "mod_poly_extended_gcd",
    "is_irreducible", "FiniteField", "FieldElement", "field_profile",
]
