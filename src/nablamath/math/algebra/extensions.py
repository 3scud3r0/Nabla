"""Exact simple algebraic extensions ``Q(α)=Q[x]/(m(x))`` for degree 2/3."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import gcd
from math import isqrt
from typing import Iterable

Coefficients = tuple[Fraction, ...]  # low degree first


def _trim(values: Iterable[Fraction | int]) -> Coefficients:
    result = [Fraction(value) for value in values]
    while result and result[-1] == 0:
        result.pop()
    return tuple(result)


def _add(first: Coefficients, second: Coefficients) -> Coefficients:
    size = max(len(first), len(second))
    return _trim((first[index] if index < len(first) else 0)
                 + (second[index] if index < len(second) else 0) for index in range(size))


def _neg(values: Coefficients) -> Coefficients:
    return tuple(-value for value in values)


def _mul(first: Coefficients, second: Coefficients) -> Coefficients:
    if not first or not second:
        return ()
    result = [Fraction(0)] * (len(first) + len(second) - 1)
    for left_degree, left in enumerate(first):
        for right_degree, right in enumerate(second):
            result[left_degree + right_degree] += left * right
    return _trim(result)


def _divmod(dividend: Coefficients, divisor: Coefficients) -> tuple[Coefficients, Coefficients]:
    if not divisor:
        raise ZeroDivisionError("Polinômio divisor zero")
    remainder = list(dividend)
    quotient = [Fraction(0)] * max(0, len(dividend) - len(divisor) + 1)
    while len(remainder) >= len(divisor) and remainder:
        degree = len(remainder) - len(divisor)
        factor = remainder[-1] / divisor[-1]
        quotient[degree] += factor
        for index, coefficient in enumerate(divisor):
            remainder[degree + index] -= factor * coefficient
        remainder = list(_trim(remainder))
    return _trim(quotient), _trim(remainder)


def _xgcd(first: Coefficients, second: Coefficients) -> tuple[Coefficients, Coefficients, Coefficients]:
    old_r, r = first, second
    old_s, s = (Fraction(1),), ()
    old_t, t = (), (Fraction(1),)
    while r:
        quotient, remainder = _divmod(old_r, r)
        old_r, r = r, remainder
        old_s, s = s, _add(old_s, _neg(_mul(quotient, s)))
        old_t, t = t, _add(old_t, _neg(_mul(quotient, t)))
    if old_r:
        scale = old_r[-1]
        old_r = tuple(value / scale for value in old_r)
        old_s = tuple(value / scale for value in old_s)
        old_t = tuple(value / scale for value in old_t)
    return old_r, old_s, old_t


def _integer_polynomial(values: Coefficients) -> tuple[int, ...]:
    common = 1
    for value in values:
        common = common * value.denominator // gcd(common, value.denominator)
    integers = tuple(int(value * common) for value in values)
    common_gcd = 0
    for value in integers:
        common_gcd = gcd(common_gcd, abs(value))
    return tuple(value // max(1, common_gcd) for value in integers)


def _has_rational_root(values: Coefficients) -> bool:
    integers = _integer_polynomial(values)
    if max(abs(v) for v in integers)>100000:
        from .._structured import sympy
        sp=sympy();x=sp.Symbol('x')
        return not sp.Poly(sum(int(v)*x**i for i,v in enumerate(integers)),x,domain=sp.QQ).is_irreducible
    constant, leading = integers[0], integers[-1]
    if constant == 0:
        return True
    numerators = [value for value in range(1, abs(constant) + 1) if constant % value == 0]
    denominators = [value for value in range(1, abs(leading) + 1) if leading % value == 0]
    for numerator in numerators:
        for denominator in denominators:
            for sign in (-1, 1):
                root = Fraction(sign * numerator, denominator)
                if sum(coefficient * root**degree for degree, coefficient in enumerate(values)) == 0:
                    return True
    return False


@dataclass(frozen=True)
class AlgebraicField:
    minimal_polynomial: Coefficients
    symbol: str = "α"

    def __post_init__(self) -> None:
        polynomial = _trim(self.minimal_polynomial)
        degree = len(polynomial) - 1
        if not 2 <= degree <= 16:
            raise ValueError("Extension degree must be between two and sixteen")
        if polynomial[-1] != 1:
            polynomial = tuple(value / polynomial[-1] for value in polynomial)
        if any(max(v.numerator.bit_length(),v.denominator.bit_length())>4096 for v in polynomial):
            raise ValueError('Algebraic coefficient input budget exceeded')
        if degree == 2:
            discriminant=polynomial[1]**2-4*polynomial[0]*polynomial[2]
            reducible=(discriminant>=0 and isqrt(discriminant.numerator)**2==discriminant.numerator and isqrt(discriminant.denominator)**2==discriminant.denominator)
        elif degree == 3:
            reducible = _has_rational_root(polynomial)
        else:
            from .._structured import sympy
            sp=sympy();x=sp.Symbol('x')
            reducible = not sp.Poly(sum(sp.Rational(str(v))*x**i for i,v in enumerate(polynomial)),x,domain=sp.QQ).is_irreducible
        if reducible:raise ValueError("Polinômio não é irredutível sobre Q")
        object.__setattr__(self, "minimal_polynomial", polynomial)

    @property
    def degree(self) -> int:
        return len(self.minimal_polynomial) - 1

    def element(self, coefficients: Iterable[Fraction | int]) -> AlgebraicNumber:
        _, reduced = _divmod(_trim(coefficients), self.minimal_polynomial)
        return AlgebraicNumber(self, reduced + (Fraction(0),) * (self.degree - len(reduced)))

    @property
    def alpha(self) -> AlgebraicNumber:
        return self.element((0, 1))


@dataclass(frozen=True)
class AlgebraicNumber:
    field: AlgebraicField
    coefficients: Coefficients

    def __post_init__(self) -> None:
        if len(self.coefficients) != self.field.degree:
            raise ValueError("Representante fora da dimensão da extensão")
        if any(max(Fraction(v).numerator.bit_length(),Fraction(v).denominator.bit_length())>65536 for v in self.coefficients):
            raise ValueError('Algebraic element arithmetic budget exceeded')

    def _coerce(self, other: AlgebraicNumber | Fraction | int) -> AlgebraicNumber:
        if isinstance(other, AlgebraicNumber):
            if other.field != self.field:
                raise ValueError("Elementos pertencem a extensões diferentes")
            return other
        return self.field.element((Fraction(other),))

    def __add__(self, other: AlgebraicNumber | Fraction | int) -> AlgebraicNumber:
        right = self._coerce(other)
        return self.field.element(_add(self.coefficients, right.coefficients))

    __radd__ = __add__

    def __neg__(self) -> AlgebraicNumber:
        return self.field.element(_neg(self.coefficients))

    def __sub__(self, other: AlgebraicNumber | Fraction | int) -> AlgebraicNumber:
        return self + -self._coerce(other)

    def __mul__(self, other: AlgebraicNumber | Fraction | int) -> AlgebraicNumber:
        right = self._coerce(other)
        return self.field.element(_mul(self.coefficients, right.coefficients))

    __rmul__ = __mul__

    def inverse(self) -> AlgebraicNumber:
        if not any(self.coefficients):
            raise ZeroDivisionError("Zero não possui inverso")
        gcd_polynomial, coefficient, _ = _xgcd(_trim(self.coefficients), self.field.minimal_polynomial)
        if gcd_polynomial != (Fraction(1),):
            raise ArithmeticError("Elemento não invertível; extensão inconsistente")
        return self.field.element(coefficient)

    def __truediv__(self, other: AlgebraicNumber | Fraction | int) -> AlgebraicNumber:
        return self * self._coerce(other).inverse()

    def __pow__(self, exponent: int) -> AlgebraicNumber:
        if type(exponent) is not int or abs(exponent)>10000:
            raise ValueError("Expoente deve ser inteiro entre -10000 e 10000")
        if exponent < 0:
            return self.inverse() ** -exponent
        result, factor = self.field.element((1,)), self
        while exponent:
            if exponent & 1:
                result = result * factor
            factor = factor * factor
            exponent //= 2
        return result


__all__ = ["AlgebraicField", "AlgebraicNumber", "Coefficients"]


def number_field(radicals,polynomial=None,variable='x'):
    """Construct the primitive element of a supplied tower of algebraic generators."""
    from .._structured import expression,sympy,data
    sp=sympy()
    if not isinstance(radicals,list) or not 1<=len(radicals)<=8:raise ValueError('Require 1–8 algebraic generators')
    values=[]
    for raw in radicals:
        value,_=expression(raw,[variable])
        if value.free_symbols or value.is_algebraic is not True:raise ValueError('Constant algebraic generators required')
        values.append(value)
    primitive=sp.polys.numberfields.to_number_field(values)
    result={'primitive_element':str(primitive.as_expr()),'minimal_polynomial':str(primitive.minpoly.as_expr()),
            'degree':primitive.minpoly.degree(),'generator_coordinates':[data(sp.polys.numberfields.to_number_field(v,primitive).coeffs()) for v in values]}
    if result['degree']>64:raise ValueError('Primitive extension degree budget exceeded')
    if polynomial is not None:
        p,(x,)=expression(polynomial,[variable],functions=False)
        coefficient,factors=sp.factor_list(p,x,extension=values)
        result['factorization']={'coefficient':str(coefficient),'factors':[[str(f),m] for f,m in factors]}
    return result


def field_arithmetic(polynomial,left,*,right=None,operation='multiply',exponent=1):
    from ...ops._area_utils import vector
    field=AlgebraicField(tuple(vector(polynomial,maximum=17)));a=field.element(vector(left,maximum=64))
    if operation=='inverse':value=a.inverse()
    elif operation=='power':value=a**exponent
    else:
        if right is None:raise ValueError('Binary field operation requires right operand')
        b=field.element(vector(right,maximum=64))
        if operation=='add':value=a+b
        elif operation=='subtract':value=a-b
        elif operation=='multiply':value=a*b
        elif operation=='divide':value=a/b
        else:raise ValueError('Unknown field operation')
    return {'coefficients':list(map(str,value.coefficients)),'degree':field.degree,'arithmetic':'exact_Q_extension'}
