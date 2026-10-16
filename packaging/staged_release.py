"""Crash-recoverable offline venv releases with an atomic active pointer.

The active environment is a SQLite pointer, not an overwritten installation or a
mutable symlink. Consumers ask ``active_environment`` for the environment to run.
A committed activation transaction updates that pointer and its journal together.
Prepared environments are never made active before installation and smoke checks.

This implementation requires POSIX file locks and is tested on the current Linux
host. It is not a cross-platform installer, process sandbox, public release or
protection against an administrator rewriting both the database and artifact store.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
from threading import Thread, Event
import sqlite3
import subprocess
import sys
import venv

_MODULE = '_nabla_signed_offline_release'
if _MODULE in sys.modules:
    signed = sys.modules[_MODULE]
else:
    _spec = importlib.util.spec_from_file_location(
        _MODULE, Path(__file__).with_name('signed_release.py'))
    signed = importlib.util.module_from_spec(_spec)
    sys.modules[_MODULE] = signed
    _spec.loader.exec_module(signed)

MAX_RELEASES = 128
MAX_EVENTS = 4096
MAX_STATE_BYTES = 32 * 1024 * 1024
SMOKE_CODE = (
    'import importlib.metadata as m, json, sys; '
    'import nablamath; '
    'print(json.dumps({"version":m.version("nablamath"),'
    '"prefix":sys.prefix,"module":nablamath.__file__},sort_keys=True))'
)


def _plain_directory(path, *, create=False):
    path = Path(path).absolute()
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError('Release state directories cannot contain symlinks')
    if path in {Path('/'), Path(sys.prefix), Path.home()}:
        raise ValueError('Dedicated release directory required')
    if create:
        path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise ValueError('Release state directory missing')
    return path


def _file_hash(path, maximum):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError('Expected bounded regular release file')
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        count = 0
        while block := stream.read(1024 * 1024):
            count += len(block)
            if count > maximum:
                raise ValueError('Release file exceeds byte budget')
            sha.update(block)
    return sha.hexdigest(), count


def _atomic_json(path, value):
    encoded = signed._json(value)
    temporary = path.with_name(path.name + '.writing')
    if temporary.exists() or temporary.is_symlink():
        raise ValueError('Unexpected release marker temporary file')
    try:
        with temporary.open('xb') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.is_file() and not temporary.is_symlink():
            temporary.unlink()


def _run_bounded(command, *, timeout, output_limit, environment):
    """Bound pipe memory and kill the child process group on overflow/timeout.

    This is lifecycle hygiene, not CPU/memory isolation for package code. The
    command is assembled internally from fixed probes and verified wheel paths.
    """
    if type(output_limit) is not int or not 1 <= output_limit <= 1024*1024:
        raise ValueError('Invalid subprocess output budget')
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=environment, start_new_session=True)
    overflow = Event()
    chunks = {'stdout': bytearray(), 'stderr': bytearray()}

    def terminate_group():
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def read_stream(name, stream):
        try:
            while True:
                block = stream.read1(8192)
                if not block:
                    break
                remaining = output_limit+1-len(chunks[name])
                if remaining > 0:
                    chunks[name].extend(block[:remaining])
                if len(chunks[name]) > output_limit:
                    overflow.set()
                    terminate_group()
                    break
        finally:
            stream.close()

    readers = [Thread(target=read_stream, args=(name, stream), daemon=True)
               for name, stream in [('stdout', process.stdout), ('stderr', process.stderr)]]
    for reader in readers:
        reader.start()
    try:
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            terminate_group()
            process.wait(timeout=5)
            raise ValueError('Release subprocess timed out') from exc
        # A descendant retaining output descriptors must not block the release
        # manager indefinitely after its parent exits.
        for reader in readers:
            reader.join(timeout=1)
        if any(reader.is_alive() for reader in readers):
            terminate_group()
            for reader in readers:
                reader.join(timeout=1)
            raise ValueError('Release subprocess left inherited output streams open')
        if overflow.is_set():
            raise ValueError('Release subprocess output exceeds budget')
        return subprocess.CompletedProcess(command, returncode,
            bytes(chunks['stdout']).decode('utf-8', errors='replace'),
            bytes(chunks['stderr']).decode('utf-8', errors='replace'))
    finally:
        if process.poll() is None:
            terminate_group()
            process.wait(timeout=5)
        for reader in readers:
            reader.join(timeout=1)



class ReleaseManager:
    """One locally configured channel and issuer per installation store.

    ``sequence`` is a publisher-issued monotonically increasing integer, separate
    from packaging version spelling. Manual rollback only selects a previously
    activated release and never reduces that durable anti-rollback high-water.
    Reinstalling an older release through the update path stays forbidden.
    """
    def __init__(self, root, trust, *, issuer, channel, checkpoint=None, checkpoint_sha256=None):
        if os.name != 'posix':
            raise NotImplementedError('This staged release profile requires POSIX file locking')
        if not isinstance(trust, (signed.IssuerTrust, signed.DelegatedPublisherTrust)):
            raise ValueError('Explicit issuer trust store required')
        signed._token(issuer, 'issuer')
        signed._token(channel, 'channel')
        self.root = _plain_directory(root, create=True)
        self.trust, self.issuer, self.channel = trust, issuer, channel
        self._checkpoint = None
        if (checkpoint is None) != (checkpoint_sha256 is None):
            raise ValueError('Checkpoint data and separately pinned digest must be supplied together')
        if checkpoint is not None:
            self._checkpoint = self._validate_checkpoint(checkpoint, checkpoint_sha256)
        self.path = self.root / 'state.sqlite3'
        self.environments = _plain_directory(self.root / 'environments', create=True)
        self.artifacts = _plain_directory(self.root / 'artifacts', create=True)
        with self._lock(), self._db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS configuration (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    issuer TEXT NOT NULL, channel TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS state (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    active_id TEXT, high_sequence INTEGER NOT NULL,
                    high_manifest_id TEXT, last_unix INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS releases (
                    id TEXT PRIMARY KEY, sequence INTEGER NOT NULL UNIQUE,
                    version TEXT NOT NULL, envelope TEXT NOT NULL,
                    status TEXT NOT NULL, ever_active INTEGER NOT NULL DEFAULT 0,
                    inventory TEXT, failure TEXT);
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    previous_hash TEXT, record TEXT NOT NULL, record_hash TEXT NOT NULL);
            ''')
            current = db.execute('SELECT issuer,channel FROM configuration WHERE singleton=1').fetchone()
            if current is None:
                db.execute('INSERT INTO configuration VALUES (1,?,?)', (issuer, channel))
                db.execute('INSERT INTO state VALUES (1,NULL,0,NULL,0)')
            elif tuple(current) != (issuer, channel):
                raise ValueError('Release store belongs to a different issuer or channel')
            self._state(db)
            if self._checkpoint is not None:
                self._verify_checkpoint_record(db, self._checkpoint)

    @contextmanager
    def _lock(self):
        _plain_directory(self.root)
        _plain_directory(self.environments)
        _plain_directory(self.artifacts)
        import fcntl
        path = self.root / 'operation.lock'
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError('Another release operation is in progress') from exc
            yield
        finally:
            os.close(descriptor)

    @contextmanager
    def _db(self):
        _plain_directory(self.root)
        if self.path.is_symlink() or (self.path.exists() and self.path.stat().st_size > MAX_STATE_BYTES):
            raise ValueError('Release state database is unsafe or exceeds budget')
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA synchronous=FULL')
            db.execute('PRAGMA foreign_keys=ON')
            with db:
                yield db
        finally:
            db.close()

    def _state(self, db):
        row = db.execute('SELECT * FROM state WHERE singleton=1').fetchone()
        if row is None:
            raise ValueError('Release high-water state missing')
        signed._integer(row['high_sequence'], 'stored high-water sequence')
        signed._integer(row['last_unix'], 'stored clock')
        if row['high_sequence'] == 0:
            if row['high_manifest_id'] is not None or row['active_id'] is not None:
                raise ValueError('Initial release state corrupted')
        else:
            signed._hex(row['high_manifest_id'], 64, 'stored high-water manifest')
            high = db.execute('SELECT sequence FROM releases WHERE id=?',
                              (row['high_manifest_id'],)).fetchone()
            if high is None or high['sequence'] != row['high_sequence']:
                raise ValueError('Release high-water commitment corrupted')
        if row['active_id'] is not None:
            signed._hex(row['active_id'], 64, 'active manifest')
            active = db.execute('SELECT status,ever_active FROM releases WHERE id=?',
                                (row['active_id'],)).fetchone()
            if active is None or active['status'] != 'active' or active['ever_active'] != 1:
                raise ValueError('Active release pointer corrupted')
        maximum_activated = db.execute('SELECT max(sequence) FROM releases WHERE ever_active=1').fetchone()[0] or 0
        if maximum_activated != row['high_sequence']:
            raise ValueError('Release high-water was reduced or activation history corrupted')
        active_rows = db.execute('SELECT count(*) FROM releases WHERE status="active"').fetchone()[0]
        if active_rows != int(row['active_id'] is not None):
            raise ValueError('Release active-state cardinality corrupted')
        return row

    def _observe(self, db, now):
        signed._integer(now, 'release operation time')
        state = self._state(db)
        self._verify_journal(db)
        if self._checkpoint is not None:
            self._verify_checkpoint_record(db, self._checkpoint)
        if now < state['last_unix']:
            raise ValueError('Release operation clock regressed')
        db.execute('UPDATE state SET last_unix=? WHERE singleton=1', (now,))
        return state

    def _event(self, db, kind, manifest_id, *, detail=None):
        if db.execute('SELECT count(*) FROM events').fetchone()[0] >= MAX_EVENTS:
            raise ValueError('Release event capacity exhausted')
        last = db.execute('SELECT record_hash FROM events ORDER BY sequence DESC LIMIT 1').fetchone()
        previous = last[0] if last else None
        record = {'kind': kind, 'manifest_id': manifest_id,
                  'previous': previous, 'detail': detail}
        encoded = signed._json(record).decode()
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        db.execute('INSERT INTO events(previous_hash,record,record_hash) VALUES (?,?,?)',
                   (previous, encoded, digest))
        return digest

    def _verify(self, envelope, now):
        receipt = self.trust.verify(envelope, now_unix=now)
        body = receipt.body
        if body['issuer'] != self.issuer or body['channel'] != self.channel:
            raise ValueError('Release does not belong to this configured issuer/channel')
        return receipt

    def _stored_receipt(self, db, manifest_id, now):
        signed._hex(manifest_id, 64, 'release manifest id')
        row = db.execute('SELECT * FROM releases WHERE id=?', (manifest_id,)).fetchone()
        if row is None or type(row['envelope']) is not str or len(row['envelope']) > signed.MAX_MANIFEST_BYTES:
            raise ValueError('Unknown or corrupted stored release')
        receipt = self._verify(signed._load(row['envelope'].encode()), now)
        body = receipt.body
        if (receipt.manifest_id != manifest_id or body['sequence'] != row['sequence']
                or body['version'] != row['version']):
            raise ValueError('Stored signed release commitment corrupted')
        return receipt, row

    def _environment(self, manifest_id):
        signed._hex(manifest_id, 64, 'release manifest id')
        path = self.environments / manifest_id
        if path.is_symlink():
            raise ValueError('Release environment symlink not allowed')
        return path

    def _artifact_directory(self, manifest_id):
        signed._hex(manifest_id, 64, 'release manifest id')
        directory = self.artifacts / manifest_id
        if directory.is_symlink():
            raise ValueError('Release artifact directory symlink not allowed')
        return directory

    def _copy_artifacts(self, receipt, source):
        signed.verify_artifacts(receipt, source)
        target = self._artifact_directory(receipt.manifest_id)
        target.mkdir()
        try:
            for field in ('wheel', 'sbom'):
                row = receipt.body[field]
                source_file = Path(source) / row['filename']
                destination = target / row['filename']
                with source_file.open('rb') as src, destination.open('xb') as dst:
                    remaining = row['size']
                    while remaining:
                        block = src.read(min(1024 * 1024, remaining))
                        if not block:
                            raise ValueError('Release artifact changed during staging')
                        dst.write(block)
                        remaining -= len(block)
                    if src.read(1):
                        raise ValueError('Release artifact grew during staging')
                    dst.flush()
                    os.fsync(dst.fileno())
            signed.verify_artifacts(receipt, target)
        except BaseException:
            shutil.rmtree(target)
            raise
        return target

    def _inventory(self, environment):
        """Bind all staged files, including pip, configuration and bytecode.

        Interpreter aliases created by venv must resolve to this process's base
        interpreter; other symlinks are refused except venv's internal lib64 alias.
        Cached bytecode is included because -B prevents writes, not cache reads.
        """
        if not environment.is_dir() or environment.is_symlink():
            raise ValueError('Expected a dedicated prepared environment')
        interpreter = Path(sys.executable).resolve()
        aliases = {'python', 'python3', f'python{sys.version_info.major}.{sys.version_info.minor}'}
        records = []
        total = 0
        package_roots = list(environment.glob('lib/python*/site-packages/nablamath'))
        if len(package_roots) != 1 or package_roots[0].is_symlink():
            raise ValueError('Exactly one installed nablamath package required')
        for path in sorted(environment.rglob('*')):
            relative = path.relative_to(environment).as_posix()
            if relative == 'nabla-release.json':
                continue
            if path.is_symlink():
                allowed_interpreter = path.parent == environment/'bin' and path.name in aliases
                allowed_internal = relative == 'lib64' and path.resolve() == (environment/'lib').resolve()
                if not ((allowed_interpreter and path.resolve() == interpreter) or allowed_internal):
                    raise ValueError('Unexpected symlink in staged release environment')
                records.append([relative, 'symlink', os.readlink(path)])
            elif path.is_file():
                sha, size = _file_hash(path, signed.MAX_WHEEL_BYTES)
                total += size
                if total > 256 * 1024 * 1024 or len(records) >= 10000:
                    raise ValueError('Installed release inventory exceeds budget')
                records.append([relative, sha, size])
        return hashlib.sha256(json.dumps(records, separators=(',', ':')).encode()).hexdigest()

    def _python(self, environment):
        path = environment / 'bin/python'
        if not path.is_file() or not (environment / 'pyvenv.cfg').is_file():
            raise ValueError('Staged virtual environment is incomplete')
        return path

    def _smoke(self, environment, version):
        python = self._python(environment)
        # The only executed code is a fixed smoke probe plus the signed package's
        # import. There is no caller-supplied command or setup/build hook.
        process = _run_bounded([str(python), '-I', '-B', '-c', SMOKE_CODE],
                               timeout=30, output_limit=32768,
                               environment=self._subprocess_environment())
        if process.returncode or len(process.stdout) > 32768 or len(process.stderr) > 32768:
            raise ValueError('Staged release import smoke check failed')
        try:
            report = json.loads(process.stdout)
        except ValueError as exc:
            raise ValueError('Unexpected release smoke output') from exc
        if (type(report) is not dict or set(report) != {'version', 'prefix', 'module'}
                or report['version'] != version
                or Path(report['prefix']).absolute() != environment.absolute()
                or not Path(report['module']).resolve().is_relative_to(environment.resolve())):
            raise ValueError('Staged release smoke identity mismatch')
        return report

    def _subprocess_environment(self):
        # Prevent inherited pip configuration, user site and Python injection.
        allowed = ('PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL')
        result = {name: os.environ[name] for name in allowed if name in os.environ}
        result.update({'PIP_CONFIG_FILE': os.devnull, 'PIP_NO_INDEX': '1',
                       'PIP_DISABLE_PIP_VERSION_CHECK': '1', 'PYTHONNOUSERSITE': '1',
                       'PYTHONDONTWRITEBYTECODE': '1'})
        return result

    def _install(self, receipt, artifact_directory, environment):
        if environment.exists():
            raise ValueError('Never overwrite a staged environment')
        venv.EnvBuilder(with_pip=True, clear=False).create(environment)
        wheel = artifact_directory / receipt.body['wheel']['filename']
        command = [str(self._python(environment)), '-I', '-B', '-m', 'pip', 'install',
                   '--isolated', '--no-index', '--no-deps', '--no-compile', str(wheel)]
        process = _run_bounded(command, timeout=120, output_limit=1024*1024,
                               environment=self._subprocess_environment())
        if process.returncode or len(process.stdout) > 1024 * 1024 or len(process.stderr) > 1024 * 1024:
            raise ValueError('Offline wheel installation failed')
        self._smoke(environment, receipt.body['version'])

    def stage(self, envelope, source_directory, *, now_unix):
        """Prepare a distinct environment; never changes the active pointer."""
        receipt = self._verify(envelope, now_unix)
        body, identifier = receipt.body, receipt.manifest_id
        with self._lock():
            with self._db() as db:
                db.execute('BEGIN IMMEDIATE')
                state = self._observe(db, now_unix)
                existing = db.execute('SELECT id,status FROM releases WHERE sequence=?',
                                      (body['sequence'],)).fetchone()
                if existing:
                    if existing['id'] != identifier:
                        raise ValueError('Release sequence equivocation detected')
                    if existing['status'] in {'ready', 'active', 'inactive'}:
                        stored, row = self._stored_receipt(db, identifier, now_unix)
                        self._validate_prepared(stored, row)
                        return self._receipt(db, identifier)
                    raise ValueError('Release staging was interrupted or failed; recover and use a new sequence')
                if body['sequence'] <= state['high_sequence']:
                    raise ValueError('Release would roll back the durable high-water sequence')
                if db.execute('SELECT count(*) FROM releases').fetchone()[0] >= MAX_RELEASES:
                    raise ValueError('Stored release capacity exhausted')
                signed.verify_artifacts(receipt, source_directory)
                db.execute('INSERT INTO releases(id,sequence,version,envelope,status) VALUES (?,?,?,?,?)',
                           (identifier, body['sequence'], body['version'],
                            (receipt.authorization_json or receipt.envelope_json).decode(), 'staging'))
                self._event(db, 'stage-started', identifier)
            # A committed staging record precedes filesystem work. A crash here
            # can be recovered without guessing whether activation occurred.
            try:
                artifacts = self._copy_artifacts(receipt, source_directory)
                environment = self._environment(identifier)
                self._install(receipt, artifacts, environment)
                inventory = self._inventory(environment)
                marker = {'manifest_id': identifier, 'wheel_sha256': body['wheel']['sha256'],
                          'version': body['version'], 'inventory': inventory}
                _atomic_json(environment / 'nabla-release.json', marker)
                with self._db() as db:
                    db.execute('BEGIN IMMEDIATE')
                    db.execute('UPDATE releases SET status="ready",inventory=? WHERE id=? AND status="staging"',
                               (inventory, identifier))
                    self._event(db, 'stage-ready', identifier, detail={'inventory': inventory})
                    return self._receipt(db, identifier)
            except Exception as exc:
                with self._db() as db:
                    db.execute('BEGIN IMMEDIATE')
                    db.execute('UPDATE releases SET status="failed",failure=? WHERE id=?',
                               (type(exc).__name__, identifier))
                    self._event(db, 'stage-failed', identifier, detail={'reason': type(exc).__name__})
                self._remove_unactivated(identifier)
                raise

    def _validate_prepared(self, receipt, row):
        identifier = receipt.manifest_id
        environment = self._environment(identifier)
        if not environment.is_dir():
            raise ValueError('Prepared release environment missing')
        signed.verify_artifacts(receipt, self._artifact_directory(identifier))
        marker_path = environment / 'nabla-release.json'
        marker = signed.load_envelope(marker_path)
        expected = {'manifest_id': identifier, 'wheel_sha256': receipt.body['wheel']['sha256'],
                    'version': receipt.body['version'], 'inventory': row['inventory']}
        if (row['sequence'] != receipt.body['sequence'] or row['version'] != receipt.body['version']
                or row['inventory'] != self._committed_inventory(identifier)):
            raise ValueError('Prepared metadata differs from signed release or preparation journal')
        if marker != expected or self._inventory(environment) != row['inventory']:
            raise ValueError('Prepared release bytes or marker changed')
        self._smoke(environment, receipt.body['version'])

    def _committed_inventory(self, identifier):
        """Keep post-install integrity bound to the original preparation event.

        Changing a mutable row and its filesystem marker must not silently change
        what was recorded as successfully installed. A separately pinned journal
        checkpoint additionally detects coordinated rewriting of the whole store.
        """
        matches = []
        with self._db() as db:
            self._verify_journal(db)
            for row in db.execute('SELECT record FROM events ORDER BY sequence'):
                record = signed._load(row[0].encode())
                if record.get('kind') == 'stage-ready' and record.get('manifest_id') == identifier:
                    detail = record.get('detail')
                    if type(detail) is not dict or set(detail) != {'inventory'}:
                        raise ValueError('Preparation journal inventory record corrupted')
                    matches.append(signed._hex(detail['inventory'], 64, 'preparation inventory'))
        if len(matches) != 1:
            raise ValueError('Prepared release lacks one committed inventory record')
        return matches[0]

    def activate(self, manifest_id, *, now_unix):
        """Atomic pointer update; source and environment are checked before commit."""
        with self._lock(), self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            state = self._observe(db, now_unix)
            receipt, row = self._stored_receipt(db, manifest_id, now_unix)
            if row['status'] not in {'ready', 'active'}:
                raise ValueError('Only a ready release can be activated through the update path')
            if row['sequence'] < state['high_sequence']:
                raise ValueError('Activation would roll back the high-water sequence')
            if row['sequence'] == state['high_sequence'] and state['high_manifest_id'] != manifest_id:
                raise ValueError('High-water manifest equivocation')
            self._validate_prepared(receipt, row)
            if state['active_id'] == manifest_id:
                return self._receipt(db, manifest_id)
            old = state['active_id']
            if old:
                db.execute('UPDATE releases SET status="inactive" WHERE id=?', (old,))
            db.execute('UPDATE releases SET status="active",ever_active=1 WHERE id=?', (manifest_id,))
            db.execute('UPDATE state SET active_id=?,high_sequence=?,high_manifest_id=? WHERE singleton=1',
                       (manifest_id, row['sequence'], manifest_id))
            self._event(db, 'activated', manifest_id, detail={'previous_active': old})
            return self._receipt(db, manifest_id)

    def refresh_authorization(self, envelope, *, now_unix):
        """Bind existing staged bytes to current root approvals after key rotation.

        This changes authorization only. Version, sequence, source, wheel, SBOM,
        environment inventory and active/high-water pointers remain committed.
        A changed manifest requires a separate update sequence instead.
        """
        receipt = self._verify(envelope, now_unix)
        identifier = receipt.manifest_id
        with self._lock(), self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            self._observe(db, now_unix)
            row = db.execute('SELECT * FROM releases WHERE id=?', (identifier,)).fetchone()
            if row is None or row['status'] not in {'ready', 'active', 'inactive'}:
                raise ValueError('Authorization refresh requires an existing prepared release')
            old_data = signed._load(row['envelope'].encode())
            old_envelope = old_data['release'] if old_data.get('schema') == 'nabla.threshold-release.v1' else old_data
            if signed._json(old_envelope['body']) != signed._json(receipt.body):
                raise ValueError('Authorization refresh cannot change release content')
            self._validate_prepared(receipt, row)
            db.execute('UPDATE releases SET envelope=? WHERE id=?',
                       ((receipt.authorization_json or receipt.envelope_json).decode(), identifier))
            self._event(db, 'authorization-refreshed', identifier,
                        detail={'root_version': envelope.get('root_version')})
            return self._receipt(db, identifier)

    def rollback(self, manifest_id, *, reason, now_unix):
        """Explicitly select a previously active, still trusted release.

        High-water remains unchanged. This never authorizes a fresh old update,
        an expired signature, an unknown issuer, or an environment not once active.
        """
        signed._text(reason, 'rollback reason', 512)
        with self._lock(), self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            state = self._observe(db, now_unix)
            receipt, row = self._stored_receipt(db, manifest_id, now_unix)
            if row['ever_active'] != 1 or row['status'] not in {'active', 'inactive'}:
                raise ValueError('Rollback requires a previously activated release')
            if state['active_id'] is None:
                raise ValueError('No active release to roll back')
            self._validate_prepared(receipt, row)
            if state['active_id'] == manifest_id:
                return self._receipt(db, manifest_id)
            previous = state['active_id']
            db.execute('UPDATE releases SET status="inactive" WHERE id=?', (previous,))
            db.execute('UPDATE releases SET status="active" WHERE id=?', (manifest_id,))
            db.execute('UPDATE state SET active_id=? WHERE singleton=1', (manifest_id,))
            self._event(db, 'manual-rollback', manifest_id,
                        detail={'previous_active': previous, 'reason': reason})
            return self._receipt(db, manifest_id)

    def _receipt(self, db, identifier):
        state = self._state(db)
        row = db.execute('SELECT sequence,version,status FROM releases WHERE id=?', (identifier,)).fetchone()
        return {'manifest_id': identifier, 'sequence': row['sequence'], 'version': row['version'],
                'status': row['status'], 'active_manifest_id': state['active_id'],
                'high_water_sequence': state['high_sequence'],
                'environment': str(self._environment(identifier)),
                'scope': 'local signed offline release; package imports are trusted code, not sandboxed'}

    def active_environment(self, *, now_unix):
        """Recheck active package integrity, issuer trust and expiry before use."""
        with self._lock(), self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            state = self._observe(db, now_unix)
            if state['active_id'] is None:
                return None
            receipt, row = self._stored_receipt(db, state['active_id'], now_unix)
            self._validate_prepared(receipt, row)
            return self._environment(state['active_id'])

    def _remove_unactivated(self, identifier):
        with self._db() as db:
            row = db.execute('SELECT status,ever_active FROM releases WHERE id=?', (identifier,)).fetchone()
            state = self._state(db)
            if (row is None or row['ever_active'] != 0 or state['active_id'] == identifier
                    or row['status'] not in {'failed', 'staging', 'abandoned'}):
                raise ValueError('Refusing to remove a ready or previously active release')
        for path in (self._environment(identifier), self._artifact_directory(identifier)):
            if path.is_symlink():
                raise ValueError('Refusing symlink cleanup')
            if path.exists():
                shutil.rmtree(path)

    def recover(self):
        """Abandon interrupted preparations; committed active pointer is untouched.

        The process-wide OS lock prevents recovery from racing a live preparation.
        No expired or revoked release is activated as a recovery shortcut.
        """
        with self._lock():
            with self._db() as db:
                db.execute('BEGIN IMMEDIATE')
                state = self._state(db)
                self._verify_journal(db)
                rows = db.execute('SELECT id FROM releases WHERE status IN ("staging","failed")').fetchall()
                identifiers = [row[0] for row in rows]
                for identifier in identifiers:
                    signed._hex(identifier, 64, 'interrupted release id')
                    db.execute('UPDATE releases SET status="abandoned" WHERE id=?', (identifier,))
                    self._event(db, 'recovered-abandoned-stage', identifier)
            for identifier in identifiers:
                self._remove_unactivated(identifier)
            return {'abandoned': identifiers, 'active_manifest_id': state['active_id'],
                    'high_water_sequence': state['high_sequence'], 'automatic_activation': False}

    def _verify_journal(self, db):
        previous = None
        count = 0
        for row in db.execute('SELECT * FROM events ORDER BY sequence'):
            count += 1
            if count > MAX_EVENTS or type(row['record']) is not str or len(row['record']) > signed.MAX_MANIFEST_BYTES:
                raise ValueError('Release journal exceeds resource budget')
            record = signed._load(row['record'].encode())
            signed._fields(record, {'kind','manifest_id','previous','detail'})
            if record['kind'] not in {'stage-started','stage-ready','stage-failed','activated',
                    'manual-rollback','authorization-refreshed','recovered-abandoned-stage'}:
                raise ValueError('Unknown release journal event')
            signed._hex(record['manifest_id'], 64, 'journal manifest identity')
            if (record.get('previous') != previous or row['previous_hash'] != previous
                    or hashlib.sha256(signed._json(record)).hexdigest() != row['record_hash']):
                raise ValueError('Release journal hash chain corrupted')
            previous = row['record_hash']
        return {'events': count, 'head': previous,
                'authenticated_external_timestamp': False, 'administrator_tamperproof': False}

    def journal(self):
        with self._lock(), self._db() as db:
            self._state(db)
            return self._verify_journal(db)

    @staticmethod
    def _validate_checkpoint(checkpoint, expected_sha256):
        signed._hex(expected_sha256, 64, 'separately pinned checkpoint digest')
        detached = signed._load(signed._json(checkpoint))
        signed._fields(detached, {'schema', 'issuer', 'channel', 'high_water_sequence',
                                  'high_manifest_id', 'active_manifest_id',
                                  'journal_events', 'journal_head', 'last_unix'})
        if detached['schema'] != 'nabla.release-checkpoint.v1':
            raise ValueError('Unknown release checkpoint schema')
        if hashlib.sha256(signed._json(detached)).hexdigest() != expected_sha256:
            raise ValueError('Checkpoint differs from separately pinned digest')
        signed._token(detached['issuer'], 'checkpoint issuer')
        signed._token(detached['channel'], 'checkpoint channel')
        signed._integer(detached['high_water_sequence'], 'checkpoint high-water')
        signed._integer(detached['journal_events'], 'checkpoint event count', 0, MAX_EVENTS)
        signed._integer(detached['last_unix'], 'checkpoint clock')
        for name in ('high_manifest_id', 'active_manifest_id', 'journal_head'):
            if detached[name] is not None:
                signed._hex(detached[name], 64, 'checkpoint ' + name)
        if (detached['high_water_sequence'] == 0) != (detached['high_manifest_id'] is None):
            raise ValueError('Checkpoint high-water identity mismatch')
        if (detached['journal_events'] == 0) != (detached['journal_head'] is None):
            raise ValueError('Checkpoint journal identity mismatch')
        if detached['active_manifest_id'] is not None and detached['high_water_sequence'] == 0:
            raise ValueError('Checkpoint active state lacks activation history')
        return detached

    def export_checkpoint(self):
        """Export an identity record to pin outside this release store.

        Save the returned record AND authenticate its SHA256 separately. Keeping
        both alongside the database does not detect restoration of an old backup.
        This record is an anti-rollback comparison anchor, not a signed timestamp.
        """
        with self._lock(), self._db() as db:
            state = self._state(db)
            journal = self._verify_journal(db)
            return {'schema': 'nabla.release-checkpoint.v1', 'issuer': self.issuer,
                    'channel': self.channel, 'high_water_sequence': state['high_sequence'],
                    'high_manifest_id': state['high_manifest_id'],
                    'active_manifest_id': state['active_id'],
                    'journal_events': journal['events'], 'journal_head': journal['head'],
                    'last_unix': state['last_unix']}

    def _verify_checkpoint_record(self, db, checkpoint):
        state = self._state(db)
        journal = self._verify_journal(db)
        if checkpoint['issuer'] != self.issuer or checkpoint['channel'] != self.channel:
            raise ValueError('Checkpoint belongs to a different installation identity')
        if (state['high_sequence'] < checkpoint['high_water_sequence']
                or state['last_unix'] < checkpoint['last_unix']
                or journal['events'] < checkpoint['journal_events']):
            raise ValueError('Release store regressed behind externally pinned checkpoint')
        if (state['high_sequence'] == checkpoint['high_water_sequence']
                and state['high_manifest_id'] != checkpoint['high_manifest_id']):
            raise ValueError('Release high-water differs from pinned checkpoint')
        if checkpoint['journal_events']:
            anchor = db.execute('SELECT record_hash FROM events ORDER BY sequence LIMIT 1 OFFSET ?',
                                (checkpoint['journal_events']-1,)).fetchone()
            if anchor is None or anchor[0] != checkpoint['journal_head']:
                raise ValueError('Release journal does not extend pinned checkpoint')
        if (journal['events'] == checkpoint['journal_events']
                and state['active_id'] != checkpoint['active_manifest_id']):
            raise ValueError('Active pointer changed without a journal extension')
        if checkpoint['high_water_sequence']:
            original = db.execute('SELECT sequence,ever_active FROM releases WHERE id=?',
                                  (checkpoint['high_manifest_id'],)).fetchone()
            if (original is None or original[0] != checkpoint['high_water_sequence']
                    or original[1] != 1):
                raise ValueError('Pinned activation no longer exists in local history')
        return {'extends_checkpoint': True, 'high_water_sequence': state['high_sequence'],
                'journal_events': journal['events'],
                'pin_authentication': 'external responsibility of the caller'}

    def verify_checkpoint(self, checkpoint, *, expected_sha256):
        detached = self._validate_checkpoint(checkpoint, expected_sha256)
        with self._lock(), self._db() as db:
            return self._verify_checkpoint_record(db, detached)
