"""Reject mutated artifacts and dependency sources before installing or building."""
import base64
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


wheel_check = load('supply_chain_wheel', 'tools/verify_wheel.py')
offline = load('supply_chain_offline', 'packaging/offline_release.py')
formal = load('supply_chain_formal', 'tools/check_formal_environment.py')
archive = load('supply_chain_archive', 'tools/build_nabla_bundle.py')


def wheel(path, *, dependency='sample==1.0', altered=False, broken_record=False):
    prefix = 'nablamath-0.1.0a1.dist-info'
    entries = {'nablamath/__init__.py': b'raise RuntimeError("must never execute")\n',
               prefix+'/METADATA': ('Metadata-Version: 2.1\nName: nablamath\nVersion: 0.1.0a1\n'
                                    'Requires-Python: >=3.10\nRequires-Dist: '+dependency+'\n').encode(),
               prefix+'/WHEEL': b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n'}
    if altered:
        entries['nablamath/__init__.py'] += b'# altered source\n'
    record = io.StringIO()
    writer = csv.writer(record)
    for name, raw in entries.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode()
        writer.writerow([name, 'sha256='+digest, str(len(raw))])
    writer.writerow([prefix+'/RECORD', '', ''])
    entries[prefix+'/RECORD'] = record.getvalue().encode()
    if broken_record:
        entries['nablamath/__init__.py'] += b'# unrecorded mutation\n'
    with zipfile.ZipFile(path, 'w') as target:
        for name, raw in entries.items():
            target.writestr(name, raw)


@pytest.mark.parametrize('change', ['source', 'dependency', 'record'])
def test_pin_rejects_source_dependency_and_record_mutation_before_install(tmp_path, change):
    path = tmp_path/'nablamath-0.1.0a1-py3-none-any.whl'
    wheel(path)
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    wheel(path, altered=change=='source', dependency='sample==9.9' if change=='dependency' else 'sample==1.0',
          broken_record=change=='record')
    with pytest.raises(ValueError):
        offline.release_plan(path, tmp_path/'environment', expected_sha256=expected)
    assert not (tmp_path/'environment').exists()
    if change != 'record':
        # A self-consistent RECORD alone cannot authenticate a rewritten artifact.
        assert wheel_check.verify_wheel(path)['name'] == 'nablamath'


def test_archive_payload_edit_fails_internal_digest(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    (tmp_path/'source.py').write_bytes(b'value = 11\r\n')
    original = archive.build_bundle(tmp_path)
    assert archive.inspect_bundle(original)['file_count'] == 1
    with pytest.raises(ValueError, match='hash'):
        archive.inspect_bundle(original.replace(b'value = 11', b'value = 22'))


def test_mathlib_pin_and_worktree_are_checked_before_build(tmp_path):
    project = tmp_path/'lean'
    package = project/'.lake/packages/mathlib'
    package.mkdir(parents=True)
    subprocess.run(['git', 'init', '-q', str(package)], check=True)
    (package/'Mathlib.lean').write_text('-- fixture source\n')
    subprocess.run(['git', '-C', str(package), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(package), '-c', 'user.name=Fixture',
                    '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'], check=True)
    revision = subprocess.check_output(['git', '-C', str(package), 'rev-parse', 'HEAD'], text=True).strip()
    (project/'lake-manifest.json').write_text(json.dumps({'packagesDir': '.lake/packages',
        'packages': [{'name': 'mathlib', 'rev': revision}]}))
    assert formal.validate(project, sources_only=True)['pinned_dependencies'] == 1
    (package/'Mathlib.lean').write_text('-- changed after dependency pin\n')
    with pytest.raises(ValueError, match='dependency changed'):
        formal.validate(project, sources_only=True)
    (package/'Mathlib.lean').write_text('-- fixture source\n')
    manifest = json.loads((project/'lake-manifest.json').read_text())
    manifest['packages'][0]['rev'] = '0'*40
    (project/'lake-manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='dependency changed'):
        formal.validate(project, sources_only=True)


def stable_statement(signed, body):
    return {'schema': 'nabla.release-acceptance.v1', 'profile': 'nabla-local-cpu-v1',
            'version': body['version'], 'source_commit': body['source']['commit'],
            'wheel_sha256': body['wheel']['sha256'], 'reviewer': 'explicit synthetic test reviewer',
            'gates': [{'id': name, 'status': 'passed',
                       'evidence': [{'uri': 'https://example.invalid/synthetic-test-evidence', 'sha256': 'b'*64}]}
                      for name in signed.STABLE_GATES]}


def test_final_stable_release_requires_exact_complete_signed_checklist(tmp_path):
    from copy import deepcopy
    signed = load('supply_chain_stable_signed', 'packaging/signed_release.py')
    body = {'version': '1.0.0', 'source': {'commit': 'a'*40}, 'wheel': {'sha256': 'c'*64}}
    statement = stable_statement(signed, body)
    annotation = {'annotationType': 'REVIEW', 'comment': json.dumps(statement)}
    assert signed.validate_stable_acceptance({'annotations': [annotation]}, body)['publisher_attested']
    for field, bad in [('source_commit', 'd'*40), ('wheel_sha256', 'e'*64), ('version', '1.0.1')]:
        changed = {**statement, field: bad}
        with pytest.raises(ValueError, match='bound'):
            signed.validate_stable_acceptance({'annotations': [{**annotation, 'comment': json.dumps(changed)}]}, body)
    for gates in [statement['gates'][:-1], statement['gates'][:-1]+[statement['gates'][0]],
                  [{**row, 'status': 'failed'} for row in statement['gates']]]:
        with pytest.raises(ValueError):
            signed.validate_stable_acceptance({'annotations': [{**annotation, 'comment': json.dumps({**statement,'gates':gates})}]}, body)
    with pytest.raises(ValueError):
        signed.validate_stable_acceptance({'annotations': []}, body)
    with pytest.raises(ValueError):
        signed.validate_stable_acceptance({'annotations': [annotation, annotation]}, body)
    assert not signed.validate_stable_acceptance({'annotations': []}, {**body,'version':'1.0.0rc1'})['required']


@pytest.mark.parametrize('version',['1.0','1.0.0','1.0.0+build.1','2.0.0.post1'])
def test_final_version_metadata_cannot_bypass_stable_gates(version):
    signed = load('supply_chain_version_signed', 'packaging/signed_release.py')
    with pytest.raises(ValueError, match='acceptance'):
        signed.validate_stable_acceptance({'annotations':[]}, {'version':version})
