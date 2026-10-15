"""Versioned scalar endpoint contracts; derivatives point in the +x direction."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class BoundaryCondition:
    kind: str
    value: float
    alpha: float = 1.0
    beta: float = 0.0

    def __post_init__(self):
        if self.kind not in {'dirichlet', 'neumann', 'robin'}:
            raise ValueError('Unsupported boundary kind')
        if any(isinstance(v, bool) or not math.isfinite(v) for v in (self.value, self.alpha, self.beta)):
            raise ValueError('Boundary coefficients must be finite numbers')
        if self.kind == 'robin' and self.alpha == self.beta == 0:
            raise ValueError('Robin condition cannot have zero coefficients')

    def residual(self, value, derivative):
        if any(isinstance(v, bool) or not math.isfinite(v) for v in (value, derivative)):
            raise ValueError('Boundary state must be finite')
        if self.kind == 'dirichlet':
            return value - self.value
        if self.kind == 'neumann':
            return derivative - self.value
        return self.alpha*value + self.beta*derivative - self.value

    def to_data(self):
        from dataclasses import asdict
        return {'schema_version': 1, **asdict(self), 'derivative_convention': 'positive_x'}
