"""Small strictly convex rational QPs by active sets and exact KKT certificates."""
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from ..linear_algebra import Matrix,solve_linear


@dataclass(frozen=True)
class QuadraticSolution:
    point: tuple[Fraction,...]
    value: Fraction
    multipliers: tuple[Fraction,...]
    active: tuple[int,...]
    kkt_verified: bool


def minimize_quadratic(hessian,linear,constraints=(),upper=(),constant=0):
    n,m=hessian.shape
    if n!=m or not 1<=n<=8 or len(linear)!=n or len(constraints)!=len(upper) or len(constraints)>8 or any(len(row)!=n for row in constraints):
        raise ValueError('QP requer 1..8 variaveis e ate 8 desigualdades')
    h=hessian.rows;b=tuple(Fraction(v) for v in linear)
    a=tuple(tuple(Fraction(v) for v in row) for row in constraints)
    bounds=tuple(Fraction(v) for v in upper)
    if any(h[i][j]!=h[j][i] for i in range(n) for j in range(n)):
        raise ValueError('Hessiana deve ser simetrica')
    for k in range(1,n+1):
        if Matrix(tuple(row[:k] for row in h[:k])).determinant()<=0:
            raise ValueError('Hessiana deve ser definida positiva')
    for size in range(min(n,len(a))+1):
        for active in combinations(range(len(a)),size):
            kkt=tuple(tuple(h[i])+tuple(a[j][i] for j in active) for i in range(n))
            kkt+=tuple(a[j]+(Fraction(),)*size for j in active)
            result=solve_linear(Matrix(kkt),tuple(-v for v in b)+tuple(bounds[j] for j in active))
            if result.status!='unique':
                continue
            point=result.particular[:n];selected=result.particular[n:]
            if any(v<0 for v in selected) or any(sum(v*x for v,x in zip(row,point))>bound for row,bound in zip(a,bounds)):
                continue
            multipliers=tuple(selected[active.index(j)] if j in active else Fraction() for j in range(len(a)))
            residuals=tuple(sum(h[i][j]*point[j] for j in range(n))+b[i]+sum(a[j][i]*multipliers[j] for j in range(len(a))) for i in range(n))
            complementary=all(mult*(sum(v*x for v,x in zip(row,point))-bound)==0 for row,bound,mult in zip(a,bounds,multipliers))
            if any(residuals) or not complementary:
                raise ArithmeticError('Certificado KKT divergente')
            value=sum(point[i]*h[i][j]*point[j] for i in range(n) for j in range(n))/2+sum(v*x for v,x in zip(b,point))+Fraction(constant)
            return QuadraticSolution(point,value,multipliers,active,True)
    raise ValueError('Problema inviavel no dominio convexo declarado')
