"""Exact binary reliability bins, Brier score and expected calibration error."""
from fractions import Fraction

from ..core.semantic_ir import rational, fingerprint
from ..core.semantic_contracts import canonical_payload


def calibration_report(probabilities, outcomes, *, bins=10):
    if (not isinstance(probabilities, (list, tuple)) or not isinstance(outcomes, (list, tuple))
            or not 1 <= len(probabilities) == len(outcomes) <= 10000
            or type(bins) is not int or not 1 <= bins <= 100):
        raise ValueError("Bounded equal-length observations and 1–100 bins required")
    values = [rational(value) for value in probabilities]
    if any(not 0 <= value <= 1 for value in values) or any(type(y) is not bool for y in outcomes):
        raise ValueError("Exact probabilities in [0,1] and boolean outcomes required")
    groups = [[] for _ in range(bins)]
    for p, y in zip(values, outcomes):
        groups[min(bins-1, int(p*bins))].append((p, y))
    rows, ece = [], Fraction()
    for index, group in enumerate(groups):
        n = len(group)
        confidence = sum((p for p, _ in group), Fraction()) / n if n else None
        observed = Fraction(sum(y for _, y in group), n) if n else None
        if n:
            ece += Fraction(n, len(values)) * abs(confidence-observed)
        rows.append({"index": index, "count": n,
                     "mean_probability": str(confidence) if n else None,
                     "observed_frequency": str(observed) if n else None})
    report = {"schema_version": 1, "count": len(values), "bins": rows,
              "brier": str(sum(((p-int(y))**2 for p, y in zip(values, outcomes)), Fraction()) / len(values)),
              "ece": str(ece), "input_id": fingerprint({"probabilities": [str(p) for p in values], "outcomes": list(outcomes)}),
              "scope": "binary descriptive calibration on supplied observations; no external generalization claim"}
    return {**report, "report_id": fingerprint(report)}


def verify_calibration(report, probabilities, outcomes, *, bins=10):
    try:
        return canonical_payload(report) == canonical_payload(calibration_report(probabilities, outcomes, bins=bins))
    except (ValueError, TypeError, ArithmeticError):
        return False
