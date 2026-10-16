"""Bounded, reviewed, closed-portfolio proof planning with semantic replay.

Generated Lean is executed only through the existing checked backend. SMT UNSAT
is a solver result, not a Lean certificate. Stored success flags are not trusted
by replay, and a counterexample terminates the portfolio instead of being hidden.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import time

from ..calc.session import encode
from ..core.semantic_contracts import canonical_payload, load_json, require_fields
from ..core.semantic_ir import fingerprint, rational
from .autoformalization import FormalizationDraft, FormalizationReview
from .lean_bridge import translate_statement, STRATEGIES
from .lean_checker import check_lean
from .smt_bridge import solve_statement

TERMINAL = frozenset({"proved", "unsat", "counterexample", "inconsistent_assumptions"})
KNOWN_STATUSES = frozenset({"proved", "unsat", "counterexample", "inconsistent_assumptions",
                            "unsupported", "unavailable", "unknown", "failed", "timeout",
                            "rejected_axioms", "translation_rejected", "replay_failed"})
RUN_SCOPE = "reviewed controlled language and closed tactics; review identity unverified; SMT UNSAT is not a Lean certificate"


@dataclass(frozen=True)
class ProofBudget:
    max_attempts: int = 4
    attempt_timeout_seconds: int = 5
    total_seconds: int = 20
    backends: tuple[str, ...] = ("smt", "lean")
    strategies: tuple[str, ...] = ("auto", "ring", "field")

    def __post_init__(self):
        for value, limit in ((self.max_attempts, 8), (self.attempt_timeout_seconds, 60), (self.total_seconds, 300)):
            if type(value) is not int or not 1 <= value <= limit:
                raise ValueError("Invalid proof search budget")
        if not isinstance(self.backends, (tuple, list)) or not 1 <= len(self.backends) <= 2:
            raise ValueError("One or two explicit backends required")
        if len(set(self.backends)) != len(self.backends) or any(item not in ("smt", "lean") for item in self.backends):
            raise ValueError("Unknown or duplicate proof backend")
        if not isinstance(self.strategies, (tuple, list)) or not 1 <= len(self.strategies) <= len(STRATEGIES):
            raise ValueError("Bounded explicit tactic portfolio required")
        if len(set(self.strategies)) != len(self.strategies) or any(item not in STRATEGIES for item in self.strategies):
            raise ValueError("Unknown or duplicate proof tactic")
        object.__setattr__(self, "backends", tuple(self.backends))
        object.__setattr__(self, "strategies", tuple(self.strategies))

    def to_data(self):
        return encode(asdict(self))


@dataclass(frozen=True)
class ProofPlan:
    manifest_json: str

    def __post_init__(self):
        data = load_json(self.manifest_json)
        require_fields(data, {"schema_version", "draft_id", "statement_id", "budget", "attempts"})
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ValueError("Unsupported proof plan version")
        from ..core.semantic_contracts import require_digest
        require_digest(data["draft_id"])
        require_digest(data["statement_id"])
        require_fields(data["budget"], {"max_attempts", "attempt_timeout_seconds", "total_seconds", "backends", "strategies"})
        budget = ProofBudget(**data["budget"])
        rows = data["attempts"]
        if not isinstance(rows, list) or not 1 <= len(rows) <= budget.max_attempts:
            raise ValueError("Invalid proof attempt count")
        consumed, identities = 0, set()
        for index, row in enumerate(rows):
            require_fields(row, {"index", "backend", "strategy", "timeout_seconds", "translation_hash"})
            if type(row["index"]) is not int or row["index"] != index or row["backend"] not in budget.backends:
                raise ValueError("Invalid proof attempt ordering/backend")
            backend, strategy = row["backend"], row["strategy"]
            if backend == "smt":
                if strategy != "QF_LRA" or row["translation_hash"] is not None:
                    raise ValueError("SMT attempts use the typed QF_LRA backend only")
            else:
                if strategy not in budget.strategies:
                    raise ValueError("Lean strategy outside portfolio")
                require_digest(row["translation_hash"])
            identity = (backend, strategy)
            if identity in identities:
                raise ValueError("Duplicate proof attempt")
            identities.add(identity)
            timeout = row["timeout_seconds"]
            if type(timeout) is not int or not 1 <= timeout <= budget.attempt_timeout_seconds:
                raise ValueError("Invalid per-attempt proof deadline")
            consumed += timeout
        if consumed > budget.total_seconds:
            raise ValueError("Planned deadlines exceed total proof budget")
        object.__setattr__(self, "manifest_json", canonical_payload(data))

    def to_data(self):
        return load_json(self.manifest_json)

    @property
    def content_id(self):
        return fingerprint(self.to_data())

    def to_json(self):
        return canonical_payload({**self.to_data(), "plan_id": self.content_id})

    @classmethod
    def from_json(cls, raw):
        data = load_json(raw)
        require_fields(data, {"schema_version", "draft_id", "statement_id", "budget", "attempts", "plan_id"})
        identifier = data.pop("plan_id")
        result = cls(canonical_payload(data))
        if result.content_id != identifier:
            raise ValueError("Proof plan commitment mismatch")
        return result


def build_proof_plan(draft: FormalizationDraft, budget: ProofBudget = ProofBudget()):
    if not isinstance(draft, FormalizationDraft) or not isinstance(budget, ProofBudget):
        raise ValueError("Typed draft and proof budget required")
    candidates = []
    for backend in budget.backends:
        if backend == "smt":
            candidates.append((backend, "QF_LRA", None))
        else:
            for strategy in budget.strategies:
                candidates.append((backend, strategy, translate_statement(draft.statement, strategy).source_hash))
    remaining, attempts = budget.total_seconds, []
    for backend, strategy, source_hash in candidates[:budget.max_attempts]:
        timeout = min(budget.attempt_timeout_seconds, remaining)
        if timeout < 1:
            break
        attempts.append({"index": len(attempts), "backend": backend, "strategy": strategy,
                         "timeout_seconds": timeout, "translation_hash": source_hash})
        remaining -= timeout
    return ProofPlan(canonical_payload({"schema_version": 1, "draft_id": draft.content_id,
        "statement_id": draft.statement.content_id, "budget": budget.to_data(), "attempts": attempts}))


def _require_current_plan(draft, review, plan):
    if not isinstance(review, FormalizationReview) or not isinstance(plan, ProofPlan):
        raise ValueError("Typed review and proof plan required")
    review.require(draft)
    expected = build_proof_plan(draft, ProofBudget(**plan.to_data()["budget"]))
    if expected != plan:
        raise ValueError("Proof plan does not match regenerated typed statement/portfolio")


def execute_proof_plan(draft, review, plan, *, project=Path("lean"), stop_after=None):
    _require_current_plan(draft, review, plan)
    data = plan.to_data()
    if stop_after is not None and (type(stop_after) is not int or not 1 <= stop_after <= len(data["attempts"])):
        raise ValueError("Invalid proof checkpoint boundary")
    start = time.monotonic()
    attempts, stopped = [], "portfolio_exhausted"
    for step in data["attempts"]:
        if stop_after is not None and len(attempts) >= stop_after:
            stopped = "checkpoint"
            break
        remaining = data["budget"]["total_seconds"] - (time.monotonic()-start)
        if remaining < 1:
            stopped = "budget_exhausted"
            break
        timeout = min(step["timeout_seconds"], int(remaining))
        if step["backend"] == "smt":
            receipt = solve_statement(draft.statement, timeout_ms=timeout*1000)
        else:
            translation = translate_statement(draft.statement, step["strategy"])
            if translation.source_hash != step["translation_hash"]:
                raise ValueError("Lean source differs from committed proof plan")
            receipt = check_lean(translation, project=project, timeout=timeout).to_data()
        receipt = encode(receipt)
        _validate_receipt(receipt, step, draft.statement)
        status = receipt["status"]
        if status not in KNOWN_STATUSES:
            raise ValueError("Unknown backend status")
        attempts.append({"index": step["index"], "backend": step["backend"], "strategy": step["strategy"],
                         "status": status, "receipt": receipt, "receipt_content_id": fingerprint(receipt)})
        if status in TERMINAL:
            stopped = status
            break
    result = {"schema_version": 1, "plan_id": plan.content_id, "draft_id": draft.content_id,
              "review_id": review.to_data()["review_id"], "attempts": attempts, "stopped": stopped,
              "kernel_proved": any(item["backend"] == "lean" and item["status"] == "proved" for item in attempts),
              "scope": RUN_SCOPE}
    result = {**result, "run_id": fingerprint(result)}
    canonical_payload(result)
    return result


def _validate_receipt(receipt, planned, statement):
    if not isinstance(receipt, dict) or receipt.get("statement_id") != statement.content_id:
        raise ValueError("Backend receipt has no matching statement")
    status = receipt.get("status")
    if "receipt_id" in receipt and receipt["receipt_id"] != fingerprint({k: v for k, v in receipt.items() if k != "receipt_id"}):
        raise ValueError("Backend receipt content commitment mismatch")
    if planned["backend"] == "smt":
        if status not in {"unsat", "counterexample", "inconsistent_assumptions", "unsupported", "unavailable", "unknown", "replay_failed"}:
            raise ValueError("Status does not belong to SMT backend")
        if receipt.get("backend") != "z3" or receipt.get("formal_proof") is not False:
            raise ValueError("SMT receipt may not claim a Lean kernel proof")
        if "statement" in receipt and canonical_payload(receipt["statement"]) != canonical_payload(statement.to_data()):
            raise ValueError("SMT receipt statement differs from committed statement")
        if "query_hash" in receipt and receipt["query_hash"] != fingerprint({"query": receipt.get("query")}):
            raise ValueError("SMT query commitment mismatch")
        if status == "counterexample":
            witness = receipt.get("witness")
            if not isinstance(witness, dict) or set(witness) != set(statement.variables) or receipt.get("exact_replay") is not True:
                raise ValueError("Complete exact counterexample required")
            values = {name: rational(value) for name, value in witness.items()}
            if not all(predicate.evaluate(values) for predicate in statement.hypotheses) or statement.goal.evaluate(values):
                raise ValueError("Counterexample failed independent rational replay")
    else:
        if status not in {"proved", "unavailable", "failed", "timeout", "rejected_axioms", "translation_rejected"}:
            raise ValueError("Status does not belong to Lean backend")
        if (receipt.get("backend") != "lean4" or receipt.get("source_hash") != planned["translation_hash"]
                or receipt.get("formal_proof") is not (status == "proved")):
            raise ValueError("Lean receipt source or proof flag mismatch")
        if status == "proved":
            from .lean_checker import ALLOWED_AXIOMS
            axioms = receipt.get("axioms")
            if not isinstance(axioms, list) or not set(axioms) <= ALLOWED_AXIOMS:
                raise ValueError("Unsupported Lean axioms")


def validate_run_structure(run, draft, review, plan):
    """Validate record bindings only; a true return is not a verified theorem."""
    _require_current_plan(draft, review, plan)
    fields = {"schema_version", "plan_id", "draft_id", "review_id", "attempts", "stopped",
              "kernel_proved", "scope", "run_id"}
    require_fields(run, fields)
    if (type(run["schema_version"]) is not int or run["schema_version"] != 1
            or run["plan_id"] != plan.content_id or run["draft_id"] != draft.content_id
            or run["review_id"] != review.to_data()["review_id"] or run["scope"] != RUN_SCOPE):
        raise ValueError("Proof run binding mismatch")
    expected_id = fingerprint({key: value for key, value in run.items() if key != "run_id"})
    if run["run_id"] != expected_id:
        raise ValueError("Proof run content mismatch")
    if not isinstance(run["attempts"], list) or len(run["attempts"]) > len(plan.to_data()["attempts"]):
        raise ValueError("Invalid proof attempt records")
    for recorded, planned in zip(run["attempts"], plan.to_data()["attempts"]):
        require_fields(recorded, {"index", "backend", "strategy", "status", "receipt", "receipt_content_id"})
        if (type(recorded["index"]) is not int or recorded["index"] != planned["index"]
                or recorded["backend"] != planned["backend"] or recorded["strategy"] != planned["strategy"]
                or recorded["status"] not in KNOWN_STATUSES
                or not isinstance(recorded["receipt"], dict)
                or recorded["receipt"].get("status") != recorded["status"]
                or recorded["receipt"].get("statement_id") != draft.statement.content_id
                or fingerprint(recorded["receipt"]) != recorded["receipt_content_id"]):
            raise ValueError("Proof attempt metadata mismatch")
        _validate_receipt(recorded["receipt"], planned, draft.statement)
    if any(row["status"] in TERMINAL for row in run["attempts"][:-1]):
        raise ValueError("Proof portfolio continued after a terminal outcome")
    if run["stopped"] not in TERMINAL | {"checkpoint", "budget_exhausted", "portfolio_exhausted"}:
        raise ValueError("Unknown proof search termination")
    if run["attempts"] and run["attempts"][-1]["status"] in TERMINAL and run["stopped"] != run["attempts"][-1]["status"]:
        raise ValueError("Terminal outcome does not match termination record")
    if run["stopped"] in TERMINAL and (not run["attempts"] or run["attempts"][-1]["status"] != run["stopped"]):
        raise ValueError("Terminal termination requires a matching terminal attempt")
    if run["stopped"] == "portfolio_exhausted" and len(run["attempts"]) != len(plan.to_data()["attempts"]):
        raise ValueError("Portfolio exhaustion requires every planned attempt")
    if run["stopped"] == "checkpoint" and not 0 < len(run["attempts"]) < len(plan.to_data()["attempts"]):
        raise ValueError("Checkpoint requires a nonempty proper prefix")
    if type(run["kernel_proved"]) is not bool or run["kernel_proved"] != any(
            row["backend"] == "lean" and row["status"] == "proved" for row in run["attempts"]):
        raise ValueError("Kernel proof flag inconsistent with attempt metadata")
    canonical_payload(run)
    return True


def replay_proof_run(run, draft, review, plan, *, project=Path("lean")):
    """Reexecute backends, comparing semantic outcomes rather than solver traces."""
    try:
        validate_run_structure(run, draft, review, plan)
        stop_after = len(run["attempts"]) if run["stopped"] == "checkpoint" else None
        fresh = execute_proof_plan(draft, review, plan, project=project, stop_after=stop_after)
        old_outcomes = [(item["backend"], item["strategy"], item["status"]) for item in run["attempts"]]
        new_outcomes = [(item["backend"], item["strategy"], item["status"]) for item in fresh["attempts"]]
        axioms_match = all(old["receipt"].get("axioms") == new["receipt"].get("axioms")
                           for old, new in zip(run["attempts"], fresh["attempts"]) if old["backend"] == "lean")
        return (old_outcomes == new_outcomes and run["stopped"] == fresh["stopped"]
                and run["kernel_proved"] == fresh["kernel_proved"] and axioms_match)
    except (ValueError, TypeError, KeyError, PermissionError, ArithmeticError):
        return False
