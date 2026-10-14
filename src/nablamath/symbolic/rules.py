"""Declarative rewrite rules and stable rule identifiers for auditing."""
from __future__ import annotations

from ..expression import Expr
from .patterns import RewriteRule, RuleCondition, parse_pattern

# Legacy research-pipeline identifiers retained for compatibility.
EQUAL_TERMS = "soma_de_termos_iguais"
CONDITIONAL_CANCEL = "cancelamento_condicional"


def _rule(name: str, lhs: str, rhs: str, *, nonzero: str | None = None,
          justification: str, lean_theorem: str, defined: str | None = None) -> RewriteRule:
    conditions = () if nonzero is None else (RuleCondition("nonzero", nonzero),)
    if defined is not None:
        conditions += (RuleCondition("defined", defined),)
    return RewriteRule(
        name=name,
        lhs=parse_pattern(lhs),
        rhs=parse_pattern(rhs),
        conditions=conditions,
        domains=("rational",),
        justification=justification,
        lean_theorem=lean_theorem,
    )


DEFAULT_EGRAPH_RULES: tuple[RewriteRule, ...] = (
    _rule("add_zero", "?a + 0", "?a", justification="Aditividade do elemento neutro.", lean_theorem="NablaMath.add_zero"),
    _rule("zero_add", "0 + ?a", "?a", justification="Aditividade do elemento neutro.", lean_theorem="NablaMath.zero_add"),
    _rule("multiply_one", "?a * 1", "?a", justification="Multiplicatividade do elemento neutro.", lean_theorem="NablaMath.mul_one"),
    _rule("one_multiply", "1 * ?a", "?a", justification="Multiplicatividade do elemento neutro.", lean_theorem="NablaMath.one_mul"),
    _rule("divide_one", "?a / 1", "?a", justification="Divisão pelo elemento multiplicativo neutro.", lean_theorem="NablaMath.div_one"),
    _rule("power_one", "?a ** 1", "?a", justification="Potência de expoente unitário.", lean_theorem="NablaMath.pow_one"),
    _rule("subtract_self", "?a - ?a", "0", defined="a", justification="Subtração reflexiva no corpo racional.", lean_theorem="NablaMath.subtract_self"),
    _rule("divide_self", "?a / ?a", "1", nonzero="a", justification="Cancelamento exige denominador não nulo.", lean_theorem="NablaMath.div_self"),
    _rule("commute_+", "?a + ?b", "?b + ?a", justification="Comutatividade da adição racional.", lean_theorem="NablaMath.add_comm_rule"),
    _rule("commute_*", "?a * ?b", "?b * ?a", justification="Comutatividade da multiplicação racional.", lean_theorem="NablaMath.mul_comm_rule"),
    _rule("associate_+", "(?a + ?b) + ?c", "?a + (?b + ?c)", justification="Associatividade da adição racional.", lean_theorem="NablaMath.add_assoc_rule"),
    _rule("associate_*", "(?a * ?b) * ?c", "?a * (?b * ?c)", justification="Associatividade da multiplicação racional.", lean_theorem="NablaMath.mul_assoc_rule"),
    _rule("factor_common_left", "?a * ?b + ?a * ?c", "?a * (?b + ?c)", justification="Distributividade, usada no sentido de fatoração.", lean_theorem="NablaMath.factor_common_left"),
)

RULESET_VERSION = "domain-safe-rational-v3"


def default_egraph_rules() -> tuple[RewriteRule, ...]:
    return DEFAULT_EGRAPH_RULES


def rewrite_once(expr: Expr):
    # Imported lazily to avoid a research<->symbolic import cycle at module load.
    from ..research import _rewrite
    return _rewrite(expr)

__all__ = [
    "EQUAL_TERMS", "CONDITIONAL_CANCEL", "RULESET_VERSION",
    "DEFAULT_EGRAPH_RULES", "default_egraph_rules", "rewrite_once",
]
