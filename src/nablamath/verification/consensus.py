"""Receipt agreement against a caller-verified result; labels do not prove identity."""
from ..core.semantic_contracts import require_digest, require_fields, require_text
from ..core.semantic_ir import fingerprint


def receipt_consensus(receipts, *, expected_result_id, quorum=2):
    require_digest(expected_result_id)
    if (not isinstance(receipts, list) or len(receipts) > 1024
            or type(quorum) is not int or not 2 <= quorum <= 1024):
        raise ValueError("Bounded receipts and quorum of at least two required")
    participants, agreeing, disagreeing = set(), [], []
    for receipt in receipts:
        require_fields(receipt, {"participant_id", "result_id"})
        participant = require_text(receipt["participant_id"], "participant_id", limit=128)
        require_digest(receipt["result_id"])
        if participant in participants:
            raise ValueError("One receipt per distinct participant label required")
        participants.add(participant)
        (agreeing if receipt["result_id"] == expected_result_id else disagreeing).append(participant)
    report = {"schema_version": 1, "expected_result_id": expected_result_id, "quorum": quorum,
              "agreeing": sorted(agreeing), "disagreeing": sorted(disagreeing),
              "quorum_met": len(agreeing) >= quorum, "scientific_truth_established": False,
              "scope": "label agreement only; expected result must be independently verified; no Sybil resistance"}
    return {**report, "report_id": fingerprint(report)}
