"""Rational root factorization with multiplicities and explicit unresolved residuals."""
from dataclasses import dataclass
from fractions import Fraction
from math import isqrt,lcm
from .univariate import Polynomial


@dataclass(frozen=True)
class RationalFactorization:
    leading: Fraction
    roots: tuple[Fraction,...]
    residual: Polynomial
    complete: bool


def factor_rational(polynomial: Polynomial, *, divisor_budget: int=100000) -> RationalFactorization:
    if polynomial.is_zero or polynomial.degree>16 or type(divisor_budget) is not int or not 1<=divisor_budget<=1000000:
        raise ValueError('Fatoracao requer polinomio nao nulo ate grau 16 e orcamento valido')
    original_leading=polynomial.leading
    current=polynomial.monic()
    roots=[]
    spent=0
    def divisors(value):
        nonlocal spent
        value=abs(value)
        if isqrt(value)>divisor_budget-spent:
            raise ValueError('Orcamento de divisores excedido')
        result=set()
        for d in range(1,isqrt(value)+1):
            spent+=1
            if value%d==0:
                result.update((d,value//d))
        return result
    while current.degree>0:
        if current.coefficients[0]==0:
            root=Fraction()
        else:
            denominator=lcm(*(v.denominator for v in current.coefficients))
            integers=[int(v*denominator) for v in current.coefficients]
            numerators=divisors(integers[0])
            denominators=divisors(integers[-1])
            if len(numerators)*len(denominators)*2>divisor_budget-spent:
                raise ValueError('Orcamento de candidatos excedido')
            candidates=sorted({Fraction(sign*p,q) for p in numerators for q in denominators for sign in (-1,1)})
            spent+=len(candidates)
            root=next((r for r in candidates if current(r)==0),None)
            if root is None:
                break
        quotient,remainder=current.divmod(Polynomial((-root,1)))
        if not remainder.is_zero:
            raise ArithmeticError('Divisao de fator divergente')
        roots.append(root)
        current=quotient
    return RationalFactorization(original_leading,tuple(sorted(roots)),current,current.degree==0)
