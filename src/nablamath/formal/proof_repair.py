"""Closed tactic repair suggestions that never alter statements or hypotheses."""
from __future__ import annotations

from dataclasses import dataclass
from ..core.semantic_contracts import canonical_payload, require_fields, require_digest
from ..core.semantic_ir import fingerprint
from .autoformalization import FormalizationDraft
from .lean_bridge import STRATEGIES, translate_statement


@dataclass(frozen=True)
class RepairProposal:
    draft_id: str
    statement_id: str
    previous_strategy: str
    next_strategy: str
    failure_kind: str

    def __post_init__(self):
        require_digest(self.draft_id)
        require_digest(self.statement_id)
        if (self.previous_strategy not in STRATEGIES or self.next_strategy not in STRATEGIES
                or self.previous_strategy == self.next_strategy
                or self.failure_kind not in {"failed", "timeout", "unsupported"}):
            raise ValueError("Repair must select another allowed tactic after a recoverable failure")

    def to_data(self):
        data = {"schema_version": 1, "draft_id": self.draft_id, "statement_id": self.statement_id,
                "previous_strategy": self.previous_strategy, "next_strategy": self.next_strategy,
                "failure_kind": self.failure_kind, "statement_changed": False,
                "hypotheses_removed": False}
        return {**data, "proposal_id": fingerprint(data)}

    def apply(self, draft: FormalizationDraft):
        if (draft.content_id != self.draft_id or draft.statement.content_id != self.statement_id
                or draft.strategy != self.previous_strategy):
            raise ValueError("Stale or mismatched proof repair")
        result = FormalizationDraft(draft.source, self.next_strategy)
        if result.statement.to_data() != draft.statement.to_data():
            raise ValueError("Proof repair may not change mathematical meaning")
        return result


def suggest_repairs(draft, *, failure_kind, attempted=()):
    if not isinstance(draft, FormalizationDraft):
        raise ValueError("FormalizationDraft required")
    if failure_kind in {"counterexample", "inconsistent_assumptions", "proved", "unsat", "unavailable"}:
        return ()
    if failure_kind not in {"failed", "timeout", "unsupported"}:
        raise ValueError("Unknown proof failure classification")
    if not isinstance(attempted, (list, tuple)) or len(attempted) > len(STRATEGIES):
        raise ValueError("Bounded list of attempted tactics required")
    if any(strategy not in STRATEGIES for strategy in attempted):
        raise ValueError("Unknown attempted tactic")
    hypotheses = draft.statement.hypotheses
    preferred = ("field", "ring", "linarith", "nlinarith", "norm_num", "auto") if hypotheses else (
        "ring", "norm_num", "field", "linarith", "nlinarith", "auto")
    return tuple(RepairProposal(draft.content_id, draft.statement.content_id, draft.strategy, strategy, failure_kind)
                 for strategy in preferred if strategy != draft.strategy and strategy not in attempted)


def verify_repair(proposal: dict, draft):
    try:
        require_fields(proposal, {"schema_version", "draft_id", "statement_id", "previous_strategy",
                                 "next_strategy", "failure_kind", "statement_changed", "hypotheses_removed", "proposal_id"})
        item = RepairProposal(proposal["draft_id"], proposal["statement_id"], proposal["previous_strategy"],
                              proposal["next_strategy"], proposal["failure_kind"])
        item.apply(draft)
        return canonical_payload(proposal) == canonical_payload(item.to_data())
    except (ValueError, TypeError, KeyError, AttributeError):
        return False
