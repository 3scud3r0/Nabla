"""Transactional SQLite state for pinned identities and consented discovery.

The database path is trusted local configuration. Key pinning is an operator
operation, deliberately separate from untrusted network registration. This store
provides integrity constraints and atomicity, not encryption or reviewer identity.
"""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from threading import RLock

from nablamath.core.semantic_contracts import canonical_payload, load_json
from nablamath.knowledge.identity import PeerKey
from nablamath.network.signatures import MessageVerifier


class RegistryDB:
    """One bounded durable database; independent instances share SQLite locking."""

    def __init__(self, path, *, max_peers=10000, max_keys=20000,
                 max_replays=100000, max_audit=100000):
        for name, value in [('max_peers', max_peers), ('max_keys', max_keys),
                            ('max_replays', max_replays), ('max_audit', max_audit)]:
            if type(value) is not int or not 1 <= value <= 1000000:
                raise ValueError('Invalid database bound: ' + name)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_peers = max_peers
        self.max_keys = max_keys
        self.max_replays = max_replays
        self.max_audit = max_audit
        self._lock = RLock()
        with self.transaction() as connection:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS peer_keys (
                    peer_id TEXT NOT NULL, public_key TEXT NOT NULL,
                    revoked INTEGER NOT NULL CHECK(revoked IN (0,1)),
                    PRIMARY KEY(peer_id, public_key)
                );
                CREATE TABLE IF NOT EXISTS peers (
                    peer_id TEXT PRIMARY KEY, capabilities TEXT NOT NULL,
                    expires INTEGER NOT NULL CHECK(expires >= 0),
                    visible INTEGER NOT NULL CHECK(visible IN (0,1))
                );
                CREATE TABLE IF NOT EXISTS replays (
                    peer_id TEXT NOT NULL, nonce TEXT NOT NULL,
                    expires INTEGER NOT NULL, PRIMARY KEY(peer_id, nonce)
                );
                CREATE TABLE IF NOT EXISTS audit (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event TEXT NOT NULL, peer_id TEXT,
                    at_unix INTEGER NOT NULL, detail TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS configuration (
                    name TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                INSERT OR IGNORE INTO configuration VALUES ('clock', '0');
                INSERT OR IGNORE INTO configuration VALUES ('schema', '1');
            ''')
            if self.get_setting(connection, 'schema') != '1':
                raise ValueError('Unsupported registry database schema')

    @contextmanager
    def transaction(self):
        """Serialize admission checks with writes; rollback on any failure."""
        with self._lock:
            connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            try:
                connection.execute('PRAGMA foreign_keys=ON')
                connection.execute('PRAGMA busy_timeout=5000')
                connection.execute('BEGIN IMMEDIATE')
                yield connection
                if connection.in_transaction:
                    connection.execute('COMMIT')
            except BaseException:
                if connection.in_transaction:
                    connection.execute('ROLLBACK')
                raise
            finally:
                connection.close()

    @staticmethod
    def get_setting(connection, name, default=None):
        row = connection.execute('SELECT value FROM configuration WHERE name=?',
                                 (name,)).fetchone()
        return default if row is None else row['value']

    @staticmethod
    def set_setting(connection, name, value):
        connection.execute('INSERT OR REPLACE INTO configuration VALUES (?,?)',
                           (name, str(value)))

    def check_clock(self, connection, now_unix):
        if type(now_unix) is not int or now_unix < 0:
            raise ValueError('Nonnegative integer clock required')
        previous = int(self.get_setting(connection, 'clock'))
        if now_unix < previous:
            raise ValueError('Registry clock rollback')
        self.set_setting(connection, 'clock', now_unix)

    def append_audit(self, connection, event, peer_id, now_unix, detail=None):
        """Fail closed when audit capacity is full; never silently erase history."""
        if connection.execute('SELECT count(*) FROM audit').fetchone()[0] >= self.max_audit:
            raise ValueError('Audit capacity exhausted; explicit archive required')
        if not isinstance(event, str) or not event or len(event) > 64:
            raise ValueError('Invalid event category')
        encoded = canonical_payload({} if detail is None else detail)
        if len(encoded.encode()) > 4096:
            raise ValueError('Audit detail exceeds budget')
        connection.execute('INSERT INTO audit(event,peer_id,at_unix,detail) VALUES (?,?,?,?)',
                           (event, peer_id, now_unix, encoded))

    def pin_key(self, peer_id, public_key, *, now_unix):
        """Trusted administrative pin; public HTTP APIs never expose this method."""
        key = PeerKey(peer_id, public_key)
        with self.transaction() as connection:
            self.check_clock(connection, now_unix)
            row = connection.execute('SELECT revoked FROM peer_keys WHERE peer_id=? AND public_key=?',
                                     (key.peer_id, key.public_key)).fetchone()
            if row is not None:
                if row['revoked']:
                    raise ValueError('Revoked key cannot be reactivated')
                return False
            count = connection.execute('SELECT count(*) FROM peer_keys').fetchone()[0]
            if count >= self.max_keys:
                raise ValueError('Pinned key capacity exhausted')
            connection.execute('INSERT INTO peer_keys VALUES (?,?,0)',
                               (key.peer_id, key.public_key))
            self.append_audit(connection, 'key_pinned', peer_id, now_unix)
            return True

    def revoke_key(self, peer_id, public_key, *, now_unix):
        key = PeerKey(peer_id, public_key)
        with self.transaction() as connection:
            self.check_clock(connection, now_unix)
            changed = connection.execute('UPDATE peer_keys SET revoked=1 WHERE peer_id=? AND public_key=? AND revoked=0',
                                         (key.peer_id, key.public_key)).rowcount
            if changed:
                self.append_audit(connection, 'key_revoked', peer_id, now_unix)
            return bool(changed)

    def rotate_key(self, peer_id, new_public_key, *, now_unix):
        """Atomic administrative rotation; old keys remain permanently revoked."""
        key = PeerKey(peer_id, new_public_key)
        with self.transaction() as connection:
            self.check_clock(connection, now_unix)
            if connection.execute('SELECT 1 FROM peer_keys WHERE peer_id=? AND public_key=?',
                                  (key.peer_id, key.public_key)).fetchone():
                raise ValueError('Rotation requires a previously unseen key')
            if connection.execute('SELECT count(*) FROM peer_keys').fetchone()[0] >= self.max_keys:
                raise ValueError('Pinned key capacity exhausted')
            connection.execute('UPDATE peer_keys SET revoked=1 WHERE peer_id=?', (peer_id,))
            connection.execute('INSERT INTO peer_keys VALUES (?,?,0)', (peer_id, key.public_key))
            self.append_audit(connection, 'key_rotated', peer_id, now_unix)

    def authenticate(self, connection, envelope, *, audience, now_unix):
        """Verify signature and consume nonce in the caller's application transaction.

        A transaction rollback also rolls back nonce consumption. Retrying an
        operation rejected for quota or malformed payload is therefore possible;
        a committed successful operation can never be replayed after restart.
        """
        self.check_clock(connection, now_unix)

        class TransactionTrust:
            def accepts(self, peer_id, public_key):
                row = connection.execute('SELECT revoked FROM peer_keys WHERE peer_id=? AND public_key=?',
                                         (peer_id, public_key)).fetchone()
                return row is not None and row['revoked'] == 0

        # Freeze caller-owned input before verifying and persisting replay fields.
        snapshot = load_json(canonical_payload(envelope))
        verification = MessageVerifier(TransactionTrust(), audience).verify(snapshot, now_unix=now_unix)
        if not verification['valid']:
            raise PermissionError(verification.get('reason', 'Unauthenticated message'))
        connection.execute('DELETE FROM replays WHERE expires<=?', (now_unix,))
        if connection.execute('SELECT count(*) FROM replays').fetchone()[0] >= self.max_replays:
            raise ValueError('Replay capacity exhausted')
        try:
            connection.execute('INSERT INTO replays VALUES (?,?,?)',
                               (verification['peer_id'], snapshot['nonce'], snapshot['expires_unix']))
        except sqlite3.IntegrityError as exc:
            raise PermissionError('Replayed authenticated envelope') from exc
        return verification['peer_id'], verification['payload']

    def active_peer(self, connection, peer_id, *, now_unix, capability=None):
        row = connection.execute('SELECT capabilities,expires FROM peers WHERE peer_id=?',
                                 (peer_id,)).fetchone()
        if row is None or row['expires'] <= now_unix:
            return False
        if not connection.execute('SELECT 1 FROM peer_keys WHERE peer_id=? AND revoked=0',
                                  (peer_id,)).fetchone():
            return False
        return capability is None or capability in load_json(row['capabilities'])

    def audit(self, *, after=0, limit=100):
        """Privileged local audit export. Peer IDs are NOT anonymized here."""
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError('Invalid audit pagination')
        with self.transaction() as connection:
            rows = connection.execute('SELECT * FROM audit WHERE sequence>? ORDER BY sequence LIMIT ?',
                                      (after, limit)).fetchall()
        return tuple({**dict(row), 'detail': load_json(row['detail'])} for row in rows)
