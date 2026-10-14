"""Decimal approximations carry exact rounding error and outward interval bounds."""
from dataclasses import dataclass
from decimal import Decimal,localcontext,ROUND_HALF_EVEN,ROUND_FLOOR,ROUND_CEILING
from fractions import Fraction
from .semantic_ir import rational


@dataclass(frozen=True)
class PrecisionPolicy:
    digits: int=34

    def __post_init__(self):
        if type(self.digits) is not int or not 8<=self.digits<=1000:
            raise ValueError('Precisao deve estar entre 8 e 1000 digitos')

    def approximate(self,value):
        value=rational(value)
        with localcontext() as context:
            context.prec=self.digits
            context.rounding=ROUND_HALF_EVEN
            decimal=Decimal(value.numerator)/Decimal(value.denominator)
        return {'decimal':str(decimal),'exact':str(value),'absolute_error':str(abs(Fraction(decimal)-value)),
                'digits':self.digits,'rounding':'half_even'}

    def interval(self,value):
        value=rational(value)
        bounds=[]
        for rounding in (ROUND_FLOOR,ROUND_CEILING):
            with localcontext() as context:
                context.prec=self.digits
                context.rounding=rounding
                bounds.append(Decimal(value.numerator)/Decimal(value.denominator))
        return tuple(bounds)


@dataclass(frozen=True)
class RationalInterval:
    lower: Fraction
    upper: Fraction

    def __post_init__(self):
        object.__setattr__(self,'lower',rational(self.lower))
        object.__setattr__(self,'upper',rational(self.upper))
        if self.lower>self.upper:
            raise ValueError('Intervalo invertido')

    def __add__(self,other):
        return RationalInterval(self.lower+other.lower,self.upper+other.upper)

    def __mul__(self,other):
        values=[a*b for a in (self.lower,self.upper) for b in (other.lower,other.upper)]
        return RationalInterval(min(values),max(values))

    def __truediv__(self,other):
        if other.lower<=0<=other.upper:
            raise ValueError('Intervalo divisor contem zero')
        return self*RationalInterval(1/other.upper,1/other.lower)
