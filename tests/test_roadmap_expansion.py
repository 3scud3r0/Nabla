from fractions import Fraction as F
import hashlib
import random

import pytest

from nablamath.core.precision import RationalInterval as I
from nablamath.core.uncertainty import UncertainQuantity as U
from nablamath.core.units import METER, KILOMETER, SECOND
from nablamath.core.semantic_ir import fingerprint, ScientificTask
from nablamath.numeric.intervals import sqrt_enclosure, square, subtract, intersect
from nablamath.evaluation.calibration import calibration_report, verify_calibration
from nablamath.evaluation.ablation import compare_ablations, verify_ablations
from nablamath.evaluation.frozen import FrozenEvaluation
from nablamath.verification.independence import IndependencePolicy
from nablamath.knowledge.lineage import LineageGraph
from nablamath.knowledge.retraction_index import retraction_impact, verify_retraction_impact
from nablamath.training.snapshot import SnapshotStore
from nablamath.training.lineage import snapshot_lineage
from nablamath.training.mixture import plan_mixture, verify_mixture
from nablamath.training.compute_accounting import ComputeRecord
from nablamath.datasets.corpus_registry import CorpusManifest, CorpusRegistry


def digest(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def test_exact_interval_arithmetic_and_outward_square_roots():
    rng = random.Random(42)
    for _ in range(100):
        a, b = sorted([F(rng.randrange(100), rng.randrange(1, 30)) for _ in range(2)])
        bound = sqrt_enclosure(I(a, b), digits=8)
        assert bound.lower**2 <= a <= b <= bound.upper**2
        assert (bound.lower + F(1, 10**8))**2 > a
        assert (bound.upper - F(1, 10**8))**2 < b or b == 0
    assert sqrt_enclosure(I(4, 9)) == I(2, 3)
    assert square(I(-2, 3)) == I(0, 9)
    assert square(I(-3, -2)) == I(4, 9)
    assert subtract(I(1, 2), I(3, 4)) == I(-3, -1)
    assert intersect(I(1, 3), I(2, 4)) == I(2, 3)
    for value, digits in [(I(-1, 1), 8), (I(0, 1), True), (I(0, 1), 33)]:
        with pytest.raises(ValueError):
            sqrt_enclosure(value, digits=digits)
    with pytest.raises(ValueError):
        intersect(I(1, 2), I(3, 4))


def test_uncertainty_units_conversion_and_conservative_dependency():
    distance = U.around(1, "1/100", KILOMETER)
    addition = distance + U.around(2, 1, METER)
    assert addition.to(METER).interval == I(991, 1013)
    assert (distance - distance).interval == I("-1/50", "1/50")
    speed = distance / U.around(2, 0, SECOND)
    assert speed.to(KILOMETER/SECOND).interval == I("99/200", "101/200")
    assert (U.around(2, 1) * U.around(3, 1)).interval == I(2, 12)
    for operation in [lambda: distance + U.around(1, 0, SECOND),
                      lambda: distance / U.around(0, 1), lambda: U.around(1, -1)]:
        with pytest.raises(ValueError):
            operation()


def test_calibration_exact_reference_empty_bins_and_rehashed_forgery():
    report = calibration_report(["1/4", "3/4"], [False, True], bins=2)
    assert report["brier"] == "1/16" and report["ece"] == "1/4"
    assert verify_calibration(report, ["1/4", "3/4"], [False, True], bins=2)
    boundary = calibration_report([0, 1], [False, True], bins=10)
    assert boundary["bins"][0]["count"] == boundary["bins"][-1]["count"] == 1
    assert boundary["bins"][1]["mean_probability"] is None
    assert boundary["brier"] == boundary["ece"] == "0"
    singleton = calibration_report([1], [True], bins=1)
    singleton["count"] = True
    assert not verify_calibration(singleton, [1], [True], bins=1)
    report["ece"] = "0"
    report["report_id"] = fingerprint({k: v for k, v in report.items() if k != "report_id"})
    assert not verify_calibration(report, ["1/4", "3/4"], [False, True], bins=2)


@pytest.mark.parametrize("probabilities,outcomes,bins", [([], [], 10), (["2"], [True], 10),
    ([0.5], [True], 10), ([1], [1], 10), ([1], [True], True), ([1], [], 10)])
def test_calibration_rejects_ambiguous_inputs(probabilities, outcomes, bins):
    with pytest.raises(ValueError):
        calibration_report(probabilities, outcomes, bins=bins)


def test_frozen_ablation_is_paired_without_selection():
    task = ScientificTask("linear_system", matrix=((2,),), rhs=(4,))
    base = [{"task_id": task.content_id, "values": ["0"]}]
    protocol = FrozenEvaluation.freeze(tasks=[task], baseline=base, policy="fixed test",
        actors=IndependencePolicy("a", "b", "c", "d"),
        lineage=[{"id": task.content_id, "split": "test", "parents": [], "groups": {}},
                 {"id": "train", "split": "train", "parents": [], "groups": {}}])
    good = {"protocol_id": protocol.protocol_id, "predictions": [{"task_id": task.content_id, "values": ["2"]}]}
    bad = {"protocol_id": protocol.protocol_id, "predictions": base}
    variants = {"all": good, "without_feature": bad}
    report = compare_ablations(protocol, variants)
    assert report["comparisons"]["without_feature"] == {"wins": 0, "losses": 1, "ties": 0}
    assert not report["selection_performed"] and verify_ablations(report, protocol, variants)
    report["selection_performed"] = True
    assert not verify_ablations(report, protocol, variants)
    with pytest.raises(ValueError):
        compare_ablations(protocol, {"missing-control": good, "other": bad})


def test_lineage_retractions_propagate_without_mutation():
    a, b, c, d = map(digest, "abcd")
    nodes = [{"id": a, "parents": []}, {"id": b, "parents": [a]},
             {"id": c, "parents": [b]}, {"id": d, "parents": []}]
    graph = LineageGraph.create(nodes)
    before = graph.to_data()
    assert graph.descendants(a) == tuple(sorted([b, c]))
    records = [{"target_id": a, "issuer": "declared operator", "reason": "bad calibration", "evidence_id": digest("evidence")}]
    report = retraction_impact(graph, records)
    assert {row["node_id"] for row in report["alerts"]} == {a, b, c}
    assert not report["historic_content_modified"] and verify_retraction_impact(report, graph, records)
    assert graph.to_data() == before
    report["alerts"].pop()
    assert not verify_retraction_impact(report, graph, records)
    with pytest.raises(ValueError):
        retraction_impact(graph, records*2)
    with pytest.raises(ValueError):
        LineageGraph.create(nodes + [{"id": a, "parents": []}])
    with pytest.raises(ValueError):
        LineageGraph.create([{"id": a, "parents": [b]}, {"id": b, "parents": [a]}])
    with pytest.raises(ValueError):
        LineageGraph.create([{"id": a, "parents": [b]}])


def test_long_lineage_does_not_require_recursive_traversal():
    ids = [digest(i) for i in range(1100)]
    graph = LineageGraph.create([{"id": key, "parents": [ids[i-1]] if i else []} for i, key in enumerate(ids)])
    assert len(graph.descendants(ids[0])) == 1099


def test_opaque_snapshots_verify_all_bytes_and_lineage(tmp_path):
    store = SnapshotStore(tmp_path)
    args = dict(weights=b"opaque, never executable", datasets={"train": b"record one"}, code_id=digest("code"), license_id="MIT")
    parent = store.capture(**args)
    assert store.capture(**args) == parent
    child = store.capture(**{**args, "weights": b"second"}, parents=[parent])
    graph = snapshot_lineage(store, [child])
    assert graph.descendants(parent) == (child,)
    manifest = store.get(child)
    manifest["license_id"] = "tampered caller copy"
    assert store.get(child)["license_id"] == "MIT"
    before = sorted(tmp_path.rglob("*"))
    with pytest.raises(ValueError):
        store.capture(**{**args, "code_id": "invalid"})
    assert sorted(tmp_path.rglob("*")) == before
    key = store.get(child)["datasets"]["train"]
    (tmp_path / key[:2] / key).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="corrompido"):
        store.get(child)


