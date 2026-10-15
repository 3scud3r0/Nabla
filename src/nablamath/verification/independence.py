"""Declared actor separation, not authentication or institutional independence."""
from dataclasses import dataclass

from ..core.semantic_contracts import require_text


@dataclass(frozen=True)
class IndependencePolicy:
    proposer: str
    solver: str
    evaluator: str
    reviewer: str

    def __post_init__(self):
        actors = [require_text(getattr(self, field), field, limit=256)
                  for field in ("proposer", "solver", "evaluator", "reviewer")]
        if len(set(actors)) != 4:
            raise ValueError("Four distinct declared actors are required")

    def to_data(self):
        return {field: getattr(self, field)
                for field in ("proposer", "solver", "evaluator", "reviewer")}
