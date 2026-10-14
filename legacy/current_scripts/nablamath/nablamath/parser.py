from __future__ import annotations

"""Safe parser for small mathematical expressions.

It converts strings like "sin(x)^2 + cos(x)^2" into NablaMath Expr objects.
Only a controlled AST subset is accepted.
"""

import ast
from typing import Dict, Any

from .core import Symbol, Number, Expr, sin, cos, exp, log, sqrt

_ALLOWED_FUNCS = {"sin": sin, "cos": cos, "exp": exp, "log": log, "sqrt": sqrt}


def parse_expr(text: str, symbols: Dict[str, Symbol] | None = None) -> Expr:
    symbols = dict(symbols or {})
    text = text.replace("^", "**")
    tree = ast.parse(text, mode="eval")
    return _convert(tree.body, symbols)


def _convert(node: ast.AST, symbols: Dict[str, Symbol]) -> Expr:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return Number(node.value)
    if isinstance(node, ast.Name):
        if node.id in symbols:
            return symbols[node.id]
        sym = Symbol(node.id)
        symbols[node.id] = sym
        return sym
    if isinstance(node, ast.BinOp):
        left = _convert(node.left, symbols)
        right = _convert(node.right, symbols)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left ** right
    if isinstance(node, ast.UnaryOp):
        val = _convert(node.operand, symbols)
        if isinstance(node.op, ast.USub):
            return -val
        if isinstance(node.op, ast.UAdd):
            return val
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id not in _ALLOWED_FUNCS:
            raise ValueError(f"Função não permitida: {node.func.id}")
        if len(node.args) != 1:
            raise ValueError("Funções matemáticas aceitam exatamente um argumento neste parser.")
        return _ALLOWED_FUNCS[node.func.id](_convert(node.args[0], symbols))
    raise ValueError(f"Expressão não suportada pelo parser seguro: {ast.dump(node)}")
