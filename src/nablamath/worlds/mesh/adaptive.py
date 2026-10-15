"""Deterministic bounded one-dimensional adaptive piecewise-linear meshes.

Quarter-point residuals are sampled error indicators, never rigorous supremum
bounds. They can miss oscillations between samples. An optional supplied bound
on |f''| gives a conditional h²M/8 interpolation bound per cell. No PDE solver,
multidimensional mesh or automatic derivative certification is implied.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from itertools import islice
import math
from typing import Callable, Iterable, Mapping

CONTRACT_VERSION = 1
MAX_NODES = 16385


def _finite(value: float, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _bounded_values(values: Iterable[float], label: str) -> tuple[float, ...]:
    result = tuple(_finite(v, label) for v in islice(values, MAX_NODES + 1))
    if len(result) > MAX_NODES:
        raise ValueError(f"{label} node budget exceeded")
    return result


@dataclass(frozen=True)
class Mesh1D:
    nodes: tuple[float, ...]
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        nodes = _bounded_values(self.nodes, "mesh coordinates")
        values = _bounded_values(self.values, "mesh values")
        if len(nodes) < 2 or len(nodes) != len(values):
            raise ValueError("mesh requires equal node/value lengths and at least two nodes")
        if any(right <= left for left, right in zip(nodes, nodes[1:])):
            raise ValueError("mesh coordinates must be strictly increasing")
        if not math.isfinite(nodes[-1] - nodes[0]):
            raise ValueError("mesh span must be representable")
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "values", values)

    @property
    def cell_count(self) -> int:
        return len(self.nodes) - 1

    @property
    def domain(self) -> tuple[float, float]:
        return self.nodes[0], self.nodes[-1]

    @property
    def widths(self) -> tuple[float, ...]:
        return tuple(b-a for a, b in zip(self.nodes, self.nodes[1:]))

    def locate(self, x: float) -> int:
        """Cell containing x; the right endpoint belongs to the last cell."""
        x = _finite(x, "query coordinate")
        if not self.nodes[0] <= x <= self.nodes[-1]:
            raise ValueError("query lies outside mesh domain")
        return min(bisect_right(self.nodes, x)-1, self.cell_count-1)

    def interpolate(self, x: float) -> float:
        x = _finite(x, "query coordinate")
        i = self.locate(x)
        weight = (x-self.nodes[i]) / (self.nodes[i+1]-self.nodes[i])
        result = (1-weight)*self.values[i] + weight*self.values[i+1]
        if not math.isfinite(result):
            raise ArithmeticError("interpolation overflow")
        return result

    def slope(self, cell: int) -> float:
        if type(cell) is not int or not 0 <= cell < self.cell_count:
            raise ValueError("invalid cell index")
        result = (self.values[cell+1]-self.values[cell]) / (self.nodes[cell+1]-self.nodes[cell])
        if not math.isfinite(result):
            raise ArithmeticError("slope overflow")
        return result

    def integrate(self, left: float | None = None, right: float | None = None) -> float:
        """Exactly integrate the piecewise-linear interpolant (float arithmetic)."""
        a = self.nodes[0] if left is None else _finite(left, "left integration endpoint")
        b = self.nodes[-1] if right is None else _finite(right, "right integration endpoint")
        self.locate(a)
        self.locate(b)
        if a == b:
            return 0.0
        if b < a:
            return -self.integrate(b, a)
        points = [a] + [x for x in self.nodes if a < x < b] + [b]
        contributions = []
        for lo, hi in zip(points, points[1:]):
            contributions.append((hi-lo) * (self.interpolate(lo)+self.interpolate(hi)) / 2)
        result = math.fsum(contributions)
        if not math.isfinite(result):
            raise ArithmeticError("integral overflow")
        return result

    def to_data(self) -> dict:
        return {"version": CONTRACT_VERSION, "nodes": list(self.nodes), "values": list(self.values)}

    @classmethod
    def from_data(cls, data: Mapping) -> Mesh1D:
        if (not isinstance(data, Mapping) or set(data) != {"version", "nodes", "values"}
                or type(data["version"]) is not int or data["version"] != CONTRACT_VERSION
                or not isinstance(data["nodes"], list) or not isinstance(data["values"], list)):
            raise ValueError("invalid mesh payload schema")
        return cls(data["nodes"], data["values"])


@dataclass(frozen=True)
class CellIndicator:
    left: float
    right: float
    sampled_error: float
    threshold: float
    curvature_bound: float | None = None

    @property
    def needs_refinement(self) -> bool:
        return self.sampled_error > self.threshold


@dataclass(frozen=True)
class RefinementRecord:
    iteration: int
    cells: int
    evaluations: int
    maximum_sampled_error: float
    marked_cells: int


@dataclass(frozen=True)
class AdaptiveResult:
    mesh: Mesh1D
    indicators: tuple[CellIndicator, ...]
    history: tuple[RefinementRecord, ...]
    converged: bool
    reason: str
    evaluations: int

    def to_data(self) -> dict:
        return {
            "version": CONTRACT_VERSION,
            "mesh": self.mesh.to_data(),
            "indicators": [dict(left=i.left, right=i.right, sampled_error=i.sampled_error,
                                threshold=i.threshold, curvature_bound=i.curvature_bound)
                           for i in self.indicators],
            "history": [dict(iteration=r.iteration, cells=r.cells, evaluations=r.evaluations,
                             maximum_sampled_error=r.maximum_sampled_error, marked_cells=r.marked_cells)
                        for r in self.history],
            "converged": self.converged,
            "reason": self.reason,
            "evaluations": self.evaluations,
        }


class _EvaluationBudget(Exception):
    pass


class _Sampler:
    """Cache deterministic coordinate evaluations; callbacks must be pure."""
    def __init__(self, function: Callable[[float], float], budget: int):
        self.function = function
        self.budget = budget
        self.cache: dict[float, float] = {}

    def __call__(self, x: float) -> float:
        if x not in self.cache:
            if len(self.cache) >= self.budget:
                raise _EvaluationBudget
            self.cache[x] = _finite(self.function(x), "profile evaluation")
        return self.cache[x]


def uniform_mesh(function: Callable[[float], float], left: float, right: float,
                 cells: int = 4) -> Mesh1D:
    """Sample an initial uniform mesh; reject collapsed floating coordinates."""
    left, right = _finite(left, "left endpoint"), _finite(right, "right endpoint")
    if right <= left or not math.isfinite(right-left):
        raise ValueError("finite ordered endpoints required")
    if type(cells) is not int or not 1 <= cells < MAX_NODES:
        raise ValueError("invalid initial cell count")
    nodes = tuple(left + (right-left)*(i/cells) for i in range(cells)) + (right,)
    if any(b <= a for a, b in zip(nodes, nodes[1:])):
        raise ValueError("uniform coordinates are not representable")
    return Mesh1D(nodes, tuple(function(x) for x in nodes))


def estimate_cells(mesh: Mesh1D, function: Callable[[float], float], *,
                   absolute_tolerance: float = 1e-4, relative_tolerance: float = 0,
                   second_derivative_bound: Callable[[float, float], float] | None = None,
                   ) -> tuple[CellIndicator, ...]:
    """Compare interpolant with fresh samples at 1/4, 1/2 and 3/4 of each cell.

    curvature_bound is h²M/8 conditional on the supplied M actually bounding
    |f''| throughout the cell. It is reported separately from sampled error.
    """
    atol = _finite(absolute_tolerance, "absolute tolerance")
    rtol = _finite(relative_tolerance, "relative tolerance")
    if atol < 0 or rtol < 0 or atol == rtol == 0:
        raise ValueError("at least one tolerance must be positive")
    indicators = []
    for i, (left, right) in enumerate(zip(mesh.nodes, mesh.nodes[1:])):
        errors, magnitude = [], max(abs(mesh.values[i]), abs(mesh.values[i+1]))
        for fraction in (.25, .5, .75):
            point = left + (right-left)*fraction
            if not left < point < right:
                raise ValueError("interior estimator coordinates are not representable")
            value = _finite(function(point), "estimator evaluation")
            approximation = mesh.interpolate(point)
            errors.append(abs(value-approximation))
            magnitude = max(magnitude, abs(value))
        threshold = atol + rtol*magnitude
        if not math.isfinite(threshold) or not all(math.isfinite(error) for error in errors):
            raise ArithmeticError("estimator arithmetic overflow")
        bound = None
        if second_derivative_bound is not None:
            curvature = _finite(second_derivative_bound(left, right), "curvature bound")
            if curvature < 0:
                raise ValueError("curvature bound must be nonnegative")
            bound = (right-left)**2 * curvature / 8
            if not math.isfinite(bound):
                raise ArithmeticError("curvature bound overflow")
        indicators.append(CellIndicator(left, right, max(errors), threshold, bound))
    return tuple(indicators)


def refine_mesh(mesh: Mesh1D, cells: Iterable[int], function: Callable[[float], float], *,
                max_cells: int = MAX_NODES-1) -> Mesh1D:
    """Bisect specified cells once; retain every old node and value."""
    if type(max_cells) is not int or not 1 <= max_cells < MAX_NODES:
        raise ValueError("invalid cell budget")
    selected = tuple(islice(cells, MAX_NODES))
    if len(selected) >= MAX_NODES or any(type(i) is not int or not 0 <= i < mesh.cell_count for i in selected):
        raise ValueError("invalid refinement cell list")
    marked = set(selected)
    if mesh.cell_count + len(marked) > max_cells:
        raise ValueError("refinement would exceed cell budget")
    nodes, values = [], []
    for i, (left, right) in enumerate(zip(mesh.nodes, mesh.nodes[1:])):
        nodes.append(left)
        values.append(mesh.values[i])
        if i in marked:
            midpoint = left + (right-left)/2
            if not left < midpoint < right:
                raise ValueError("refinement midpoint is not representable")
            nodes.append(midpoint)
            values.append(function(midpoint))
    nodes.append(mesh.nodes[-1])
    values.append(mesh.values[-1])
    return Mesh1D(tuple(nodes), tuple(values))


def adaptive_interpolate(function: Callable[[float], float], left: float, right: float, *,
                         initial_cells: int = 4, absolute_tolerance: float = 1e-4,
                         relative_tolerance: float = 0, max_cells: int = 1024,
                         max_iterations: int = 20, max_evaluations: int = 100000,
                         second_derivative_bound: Callable[[float, float], float] | None = None,
                         ) -> AdaptiveResult:
    """Refine every marked cell deterministically until sampled criteria pass.

    When a budget prevents another full iteration, return the last complete
    mesh, with converged=False and a specific reason. Evaluation count includes
    cached estimator samples, not just retained mesh nodes. Profile callbacks
    must be pure; determinism cannot be promised for stateful callbacks.
    """
    if type(max_cells) is not int or not 1 <= max_cells < MAX_NODES:
        raise ValueError("invalid cell budget")
    if type(initial_cells) is not int or not 1 <= initial_cells <= max_cells:
        raise ValueError("initial cells exceed budget")
    if type(max_iterations) is not int or not 0 <= max_iterations <= 100:
        raise ValueError("invalid iteration budget")
    if type(max_evaluations) is not int or not initial_cells+1 <= max_evaluations <= 1000000:
        raise ValueError("invalid evaluation budget")
    sampler = _Sampler(function, max_evaluations)
    mesh = uniform_mesh(sampler, left, right, initial_cells)
    history = []
    indicators: tuple[CellIndicator, ...] = ()
    for iteration in range(max_iterations+1):
        try:
            indicators = estimate_cells(mesh, sampler, absolute_tolerance=absolute_tolerance,
                                        relative_tolerance=relative_tolerance,
                                        second_derivative_bound=second_derivative_bound)
        except _EvaluationBudget:
            return AdaptiveResult(mesh, (), tuple(history), False, "evaluation_budget", len(sampler.cache))
        marked = [i for i, indicator in enumerate(indicators) if indicator.needs_refinement]
        history.append(RefinementRecord(iteration, mesh.cell_count, len(sampler.cache),
                                        max(i.sampled_error for i in indicators), len(marked)))
        if not marked:
            return AdaptiveResult(mesh, indicators, tuple(history), True, "sampled_tolerance", len(sampler.cache))
        if iteration == max_iterations:
            reason = "iteration_budget"
            break
        if mesh.cell_count+len(marked) > max_cells:
            reason = "cell_budget"
            break
        # Midpoints were already sampled in estimate_cells, so refinement does
        # not consume new evaluations or leave a partially updated mesh.
        mesh = refine_mesh(mesh, marked, sampler, max_cells=max_cells)
    return AdaptiveResult(mesh, indicators, tuple(history), False, reason, len(sampler.cache))


def sampled_error(mesh: Mesh1D, reference: Callable[[float], float], points: Iterable[float]) -> float:
    """Maximum error on a bounded independent validation grid, not a norm bound."""
    coordinates = tuple(islice(points, 100001))
    if not coordinates or len(coordinates) > 100000:
        raise ValueError("validation grid must have 1..100000 points")
    maximum = 0.0
    for x in coordinates:
        error = abs(mesh.interpolate(x)-_finite(reference(x), "reference value"))
        if not math.isfinite(error):
            raise ArithmeticError("validation error overflow")
        maximum = max(maximum, error)
    return maximum
