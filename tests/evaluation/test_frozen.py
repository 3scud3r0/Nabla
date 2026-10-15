from dataclasses import replace
import copy
import json

import pytest

from nablamath.core.semantic_contracts import canonical_payload
from nablamath.core.semantic_ir import ScientificTask, fingerprint
from nablamath.evaluation.statistics import wilson_interval
from nablamath.evaluation.frozen import FrozenEvaluation
from nablamath.verification.independence import IndependencePolicy


def fixture():
    linear = ScientificTask("linear_system", matrix=((1,),), rhs=(1,))
    integral = ScientificTask("polynomial_integral", coefficients=(2,))
    other = ScientificTask("linear_system", matrix=((1,),), rhs=(5,))
    tasks = [linear, integral, other]
    lineage = [{"id": task.content_id, "split": "test", "parents": [], "groups": {}} for task in tasks]
    lineage.append({"id": "training-corpus", "split": "train", "parents": [], "groups": {}})
    baseline = [{"task_id": task.content_id, "values": values}
                for task, values in zip(tasks, [["1"], ["0", "0"], ["0"]])]
    protocol = FrozenEvaluation.freeze(tasks=tasks, lineage=lineage, baseline=baseline,
                policy="Predeclared exact correctness on three synthetic tasks; descriptive only",
                actors=IndependencePolicy("proposer", "solver", "evaluator", "reviewer"))
    submission = {"protocol_id": protocol.protocol_id,
                  "predictions": [{"task_id": task.content_id, "values": values}
                                  for task, values in zip(tasks, [["0"], ["99", "2"], ["0"]])]}
    return protocol, submission


def test_paired_scores_and_independent_polynomial_identity():
    protocol, submission = fixture()
    report = protocol.evaluate(submission)
    assert report["count"] == 3
    assert report["candidate_correct"] == report["baseline_correct"] == 1
    assert (report["wins"], report["losses"], report["ties"]) == (1, 1, 1)
    assert report["decision"] == "descriptive_only"
    assert protocol.verify_report(report, submission)
    # An arbitrary additive constant is mathematically valid, not a label mismatch.
    integral = ScientificTask("polynomial_integral", coefficients=(2,))
    assert next(row for row in report["scores"] if row["task_id"] == integral.content_id)["candidate"]
    assert FrozenEvaluation.from_json(protocol.to_json(), expected_id=protocol.protocol_id) == protocol


def test_snapshot_immutability_and_deterministic_replay():
    protocol, submission = fixture()
    before = protocol.to_json()
    report = protocol.evaluate(submission)
    submission["predictions"][0]["values"][0] = "100"
    assert protocol.to_json() == before
    assert not protocol.verify_report(report, submission)
    assert fixture()[0] == protocol


@pytest.mark.parametrize("mutate", [
    lambda s: s.update(protocol_id="0"*64),
    lambda s: s["predictions"].pop(),
    lambda s: s["predictions"].append(copy.deepcopy(s["predictions"][0])),
    lambda s: s["predictions"][0].update(task_id="0"*64),
    lambda s: s["predictions"][0].update(values=[]),
    lambda s: s["predictions"][0].update(values=[True]),
    lambda s: s["predictions"][0].update(values=["1/0"]),
    lambda s: s["predictions"][0].update(values=["9"*1000]),
    lambda s: s["predictions"][0].update(code="raise RuntimeError"),
    lambda s: s.update(callback="untrusted"),
])
def test_reject_unknown_incomplete_or_executable_submissions(mutate):
    protocol, submission = fixture()
    mutate(submission)
    with pytest.raises((ValueError, ArithmeticError)):
        protocol.evaluate(submission)


