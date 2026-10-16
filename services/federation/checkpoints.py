"""Durable bounded transfer checkpoints over immutable Merkle snapshot pages.

An acknowledged page means authenticated event admission into the reconciler,
not formal validation. SQLite commits make each checkpoint idempotent. Event
admission and journal commits use separate stores; replay repairs that crash gap.
"""
import json
import uuid

from nablamath.core.semantic_contracts import canonical_payload, require_digest, require_fields, require_text
from nablamath.core.semantic_ir import fingerprint
from nablamath.network.merkle_inventory import validate_manifest, verify_page
from services.registry.db import RegistryDB
from .reconciliation import Reconciler


class TransferJournal:
    def __init__(self, database, *, max_sessions=100, max_total_bytes=64 * 1024 * 1024,
                 max_pages_per_session=10000):
        if not isinstance(database, RegistryDB):
            raise ValueError('Transactional database required')
        for value, upper in ((max_sessions, 10000), (max_total_bytes, 1024 * 1024 * 1024),
                             (max_pages_per_session, 10000)):
            if type(value) is not int or not 1 <= value <= upper:
                raise ValueError('Invalid checkpoint resource budget')
        self.database = database
        self.max_sessions = max_sessions
        self.max_total_bytes = max_total_bytes
        self.max_pages_per_session = max_pages_per_session
        with database.transaction() as connection:
            connection.executescript('''
              CREATE TABLE IF NOT EXISTS federation_transfers(
                id TEXT PRIMARY KEY, peer TEXT NOT NULL, manifest TEXT NOT NULL,
                next_position INTEGER NOT NULL, status TEXT NOT NULL,
                created_unix INTEGER NOT NULL, last_unix INTEGER NOT NULL,
                transferred_bytes INTEGER NOT NULL DEFAULT 0,
                error TEXT);
              CREATE TABLE IF NOT EXISTS federation_transfer_grants(
                session TEXT PRIMARY KEY REFERENCES federation_transfers(id),
                access_id TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS federation_transfer_requests(
                session TEXT NOT NULL REFERENCES federation_transfers(id),
                sequence INTEGER NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL,
                PRIMARY KEY(session,sequence));
              CREATE TABLE IF NOT EXISTS federation_transfer_pages(
                session TEXT NOT NULL REFERENCES federation_transfers(id),
                start INTEGER NOT NULL, page_id TEXT NOT NULL,
                body TEXT NOT NULL, body_bytes INTEGER NOT NULL,
                state TEXT NOT NULL, receipt TEXT,
                PRIMARY KEY(session,start));
            ''')

    def begin(self, peer, manifest, *, now_unix):
        require_text(peer, 'authenticated remote peer', limit=256)
        validate_manifest(manifest)
        if type(now_unix) is not int or now_unix < 0:
            raise ValueError('Explicit transfer clock required')
        session_id = uuid.uuid4().hex
        with self.database.transaction() as connection:
            self.database.check_clock(connection, now_unix)
            count = connection.execute('SELECT count(*) FROM federation_transfers').fetchone()[0]
            if count >= self.max_sessions:
                raise ValueError('Durable transfer session capacity exhausted')
            # Even an empty inventory requires its empty page to be checked.
            connection.execute('INSERT INTO federation_transfers(id,peer,manifest,next_position,status,created_unix,last_unix) VALUES(?,?,?,0,?,?,?)',
                               (session_id, peer, canonical_payload(manifest), 'active', now_unix, now_unix))
        return session_id

    @staticmethod
    def _row(connection, session_id):
        if type(session_id) is not str or len(session_id) != 32 or any(c not in '0123456789abcdef' for c in session_id):
            raise ValueError('Invalid transfer session identifier')
        row = connection.execute('SELECT * FROM federation_transfers WHERE id=?', (session_id,)).fetchone()
        if row is None:
            raise KeyError('Unknown transfer session')
        return row

    @staticmethod
    def _status(row):
        manifest = json.loads(row['manifest'])
        validate_manifest(manifest)
        return {'schema_version': 1, 'session_id': row['id'], 'peer': row['peer'],
                'manifest': manifest, 'next_position': row['next_position'],
                'status': row['status'], 'created_unix': row['created_unix'],
                'last_unix': row['last_unix'], 'transferred_bytes': row['transferred_bytes'],
                'error': row['error'], 'formal_proof': False}

    def status(self, session_id):
        with self.database.transaction() as connection:
            return self._status(self._row(connection, session_id))

    def cancel(self, session_id, *, now_unix):
        with self.database.transaction() as connection:
            self.database.check_clock(connection, now_unix)
            row = self._row(connection, session_id)
            if row['status'] == 'complete':
                raise ValueError('Completed transfer cannot be cancelled')
            connection.execute("UPDATE federation_transfers SET status='cancelled',last_unix=? WHERE id=?",
                               (now_unix, session_id))
        return self.status(session_id)

    @staticmethod
    def validate_batch(batch, *, manifest=None, expected_start=None):
        canonical_payload(batch)
        require_fields(batch, {'schema_version', 'inventory_page', 'events'})
        if type(batch['schema_version']) is not int or batch['schema_version'] != 1:
            raise ValueError('Unsupported transfer batch')
        page = batch['inventory_page']
        identifiers = verify_page(page, manifest=manifest, expected_start=expected_start)
        events = batch['events']
        if type(events) is not list or len(events) != len(identifiers):
            raise ValueError('Transfer event/proof count mismatch')
        if [fingerprint(event) for event in events] != identifiers:
            raise ValueError('Transfer event content binding mismatch')
        return identifiers

    def _prepare(self, session_id, batch, *, peer, now_unix):
        raw = canonical_payload(batch)
        page_id = fingerprint(batch)
        page = batch['inventory_page']
        with self.database.transaction() as connection:
            self.database.check_clock(connection, now_unix)
            row = self._row(connection, session_id)
            if row['peer'] != peer:
                raise ValueError('Authenticated response peer does not match session')
            manifest = json.loads(row['manifest'])
            self.validate_batch(batch, manifest=manifest)
            start = page['start']
            existing = connection.execute('SELECT * FROM federation_transfer_pages WHERE session=? AND start=?',
                                          (session_id, start)).fetchone()
            if existing:
                if existing['page_id'] != page_id or existing['body'] != raw:
                    raise ValueError('A checkpoint cannot be replaced by different page bytes')
                if existing['state'] == 'committed':
                    return row, json.loads(existing['receipt'])
            if row['status'] != 'active':
                raise ValueError('Transfer is not active')
            if start != row['next_position']:
                raise ValueError('Transfer pages must be contiguous')
            if start and batch['events']:
                previous = connection.execute("SELECT body FROM federation_transfer_pages WHERE session=? AND state='committed' ORDER BY start DESC LIMIT 1", (session_id,)).fetchone()
                if previous is None:
                    raise ValueError('Missing prior committed page')
                previous_events = json.loads(previous['body'])['events']
                if not previous_events or fingerprint(previous_events[-1]) >= fingerprint(batch['events'][0]):
                    raise ValueError('Inventory order changed between pages')
            if existing is None:
                page_count = connection.execute('SELECT count(*) FROM federation_transfer_pages WHERE session=?',
                                                (session_id,)).fetchone()[0]
                used = connection.execute('SELECT coalesce(sum(body_bytes),0) FROM federation_transfer_pages').fetchone()[0]
                size = len(raw.encode())
                if page_count >= self.max_pages_per_session or used + size > self.max_total_bytes:
                    raise ValueError('Durable checkpoint page capacity exhausted')
                connection.execute("INSERT INTO federation_transfer_pages VALUES(?,?,?,?,?,'prepared',NULL)",
                                   (session_id, start, page_id, raw, size))
            connection.execute('UPDATE federation_transfers SET last_unix=? WHERE id=?', (now_unix, session_id))
            return row, None

    def accept(self, session_id, batch, reconciler, *, authenticated_peer, now_unix):
        """Validate proofs, persist intent, admit events, then atomically advance.

        A fully transferred snapshot with missing external parents fails closed.
        Pending parents inside later pages are permitted until the last page.
        """
        if not isinstance(reconciler, Reconciler):
            raise ValueError('Typed reconciler required')
        identifiers = self.validate_batch(batch)
        row, receipt = self._prepare(session_id, batch, peer=authenticated_peer, now_unix=now_unix)
        if receipt is not None:
            return receipt
        report = reconciler.receive(batch['events'], now_unix=now_unix)
        by_id = {event['event_id']: event for event in report['events']}
        quarantined = [identifier for identifier in identifiers if by_id.get(identifier, {}).get('state') == 'quarantined']
        page = batch['inventory_page']
        complete = page['next_position'] is None
        if complete:
            # Check only this transfer's committed/prepared event IDs. Unrelated
            # pending messages in the same reconciler do not block completion.
            with self.database.transaction() as connection:
                page_rows = connection.execute('SELECT body FROM federation_transfer_pages WHERE session=?',
                                               (session_id,)).fetchall()
            all_ids = {fingerprint(event) for item in page_rows for event in json.loads(item['body'])['events']}
            unresolved = [identifier for identifier in all_ids if by_id.get(identifier, {}).get('state') != 'accepted']
        else:
            unresolved = []
        if quarantined or unresolved:
            with self.database.transaction() as connection:
                connection.execute("UPDATE federation_transfers SET status='failed',error=?,last_unix=? WHERE id=?",
                                   ('quarantined or unresolved signed history', now_unix, session_id))
            raise ValueError('Transfer contains quarantined or unresolved events')
        stop = page['start'] + len(identifiers)
        body = {'schema_version': 1, 'session_id': session_id, 'page_id': fingerprint(batch),
                'snapshot_id': json.loads(row['manifest'])['snapshot_id'],
                'accepted_position': stop, 'complete': complete,
                'scientific_validity_established': False,
                'scope': 'authenticated content and causal admission only'}
        receipt = {**body, 'receipt_id': fingerprint(body)}
        with self.database.transaction() as connection:
            current = self._row(connection, session_id)
            existing = connection.execute('SELECT * FROM federation_transfer_pages WHERE session=? AND start=?',
                                          (session_id, page['start'])).fetchone()
            if existing['state'] == 'committed':
                return json.loads(existing['receipt'])
            if current['status'] != 'active' or current['next_position'] != page['start']:
                raise ValueError('Transfer changed while page was being admitted')
            connection.execute("UPDATE federation_transfer_pages SET state='committed',receipt=? WHERE session=? AND start=?",
                               (canonical_payload(receipt), session_id, page['start']))
            connection.execute("UPDATE federation_transfer_requests SET state='committed' WHERE session=? AND state='prepared'", (session_id,))
            connection.execute('UPDATE federation_transfers SET next_position=?,status=?,last_unix=?,transferred_bytes=transferred_bytes+? WHERE id=?',
                               (stop, 'complete' if complete else 'active', now_unix, existing['body_bytes'], session_id))
        return receipt

    def resume_prepared(self, session_id, reconciler, *, now_unix):
        """Replay durable intent after a crash, including post-admission crashes."""
        with self.database.transaction() as connection:
            row = self._row(connection, session_id)
            prepared = connection.execute("SELECT body FROM federation_transfer_pages WHERE session=? AND state='prepared' ORDER BY start",
                                          (session_id,)).fetchall()
        if len(prepared) > 1:
            raise ValueError('Multiple unacknowledged checkpoints violate transfer ordering')
        if not prepared:
            return self.status(session_id)
        return self.accept(session_id, json.loads(prepared[0]['body']), reconciler,
                           authenticated_peer=row['peer'], now_unix=now_unix)


    def bind_access(self, session_id, access_id):
        """Bind a local transfer to one remote grant, durably and irreversibly."""
        if type(access_id) is not str or len(access_id) != 32 or any(c not in '0123456789abcdef' for c in access_id):
            raise ValueError('Invalid remote access grant identifier')
        with self.database.transaction() as connection:
            row = self._row(connection, session_id)
            existing = connection.execute('SELECT access_id FROM federation_transfer_grants WHERE session=?',
                                          (session_id,)).fetchone()
            if existing:
                if existing['access_id'] != access_id:
                    raise ValueError('A local transfer cannot switch remote access grants')
                return
            if row['next_position'] != 0 or row['status'] != 'active':
                raise ValueError('Access grant must be bound before any local page is committed')
            connection.execute('INSERT INTO federation_transfer_grants VALUES(?,?)', (session_id, access_id))

    def prepare_access_request(self, session_id, access_id, *, page_size):
        """Persist operation parameters before I/O so lost replies replay exactly."""
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError('Invalid access request page size')
        with self.database.transaction() as connection:
            row = self._row(connection, session_id)
            binding = connection.execute('SELECT access_id FROM federation_transfer_grants WHERE session=?',
                                         (session_id,)).fetchone()
            if binding is None or binding['access_id'] != access_id:
                raise ValueError('Local transfer is not bound to this access grant')
            if row['status'] != 'active':
                raise ValueError('Local transfer is not active')
            pending = connection.execute("SELECT payload FROM federation_transfer_requests WHERE session=? AND state='prepared'",
                                         (session_id,)).fetchall()
            if len(pending) > 1:
                raise ValueError('Multiple outgoing requests violate transfer ordering')
            if pending:
                return json.loads(pending[0]['payload'])
            sequence = connection.execute("SELECT count(*) FROM federation_transfer_pages WHERE session=? AND state='committed'",
                                          (session_id,)).fetchone()[0]
            payload = {'session_id': access_id, 'snapshot_id': json.loads(row['manifest'])['snapshot_id'],
                       'sequence': sequence, 'start': row['next_position'], 'limit': page_size}
            connection.execute("INSERT INTO federation_transfer_requests VALUES(?,?,?,'prepared')",
                               (session_id, sequence, canonical_payload(payload)))
            return payload
