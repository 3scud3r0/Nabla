"""Exact symbolic Itô formula for polynomial time/state functions."""

from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction

from ..algebra.groebner import Polynomial


def _partial(polynomial: Polynomial, index: int) -> Polynomial:
    terms = []
    for monomial, coefficient in polynomial.terms:
        if monomial[index]:
            reduced = list(monomial)
            factor = reduced[index]
            reduced[index] -= 1
            terms.append((tuple(reduced), coefficient * factor))
    return Polynomial(polynomial.variables, terms)


@dataclass(frozen=True)
class ItoDifferential:
    dt: Polynomial
    dW: Polynomial


def ito_formula(function: Polynomial, drift: Polynomial,
                diffusion: Polynomial, *, time_variable: str = "t",
                state_variable: str = "x") -> ItoDifferential:
    if not (function.variables == drift.variables == diffusion.variables):
        raise ValueError("Função e coeficientes SDE devem usar o mesmo anel")
    try:
        time_index = function.variables.index(time_variable)
        state_index = function.variables.index(state_variable)
    except ValueError as exc:
        raise ValueError("Variáveis de tempo/estado ausentes") from exc
    if time_index == state_index:
        raise ValueError("Tempo e estado devem ser variáveis distintas")
    f_t = _partial(function, time_index)
    f_x = _partial(function, state_index)
    f_xx = _partial(f_x, state_index)
    return ItoDifferential(f_t + drift * f_x + diffusion**2 * f_xx * Fraction(1, 2),
                           diffusion * f_x)


__all__ = ["ItoDifferential", "ito_formula"]


def multivariate_ito(function,drift,diffusion,variables,time='t'):
    from .._structured import expression,sympy,data
    sp=sympy();n=len(variables)
    if time in variables or not 1<=n<=8 or len(drift)!=n or len(diffusion)!=n or not diffusion or not 1<=len(diffusion[0])<=8 or any(len(row)!=len(diffusion[0]) for row in diffusion):raise ValueError('Invalid Ito system dimensions')
    names=[time]+list(variables);f,symbols=expression(function,names);t=symbols[0];x=symbols[1:]
    a=sp.Matrix([expression(v,names)[0] for v in drift]);b=sp.Matrix([[expression(v,names)[0] for v in row] for row in diffusion]);gradient=sp.Matrix([sp.diff(f,v) for v in x]);hessian=sp.hessian(f,x)
    dt=sp.diff(f,t)+(gradient.T*a)[0]+sp.trace(b*b.T*hessian)/2;dw=gradient.T*b
    return {'dt':str(sp.simplify(dt)),'dW':data(dw.applyfunc(sp.simplify)),
            'hypotheses':'f is C^(1,2) on the trajectory domain; independent standard Brownian drivers and Ito convention.'}
