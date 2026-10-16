"""Signed offline updates tested with ephemeral test keys and synthetic wheels.

These tests do not sign or publish a Nabla release. Real integration tests create
clean local Linux venvs, install only fixture wheels without network/dependencies,
and exercise activation, rollback and recovery against durable SQLite state.
"""
from copy import deepcopy
import base64
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


staged = load('_nabla_delivery_staged_tests', ROOT / 'packaging/staged_release.py')
signed = staged.signed
offline = load('_nabla_delivery_offline_tests', ROOT / 'packaging/offline_release.py')
COMMIT = 'a' * 40
ISSUED = 1000
NOW = 1100
EXPIRES = 9000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_wheel(directory, version='0.1', *, extra=None, code=None, tags=None):
    directory.mkdir(parents=True, exist_ok=True)
    prefix = f'nablamath-{version}.dist-info'
    content = {
        'nablamath/__init__.py': code or b'"""Ephemeral signed-release test fixture."""\nVALUE = 42\n',
        prefix + '/METADATA': (
            f'Metadata-Version: 2.1\nName: nablamath\nVersion: {version}\n'
            'Requires-Python: >=3.10\n').encode(),
        prefix + '/WHEEL': (
            'Wheel-Version: 1.0\nGenerator: offline-test\nRoot-Is-Purelib: true\n'
            + (tags or 'Tag: py3-none-any\n')).encode(),
    }
    if extra:
        content.update(extra)
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator='\n')
    for name, data in content.items():
        checksum = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
        writer.writerow([name, 'sha256=' + checksum, len(data)])
    writer.writerow([prefix + '/RECORD', '', ''])
    content[prefix + '/RECORD'] = stream.getvalue().encode()
    path = directory / f'nablamath-{version}-py3-none-any.whl'
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in content.items():
            archive.writestr(name, data)
    return path


@pytest.fixture
def keys():
    pytest.importorskip('cryptography')
    private, _, _ = signed._crypto()
    return private.generate(), private.generate()


@pytest.fixture
def trust(tmp_path, keys):
    store = signed.IssuerTrust(tmp_path / 'trust.sqlite3')
    store.enroll(issuer='fixture-publisher', public_key=signed.public_hex(keys[0]),
                 channels=['stable', 'preview'], not_before=900, expires_unix=10000)
    return store


def manifest(directory, private_key, *, sequence=1, version='0.1', extra=None,
             code=None, tags=None, channel='stable', issuer='fixture-publisher'):
    wheel = write_wheel(directory, version, extra=extra, code=code, tags=tags)
    sbom = directory / f'nablamath-{version}.spdx.json'
    sbom.write_text(json.dumps(offline.wheel_sbom(wheel, source_commit=COMMIT), sort_keys=True))
    public = signed.public_hex(private_key)
    body = {'schema': 'nabla.signed-release.v1', 'context': signed.CONTEXT,
            'issuer': issuer, 'key_id': signed.key_id(public), 'public_key': public,
            'channel': channel, 'package': 'nablamath', 'version': version,
            'sequence': sequence, 'issued_unix': ISSUED, 'expires_unix': EXPIRES,
            'source': {'repository': 'https://example.org/synthetic-test-source',
                       'commit': COMMIT, 'binding': 'issuer-declared-not-reproduced'},
            'python': {'minimum': [3, 10], 'maximum_exclusive': [3, 15]},
            'wheel': {'filename': wheel.name, 'sha256': sha(wheel), 'size': wheel.stat().st_size},
            'sbom': {'filename': sbom.name, 'sha256': sha(sbom), 'size': sbom.stat().st_size}}
    return signed.sign_release(body, private_key)


def manager(tmp_path, trust):
    if os.name != 'posix':
        pytest.skip('Staged release integration profile currently requires POSIX')
    return staged.ReleaseManager(tmp_path / 'application', trust,
                                issuer='fixture-publisher', channel='stable')


def test_signature_receipt_and_exact_artifact_binding(tmp_path, keys, trust):
    envelope = manifest(tmp_path / 'source', keys[0])
    receipt = trust.verify(envelope, now_unix=NOW)
    assert receipt.manifest_id == hashlib.sha256(signed.validate_body(envelope['body'])).hexdigest()
    original_id = receipt.manifest_id
    envelope['body']['version'] = '99.0'
    assert receipt.body['version'] == '0.1' and receipt.manifest_id == original_id
    detached = receipt.to_data()
    detached['body']['version'] = '98.0'
    assert receipt.body['version'] == '0.1'
    result = signed.verify_artifacts(receipt, tmp_path / 'source')
    assert result['artifact_identity_verified']
    assert not result['issuer_trust_rechecked']
    assert not result['source_build_reproduced'] and not result['scientific_validation']
    assert result['wheel_sha256'] == receipt.body['wheel']['sha256']


def test_issuer_enrollment_idempotence_immutable_policy_and_permanent_revocation(tmp_path, keys, trust):
    public = signed.public_hex(keys[0])
    assert not trust.enroll(issuer='fixture-publisher', public_key=public,
                           channels=['preview', 'stable'], not_before=900, expires_unix=10000)
    with pytest.raises(ValueError, match='immutable'):
        trust.enroll(issuer='fixture-publisher', public_key=public,
                     channels=['stable'], not_before=900, expires_unix=10000)
    identifier = signed.key_id(public)
    assert trust.revoke('fixture-publisher', identifier)
    assert not trust.revoke('fixture-publisher', identifier)
    with pytest.raises(ValueError, match='revoked'):
        trust.enroll(issuer='fixture-publisher', public_key=public,
                     channels=['preview', 'stable'], not_before=900, expires_unix=10000)
    with pytest.raises(ValueError, match='Unknown or revoked'):
        trust.verify(manifest(tmp_path / 'source', keys[0]), now_unix=NOW)
    reopened = signed.IssuerTrust(trust.path)
    with pytest.raises(ValueError, match='Unknown or revoked'):
        reopened.verify(manifest(tmp_path / 'again', keys[0]), now_unix=NOW)


def test_unknown_issuer_wrong_channel_and_rotated_key(tmp_path, keys, trust):
    unknown = manifest(tmp_path / 'unknown', keys[1])
    with pytest.raises(ValueError, match='Unknown'):
        trust.verify(unknown, now_unix=NOW)
    trust.enroll(issuer='fixture-publisher', public_key=signed.public_hex(keys[1]),
                 channels=['stable'], not_before=900, expires_unix=10000)
    assert trust.verify(unknown, now_unix=NOW).body['public_key'] == signed.public_hex(keys[1])
    preview = manifest(tmp_path / 'preview', keys[1], channel='preview')
    with pytest.raises(ValueError, match='channel'):
        trust.verify(preview, now_unix=NOW)
    trust.revoke('fixture-publisher', signed.key_id(signed.public_hex(keys[0])))
    assert trust.verify(unknown, now_unix=NOW).body['version'] == '0.1'


@pytest.mark.parametrize('time', [999, EXPIRES, EXPIRES+1])
def test_expiry_and_future_release_are_rejected(tmp_path, keys, trust, time):
    with pytest.raises(ValueError, match='expired or not yet'):
        trust.verify(manifest(tmp_path / 'source', keys[0]), now_unix=time)


