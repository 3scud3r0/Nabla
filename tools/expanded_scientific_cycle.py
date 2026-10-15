"""Reproduce bounded data/evidence workflows; fixture weights are never trained."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from nablamath.calc.session import encode
from nablamath.core.semantic_ir import ScientificTask, fingerprint
from nablamath.core.semantic_contracts import canonical_payload
from nablamath.core.uncertainty import UncertainQuantity
from nablamath.core.units import METER, SECOND
from nablamath.datasets.corpus_registry import CorpusManifest, CorpusRegistry
from nablamath.documents import Document, Section
from nablamath.documents.reference_graph import document_reference_graph
from nablamath.evaluation.ablation import compare_ablations, verify_ablations
from nablamath.evaluation.calibration import calibration_report
from nablamath.evaluation.frozen import FrozenEvaluation
from nablamath.evolution.longitudinal_monitor import monitor_evaluations
from nablamath.knowledge.retraction_index import retraction_impact
from nablamath.pipeline.scientific_cycle import build_scientific_artifact, replay_scientific_artifact
from nablamath.training.lineage import snapshot_lineage
from nablamath.training.mixture import plan_mixture
from nablamath.training.snapshot import SnapshotStore
from nablamath.verification.independence import IndependencePolicy
from nablamath.worlds import ModelSpec, simulate


def run_cycle(destination: Path):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    artifact = build_scientific_artifact(family="linear_system", seed=42, license_id="MIT", provenance="synthetic expanded fixture")
    replay_scientific_artifact(artifact)
    cert = next(node.content_id for node in artifact.nodes if node.kind == "verification")
    document = Document("Synthetic evidence cycle", (Section("Exact check", "Bounded instance only", evidence_ids=(cert,)),))
    references = document_reference_graph(document, artifact)
    corpora, payloads = [], {}
    registry = CorpusRegistry(destination / "corpora")
    for source in ("a", "b"):
        records = [canonical_payload({"synthetic_fixture": source, "record": i}).encode() for i in range(3)]
        by_digest = {hashlib.sha256(raw).hexdigest(): raw for raw in records}
        corpus = CorpusManifest.create(name=source, license_id="MIT", provenance="synthetic local fixture",
                                       split="train", records=list(by_digest))
        if not corpus.verify_records(by_digest):
            raise ValueError("Fixture corpus integrity failed")
        registry.register(corpus)
        corpora.append(corpus)
        payloads[source] = canonical_payload({key: raw.decode() for key, raw in by_digest.items()}).encode()
    mixture = plan_mixture(corpora, {corpus.content_id: 1 for corpus in corpora}, count=4, seed=42)
    store = SnapshotStore(destination / "snapshots")
    code_id = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    first = store.capture(weights=b"opaque fixture one; not trained", datasets=payloads, code_id=code_id, license_id="MIT")
    second = store.capture(weights=b"opaque fixture two; not trained", datasets=payloads, code_id=code_id, license_id="MIT", parents=[first])
    lineage = snapshot_lineage(store, [second])
    retractions = [{"target_id": first, "issuer": "fixture operator", "reason": "synthetic recall exercise", "evidence_id": artifact.content_id}]
    impact = retraction_impact(lineage, retractions)
    task = ScientificTask("linear_system", matrix=((1,),), rhs=(1,))
    baseline = [{"task_id": task.content_id, "values": ["0"]}]
    evaluation = FrozenEvaluation.freeze(tasks=[task], baseline=baseline, policy="Exact synthetic fixture; descriptive only",
        actors=IndependencePolicy("fixture proposer", "fixture solver", "fixture evaluator", "fixture reviewer"),
        lineage=[{"id": task.content_id, "split": "test", "parents": [], "groups": {}},
                 {"id": "declared fixture training corpus", "split": "train", "parents": [], "groups": {}}])
    good = {"protocol_id": evaluation.protocol_id, "predictions": [{"task_id": task.content_id, "values": ["1"]}]}
    bad = {"protocol_id": evaluation.protocol_id, "predictions": baseline}
    variants = {"all": good, "without_feature": bad}
    ablations = compare_ablations(evaluation, variants)
    if not verify_ablations(ablations, evaluation, variants):
        raise ValueError("Ablation replay failed")
    monitor = monitor_evaluations(evaluation, [
        {"step": 0, "model_id": first, "submission": good, "report": evaluation.evaluate(good)},
        {"step": 1, "model_id": second, "submission": bad, "report": evaluation.evaluate(bad)}])
    simulation = simulate(ModelSpec("exponential_decay", (1,), 1, 1), steps=20, method="rk4")
    uncertainty = (UncertainQuantity.around(10, 1, METER) / UncertainQuantity.around(2, "1/10", SECOND)).to_data()
    outputs = {"artifact": json.loads(artifact.to_json()), "document_references": references,
               "corpora": [corpus.to_data() for corpus in corpora], "mixture": mixture,
               "snapshot_lineage": lineage.to_data(), "retraction_impact": impact,
               "evaluation_protocol": json.loads(evaluation.to_json()), "ablations": ablations,
               "monitor": monitor, "calibration": calibration_report(["1/4", "3/4"], [False, True], bins=2),
               "simulation": encode(simulation), "uncertainty": uncertainty,
               "limitations": ["Synthetic fixtures, no trained model, no private holdout or authenticated reviewers",
                               "No observational validation, external discovery, federation or GPU validation"]}
    # Persist all evidence needed to replay evaluation and retraction reports.
    outputs["submissions"] = variants
    outputs["retractions"] = retractions
    result = {"schema_version": 1, "outputs": outputs, "content_id": fingerprint(outputs)}
    (destination / "summary.json").write_text(canonical_payload(result), encoding="utf-8")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    print(run_cycle(args.destination)["content_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
