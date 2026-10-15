"""Bounded 1D Poisson solver: -u''=f with Dirichlet endpoint values.

Other boundary kinds have contracts but are deliberately rejected by this solver.
No claim of a general PDE engine or physical validation is made.
"""
from dataclasses import dataclass
import math
from ..worlds.boundary_conditions import BoundaryCondition


@dataclass(frozen=True)
class Poisson1D:
    length: float
    left: BoundaryCondition
    right: BoundaryCondition

    def __post_init__(self):
        if isinstance(self.length, bool) or not math.isfinite(self.length) or not 1e-9 <= self.length <= 1e9:
            raise ValueError('Finite bounded positive length required')
        if not all(isinstance(b, BoundaryCondition) for b in (self.left, self.right)):
            raise ValueError('Boundary contracts required')
        if any(b.kind != 'dirichlet' for b in (self.left, self.right)):
            raise ValueError('This solver supports Dirichlet endpoints only')

    def to_data(self):
        return {'schema_version': 1, 'equation': '-u_xx=f', 'length': self.length,
                'left': self.left.to_data(), 'right': self.right.to_data(),
                'coordinates': 'caller-consistent units'}


def solve_poisson_1d(problem, forcing, *, cells=32):
    """Second-order central differences and O(n) Thomas elimination."""
    if not isinstance(problem, Poisson1D) or type(cells) is not int or not 2 <= cells <= 100000:
        raise ValueError('Poisson1D and 2..100000 cells required')
    h = problem.length/cells
    xs = tuple(i*h for i in range(cells+1))
    rhs = []
    for x in xs[1:-1]:
        value = forcing(x)
        if isinstance(value, bool) or not math.isfinite(value):
            raise ValueError('Nonfinite forcing')
        rhs.append(float(value)*h*h)
    rhs[0] += problem.left.value
    rhs[-1] += problem.right.value
    diagonal = [2.0]*(cells-1)
    for i in range(1, cells-1):
        factor = -1.0/diagonal[i-1]
        diagonal[i] += factor
        rhs[i] -= factor*rhs[i-1]
    interior = [0.0]*(cells-1)
    interior[-1] = rhs[-1]/diagonal[-1]
    for i in range(cells-3, -1, -1):
        interior[i] = (rhs[i]+interior[i+1])/diagonal[i]
    values = (problem.left.value, *interior, problem.right.value)
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Solution overflow')
    return {'schema_version': 1, 'problem': problem.to_data(), 'positions': xs,
            'values': values, 'cells': cells, 'method': 'central_difference_thomas',
            'experimental_validation': False}