def test_clock_floor_survives_restart_and_failed_signature_does_not_advance(tmp_path, keys, trust):
    envelope = manifest(tmp_path / 'source', keys[0])
    trust.verify(envelope, now_unix=NOW)
    corrupted = deepcopy(envelope)
    corrupted['signature'] = '0' * 128
    with pytest.raises(ValueError, match='signature'):
        trust.verify(corrupted, now_unix=NOW+50)
    reopened = signed.IssuerTrust(trust.path)
    assert reopened.verify(envelope, now_unix=NOW).body['sequence'] == 1
    with pytest.raises(ValueError, match='regressed'):
        reopened.verify(envelope, now_unix=NOW-1)


def test_release_must_fit_pinned_key_validity_interval(tmp_path, keys, trust):
    envelope = manifest(tmp_path / 'source', keys[0])
    envelope['body']['issued_unix'] = 899
    envelope = signed.sign_release(envelope['body'], keys[0])
    with pytest.raises(ValueError, match='trust validity'):
        trust.verify(envelope, now_unix=NOW)
    envelope['body']['issued_unix'] = ISSUED
    envelope['body']['expires_unix'] = 10001
    envelope = signed.sign_release(envelope['body'], keys[0])
    with pytest.raises(ValueError, match='trust validity'):
        trust.verify(envelope, now_unix=NOW)


@pytest.mark.parametrize('field,value', [
    ('schema', 'other'), ('context', 'Nabla-network-message-v1'),
    ('package', 'unrelated'), ('issuer', '../issuer'), ('channel', ''),
    ('version', '1.0\nInjected'), ('sequence', True), ('sequence', 0),
    ('sequence', 2**64), ('issued_unix', 1.5), ('expires_unix', ISSUED),
    ('expires_unix', ISSUED+signed.MAX_LIFETIME+1), ('public_key', '0'*63),
    ('key_id', 'f'*64),
])
def test_signed_body_refuses_malformed_fields_before_signing(tmp_path, keys, field, value):
    envelope = manifest(tmp_path / 'source', keys[0])
    body = deepcopy(envelope['body'])
    body[field] = value
    with pytest.raises(ValueError):
        signed.sign_release(body, keys[0])


@pytest.mark.parametrize('field,value', [
    ('filename', '../release.whl'), ('filename', '/release.whl'),
    ('filename', 'C:\\release.whl'), ('filename', 'a//release.whl'),
    ('sha256', 'G'*64), ('size', True), ('size', 0),
    ('size', signed.MAX_WHEEL_BYTES+1),
])
def test_artifact_constraints_are_signed_and_bounded(tmp_path, keys, field, value):
    envelope = manifest(tmp_path / 'source', keys[0])
    body = envelope['body']
    body['wheel'][field] = value
    with pytest.raises(ValueError):
        signed.sign_release(body, keys[0])


def test_duplicate_fields_float_and_structural_resource_limits():
    with pytest.raises(ValueError, match='Duplicate'):
        signed._load(b'{"body":{},"body":{}}')
    with pytest.raises(ValueError, match='without floats'):
        signed._load(b'{"time":1.0}')
    with pytest.raises(ValueError, match='structural'):
        signed._json({'many': [None]*5000})
    with pytest.raises(ValueError, match='byte budget'):
        signed._json({'text': 'x' * signed.MAX_MANIFEST_BYTES})
    with pytest.raises(ValueError, match='Bounded'):
        signed._load(b' '*(signed.MAX_MANIFEST_BYTES+1))


def test_extra_fields_signature_tampering_and_domain_separation(tmp_path, keys, trust):
    envelope = manifest(tmp_path / 'source', keys[0])
    with pytest.raises(ValueError, match='Signing key'):
        signed.sign_release(envelope['body'], keys[1])
    for field, value in [('version', '0.2'), ('channel', 'preview'), ('sequence', 2)]:
        forged = deepcopy(envelope)
        forged['body'][field] = value
        with pytest.raises(ValueError, match='signature'):
            trust.verify(forged, now_unix=NOW)
    forged = deepcopy(envelope)
    forged['body']['unreviewed_command'] = 'execute'
    with pytest.raises(ValueError, match='fields'):
        trust.verify(forged, now_unix=NOW)
    forged = deepcopy(envelope)
    forged['signature'] = 'AB' * 64
    with pytest.raises(ValueError, match='signature'):
        trust.verify(forged, now_unix=NOW)


def test_optional_crypto_failure_is_closed(tmp_path, keys, trust, monkeypatch):
    envelope = manifest(tmp_path / 'source', keys[0])
    def unavailable():
        raise RuntimeError('Optional cryptography unavailable')
    monkeypatch.setattr(signed, '_crypto', unavailable)
    with pytest.raises(RuntimeError, match='unavailable'):
        trust.verify(envelope, now_unix=NOW)


def test_invalid_python_source_and_compatibility_constraints(tmp_path, keys, trust):
    envelope = manifest(tmp_path / 'source', keys[0])
    for value in [True, [3], [3, True], [3, -1]]:
        body = deepcopy(envelope['body'])
        body['python']['minimum'] = value
        with pytest.raises(ValueError):
            signed.sign_release(body, keys[0])
    body = deepcopy(envelope['body'])
    body['python'] = {'minimum': [3, 14], 'maximum_exclusive': [3, 15]}
    signed_version = signed.sign_release(body, keys[0])
    if sys.version_info[:2] < (3, 14):
        with pytest.raises(ValueError, match='compatibility'):
            trust.verify(signed_version, now_unix=NOW)
    body = deepcopy(envelope['body'])
    body['source']['binding'] = 'scientifically-proved'
    with pytest.raises(ValueError, match='verification limit'):
        signed.sign_release(body, keys[0])


def test_signed_wheel_and_sbom_corruption_are_rejected(tmp_path, keys, trust):
    directory = tmp_path / 'source'
    envelope = manifest(directory, keys[0])
    receipt = trust.verify(envelope, now_unix=NOW)
    wheel = directory / receipt.body['wheel']['filename']
    data = wheel.read_bytes()
    wheel.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
    with pytest.raises(ValueError, match='hash mismatch'):
        signed.verify_artifacts(receipt, directory)
    wheel.write_bytes(data)
    sbom = directory / receipt.body['sbom']['filename']
    sbom.write_bytes(sbom.read_bytes()+b' ')
    with pytest.raises(ValueError, match='size mismatch'):
        signed.verify_artifacts(receipt, directory)


@pytest.mark.parametrize('extra', [
    {'nablamath/hook.pth': b'import os\n'},
    {'bin/installer': b'execute'},
    {'otherpackage/__init__.py': b'pass\n'},
    {'nablamath/native.so': b'not really native'},
])
def test_signed_wheel_refuses_hooks_native_code_and_other_targets(tmp_path, keys, trust, extra):
    envelope = manifest(tmp_path / 'source', keys[0], extra=extra)
    receipt = trust.verify(envelope, now_unix=NOW)
    with pytest.raises(ValueError, match='contains'):
        signed.verify_artifacts(receipt, tmp_path / 'source')


def test_signed_native_tag_and_mismatched_sbom_rejected(tmp_path, keys, trust):
    directory = tmp_path / 'source'
    envelope = manifest(directory, keys[0], tags='Tag: cp312-cp312-linux_x86_64\n')
    with pytest.raises(ValueError, match='pure Python'):
        signed.verify_artifacts(trust.verify(envelope, now_unix=NOW), directory)
    envelope = manifest(tmp_path / 'other', keys[0])
    body = envelope['body']
    sbom_path = tmp_path / 'other' / body['sbom']['filename']
    sbom = json.loads(sbom_path.read_text())
    sbom['packages'][0]['checksums'][0]['checksumValue'] = '0' * 64
    sbom_path.write_text(json.dumps(sbom))
    body['sbom'].update(sha256=sha(sbom_path), size=sbom_path.stat().st_size)
    envelope = signed.sign_release(body, keys[0])
    with pytest.raises(ValueError, match='SBOM does not bind'):
        signed.verify_artifacts(trust.verify(envelope, now_unix=NOW), tmp_path / 'other')


