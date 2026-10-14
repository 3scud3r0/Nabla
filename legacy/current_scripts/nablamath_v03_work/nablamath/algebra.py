from __future__ import annotations

"""Symbolic algebra utilities for NablaMath.

This module is intentionally conservative: it prefers correct, explainable
transformations over aggressive CAS behaviour.  It adds expression expansion,
polynomial coefficient extraction for one variable, quadratic factorization,
and small symbolic reports.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import math

from .core import Expr, Symbol, Number, Add, Mul, Pow, Neg, to_expr, sqrt


def structural_key(expr: Expr) -> str:
    return repr(expr)


def expand(expr: Expr) -> Expr:
    """Expand products and integer powers in a small but useful symbolic subset."""
    expr = expr.simplify()
    if isinstance(expr, Add):
        return (expand(expr.left) + expand(expr.right)).simplify()
    if isinstance(expr, Neg):
        return (-expand(expr.expr)).simplify()
    if isinstance(expr, Mul):
        left = expand(expr.left)
        right = expand(expr.right)
        if isinstance(left, Add):
            return expand(left.left * right + left.right * right).simplify()
        if isinstance(right, Add):
            return expand(left * right.left + left * right.right).simplify()
        return (left * right).simplify()
    if isinstance(expr, Pow):
        base = expand(expr.base)
        exponent = expr.exponent.simplify()
        if isinstance(exponent, Number) and float(exponent.value).is_integer():
            n = int(exponent.value)
            if n == 0:
                return Number(1)
            if n > 0 and n <= 12:
                out: Expr = Number(1)
                for _ in range(n):
                    out = expand(out * base)
                return out.simplify()
        return Pow(base, exponent).simplify()
    return expr


def _poly_add(a: Dict[int, Expr], b: Dict[int, Expr]) -> Dict[int, Expr]:
    out = dict(a)
    for k, v in b.items():
        out[k] = (out.get(k, Number(0)) + v).simplify()
    return {k: v for k, v in out.items() if not (isinstance(v, Number) and abs(float(v.value)) < 1e-12)}


def _poly_mul(a: Dict[int, Expr], b: Dict[int, Expr]) -> Dict[int, Expr]:
    out: Dict[int, Expr] = {}
    for da, ca in a.items():
        for db, cb in b.items():
            d = da + db
            out[d] = (out.get(d, Number(0)) + ca * cb).simplify()
    return {k: v for k, v in out.items() if not (isinstance(v, Number) and abs(float(v.value)) < 1e-12)}


def polynomial_coefficients(expr: Expr, var: Symbol) -> Dict[int, Expr]:
    """Return coefficients of expr as a polynomial in var.

    Example: x**2 + 3*x + 2 -> {2: 1, 1: 3, 0: 2}
    Raises ValueError when the expression is outside this polynomial subset.
    """
    expr = expand(expr).simplify()
    if isinstance(expr, Number):
        return {0: expr}
    if isinstance(expr, Symbol):
        if expr.name == var.name:
            return {1: Number(1)}
        return {0: expr}
    if isinstance(expr, Neg):
        return {k: (-v).simplify() for k, v in polynomial_coefficients(expr.expr, var).items()}
    if isinstance(expr, Add):
        return _poly_add(polynomial_coefficients(expr.left, var), polynomial_coefficients(expr.right, var))
    if isinstance(expr, Mul):
        return _poly_mul(polynomial_coefficients(expr.left, var), polynomial_coefficients(expr.right, var))
    if isinstance(expr, Pow):
        base = expr.base.simplify()
        expn = expr.exponent.simplify()
        if isinstance(base, Symbol) and base.name == var.name and isinstance(expn, Number) and float(expn.value).is_integer() and int(expn.value) >= 0:
            return {int(expn.value): Number(1)}
        if isinstance(expn, Number) and float(expn.value).is_integer() and int(expn.value) >= 0:
            coeff = {0: Number(1)}
            base_coeff = polynomial_coefficients(base, var)
            for _ in range(int(expn.value)):
                coeff = _poly_mul(coeff, base_coeff)
            return coeff
    raise ValueError(f"Expressão não polinomial em {var.name}: {expr}")


def degree(expr: Expr, var: Symbol) -> int:
    coeffs = polynomial_coefficients(expr, var)
    return max(coeffs.keys()) if coeffs else -math.inf  # type: ignore[return-value]


def polynomial_to_expr(coeffs: Dict[int, Expr], var: Symbol) -> Expr:
    out: Expr = Number(0)
    for deg, coeff in sorted(coeffs.items(), reverse=True):
        term: Expr
        if deg == 0:
            term = coeff
        elif deg == 1:
            term = coeff * var
        else:
            term = coeff * (var ** deg)
        out = out + term
    return out.simplify()


@dataclass
class QuadraticAnalysis:
    a: Expr
    b: Expr
    c: Expr
    discriminant: Expr
    roots: Tuple[Expr, Expr]
    factored: Expr

    def to_markdown(self) -> str:
        r1, r2 = self.roots
        return (
            "## Análise quadrática\n"
            f"- a = `{self.a}`\n"
            f"- b = `{self.b}`\n"
            f"- c = `{self.c}`\n"
            f"- discriminante Δ = `{self.discriminant}`\n"
            f"- raízes: `{r1}`, `{r2}`\n"
            f"- forma fatorada: `{self.factored}`\n"
        )


def analyze_quadratic(expr: Expr, var: Symbol) -> QuadraticAnalysis:
    coeffs = polynomial_coefficients(expr, var)
    a = coeffs.get(2, Number(0)).simplify()
    b = coeffs.get(1, Number(0)).simplify()
    c = coeffs.get(0, Number(0)).simplify()
    if isinstance(a, Number) and abs(float(a.value)) < 1e-12:
        raise ValueError("A expressão não é quadrática: coeficiente a é zero.")
    disc = expand(b*b - Number(4)*a*c).simplify()
    r1 = ((-b + sqrt(disc)) / (Number(2)*a)).simplify()
    r2 = ((-b - sqrt(disc)) / (Number(2)*a)).simplify()
    factored = (a * (var - r1) * (var - r2)).simplify()
    return QuadraticAnalysis(a, b, c, disc, (r1, r2), factored)


def factor(expr: Expr, var: Symbol | None = None) -> Expr:
    """Small factorization helper. Currently strongest for quadratics."""
    if var is None:
        syms = sorted(expr.symbols())
        if len(syms) != 1:
            return expr.simplify()
        var = Symbol(syms[0])
    try:
        if degree(expr, var) == 2:
            return analyze_quadratic(expr, var).factored.simplify()
    except Exception:
        return expr.simplify()
    return expr.simplify()
