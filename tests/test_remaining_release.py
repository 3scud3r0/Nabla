"""Adversarial local preservation, frozen results and offline release contracts."""
import base64
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p = load('preserve_evidence', ROOT / 'tools/preserve_evidence.py')
r = load('offline_release', ROOT / 'packaging/offline_release.py')
COMMIT = 'a' * 40


@pytest.fixture
def archive(tmp_path):
    for folder in p.ROOTS:
        target = tmp_path / folder
        target.mkdir(parents=True)
        (target / 'original.txt').write_text('Original historical bytes: aspiration ≠ evidence.\n')
    return tmp_path


def index(root):
    return p.preserve(root, commit=COMMIT, repository='https://example.org/source')


def test_original_index_is_complete_and_legacy_boundary_clean():
    manifest = json.loads((ROOT / p.INDEX).read_text())
    assert p.verify_preservation(ROOT, manifest)['verified_files'] >= 300
    assert p.audit_production_boundary(ROOT)['explicit_legacy_imports'] == 0
    assert all(row['origin']['path'] == row['path'] for row in manifest['records'])
    assert {row['role'] for row in manifest['records']} == {
        'historical-aspiration', 'non-production-legacy', 'reference-fixture',
        'frozen-result-including-failures'}


def test_index_roundtrip_deterministic_and_repeated(archive):
    first = index(archive)
    assert first == index(archive)
    assert p.verify_preservation(archive, json.loads(json.dumps(first)))['verified_files'] == 4
    assert not p.verify_preservation(archive, first)['scientific_validation']


@pytest.mark.parametrize('mutation', ['edit', 'delete', 'add'])
def test_frozen_set_rejects_mutation(archive, mutation):
    manifest = index(archive)
    target = archive / 'legacy/original.txt'
    if mutation == 'edit':
        target.write_text('changed')
    elif mutation == 'delete':
        target.unlink()
    else:
        (archive / 'legacy/new.txt').write_text('new')
    with pytest.raises((ValueError, FileNotFoundError)):
        p.verify_preservation(archive, manifest)


def test_index_rejects_hash_tamper(archive):
    manifest = index(archive)
    manifest['records'][0]['size'] += 1
    with pytest.raises(ValueError, match='hash mismatch'):
        p.verify_preservation(archive, manifest)


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'a\\b', 'a/../b', 'a//b', 'C:/file', ''])
def test_paths_are_confined(tmp_path, name):
    with pytest.raises(ValueError):
        p.safe_path(tmp_path, name)


def test_symlink_rejected_even_inside_root(tmp_path):
    (tmp_path / 'source').write_text('data')
    (tmp_path / 'alias').symlink_to(tmp_path / 'source')
    with pytest.raises(ValueError, match='Symlink'):
        p.safe_path(tmp_path, 'alias')


def test_fixture_pin_and_license():
    folder = ROOT / 'benchmarks/fixtures/longley-nist'
    manifest = json.loads((folder / 'manifest.json').read_text())
    checked = p.verify_fixture(folder, manifest)
    assert len(checked['files']) == 3
    assert checked['upstream_independently_checked'] is False
    manifest['license_basis'] = ''
    with pytest.raises(ValueError):
        p.verify_fixture(folder, manifest)


def test_fixture_corruption(tmp_path):
    (tmp_path / 'data').write_bytes(b'actual')
    manifest = {'commit': COMMIT, 'mirror': 'https://example.org', 'license_id': 'CC0-1.0',
                'license_basis': 'declared', 'original_reference': 'paper',
                'files': {'data': {'sha256': '0' * 64, 'path': 'upstream/data'}}}
    with pytest.raises(ValueError, match='checksum'):
        p.verify_fixture(tmp_path, manifest)