def test_manifest_and_artifact_symlinks_rejected(tmp_path, keys, trust):
    envelope = manifest(tmp_path / 'source', keys[0])
    path = tmp_path / 'release.json'
    path.write_bytes(signed._json(envelope))
    alias = tmp_path / 'alias.json'
    alias.symlink_to(path)
    with pytest.raises(ValueError, match='symlink'):
        signed.load_envelope(alias)
    receipt = trust.verify(envelope, now_unix=NOW)
    wheel = tmp_path / 'source' / receipt.body['wheel']['filename']
    original = wheel.with_suffix('.original')
    wheel.rename(original)
    wheel.symlink_to(original)
    with pytest.raises(ValueError, match='Regular'):
        signed.verify_artifacts(receipt, tmp_path / 'source')


def test_real_clean_venv_stage_activate_upgrade_and_explicit_rollback(tmp_path, keys, trust):
    release = manager(tmp_path, trust)
    assert release.active_environment(now_unix=NOW) is None
    first = manifest(tmp_path / 'one', keys[0])
    prepared = release.stage(first, tmp_path / 'one', now_unix=NOW)
    assert prepared['status'] == 'ready' and prepared['active_manifest_id'] is None
    assert release.active_environment(now_unix=NOW) is None
    active = release.activate(prepared['manifest_id'], now_unix=NOW)
    assert active['status'] == 'active' and active['high_water_sequence'] == 1
    environment = release.active_environment(now_unix=NOW)
    assert environment == Path(prepared['environment'])
    assert (environment / 'pyvenv.cfg').is_file()
    journal_before = release.journal()['events']
    assert release.stage(first, tmp_path / 'one', now_unix=NOW)['status'] == 'active'
    assert release.activate(prepared['manifest_id'], now_unix=NOW)['status'] == 'active'
    assert release.journal()['events'] == journal_before
    second = manifest(tmp_path / 'two', keys[0], sequence=2, version='0.2')
    newer = release.stage(second, tmp_path / 'two', now_unix=NOW+1)
    assert release.active_environment(now_unix=NOW+1) == environment
    release.activate(newer['manifest_id'], now_unix=NOW+1)
    assert release.active_environment(now_unix=NOW+1) == Path(newer['environment'])
    reopened = manager(tmp_path, signed.IssuerTrust(trust.path))
    rollback = reopened.rollback(prepared['manifest_id'], reason='operator-observed fixture regression', now_unix=NOW+2)
    assert rollback['active_manifest_id'] == prepared['manifest_id']
    assert rollback['high_water_sequence'] == 2
    assert reopened.active_environment(now_unix=NOW+2) == environment
    with pytest.raises(ValueError, match='high-water'):
        reopened.activate(prepared['manifest_id'], now_unix=NOW+2)
    assert reopened.journal()['events'] == 7
    assert not reopened.journal()['administrator_tamperproof']


def root_body(root_keys, publishers, *, version=1, threshold=2, publisher_threshold=2,
              authority='fixture-root-authority'):
    all_keys = [*root_keys, *publishers]
    keys = {signed.key_id(signed.public_hex(key)): signed.public_hex(key) for key in all_keys}
    return {'schema': 'nabla.release-root.v1', 'context': signed.ROOT_CONTEXT,
            'authority': authority, 'version': version, 'issued_unix': 900,
            'expires_unix': 10000, 'keys': keys,
            'root_keys': [signed.key_id(signed.public_hex(key)) for key in root_keys],
            'root_threshold': threshold,
            'delegations': [{'issuer': 'fixture-publisher', 'channel': 'stable',
                             'threshold': publisher_threshold,
                             'key_ids': [signed.key_id(signed.public_hex(key)) for key in publishers]}]}


@pytest.fixture
def delegated(tmp_path, keys):
    private, _, _ = signed._crypto()
    roots = [private.generate(), private.generate()]
    publishers = list(keys)
    envelope = signed.sign_root(root_body(roots, publishers), roots)
    trust = signed.DelegatedPublisherTrust(tmp_path / 'delegated.sqlite3')
    trust.bootstrap(envelope, expected_sha256=hashlib.sha256(signed._json(envelope)).hexdigest(), now_unix=NOW)
    return trust, roots, publishers


def test_delegated_bootstrap_requires_exact_out_of_band_pin_and_self_threshold(tmp_path, keys):
    private, _, _ = signed._crypto()
    roots = [private.generate(), private.generate()]
    body = root_body(roots, list(keys))
    envelope = signed.sign_root(body, roots)
    trust = signed.DelegatedPublisherTrust(tmp_path / 'delegated.sqlite3')
    with pytest.raises(ValueError, match='pinned digest'):
        trust.bootstrap(envelope, expected_sha256='0'*64, now_unix=NOW)
    insufficient = signed.sign_root(body, roots[:1])
    with pytest.raises(ValueError, match='threshold'):
        trust.bootstrap(insufficient, expected_sha256=hashlib.sha256(signed._json(insufficient)).hexdigest(), now_unix=NOW)
    trust.bootstrap(envelope, expected_sha256=hashlib.sha256(signed._json(envelope)).hexdigest(), now_unix=NOW)
    with pytest.raises(ValueError, match='already bootstrapped'):
        trust.bootstrap(envelope, expected_sha256=hashlib.sha256(signed._json(envelope)).hexdigest(), now_unix=NOW)
    assert trust.describe(now_unix=NOW)['root_threshold'] == 2


def test_independent_threshold_approvals_detach_and_bind_exact_release(tmp_path, delegated):
    trust, _, publishers = delegated
    envelope = manifest(tmp_path / 'source', publishers[0])
    bundle = signed.approve_release(envelope, root_version=1, private_keys=publishers)
    receipt = trust.verify(bundle, now_unix=NOW)
    assert receipt.authorization_json == signed._json(bundle)
    assert receipt.body == envelope['body']
    original = receipt.manifest_id
    bundle['release']['body']['sequence'] = 99
    assert receipt.manifest_id == original and receipt.body['sequence'] == 1
    valid = signed._load(receipt.authorization_json)
    valid['approvals'].pop()
    with pytest.raises(ValueError, match='threshold'):
        trust.verify(valid, now_unix=NOW)


def test_duplicate_signatures_untrusted_approvers_and_wrong_context_cannot_meet_threshold(tmp_path, delegated):
    trust, _, publishers = delegated
    envelope = manifest(tmp_path / 'source', publishers[0])
    bundle = signed.approve_release(envelope, root_version=1, private_keys=publishers)
    duplicate = deepcopy(bundle)
    duplicate['approvals'] = [bundle['approvals'][0], bundle['approvals'][0]]
    with pytest.raises(ValueError, match='Duplicate'):
        trust.verify(duplicate, now_unix=NOW)
    with pytest.raises(ValueError, match='Duplicate'):
        signed.approve_release(envelope, root_version=1, private_keys=[publishers[0], publishers[0]])
    foreign = signed._crypto()[0].generate()
    unknown = signed.approve_release(envelope, root_version=1, private_keys=[publishers[0], foreign])
    with pytest.raises(ValueError, match='outside'):
        trust.verify(unknown, now_unix=NOW)
    wrong_context = deepcopy(bundle)
    wrong_context['approvals'][0]['signature'] = envelope['signature']
    with pytest.raises(ValueError, match='signature'):
        trust.verify(wrong_context, now_unix=NOW)