def corpus(name, records, split="train"):
    return CorpusManifest.create(name=name, license_id="MIT", provenance="synthetic fixture", split=split, records=records)


def test_corpus_mixture_exact_quotas_and_no_replacement(tmp_path):
    a, b = corpus("a", [digest(i) for i in range(10)]), corpus("b", [digest(i) for i in range(10, 20)])
    registry = CorpusRegistry(tmp_path)
    assert registry.get(registry.register(a)) == a
    weights = {a.content_id: 1, b.content_id: 3}
    report = plan_mixture([a, b], weights, count=8, seed=42)
    assert {row["source_id"]: row["count"] for row in report["allocations"]} == {a.content_id: 2, b.content_id: 6}
    assert len({row["record_id"] for row in report["selections"]}) == 8
    assert plan_mixture([b, a], weights, count=8, seed=42) == report
    assert verify_mixture(report, [a, b], weights, count=8, seed=42)
    report["allocations"][0]["count"] = 99
    assert not verify_mixture(report, [a, b], weights, count=8, seed=42)
    records = {digest(i): str(i).encode() for i in range(10)}
    assert a.verify_records(records)
    records[digest(0)] = b"bad"
    assert not a.verify_records(records)
    singleton = plan_mixture([a], {a.content_id: 1}, count=1, seed=42)
    singleton["count"] = True
    assert not verify_mixture(singleton, [a], {a.content_id: 1}, count=1, seed=42)


@pytest.mark.parametrize("case", ["overlap", "split", "capacity", "weight", "seed"])
def test_mixture_rejects_invalid_or_leaking_plans(case):
    a, b = corpus("a", [digest(1)]), corpus("b", [digest(2)])
    if case == "overlap":
        b = corpus("b", [digest(1)])
    if case == "split":
        b = corpus("b", [digest(2)], "test")
    weights = {a.content_id: 1, b.content_id: 1 if case != "weight" else 0}
    with pytest.raises(ValueError):
        plan_mixture([a, b], weights, count=10 if case == "capacity" else 2, seed=True if case == "seed" else 42)


def test_compute_measurements_do_not_invent_energy():
    record = ComputeRecord("declared CPU", "operator stopwatch", 100, 1024)
    assert record.to_data()["energy_joules"] is None
    assert ComputeRecord("CPU", "meter", 100, 0, "1/2").to_data()["energy_joules"] == "1/2"
    for args in [("", "method", 1, 0), ("CPU", "method", True, 0), ("CPU", "method", 1, -1), ("CPU", "method", 1, 0, "-1")]:
        with pytest.raises(ValueError):
            ComputeRecord(*args)
