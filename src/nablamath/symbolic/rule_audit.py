"""Finite exact-rational falsification of declarative rewrite rules.

This independently evaluates both instantiated ASTs instead of trusting a rule
name, hash, or stated theorem. Passing a finite grid is never a proof; the report
always records that limitation. Undefinedness is checked before equality.
"""
from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from math import prod

from ..expression import Number, evaluate
from .patterns import RewriteRule, instantiate_expr, pattern_variables


@dataclass(frozen=True)
class RuleAudit:
    rule_hash: str
    tested: int
    excluded: int
    counterexample: tuple[tuple[str, str], ...] | None
    failure: str | None

    @property
    def passed(self):
        return self.tested > 0 and self.failure is None

    def to_data(self):
        return {"schema_version": 1, "rule_hash": self.rule_hash,
                "tested": self.tested, "excluded": self.excluded,
                "counterexample": None if self.counterexample is None else dict(self.counterexample),
                "failure": self.failure, "passed": self.passed,
                "formal_proof": False,
                "scope": "finite exact-rational scalar substitutions only; not composite AST domain proof"}


def audit_rule(rule: RewriteRule, values=(-2, -1, 0, 1, 2), *, max_cases=10000):
    """Find a value or definedness counterexample over a bounded scalar grid.

    Conditions are applied to scalar metavariables. A separate rewrite
    certificate/domain checker is required for composite AST substitutions.
    """
    if type(max_cases) is not int or not 1 <= max_cases <= 100000:
        raise ValueError("audit case budget must be in [1,100000]")
    if not isinstance(values, (tuple, list)) or not 1 <= len(values) <= 64:
        raise ValueError("audit requires 1..64 exact grid values")
    grid = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
            raise ValueError("grid values must be exact rationals")
        value = Fraction(value)
        if max(abs(value.numerator).bit_length(), value.denominator.bit_length()) > 128:
            raise ValueError("grid values exceed bit budget")
        if value not in grid:
            grid.append(value)
    variables = tuple(sorted(pattern_variables(rule.lhs)))
    if prod([len(grid)] * len(variables)) > max_cases:
        raise ValueError("rule grid exceeds audit budget")
    tested = excluded = 0
    for case in product(grid, repeat=len(variables)):
        binding = dict(zip(variables, case))
        if any(condition.kind == "nonzero" and binding[condition.variable] == 0
               for condition in rule.conditions):
            excluded += 1
            continue
        instantiated = {name: Number(value) for name, value in binding.items()}
        results = []
        for pattern in (rule.lhs, rule.rhs):
            try:
                result = evaluate(instantiate_expr(pattern, instantiated), {})
            except (ZeroDivisionError, ValueError):
                result = None
            results.append(result)
        tested += 1
        failure = None
        if (results[0] is None) != (results[1] is None):
            failure = "definedness mismatch"
        elif results[0] != results[1]:
            failure = "value mismatch"
        if failure:
            return RuleAudit(rule.rule_hash, tested, excluded,
                             tuple((name, str(binding[name])) for name in variables), failure)
    return RuleAudit(rule.rule_hash, tested, excluded, None, None)


__all__ = ["RuleAudit", "audit_rule"]