def test_approval_replay_cannot_authorize_another_version_sequence_or_root(tmp_path, delegated):
    trust, _, publishers = delegated
    first = manifest(tmp_path / 'first', publishers[0])
    second = manifest(tmp_path / 'second', publishers[0], sequence=2, version='0.2')
    bundle = signed.approve_release(first, root_version=1, private_keys=publishers)
    bundle['release'] = second
    with pytest.raises(ValueError, match='signature'):
        trust.verify(bundle, now_unix=NOW)
    bundle = signed.approve_release(first, root_version=2, private_keys=publishers)
    with pytest.raises(ValueError, match='stale or unknown'):
        trust.verify(bundle, now_unix=NOW)


def test_primary_publisher_needs_its_own_approval_even_if_other_keys_meet_threshold(tmp_path, keys):
    private, _, _ = signed._crypto()
    roots = [private.generate()]
    publishers = [*keys, private.generate()]
    body = root_body(roots, publishers, threshold=1)
    root = signed.sign_root(body, roots)
    trust = signed.DelegatedPublisherTrust(tmp_path / 'root.sqlite3')
    trust.bootstrap(root, expected_sha256=hashlib.sha256(signed._json(root)).hexdigest(), now_unix=NOW)
    envelope = manifest(tmp_path / 'source', publishers[0])
    bundle = signed.approve_release(envelope, root_version=1, private_keys=publishers[1:])
    with pytest.raises(ValueError, match='Primary publisher'):
        trust.verify(bundle, now_unix=NOW)


def test_dual_threshold_root_rotation_and_delegated_key_revocation(tmp_path, delegated):
    trust, roots, publishers = delegated
    private, _, _ = signed._crypto()
    successors = [private.generate(), private.generate()]
    replacement_publishers = [publishers[0], private.generate()]
    next_body = root_body(successors, replacement_publishers, version=2)
    only_old = signed.sign_root(next_body, roots)
    only_new = signed.sign_root(next_body, successors)
    with pytest.raises(ValueError, match='both predecessor and successor'):
        trust.rotate(only_old, now_unix=NOW)
    with pytest.raises(ValueError, match='both predecessor and successor'):
        trust.rotate(only_new, now_unix=NOW)
    valid = signed.sign_root(next_body, [*roots, *successors])
    assert trust.rotate(valid, now_unix=NOW)['previous_approvals_invalidated']
    assert signed.DelegatedPublisherTrust(trust.path).describe(now_unix=NOW)['version'] == 2
    envelope = manifest(tmp_path / 'source', publishers[0])
    with pytest.raises(ValueError, match='stale'):
        trust.verify(signed.approve_release(envelope, root_version=1, private_keys=publishers), now_unix=NOW)
    with pytest.raises(ValueError, match='outside'):
        trust.verify(signed.approve_release(envelope, root_version=2, private_keys=publishers), now_unix=NOW)
    assert trust.verify(signed.approve_release(envelope, root_version=2,
                        private_keys=replacement_publishers), now_unix=NOW).body['sequence'] == 1
    with pytest.raises(ValueError, match='advance one'):
        trust.rotate(valid, now_unix=NOW)


@pytest.mark.parametrize('corruption', ['threshold','publisher-threshold','duplicate-keys',
                                      'roles','unassigned','version','authority'])
def test_root_policy_structure_and_rotation_invariants(tmp_path, delegated, corruption):
    trust, roots, publishers = delegated
    body = root_body(roots, publishers, version=2)
    if corruption == 'threshold':
        body['root_threshold'] = 3
    elif corruption == 'publisher-threshold':
        body['delegations'][0]['threshold'] = True
    elif corruption == 'duplicate-keys':
        body['delegations'][0]['key_ids'] *= 2
    elif corruption == 'roles':
        body['delegations'][0]['key_ids'][0] = body['root_keys'][0]
    elif corruption == 'unassigned':
        foreign = signed.public_hex(signed._crypto()[0].generate())
        body['keys'][signed.key_id(foreign)] = foreign
    elif corruption == 'version':
        body['version'] = 3
    else:
        body['authority'] = 'changed-authority'
    with pytest.raises(ValueError):
        trust.rotate(signed.sign_root(body, roots), now_unix=NOW)
    assert trust.describe(now_unix=NOW)['version'] == 1


def test_expired_roots_and_corrupted_persistent_root_fail_closed(tmp_path, delegated):
    trust, _, publishers = delegated
    bundle = signed.approve_release(manifest(tmp_path / 'source', publishers[0]),
                                    root_version=1, private_keys=publishers)
    with pytest.raises(ValueError, match='root expired'):
        trust.verify(bundle, now_unix=10000)
    with sqlite3.connect(trust.path) as db:
        db.execute('UPDATE trust_root SET version=2')
    with pytest.raises(ValueError, match='commitment corrupted'):
        trust.verify(bundle, now_unix=NOW)


def test_revocation_after_staging_prevents_activation_and_active_use(tmp_path, keys, trust):
    release = manager(tmp_path, trust)
    envelope = manifest(tmp_path / 'source', keys[0])
    prepared = release.stage(envelope, tmp_path / 'source', now_unix=NOW)
    assert prepared['status'] == 'ready'
    trust.revoke('fixture-publisher', signed.key_id(signed.public_hex(keys[0])))
    with pytest.raises(ValueError, match='revoked'):
        release.activate(prepared['manifest_id'], now_unix=NOW)
    with release._db() as db:
        assert release._state(db)['active_id'] is None
    # The signed bytes are present, but that cannot bypass current revocation.
    with pytest.raises(ValueError, match='revoked'):
        release.stage(envelope, tmp_path / 'source', now_unix=NOW)


def test_failed_smoke_never_changes_active_pointer_and_recovery_is_idempotent(tmp_path, keys, trust):
    release = manager(tmp_path, trust)
    broken = manifest(tmp_path / 'broken', keys[0], code=b'raise RuntimeError("fixture failure")\n')
    identifier = trust.verify(broken, now_unix=NOW).manifest_id
    with pytest.raises(ValueError, match='smoke check failed'):
        release.stage(broken, tmp_path / 'broken', now_unix=NOW)
    assert release.active_environment(now_unix=NOW) is None
    assert not release._environment(identifier).exists()
    assert not release._artifact_directory(identifier).exists()
    assert release.recover()['abandoned'] == [identifier]
    assert release.recover()['abandoned'] == []
    with pytest.raises(ValueError, match='new sequence'):
        release.stage(broken, tmp_path / 'broken', now_unix=NOW)


