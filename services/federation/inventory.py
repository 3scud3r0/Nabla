"""Durable immutable provenance snapshots and evidence of signed revocation.

Snapshots are local administrative exports. Read-only network access is separately
authorized by the federation service; possession of a snapshot ID is not consent.
"""
import json

from nablamath.core.semantic_contracts import canonical_payload, require_digest, require_fields
from nablamath.core.semantic_ir import fingerprint
from nablamath.knowledge.distributed_provenance import ProvenanceLog, AUDIENCE, validate_payload
from nablamath.network.signatures import MessageVerifier
from nablamath.network.merkle_inventory import MerkleInventory, verify_membership, validate_manifest, _split
from services.registry.db import RegistryDB


class InventoryStore:
    def __init__(self, database, *, max_snapshots=100, max_total_items=100000,
                 max_total_bytes=64 * 1024 * 1024):
        if not isinstance(database, RegistryDB):
            raise ValueError('Transactional registry database required')
        for value, upper in ((max_snapshots, 10000), (max_total_items, 1000000),
                             (max_total_bytes, 1024 * 1024 * 1024)):
            if type(value) is not int or not 1 <= value <= upper:
                raise ValueError('Invalid snapshot storage budget')
        self.database = database
        self.max_snapshots = max_snapshots
        self.max_total_items = max_total_items
        self.max_total_bytes = max_total_bytes
        with database.transaction() as connection:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS federation_snapshots(
                  id TEXT PRIMARY KEY, manifest TEXT NOT NULL, created_unix INTEGER NOT NULL,
                  event_bytes INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS federation_snapshot_events(
                  snapshot TEXT NOT NULL REFERENCES federation_snapshots(id),
                  position INTEGER NOT NULL, event_id TEXT NOT NULL, envelope TEXT NOT NULL,
                  PRIMARY KEY(snapshot,position), UNIQUE(snapshot,event_id));
                CREATE TABLE IF NOT EXISTS federation_snapshot_nodes(
                  snapshot TEXT NOT NULL REFERENCES federation_snapshots(id),
                  start INTEGER NOT NULL, stop INTEGER NOT NULL, hash TEXT NOT NULL,
                  PRIMARY KEY(snapshot,start,stop));
            ''')

    def freeze(self, log, *, now_unix):
        if not isinstance(log, ProvenanceLog) or type(now_unix) is not int or now_unix < 0:
            raise ValueError('Explicit provenance log and clock required')
        # A single SELECT statement sees a SQLite-consistent event inventory.
        envelopes = log.export()
        if len(envelopes) > 10000:
            raise ValueError('Snapshot event budget exceeded')
        by_id = {fingerprint(e): canonical_payload(e) for e in envelopes}
        tree = MerkleInventory(by_id)
        manifest = tree.manifest
        total_bytes = sum(len(raw.encode()) for raw in by_id.values())
        with self.database.transaction() as connection:
            self.database.check_clock(connection, now_unix)
            existing = connection.execute('SELECT manifest FROM federation_snapshots WHERE id=?',
                                          (manifest['snapshot_id'],)).fetchone()
            if existing:
                if existing['manifest'] != canonical_payload(manifest):
                    raise ValueError('Stored snapshot identifier collision')
                return manifest
            count = connection.execute('SELECT count(*) FROM federation_snapshots').fetchone()[0]
            used_items = connection.execute('SELECT count(*) FROM federation_snapshot_events').fetchone()[0]
            used_bytes = connection.execute('SELECT coalesce(sum(event_bytes),0) FROM federation_snapshots').fetchone()[0]
            if (count >= self.max_snapshots or used_items + tree.count > self.max_total_items
                    or used_bytes + total_bytes > self.max_total_bytes):
                raise ValueError('Durable snapshot storage capacity exhausted')
            connection.execute('INSERT INTO federation_snapshots VALUES(?,?,?,?)',
                               (manifest['snapshot_id'], canonical_payload(manifest), now_unix, total_bytes))
            connection.executemany('INSERT INTO federation_snapshot_nodes VALUES(?,?,?,?)',
                [(manifest['snapshot_id'], start, stop, value)
                 for (start, stop), value in tree._subtrees.items()])
            connection.executemany('INSERT INTO federation_snapshot_events VALUES(?,?,?,?)',
                [(manifest['snapshot_id'], i, event_id, by_id[event_id])
                 for i, event_id in enumerate(tree.identifiers)])
        return manifest

    @staticmethod
    def _load(connection, snapshot_id):
        require_digest(snapshot_id)
        row = connection.execute('SELECT manifest FROM federation_snapshots WHERE id=?', (snapshot_id,)).fetchone()
        if row is None:
            raise KeyError('Unknown immutable snapshot')
        manifest = validate_manifest(json.loads(row['manifest']))
        rows = connection.execute('SELECT position,event_id,envelope FROM federation_snapshot_events WHERE snapshot=? ORDER BY position',
                                  (snapshot_id,)).fetchall()
        if len(rows) != manifest['count'] or [r['position'] for r in rows] != list(range(len(rows))):
            raise ValueError('Stored snapshot positions corrupted')
        identifiers = [r['event_id'] for r in rows]
        tree = MerkleInventory(identifiers)
        if identifiers != list(tree.identifiers) or tree.manifest != manifest:
            raise ValueError('Stored snapshot commitment corrupted')
        for row in rows:
            if fingerprint(json.loads(row['envelope'])) != row['event_id']:
                raise ValueError('Stored snapshot event bytes corrupted')
        return manifest, rows, tree

    def manifest(self, snapshot_id):
        with self.database.transaction() as connection:
            manifest, _, _ = self._load(connection, snapshot_id)
            return manifest

    def page(self, snapshot_id, *, start=0, limit=20):
        with self.database.transaction() as connection:
            return self.page_in_transaction(connection, snapshot_id, start=start, limit=limit)

    def page_in_transaction(self, connection, snapshot_id, *, start=0, limit=20):
        """Fetch only requested event bytes and logarithmic proof nodes.

        Subtree caches are derived data. Every returned path is checked against
        the immutable manifest, so corrupt cached hashes fail closed. Full-store
        audit is separate from serving one bounded page.
        """
        manifest = self._manifest_in_transaction(connection, snapshot_id)
        count = manifest['count']
        if type(start) is not int or not 0 <= start <= count or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Invalid inventory page bounds')
        stop = min(count, start + limit)
        rows = connection.execute('SELECT position,event_id,envelope FROM federation_snapshot_events WHERE snapshot=? AND position>=? AND position<? ORDER BY position',
                                  (snapshot_id, start, stop)).fetchall()
        if [row['position'] for row in rows] != list(range(start, stop)):
            raise ValueError('Stored snapshot page positions corrupted')
        proofs, events = [], []
        previous = None
        for row in rows:
            envelope = json.loads(row['envelope'])
            canonical_payload(envelope)
            identifier = fingerprint(envelope)
            if identifier != row['event_id'] or (previous is not None and previous >= identifier):
                raise ValueError('Stored snapshot event bytes or ordering corrupted')
            previous = identifier
            siblings = []
            def descend(left, right, index):
                if right - left == 1:
                    return
                cut = left + _split(right - left)
                if index < cut:
                    descend(left, cut, index)
                    other_start, other_stop, side = cut, right, 'right'
                else:
                    descend(cut, right, index)
                    other_start, other_stop, side = left, cut, 'left'
                node = connection.execute('SELECT hash FROM federation_snapshot_nodes WHERE snapshot=? AND start=? AND stop=?',
                                          (snapshot_id, other_start, other_stop)).fetchone()
                if node is None:
                    raise ValueError('Stored Merkle subtree is missing')
                siblings.append({'side': side, 'hash': node['hash']})
            descend(0, count, row['position'])
            proof = {'schema_version': 1, 'snapshot_id': snapshot_id, 'index': row['position'],
                     'identifier': identifier, 'siblings': siblings}
            verify_membership(manifest, proof)
            proofs.append(proof)
            events.append(envelope)
        page = {'schema_version': 1, 'manifest': manifest, 'start': start, 'proofs': proofs,
                'next_position': stop if stop < count else None}
        body = {'schema_version': 1, 'inventory_page': page, 'events': events}
        canonical_payload(body)
        return body

    @staticmethod
    def _manifest_in_transaction(connection, snapshot_id):
        require_digest(snapshot_id)
        row = connection.execute('SELECT manifest FROM federation_snapshots WHERE id=?', (snapshot_id,)).fetchone()
        if row is None:
            raise KeyError('Unknown immutable snapshot')
        manifest = validate_manifest(json.loads(row['manifest']))
        if manifest['snapshot_id'] != snapshot_id:
            raise ValueError('Stored snapshot manifest binding corrupted')
        return manifest

    def audit_snapshot(self, snapshot_id):
        """Independently rebuild all nodes and compare immutable cached storage."""
        with self.database.transaction() as connection:
            manifest, rows, tree = self._load(connection, snapshot_id)
            cached = connection.execute('SELECT start,stop,hash FROM federation_snapshot_nodes WHERE snapshot=?',
                                        (snapshot_id,)).fetchall()
            if {(r['start'], r['stop']): r['hash'] for r in cached} != tree._subtrees:
                raise ValueError('Stored Merkle subtree cache corrupted')
            actual_bytes = sum(len(row['envelope'].encode()) for row in rows)
            declared = connection.execute('SELECT event_bytes FROM federation_snapshots WHERE id=?', (snapshot_id,)).fetchone()[0]
            if actual_bytes != declared:
                raise ValueError('Stored snapshot byte accounting corrupted')
            return {'valid': True, 'snapshot_id': snapshot_id, 'events': manifest['count'],
                    'subtrees': len(cached), 'event_bytes': actual_bytes,
                    'scope': 'local snapshot integrity; no scientific verification'}

    def revocation_proof(self, snapshot_id, event_id, *, max_chain=100):
        require_digest(event_id)
        if type(max_chain) is not int or not 1 <= max_chain <= 100:
            raise ValueError('Invalid chain proof budget')
        with self.database.transaction() as connection:
            return self.revocation_in_transaction(connection, snapshot_id, event_id, max_chain=max_chain)

    def revocation_in_transaction(self, connection, snapshot_id, event_id, *, max_chain=100):
        require_digest(event_id)
        if type(max_chain) is not int or not 1 <= max_chain <= 100:
            raise ValueError('Invalid chain proof budget')
        manifest, rows, tree = self._load(connection, snapshot_id)
        indexed = {r['event_id']: (i, json.loads(r['envelope'])) for i, r in enumerate(rows)}
        if event_id not in indexed:
            raise KeyError('Event not in requested snapshot')
        chain = []
        current = event_id
        while current is not None:
            if len(chain) >= max_chain:
                raise ValueError('Revocation chain exceeds budget')
            if current not in indexed:
                raise ValueError('Snapshot causal parent is missing')
            index, envelope = indexed[current]
            chain.append({'event': envelope, 'membership': tree.proof(index)})
            current = envelope['payload']['previous']
        chain.reverse()
        if chain[-1]['event']['payload']['action'] != 'revoke':
            raise ValueError('Requested event is not a revocation')
        proof = {'schema_version': 1, 'manifest': manifest, 'chain': chain}
        canonical_payload(proof)
        return proof

def verify_revocation_proof(proof, trust, *, expected_manifest):
    """Verify inclusion and operator chain with current pinned keys.

    Signatures are checked at their own declared issue time to permit historical
    evidence. This is not a trusted timestamp or a proof of timely admission.
    The expected manifest must come from an authenticated, fresh source response.
    """
    canonical_payload(proof)
    require_fields(proof, {'schema_version', 'manifest', 'chain'})
    if type(proof['schema_version']) is not int or proof['schema_version'] != 1:
        raise ValueError('Unsupported revocation proof')
    validate_manifest(expected_manifest)
    if proof['manifest'] != expected_manifest:
        raise ValueError('Revocation proof snapshot mismatch')
    chain = proof['chain']
    if type(chain) is not list or not 2 <= len(chain) <= 100:
        raise ValueError('Bounded complete revocation chain required')
    previous = None
    operator = artifact = None
    seen = set()
    for item in chain:
        require_fields(item, {'event', 'membership'})
        event = item['event']
        identifier = verify_membership(expected_manifest, item['membership'])
        if fingerprint(event) != identifier or identifier in seen:
            raise ValueError('Revocation event content binding mismatch')
        seen.add(identifier)
        if type(event) is not dict or type(event.get('issued_unix')) is not int:
            raise ValueError('Invalid historical event envelope')
        result = MessageVerifier(trust, AUDIENCE).verify(event, now_unix=event['issued_unix'])
        if not result['valid']:
            raise ValueError('Untrusted historical event signature')
        payload = result['payload']
        validate_payload(payload)
        if payload['previous'] != previous:
            raise ValueError('Incomplete revocation causal chain')
        if operator is None:
            operator, artifact = result['peer_id'], payload['artifact']
        elif operator != result['peer_id'] or artifact != payload['artifact']:
            raise ValueError('Revocation crosses operator or artifact')
        if payload['action'] == 'revoke' and item is not chain[-1]:
            raise ValueError('Revoked chain has a successor')
        previous = identifier
    if chain[-1]['event']['payload']['action'] != 'revoke':
        raise ValueError('Terminal event is not a revocation')
    return {'valid': True, 'operator': operator, 'artifact': artifact,
            'revocation_event_id': previous, 'snapshot_id': expected_manifest['snapshot_id'],
            'scientific_validity_established': False,
            'trusted_timestamp_established': False,
            'scope': 'signed operator revocation included in authenticated snapshot'}
