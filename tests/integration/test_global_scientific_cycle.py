"""Finite integrated profiles with explicit gaps; not acceptance of all F1–F12."""
import importlib.util
import math
from pathlib import Path

import pytest

from nablamath.core.semantic_ir import fingerprint
from nablamath.evaluation.frozen import FrozenEvaluation
from nablamath.evaluation.ablation import verify_ablations
from nablamath.knowledge.lineage import LineageGraph
from nablamath.knowledge.retraction_index import verify_retraction_impact
from nablamath.training.snapshot import SnapshotStore
from nablamath.training.lineage import snapshot_lineage

spec = importlib.util.spec_from_file_location("expanded_cycle", Path(__file__).resolve().parents[2] / "tools/expanded_scientific_cycle.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_reproducible_integrated_evidence_and_replay(tmp_path):
    first = module.run_cycle(tmp_path / "first")
    second = module.run_cycle(tmp_path / "second")
    assert first == second
    assert first["content_id"] == fingerprint(first["outputs"])
    outputs = first["outputs"]
    protocol = outputs["evaluation_protocol"]
    from nablamath.core.semantic_contracts import canonical_payload
    evaluation = FrozenEvaluation.from_json(canonical_payload(protocol), expected_id=protocol["protocol_id"])
    assert verify_ablations(outputs["ablations"], evaluation, outputs["submissions"])
    graph = LineageGraph.create(outputs["snapshot_lineage"]["nodes"])
    assert verify_retraction_impact(outputs["retraction_impact"], graph, outputs["retractions"])
    assert len(outputs["retraction_impact"]["alerts"]) == 2
    last = outputs["monitor"]["observations"][-1]
    assert last["regression"]
    assert snapshot_lineage(SnapshotStore(tmp_path / "first/snapshots"), [last["model_id"]]) == graph
    assert outputs["calibration"]["brier"] == "1/16"
    assert abs(outputs["simulation"]["final"][0] - math.exp(-1)) < 1e-6
    assert outputs["uncertainty"]["unit"]["dimensions"] == [0, 1, -1, 0, 0, 0, 0]
    assert outputs["limitations"]
    with pytest.raises(FileExistsError):
        module.run_cycle(tmp_path / "first")
