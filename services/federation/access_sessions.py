"""Peer-bound, expiring, sequenced read grants for immutable snapshot transfer.

Grants inherit live registry consent/key revocation on every request. They do not
replace those checks, authorize arbitrary objects, or promise remote availability.
Sequence retries are idempotent only for exactly the same signed operation data.
"""
import json
import uuid

from nablamath.core.semantic_contracts import canonical_payload, require_digest, require_text
from nablamath.core.semantic_ir import fingerprint
from services.registry.db import RegistryDB


class InventoryAccess:
    def __init__(self, database, *, max_sessions=1000, max_cached_bytes=64 * 1024 * 1024):
        if not isinstance(database, RegistryDB):
            raise ValueError('Transactional registry database required')
        if type(max_sessions) is not int or not 1 <= max_sessions <= 10000:
            raise ValueError('Invalid durable access-session bound')
        if type(max_cached_bytes) is not int or not 1 <= max_cached_bytes <= 1024 * 1024 * 1024:
            raise ValueError('Invalid durable access-cache bound')
        self.database = database
        self.max_sessions = max_sessions
        self.max_cached_bytes = max_cached_bytes
        with database.transaction() as connection:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS federation_access_sessions(
                  id TEXT PRIMARY KEY, peer TEXT NOT NULL, snapshot TEXT NOT NULL,
                  issued INTEGER NOT NULL, expires INTEGER NOT NULL,
                  state TEXT NOT NULL CHECK(state IN ('active','cancelled','expired')),
                  next_sequence INTEGER NOT NULL, next_position INTEGER NOT NULL,
                  max_pages INTEGER NOT NULL, max_response_bytes INTEGER NOT NULL,
                  used_response_bytes INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS federation_access_responses(
                  session TEXT NOT NULL REFERENCES federation_access_sessions(id),
                  sequence INTEGER NOT NULL, operation_id TEXT NOT NULL,
                  result TEXT NOT NULL, response_bytes INTEGER NOT NULL,
                  PRIMARY KEY(session,sequence));
            ''')

    @staticmethod
    def validate_open(payload):
        for name, upper in (('ttl_seconds', 3600), ('max_pages', 10000),
                            ('max_response_bytes', 64 * 1024 * 1024)):
            if type(payload.get(name)) is not int or not 1 <= payload[name] <= upper:
                raise ValueError('Invalid access-session budget ' + name)

    @staticmethod
    def _id(value):
        if type(value) is not str or len(value) != 32 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Invalid access-session identifier')
        return value

    def open(self, connection, peer, payload, *, now_unix):
        self.validate_open(payload)
        require_digest(payload['snapshot_id'])
        require_text(peer, 'peer', limit=256)
        if connection.execute('SELECT count(*) FROM federation_access_sessions').fetchone()[0] >= self.max_sessions:
            raise ValueError('Durable access-session capacity exhausted')
        session_id = uuid.uuid4().hex
        connection.execute('INSERT INTO federation_access_sessions(id,peer,snapshot,issued,expires,state,next_sequence,next_position,max_pages,max_response_bytes) VALUES(?,?,?,?,?,\'active\',0,0,?,?)',
            (session_id, peer, payload['snapshot_id'], now_unix, now_unix + payload['ttl_seconds'],
             payload['max_pages'], payload['max_response_bytes']))
        return self.status(connection, peer, session_id, now_unix=now_unix)

    def _row(self, connection, peer, session_id, *, now_unix):
        self._id(session_id)
        row = connection.execute('SELECT * FROM federation_access_sessions WHERE id=?', (session_id,)).fetchone()
        if row is None:
            raise KeyError('Unknown access session')
        if row['peer'] != peer:
            raise PermissionError('Access session belongs to another peer')
        if row['state'] == 'active' and now_unix >= row['expires']:
            connection.execute("UPDATE federation_access_sessions SET state='expired' WHERE id=?", (session_id,))
            row = connection.execute('SELECT * FROM federation_access_sessions WHERE id=?', (session_id,)).fetchone()
        return row

    def status(self, connection, peer, session_id, *, now_unix):
        row = self._row(connection, peer, session_id, now_unix=now_unix)
        return {'schema_version': 1, 'session_id': row['id'], 'peer': row['peer'],
                'snapshot_id': row['snapshot'], 'issued_unix': row['issued'],
                'expires_unix': row['expires'], 'state': row['state'],
                'next_sequence': row['next_sequence'], 'next_position': row['next_position'],
                'max_pages': row['max_pages'], 'max_response_bytes': row['max_response_bytes'],
                'used_response_bytes': row['used_response_bytes'],
                'scope': 'peer-bound immutable snapshot reads; live consent required'}

    def cancel(self, connection, peer, session_id, *, now_unix):
        row = self._row(connection, peer, session_id, now_unix=now_unix)
        if row['state'] == 'active':
            connection.execute("UPDATE federation_access_sessions SET state='cancelled' WHERE id=?", (session_id,))
        return self.status(connection, peer, session_id, now_unix=now_unix)

    def prepare_page(self, connection, peer, payload, *, now_unix):
        row = self._row(connection, peer, payload['session_id'], now_unix=now_unix)
        if row['state'] != 'active':
            raise PermissionError('Access session expired or cancelled')
        if payload['snapshot_id'] != row['snapshot']:
            raise ValueError('Access session snapshot mismatch')
        sequence = payload['sequence']
        if type(sequence) is not int or not 0 <= sequence < row['max_pages']:
            raise ValueError('Access sequence outside page budget')
        operation_id = fingerprint(payload)
        cached = connection.execute('SELECT * FROM federation_access_responses WHERE session=? AND sequence=?',
                                    (row['id'], sequence)).fetchone()
        if cached:
            if cached['operation_id'] != operation_id:
                raise ValueError('Cannot replace a committed access sequence')
            return row, json.loads(cached['result'])
        if sequence != row['next_sequence'] or payload['start'] != row['next_position']:
            raise ValueError('Access sequence or page position is not contiguous')
        return row, None

    def commit_page(self, connection, payload, result, *, response_bytes):
        """Called within the same authorization/response-signing transaction."""
        row = connection.execute('SELECT * FROM federation_access_sessions WHERE id=?',
                                 (payload['session_id'],)).fetchone()
        if row is None or row['state'] != 'active':
            raise PermissionError('Access session is no longer active')
        if row['next_sequence'] != payload['sequence']:
            raise ValueError('Access sequence changed during response')
        if type(response_bytes) is not int or response_bytes < 1:
            raise ValueError('Positive response byte charge required')
        used = connection.execute('SELECT coalesce(sum(response_bytes),0) FROM federation_access_responses').fetchone()[0]
        if row['used_response_bytes'] + response_bytes > row['max_response_bytes'] or used + response_bytes > self.max_cached_bytes:
            raise ValueError('Access response byte budget exhausted')
        page = result['page']['inventory_page']
        stop = page['start'] + len(page['proofs'])
        connection.execute('INSERT INTO federation_access_responses VALUES(?,?,?,?,?)',
                           (row['id'], payload['sequence'], fingerprint(payload), canonical_payload(result), response_bytes))
        connection.execute('UPDATE federation_access_sessions SET next_sequence=next_sequence+1,next_position=?,used_response_bytes=used_response_bytes+? WHERE id=?',
                           (stop, response_bytes, row['id']))