def test_metadata_only_manifest_and_inventory_forgery_rejected(tmp_path, keys, trust):
    release = manager(tmp_path, trust)
    envelope = manifest(tmp_path / 'source', keys[0])
    prepared = release.stage(envelope, tmp_path / 'source', now_unix=NOW)
    identifier = prepared['manifest_id']
    with sqlite3.connect(release.path) as db:
        db.execute('UPDATE releases SET sequence=99 WHERE id=?', (identifier,))
    with pytest.raises(ValueError, match='commitment corrupted'):
        release.activate(identifier, now_unix=NOW)
    with sqlite3.connect(release.path) as db:
        db.execute('UPDATE releases SET sequence=1 WHERE id=?', (identifier,))
    environment = Path(prepared['environment'])
    cfg = environment / 'pyvenv.cfg'
    original = cfg.read_bytes()
    cfg.write_bytes(original + b'\n# tampered configuration\n')
    with pytest.raises(ValueError, match='bytes or marker changed'):
        release.activate(identifier, now_unix=NOW)
    cfg.write_bytes(original)
    package = next(environment.glob('lib/python*/site-packages/nablamath'))
    (package.parent / 'injected.pth').write_text('import os\n')
    with pytest.raises(ValueError, match='bytes or marker changed'):
        release.activate(identifier, now_unix=NOW)
    (package.parent / 'injected.pth').unlink()
    (package / 'injected.pyc').write_bytes(b'poisoned bytecode')
    with pytest.raises(ValueError, match='bytes or marker changed'):
        release.activate(identifier, now_unix=NOW)
    (package / 'injected.pyc').unlink()
    assert release.activate(identifier, now_unix=NOW)['status'] == 'active'
    trust.revoke('fixture-publisher', signed.key_id(signed.public_hex(keys[0])))
    with pytest.raises(ValueError, match='revoked'):
        release.active_environment(now_unix=NOW)


def test_interrupted_staging_recovers_without_activating_partial_environment(tmp_path, keys, trust, monkeypatch):
    release = manager(tmp_path, trust)
    envelope = manifest(tmp_path / 'source', keys[0])
    identifier = trust.verify(envelope, now_unix=NOW).manifest_id
    def interrupted(receipt, artifact_directory, environment):
        environment.mkdir()
        (environment / 'partial.txt').write_text('not an installed package')
        raise KeyboardInterrupt('simulated process interruption')
    monkeypatch.setattr(release, '_install', interrupted)
    with pytest.raises(KeyboardInterrupt):
        release.stage(envelope, tmp_path / 'source', now_unix=NOW)
    assert release._environment(identifier).exists()
    reopened = manager(tmp_path, trust)
    recovered = reopened.recover()
    assert recovered['abandoned'] == [identifier]
    assert not recovered['automatic_activation']
    assert recovered['active_manifest_id'] is None and recovered['high_water_sequence'] == 0
    assert not reopened._environment(identifier).exists()
    assert not reopened._artifact_directory(identifier).exists()
    assert reopened.recover()['abandoned'] == []


def test_activation_transaction_failure_rolls_back_pointer_and_journal(tmp_path, keys, trust, monkeypatch):
    release = manager(tmp_path, trust)
    envelope = manifest(tmp_path / 'source', keys[0])
    prepared = release.stage(envelope, tmp_path / 'source', now_unix=NOW)
    identifier = prepared['manifest_id']
    original_event = release._event
    def fail_activation(db, kind, manifest_id, **kwargs):
        if kind == 'activated':
            raise OSError('simulated journal storage failure')
        return original_event(db, kind, manifest_id, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(release, '_event', fail_activation)
        with pytest.raises(OSError, match='storage failure'):
            release.activate(identifier, now_unix=NOW)
    assert release.active_environment(now_unix=NOW) is None
    assert release.journal()['events'] == 2
    assert release.activate(identifier, now_unix=NOW)['status'] == 'active'
    assert release.journal()['events'] == 3


def test_delegated_rotation_between_stage_and_activation_requires_explicit_reapproval(tmp_path, delegated):
    trust, roots, publishers = delegated
    release = manager(tmp_path, trust)
    envelope = manifest(tmp_path / 'source', publishers[0])
    bundle = signed.approve_release(envelope, root_version=1, private_keys=publishers)
    prepared = release.stage(bundle, tmp_path / 'source', now_unix=NOW)
    next_body = root_body(roots, publishers, version=2)
    trust.rotate(signed.sign_root(next_body, roots), now_unix=NOW)
    identifier = prepared['manifest_id']
    with pytest.raises(ValueError, match='stale'):
        release.activate(identifier, now_unix=NOW)
    fresh = signed.approve_release(envelope, root_version=2, private_keys=publishers)
    refreshed = release.refresh_authorization(fresh, now_unix=NOW)
    assert refreshed['status'] == 'ready' and refreshed['high_water_sequence'] == 0
    assert release.activate(identifier, now_unix=NOW)['status'] == 'active'
    assert release.active_environment(now_unix=NOW) == Path(prepared['environment'])
    reopened = manager(tmp_path, signed.DelegatedPublisherTrust(trust.path))
    assert reopened.active_environment(now_unix=NOW) == Path(prepared['environment'])
    assert reopened.journal()['events'] == 4


def test_external_checkpoint_detects_full_database_backup_rollback(tmp_path, keys, trust):
    release = manager(tmp_path, trust)
    empty = release.export_checkpoint()
    assert empty['high_water_sequence'] == 0
    # Keep a complete earlier SQLite image, not a malformed partial-state edit.
    backup = tmp_path / 'previous-state.sqlite3'
    with sqlite3.connect(release.path) as source, sqlite3.connect(backup) as target:
        source.backup(target)
    envelope = manifest(tmp_path / 'source', keys[0])
    prepared = release.stage(envelope, tmp_path / 'source', now_unix=NOW)
    release.activate(prepared['manifest_id'], now_unix=NOW)
    checkpoint = release.export_checkpoint()
    pinned = hashlib.sha256(signed._json(checkpoint)).hexdigest()
    assert release.verify_checkpoint(checkpoint, expected_sha256=pinned)['extends_checkpoint']
    pinned_manager = staged.ReleaseManager(release.root, trust, issuer='fixture-publisher',
        channel='stable', checkpoint=checkpoint, checkpoint_sha256=pinned)
    assert pinned_manager.active_environment(now_unix=NOW) == Path(prepared['environment'])
    with sqlite3.connect(backup) as source, sqlite3.connect(release.path) as target:
        source.backup(target)
    # Without a separate pin, a complete administrator-restored old backup is
    # indistinguishable from legitimate old state. The explicit pin detects it.
    with pytest.raises(ValueError, match='regressed behind'):
        release.verify_checkpoint(checkpoint, expected_sha256=pinned)
    with pytest.raises(ValueError, match='regressed behind'):
        staged.ReleaseManager(release.root, trust, issuer='fixture-publisher', channel='stable',
                             checkpoint=checkpoint, checkpoint_sha256=pinned)


def test_checkpoint_validation_requires_independent_pin_and_channel_identity(tmp_path, trust):
    release = manager(tmp_path, trust)
    checkpoint = release.export_checkpoint()
    checksum = hashlib.sha256(signed._json(checkpoint)).hexdigest()
    with pytest.raises(ValueError, match='separately pinned digest'):
        release.verify_checkpoint(checkpoint, expected_sha256='0'*64)
    with pytest.raises(ValueError, match='supplied together'):
        staged.ReleaseManager(release.root, trust, issuer='fixture-publisher', channel='stable',
                             checkpoint=checkpoint)
    changed = {**checkpoint, 'channel': 'preview'}
    with pytest.raises(ValueError, match='different installation'):
        release.verify_checkpoint(changed, expected_sha256=hashlib.sha256(signed._json(changed)).hexdigest())
    bad = {**checkpoint, 'high_water_sequence': 1}
    with pytest.raises(ValueError, match='high-water identity'):
        release.verify_checkpoint(bad, expected_sha256=hashlib.sha256(signed._json(bad)).hexdigest())
    assert release.verify_checkpoint(checkpoint, expected_sha256=checksum)['high_water_sequence'] == 0


def test_checkpoint_remains_valid_under_forward_journal_extension(tmp_path, keys, trust):
    release = manager(tmp_path, trust)
    before = release.export_checkpoint()
    checksum = hashlib.sha256(signed._json(before)).hexdigest()
    envelope = manifest(tmp_path / 'source', keys[0])
    prepared = release.stage(envelope, tmp_path / 'source', now_unix=NOW)
    receipt = release.verify_checkpoint(before, expected_sha256=checksum)
    assert receipt['journal_events'] == 2 and receipt['high_water_sequence'] == 0
    after_stage = release.export_checkpoint()
    stage_pin = hashlib.sha256(signed._json(after_stage)).hexdigest()
    release.activate(prepared['manifest_id'], now_unix=NOW)
    assert release.verify_checkpoint(after_stage, expected_sha256=stage_pin)['high_water_sequence'] == 1
    forged = deepcopy(after_stage)
    forged['journal_head'] = '0' * 64
    with pytest.raises(ValueError, match='does not extend'):
        release.verify_checkpoint(forged, expected_sha256=hashlib.sha256(signed._json(forged)).hexdigest())


@pytest.mark.parametrize('output', ['stdout', 'stderr'])
def test_release_subprocess_output_is_memory_bounded_and_fails_on_overflow(output):
    code = f'import sys; sys.{output}.write("x"*1000000); sys.{output}.flush()'
    with pytest.raises(ValueError, match='output exceeds budget'):
        staged._run_bounded([sys.executable, '-I', '-c', code], timeout=5,
                            output_limit=1024, environment=dict(os.environ))


def test_release_subprocess_timeout_and_exit_code():
    with pytest.raises(ValueError, match='timed out'):
        staged._run_bounded([sys.executable, '-I', '-c', 'import time;time.sleep(10)'],
                            timeout=0.05, output_limit=1024, environment=dict(os.environ))
    result = staged._run_bounded([sys.executable, '-I', '-c',
        'import sys;print("fixture output");print("fixture error",file=sys.stderr);sys.exit(7)'],
        timeout=5, output_limit=1024, environment=dict(os.environ))
    assert result.returncode == 7
    assert result.stdout.strip() == 'fixture output'
    assert result.stderr.strip() == 'fixture error'


def test_release_output_descendant_cannot_keep_probe_open():
    if os.name != 'posix':
        pytest.skip('POSIX process-group cleanup profile')
    # The child retaining stdout is killed as part of the fixed probe's process
    # group. This exercises lifecycle cleanup; it does not establish a sandbox.
    code = ('import os,time; pid=os.fork(); '
            'time.sleep(10) if pid==0 else None')
    with pytest.raises(ValueError, match='inherited output streams'):
        staged._run_bounded([sys.executable, '-I', '-c', code], timeout=5,
                            output_limit=1024, environment=dict(os.environ))


def test_single_operation_lock_and_symlink_boundaries(tmp_path, keys, trust):
    release = manager(tmp_path, trust)
    with release._lock():
        with pytest.raises(ValueError, match='in progress'):
            release.recover()
        with pytest.raises(ValueError, match='in progress'):
            manager(tmp_path, trust)
    target = tmp_path / 'target'
    target.mkdir()
    alias = tmp_path / 'alias'
    alias.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match='symlinks'):
        staged.ReleaseManager(alias, trust, issuer='fixture-publisher', channel='stable')
    with pytest.raises(ValueError, match='different issuer or channel'):
        staged.ReleaseManager(release.root, trust, issuer='fixture-publisher', channel='preview')


