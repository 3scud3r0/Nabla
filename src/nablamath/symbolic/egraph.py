"""Bounded equality saturation with declarative rules and verified certificates."""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
from typing import Callable, Iterable, Iterator, Literal, Mapping

from ..expression import Binary, Expr, Number, Symbol, render, to_data
from .assumptions import AssumptionSet
from .patterns import PNode, PVar, Pattern, RewriteRule, instantiate_expr
from .proof import RewriteEvent, constant_fold_event, verify_saturation_certificate
from .rules import RULESET_VERSION, default_egraph_rules

EGRAPH_SCHEMA_VERSION = 2

@dataclass(frozen=True, order=True)
class ENode:
    op: str
    children: tuple[int, ...] = ()
    value: Fraction | str | None = None


@dataclass(frozen=True)
class SaturationResult:
    original: Expr
    expression: Expr
    cost: float
    iterations: int
    saturated: bool
    class_count: int
    node_count: int
    proof: tuple[RewriteEvent, ...]
    stop_reason: Literal["saturated", "node_limit", "iteration_limit"]
    operation_costs: tuple[tuple[str, float], ...]

    assumptions: tuple[str, ...]
    rule_hashes: tuple[tuple[str, str], ...]
    certificate_verified: bool

    def to_data(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": EGRAPH_SCHEMA_VERSION,
            "ruleset_version": RULESET_VERSION,
            "original": to_data(self.original),
            "expression": to_data(self.expression),
            "cost": self.cost,
            "iterations": self.iterations,
            "saturated": self.saturated,
            "stop_reason": self.stop_reason,
            "class_count": self.class_count,
            "node_count": self.node_count,
            "operation_costs": dict(self.operation_costs),
            "assumptions": list(self.assumptions),
            "rule_hashes": dict(self.rule_hashes),
            "certificate_verified": self.certificate_verified,
            "proof": [event.to_data() for event in self.proof],
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return {**payload, "content_id": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}

    @property
    def content_id(self) -> str:
        """SHA-256 identity of the complete optimization audit record."""
        return str(self.to_data()["content_id"])


CostFunction = Callable[[str, Fraction | str | None], float]
def _default_cost(op: str, value: Fraction | str | None) -> float: return 1.0

class EGraphLimitError(RuntimeError):
    pass

class EGraph:
    """Union-find e-graph whose semantic rewrites come from a declarative rule set."""
    def __init__(self, *, node_limit: int | None = None, assumptions: AssumptionSet | None = None) -> None:
        if node_limit is not None and node_limit < 1:
            raise ValueError("O limite de nós deve ser positivo")
        self._node_limit = node_limit
        self.assumptions = assumptions or AssumptionSet()
        self._parent: list[int] = []
        self._classes: dict[int, set[ENode]] = {}
        self._memo: dict[ENode, int] = {}
        self.proof: list[RewriteEvent] = []

    def find(self, class_id: int) -> int:
        parent = self._parent[class_id]
        if parent != class_id:
            self._parent[class_id] = self.find(parent)
        return self._parent[class_id]

    def add(self, node: ENode) -> int:
        node = self._canonical(node)
        existing = self._memo.get(node)
        if existing is not None:
            return self.find(existing)
        if self._node_limit is not None and self.node_count >= self._node_limit:
            raise EGraphLimitError(f"Limite rígido de {self._node_limit} nós atingido")
        class_id = len(self._parent)
        self._parent.append(class_id)
        self._classes[class_id] = {node}
        self._memo[node] = class_id
        return class_id

    def add_expr(self, expr: Expr) -> int:
        if isinstance(expr, Number):
            return self.add(ENode("number", value=expr.value))
        if isinstance(expr, Symbol):
            return self.add(ENode("symbol", value=expr.name))
        return self.add(ENode(expr.op, (self.add_expr(expr.left), self.add_expr(expr.right))))

    def union(self, first: int, second: int, *, event: RewriteEvent | None = None) -> bool:
        first, second = self.find(first), self.find(second)
        if first == second: return False
        root, merged = min(first, second), max(first, second)
        self._parent[merged] = root
        self._classes[root].update(self._classes.pop(merged))
        if event is not None:
            self.proof.append(event)
        return True

    def rebuild(self) -> None:
        while True:
            self._memo.clear()
            collision: tuple[int, int] | None = None
            for class_id in sorted(self._classes):
                root = self.find(class_id)
                canonical = {self._canonical(node) for node in self._classes[class_id]}
                self._classes[class_id] = canonical
                for node in canonical:
                    other = self._memo.get(node)
                    if other is not None and self.find(other) != root:
                        collision = (root, other)
                        break
                    self._memo[node] = root
                if collision:
                    break
            if collision is None:
                return
            self.union(*collision)

    def _canonical(self, node: ENode) -> ENode:
        return ENode(node.op, tuple(self.find(child) for child in node.children), node.value)

    def nodes(self) -> list[tuple[int, ENode]]:
        return [(root, node) for root in sorted(self._classes) for node in sorted(self._classes[root])]

    @property
    def class_count(self) -> int:
        return len(self._classes)

    @property
    def node_count(self) -> int:
        return sum(len(nodes) for nodes in self._classes.values())

    def _constant(self, class_id: int) -> Fraction | None:
        for node in self._classes[self.find(class_id)]:
            if node.op == "number":
                assert isinstance(node.value, Fraction)
                return node.value
        return None

    def proves_nonzero(self, class_id: int, _seen: frozenset[int] = frozenset()) -> bool:
        root = self.find(class_id)
        if root in _seen: return False
        seen = _seen | {root}
        for node in self._classes[root]:
            if node.op == "number" and isinstance(node.value, Fraction) and node.value != 0:
                return True
            if node.op == "symbol" and isinstance(node.value, str) and node.value in self.assumptions.nonzero_symbols:
                return True
            if node.op in {"*", "/"} and len(node.children) == 2:
                if self.proves_nonzero(node.children[0], seen) and self.proves_nonzero(node.children[1], seen):
                    return True
            if node.op == "**" and node.children and self.proves_nonzero(node.children[0], seen):
                return True
        return False

    def _match_pattern(self, pattern: Pattern, class_id: int,
                       bindings: Mapping[str, int] | None = None) -> Iterator[dict[str, int]]:
        root = self.find(class_id)
        current = dict(bindings or {})
        if isinstance(pattern, PVar):
            previous = current.get(pattern.name)
            if previous is not None:
                if self.find(previous) == root: yield current
                return
            current[pattern.name] = root
            yield current
            return
        for node in tuple(sorted(self._classes[root])):
            if pattern.op in {"number", "symbol"}:
                if node.op == pattern.op and node.value == pattern.value:
                    yield current
                continue
            if node.op != pattern.op or len(node.children) != len(pattern.children):
                continue
            candidates = [current]
            for child_pattern, child_class in zip(pattern.children, node.children):
                next_candidates: list[dict[str, int]] = []
                for candidate in candidates:
                    next_candidates.extend(self._match_pattern(child_pattern, child_class, candidate))
                candidates = next_candidates
                if not candidates: break
            yield from candidates

    def _instantiate_pattern(self, pattern: Pattern, bindings: Mapping[str, int]) -> int:
        if isinstance(pattern, PVar): return self.find(bindings[pattern.name])
        if pattern.op in {"number", "symbol"}: return self.add(ENode(pattern.op, value=pattern.value))
        return self.add(ENode(pattern.op, tuple(self._instantiate_pattern(child, bindings) for child in pattern.children)))

    def _conditions_hold(self, rule: RewriteRule, bindings: Mapping[str, int]) -> bool:
        for condition in rule.conditions:
            if condition.kind == "nonzero" and not self.proves_nonzero(bindings[condition.variable]):
                return False
            if condition.kind == "defined" and not self.assumptions.proves_defined(self.extract(bindings[condition.variable])[0]):
                return False
        return True

    def _binding_expressions(self, bindings: Mapping[str, int]) -> dict[str, Expr]:
        return {name: self.extract(class_id)[0] for name, class_id in sorted(bindings.items())}

    def _apply_constant_folding(self, snapshot: list[tuple[int, ENode]]) -> bool:
        changed = False
        for owner, node in snapshot:
            if len(node.children) != 2: continue
            lval, rval = self._constant(node.children[0]), self._constant(node.children[1])
            if lval is None or rval is None: continue
            folded = _fold(node.op, lval, rval)
            if folded is None: continue
            before = Binary(node.op, Number(lval), Number(rval))
            after = Number(folded)
            target = self.add(ENode("number", value=folded))
            event = constant_fold_event(before, after, self.find(owner), self.find(target))
            changed |= self.union(owner, target, event=event)
        return changed

    def apply_rules(self, rules: Iterable[RewriteRule]) -> tuple[bool, bool]:
        """Run one bounded pass of constant folding plus declarative e-matching."""
        changed = False
        snapshot = self.nodes()
        try:
            changed |= self._apply_constant_folding(snapshot)
            if changed: self.rebuild()
            roots = tuple(sorted(self._classes))
            for rule in rules:
                for owner in roots:
                    if owner not in self._classes: continue
                    matches = list(self._match_pattern(rule.lhs, owner))
                    for bindings in matches:
                        if not self._conditions_hold(rule, bindings): continue
                        expr_bindings = self._binding_expressions(bindings)
                        before = instantiate_expr(rule.lhs, expr_bindings)
                        after = instantiate_expr(rule.rhs, expr_bindings)
                        target = self._instantiate_pattern(rule.rhs, bindings)
                        source_root, target_root = self.find(owner), self.find(target)
                        assumptions = tuple(
                            (f"{render(expr_bindings[c.variable])} != 0" if c.kind == "nonzero"
                             else f"defined({render(expr_bindings[c.variable])})")
                            for c in rule.conditions
                        )
                        event = RewriteEvent(
                            rule=rule.name,
                            source_class=source_root,
                            target_class=target_root,
                            before=before,
                            after=after,
                            substitution=tuple(sorted(expr_bindings.items())),
                            assumptions=assumptions,
                            justification=rule.justification,
                            rule_hash=rule.rule_hash,
                        )
                        if self.union(source_root, target_root, event=event):
                            changed = True
                            self.rebuild()
        except EGraphLimitError:
            if changed: self.rebuild()
            return changed, True
        return changed, False

    def extract(self, root: int, cost: CostFunction = _default_cost) -> tuple[Expr, float]:
        best: dict[int, tuple[float, Expr]] = {}
        # Bellman-Ford-style relaxation supports cyclic e-graphs safely.
        for _ in range(max(1, len(self._classes))):
            updated = False
            for owner, node in self.nodes():
                own_cost = float(cost(node.op, node.value))
                if not math.isfinite(own_cost) or own_cost < 0:
                    raise ValueError("Custos de extração devem ser finitos e não negativos")
                if node.op == "number":
                    if not isinstance(node.value, Fraction):
                        raise TypeError("Nó numérico inválido no e-graph")
                    candidate = (own_cost, Number(node.value))
                elif node.op == "symbol":
                    if not isinstance(node.value, str):
                        raise TypeError("Nó simbólico inválido no e-graph")
                    candidate = (own_cost, Symbol(node.value))
                elif all(self.find(child) in best for child in node.children):
                    a, b = (best[self.find(child)] for child in node.children)
                    candidate = (own_cost + a[0] + b[0], Binary(node.op, a[1], b[1]))
                else:
                    continue
                owner = self.find(owner)
                if owner not in best or candidate[0] < best[owner][0]:
                    best[owner], updated = candidate, True
            if not updated:
                break
        return best[self.find(root)][1], best[self.find(root)][0]


def _fold(op: str, left: Fraction, right: Fraction) -> Fraction | None:
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        return None if right == 0 else left / right
    if op == "**" and right.denominator == 1 and not (left == 0 and right <= 0):
        return left ** right.numerator
    return None


def saturate(expr: Expr, *, iteration_limit: int = 12, node_limit: int = 10_000,
             operation_costs: Mapping[str, float] | None = None,
             rules: Iterable[RewriteRule] | None = None,
             assumptions: AssumptionSet | None = None,
             active_domains: Iterable[str] = ("rational",),
             verify_certificate: bool = True) -> SaturationResult:
    if iteration_limit < 1 or node_limit < 1:
        raise ValueError("Os limites de iteração e nós devem ser positivos")
    weights = dict(operation_costs or {})
    for name, weight in weights.items():
        try:
            numeric_weight = float(weight)
        except (TypeError, ValueError) as exc:
            raise ValueError("Custos de operação devem ser números reais") from exc
        if not isinstance(name, str) or not math.isfinite(numeric_weight) or numeric_weight < 0:
            raise ValueError("Custos de operação devem ser finitos, não negativos e ter nomes textuais")
        weights[name] = numeric_weight
    domains = frozenset(active_domains)
    if not domains: raise ValueError("É necessário ativar ao menos um domínio de regras")
    selected = tuple(rule for rule in (tuple(rules) if rules is not None else default_egraph_rules()) if domains.intersection(rule.domains))
    names = [rule.name for rule in selected]
    if len(names) != len(set(names)): raise ValueError("Nomes de regras devem ser únicos")
    assumptions = assumptions or AssumptionSet()
    graph = EGraph(node_limit=node_limit, assumptions=assumptions)
    try: root = graph.add_expr(expr)
    except EGraphLimitError as exc: raise ValueError("O limite de nós é menor que a expressão de entrada") from exc
    saturated = False
    stop_reason: Literal["saturated", "node_limit", "iteration_limit"] = "iteration_limit"
    iterations = 0
    for iterations in range(1, iteration_limit + 1):
        changed, budget_exhausted = graph.apply_rules(selected)
        if budget_exhausted: stop_reason = "node_limit"; break
        if not changed: saturated = True; stop_reason = "saturated"; break
    result, result_cost = graph.extract(root, lambda op, value: weights.get(op, 1.0))
    verification = verify_saturation_certificate(expr, result, graph.proof, selected, assumptions)
    if verify_certificate and not verification.valid:
        raise RuntimeError("Falha interna na verificação independente do certificado: " + "; ".join(verification.errors))
    return SaturationResult(
        expr, result, result_cost, iterations, saturated, graph.class_count, graph.node_count,
        tuple(graph.proof), stop_reason, tuple(sorted(weights.items())), assumptions.statements(),
        tuple(sorted((rule.name, rule.rule_hash) for rule in selected)), verification.valid,
    )

__all__ = ["ENode", "EGraph", "EGraphLimitError", "RewriteEvent", "SaturationResult", "saturate"]
