"""Versioned data-only algorithm choices committed to an exact evaluation.

A CodeProposal does not contain a patch, module path, callback, bytecode, command,
URL or source text. The name refers to a proposal about a known algorithm, not
permission to execute generated code. Extending ALGORITHMS requires an ordinary
reviewed repository change. Hash commitments are integrity checks, not signatures.
"""
from dataclasses import asdict, dataclass
from itertools import islice
import hashlib
from pathlib import Path

from ..core.semantic_contracts import require_digest, require_fields, require_text
from ..core.semantic_ir import canonical_json, fingerprint
from ..evaluation.frozen import FrozenEvaluation

ALGORITHMS = frozenset({'exact-rational-v1', 'alternate-rational-v1'})
VERSION = 'declarative-algorithm-proposal-v1'


def implementation_digest():
    """Bind trials to the actual trusted implementations and evaluator sources."""
    root = Path(__file__).resolve().parents[1]
    names = ('evolution/code_proposals.py', 'evolution/secure_trials.py',
             'evaluation/frozen.py', 'verify/certificate.py',
             'math/linear_algebra/matrices.py', 'math/linear_algebra/solvers.py',
             'agents/tool_registry.py', 'core/semantic_contracts.py',
             'verification/independence.py', 'evaluation/lineage.py',
             'verify/__init__.py', 'core/semantic_ir.py')
    return fingerprint({name: hashlib.sha256((root/name).read_bytes()).hexdigest()
                        for name in names})


@dataclass(frozen=True)
class TrialBudget:
    """Whole-trial limits. Task cost is conservatively charged before execution."""
    max_tasks: int = 16
    max_attempts: int = 1
    max_input_bytes: int = 65536
    max_output_bytes: int = 262144
    timeout_seconds: float = 10.0

    def __post_init__(self):
        import math
        limits = ((self.max_tasks, 100), (self.max_attempts, 8),
                  (self.max_input_bytes, 1048576), (self.max_output_bytes, 1048576))
        if any(type(value) is not int or not 1 <= value <= limit for value, limit in limits):
            raise ValueError('Invalid trial budget')
        if (isinstance(self.timeout_seconds, bool)
                or not isinstance(self.timeout_seconds, (int, float))
                or not math.isfinite(self.timeout_seconds)
                or not 0 < self.timeout_seconds <= 60):
            raise ValueError('Invalid trial deadline')

    def to_data(self):
        return asdict(self)

    @classmethod
    def from_data(cls, data):
        require_fields(data, set(cls.__dataclass_fields__))
        return cls(**data)


@dataclass(frozen=True)
class CodeProposal:
    """One immutable algorithm revision against exactly one frozen protocol."""
    algorithm: str
    protocol_id: str
    implementation_id: str
    owner: str
    rationale: str
    budget: TrialBudget
    parent_id: str | None = None
    generation: int = 0
    schema_version: int = 1

    def __post_init__(self):
        if self.algorithm not in ALGORITHMS:
            raise ValueError('Only reviewed built-in algorithm IDs are allowed')
        require_digest(self.protocol_id)
        require_digest(self.implementation_id)
        require_text(self.owner, 'owner', limit=256)
        require_text(self.rationale, 'rationale', limit=4096)
        if not isinstance(self.budget, TrialBudget):
            raise ValueError('Immutable trial budget required')
        if type(self.generation) is not int or not 0 <= self.generation <= 32:
            raise ValueError('Invalid proposal generation')
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError('Unsupported proposal version')
        if self.parent_id is not None:
            require_digest(self.parent_id)
        if (self.generation == 0) != (self.parent_id is None):
            raise ValueError('Root and child lineage must be explicit')

    @classmethod
    def create(cls, protocol, *, algorithm, owner, rationale, budget=None):
        if not isinstance(protocol, FrozenEvaluation):
            raise ValueError('Frozen exact evaluation required')
        result = cls(algorithm, protocol.protocol_id, implementation_digest(),
                     owner, rationale, budget or TrialBudget())
        result.preflight(protocol)
        return result

    def descendant(self, *, algorithm, rationale, budget=None):
        """A changed budget is part of the new revision and invalidates approval."""
        return CodeProposal(algorithm, self.protocol_id, self.implementation_id,
                            self.owner, rationale, budget or self.budget,
                            self.proposal_id, self.generation+1)

    def to_data(self):
        return asdict(self)

    @property
    def proposal_id(self):
        return fingerprint(self.to_data())

    @classmethod
    def from_data(cls, data, *, expected_id):
        require_digest(expected_id)
        require_fields(data, set(cls.__dataclass_fields__))
        payload = dict(data)
        payload['budget'] = TrialBudget.from_data(payload['budget'])
        result = cls(**payload)
        if result.proposal_id != expected_id:
            raise ValueError('Proposal commitment mismatch')
        return result

    def preflight(self, protocol):
        import json
        if not isinstance(protocol, FrozenEvaluation) or protocol.protocol_id != self.protocol_id:
            raise ValueError('Proposal targets a different frozen protocol')
        if self.implementation_id != implementation_digest():
            raise ValueError('Trusted implementation changed; create a newly reviewed proposal')
        data = json.loads(protocol.protocol_json)
        tasks = data['tasks']
        if len(tasks) > self.budget.max_tasks:
            raise ValueError('Frozen cohort exceeds whole-trial task budget')
        if len(canonical_json(data).encode()) > self.budget.max_input_bytes:
            raise ValueError('Frozen protocol exceeds input budget')
        # The built-in trial adapter intentionally supports a small exact domain.
        # FrozenEvaluation supports larger cohorts; that does not expand this worker.
        for task in tasks:
            if task['family'] == 'linear_system' and len(task['rhs']) > 8:
                raise ValueError('Trial linear systems are limited to dimension eight')
            if task['family'] == 'polynomial_integral' and len(task['coefficients']) > 16:
                raise ValueError('Trial integral degree exceeds supported arithmetic budget')
        return self.proposal_id


def validate_lineage(proposals):
    """Validate a bounded ordered revision chain, never resolve external parents."""
    rows = list(islice(proposals, 34))
    if not rows or len(rows) > 33:
        raise ValueError('Expected at most 33 proposal revisions')
    previous = None
    for proposal in rows:
        if not isinstance(proposal, CodeProposal):
            raise ValueError('Typed proposal required')
        if previous is None:
            if proposal.parent_id is not None:
                raise ValueError('Lineage must begin at a root')
        elif (proposal.parent_id != previous.proposal_id
              or proposal.generation != previous.generation+1
              or proposal.protocol_id != previous.protocol_id
              or proposal.owner != previous.owner
              or proposal.implementation_id != previous.implementation_id):
            raise ValueError('Revision chain fork or contract change')
        previous = proposal
    return dict(valid=True, count=len(rows), head=previous.proposal_id)
