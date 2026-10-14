from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Sequence, Tuple
import copy
import math
import random

import numpy as np

from .core import Expr, Symbol


@dataclass
class OptimizationTrace:
    method: str
    variables: List[str]
    path: List[Dict[str, float]]
    values: List[float]
    converged: bool
    message: str

    @property
    def best_point(self) -> Dict[str, float]:
        if not self.values:
            return {}
        idx = min(range(len(self.values)), key=lambda i: self.values[i])
        return self.path[idx]

    @property
    def best_value(self) -> float:
        return min(self.values) if self.values else math.inf

    def summary(self) -> str:
        return (
            f"Método: {self.method}\n"
            f"Convergiu: {self.converged}\n"
            f"Mensagem: {self.message}\n"
            f"Melhor ponto: {self.best_point}\n"
            f"Melhor valor: {self.best_value}\n"
            f"Iterações registradas: {len(self.values)}"
        )


def gradient_descent(
    expr: Expr,
    variables: Sequence[Symbol],
    start: Dict[str, float],
    lr: float = 0.01,
    steps: int = 1000,
    tolerance: float = 1e-8,
    clip_grad: float | None = 100.0,
) -> OptimizationTrace:
    grads = expr.grad(variables)
    point = {v.name: float(start[v.name]) for v in variables}
    path: List[Dict[str, float]] = []
    values: List[float] = []
    converged = False
    message = "número máximo de passos atingido"

    for step in range(steps):
        val = expr.eval(point)
        grad_vals = np.array([g.eval(point) for g in grads], dtype=float)
        grad_norm = float(np.linalg.norm(grad_vals))
        path.append(dict(point))
        values.append(float(val))
        if not math.isfinite(val) or not np.all(np.isfinite(grad_vals)):
            message = "valor ou gradiente não finito"
            break
        if grad_norm < tolerance:
            converged = True
            message = "norma do gradiente abaixo da tolerância"
            break
        if clip_grad is not None and grad_norm > clip_grad:
            grad_vals = grad_vals * (clip_grad / (grad_norm + 1e-12))
        for i, v in enumerate(variables):
            point[v.name] -= lr * float(grad_vals[i])
    return OptimizationTrace("gradient_descent", [v.name for v in variables], path, values, converged, message)


def newton_optimize(
    expr: Expr,
    variables: Sequence[Symbol],
    start: Dict[str, float],
    steps: int = 100,
    damping: float = 1e-4,
    tolerance: float = 1e-8,
) -> OptimizationTrace:
    grads = expr.grad(variables)
    hess = expr.hessian(variables)
    point = {v.name: float(start[v.name]) for v in variables}
    path: List[Dict[str, float]] = []
    values: List[float] = []
    converged = False
    message = "número máximo de passos atingido"

    for step in range(steps):
        val = expr.eval(point)
        g = np.array([gi.eval(point) for gi in grads], dtype=float)
        H = np.array([[hij.eval(point) for hij in row] for row in hess], dtype=float)
        path.append(dict(point))
        values.append(float(val))
        if float(np.linalg.norm(g)) < tolerance:
            converged = True
            message = "norma do gradiente abaixo da tolerância"
            break
        try:
            delta = np.linalg.solve(H + damping * np.eye(len(variables)), g)
        except np.linalg.LinAlgError:
            message = "Hessiana singular ou mal condicionada"
            break
        if not np.all(np.isfinite(delta)):
            message = "passo de Newton não finito"
            break
        for i, v in enumerate(variables):
            point[v.name] -= float(delta[i])
    return OptimizationTrace("newton", [v.name for v in variables], path, values, converged, message)


def random_search(
    expr: Expr,
    variables: Sequence[Symbol],
    bounds: Dict[str, Tuple[float, float]],
    samples: int = 1000,
    seed: int | None = 42,
) -> OptimizationTrace:
    rng = random.Random(seed)
    path: List[Dict[str, float]] = []
    values: List[float] = []
    for _ in range(samples):
        p = {v.name: rng.uniform(*bounds[v.name]) for v in variables}
        try:
            val = expr.eval(p)
        except Exception:
            val = math.inf
        path.append(p)
        values.append(float(val))
    return OptimizationTrace("random_search", [v.name for v in variables], path, values, True, "busca aleatória finalizada")


