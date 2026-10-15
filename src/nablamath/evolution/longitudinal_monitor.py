"""Replay a fixed cohort over declared ordered snapshots; do not select or deploy."""
from fractions import Fraction

from ..core.semantic_contracts import require_fields, require_digest
from ..core.semantic_ir import rational, fingerprint
from ..evaluation.frozen import FrozenEvaluation


def monitor_evaluations(protocol: FrozenEvaluation, observations: list, *, max_drop="0"):
    threshold = rational(max_drop)
    if (not isinstance(protocol, FrozenEvaluation) or not isinstance(observations, list)
            or not 1 <= len(observations) <= 128 or not 0 <= threshold <= 1):
        raise ValueError("Frozen protocol, bounded observations and drop threshold required")
    rows, previous, last_step, seen = [], None, -1, set()
    for observation in observations:
        require_fields(observation, {"step", "model_id", "submission", "report"})
        step, model_id = observation["step"], require_digest(observation["model_id"])
        if type(step) is not int or not last_step < step <= 10**12 or model_id in seen:
            raise ValueError("Strictly increasing steps and unique model IDs required")
        if not protocol.verify_report(observation["report"], observation["submission"]):
            raise ValueError("Observation failed frozen evaluator replay")
        report = observation["report"]
        accuracy = Fraction(report["candidate_correct"], report["count"])
        delta = accuracy-previous if previous is not None else None
        rows.append({"step": step, "model_id": model_id, "evaluation_id": report["report_id"],
                     "accuracy": str(accuracy), "delta_previous": str(delta) if delta is not None else None,
                     "regression": delta is not None and delta < -threshold})
        previous, last_step = accuracy, step
        seen.add(model_id)
    result = {"schema_version": 1, "protocol_id": protocol.protocol_id, "max_drop": str(threshold),
              "observations": rows, "deployment_performed": False,
              "scope": "declared snapshot order and replayed fixed cohort; no sustained external gain demonstrated"}
    return {**result, "report_id": fingerprint(result)}
