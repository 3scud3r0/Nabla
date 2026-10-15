"""Bounded exact (weighted) multivariate least squares over rational observations."""
from dataclasses import dataclass
from fractions import Fraction
from ...core.semantic_ir import rational
from ..linear_algebra import Matrix


@dataclass(frozen=True)
class ExactLinearFit:
    coefficients: tuple[Fraction,...]
    residual_sum_squares: Fraction
    residuals: tuple[Fraction,...]
    degrees_of_freedom: int
    r_squared: Fraction | None
    coefficient_covariance: tuple[tuple[Fraction,...],...]
    intercept: bool

    def predict(self,row):
        values=tuple(rational(v) for v in row)
        if self.intercept:values=(Fraction(1),*values)
        if len(values)!=len(self.coefficients):raise ValueError('Preditor incompatível')
        return sum((a*b for a,b in zip(values,self.coefficients)),Fraction())


def exact_least_squares(predictors,response,*,intercept=True,weights=None):
    if type(intercept) is not bool or not 2<=len(predictors)<=128 or len(response)!=len(predictors):raise ValueError('Observações inválidas')
    columns=len(predictors[0])
    if not 1<=columns<=16 or any(len(row)!=columns for row in predictors):raise ValueError('Preditores retangulares limitados obrigatórios')
    rows=tuple(((Fraction(1),) if intercept else ())+tuple(rational(v) for v in row) for row in predictors)
    y=tuple(rational(v) for v in response);n=len(rows);p=len(rows[0])
    if n<=p:raise ValueError('Regressão requer graus de liberdade residuais positivos')
    w=tuple(Fraction(1) for _ in rows) if weights is None else tuple(rational(v) for v in weights)
    if len(w)!=n or any(v<=0 for v in w):raise ValueError('Pesos positivos compatíveis obrigatórios')
    if any(max(v.numerator.bit_length(),v.denominator.bit_length())>512 for row in rows for v in row) or any(max(v.numerator.bit_length(),v.denominator.bit_length())>512 for v in (*y,*w)):
        raise ValueError('Custo racional de entrada excedido')
    gram=Matrix(tuple(tuple(sum(w[k]*rows[k][i]*rows[k][j] for k in range(n)) for j in range(p)) for i in range(p)))
    rhs=Matrix(tuple((sum(w[k]*rows[k][i]*y[k] for k in range(n)),) for i in range(p)))
    inverse=gram.inverse();coefficients=tuple(row[0] for row in (inverse@rhs).rows)
    residuals=tuple(y[k]-sum(a*b for a,b in zip(rows[k],coefficients)) for k in range(n))
    sse=sum(w[k]*residuals[k]**2 for k in range(n));mean=sum(a*b for a,b in zip(w,y))/sum(w)
    total=sum(w[k]*(y[k]-mean)**2 for k in range(n));sigma=sse/(n-p)
    covariance=tuple(tuple(sigma*v for v in row) for row in inverse.rows)
    return ExactLinearFit(coefficients,sse,residuals,n-p,1-sse/total if total else None,covariance,intercept)