def auto_optimize(
    expr: Expr,
    variables: Sequence[Symbol],
    start: Dict[str, float] | None = None,
    bounds: Dict[str, Tuple[float, float]] | None = None,
) -> List[OptimizationTrace]:
    traces: List[OptimizationTrace] = []
    if bounds is not None:
        traces.append(random_search(expr, variables, bounds=bounds, samples=800))
        if start is None:
            start = traces[-1].best_point
    if start is not None:
        for lr in [0.1, 0.03, 0.01, 0.003]:
            traces.append(gradient_descent(expr, variables, start=start, lr=lr, steps=1000))
        traces.append(newton_optimize(expr, variables, start=start))
    return sorted(traces, key=lambda t: t.best_value)


@dataclass
class Candidate:
    state: Dict[str, float]
    value: float = math.inf
    mutation: str = "initial"
    parent_index: int | None = None


@dataclass
class SelfImprovingOptimizer:
    expr: Expr
    variables: Sequence[Symbol]
    initial_state: Dict[str, float]
    step_sizes: List[float] = field(default_factory=lambda: [1.0, 0.3, 0.1, 0.03])
    population_size: int = 8
    iterations: int = 60
    patience: int = 12

    def _evaluate(self, state: Dict[str, float]) -> float:
        try:
            val = self.expr.eval(state)
            return float(val) if math.isfinite(val) else math.inf
        except Exception:
            return math.inf

    def _propose(self, state: Dict[str, float]) -> List[Tuple[str, Dict[str, float]]]:
        proposals: List[Tuple[str, Dict[str, float]]] = []
        names = [v.name for v in self.variables]
        for s in self.step_sizes:
            for name in names:
                for sign in [-1.0, 1.0]:
                    ns = dict(state)
                    ns[name] += sign * s
                    proposals.append((f"{name}{'+' if sign > 0 else '-'}{s}", ns))
        # diagonal mutation
        for s in self.step_sizes:
            ns = dict(state)
            for name in names:
                ns[name] += random.choice([-1.0, 1.0]) * s
            proposals.append((f"random_diagonal_{s}", ns))
        return proposals

    def run(self) -> OptimizationTrace:
        initial = Candidate(dict(self.initial_state), self._evaluate(self.initial_state))
        population = [initial]
        history = [initial]
        best = initial
        no_improvement = 0

        for _ in range(self.iterations):
            children: List[Candidate] = []
            for idx, cand in enumerate(population):
                for mutation, state in self._propose(cand.state):
                    children.append(Candidate(state, self._evaluate(state), mutation, idx))
            population = sorted(population + children, key=lambda c: c.value)[: self.population_size]
            history.extend(children)
            current = population[0]
            if current.value < best.value:
                best = current
                no_improvement = 0
                # make search more precise around improvements
                self.step_sizes = sorted(set([s * 0.7 for s in self.step_sizes] + self.step_sizes), reverse=True)[:8]
            else:
                no_improvement += 1
            if no_improvement >= self.patience:
                break
        path = [c.state for c in history if math.isfinite(c.value)]
        values = [c.value for c in history if math.isfinite(c.value)]
        return OptimizationTrace(
            "self_improving_recursive_search",
            [v.name for v in self.variables],
            path,
            values,
            True,
            f"melhor mutação: {best.mutation}",
        )


def adam_optimize(
    expr: Expr,
    variables: Sequence[Symbol],
    start: Dict[str, float],
    lr: float = 0.03,
    steps: int = 1000,
    beta1: float = 0.9,
    beta2: float = 0.999,
    eps: float = 1e-8,
    tolerance: float = 1e-8,
) -> OptimizationTrace:
    """Adam optimizer for symbolic expressions through symbolic gradients."""
    grads = expr.grad(variables)
    point = {v.name: float(start[v.name]) for v in variables}
    m = np.zeros(len(variables), dtype=float)
    v2 = np.zeros(len(variables), dtype=float)
    path: List[Dict[str, float]] = []
    values: List[float] = []
    converged = False
    message = "número máximo de passos atingido"
    for t in range(1, steps + 1):
        val = expr.eval(point)
        g = np.array([gi.eval(point) for gi in grads], dtype=float)
        path.append(dict(point))
        values.append(float(val))
        if not math.isfinite(val) or not np.all(np.isfinite(g)):
            message = "valor ou gradiente não finito"
            break
        if float(np.linalg.norm(g)) < tolerance:
            converged = True
            message = "norma do gradiente abaixo da tolerância"
            break
        m = beta1 * m + (1 - beta1) * g
        v2 = beta2 * v2 + (1 - beta2) * (g * g)
        m_hat = m / (1 - beta1 ** t)
        v_hat = v2 / (1 - beta2 ** t)
        step = lr * m_hat / (np.sqrt(v_hat) + eps)
        for i, sym in enumerate(variables):
            point[sym.name] -= float(step[i])
    return OptimizationTrace("adam", [v.name for v in variables], path, values, converged, message)


