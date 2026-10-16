"""Pinned-key offline release manifests and durable issuer administration.

Ed25519 authenticates an explicitly enrolled release key. It does not establish a
human identity, safe package code, reproducible source build, or scientific truth.
Clock input comes from the caller. The durable floor rejects times below the
last successful authenticated verification; rejected/expired messages do not
advance it. This is not a trusted time service or a record of every observed time. Database administrators remain
trusted. No network request, private-key persistence, or release publication occurs.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from verify_wheel import verify_wheel

CONTEXT = 'Nabla-offline-release-manifest-v1'
MAX_MANIFEST_BYTES = 32_768
MAX_WHEEL_BYTES = 64 * 1024 * 1024
MAX_SBOM_BYTES = 2 * 1024 * 1024
MAX_SEQUENCE = 2**53 - 1
MAX_LIFETIME = 366 * 86400
MAX_KEYS = 128
_TOKEN = re.compile(r'[A-Za-z0-9][A-Za-z0-9._+-]{0,127}\Z')


def _database_path(path):
    path = Path(path).absolute()
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError('Trust database path cannot contain symlinks')
    if path.exists() and not path.is_file():
        raise ValueError('Trust database must be a regular file')
    return path


def _json(value):
    """Bounded JSON-native encoding; no floats, duplicate fields or coercion."""
    remaining = 4096

    def visit(item, depth=0):
        nonlocal remaining
        remaining -= 1
        if depth > 16 or remaining < 0:
            raise ValueError('Release JSON structural budget exceeded')
        if item is None or type(item) is bool or type(item) is str:
            return
        if type(item) is int and item.bit_length() <= 64:
            return
        if type(item) is list:
            for child in item:
                visit(child, depth+1)
            return
        if type(item) is dict and all(type(key) is str for key in item):
            for child in item.values():
                visit(child, depth+1)
            return
        raise ValueError('Release JSON requires bounded native values without floats')

    visit(value)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise ValueError('Release manifest byte budget exceeded')
    return encoded


def _load(raw):
    if type(raw) is not bytes or len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError('Bounded release manifest bytes required')

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate release JSON field')
            result[key] = value
        return result

    try:
        data = json.loads(raw, object_pairs_hook=pairs)
        _json(data)
        return data
    except (UnicodeError, RecursionError, OverflowError) as exc:
        raise ValueError('Invalid release JSON') from exc


def _fields(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError('Unexpected release fields')


def _text(value, label, limit=256):
    if (type(value) is not str or not value.strip() or len(value) > limit
            or any(ord(c) < 32 for c in value)):
        raise ValueError('Invalid ' + label)
    return value


def _integer(value, label, minimum=0, maximum=MAX_SEQUENCE):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Invalid ' + label)
    return value


def _hex(value, length, label):
    if (type(value) is not str or len(value) != length
            or any(c not in '0123456789abcdef' for c in value)):
        raise ValueError('Invalid ' + label)
    return value


def _token(value, label):
    if type(value) is not str or not _TOKEN.fullmatch(value):
        raise ValueError('Invalid ' + label)
    return value


def _filename(value, suffix):
    _text(value, 'artifact filename', 240)
    path = PurePosixPath(value)
    if (len(path.parts) != 1 or value in {'.', '..'} or '/' in value
            or '\\' in value or ':' in value or not value.endswith(suffix)
            or path.as_posix() != value):
        raise ValueError('Artifact must have a plain local filename')
    return value


def _crypto():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey, Ed25519PublicKey)
        from cryptography.hazmat.primitives import serialization
    except ImportError as exc:
        raise RuntimeError('Optional cryptography is required for signed releases') from exc
    return Ed25519PrivateKey, Ed25519PublicKey, serialization


def public_hex(private_key):
    _, _, serialization = _crypto()
    return private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def key_id(public_key):
    _hex(public_key, 64, 'Ed25519 public key')
    return hashlib.sha256(bytes.fromhex(public_key)).hexdigest()


def _validate_artifact(row, *, suffix, maximum):
    _fields(row, {'filename', 'sha256', 'size'})
    _filename(row['filename'], suffix)
    _hex(row['sha256'], 64, 'artifact SHA256')
    _integer(row['size'], 'artifact size', 1, maximum)


def validate_body(body):
    """Validate the full signed statement before decoding signatures or keys."""
    encoded = _json(body)
    _fields(body, {'schema', 'context', 'issuer', 'key_id', 'public_key', 'channel',
                   'package', 'version', 'sequence', 'issued_unix', 'expires_unix',
                   'source', 'python', 'wheel', 'sbom'})
    if body['schema'] != 'nabla.signed-release.v1' or body['context'] != CONTEXT:
        raise ValueError('Wrong release schema or signature domain')
    for field in ('issuer', 'channel', 'version'):
        _token(body[field], field)
    if body['package'] != 'nablamath':
        raise ValueError('Only nablamath releases are accepted')
    _hex(body['public_key'], 64, 'Ed25519 public key')
    if body['key_id'] != key_id(body['public_key']):
        raise ValueError('Release key identity mismatch')
    _integer(body['sequence'], 'release sequence', 1)
    issued = _integer(body['issued_unix'], 'release issue time')
    expires = _integer(body['expires_unix'], 'release expiry')
    if not 1 <= expires-issued <= MAX_LIFETIME:
        raise ValueError('Invalid release lifetime')
    source = body['source']
    _fields(source, {'repository', 'commit', 'binding'})
    if (type(source['repository']) is not str or not source['repository'].startswith('https://')
            or len(source['repository']) > 2048 or any(c.isspace() for c in source['repository'])):
        raise ValueError('Explicit HTTPS source repository required')
    _hex(source['commit'], 40, 'source commit')
    if source['binding'] != 'issuer-declared-not-reproduced':
        raise ValueError('Source binding must state its verification limit')
    py = body['python']
    _fields(py, {'minimum', 'maximum_exclusive'})
    for version in py.values():
        if (type(version) is not list or len(version) != 2
                or any(type(n) is not int or not 0 <= n <= 99 for n in version)):
            raise ValueError('Explicit major/minor Python bounds required')
    if not (3, 10) <= tuple(py['minimum']) < tuple(py['maximum_exclusive']) <= (4, 0):
        raise ValueError('Invalid supported Python interval')
    _validate_artifact(body['wheel'], suffix='.whl', maximum=MAX_WHEEL_BYTES)
    _validate_artifact(body['sbom'], suffix='.json', maximum=MAX_SBOM_BYTES)
    if body['wheel']['filename'] == body['sbom']['filename']:
        raise ValueError('Distinct wheel and SBOM filenames required')
    return encoded


def sign_release(body, private_key):
    """Create a detached envelope using a caller-owned key; never writes the key."""
    data = _load(_json(body))
    if data.get('public_key') != public_hex(private_key):
        raise ValueError('Signing key differs from declared release key')
    encoded = validate_body(data)
    return {'body': data, 'signature': private_key.sign(encoded).hex()}


@dataclass(frozen=True)
class VerifiedRelease:
    """A detached validated receipt, reverified by stage/activate operations.

    Constructing this data class is not an authorization boundary. Every mutating
    lifecycle operation rechecks the underlying signed envelope against live trust.
    """
    envelope_json: bytes
    manifest_id: str
    authorization_json: bytes | None = None

    @property
    def body(self):
        return _load(self.envelope_json)['body']

    def to_data(self):
        return _load(self.envelope_json)


def load_envelope(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Release manifest symlink not allowed')
    with path.open('rb') as stream:
        raw = stream.read(MAX_MANIFEST_BYTES+1)
    return _load(raw)


class IssuerTrust:
    """Locally administered durable pin/revoke records with per-key channels.

    Trust enrollment must be performed over a separately authenticated channel.
    Revocation is permanent for a key id. Rotation means enrolling a distinct key
    and optionally revoking the predecessor; it never silently unrevokes a key.
    The clock floor advances only on accepted authenticated verifications, so an
    invalid envelope cannot force a future floor. Trusted current time remains
    the caller's responsibility, including after observing an expired envelope.
    """
    def __init__(self, path):
        self.path = _database_path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS issuers ('
                       'issuer TEXT NOT NULL, key_id TEXT NOT NULL, public_key TEXT NOT NULL, '
                       'channels TEXT NOT NULL, not_before INTEGER NOT NULL, '
                       'expires INTEGER NOT NULL, revoked INTEGER NOT NULL DEFAULT 0, '
                       'PRIMARY KEY(issuer,key_id))')
            db.execute('CREATE TABLE IF NOT EXISTS trust_clock '
                       '(singleton INTEGER PRIMARY KEY CHECK(singleton=1), last_unix INTEGER NOT NULL)')
            db.execute('INSERT OR IGNORE INTO trust_clock VALUES (1,0)')

    @contextmanager
    def connection(self):
        _database_path(self.path)
        if self.path.exists() and self.path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Issuer trust database exceeds budget')
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute('PRAGMA synchronous=FULL')
            with db:
                yield db
        finally:
            db.close()

    def enroll(self, *, issuer, public_key, channels, not_before, expires_unix):
        _token(issuer, 'issuer')
        identifier = key_id(public_key)
        if type(channels) not in (list, tuple) or not 1 <= len(channels) <= 16:
            raise ValueError('One to sixteen explicit release channels required')
        for channel in channels:
            _token(channel, 'channel')
        if len(set(channels)) != len(channels):
            raise ValueError('Duplicate release channel')
        _integer(not_before, 'issuer not-before')
        _integer(expires_unix, 'issuer expiry')
        if not not_before < expires_unix:
            raise ValueError('Issuer trust interval must be nonempty')
        values = (public_key, json.dumps(sorted(channels)), not_before, expires_unix)
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute('SELECT public_key,channels,not_before,expires,revoked '
                                 'FROM issuers WHERE issuer=? AND key_id=?',
                                 (issuer, identifier)).fetchone()
            if current:
                if tuple(current[:4]) != values or current[4]:
                    raise ValueError('Pinned key is immutable or revoked')
                return False
            if db.execute('SELECT count(*) FROM issuers').fetchone()[0] >= MAX_KEYS:
                raise ValueError('Issuer trust capacity exhausted')
            db.execute('INSERT INTO issuers VALUES (?,?,?,?,?,?,0)',
                       (issuer, identifier, *values))
            return True

    def revoke(self, issuer, identifier):
        _token(issuer, 'issuer')
        _hex(identifier, 64, 'key id')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT revoked FROM issuers WHERE issuer=? AND key_id=?',
                             (issuer, identifier)).fetchone()
            if row is None:
                raise ValueError('Cannot revoke an unknown issuer key')
            db.execute('UPDATE issuers SET revoked=1 WHERE issuer=? AND key_id=?',
                       (issuer, identifier))
            return row[0] == 0

    def verify(self, envelope, *, now_unix):
        _integer(now_unix, 'verification time')
        detached = _load(_json(envelope))
        _fields(detached, {'body', 'signature'})
        signature = _hex(detached['signature'], 128, 'Ed25519 release signature')
        body = detached['body']
        encoded = validate_body(body)
        if not body['issued_unix'] <= now_unix < body['expires_unix']:
            raise ValueError('Release is expired or not yet valid')
        if not tuple(body['python']['minimum']) <= sys.version_info[:2] < tuple(body['python']['maximum_exclusive']):
            raise ValueError('Interpreter outside signed release compatibility interval')
        _, public, _ = _crypto()
        from cryptography.exceptions import InvalidSignature
        try:
            public.from_public_bytes(bytes.fromhex(body['public_key'])).verify(
                bytes.fromhex(signature), encoded)
        except InvalidSignature as exc:
            raise ValueError('Invalid release signature') from exc
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            clock_row = db.execute('SELECT last_unix FROM trust_clock WHERE singleton=1').fetchone()
            if clock_row is None:
                raise ValueError('Release verifier clock state missing')
            last_time = clock_row[0]
            if type(last_time) is not int or now_unix < last_time:
                raise ValueError('Release verifier clock regressed or clock state corrupted')
            row = db.execute('SELECT public_key,channels,not_before,expires,revoked '
                             'FROM issuers WHERE issuer=? AND key_id=?',
                             (body['issuer'], body['key_id'])).fetchone()
            if row is None or row[0] != body['public_key'] or row[4] != 0:
                raise ValueError('Unknown or revoked release issuer')
            _integer(row[2], 'stored issuer not-before')
            _integer(row[3], 'stored issuer expiry')
            if (not row[2] <= now_unix < row[3] or body['issued_unix'] < row[2]
                    or body['expires_unix'] > row[3]):
                raise ValueError('Release exceeds issuer trust validity')
            if body['channel'] not in _load_channels(row[1]):
                raise ValueError('Issuer not trusted for this channel')
            db.execute('UPDATE trust_clock SET last_unix=? WHERE singleton=1', (now_unix,))
        return VerifiedRelease(_json(detached), hashlib.sha256(encoded).hexdigest())


def _load_channels(encoded):
    if type(encoded) is not str or len(encoded) > 4096:
        raise ValueError('Issuer channel state corrupted')
    channels = json.loads(encoded)
    if type(channels) is not list or not 1 <= len(channels) <= 16:
        raise ValueError('Issuer channel state corrupted')
    for channel in channels:
        _token(channel, 'channel')
    return channels


def _regular_artifact(directory, row):
    directory = Path(directory).resolve()
    path = directory / row['filename']
    if path.is_symlink() or not path.is_file():
        raise ValueError('Regular local release artifact required')
    expected = row['size']
    if path.stat().st_size != expected:
        raise ValueError('Signed artifact size mismatch')
    with path.open('rb') as stream:
        content = stream.read(expected+1)
    if len(content) != expected or hashlib.sha256(content).hexdigest() != row['sha256']:
        raise ValueError('Signed artifact hash mismatch')
    return path


def verify_artifacts(receipt, directory):
    """Verify exact signed bytes, wheel RECORD, pure-Python layout and SBOM binding.

    The wheel may contain executable Python belonging to the trusted publisher.
    This profile refuses installation hooks, .pth files, scripts and binary wheels;
    it does not sandbox package imports or claim code review of signed content.
    """
    if not isinstance(receipt, VerifiedRelease):
        raise ValueError('Verified release receipt required')
    body = receipt.body
    validate_body(body)
    if hashlib.sha256(validate_body(body)).hexdigest() != receipt.manifest_id:
        raise ValueError('Release receipt identity mismatch')
    wheel = _regular_artifact(directory, body['wheel'])
    sbom = _regular_artifact(directory, body['sbom'])
    wheel_result = verify_wheel(wheel)
    if wheel_result['name'] != body['package'] or wheel_result['version'] != body['version']:
        raise ValueError('Signed package identity differs from wheel metadata')
    with zipfile.ZipFile(wheel) as archive:
        infos = [name for name in archive.namelist() if name.endswith('.dist-info/WHEEL')]
        from email.parser import BytesParser
        metadata = BytesParser().parsebytes(archive.read(infos[0]))
        if metadata.get_all('Tag') != ['py3-none-any'] or metadata.get('Root-Is-Purelib', '').lower() != 'true':
            raise ValueError('Only pure Python py3-none-any releases are accepted')
        prefix = infos[0].rsplit('/', 1)[0] + '/'
        for name in archive.namelist():
            if not (name.startswith('nablamath/') or name.startswith(prefix)):
                raise ValueError('Release wheel contains an undeclared installation target')
            if name.endswith(('.pth', '.so', '.pyd', '.dll', '.dylib')):
                raise ValueError('Release wheel contains executable install hooks or native code')
    with sbom.open('rb') as stream:
        raw = stream.read(MAX_SBOM_BYTES+1)
    try:
        inventory = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise ValueError('Invalid signed SBOM JSON') from exc
    if type(inventory) is not dict or inventory.get('spdxVersion') != 'SPDX-2.3':
        raise ValueError('SPDX 2.3 SBOM required')
    packages = inventory.get('packages')
    if type(packages) is not list or len(packages) != 1:
        raise ValueError('One wheel package must be described by the SBOM')
    package = packages[0]
    if (type(package) is not dict or package.get('name') != body['package']
            or package.get('versionInfo') != body['version']
            or package.get('checksums') != [{'algorithm': 'SHA256', 'checksumValue': body['wheel']['sha256']}]
            or package.get('sourceInfo') != 'Declared source commit: ' + body['source']['commit']):
        raise ValueError('SBOM does not bind the signed wheel and declared source')
    return {'manifest_id': receipt.manifest_id, 'wheel': str(wheel), 'sbom': str(sbom),
            'wheel_sha256': body['wheel']['sha256'], 'artifact_identity_verified': True,
            'issuer_trust_rechecked': False,
            'source_build_reproduced': False, 'scientific_validation': False}


ROOT_CONTEXT = 'Nabla-release-trust-root-v1'
APPROVAL_CONTEXT = 'Nabla-release-approval-v1'
MAX_ROOT_KEYS = 24


def validate_root(body):
    encoded = _json(body)
    _fields(body, {'schema', 'context', 'authority', 'version', 'issued_unix',
                   'expires_unix', 'keys', 'root_keys', 'root_threshold', 'delegations'})
    if body['schema'] != 'nabla.release-root.v1' or body['context'] != ROOT_CONTEXT:
        raise ValueError('Wrong delegated release root domain')
    _token(body['authority'], 'root authority')
    _integer(body['version'], 'root version', 1)
    issued = _integer(body['issued_unix'], 'root issue time')
    expires = _integer(body['expires_unix'], 'root expiry')
    if not 1 <= expires-issued <= 5 * MAX_LIFETIME:
        raise ValueError('Invalid root lifetime')
    keys = body['keys']
    if type(keys) is not dict or not 2 <= len(keys) <= MAX_ROOT_KEYS:
        raise ValueError('Two to twenty-four explicit trust keys required')
    for identifier, public in keys.items():
        if key_id(public) != identifier:
            raise ValueError('Root key identity mismatch')
    roots = body['root_keys']
    if (type(roots) is not list or not 1 <= len(roots) <= 8
            or any(type(item) is not str or item not in keys for item in roots)
            or len(set(roots)) != len(roots)):
        raise ValueError('Explicit unique root key identities required')
    _integer(body['root_threshold'], 'root threshold', 1, len(roots))
    delegations = body['delegations']
    if type(delegations) is not list or not 1 <= len(delegations) <= 16:
        raise ValueError('One to sixteen explicit issuer/channel delegations required')
    pairs = set()
    used = set(roots)
    for delegation in delegations:
        _fields(delegation, {'issuer', 'channel', 'threshold', 'key_ids'})
        identity = (_token(delegation['issuer'], 'delegated issuer'),
                    _token(delegation['channel'], 'delegated channel'))
        if identity in pairs:
            raise ValueError('Duplicate issuer/channel delegation')
        pairs.add(identity)
        ids = delegation['key_ids']
        if (type(ids) is not list or not 1 <= len(ids) <= 8
                or any(type(item) is not str or item not in keys for item in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError('Explicit unique delegated signing keys required')
        if set(ids) & set(roots):
            raise ValueError('Root administration keys cannot sign publisher releases')
        _integer(delegation['threshold'], 'publisher approval threshold', 1, len(ids))
        used.update(ids)
    if used != set(keys):
        raise ValueError('Trust root contains an unassigned key')
    return encoded


def sign_root(body, private_keys):
    """Sign an administrative root using ephemeral or externally held keys."""
    detached = _load(validate_root(body))
    if type(private_keys) not in (list, tuple) or not 1 <= len(private_keys) <= 16:
        raise ValueError('Bounded root signing key list required')
    encoded = validate_root(detached)
    signatures = []
    identifiers = set()
    for key in private_keys:
        identifier = key_id(public_hex(key))
        if identifier in identifiers:
            raise ValueError('Duplicate root signing key')
        identifiers.add(identifier)
        signatures.append({'key_id': identifier, 'signature': key.sign(encoded).hex()})
    return {'body': detached, 'signatures': sorted(signatures, key=lambda row: row['key_id'])}


def _verify_signatures(signatures, encoded, keys):
    if type(signatures) is not list or not 1 <= len(signatures) <= 16:
        raise ValueError('One to sixteen detached signatures required')
    _, public, _ = _crypto()
    from cryptography.exceptions import InvalidSignature
    valid = set()
    seen = set()
    for signature in signatures:
        _fields(signature, {'key_id', 'signature'})
        identifier = _hex(signature['key_id'], 64, 'signature key identity')
        value = _hex(signature['signature'], 128, 'detached signature')
        if identifier in seen:
            raise ValueError('Duplicate signatures cannot satisfy a threshold')
        seen.add(identifier)
        if identifier not in keys:
            raise ValueError('Signature from a key outside the declared trust policy')
        try:
            public.from_public_bytes(bytes.fromhex(keys[identifier])).verify(bytes.fromhex(value), encoded)
        except InvalidSignature as exc:
            raise ValueError('Invalid delegated release signature') from exc
        valid.add(identifier)
    return valid


def approval_statement(envelope, root_version):
    _fields(envelope, {'body', 'signature'})
    body = envelope['body']
    encoded = validate_body(body)
    _integer(root_version, 'approval root version', 1)
    return {'context': APPROVAL_CONTEXT, 'root_version': root_version,
            'manifest_id': hashlib.sha256(encoded).hexdigest(), 'issuer': body['issuer'],
            'channel': body['channel'], 'expires_unix': body['expires_unix']}


def approve_release(envelope, *, root_version, private_keys):
    """Bind independent release approvals to exact bytes and a root policy version."""
    detached = _load(_json(envelope))
    statement = approval_statement(detached, root_version)
    encoded = _json(statement)
    if type(private_keys) not in (list, tuple) or not 1 <= len(private_keys) <= 8:
        raise ValueError('One to eight release approval keys required')
    signatures = []
    seen = set()
    for private_key in private_keys:
        identifier = key_id(public_hex(private_key))
        if identifier in seen:
            raise ValueError('Duplicate release approver')
        seen.add(identifier)
        signatures.append({'key_id': identifier, 'signature': private_key.sign(encoded).hex()})
    return {'schema': 'nabla.threshold-release.v1', 'root_version': root_version,
            'release': detached, 'approvals': sorted(signatures, key=lambda row: row['key_id'])}


class DelegatedPublisherTrust:
    """Versioned offline root with independent threshold release approvals.

    Bootstrap requires a separately authenticated SHA256 of the complete root
    envelope. Root rotation is signed by thresholds of BOTH old and new root
    keys, advances exactly one version, and changes delegated publisher policy.
    All previously approved bundles must be reapproved after root rotation.
    Removed publisher keys are revoked by the new version. There is no network
    discovery, trusted timestamp, recovery bypass or automatic root replacement.
    Clock floors record accepted verification/root-rotation times; rejected expired
    envelopes do not advance them, and caller clock correctness is not established.
    """
    def __init__(self, path):
        self.path = _database_path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS trust_root '
                       '(singleton INTEGER PRIMARY KEY CHECK(singleton=1), '
                       'version INTEGER NOT NULL, envelope TEXT NOT NULL, '
                       'root_hash TEXT NOT NULL, last_unix INTEGER NOT NULL)')

    @contextmanager
    def connection(self):
        _database_path(self.path)
        if self.path.exists() and self.path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Delegated trust database exceeds budget')
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute('PRAGMA synchronous=FULL')
            with db:
                yield db
        finally:
            db.close()

    def _root(self, db, now):
        _integer(now, 'delegated verification time')
        row = db.execute('SELECT version,substr(envelope,1,32769),root_hash,last_unix '
                         'FROM trust_root WHERE singleton=1').fetchone()
        if row is None:
            raise ValueError('No authenticated release trust root bootstrapped')
        if type(row[1]) is not str or len(row[1].encode()) > MAX_MANIFEST_BYTES:
            raise ValueError('Stored release root exceeds byte budget')
        envelope = _load(row[1].encode())
        _fields(envelope, {'body', 'signatures'})
        body = envelope['body']
        validate_root(body)
        if row[0] != body['version'] or hashlib.sha256(_json(envelope)).hexdigest() != row[2]:
            raise ValueError('Stored release root commitment corrupted')
        if type(row[3]) is not int or now < row[3]:
            raise ValueError('Delegated release clock regressed')
        if not body['issued_unix'] <= now < body['expires_unix']:
            raise ValueError('Delegated release trust root expired or future')
        # Revalidate the root's self threshold to reject corrupted rows, while
        # acknowledging an administrator can replace every local trust anchor.
        root_keys = {identifier: body['keys'][identifier] for identifier in body['root_keys']}
        # Rotation envelopes may carry predecessor signatures. Only current
        # roots count in this self check; predecessors were checked on rotation.
        current = [sig for sig in envelope['signatures'] if sig.get('key_id') in root_keys]
        valid = _verify_signatures(current, validate_root(body), root_keys)
        if len(valid) < body['root_threshold']:
            raise ValueError('Stored root lacks its own signing threshold')
        return envelope

    def bootstrap(self, envelope, *, expected_sha256, now_unix):
        _hex(expected_sha256, 64, 'pinned trust-root digest')
        detached = _load(_json(envelope))
        _fields(detached, {'body', 'signatures'})
        body = detached['body']
        encoded = validate_root(body)
        if hashlib.sha256(_json(detached)).hexdigest() != expected_sha256:
            raise ValueError('Root differs from out-of-band pinned digest')
        if body['version'] != 1:
            raise ValueError('Bootstrap root must start at version one')
        _integer(now_unix, 'bootstrap time')
        if not body['issued_unix'] <= now_unix < body['expires_unix']:
            raise ValueError('Bootstrap root is expired or future')
        roots = {identifier: body['keys'][identifier] for identifier in body['root_keys']}
        valid = _verify_signatures(detached['signatures'], encoded, roots)
        if len(valid) < body['root_threshold']:
            raise ValueError('Bootstrap root signing threshold not met')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT count(*) FROM trust_root').fetchone()[0]:
                raise ValueError('Trust root already bootstrapped; use dual-threshold rotation')
            db.execute('INSERT INTO trust_root VALUES (1,?,?,?,?)',
                       (1, _json(detached).decode(), expected_sha256, now_unix))
        return {'root_version': 1, 'root_sha256': expected_sha256,
                'out_of_band_pin_authenticated_by_caller': True}

    def rotate(self, envelope, *, now_unix):
        detached = _load(_json(envelope))
        _fields(detached, {'body', 'signatures'})
        next_body = detached['body']
        encoded = validate_root(next_body)
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            current = self._root(db, now_unix)['body']
            if next_body['authority'] != current['authority'] or next_body['version'] != current['version']+1:
                raise ValueError('Root rotation must preserve authority and advance one version')
            if (not next_body['issued_unix'] <= now_unix < next_body['expires_unix']
                    or next_body['issued_unix'] < current['issued_unix']):
                raise ValueError('Invalid root rotation validity interval')
            old_keys = {identifier: current['keys'][identifier] for identifier in current['root_keys']}
            new_keys = {identifier: next_body['keys'][identifier] for identifier in next_body['root_keys']}
            valid = _verify_signatures(detached['signatures'], encoded, {**old_keys, **new_keys})
            if (len(valid & set(old_keys)) < current['root_threshold']
                    or len(valid & set(new_keys)) < next_body['root_threshold']):
                raise ValueError('Root rotation requires both predecessor and successor thresholds')
            root_hash = hashlib.sha256(_json(detached)).hexdigest()
            db.execute('UPDATE trust_root SET version=?,envelope=?,root_hash=?,last_unix=? WHERE singleton=1',
                       (next_body['version'], _json(detached).decode(), root_hash, now_unix))
        return {'root_version': next_body['version'], 'root_sha256': root_hash,
                'previous_approvals_invalidated': True}

    def verify(self, bundle, *, now_unix):
        detached = _load(_json(bundle))
        _fields(detached, {'schema', 'root_version', 'release', 'approvals'})
        if detached['schema'] != 'nabla.threshold-release.v1':
            raise ValueError('Threshold release approval bundle required')
        _integer(detached['root_version'], 'release root version', 1)
        envelope = detached['release']
        statement = approval_statement(envelope, detached['root_version'])
        body = envelope['body']
        signature = _hex(envelope['signature'], 128, 'primary release signature')
        _, public, _ = _crypto()
        from cryptography.exceptions import InvalidSignature
        try:
            public.from_public_bytes(bytes.fromhex(body['public_key'])).verify(
                bytes.fromhex(signature), validate_body(body))
        except InvalidSignature as exc:
            raise ValueError('Invalid primary release signature') from exc
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            root = self._root(db, now_unix)['body']
            if detached['root_version'] != root['version']:
                raise ValueError('Release approval uses stale or unknown root version')
            if (not body['issued_unix'] <= now_unix < body['expires_unix']
                    or body['issued_unix'] < root['issued_unix']
                    or body['expires_unix'] > root['expires_unix']):
                raise ValueError('Release validity exceeds current delegation')
            if not tuple(body['python']['minimum']) <= sys.version_info[:2] < tuple(body['python']['maximum_exclusive']):
                raise ValueError('Interpreter outside delegated release compatibility interval')
            policy = next((item for item in root['delegations']
                           if item['issuer'] == body['issuer'] and item['channel'] == body['channel']), None)
            if policy is None:
                raise ValueError('No publisher delegation for this issuer/channel')
            keys = {identifier: root['keys'][identifier] for identifier in policy['key_ids']}
            if body['key_id'] not in keys or keys[body['key_id']] != body['public_key']:
                raise ValueError('Primary release signer is not delegated or has been revoked')
            valid = _verify_signatures(detached['approvals'], _json(statement), keys)
            if len(valid) < policy['threshold']:
                raise ValueError('Publisher release approval threshold not met')
            if body['key_id'] not in valid:
                raise ValueError('Primary publisher must also explicitly approve this release')
            db.execute('UPDATE trust_root SET last_unix=? WHERE singleton=1', (now_unix,))
        return VerifiedRelease(_json(envelope), statement['manifest_id'], _json(detached))

    def describe(self, *, now_unix):
        with self.connection() as db:
            body = self._root(db, now_unix)['body']
            return _load(_json({'authority': body['authority'], 'version': body['version'],
                               'root_threshold': body['root_threshold'],
                               'delegations': body['delegations'],
                               'expires_unix': body['expires_unix']}))