def test_negative_results_and_chain_preserved(tmp_path):
    (tmp_path / 'negative.json').write_text('{"correct":0,"total":48}')
    first = p.campaign_record(tmp_path, campaign='frozen', protocol='blind-v1',
                              license_id='CC0-1.0', files=['negative.json'])
    (tmp_path / 'new.json').write_text('{"correct":0,"total":48}')
    second = p.campaign_record(tmp_path, campaign='new', protocol='blind-v1',
                               license_id='CC0-1.0', files=['new.json'], previous=first)
    assert p.verify_chain(tmp_path, [first, second])['campaigns'] == 2
    assert not p.verify_chain(tmp_path, [first, second])['experiment_reexecuted']
    with pytest.raises(ValueError, match='distinct campaign'):
        p.campaign_record(tmp_path, campaign='frozen', protocol='blind-v1',
                          license_id='CC0-1.0', files=['new.json'], previous=first)
    with pytest.raises(ValueError, match='Broken'):
        p.verify_chain(tmp_path, [second, first])
    (tmp_path / 'negative.json').write_text('{"correct":48,"total":48}')
    with pytest.raises(ValueError, match='Frozen result'):
        p.verify_chain(tmp_path, [first, second])


def test_semantic_json_check_independent_of_byte_hash(tmp_path):
    path = tmp_path / 'result.json'
    path.write_text('{"negative":true}')
    record = p.campaign_record(tmp_path, campaign='one', protocol='v1', license_id='MIT', files=['result.json'])
    record.pop('record_id')
    record['artifacts'][0]['semantic_json_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='Semantic'):
        p.verify_chain(tmp_path, [p.sealed(record)])


def test_legacy_static_import_rejected(tmp_path):
    source = tmp_path / 'src'
    source.mkdir()
    (source / 'bad.py').write_text('from legacy.prototype import solve\n')
    with pytest.raises(ValueError, match='historical code'):
        p.audit_production_boundary(tmp_path)


def make_wheel(tmp_path, version='1.0'):
    prefix = f'nablamath-{version}.dist-info'
    entries = {'nablamath/__init__.py': b'"""Test wheel."""\n',
               prefix + '/METADATA': f'Metadata-Version: 2.1\nName: nablamath\nVersion: {version}\nRequires-Python: >=3.10\n'.encode(),
               prefix + '/WHEEL': b'Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n'}
    output = io.StringIO()
    writer = csv.writer(output, lineterminator='\n')
    for name, content in entries.items():
        encoded = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b'=').decode()
        writer.writerow([name, 'sha256=' + encoded, len(content)])
    writer.writerow([prefix + '/RECORD', '', ''])
    entries[prefix + '/RECORD'] = output.getvalue().encode()
    wheel = tmp_path / f'nablamath-{version}-py3-none-any.whl'
    with zipfile.ZipFile(wheel, 'w') as z:
        for name, content in entries.items():
            z.writestr(name, content)
    return wheel


@pytest.mark.parametrize('operation', ['install', 'upgrade', 'downgrade', 'repair'])
def test_offline_release_plans_idempotent(tmp_path, operation):
    wheel = make_wheel(tmp_path)
    checksum = hashlib.sha256(wheel.read_bytes()).hexdigest()
    plan = r.release_plan(wheel, tmp_path / 'env', expected_sha256=checksum, operation=operation)
    assert plan == r.release_plan(wheel, tmp_path / 'env', expected_sha256=checksum, operation=operation)
    assert '--no-index' in plan['command'] and '--no-deps' in plan['command']
    assert not (tmp_path / 'env').exists()
    assert plan['publisher_authenticated'] is False
    with pytest.raises(ValueError, match='isolated venv'):
        r.execute_plan(plan)
    plan['command'].append('--index-url=https://example.org')
    with pytest.raises(ValueError, match='modified'):
        r.execute_plan(plan)


def test_wheel_pin_fails_before_install(tmp_path):
    wheel = make_wheel(tmp_path)
    with pytest.raises(ValueError, match='digest mismatch'):
        r.release_plan(wheel, tmp_path / 'env', expected_sha256='0' * 64)
    checksum = hashlib.sha256(wheel.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='Dedicated'):
        r.release_plan(wheel, sys.prefix, expected_sha256=checksum)


def test_sbom_binds_wheel_and_declares_uncertainty(tmp_path):
    wheel = make_wheel(tmp_path)
    sbom = r.wheel_sbom(wheel, source_commit=COMMIT)
    assert sbom['spdxVersion'] == 'SPDX-2.3'
    package = sbom['packages'][0]
    assert package['checksums'][0]['checksumValue'] == hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert package['sourceInfo'].endswith(COMMIT)
    assert package['licenseDeclared'] == 'NOASSERTION'
    assert json.loads(sbom['comment'])['signed'] is False
    with pytest.raises(ValueError):
        r.wheel_sbom(wheel, source_commit='main')


