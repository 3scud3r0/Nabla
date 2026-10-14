"""Explicit domains and scalar/vector/matrix shapes; no implicit float coercion."""
from dataclasses import dataclass
from enum import Enum
from .units import ONE,Unit


class ScalarDomain(str,Enum):
    RATIONAL='rational'
    REAL_APPROXIMATION='real_approximation'
    BOOLEAN='boolean'


@dataclass(frozen=True)
class ScientificType:
    domain: ScalarDomain=ScalarDomain.RATIONAL
    shape: tuple[int,...]=()
    unit: Unit=ONE

    def __post_init__(self):
        object.__setattr__(self,'domain',ScalarDomain(self.domain))
        if len(self.shape)>2 or any(type(n) is not int or not 1<=n<=32 for n in self.shape):
            raise ValueError('Forma deve ser escalar, vetor ou matriz ate 32')
        object.__setattr__(self,'shape',tuple(self.shape))
        if self.domain==ScalarDomain.BOOLEAN and self.unit.dimensions!=ONE.dimensions:
            raise ValueError('Booleanos nao possuem unidade fisica')

    def to_data(self):
        return {'domain':self.domain.value,'shape':list(self.shape),'unit':self.unit.to_data()}
