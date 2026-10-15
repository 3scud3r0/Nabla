"""Declared retractions propagate review alerts, without rewriting historic claims."""
from .lineage import LineageGraph
from ..core.semantic_contracts import canonical_payload, require_fields, require_digest, require_text
from ..core.semantic_ir import fingerprint


def retraction_impact(graph: LineageGraph, retractions: list) -> dict:
    if not isinstance(graph, LineageGraph) or not isinstance(retractions, list) or len(retractions) > 1024:
        raise ValueError("Bounded graph and retraction records required")
    canonical_payload(retractions)
    known = {row["id"] for row in graph.to_data()["nodes"]}
    receipts, alerts = {}, {}
    for row in retractions:
        require_fields(row, {"target_id", "issuer", "reason", "evidence_id"})
        target = require_digest(row["target_id"])
        require_digest(row["evidence_id"])
        require_text(row["issuer"], "issuer", limit=256)
        require_text(row["reason"], "reason")
        if target not in known:
            raise ValueError("Retraction target absent from lineage")
        identifier = fingerprint(row)
        if identifier in receipts:
            raise ValueError("Duplicate retraction record")
        receipts[identifier] = dict(row)
        for node in (target, *graph.descendants(target)):
            alerts.setdefault(node, []).append(identifier)
    report = {"schema_version": 1, "lineage_id": graph.content_id,
              "retractions": [{"id": key, **receipts[key]} for key in sorted(receipts)],
              "alerts": [{"node_id": key, "requires_review": True, "retraction_ids": sorted(alerts[key])}
                         for key in sorted(alerts)], "historic_content_modified": False,
              "scope": "declared retractions and dependencies; issuer authenticity and scientific truth not established"}
    return {**report, "report_id": fingerprint(report)}


def verify_retraction_impact(report, graph, retractions):
    try:
        return canonical_payload(report) == canonical_payload(retraction_impact(graph, retractions))
    except (ValueError, TypeError, KeyError):
        return False
