"""Finite synthetic evaluation fixture; no trained model or external holdout."""
import argparse
from pathlib import Path

from nablamath.core.semantic_contracts import canonical_payload
from nablamath.core.semantic_ir import ScientificTask
from nablamath.evaluation.frozen import FrozenEvaluation
from nablamath.verification.independence import IndependencePolicy


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    tasks = [ScientificTask("linear_system", matrix=((1,),), rhs=(1,)),
             ScientificTask("polynomial_integral", coefficients=(2,))]
    lineage = [{"id": task.content_id, "split": "test", "parents": [], "groups": {}}
               for task in tasks]
    lineage.append({"id": "declared-unrelated-training-source", "split": "train", "parents": [], "groups": {}})
    baseline = [{"task_id": task.content_id, "values": values}
                for task, values in zip(tasks, [["0"], ["0", "0"]])]
    protocol = FrozenEvaluation.freeze(tasks=tasks, lineage=lineage, baseline=baseline,
                    policy="Synthetic fixture: exact per-instance correctness, paired counts, descriptive only",
                    actors=IndependencePolicy("fixture-proposer", "fixture-solver", "fixture-evaluator", "fixture-reviewer"))
    submission = {"protocol_id": protocol.protocol_id,
                  "predictions": [{"task_id": task.content_id, "values": values}
                                  for task, values in zip(tasks, [["1"], ["99", "2"]])]}
    report = protocol.evaluate(submission)
    args.destination.mkdir(parents=True, exist_ok=False)
    for name, content in [("spec.json", protocol.protocol_json), ("protocol.json", protocol.to_json()),
                          ("submission.json", canonical_payload(submission)), ("report.json", canonical_payload(report))]:
        (args.destination / name).write_text(content, encoding="utf-8")
    print(protocol.protocol_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
