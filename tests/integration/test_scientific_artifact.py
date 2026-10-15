"""Real cycle replay, rehashed semantic forgeries and atomic persistence."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from nablamath.core.scientific_artifact import ArtifactNode, ScientificArtifact
from nablamath.core.semantic_ir import fingerprint
from nablamath.pipeline.artifact_store import ScientificArtifactStore
from nablamath.pipeline.scientific_cycle import build_scientific_artifact, replay_scientific_artifact


def cycle(family="linear_system", seed=42):
    return build_scientific_artifact(family=family, seed=seed, license_id="MIT", provenance="synthetic test")


def rehash_graph(artifact, target_kind, mutate):
    """Rebuild every downstream hash so rejection cannot rely on stale digests."""
    remaining = {n.content_id: n for n in artifact.nodes}
    rebuilt, identifiers = [], {}
    while remaining:
        for key, node in list(remaining.items()):
            if all(parent in identifiers for parent in node.parents):
                payload = node.payload
                if node.kind == target_kind:
                    mutate(payload)
                replacement = ArtifactNode.create(node.kind, node.algorithm, payload,
                                                   tuple(identifiers[p] for p in node.parents))
                identifiers[key] = replacement.content_id
                rebuilt.append(replacement)
                del remaining[key]
    return replace(artifact, nodes=tuple(rebuilt), roots=tuple(identifiers[r] for r in artifact.roots))


@pytest.mark.parametrize("family", ["linear_system", "polynomial_integral"])
@pytest.mark.parametrize("seed", [0, 42, 951017])
def test_cycle_roundtrip_and_semantic_replay(family, seed):
    artifact = cycle(family, seed)
    assert ScientificArtifact.from_json(artifact.to_json()) == artifact
    assert cycle(family, seed) == artifact
    assert replace(artifact, nodes=tuple(reversed(artifact.nodes))) == artifact
    report = replay_scientific_artifact(artifact)
    assert report["valid"] and report["replayed_nodes"] == 7
    assert not report["formal_proof"] and not report["empirical_validation"]
    assert {n.kind for n in artifact.nodes} == {
        "request", "problem", "solution", "verification", "dataset", "figure", "document"}
    # Independent analytic checks on the actual solution, outside hash comparison.
    problem = next(n.payload for n in artifact.nodes if n.kind == "problem")
    values = next(n.payload["values"] for n in artifact.nodes if n.kind == "solution")
    from fractions import Fraction as F
    values = list(map(F, values))
    if family == "linear_system":
        assert all(sum(F(a) * x for a, x in zip(row, values)) == F(b)
                   for row, b in zip(problem["matrix"], problem["rhs"]))
    else:
        assert [F(i) * values[i] for i in range(1, len(values))] == list(map(F, problem["coefficients"]))


@pytest.mark.parametrize("kind,mutate", [
    ("request", lambda p: p.update(seed=43)),
    ("problem", lambda p: p["rhs"].__setitem__(0, "999")),
    ("solution", lambda p: p["values"].__setitem__(0, "999")),
    ("verification", lambda p: p.update(formal_proof=True)),
    ("dataset", lambda p: p.update(split="invalid")),
    ("figure", lambda p: p.update(svg="<svg>forged</svg>")),
    ("document", lambda p: p.update(html="<p>forged result</p>")),
])
def test_every_rehashed_link_is_rejected(kind, mutate):
    forged = rehash_graph(cycle(), kind, mutate)
    # The forged object is structurally valid and its new digest is consistent.
    restored = ScientificArtifact.from_json(forged.to_json())
    with pytest.raises(ValueError, match="replay mismatch"):
        replay_scientific_artifact(restored)


def test_unknown_algorithms_and_metadata_are_not_silently_accepted():
    artifact = cycle()
    for forged in [replace(artifact, source="other"), replace(artifact, license_id="other"),
                   replace(artifact, statement="all science proven")]:
        with pytest.raises(ValueError):
            replay_scientific_artifact(forged)
    forged = rehash_graph(artifact, "request", lambda p: p.update(extra="field"))
    with pytest.raises(ValueError):
        replay_scientific_artifact(forged)
    standalone = ArtifactNode.create("request", "unsupported", {})
    with pytest.raises(ValueError):
        replay_scientific_artifact(replace(artifact, nodes=(standalone,), roots=(standalone.content_id,)))


def test_malformed_graph_and_snapshot_immutability():
    payload = {"nested": [1]}
    node = ArtifactNode.create("input", "test-v1", payload)
    payload["nested"][0] = 999
    node.payload["nested"].append(2)
    assert node.payload == {"nested": [1]}
    artifact = ScientificArtifact("test", "synthetic", "MIT", (node,), (node.content_id,))
    for changes in [dict(roots=("0" * 64,)), dict(nodes=(node, node)), dict(schema_version=True),
                    dict(roots=(node.content_id, node.content_id))]:
        with pytest.raises(ValueError):
            replace(artifact, **changes)
    child = ArtifactNode.create("output", "test-v1", {}, ("0" * 64,))
    with pytest.raises(ValueError):
        replace(artifact, nodes=(child,), roots=(child.content_id,))
    unrelated = ArtifactNode.create("input", "test-v1", {"other": 1})
    with pytest.raises(ValueError):
        replace(artifact, nodes=(node, unrelated))
    data = json.loads(artifact.to_json())
    data["statement"] = "altered"
    with pytest.raises(ValueError, match="digest mismatch"):
        ScientificArtifact.from_json(json.dumps(data))
    data["content_id"] = fingerprint({k: v for k, v in data.items() if k != "content_id"})
    assert ScientificArtifact.from_json(json.dumps(data)).statement == "altered"


def test_store_roundtrip_idempotence_corruption_and_failed_transaction():
    with tempfile.TemporaryDirectory() as root:
        store = ScientificArtifactStore(Path(root))
        artifact = cycle()
        digest = store.put(artifact)
        assert store.put(artifact) == digest
        assert store.get(digest) == artifact
        before = sorted(Path(root).rglob("*"))
        forged = rehash_graph(artifact, "solution", lambda p: p.update(values=["0"]))
        with pytest.raises(ValueError):
            store.put(forged)
        assert sorted(Path(root).rglob("*")) == before
        path = Path(root) / digest[:2] / digest
        path.write_bytes(b"corrupt")
        with pytest.raises(ValueError, match="corrompido"):
            store.get(digest)


def test_rejected_solver_output_never_produces_artifact():
    with patch("nablamath.pipeline.scientific_cycle.solve", return_value=(0, 0, 0)):
        with pytest.raises(ValueError, match="verifier rejected"):
            cycle()


def test_cli_build_check_failure_and_existing_file(tmp_path, capsys):
    from nablamath.cli import main
    target = tmp_path / "artifact.json"
    arguments = ["artifact", str(target), "--license", "MIT", "--provenance", "synthetic test"]
    assert main(arguments) == 0
    original = target.read_bytes()
    assert main(["check-artifact", str(target)]) == 0
    assert main(arguments) == 1
    assert target.read_bytes() == original
    forged = rehash_graph(ScientificArtifact.from_json(original.decode()), "solution",
                          lambda p: p.update(values=["0"]))
    target.write_text(forged.to_json(), encoding="utf-8")
    assert main(["check-artifact", str(target)]) == 1
    target.write_bytes(b"\xff")
    assert main(["check-artifact", str(target)]) == 1
    target.write_bytes(b" " * 1_000_001)
    assert main(["check-artifact", str(target)]) == 1
