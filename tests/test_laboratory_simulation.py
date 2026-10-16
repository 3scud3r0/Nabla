import hashlib
import json
from pathlib import Path
import pytest
from nablamath.benchmarks.laboratory import run_laboratory_workload, verify_laboratory_workload
from nablamath.core.semantic_ir import canonical_json


def rehash(root, name):
    manifest = json.loads((root / 'manifest.json').read_text())
    manifest['files'][name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    (root / 'manifest.json').write_text(canonical_json(manifest))


@pytest.fixture(scope='module')
def workload(tmp_path_factory):
    root = tmp_path_factory.mktemp('lab') / 'run'
    summary = run_laboratory_workload(root, per_family=1, seed=18951, parquet=False)
    return root, summary


def test_actual_campaign_is_reproducible_and_keeps_limits(workload):
    root, summary = workload
    assert verify_laboratory_workload(root)
    assert summary['record_count'] == 8
    assert summary['all_negative_controls_passed']
    assert summary['evaluations']['test-exact-reference']['successes'] == 2
    assert summary['vision_completion_percent'] is None
    assert not summary['external_lab_adoption']
    assert not summary['frontier_model_gain_established']
    assert not summary['external_learning_gain_established']
    with pytest.raises(FileExistsError):
        run_laboratory_workload(root, per_family=1, parquet=False)


def test_negative_control_selects_train_explicitly_not_first_sorted_row(tmp_path):
    root = tmp_path / 'ordering-regression'
    summary = run_laboratory_workload(root, per_family=1, seed=23117, parquet=False)
    lineage = json.loads((root / 'lineage.json').read_text())
    assert lineage['manifest'][0]['split'] == 'test'
    assert summary['controls']['transitive_lineage_leak_rejected']
    assert summary['all_negative_controls_passed']
    assert verify_laboratory_workload(root)


@pytest.mark.parametrize('name,mutate', [
    ('summary.json', lambda d: d.update(frontier_model_gain_established=True)),
    ('protocol.json', lambda d: d.update(selection_on_evaluation=True)),
    ('commitments.json', lambda d: d['test'].update(count=0)),
    ('lineage.json', lambda d: d.update(component_count=0)),
    ('evaluations/test-exact-reference.json', lambda d: d.update(successes=999)),
    ('models/nearest-all.json', lambda d: d.update(training_ids=[])),
])
def test_rehashed_fabrications_do_not_pass_semantic_replay(workload, tmp_path, name, mutate):
    import shutil
    root = tmp_path / 'copy'
    shutil.copytree(workload[0], root)
    path = root / name
    value = json.loads(path.read_text())
    mutate(value)
    path.write_text(canonical_json(value))
    rehash(root, name)
    assert not verify_laboratory_workload(root)


def test_unlisted_files_are_rejected(workload, tmp_path):
    import shutil
    root = tmp_path / 'copy'
    shutil.copytree(workload[0], root)
    (root / 'extra.json').write_text('{}')
    assert not verify_laboratory_workload(root)


@pytest.mark.parametrize('options', [{'per_family': 0}, {'per_family': 65}, {'seed': -1}, {'per_family': True}])
def test_invalid_budgets_leave_no_release(tmp_path, options):
    root = tmp_path / 'run'
    with pytest.raises(ValueError):
        run_laboratory_workload(root, parquet=False, **options)
    assert not root.exists()


def test_malformed_model_is_rejected_without_crashing(workload, tmp_path):
    import shutil
    root = tmp_path / 'copy'
    shutil.copytree(workload[0], root)
    path = root / 'models/nearest-all.json'
    value = json.loads(path.read_text())
    value['rows'] = [[]]
    path.write_text(canonical_json(value))
    rehash(root, 'models/nearest-all.json')
    assert not verify_laboratory_workload(root)


def test_orchestrator_keeps_failures_timeouts_and_continues(tmp_path, monkeypatch):
    import importlib.util
    import subprocess
    from types import SimpleNamespace
    spec = importlib.util.spec_from_file_location('laboratory_cli', Path(__file__).resolve().parents[1] / 'tools/simulate_frontier_lab.py')
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    calls = []
    def execute(command, **options):
        calls.append(command)
        assert options['check'] is False
        assert 'shell' not in options
        if len(calls) == 2:
            raise subprocess.TimeoutExpired(command, options['timeout'])
        return SimpleNamespace(returncode=1 if len(calls) == 1 else 0)
    monkeypatch.setattr(cli.subprocess, 'run', execute)
    root = tmp_path / 'campaign'
    args = SimpleNamespace(destination=root, per_family=1, seed=42, timeout=10)
    assert cli.run(args) is False
    summary = json.loads((root / 'summary.json').read_text())
    assert [row['status'] for row in summary['jobs']] == ['failed', 'timeout', 'passed', 'passed', 'passed']
    assert len(calls) == 5
    assert not summary['all_jobs_passed']
    assert summary['selected_phase_profiles_passed'] == 0
    assert not summary['vision_target_demonstrated']
    assert summary['vision_completion_percent'] is None
    assert len(summary['phase_profiles']) == 12
    with pytest.raises(FileExistsError):
        cli.run(args)


def test_calculator_profile_checks_exact_frozen_catalog_not_historical_count(tmp_path):
    from copy import deepcopy
    from nablamath.stability import public_contract
    from tools.simulate_frontier_lab import phase_profiles
    catalog=public_contract()['catalog']
    root=tmp_path/'science'
    root.mkdir()
    summary={'calculator_operations':len(catalog['operations']),'nist_reference_passed':True}
    (root/'summary.json').write_text(json.dumps(summary))
    assert not phase_profiles(tmp_path)['F1']['selected_profile_passed']
    (root/'calculator-catalog.json').write_text(json.dumps(catalog))
    assert phase_profiles(tmp_path)['F1']['selected_profile_passed']
    changed=deepcopy(catalog)
    changed['operations'][0]['required'].append('unreviewed_argument')
    (root/'calculator-catalog.json').write_text(json.dumps(changed))
    assert not phase_profiles(tmp_path)['F1']['selected_profile_passed']
    (root/'calculator-catalog.json').write_text(json.dumps(catalog))
    summary['calculator_operations']=33
    (root/'summary.json').write_text(json.dumps(summary))
    assert not phase_profiles(tmp_path)['F1']['selected_profile_passed']
