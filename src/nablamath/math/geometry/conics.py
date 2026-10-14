"""Exact planar conics, affine coordinates and Euclidean constructions."""
from dataclasses import dataclass
from fractions import Fraction
from .euclidean import Point2
from ..linear_algebra import Matrix,solve_linear


@dataclass(frozen=True)
class Conic:
    # Ax² + Bxy + Cy² + Dx + Ey + F = 0
    coefficients: tuple[Fraction,...]

    def __post_init__(self):
        if len(self.coefficients)!=6:
            raise ValueError('Conica requer seis coeficientes')
        object.__setattr__(self,'coefficients',tuple(Fraction(v) for v in self.coefficients))

    def evaluate(self,point):
        a,b,c,d,e,f=self.coefficients;x,y=point.x,point.y
        return a*x*x+b*x*y+c*y*y+d*x+e*y+f

    def classify(self):
        a,b,c,d,e,f=self.coefficients
        if a==b==c==0:
            return 'line' if d or e else 'whole_plane' if f==0 else 'empty'
        matrix=Matrix(((a,b/2,d/2),(b/2,c,e/2),(d/2,e/2,f)))
        if matrix.determinant()==0:
            return 'degenerate'
        discriminant=b*b-4*a*c
        if discriminant>0:
            return 'hyperbola'
        if discriminant==0:
            return 'parabola'
        center=solve_linear(Matrix(((2*a,b),(b,2*c))),(-d,-e)).particular
        return 'ellipse' if self.evaluate(Point2(*center))*a<0 else 'empty'


def affine_transform(point,matrix,translation=(0,0)):
    if matrix.shape!=(2,2) or len(translation)!=2:
        raise ValueError('Transformacao planar requer matriz 2x2 e translacao 2D')
    x,y=point.x,point.y
    return Point2(matrix.rows[0][0]*x+matrix.rows[0][1]*y+Fraction(translation[0]),
                  matrix.rows[1][0]*x+matrix.rows[1][1]*y+Fraction(translation[1]))


def circumcenter(a,b,c):
    rows=((2*(b.x-a.x),2*(b.y-a.y)),(2*(c.x-a.x),2*(c.y-a.y)))
    rhs=(b.x*b.x+b.y*b.y-a.x*a.x-a.y*a.y,c.x*c.x+c.y*c.y-a.x*a.x-a.y*a.y)
    result=solve_linear(Matrix(rows),rhs)
    if result.status!='unique':
        raise ValueError('Circuncentro indefinido para pontos colineares')
    return Point2(*result.particular)