def test_release_capacity_and_sequence_equivocation_fail_before_install(tmp_path, keys, trust, monkeypatch):
    release = manager(tmp_path, trust)
    called = []
    def should_not_run(*args):
        called.append(True)
        raise AssertionError('must fail before installation')
    monkeypatch.setattr(release, '_install', should_not_run)
    monkeypatch.setattr(staged, 'MAX_RELEASES', 0)
    envelope = manifest(tmp_path / 'source', keys[0])
    with pytest.raises(ValueError, match='capacity'):
        release.stage(envelope, tmp_path / 'source', now_unix=NOW)
    assert not called
    assert release.journal()['events'] == 0


def test_metadata_high_water_reduction_and_corrupt_journal_block_operations(tmp_path, keys, trust):
    release = manager(tmp_path, trust)
    prepared = release.stage(manifest(tmp_path / 'source', keys[0]), tmp_path / 'source', now_unix=NOW)
    release.activate(prepared['manifest_id'], now_unix=NOW)
    with sqlite3.connect(release.path) as db:
        db.execute('UPDATE state SET high_sequence=0,high_manifest_id=NULL,active_id=NULL')
        db.execute('UPDATE releases SET status="inactive"')
    with pytest.raises(ValueError, match='high-water was reduced'):
        release.recover()
    with sqlite3.connect(release.path) as db:
        db.execute('UPDATE state SET high_sequence=1,high_manifest_id=?,active_id=?',
                   (prepared['manifest_id'], prepared['manifest_id']))
        db.execute('UPDATE releases SET status="active"')
        db.execute('UPDATE events SET record_hash=? WHERE sequence=1', ('0'*64,))
    with pytest.raises(ValueError, match='hash chain corrupted'):
        release.active_environment(now_unix=NOW)
    with pytest.raises(ValueError, match='hash chain corrupted'):
        release.recover()


def test_stored_envelope_rehash_does_not_override_signature(tmp_path, keys, trust, monkeypatch):
    release = manager(tmp_path, trust)
    envelope = manifest(tmp_path / 'source', keys[0])
    # Simulate a crash just before environment creation to get a durable record
    # without spending work installing a wheel for this metadata-only test.
    def stop(*args):
        raise KeyboardInterrupt()
    monkeypatch.setattr(release, '_install', stop)
    with pytest.raises(KeyboardInterrupt):
        release.stage(envelope, tmp_path / 'source', now_unix=NOW)
    identifier = trust.verify(envelope, now_unix=NOW).manifest_id
    forged = deepcopy(envelope)
    forged['body']['version'] = '9.9'
    with sqlite3.connect(release.path) as db:
        db.execute('UPDATE releases SET envelope=?,version=? WHERE id=?',
                   (signed._json(forged).decode(), '9.9', identifier))
    with pytest.raises(ValueError, match='signature'):
        release.activate(identifier, now_unix=NOW)
    # Recovery abandons the incomplete environment, never promotes forged data.
    assert release.recover()['abandoned'] == [identifier]


def test_expired_prepared_release_cannot_activate_or_refresh(tmp_path, keys, trust):
    release = manager(tmp_path, trust)
    envelope = manifest(tmp_path / 'source', keys[0])
    prepared = release.stage(envelope, tmp_path / 'source', now_unix=NOW)
    with pytest.raises(ValueError, match='expired'):
        release.activate(prepared['manifest_id'], now_unix=EXPIRES)
    with pytest.raises(ValueError, match='expired'):
        release.refresh_authorization(envelope, now_unix=EXPIRES)
    with release._db() as db:
        assert release._state(db)['active_id'] is None


