"""Adversarial tests for the integrated validation evidence and process gate."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('integrated_validation_test', ROOT / 'tools/integrated_validation.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def test_exit_code_failure_is_not_published_as_success(tmp_path):
    row = gate.run_step('failure', [sys.executable, '-c', 'raise SystemExit(4)'], 5, False, tmp_path)
    assert row['status'] == 'failed' and row['exit_code'] == 4
    assert row['evidence']['stderr']['sha256'] == gate.sha256(tmp_path / 'failure.stderr')


def test_timeout_kills_job_and_records_failure(tmp_path):
    row = gate.run_step('timeout', [sys.executable, '-c', 'import time;time.sleep(3)'], 0.1, False, tmp_path)
    assert row['status'] == 'failed' and row['timed_out']
    assert row['exit_code'] is None


def test_missing_pytest_report_is_rejected(tmp_path):
    row = gate.run_step('fake_tests', [sys.executable, '-c', 'print("fake pass")'], 5, True, tmp_path)
    assert row['exit_code'] == 0 and row['status'] == 'failed'


def test_empty_and_skipped_pytest_fail_closed(tmp_path):
    for name, content in [('empty', '<testsuite tests="0"/>'),
                          ('skipped', '<testsuite tests="1" skipped="1"/>')]:
        path = tmp_path / (name + '.xml')
        path.write_text(content)
        with pytest.raises(ValueError):
            gate._junit_counts(path)


def test_tampering_and_incomplete_campaign_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, 'checks', lambda profile: [('pass', ['python'], 5, False)])
    out = tmp_path / 'pass.stdout'
    err = tmp_path / 'pass.stderr'
    out.write_bytes(b'ok\n')
    err.write_bytes(b'')
    report = {'schema': gate.SCHEMA, 'profile': 'ci', 'passed': True,
              'stable_release_accepted': False, 'checks': [{
                  'name': 'pass', 'argv': ['python'], 'timeout_seconds': 5, 'status': 'passed', 'exit_code': 0, 'timed_out': False,
                  'evidence': {'stdout': {'file': out.name, 'sha256': gate.sha256(out), 'bytes': out.stat().st_size},
                               'stderr': {'file': err.name, 'sha256': gate.sha256(err), 'bytes': err.stat().st_size}}
              }]}
    (tmp_path / 'report.json').write_text(json.dumps(report))
    assert gate.verify(tmp_path)['passed']
    out.write_bytes(b'altered\n')
    with pytest.raises(ValueError, match='tampered'):
        gate.verify(tmp_path)
    out.write_bytes(b'ok\n')
    report['checks'].clear()
    (tmp_path / 'report.json').write_text(json.dumps(report))
    with pytest.raises(ValueError, match='Incomplete'):
        gate.verify(tmp_path)


def test_rejects_symlinked_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, 'checks', lambda profile: [('one', ['python'], 5, False)])
    original = tmp_path / 'original'
    original.write_bytes(b'payload')
    (tmp_path / 'one.stdout').symlink_to(original)
    (tmp_path / 'one.stderr').write_bytes(b'')
    def evidence(name):
        path = tmp_path / name
        return {'file': name, 'sha256': gate.sha256(path), 'bytes': path.stat().st_size}
    (tmp_path / 'report.json').write_text(json.dumps({
        'schema': gate.SCHEMA, 'profile': 'ci', 'passed': True,
        'stable_release_accepted': False, 'checks': [{'name': 'one', 'argv': ['python'], 'timeout_seconds': 5, 'status': 'passed',
        'exit_code': 0, 'timed_out': False, 'evidence': {'stdout': evidence('one.stdout'),
                                                        'stderr': evidence('one.stderr')}}]}))
    with pytest.raises(ValueError, match='tampered'):
        gate.verify(tmp_path)

def test_missing_executable_fails_closed(tmp_path):
    row = gate.run_step('missing', ['/absolutely/not-an-executable'], 5, False, tmp_path)
    assert row['status'] == 'failed' and row['exit_code'] is None
    assert b'could not start' in (tmp_path / 'missing.stderr').read_bytes()


def test_changed_command_cannot_reuse_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, 'checks', lambda profile: [('command', ['expected'], 5, False)])
    (tmp_path / 'command.stdout').write_bytes(b'ok')
    (tmp_path / 'command.stderr').write_bytes(b'')
    row = {'name':'command', 'argv':['forged'], 'timeout_seconds':5, 'status':'passed',
           'exit_code':0, 'timed_out':False, 'evidence':{
           k:{'file':f'command.{k}', 'bytes':(tmp_path / f'command.{k}').stat().st_size,
              'sha256':gate.sha256(tmp_path / f'command.{k}')} for k in ('stdout', 'stderr')}}
    (tmp_path / 'report.json').write_text(json.dumps({'schema':gate.SCHEMA,'profile':'ci',
        'passed':True,'stable_release_accepted':False,'checks':[row]}))
    with pytest.raises(ValueError, match='contract'):
        gate.verify(tmp_path)
