"""Uniform one-dimensional meshes with bounded allocation and explicit units."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class UniformMesh:
    length: float = 1.0
    cells: int = 20
    unit: str = 'm'

    def __post_init__(self):
        if isinstance(self.length, bool) or not math.isfinite(self.length) or self.length <= 0:
            raise ValueError('Comprimento positivo finito obrigatório')
        if type(self.cells) is not int or not 4 <= self.cells <= 2000 or self.unit != 'm':
            raise ValueError('Malha requer 4–2000 células em metros')

    @property
    def spacing(self):
        return self.length / self.cells

    @property
    def nodes(self):
        return tuple(i*self.spacing for i in range(self.cells+1))