def test_rollback_cannot_select_never_activated_release(tmp_path, keys, trust):
    release = manager(tmp_path, trust)
    prepared = release.stage(manifest(tmp_path / 'source', keys[0]), tmp_path / 'source', now_unix=NOW)
    with pytest.raises(ValueError, match='previously activated'):
        release.rollback(prepared['manifest_id'], reason='cannot bypass activation policy', now_unix=NOW)
    with pytest.raises(ValueError, match='rollback reason'):
        release.rollback(prepared['manifest_id'], reason='', now_unix=NOW)


def test_active_environment_symlink_replacement_is_rejected(tmp_path, keys, trust):
    release = manager(tmp_path, trust)
    prepared = release.stage(manifest(tmp_path / 'source', keys[0]), tmp_path / 'source', now_unix=NOW)
    environment = Path(prepared['environment'])
    original = environment / 'bin/python'
    target = os.readlink(original) if original.is_symlink() else None
    original_bytes = None if target is not None else original.read_bytes()
    original_mode = original.stat().st_mode
    original.unlink()
    original.symlink_to('/bin/echo')
    with pytest.raises(ValueError, match='Unexpected symlink'):
        release.activate(prepared['manifest_id'], now_unix=NOW)
    original.unlink()
    if target is not None:
        original.symlink_to(target)
    else:
        original.write_bytes(original_bytes)
        original.chmod(original_mode)
    assert release.activate(prepared['manifest_id'], now_unix=NOW)['status'] == 'active'


def test_install_inventory_cannot_be_redeclared_by_mutable_metadata(tmp_path, keys, trust):
    release = manager(tmp_path, trust)
    prepared = release.stage(manifest(tmp_path / 'source', keys[0]), tmp_path / 'source', now_unix=NOW)
    environment = Path(prepared['environment'])
    marker_path = environment / 'nabla-release.json'
    marker = json.loads(marker_path.read_text())
    installed = next(environment.glob('lib/python*/site-packages/nablamath/__init__.py'))
    original = installed.read_bytes()
    installed.write_bytes(original+b'NEWLY_INJECTED = True\n')
    changed_inventory = release._inventory(environment)
    marker['inventory'] = changed_inventory
    marker_path.write_bytes(signed._json(marker))
    with sqlite3.connect(release.path) as db:
        db.execute('UPDATE releases SET inventory=? WHERE id=?',
                   (changed_inventory, prepared['manifest_id']))
    # Even a coordinated row+marker edit does not change the stage-ready event.
    with pytest.raises(ValueError, match='preparation journal'):
        release.activate(prepared['manifest_id'], now_unix=NOW)
    with release._db() as db:
        assert release._state(db)['active_id'] is None


def test_approval_requires_matching_primary_signature_and_expected_issuer(tmp_path, delegated):
    trust, _, publishers = delegated
    primary = manifest(tmp_path / 'source', publishers[0])
    bundle = signed.approve_release(primary, root_version=1, private_keys=publishers)
    bundle['release']['signature'] = '0'*128
    with pytest.raises(ValueError, match='primary release signature'):
        trust.verify(bundle, now_unix=NOW)
    other = manifest(tmp_path / 'other', publishers[0], issuer='another-issuer')
    approved = signed.approve_release(other, root_version=1, private_keys=publishers)
    with pytest.raises(ValueError, match='No publisher delegation'):
        trust.verify(approved, now_unix=NOW)


def test_primary_removed_by_root_rotation_cannot_be_revived_with_new_cosigners(tmp_path, delegated):
    trust, roots, publishers = delegated
    private, _, _ = signed._crypto()
    replacements = [publishers[1], private.generate()]
    next_root = root_body(roots, replacements, version=2)
    trust.rotate(signed.sign_root(next_root, roots), now_unix=NOW)
    old = manifest(tmp_path / 'old', publishers[0])
    bundle = signed.approve_release(old, root_version=2, private_keys=replacements)
    with pytest.raises(ValueError, match='not delegated or has been revoked'):
        trust.verify(bundle, now_unix=NOW)
    current = manifest(tmp_path / 'current', replacements[0])
    valid = signed.approve_release(current, root_version=2, private_keys=replacements)
    assert trust.verify(valid, now_unix=NOW).body['public_key'] == signed.public_hex(replacements[0])


def test_delegated_clock_floor_survives_restart(tmp_path, delegated):
    trust, _, publishers = delegated
    envelope = manifest(tmp_path / 'source', publishers[0])
    bundle = signed.approve_release(envelope, root_version=1, private_keys=publishers)
    trust.verify(bundle, now_unix=NOW+10)
    reopened = signed.DelegatedPublisherTrust(trust.path)
    with pytest.raises(ValueError, match='clock regressed'):
        reopened.verify(bundle, now_unix=NOW)
    assert reopened.verify(bundle, now_unix=NOW+10).body['sequence'] == 1


def test_root_digest_corruption_and_oversized_state_are_rejected(tmp_path, delegated, monkeypatch):
    trust, _, publishers = delegated
    envelope = manifest(tmp_path / 'source', publishers[0])
    bundle = signed.approve_release(envelope, root_version=1, private_keys=publishers)
    with sqlite3.connect(trust.path) as db:
        db.execute('UPDATE trust_root SET root_hash=?', ('0'*64,))
    with pytest.raises(ValueError, match='commitment corrupted'):
        trust.verify(bundle, now_unix=NOW)
    release = manager(tmp_path, trust)
    monkeypatch.setattr(staged, 'MAX_STATE_BYTES', 1)
    with pytest.raises(ValueError, match='exceeds budget'):
        release.journal()


def test_issuer_policy_capacity_and_bad_channels_are_rejected(tmp_path, keys, trust, monkeypatch):
    public = signed.public_hex(keys[1])
    with pytest.raises(ValueError, match='Duplicate release channel'):
        trust.enroll(issuer='another', public_key=public, channels=['stable','stable'],
                     not_before=900, expires_unix=10000)
    with pytest.raises(ValueError, match='trust interval'):
        trust.enroll(issuer='another', public_key=public, channels=['stable'],
                     not_before=10000, expires_unix=900)
    monkeypatch.setattr(signed, 'MAX_KEYS', 1)
    with pytest.raises(ValueError, match='capacity'):
        trust.enroll(issuer='another', public_key=public, channels=['stable'],
                     not_before=900, expires_unix=10000)
    with pytest.raises(ValueError, match='unknown'):
        trust.revoke('unknown-publisher', signed.key_id(public))


def test_manifest_receipt_identity_forgery_and_empty_receipt_rejected(tmp_path, keys, trust):
    envelope = manifest(tmp_path / 'source', keys[0])
    receipt = trust.verify(envelope, now_unix=NOW)
    forged = signed.VerifiedRelease(receipt.envelope_json, '0'*64)
    with pytest.raises(ValueError, match='identity mismatch'):
        signed.verify_artifacts(forged, tmp_path / 'source')
    with pytest.raises(ValueError, match='Verified release receipt'):
        signed.verify_artifacts(envelope, tmp_path / 'source')


def test_subprocess_environment_discards_python_and_pip_injection(tmp_path, trust, monkeypatch):
    release = manager(tmp_path, trust)
    monkeypatch.setenv('PYTHONPATH', '/attacker/modules')
    monkeypatch.setenv('PYTHONHOME', '/attacker/python')
    monkeypatch.setenv('PIP_INDEX_URL', 'https://untrusted.invalid/simple')
    monkeypatch.setenv('PIP_EXTRA_INDEX_URL', 'https://also-untrusted.invalid/simple')
    monkeypatch.setenv('PIP_CONFIG_FILE', '/attacker/pip.conf')
    monkeypatch.setenv('LD_PRELOAD', '/attacker/inject.so')
    environment = release._subprocess_environment()
    assert not {'PYTHONPATH','PYTHONHOME','PIP_INDEX_URL','PIP_EXTRA_INDEX_URL','LD_PRELOAD'} & set(environment)
    assert environment['PIP_CONFIG_FILE'] == os.devnull
    assert environment['PIP_NO_INDEX'] == '1'
    assert environment['PYTHONNOUSERSITE'] == '1'


