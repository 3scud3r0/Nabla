"""The v1 contract and candidate inventory cannot silently broaden acceptance."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest
from nablamath.calc import CalculationSession, Notebook
from nablamath.compatibility import integration_report
from nablamath.core.semantic_ir import fingerprint
from nablamath.stability import public_contract, validate_public_api

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_readiness_test', ROOT/'tools/release_readiness.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def test_every_vision1_path_present_and_api_frozen():
    report = r.validate()
    assert len(report['inventory']) == 212
    assert all(row['present'] and row['acceptance'] for row in report['inventory'])
    assert report['stable_release_accepted'] is False
    assert all(gate['status'] != 'passed' for gate in report['external_gates'])
    assert validate_public_api()['operations'] == len(public_contract()['catalog']['operations'])


def test_catalog_mutation_cannot_pass_freeze(monkeypatch):
    from nablamath.calc import catalog
    monkeypatch.setitem(catalog.OPERATIONS, 'unreviewed_operation', ('algebra', set(), set(), 'unknown'))
    # catalog() reads AREAS; changing a public required argument is incompatible.
    from nablamath.calc.session import REQUIRED
    monkeypatch.setitem(REQUIRED, 'evaluate', {'source', 'new_required_field'})
    with pytest.raises(ValueError, match='catalog'):
        validate_public_api()


def test_public_contract_is_detached():
    original = public_contract()
    altered = public_contract()
    altered['package_exports'].clear()
    assert public_contract() == original


def test_integration_discovery_is_not_validation(monkeypatch):
    monkeypatch.setattr('nablamath.compatibility.shutil.which', lambda name: '/tools/'+name)
    assert all(row['status']=='unverified' for row in integration_report().values())
    monkeypatch.setattr('nablamath.compatibility.subprocess.run', lambda *a, **k:
                        subprocess.CompletedProcess(a, 0, 'Lean (version 0.0.1, fake)\n', ''))
    assert integration_report(probe=True)['lean']['status'] == 'incompatible'


def test_probe_timeout_is_unavailable(monkeypatch):
    monkeypatch.setattr('nablamath.compatibility.shutil.which', lambda name: '/tools/'+name)
    def timeout(*a, **kw):
        raise subprocess.TimeoutExpired(a, 5)
    monkeypatch.setattr('nablamath.compatibility.subprocess.run', timeout)
    assert all(row['status']=='unavailable' for row in integration_report(probe=True).values())


@pytest.mark.parametrize('version', [True, '1', 0, 2])
def test_notebook_rejects_rehashed_unknown_or_boolean_version(tmp_path, version):
    book = Notebook('old v1 format')
    book.append(CalculationSession().execute('evaluate', source='1+1'))
    data = book.to_data()
    data.pop('content_id')
    data['schema_version'] = version
    data['content_id'] = fingerprint(data)
    path = tmp_path/'notebook.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        Notebook.load(path)


def test_notebook_duplicate_keys_and_cell_fields_are_refused(tmp_path):
    book = Notebook()
    book.append(CalculationSession().execute('evaluate', source='1+1'))
    path = tmp_path/'notebook.json'
    raw = json.dumps(book.to_data())
    path.write_text(raw.replace('"schema_version": 1', '"schema_version": 1,"schema_version": 1', 1))
    with pytest.raises(ValueError, match='duplicado'):
        Notebook.load(path)
    data = book.to_data()
    data['cells'][0]['extra'] = 'unreviewed'
    payload = {k:v for k,v in data.items() if k!='content_id'}
    data['content_id'] = fingerprint(payload)
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        Notebook.load(path)


def test_notebook_publication_failure_leaves_no_partial_file(tmp_path, monkeypatch):
    path = tmp_path/'notebook.json'
    book = Notebook()
    import os
    def failure(*a):
        raise OSError('simulated publication failure')
    monkeypatch.setattr(os, 'link', failure)
    with pytest.raises(OSError):
        book.save(path)
    assert not list(tmp_path.iterdir())
