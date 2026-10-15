"""Versioned controlled-language drafts with explicit review binding.

This parser accepts a small language, not unrestricted natural language. It does
not infer intended meaning or authenticate the person making a review decision.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from ..core.semantic_contracts import canonical_payload, load_json, require_fields, require_text
from ..core.semantic_ir import fingerprint
from ..expression import parse_expr
from .statement import FormalStatement, Predicate
from .lean_bridge import translate_statement

GRAMMAR_VERSION = "controlled-rational-v1"
OPERATORS = {"==": "eq", "!=": "ne", "<=": "le", ">=": "ge", "<": "lt", ">": "gt"}


def parse_predicate(source: str) -> Predicate:
    require_text(source, "predicate", limit=4096)
    parts = re.split(r"(==|!=|<=|>=|<|>)", source)
    if len(parts) != 3 or not parts[0].strip() or not parts[2].strip():
        raise ValueError("Exactly one explicit relation per predicate required")
    return Predicate(parse_expr(parts[0].strip()), OPERATORS[parts[1]], parse_expr(parts[2].strip()))


def parse_controlled_statement(source: str) -> FormalStatement:
    """Parse ``[forall x,y in Q: ]prove predicate[ where predicate; ...]``.

    Every free symbol must appear exactly once in the quantifier list. Constant
    statements omit the quantifier prefix. Assumptions are conjunctions only;
    comments, proof snippets, quantifier alternation and undeclared symbols fail.
    """
    require_text(source, "controlled source", limit=16384)
    if "\n" in source or "\r" in source or "#" in source:
        raise ValueError("Controlled statements use one uncommented line")
    body = source.strip()
    variables = ()
    if body.startswith("forall "):
        match = re.match(r"^forall ([A-Za-z][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z][A-Za-z0-9_]*)*) in Q:\s*", body)
        if match is None:
            raise ValueError("Unsupported quantifier declaration")
        variables = tuple(part.strip() for part in match.group(1).split(","))
        if len(variables) > 8 or len(set(variables)) != len(variables):
            raise ValueError("At most eight distinct quantified symbols required")
        body = body[match.end():]
    if not body.startswith("prove "):
        raise ValueError("Controlled statement must explicitly begin with prove")
    body = body[6:]
    if body.count(" where ") > 1:
        raise ValueError("Only one assumption clause supported")
    goal_source, separator, assumptions_source = body.partition(" where ")
    assumptions = ()
    if separator:
        pieces = assumptions_source.split(";")
        if len(pieces) > 32 or any(not piece.strip() for piece in pieces):
            raise ValueError("At most 32 nonempty explicit assumptions required")
        assumptions = tuple(parse_predicate(piece.strip()) for piece in pieces)
    result = FormalStatement(parse_predicate(goal_source.strip()), assumptions)
    if set(result.variables) != set(variables):
        raise ValueError("Quantifiers must match exactly the free symbols")
    return result


@dataclass(frozen=True)
class FormalizationDraft:
    """Immutable input/AST/source snapshot; a draft is not a theorem proof."""

    source: str
    strategy: str = "auto"

    def __post_init__(self):
        statement = parse_controlled_statement(self.source)
        translate_statement(statement, self.strategy)

    @property
    def statement(self):
        return parse_controlled_statement(self.source)

    @property
    def translation(self):
        return translate_statement(self.statement, self.strategy)

    def to_data(self):
        return {"schema_version": 1, "grammar": GRAMMAR_VERSION, "source": self.source,
                "strategy": self.strategy, "statement": self.statement.to_data(),
                "statement_id": self.statement.content_id, "translation": self.translation.to_data(),
                "natural_language_semantics_inferred": False, "formal_proof": False}

    @property
    def content_id(self):
        return fingerprint(self.to_data())

    def to_json(self):
        return canonical_payload({**self.to_data(), "draft_id": self.content_id})

    @classmethod
    def from_json(cls, raw: str):
        data = load_json(raw)
        fields = {"schema_version", "grammar", "source", "strategy", "statement", "statement_id",
                  "translation", "natural_language_semantics_inferred", "formal_proof", "draft_id"}
        require_fields(data, fields)
        draft = cls(data["source"], data["strategy"])
        if canonical_payload(data) != draft.to_json():
            raise ValueError("Formalization draft differs from controlled source regeneration")
        return draft


@dataclass(frozen=True)
class FormalizationReview:
    """Caller-authenticated review declaration bound to one complete draft."""

    draft_id: str
    reviewer: str
    accepted: bool
    correspondence_notes: str

    def __post_init__(self):
        from ..core.semantic_contracts import require_digest
        require_digest(self.draft_id)
        require_text(self.reviewer, "reviewer", limit=256)
        require_text(self.correspondence_notes, "correspondence notes")
        if type(self.accepted) is not bool:
            raise ValueError("Review decision must be an explicit boolean")

    def require(self, draft: FormalizationDraft):
        if not isinstance(draft, FormalizationDraft) or not self.accepted or self.draft_id != draft.content_id:
            raise PermissionError("Current affirmative review of this exact draft required")

    def to_data(self):
        data = {"schema_version": 1, "draft_id": self.draft_id, "reviewer": self.reviewer,
                "accepted": self.accepted, "correspondence_notes": self.correspondence_notes,
                "reviewer_authenticated_by_library": False}
        return {**data, "review_id": fingerprint(data)}