def test_clean_environment_install_upgrade_downgrade_repair(tmp_path):
    """Exercise real pip offline; no optional dependency or other OS claim."""
    import subprocess
    import venv
    environment = tmp_path / 'clean-environment'
    venv.EnvBuilder(with_pip=True).create(environment)
    original = tmp_path / 'historical.bin'
    original.write_bytes(b'unchanged historical file\x00')
    history_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    wheels = {v: make_wheel(tmp_path, v) for v in ['1.0', '2.0']}
    for operation, version in [('install', '1.0'), ('upgrade', '2.0'),
                               ('downgrade', '1.0'), ('repair', '1.0')]:
        wheel = wheels[version]
        plan = r.release_plan(wheel, environment,
                              expected_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
                              operation=operation)
        receipt = r.execute_plan(plan)
        assert receipt['installed_version'] == version
        assert hashlib.sha256(original.read_bytes()).hexdigest() == history_hash
    python = environment / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    subprocess.run([str(python), '-m', 'pip', 'uninstall', '-y', 'nablamath'],
                   check=True, capture_output=True, timeout=30)
    absent = subprocess.run([str(python), '-c', 'import nablamath'], capture_output=True, timeout=30)
    assert absent.returncode != 0
    # Reinstall from the original preserved wheel restores the application.
    wheel = wheels['1.0']
    restored = r.execute_plan(r.release_plan(wheel, environment,
        expected_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest()))
    assert restored['installed_version'] == '1.0'


archive_import = load('preserved_archive', ROOT / 'scripts/preserved_archive.py')


def test_pinned_archive_repeat_and_conflict_recovery(tmp_path):
    path = tmp_path / 'history.zip'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('code/old.py', 'historical = True\n')
        z.writestr('original.txt', 'unchanged')
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    destination = tmp_path / 'import'
    first = archive_import.import_pinned_archive(path, destination, expected_sha256=checksum)
    second = archive_import.import_pinned_archive(path, destination, expected_sha256=checksum)
    assert first['changed'] and not second['changed']
    (destination / 'original.txt').write_text('locally changed')
    with pytest.raises(ValueError, match='differs'):
        archive_import.import_pinned_archive(path, destination, expected_sha256=checksum)
    assert (destination / 'original.txt').read_text() == 'locally changed'


@pytest.mark.parametrize('names', [['../outside'], ['A.txt', 'a.txt'], ['a', 'a/b'], ['a\\b']])
def test_unsafe_archive_does_not_create_destination(tmp_path, names):
    path = tmp_path / 'history.zip'
    with zipfile.ZipFile(path, 'w') as z:
        for name in names:
            z.writestr(name, 'payload')
    destination = tmp_path / 'import'
    with pytest.raises(ValueError):
        archive_import.import_pinned_archive(path, destination,
            expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    assert not destination.exists()


def test_archive_budget_and_wrong_pin(tmp_path):
    path = tmp_path / 'history.zip'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('data', 'a' * 1000)
    with pytest.raises(ValueError, match='hash'):
        archive_import.import_pinned_archive(path, tmp_path / 'import', expected_sha256='0' * 64)
    with pytest.raises(ValueError, match='budget'):
        archive_import.import_pinned_archive(path, tmp_path / 'import',
            expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), max_bytes=20)


def test_failed_archive_write_cleans_staging_and_retry_succeeds(tmp_path, monkeypatch):
    path = tmp_path / 'history.zip'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('a.txt', 'one')
        z.writestr('b.txt', 'two')
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    original_write = Path.write_bytes
    count = 0

    def fail_second(target, data):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError('simulated storage failure')
        return original_write(target, data)

    destination = tmp_path / 'import'
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'write_bytes', fail_second)
        with pytest.raises(OSError, match='storage failure'):
            archive_import.import_pinned_archive(path, destination, expected_sha256=checksum)
    assert not destination.exists()
    assert not list(tmp_path.glob('.nabla-import-*'))
    assert archive_import.import_pinned_archive(path, destination,
                                                expected_sha256=checksum)['files'] == 2
