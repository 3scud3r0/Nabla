"""Frozen evaluator contracts and bounded proposals, never arbitrary source patches."""
from dataclasses import dataclass, asdict
import hashlib
import math
from pathlib import Path
from ..core.semantic_ir import fingerprint


def evaluator_digest():
    root=Path(__file__).resolve().parents[1]
    files=('evolution/evaluator.py','worlds/validation.py','worlds/model_spec.py','math/equations/ode.py',
           'evolution/statistical_tests.py','evolution/proposal_validator.py','evolution/release_gate.py')
    return fingerprint({name:hashlib.sha256((root/name).read_text(encoding='utf-8').encode('utf-8')).hexdigest() for name in files})


@dataclass(frozen=True)
class EvaluationContract:
    tolerance: float = 1e-5
    alpha: float = .05
    max_derivative_calls: int = 400
    max_candidates: int = 16
    max_generations: int = 8
    evaluator_id: str = ''

    def __post_init__(self):
        if not math.isfinite(self.tolerance) or self.tolerance<=0 or not 0<self.alpha<1:
            raise ValueError('Tolerância/alpha inválidos')
        if (type(self.max_derivative_calls) is not int or not 4<=self.max_derivative_calls<=40000
                or type(self.max_candidates) is not int or not 1<=self.max_candidates<=32
                or type(self.max_generations) is not int or not 1<=self.max_generations<=32):
            raise ValueError('Orçamento inválido')
        if not self.evaluator_id:
            object.__setattr__(self,'evaluator_id',evaluator_digest())

    def to_data(self):
        return asdict(self)

    @property
    def contract_id(self):
        return fingerprint(self.to_data())

    def assert_current(self):
        if self.evaluator_id!=evaluator_digest():
            raise ValueError('Código do avaliador mudou; requer novo contrato revisado')


def validate_proposal(candidate,parent,contract):
    contract.assert_current()
    if (candidate.parent_id!=parent.genome_id or candidate.generation!=parent.generation+1
            or candidate.generation>contract.max_generations):
        raise ValueError('Linhagem ou geração inválida')
    if candidate.as_policy().derivative_calls>contract.max_derivative_calls:
        raise ValueError('Proposta excede custo permitido')
    if candidate.semantic_id==parent.semantic_id:
        raise ValueError('Proposta não altera política')
    return {'valid':True,'candidate_id':candidate.genome_id,'contract_id':contract.contract_id}
