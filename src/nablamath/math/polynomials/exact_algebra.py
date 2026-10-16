"""Certified exact univariate Euclidean and quotient-algebra operations over Q.

A quotient is not called a field: reducible moduli contain nonunits. Inversion
returns a Bezout witness and rejects nonunits; no irreducibility is assumed.
"""
from dataclasses import dataclass
from fractions import Fraction
from .univariate import Polynomial
from .real_roots import _checked, _input, _divide, _scale

_ZERO = Polynomial((0,))
_ONE = Polynomial((1,))
_X = Polynomial((0,1))


def polynomial_power(polynomial, exponent):
    _checked(polynomial)
    if type(exponent) is not int or not 0 <= exponent <= 32:
        raise ValueError('Polynomial exponent must be in [0,32]')
    if polynomial.degree * exponent > 32:
        raise ValueError('Polynomial power exceeds degree budget')
    result = _ONE
    base = polynomial
    while exponent:
        if exponent & 1:
            result = _checked(result * base)
        exponent >>= 1
        if exponent:
            base = _checked(base * base)
    return result


@dataclass(frozen=True)
class BezoutCertificate:
    left: Polynomial
    right: Polynomial
    gcd: Polynomial
    left_multiplier: Polynomial
    right_multiplier: Polynomial

    def verify(self):
        try:
            for p in (self.left,self.right,self.gcd,self.left_multiplier,self.right_multiplier):
                _checked(p)
            if self.gcd.is_zero:
                return self.left.is_zero and self.right.is_zero
            if self.gcd.leading != 1:
                return False
            _, left_remainder = _divide(self.left,self.gcd)
            _, right_remainder = _divide(self.right,self.gcd)
            identity = self.left*self.left_multiplier + self.right*self.right_multiplier
            return identity == self.gcd and left_remainder.is_zero and right_remainder.is_zero
        except (ValueError,TypeError,AttributeError,ArithmeticError):
            return False


def extended_polynomial_gcd(left,right):
    """Return the monic gcd plus exact Bezout identity and divisibility witnesses."""
    _checked(left)
    _checked(right)
    old_r,r = left,right
    old_s,s = _ONE,_ZERO
    old_t,t = _ZERO,_ONE
    while not r.is_zero:
        quotient,remainder = _divide(old_r,r)
        old_r,r = r,remainder
        old_s,s = s,_checked(old_s-quotient*s)
        old_t,t = t,_checked(old_t-quotient*t)
    if not old_r.is_zero:
        scale=1/old_r.leading
        old_r,old_s,old_t = (_scale(p,scale) for p in (old_r,old_s,old_t))
    result=BezoutCertificate(left,right,old_r,old_s,old_t)
    if not result.verify():
        raise ArithmeticError('Bezout certificate replay failed')
    return result


@dataclass(frozen=True)
class QuotientElement:
    """Canonical element of Q[x]/(modulus), with no field assumption."""
    modulus: Polynomial
    representative: Polynomial

    def __post_init__(self):
        _input(self.modulus)
        _checked(self.representative)
        if self.modulus.degree < 1 or self.modulus.leading != 1:
            raise ValueError('Quotient requires positive-degree monic modulus')
        _,remainder=_divide(self.representative,self.modulus)
        object.__setattr__(self,'representative',remainder)

    @classmethod
    def generator(cls,modulus):
        return cls(modulus,_X)

    def _coerce(self,other):
        if isinstance(other,QuotientElement):
            if other.modulus != self.modulus:
                raise ValueError('Quotient moduli differ')
            return other
        if isinstance(other,bool) or not isinstance(other,(int,Fraction,Polynomial)):
            raise ValueError('Exact quotient constant or polynomial required')
        return QuotientElement(self.modulus,other if isinstance(other,Polynomial) else Polynomial((other,)))

    def __add__(self,other):
        other=self._coerce(other)
        return QuotientElement(self.modulus,self.representative+other.representative)

    __radd__=__add__

    def __neg__(self):
        return QuotientElement(self.modulus,_scale(self.representative,-1))

    def __sub__(self,other):
        return self+-self._coerce(other)

    def __rsub__(self,other):
        return self._coerce(other)-self

    def __mul__(self,other):
        other=self._coerce(other)
        # Products are reduced by Euclidean division, with degree <= 2d-2.
        if self.modulus.degree > 16:
            raise ValueError('Quotient multiplication requires modulus degree <=16')
        return QuotientElement(self.modulus,_checked(self.representative*other.representative))

    __rmul__=__mul__

    def inverse_with_certificate(self):
        certificate=extended_polynomial_gcd(self.representative,self.modulus)
        if certificate.gcd != _ONE:
            raise ZeroDivisionError('Quotient element is not a unit')
        inverse=QuotientElement(self.modulus,certificate.left_multiplier)
        if (self*inverse).representative != _ONE:
            raise ArithmeticError('Quotient inverse replay failed')
        return inverse,certificate

    def inverse(self):
        return self.inverse_with_certificate()[0]

    def __truediv__(self,other):
        return self*self._coerce(other).inverse()

    def __rtruediv__(self,other):
        return self._coerce(other)/self

    def __pow__(self,exponent):
        if type(exponent) is not int or abs(exponent)>10000:
            raise ValueError('Quotient exponent must be an integer in [-10000,10000]')
        base=self if exponent>=0 else self.inverse()
        exponent=abs(exponent)
        result=self._coerce(1)
        while exponent:
            if exponent&1:
                result=result*base
            exponent >>= 1
            if exponent:
                base=base*base
        return result

    def multiplication_matrix(self):
        """Exact Q-linear multiplication action in basis 1,x,...,x**(d-1)."""
        from ..linear_algebra.matrices import Matrix
        degree=self.modulus.degree
        if degree>16:
            raise ValueError('Multiplication matrix degree budget exceeded')
        columns=[]
        for index in range(degree):
            monomial=Polynomial((0,)*index+(1,))
            product=(self*self._coerce(monomial)).representative
            columns.append(product.coefficients+(Fraction(),)*(degree-len(product.coefficients)))
        return Matrix(tuple(tuple(column[row] for column in columns) for row in range(degree)))

    def trace(self):
        matrix=self.multiplication_matrix()
        return sum(matrix.rows[i][i] for i in range(matrix.shape[0]))

    def norm(self):
        return self.multiplication_matrix().determinant()


