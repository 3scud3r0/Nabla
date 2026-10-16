"""Deterministic Lean proof search over a closed, auditable tactic portfolio.

This is the repair-loop foundation: NablaMath generates a typed theorem from its
own AST, tries only named strategies from an allow-list, records every rejection,
and returns the first source accepted by the Lean kernel. It never evaluates
user-supplied tactic text.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Iterable

from ..expression import Binary, Expr, Symbol
from ..symbolic.patterns import RewriteRule, instantiate_expr, pattern_variables
from .check import _verify_source
from .translate import universal_lean_source


TACTIC_PORTFOLIO: tuple[tuple[str, str], ...] = (
    ("ring", "  ring\n"),
    ("ring_nf", "  ring_nf\n"),
    ("field_ring", "  field_simp <;> ring\n"),
    ("norm_num", "  norm_num\n"),
    ("linarith", "  linarith\n"),
    ("nlinarith", "  nlinarith\n"),
)


@dataclass(frozen=True)
class ProofAttempt:
    strategy: str
    verified: bool
    detail: str
    source_hash: str


@dataclass(frozen=True)
class ProofSearchResult:
    verified: bool
    theorem_name: str
    source: str | None
    strategy: str | None
    attempts: tuple[ProofAttempt, ...]

    @property
    def content_id(self) -> str:
        payload = "|".join(f"{a.strategy}:{a.source_hash}:{int(a.verified)}" for a in self.attempts)
        return hashlib.sha256((self.theorem_name + "|" + payload).encode("utf-8")).hexdigest()


def _contains_division(expr: Expr) -> bool:
    if isinstance(expr, Binary):
        return expr.op == "/" or _contains_division(expr.left) or _contains_division(expr.right)
    return False


def candidate_strategies(lhs: Expr, rhs: Expr, nonzero: Iterable[Expr] = ()) -> tuple[str, ...]:
    """Return a deterministic tactic ordering based only on typed AST features."""
    has_denominator = _contains_division(lhs) or _contains_division(rhs)
    has_hypotheses = bool(tuple(nonzero))
    preferred = ["field_ring", "ring", "ring_nf"] if (has_denominator or has_hypotheses) else ["ring", "ring_nf"]
    preferred += ["norm_num", "linarith", "nlinarith"]
    return tuple(dict.fromkeys(preferred))


def _source_for_strategy(lhs: Expr, rhs: Expr, *, nonzero: tuple[Expr, ...],
                         theorem_name: str, strategy: str) -> str:
    bodies = dict(TACTIC_PORTFOLIO)
    if strategy not in bodies:
        raise ValueError(f"Estratégia fora da carteira permitida: {strategy}")
    base = universal_lean_source(lhs, rhs, nonzero=nonzero, theorem_name=theorem_name)
    marker = ":= by\n"
    prefix, separator, _ = base.partition(marker)
    if not separator:
        raise RuntimeError("Gerador Lean não produziu corpo de prova reconhecível")
    body = bodies[strategy]
    if strategy == "field_ring" and nonzero:
        hypotheses = ", ".join(f"h{i}" for i in range(len(nonzero)))
        body = f"  field_simp [{hypotheses}] <;> ring\n"
    return prefix + marker + body + f"\n#print axioms {theorem_name}\n"


def search_universal_proof(lhs: Expr, rhs: Expr, project: Path, *,
                           nonzero: Iterable[Expr] = (), theorem_name: str = "nablamath_search",
                           timeout_s: int = 60) -> ProofSearchResult:
    nonzero = tuple(nonzero)
    attempts: list[ProofAttempt] = []
    for strategy in candidate_strategies(lhs, rhs, nonzero):
        source = _source_for_strategy(lhs, rhs, nonzero=nonzero, theorem_name=theorem_name, strategy=strategy)
        source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        check = _verify_source(source, source_hash, project, timeout_s, f"Lean aceitou {strategy}")
        attempts.append(ProofAttempt(strategy, check.verified, check.detail, source_hash))
        if check.verified:
            return ProofSearchResult(True, theorem_name, source, strategy, tuple(attempts))
    return ProofSearchResult(False, theorem_name, None, None, tuple(attempts))


def search_rule_proof(rule: RewriteRule, project: Path, *, timeout_s: int = 60) -> ProofSearchResult:
    bindings = {name: Symbol(name) for name in pattern_variables(rule.lhs)}
    lhs = instantiate_expr(rule.lhs, bindings)
    rhs = instantiate_expr(rule.rhs, bindings)
    nonzero = tuple(bindings[c.variable] for c in rule.conditions if c.kind == "nonzero")
    safe_name = "nablamath_search_" + "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in rule.name)
    return search_universal_proof(lhs, rhs, project, nonzero=nonzero, theorem_name=safe_name, timeout_s=timeout_s)


def verify_ruleset_with_lean(
    rules: Iterable[RewriteRule], project: Path, *, timeout_s: int = 60
) -> tuple[tuple[str, ProofSearchResult], ...]:
    return tuple((rule.name, search_rule_proof(rule, project, timeout_s=timeout_s)) for rule in rules)


__all__ = [
    "TACTIC_PORTFOLIO", "ProofAttempt", "ProofSearchResult", "candidate_strategies",
    "search_universal_proof", "search_rule_proof", "verify_ruleset_with_lean",
]