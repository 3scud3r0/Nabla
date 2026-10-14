"""Equation blocks retain the expression AST, rather than raw executable markup."""
from .document_model import Equation
from ..expression import parse_expr, render


def equation_data(equation: Equation) -> dict:
    return {'left': render(equation.left), 'right': render(equation.right)}


def equation_from_data(data: dict) -> Equation:
    if set(data) != {'left', 'right'}:
        raise ValueError('Contrato de equação inválido')
    return Equation(parse_expr(data['left']), parse_expr(data['right']))
