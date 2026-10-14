from __future__ import annotations

"""Generic self-improvement loops for algorithms, models, and formulas."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Sequence, Tuple
import math
import random


@dataclass
class RecursiveCandidate:
    state: Any
    metrics: Dict[str, float]
    mutation: str = "initial"
    parent: int | None = None
    generation: int = 0

    def score(self, key: str, maximize: bool = True) -> float:
        value = self.metrics.get(key, -math.inf if maximize else math.inf)
        return value if maximize else -value


class ExperimentMemory:
    def __init__(self):
        self.items: List[RecursiveCandidate] = []

    def add(self, candidate: RecursiveCandidate) -> None:
        self.items.append(candidate)

    def best(self, key: str, maximize: bool = True) -> RecursiveCandidate | None:
        if not self.items:
            return None
        return max(self.items, key=lambda c: c.score(key, maximize=maximize))

    def mutation_statistics(self, key: str, maximize: bool = True) -> Dict[str, float]:
        groups: Dict[str, List[float]] = {}
        for c in self.items:
            groups.setdefault(c.mutation, []).append(c.metrics.get(key, math.nan))
        out = {}
        for name, vals in groups.items():
            clean = [v for v in vals if math.isfinite(v)]
            if clean:
                out[name] = sum(clean) / len(clean)
        return out


@dataclass
class SelfImprovingLoop:
    initial_state: Any
    proposer: Callable[[Any, ExperimentMemory], Sequence[Tuple[str, Any]]]
    evaluator: Callable[[Any], Dict[str, float]]
    score_key: str
    maximize: bool = True
    population_size: int = 8
    iterations: int = 30
    patience: int = 8
    memory: ExperimentMemory = field(default_factory=ExperimentMemory)

    def run(self) -> RecursiveCandidate:
        first = RecursiveCandidate(self.initial_state, self.evaluator(self.initial_state))
        self.memory.add(first)
        population = [first]
        best = first
        stall = 0

        for generation in range(1, self.iterations + 1):
            children: List[RecursiveCandidate] = []
            for parent_idx, cand in enumerate(population):
                for mutation, state in self.proposer(cand.state, self.memory):
                    child = RecursiveCandidate(state, self.evaluator(state), mutation, parent_idx, generation)
                    self.memory.add(child)
                    children.append(child)
            population = sorted(population + children, key=lambda c: c.score(self.score_key, self.maximize), reverse=True)[: self.population_size]
            current = population[0]
            if current.score(self.score_key, self.maximize) > best.score(self.score_key, self.maximize):
                best = current
                stall = 0
            else:
                stall += 1
            if stall >= self.patience:
                break
        return best


def pareto_front(candidates: Sequence[RecursiveCandidate], maximize: Sequence[str] = (), minimize: Sequence[str] = ()) -> List[RecursiveCandidate]:
    """Return non-dominated candidates for multiobjective selection."""
    def dominates(a: RecursiveCandidate, b: RecursiveCandidate) -> bool:
        better_or_equal = True
        strictly_better = False
        for key in maximize:
            av, bv = a.metrics.get(key, -math.inf), b.metrics.get(key, -math.inf)
            better_or_equal &= av >= bv
            strictly_better |= av > bv
        for key in minimize:
            av, bv = a.metrics.get(key, math.inf), b.metrics.get(key, math.inf)
            better_or_equal &= av <= bv
            strictly_better |= av < bv
        return better_or_equal and strictly_better
    return [c for c in candidates if not any(dominates(o, c) for o in candidates if o is not c)]
