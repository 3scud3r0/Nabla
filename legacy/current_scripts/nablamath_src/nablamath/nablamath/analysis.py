from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from .core import Expr, Symbol
from .optimize import auto_optimize, SelfImprovingOptimizer, OptimizationTrace


@dataclass
class ResearchReport:
    expression: Expr
    variables: Sequence[Symbol]
    gradient: List[Expr]
    hessian: List[List[Expr]]
    traces: List[OptimizationTrace]

    def to_markdown(self) -> str:
        lines = []
        lines.append("# NablaMath Research Report")
        lines.append("")
        lines.append(f"Expressão: `${self.expression}`")
        lines.append("")
        lines.append(f"LaTeX: `${self.expression.to_latex()}`")
        lines.append("")
        lines.append("## Gradiente")
        for v, g in zip(self.variables, self.gradient):
            lines.append(f"- d/d{v.name}: `${g}` | LaTeX: `${g.to_latex()}`")
        lines.append("")
        lines.append("## Hessiana")
        for row in self.hessian:
            lines.append("- " + " | ".join(f"`${cell}`" for cell in row))
        lines.append("")
        lines.append("## Otimização")
        for t in self.traces:
            lines.append(f"### {t.method}")
            lines.append(f"- melhor ponto: `{t.best_point}`")
            lines.append(f"- melhor valor: `{t.best_value}`")
            lines.append(f"- mensagem: {t.message}")
        return "\n".join(lines)


def research(
    expr: Expr,
    variables: Sequence[Symbol],
    start: Dict[str, float] | None = None,
    bounds: Dict[str, tuple[float, float]] | None = None,
    self_improve: bool = True,
) -> ResearchReport:
    grad = expr.grad(variables)
    hess = expr.hessian(variables)
    traces = auto_optimize(expr, variables, start=start, bounds=bounds)
    if self_improve and start is not None:
        traces.append(SelfImprovingOptimizer(expr, variables, start).run())
        traces = sorted(traces, key=lambda t: t.best_value)
    return ResearchReport(expr, variables, grad, hess, traces)
