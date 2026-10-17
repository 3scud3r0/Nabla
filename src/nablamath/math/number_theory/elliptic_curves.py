"""Elliptic-curve group arithmetic over prime fields (not a crypto protocol)."""

from __future__ import annotations
from dataclasses import dataclass
from .primality import miller_rabin

Point = tuple[int, int] | None


@dataclass(frozen=True)
class EllipticCurveQ:
    a: object
    b: object

    def __post_init__(self):
        from fractions import Fraction
        object.__setattr__(self,'a',Fraction(self.a));object.__setattr__(self,'b',Fraction(self.b))
        if 4*self.a**3+27*self.b**2==0:raise ValueError('Singular elliptic curve')

    def contains(self,point):
        from fractions import Fraction
        if point is None:return True
        x,y=map(Fraction,point);return y*y==x*x*x+self.a*x+self.b

    def add(self,left,right):
        from fractions import Fraction
        if not self.contains(left) or not self.contains(right):raise ValueError('Point outside rational curve')
        if left is None:return right
        if right is None:return left
        x,y=map(Fraction,left);u,v=map(Fraction,right)
        if x==u and y==-v:return None
        slope=(3*x*x+self.a)/(2*y) if x==u else (v-y)/(u-x)
        target=slope*slope-x-u;return target,slope*(x-target)-y

    def search(self,height=16):
        from fractions import Fraction
        from math import isqrt
        if type(height) is not int or not 1<=height<=128:raise ValueError('Rational height search budget exceeded')
        points=set()
        for denominator in range(1,height+1):
            for numerator in range(-height,height+1):
                x=Fraction(numerator,denominator);value=x**3+self.a*x+self.b
                if value<0:continue
                p,q=isqrt(value.numerator),isqrt(value.denominator)
                if p*p==value.numerator and q*q==value.denominator:points.add((x,Fraction(p,q)));points.add((x,-Fraction(p,q)))
        return sorted(points)


def rational_points(a,b,height=16):
    curve=EllipticCurveQ(a,b)
    return {'points':[[str(x),str(y)] for x,y in curve.search(height)],'scope':'Bounded rational-x height search, not a complete Mordell–Weil computation.'}


def two_isogeny(a,b,point):
    """Vélu degree-two map for y^2=x^3+a*x^2+b*x, kernel {O,(0,0)}."""
    from fractions import Fraction
    a,b=Fraction(a),Fraction(b)
    if b==0 or a*a==4*b:raise ValueError('Nonsingular 2-torsion model required')
    target_a,target_b=-2*a,a*a-4*b
    if point is None:return {'a':str(target_a),'b':str(target_b),'point':None}
    x,y=map(Fraction,point)
    if y*y!=x**3+a*x*x+b*x:raise ValueError('Point outside source curve')
    if x==0:return {'a':str(target_a),'b':str(target_b),'point':None}
    u=x+a+b/x;v=y*(1-b/x**2)
    return {'a':str(target_a),'b':str(target_b),'point':[str(u),str(v)]}


def rational_add(a,b,left,right):
    curve=EllipticCurveQ(a,b);point=curve.add(left,right)
    return {'point':None if point is None else list(map(str,point)),'point_at_infinity':point is None}


@dataclass(frozen=True)
class EllipticCurveFp:
    prime: int
    a: int
    b: int

    def __post_init__(self) -> None:
        if not 2 <= self.prime < 2**64 or not miller_rabin(self.prime):
            raise ValueError("O módulo da curva deve ser primo de até 64 bits")
        object.__setattr__(self, "a", self.a % self.prime)
        object.__setattr__(self, "b", self.b % self.prime)
        if (4 * self.a**3 + 27 * self.b**2) % self.prime == 0:
            raise ValueError("Curva singular")

    def contains(self, point: Point) -> bool:
        if point is None:
            return True
        x, y = point
        return (y * y - x**3 - self.a * x - self.b) % self.prime == 0

    def negate(self, point: Point) -> Point:
        if not self.contains(point):
            raise ValueError("Ponto fora da curva")
        return None if point is None else (point[0] % self.prime, -point[1] % self.prime)

    def add(self, first: Point, second: Point) -> Point:
        if not self.contains(first) or not self.contains(second):
            raise ValueError("Ponto fora da curva")
        if first is None:
            return second
        if second is None:
            return first
        x1, y1 = first[0] % self.prime, first[1] % self.prime
        x2, y2 = second[0] % self.prime, second[1] % self.prime
        if x1 == x2 and (y1 + y2) % self.prime == 0:
            return None
        slope = ((3 * x1 * x1 + self.a) * pow(2 * y1, -1, self.prime)
                 if first == second else (y2 - y1) * pow(x2 - x1, -1, self.prime)) % self.prime
        x3 = (slope * slope - x1 - x2) % self.prime
        result = (x3, (slope * (x1 - x3) - y1) % self.prime)
        if not self.contains(result):
            raise ArithmeticError("Lei de grupo produziu ponto inválido")
        return result

    def multiply(self, scalar: int, point: Point) -> Point:
        if type(scalar) is not int:
            raise ValueError("Escalar deve ser inteiro")
        if scalar < 0:
            return self.multiply(-scalar, self.negate(point))
        result, addend = None, point
        while scalar:
            if scalar & 1:
                result = self.add(result, addend)
            addend, scalar = self.add(addend, addend), scalar // 2
        return result

    def points(self, *, prime_limit: int = 10_000) -> tuple[Point, ...]:
        if self.prime > prime_limit:
            raise RuntimeError("Enumeração excede limite do corpo")
        return (None, *(point for x in range(self.prime) for y in range(self.prime)
                        if self.contains(point := (x, y))))


__all__ = ["EllipticCurveFp", "Point"]