def test_recovery_never_removes_previously_active_release(tmp_path, keys, trust):
    release = manager(tmp_path, trust)
    prepared = release.stage(manifest(tmp_path / 'source', keys[0]), tmp_path / 'source', now_unix=NOW)
    release.activate(prepared['manifest_id'], now_unix=NOW)
    with pytest.raises(ValueError, match='previously active'):
        release._remove_unactivated(prepared['manifest_id'])
    recovered = release.recover()
    assert recovered['abandoned'] == []
    assert recovered['active_manifest_id'] == prepared['manifest_id']
    assert recovered['high_water_sequence'] == 1
    assert Path(prepared['environment']).is_dir()


def test_authorization_refresh_does_not_create_an_unregistered_update(tmp_path, keys, trust):
    release = manager(tmp_path, trust)
    envelope = manifest(tmp_path / 'source', keys[0])
    with pytest.raises(ValueError, match='existing prepared release'):
        release.refresh_authorization(envelope, now_unix=NOW)
    assert release.journal()['events'] == 0
    assert release.active_environment(now_unix=NOW) is None


def test_pinned_checkpoint_rejects_clock_state_rollback_without_pointer_changes(tmp_path, trust):
    release = manager(tmp_path, trust)
    assert release.active_environment(now_unix=NOW) is None
    checkpoint = release.export_checkpoint()
    pin = hashlib.sha256(signed._json(checkpoint)).hexdigest()
    with sqlite3.connect(release.path) as db:
        db.execute('UPDATE state SET last_unix=0')
    with pytest.raises(ValueError, match='regressed behind'):
        release.verify_checkpoint(checkpoint, expected_sha256=pin)


def test_corrupted_issuer_clock_and_trust_interval_fail_with_explicit_validation(tmp_path, keys, trust):
    envelope = manifest(tmp_path / 'source', keys[0])
    with sqlite3.connect(trust.path) as db:
        db.execute('UPDATE issuers SET not_before=?', ('corrupt',))
    with pytest.raises(ValueError, match='stored issuer not-before'):
        trust.verify(envelope, now_unix=NOW)
    with sqlite3.connect(trust.path) as db:
        db.execute('UPDATE issuers SET not_before=900')
        db.execute('DELETE FROM trust_clock')
    with pytest.raises(ValueError, match='clock state missing'):
        trust.verify(envelope, now_unix=NOW)


def test_open_issuer_store_rechecks_path_after_symlink_replacement(tmp_path, keys, trust):
    original = trust.path
    moved = tmp_path / 'moved-issuer.sqlite3'
    original.rename(moved)
    original.symlink_to(moved)
    before = moved.read_bytes()
    with pytest.raises(ValueError, match='symlinks'):
        trust.revoke('fixture-publisher', signed.key_id(signed.public_hex(keys[0])))
    assert moved.read_bytes() == before
    with pytest.raises(ValueError, match='symlinks'):
        signed.IssuerTrust(original)


def test_open_delegated_store_rechecks_replaced_symlink_ancestors(tmp_path, delegated):
    trust, roots, publishers = delegated
    path = trust.path
    moved = tmp_path / 'moved-root.sqlite3'
    path.rename(moved)
    path.symlink_to(moved)
    before = moved.read_bytes()
    with pytest.raises(ValueError, match='symlinks'):
        trust.describe(now_unix=NOW)
    with pytest.raises(ValueError, match='symlinks'):
        trust.rotate(signed.sign_root(root_body(roots,publishers,version=2),roots),now_unix=NOW)
    assert moved.read_bytes() == before
    actual = tmp_path/'actual-directory'
    actual.mkdir()
    alias = tmp_path/'alias-directory'
    alias.symlink_to(actual,target_is_directory=True)
    with pytest.raises(ValueError, match='symlinks'):
        signed.DelegatedPublisherTrust(alias/'trust.sqlite3')
    assert not (actual/'trust.sqlite3').exists()


def test_existing_release_manager_rechecks_replaced_root_before_lock(tmp_path, trust):
    release = manager(tmp_path, trust)
    original = release.root
    moved = tmp_path/'moved-application'
    original.rename(moved)
    original.symlink_to(moved,target_is_directory=True)
    database = moved/'state.sqlite3'
    before = database.read_bytes()
    with pytest.raises(ValueError,match='symlinks'):
        release.recover()
    assert database.read_bytes() == before


def acceptance_statement(body):
    return {'schema':'nabla.release-acceptance.v1','profile':'nabla-local-cpu-v1',
        'version':body['version'],'source_commit':body['source']['commit'],
        'wheel_sha256':body['wheel']['sha256'],'reviewer':'synthetic release fixture reviewer',
        'gates':[{'id':name,'status':'passed','evidence':[
            {'uri':'https://example.invalid/synthetic-reviewed-evidence','sha256':'b'*64}]}
            for name in signed.STABLE_GATES]}


def with_acceptance(envelope, source, private_key, statement):
    body=deepcopy(envelope['body'])
    path=source/body['sbom']['filename']
    sbom=json.loads(path.read_text())
    sbom['annotations']=[{'annotationType':'REVIEW','annotator':'Person: synthetic fixture',
                          'annotationDate':'2026-10-16T00:00:00Z','comment':json.dumps(statement)}]
    path.write_text(json.dumps(sbom))
    body['sbom']['sha256']=sha(path)
    body['sbom']['size']=path.stat().st_size
    return signed.sign_release(body,private_key)


def test_stable_final_artifact_requires_signed_bound_publisher_acceptance(tmp_path,keys,trust):
    source=tmp_path/'stable-source'
    envelope=manifest(source,keys[0],version='1.0.0')
    receipt=trust.verify(envelope,now_unix=NOW)
    with pytest.raises(ValueError,match='acceptance'):
        signed.verify_artifacts(receipt,source)
    statement=acceptance_statement(envelope['body'])
    accepted=with_acceptance(envelope,source,keys[0],statement)
    receipt=trust.verify(accepted,now_unix=NOW)
    result=signed.verify_artifacts(receipt,source)
    assert result['stable_acceptance']['gates']==13
    assert not result['stable_acceptance']['evidence_independently_reexecuted']
    # Even a trusted publisher cannot pass a checklist explicitly carrying a failed gate.
    statement['gates'][0]['status']='failed'
    rejected=with_acceptance(accepted,source,keys[0],statement)
    receipt=trust.verify(rejected,now_unix=NOW)
    with pytest.raises(ValueError,match='gate'):
        signed.verify_artifacts(receipt,source)


def test_staged_final_release_cannot_prepare_before_acceptance(tmp_path,keys,trust):
    source=tmp_path/'source'
    envelope=manifest(source,keys[0],version='1.0.0')
    release=manager(tmp_path,trust)
    with pytest.raises(ValueError,match='acceptance'):
        release.stage(envelope,source,now_unix=NOW)
    with release._db() as db:
        assert db.execute('SELECT count(*) FROM releases').fetchone()[0]==0
    assert not list(release.environments.iterdir())
