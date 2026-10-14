"""Declarative, immutable numerical policies; executable code is not a genome."""
from dataclasses import dataclass, asdict
import re
from .evaluator import SolverPolicy
from ..core.semantic_ir import fingerprint


@dataclass(frozen=True)
class PolicyGenome:
    method: str
    steps: int
    parent_id: str | None = None
    generation: int = 0
    schema_version: int = 1

    def __post_init__(self):
        SolverPolicy(self.method,self.steps)
        if type(self.generation) is not int or not 0<=self.generation<=32 or self.schema_version!=1:
            raise ValueError('Geração/versão inválida')
        if self.parent_id is not None and not re.fullmatch(r'[a-f0-9]{64}',self.parent_id):
            raise ValueError('Pai deve ser ID imutável')
        if (self.generation==0)!=(self.parent_id is None):
            raise ValueError('Geração raiz e descendentes requerem pais coerentes')

    @property
    def genome_id(self):
        return fingerprint(self.to_data())

    @property
    def semantic_id(self):
        return self.as_policy().policy_id

    def as_policy(self):
        return SolverPolicy(self.method,self.steps)

    def to_data(self):
        return asdict(self)

    @classmethod
    def from_data(cls,data):
        if set(data)!={'method','steps','parent_id','generation','schema_version'}:
            raise ValueError('Genoma admite somente dados declarativos conhecidos')
        return cls(**data)
