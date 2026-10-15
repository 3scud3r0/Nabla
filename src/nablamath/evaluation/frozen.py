"""Frozen exact-task evaluation of data-only submissions against a fixed baseline.

No candidate callbacks or code run here. Operator separation and secrecy require
external access controls; this in-process API is not a sandbox or private holdout.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..core.semantic_contracts import canonical_payload, load_json, require_fields, require_text
from ..core.semantic_ir import ScientificTask, fingerprint, rational
from ..verification.independence import IndependencePolicy
from ..verify import verify
from .statistics import wilson_interval
from .lineage import audit_lineage

VERSION = "frozen-exact-evaluator-v1"
FIELDS = {"schema_version", "evaluator", "policy", "actors", "tasks", "lineage", "baseline"}


def _predictions(rows, tasks):
    if not isinstance(rows, list) or len(rows) != len(tasks):
        raise ValueError("Exactly one prediction per frozen task required")
    predictions = {}
    for row in rows:
        require_fields(row, {"task_id", "values"})
        key, values = row["task_id"], row["values"]
        if not isinstance(key, str) or key not in tasks or key in predictions:
            raise ValueError("Unknown or duplicate prediction task")
        if not isinstance(values, list) or not 1 <= len(values) <= 33:
            raise ValueError("Expected bounded rational prediction vector")
        if any(not isinstance(value, str) for value in values):
            raise ValueError("Predictions must use exact rational strings")
        predictions[key] = tuple(rational(value) for value in values)
    return predictions


def _validate(data):
    require_fields(data, FIELDS)
    if (type(data["schema_version"]) is not int or data["schema_version"] != 1
            or data["evaluator"] != VERSION):
        raise ValueError("Unsupported frozen evaluator version")
    require_text(data["policy"], "predeclared evaluation policy")
    require_fields(data["actors"], {"proposer", "solver", "evaluator", "reviewer"})
    IndependencePolicy(**data["actors"])
    rows = data["tasks"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 256:
        raise ValueError("Evaluation requires 1 to 256 frozen tasks")
    tasks = {}
    for row in rows:
        task = ScientificTask.from_data(row)
        if task.family == "linear_system":
            from ..math.linear_algebra.matrices import Matrix
            if not Matrix(task.matrix).determinant():
                raise ValueError("Frozen linear tasks require a unique solution")
        if task.content_id in tasks:
            raise ValueError("Duplicate evaluation task")
        tasks[task.content_id] = task
    if not isinstance(data["lineage"], list):
        raise ValueError("Declared train/test lineage required")
    lineage = audit_lineage(data["lineage"])
    if not lineage["clean"]:
        raise ValueError("Declared train/test contamination")
    test_ids = {row["id"] for row in lineage["manifest"] if row["split"] == "test"}
    if not any(row["split"] == "train" for row in lineage["manifest"]):
        raise ValueError("Explicit training lineage required for contamination audit")
    if test_ids != set(tasks):
        raise ValueError("Lineage must cover exactly the frozen test tasks")
    _predictions(data["baseline"], tasks)
    return tasks, lineage


@dataclass(frozen=True)
class FrozenEvaluation:
    protocol_json: str

    def __post_init__(self):
        data = load_json(self.protocol_json)
        _validate(data)
        object.__setattr__(self, "protocol_json", canonical_payload(data))

    @classmethod
    def freeze(cls, *, tasks, lineage, baseline, policy, actors: IndependencePolicy):
        if not isinstance(actors, IndependencePolicy):
            raise ValueError("Explicit actor separation policy required")
        if not isinstance(tasks, (list, tuple)) or not 1 <= len(tasks) <= 256:
            raise ValueError("Expected bounded task collection")
        if any(not isinstance(task, ScientificTask) for task in tasks):
            raise ValueError("Expected scientific tasks")
        _predictions(baseline, {task.content_id: task for task in tasks})
        return cls(canonical_payload({"schema_version": 1, "evaluator": VERSION,
                   "policy": policy, "actors": actors.to_data(),
                   "tasks": sorted((task.to_data() for task in tasks), key=fingerprint),
                   "lineage": audit_lineage(lineage)["manifest"],
                   "baseline": sorted(baseline, key=lambda row: row["task_id"])}))

    @property
    def protocol_id(self):
        return fingerprint(load_json(self.protocol_json))

    def to_json(self):
        return canonical_payload({**load_json(self.protocol_json), "protocol_id": self.protocol_id})

    @classmethod
    def from_json(cls, raw, *, expected_id):
        from ..core.semantic_contracts import require_digest
        require_digest(expected_id)
        data = load_json(raw)
        require_fields(data, FIELDS | {"protocol_id"})
        identifier = data.pop("protocol_id")
        result = cls(canonical_payload(data))
        if result.protocol_id != identifier or result.protocol_id != expected_id:
            raise ValueError("Frozen protocol commitment mismatch")
        return result

    def evaluate(self, submission: dict) -> dict:
        # Requiring the expected commitment also on submissions prevents accidental
        # scoring against a different task cohort or baseline.
        require_fields(submission, {"protocol_id", "predictions"})
        if submission["protocol_id"] != self.protocol_id:
            raise ValueError("Submission targets a different protocol")
        canonical_payload(submission)
        data = load_json(self.protocol_json)
        tasks, lineage = _validate(data)
        candidate = _predictions(submission["predictions"], tasks)
        baseline = _predictions(data["baseline"], tasks)
        scores = [{"task_id": key,
                   "candidate": verify(task, candidate[key]).valid,
                   "baseline": verify(task, baseline[key]).valid}
                  for key, task in sorted(tasks.items())]
        candidate_correct = sum(row["candidate"] for row in scores)
        baseline_correct = sum(row["baseline"] for row in scores)
        wins = sum(row["candidate"] and not row["baseline"] for row in scores)
        losses = sum(row["baseline"] and not row["candidate"] for row in scores)
        report = {"schema_version": 1, "evaluator": VERSION,
                  "protocol_id": self.protocol_id, "submission_id": fingerprint(submission),
                  "count": len(scores), "candidate_correct": candidate_correct,
                  "baseline_correct": baseline_correct, "wins": wins, "losses": losses,
                  "ties": len(scores)-wins-losses, "scores": scores,
                  "candidate_wilson95": list(wilson_interval(candidate_correct, len(scores))),
                  "baseline_wilson95": list(wilson_interval(baseline_correct, len(scores))),
                  "lineage_manifest_id": lineage["manifest_id"],
                  "decision": "descriptive_only",
                  "limitations": ["Declared lineage only; undeclared equivalence may remain",
                                  "Wilson intervals assume independent Bernoulli trials; not established here",
                                  "No authenticated identities, private holdout or process isolation",
                                  "No external generalization or training gain demonstrated"]}
        return {**report, "report_id": fingerprint(report)}

    def verify_report(self, report: dict, submission: dict) -> bool:
        try:
            return canonical_payload(self.evaluate(submission)) == canonical_payload(report)
        except (ValueError, KeyError, TypeError, ArithmeticError):
            return False