@pytest.mark.parametrize("field,value", [
    ("count", 300), ("candidate_correct", 3), ("wins", 3),
    ("candidate_wilson95", [1.0, 1.0]), ("decision", "scientific_gain_proven"),
])
def test_rehashed_false_reports_are_rejected(field, value):
    protocol, submission = fixture()
    report = protocol.evaluate(submission)
    report[field] = value
    report["report_id"] = fingerprint({k: v for k, v in report.items() if k != "report_id"})
    assert not protocol.verify_report(report, submission)


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(schema_version=True),
    lambda d: d.update(evaluator="arbitrary-python-code"),
    lambda d: d["tasks"].append(d["tasks"][0]),
    lambda d: d["lineage"].pop(),
    lambda d: d["actors"].update(evaluator=d["actors"]["proposer"]),
    lambda d: d["baseline"].pop(),
    lambda d: d["tasks"].__setitem__(0, ScientificTask("linear_system", matrix=((0,),), rhs=(1,)).to_data()),
])
def test_reject_malformed_protocols(mutate):
    protocol, _ = fixture()
    data = json.loads(protocol.protocol_json)
    mutate(data)
    with pytest.raises(ValueError):
        FrozenEvaluation(canonical_payload(data))


def test_precommitted_protocol_cannot_be_replaced_even_with_new_hash():
    protocol, _ = fixture()
    data = json.loads(protocol.protocol_json)
    data["policy"] = "Changed after observing outcomes"
    forged = FrozenEvaluation(canonical_payload(data))
    with pytest.raises(ValueError, match="commitment mismatch"):
        FrozenEvaluation.from_json(forged.to_json(), expected_id=protocol.protocol_id)


@pytest.mark.parametrize("kind", ["parents", "template", "source"])
def test_transitive_train_test_leakage_through_external_ancestor_or_group(kind):
    protocol, _ = fixture()
    data = json.loads(protocol.protocol_json)
    train = next(row for row in data["lineage"] if row["split"] == "train")
    test = next(row for row in data["lineage"] if row["split"] == "test")
    for row in [train, test]:
        if kind == "parents":
            row["parents"] = ["external-shared-ancestor"]
        else:
            row["groups"] = {kind: ["shared-group"]}
    with pytest.raises(ValueError, match="contamination"):
        FrozenEvaluation(canonical_payload(data))


def test_wilson_known_boundary_and_bad_counts():
    low, high = wilson_interval(0, 10)
    assert low == pytest.approx(0, abs=1e-15)
    assert high == pytest.approx(0.2775327998628892)
    low, high = wilson_interval(10, 10)
    assert low == pytest.approx(0.7224672001371107)
    assert high == pytest.approx(1)
    for successes, count in [(0, 0), (-1, 10), (11, 10), (True, 2), (1, True), (1, 10001)]:
        with pytest.raises(ValueError):
            wilson_interval(successes, count)


def test_cli_freeze_evaluate_and_replay_preserve_outputs(tmp_path, capsys):
    from nablamath.cli import main
    protocol, submission = fixture()
    spec = tmp_path / "spec.json"
    spec.write_text(protocol.protocol_json, encoding="utf-8")
    frozen = tmp_path / "protocol.json"
    answers = tmp_path / "answers.json"
    answers.write_text(canonical_payload(submission), encoding="utf-8")
    report = tmp_path / "report.json"
    assert main(["freeze-evaluation", str(spec), str(frozen)]) == 0
    original = frozen.read_bytes()
    assert main(["freeze-evaluation", str(spec), str(frozen)]) == 1
    assert frozen.read_bytes() == original
    arguments = ["evaluate-frozen", str(frozen), str(answers), "--expected-id", protocol.protocol_id,
                 "--output", str(report)]
    assert main(arguments) == 0
    original = report.read_bytes()
    assert main(arguments) == 1
    assert report.read_bytes() == original
    check = ["check-evaluation", str(frozen), str(answers), str(report), "--expected-id", protocol.protocol_id]
    assert main(check) == 0
    data = json.loads(original)
    data["candidate_correct"] = 3
    data["report_id"] = fingerprint({k: v for k, v in data.items() if k != "report_id"})
    report.write_text(canonical_payload(data), encoding="utf-8")
    assert main(check) == 1
    wrong = arguments.copy()
    wrong[wrong.index(protocol.protocol_id)] = "0"*64
    wrong[-1] = str(tmp_path / "must-not-exist.json")
    assert main(wrong) == 1
    assert not (tmp_path / "must-not-exist.json").exists()
