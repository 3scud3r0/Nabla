"""A failed prerequisite cannot be disguised as successful assurance."""
import importlib.util
import json
from pathlib import Path


def test_missing_science_blocks_assurance_without_creating_empty_evidence(tmp_path):
    tool = Path(__file__).resolve().parents[1]/'tools/simulate_frontier_lab.py'
    spec = importlib.util.spec_from_file_location('frontier_prerequisite_test', tool)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.assurance(tmp_path) is False
    report = json.loads((tmp_path/'assurance.json').read_text())
    assert report['status'] == 'blocked'
    assert report['all_checks_passed'] is False
    assert set(report['missing_science_artifacts']) == {'peer-1.sqlite3', 'summary.json'}
    assert not (tmp_path/'science/peer-1.sqlite3').exists()
