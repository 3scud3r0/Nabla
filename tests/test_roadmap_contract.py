import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_roadmap", ROOT / "tools/check_roadmap.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def matrix():
    return json.loads((ROOT / "docs/acceptance/evidence_matrix.json").read_text(encoding="utf-8"))


def test_complete_original_matrix_without_false_completion():
    result = checker.validate_matrix(matrix())
    assert result["requirements"] == 213
    assert result["statuses"]["validated"] == 0
    assert sum(result["statuses"].values()) == 213


@pytest.mark.parametrize("mutate", [
    lambda m: m["requirements"].pop(),
    lambda m: m.update(source_sha256="0" * 64),
    lambda m: m["requirements"][0].update(requirement="rewritten"),
    lambda m: m["requirements"][0].update(id=True),
    lambda m: m["requirements"][0].update(status="validated"),
    lambda m: m["requirements"][0].update(implementation=["../../etc/passwd"]),
    lambda m: m["requirements"][0].update(tests=[]),
    lambda m: m["requirements"][0].update(remaining=""),
])
def test_reject_missing_forged_or_unjustified_evidence(mutate):
    data = copy.deepcopy(matrix())
    mutate(data)
    with pytest.raises(ValueError):
        checker.validate_matrix(data)


@pytest.mark.parametrize("data", [[], None, {"schema_version": True}])
def test_reject_invalid_matrix_type_or_version(data):
    with pytest.raises(ValueError):
        checker.validate_matrix(data)