def rmsprop_optimize(
    expr: Expr,
    variables: Sequence[Symbol],
    start: Dict[str, float],
    lr: float = 0.01,
    steps: int = 1000,
    beta: float = 0.9,
    eps: float = 1e-8,
    tolerance: float = 1e-8,
) -> OptimizationTrace:
    grads = expr.grad(variables)
    point = {v.name: float(start[v.name]) for v in variables}
    avg_sq = np.zeros(len(variables), dtype=float)
    path: List[Dict[str, float]] = []
    values: List[float] = []
    converged = False
    message = "número máximo de passos atingido"
    for _ in range(steps):
        val = expr.eval(point)
        g = np.array([gi.eval(point) for gi in grads], dtype=float)
        path.append(dict(point))
        values.append(float(val))
        if not math.isfinite(val) or not np.all(np.isfinite(g)):
            message = "valor ou gradiente não finito"
            break
        if float(np.linalg.norm(g)) < tolerance:
            converged = True
            message = "norma do gradiente abaixo da tolerância"
            break
        avg_sq = beta * avg_sq + (1 - beta) * (g * g)
        update = lr * g / (np.sqrt(avg_sq) + eps)
        for i, sym in enumerate(variables):
            point[sym.name] -= float(update[i])
    return OptimizationTrace("rmsprop", [v.name for v in variables], path, values, converged, message)


def simulated_annealing(
    expr: Expr,
    variables: Sequence[Symbol],
    bounds: Dict[str, Tuple[float, float]],
    steps: int = 2000,
    initial_temp: float = 1.0,
    final_temp: float = 1e-3,
    seed: int | None = 42,
) -> OptimizationTrace:
    rng = random.Random(seed)
    point = {v.name: rng.uniform(*bounds[v.name]) for v in variables}
    value = expr.eval(point)
    best_point, best_value = dict(point), float(value)
    path: List[Dict[str, float]] = []
    values: List[float] = []
    names = [v.name for v in variables]
    for step in range(steps):
        alpha = step / max(1, steps - 1)
        temp = initial_temp * ((final_temp / initial_temp) ** alpha)
        proposal = dict(point)
        for name in names:
            lo, hi = bounds[name]
            scale = (hi - lo) * 0.08 * (1 - alpha + 0.05)
            proposal[name] = min(hi, max(lo, proposal[name] + rng.gauss(0, scale)))
        try:
            new_value = float(expr.eval(proposal))
        except Exception:
            new_value = math.inf
        accept = new_value < value or rng.random() < math.exp(-(new_value - value) / max(temp, 1e-12))
        if accept:
            point, value = proposal, new_value
        if value < best_value:
            best_point, best_value = dict(point), float(value)
        path.append(dict(best_point))
        values.append(best_value)
    return OptimizationTrace("simulated_annealing", [v.name for v in variables], path, values, True, "annealing finalizado")


# Preserve previous auto optimizer while adding stronger methods.
_old_auto_optimize = auto_optimize

def auto_optimize(
    expr: Expr,
    variables: Sequence[Symbol],
    start: Dict[str, float] | None = None,
    bounds: Dict[str, Tuple[float, float]] | None = None,
) -> List[OptimizationTrace]:
    traces: List[OptimizationTrace] = []
    if bounds is not None:
        traces.append(random_search(expr, variables, bounds=bounds, samples=1000))
        traces.append(simulated_annealing(expr, variables, bounds=bounds, steps=1500))
        if start is None:
            start = min(traces, key=lambda t: t.best_value).best_point
    if start is not None:
        for lr in [0.1, 0.03, 0.01, 0.003]:
            traces.append(gradient_descent(expr, variables, start=start, lr=lr, steps=1000))
        traces.append(adam_optimize(expr, variables, start=start, lr=0.05, steps=1000))
        traces.append(rmsprop_optimize(expr, variables, start=start, lr=0.03, steps=1000))
        traces.append(newton_optimize(expr, variables, start=start))
    return sorted(traces, key=lambda t: t.best_value)
