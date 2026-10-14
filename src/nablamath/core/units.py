"""Seven SI base dimensions and exact multiplicative conversions (no affine units)."""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
from ..expression import Binary, Expr, Number, Symbol
from .semantic_ir import rational


@dataclass(frozen=True)
class Unit:
    dimensions: tuple[int, ...] = (0,)*7  # kg, m, s, A, K, mol, cd
    scale: Fraction = Fraction(1)
    symbol: str = '1'

    def __post_init__(self):
        if len(self.dimensions) != 7 or any(type(v) is not int or abs(v)>64 for v in self.dimensions):
            raise ValueError('Dimensao SI invalida')
        scale = rational(self.scale)
        if scale <= 0:
            raise ValueError('Escala precisa ser positiva')
        object.__setattr__(self, 'dimensions', tuple(self.dimensions))
        object.__setattr__(self, 'scale', scale)

    def __mul__(self, other):
        return Unit(tuple(a+b for a,b in zip(self.dimensions,other.dimensions)),self.scale*other.scale,f'{self.symbol}*{other.symbol}')

    def __truediv__(self, other):
        return self * other**-1

    def __pow__(self, exponent):
        if type(exponent) is not int or abs(exponent)>32:
            raise ValueError('Expoente dimensional inteiro limitado a 32')
        return Unit(tuple(v*exponent for v in self.dimensions),self.scale**exponent,f'({self.symbol})^{exponent}')

    def to_data(self):
        return {'dimensions':list(self.dimensions),'scale':str(self.scale)}


ONE = Unit()
KILOGRAM = Unit((1,0,0,0,0,0,0),symbol='kg')
METER = Unit((0,1,0,0,0,0,0),symbol='m')
SECOND = Unit((0,0,1,0,0,0,0),symbol='s')
AMPERE = Unit((0,0,0,1,0,0,0),symbol='A')
KELVIN = Unit((0,0,0,0,1,0,0),symbol='K')
MOLE = Unit((0,0,0,0,0,1,0),symbol='mol')
CANDELA = Unit((0,0,0,0,0,0,1),symbol='cd')
KILOMETER = Unit(METER.dimensions,Fraction(1000),'km')
HOUR = Unit(SECOND.dimensions,Fraction(3600),'h')
NEWTON = KILOGRAM*METER/SECOND**2
JOULE = NEWTON*METER
VOLT = JOULE/(AMPERE*SECOND)
UNITS = {'1':ONE,'kg':KILOGRAM,'m':METER,'s':SECOND,'A':AMPERE,'K':KELVIN,'mol':MOLE,'cd':CANDELA,
         'km':KILOMETER,'h':HOUR,'N':NEWTON,'J':JOULE,'V':VOLT}


@dataclass(frozen=True)
class Quantity:
    value: Fraction
    unit: Unit = ONE

    def __post_init__(self):
        object.__setattr__(self,'value',rational(self.value))

    def to(self, unit):
        if self.unit.dimensions != unit.dimensions:
            raise ValueError('Unidades incompativeis')
        return Quantity(self.value*self.unit.scale/unit.scale,unit)

    def __add__(self, other):
        return Quantity(self.value+other.to(self.unit).value,self.unit)

    def __sub__(self, other):
        return Quantity(self.value-other.to(self.unit).value,self.unit)

    def __mul__(self, other):
        return Quantity(self.value*other.value,self.unit*other.unit)

    def __truediv__(self, other):
        return Quantity(self.value/other.value,self.unit/other.unit)

    def __pow__(self, exponent):
        if type(exponent) is not int or abs(exponent)>32:
            raise ValueError('Expoente de quantidade deve ser inteiro limitado a 32')
        return Quantity(self.value**exponent,self.unit**exponent)


def infer_unit(expr: Expr, symbols: dict[str,Unit]) -> Unit:
    if isinstance(expr,Number):
        return ONE
    if isinstance(expr,Symbol):
        if expr.name not in symbols:
            raise ValueError(f'Unidade nao declarada: {expr.name}')
        return symbols[expr.name]
    a,b=infer_unit(expr.left,symbols),infer_unit(expr.right,symbols)
    if expr.op in {'+','-'}:
        if a.dimensions != b.dimensions:
            raise ValueError('Soma/subtracao dimensionalmente invalida')
        # Bindings are evaluated in SI, including when their display scales differ.
        return Unit(a.dimensions)
    if expr.op=='*':
        return a*b
    if expr.op=='/':
        return a/b
    if not isinstance(expr.right,Number) or expr.right.value.denominator!=1:
        raise ValueError('Potencia exige expoente inteiro literal')
    return a**expr.right.value.numerator
