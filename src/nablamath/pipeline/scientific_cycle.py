"""Finite exact-rational profile: Forge → solver → verifier → scene/data/report.

The profile is deliberately smaller than F1–F12. It does not execute supplied code,
contact services, infer novelty or claim formal/empirical validation.
"""
from __future__ import annotations

from ..calc.session import encode
from ..core.scientific_artifact import ArtifactNode, ScientificArtifact
from ..core.semantic_contracts import require_fields, require_text
from ..dataset.scientific import make_record, validate_record
from ..documents import Document, Section, to_html
from ..forge import generate
from ..graphics import task_scene, render_svg
from ..verify import solve, verify

PROFILE = "exact-rational-cycle-v1"


def build_scientific_artifact(*, family: str, seed: int, size: int = 3,
                              license_id: str, provenance: str) -> ScientificArtifact:
    require_text(license_id, "license_id")
    require_text(provenance, "provenance")
    generated = generate(family, seed, size)
    task = generated.task
    solution = solve(task)
    certificate = verify(task, solution)
    if not certificate.valid:
        raise ValueError("Independent verifier rejected solver output")
    request = ArtifactNode.create("request", PROFILE, {
        "family": family, "seed": seed, "size": size,
        "license_id": license_id, "provenance": provenance,
    })
    problem = ArtifactNode.create("problem", "scientific-task-v1", task.to_data(), (request.content_id,))
    answer = ArtifactNode.create("solution", "exact-solver-v1", {"values": [str(v) for v in solution]},
                                 (problem.content_id,))
    evidence = ArtifactNode.create("verification", "exact-certificate-v1", encode(certificate.to_data()),
                                   (problem.content_id, answer.content_id))
    record = make_record(task, solution, license_id=license_id, provenance=provenance, seed=seed)
    if not validate_record(record):
        raise ValueError("Dataset record failed semantic validation")
    dataset = ArtifactNode.create("dataset", "scientific-record-v1", encode(record),
                                  (problem.content_id, answer.content_id, evidence.content_id))
    scene = task_scene(task, solution)
    figure = ArtifactNode.create("figure", "task-scene-svg-v1",
                                 {"scene": encode(scene.to_data()), "svg": render_svg(scene)},
                                 (problem.content_id, answer.content_id))
    document = Document("Exact rational scientific cycle", (
        Section("Result", f"Task {task.content_id}; solution: {', '.join(str(v) for v in solution)}"),
        Section("Evidence", f"Independent exact-instance check: {certificate.valid}. Dataset: {dataset.content_id}. Figure: {figure.content_id}."),
        Section("Limitations", "Synthetic rational instances only. No formal proof, empirical validation, novelty or training gain demonstrated."),
    ))
    report = ArtifactNode.create("document", "cycle-html-v1", {"html": to_html(document)},
                                 (dataset.content_id, figure.content_id, evidence.content_id))
    return ScientificArtifact(
        statement=f"Verified synthetic {family} instance; exact-rational profile v1",
        source=provenance, license_id=license_id,
        nodes=(request, problem, answer, evidence, dataset, figure, report), roots=(report.content_id,),
    )


def replay_scientific_artifact(artifact: ScientificArtifact) -> dict:
    if not isinstance(artifact, ScientificArtifact):
        raise ValueError("Expected ScientificArtifact")
    requests = [n for n in artifact.nodes if n.kind == "request"]
    if len(requests) != 1 or requests[0].algorithm != PROFILE or requests[0].parents:
        raise ValueError("Unsupported replay profile")
    parameters = requests[0].payload
    require_fields(parameters, {"family", "seed", "size", "license_id", "provenance"})
    expected = build_scientific_artifact(**parameters)
    if expected != artifact:
        raise ValueError("Semantic replay mismatch")
    return {"profile": PROFILE, "artifact_id": artifact.content_id,
            "replayed_nodes": len(artifact.nodes), "valid": True,
            "formal_proof": False, "empirical_validation": False,
            "external_review": False}
