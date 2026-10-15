import copy

import pytest

from nablamath.core.semantic_ir import ScientificTask, fingerprint
from nablamath.documents import Document, Section
from nablamath.documents.reference_graph import document_reference_graph
from nablamath.pipeline.scientific_cycle import build_scientific_artifact
from nablamath.evaluation.frozen import FrozenEvaluation
from nablamath.evolution.longitudinal_monitor import monitor_evaluations
from nablamath.verification.independence import IndependencePolicy
from nablamath.verification.consensus import receipt_consensus


def test_document_references_resolve_to_real_artifact_nodes():
    artifact = build_scientific_artifact(family="linear_system", seed=42, license_id="MIT", provenance="synthetic test")
    certificate = next(node for node in artifact.nodes if node.kind == "verification")
    document = Document("Report", (Section("Result", "Exact instance", evidence_ids=(certificate.content_id,)),))
    report = document_reference_graph(document, artifact)
    assert report["sections"][0]["evidence_ids"] == [certificate.content_id]
    assert any(row["id"] == document.content_id and certificate.content_id in row["parents"]
               for row in report["lineage"]["nodes"])
    for evidence_ids in [("0"*64,), (certificate.content_id, certificate.content_id), ("not-a-digest",)]:
        with pytest.raises(ValueError):
            document_reference_graph(Document("Report", (Section("Result", "text", evidence_ids=evidence_ids),)), artifact)


def test_receipt_quorum_is_distinct_and_does_not_establish_truth():
    expected = fingerprint({"exact": 2})
    receipts = [{"participant_id": "a", "result_id": expected},
                {"participant_id": "b", "result_id": expected},
                {"participant_id": "c", "result_id": "0"*64}]
    report = receipt_consensus(receipts, expected_result_id=expected)
    assert report["quorum_met"] and report["disagreeing"] == ["c"]
    assert not report["scientific_truth_established"]
    assert not receipt_consensus(receipts[:1], expected_result_id=expected)["quorum_met"]
    with pytest.raises(ValueError):
        receipt_consensus(receipts + [receipts[0]], expected_result_id=expected)
    with pytest.raises(ValueError):
        receipt_consensus(receipts, expected_result_id=expected, quorum=True)


def test_longitudinal_monitor_replays_fixed_cohort_and_flags_decline():
    task = ScientificTask("linear_system", matrix=((1,),), rhs=(1,))
    baseline = [{"task_id": task.content_id, "values": ["0"]}]
    protocol = FrozenEvaluation.freeze(tasks=[task], baseline=baseline, policy="fixed cohort",
        actors=IndependencePolicy("a", "b", "c", "d"),
        lineage=[{"id": task.content_id, "split": "test", "parents": [], "groups": {}},
                 {"id": "train", "split": "train", "parents": [], "groups": {}}])
    observations = []
    for step, value in enumerate(["1", "0", "1"]):
        submission = {"protocol_id": protocol.protocol_id, "predictions": [{"task_id": task.content_id, "values": [value]}]}
        observations.append({"step": step, "model_id": fingerprint({"model": step}),
                             "submission": submission, "report": protocol.evaluate(submission)})
    report = monitor_evaluations(protocol, observations)
    assert [row["regression"] for row in report["observations"]] == [False, True, False]
    assert [row["delta_previous"] for row in report["observations"]] == [None, "-1", "1"]
    assert not report["deployment_performed"]
    for mutate in [lambda rows: rows.reverse(), lambda rows: rows[1].update(model_id=rows[0]["model_id"]),
                   lambda rows: rows[1]["report"].update(candidate_correct=1)]:
        forged = copy.deepcopy(observations)
        mutate(forged)
        with pytest.raises(ValueError):
            monitor_evaluations(protocol, forged)