def polynomial_crt(residues,moduli):
    """Solve polynomial congruences for pairwise-coprime rational moduli.

    The result is the unique representative of degree below the product modulus.
    Noncoprime input is rejected instead of silently discarding constraints.
    """
    if not isinstance(residues,(tuple,list)) or not isinstance(moduli,(tuple,list)):
        raise ValueError('Finite congruence sequences required')
    if not 1<=len(residues)==len(moduli)<=16:
        raise ValueError('CRT requires 1..16 congruences')
    for residue,modulus in zip(residues,moduli):
        _checked(residue)
        _input(modulus)
        if modulus.degree<1 or modulus.leading!=1:
            raise ValueError('CRT moduli must be positive-degree monic polynomials')
    if sum(modulus.degree for modulus in moduli)>16:
        raise ValueError('CRT total degree budget exceeded')
    product=_ONE
    for modulus in moduli:
        product=_checked(product*modulus)
    result=_ZERO
    for residue,modulus in zip(residues,moduli):
        complement,remainder=_divide(product,modulus)
        if not remainder.is_zero:
            raise ArithmeticError('CRT complement division failed')
        certificate=extended_polynomial_gcd(complement,modulus)
        if certificate.gcd != _ONE:
            raise ValueError('CRT moduli are not pairwise coprime')
        _,inverse=_divide(certificate.left_multiplier,modulus)
        _,reduced_residue=_divide(residue,modulus)
        _,term=_divide(_checked(reduced_residue*inverse*complement),product)
        _,result=_divide(_checked(result+term),product)
    for residue,modulus in zip(residues,moduli):
        _,actual=_divide(result,modulus)
        _,expected=_divide(residue,modulus)
        if actual != expected:
            raise ArithmeticError('CRT congruence replay failed')
    return result,product


def resultant(left,right):
    """Exact Sylvester determinant (degree sum <=16), including constants."""
    _checked(left)
    _checked(right)
    if left.is_zero or right.is_zero:
        return Fraction()
    if left.degree+right.degree>16:
        raise ValueError('Resultant total degree budget exceeded')
    if left.degree==0:
        return left.leading**right.degree
    if right.degree==0:
        return right.leading**left.degree
    from ..linear_algebra.matrices import Matrix
    m,n=left.degree,right.degree
    rows=[]
    for polynomial,count in ((left,n),(right,m)):
        coefficients=tuple(reversed(polynomial.coefficients))
        for shift in range(count):
            rows.append((Fraction(),)*shift+coefficients+(Fraction(),)*(m+n-shift-len(coefficients)))
    return Matrix(tuple(rows)).determinant()


def discriminant(polynomial):
    """Exact discriminant; zero detects repeated roots in characteristic zero."""
    _input(polynomial)
    if polynomial.degree==0:
        return Fraction(1)
    n=polynomial.degree
    return (-1)**(n*(n-1)//2)*resultant(polynomial,polynomial.derivative())/polynomial.leading


__all__=['BezoutCertificate','extended_polynomial_gcd','polynomial_power','QuotientElement',
         'polynomial_crt','resultant','discriminant']
