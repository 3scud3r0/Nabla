"""Paired data-only variants on one committed evaluator, without model execution."""
from ..core.semantic_contracts import canonical_payload, require_text
from ..core.semantic_ir import fingerprint
from .frozen import FrozenEvaluation


def compare_ablations(protocol: FrozenEvaluation, submissions: dict, *, control="all"):
    if (not isinstance(protocol, FrozenEvaluation) or not isinstance(submissions, dict)
            or not 2 <= len(submissions) <= 32 or control not in submissions):
        raise ValueError("One frozen protocol, control and 2–32 variants required")
    for name in submissions:
        require_text(name, "variant", limit=128)
    reports = {name: protocol.evaluate(submissions[name]) for name in sorted(submissions)}
    comparisons = {}
    for name, report in reports.items():
        if name == control:
            continue
        pairs = list(zip(reports[control]["scores"], report["scores"]))
        wins = sum(b["candidate"] and not a["candidate"] for a, b in pairs)
        losses = sum(a["candidate"] and not b["candidate"] for a, b in pairs)
        comparisons[name] = {"wins": wins, "losses": losses, "ties": len(pairs)-wins-losses}
    result = {"schema_version": 1, "protocol_id": protocol.protocol_id, "control": control,
              "reports": reports, "comparisons": comparisons, "selection_performed": False,
              "scope": "declared variants; interventions and equal training budgets are not authenticated"}
    report = {**result, "report_id": fingerprint(result)}
    canonical_payload(report)
    return report


def verify_ablations(report, protocol, submissions, *, control="all"):
    try:
        return canonical_payload(report) == canonical_payload(compare_ablations(protocol, submissions, control=control))
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return False
