"""Durable revocation watches backed by signed request/response evidence.

A watch authenticates a configured source's observation and the author's signed
revocation. It does not certify operator independence, scientific truth, trusted
time, or that every revocation on the Internet has been found. Accepted revocations
are never automatically undone when a source disappears or returns an older root.
"""
import json
from pathlib import Path
import sqlite3
from contextlib import contextmanager

from ..core.semantic_contracts import canonical_payload, require_fields, require_text
from ..core.semantic_ir import fingerprint
from ..network.signatures import MessageVerifier
from ..network.merkle_inventory import validate_manifest

REQUEST_AUDIENCE = 'Nabla-federation-request-v1'
RESPONSE_PREFIX = 'Nabla-federation-response-v1:'


def validate_signed_exchange(exchange, trust, *, client_peer, server_peer, now_unix):
    """Verify current keys, domain, freshness, request hash and response operation."""
    canonical_payload(exchange)
    require_fields(exchange, {'schema_version', 'request', 'response'})
    if type(exchange['schema_version']) is not int or exchange['schema_version'] != 1:
        raise ValueError('Unsupported signed exchange evidence')
    request, response = exchange['request'], exchange['response']
    authenticated_request = MessageVerifier(trust, REQUEST_AUDIENCE).verify(request, now_unix=now_unix)
    authenticated_response = MessageVerifier(trust, RESPONSE_PREFIX + fingerprint({'peer': client_peer})).verify(response, now_unix=now_unix)
    if (not authenticated_request['valid'] or authenticated_request.get('peer_id') != client_peer
            or not authenticated_response['valid'] or authenticated_response.get('peer_id') != server_peer):
        raise ValueError('Untrusted signed exchange identity or freshness')
    payload = authenticated_request['payload']
    body = authenticated_response['payload']
    require_fields(body, {'schema_version', 'request_id', 'operation', 'result', 'scope'})
    if (type(body['schema_version']) is not int or body['schema_version'] != 1
            or type(payload) is not dict or body['request_id'] != fingerprint(request)
            or body['operation'] != payload.get('operation')
            or response['issued_unix'] < request['issued_unix']
            or response['expires_unix'] > request['expires_unix']):
        raise ValueError('Signed exchange request/response binding mismatch')
    return payload, body['result']


class RevocationMonitor:
    """Bounded durable audit with monotonic source inventory observations.

    Database paths, configured identities and trust anchors are local operator
    configuration. Audit hashes detect accidental changes when the expected head
    is independently retained; they do not protect against a fully rewriting DBA.
    """
    def __init__(self, path, trust, *, client_peer, max_observations=10000,
                 max_sources=1000, max_evidence_bytes=64 * 1024 * 1024):
        require_text(client_peer, 'local peer', limit=200)
        for value, maximum in ((max_observations, 1000000), (max_sources, 10000),
                               (max_evidence_bytes, 1024 * 1024 * 1024)):
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError('Invalid revocation-watch storage budget')
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.trust = trust
        self.client_peer = client_peer
        self.max_observations = max_observations
        self.max_sources = max_sources
        self.max_evidence_bytes = max_evidence_bytes
        with self._transaction() as connection:
            connection.executescript('''
              CREATE TABLE IF NOT EXISTS watch_sources(
                peer TEXT PRIMARY KEY, count INTEGER NOT NULL, root TEXT NOT NULL,
                last_issued INTEGER NOT NULL, last_observed INTEGER NOT NULL);
              CREATE TABLE IF NOT EXISTS watch_observations(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                source TEXT NOT NULL, operator TEXT NOT NULL, artifact TEXT NOT NULL,
                event_id TEXT NOT NULL, public_key TEXT NOT NULL,
                observed INTEGER NOT NULL, evidence TEXT NOT NULL,
                evidence_bytes INTEGER NOT NULL, previous TEXT, receipt TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS watch_artifact ON watch_observations(artifact,operator);
            ''')

    @contextmanager
    def _transaction(self):
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
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

    def observe(self, manifest_exchange, revocation_exchange, *, source_peer, now_unix):
        """Record one authenticated revocation without trusting caller-only metadata."""
        from services.federation.inventory import verify_revocation_proof
        require_text(source_peer, 'source peer', limit=200)
        if type(now_unix) is not int or now_unix < 0:
            raise ValueError('Explicit observation clock required')
        manifest_request, manifest = validate_signed_exchange(manifest_exchange, self.trust,
            client_peer=self.client_peer, server_peer=source_peer, now_unix=now_unix)
        revocation_request, proof = validate_signed_exchange(revocation_exchange, self.trust,
            client_peer=self.client_peer, server_peer=source_peer, now_unix=now_unix)
        validate_manifest(manifest)
        if (manifest_request.get('operation') != 'manifest'
                or manifest_request.get('snapshot_id') != manifest['snapshot_id']
                or revocation_request.get('operation') != 'revocation'
                or revocation_request.get('snapshot_id') != manifest['snapshot_id']):
            raise ValueError('Watch evidence does not refer to one authenticated snapshot')
        report = verify_revocation_proof(proof, self.trust, expected_manifest=manifest)
        if report['revocation_event_id'] != revocation_request.get('event_id'):
            raise ValueError('Revocation proof does not match signed request')
        source_issued = max(manifest_exchange['response']['issued_unix'], revocation_exchange['response']['issued_unix'])
        evidence = {'manifest_exchange': manifest_exchange, 'revocation_exchange': revocation_exchange}
        encoded = canonical_payload(evidence)
        evidence_id = fingerprint(evidence)
        key = proof['chain'][-1]['event']['public_key']
        with self._transaction() as connection:
            last = connection.execute('SELECT * FROM watch_observations ORDER BY sequence DESC LIMIT 1').fetchone()
            if last and now_unix < last['observed']:
                raise ValueError('Persistent watch clock rollback')
            source = connection.execute('SELECT * FROM watch_sources WHERE peer=?', (source_peer,)).fetchone()
            if source:
                if manifest['count'] < source['count'] or source_issued < source['last_issued']:
                    raise ValueError('Source observation rollback')
                if manifest['count'] == source['count'] and manifest['root'] != source['root']:
                    raise ValueError('Source equivocated at the same inventory size')
            elif connection.execute('SELECT count(*) FROM watch_sources').fetchone()[0] >= self.max_sources:
                raise ValueError('Watch source capacity exhausted')
            existing = connection.execute('SELECT receipt FROM watch_observations WHERE id=?', (evidence_id,)).fetchone()
            if existing:
                return json.loads(existing['receipt'])
            count, used = connection.execute('SELECT count(*),coalesce(sum(evidence_bytes),0) FROM watch_observations').fetchone()
            if count >= self.max_observations or used + len(encoded.encode()) > self.max_evidence_bytes:
                raise ValueError('Durable revocation evidence capacity exhausted')
            previous = None if last is None else fingerprint(json.loads(last['receipt']))
            body = {'schema_version': 1, 'evidence_id': evidence_id, 'source_peer': source_peer,
                    'operator': report['operator'], 'artifact': report['artifact'],
                    'revocation_event_id': report['revocation_event_id'],
                    'snapshot_id': manifest['snapshot_id'], 'observed_unix': now_unix,
                    'previous_receipt': previous, 'trusted_timestamp_established': False}
            receipt = {**body, 'receipt_id': fingerprint(body)}
            connection.execute('INSERT INTO watch_observations(id,source,operator,artifact,event_id,public_key,observed,evidence,evidence_bytes,previous,receipt) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (evidence_id, source_peer, report['operator'], report['artifact'], report['revocation_event_id'],
                 key, now_unix, encoded, len(encoded.encode()), previous, canonical_payload(receipt)))
            connection.execute('INSERT OR REPLACE INTO watch_sources VALUES(?,?,?,?,?)',
                (source_peer, manifest['count'], manifest['root'], source_issued, now_unix))
        return receipt

    def status(self, artifact):
        from ..core.semantic_contracts import require_digest
        require_digest(artifact)
        with self._transaction() as connection:
            rows = connection.execute('SELECT operator,event_id,source,public_key,observed FROM watch_observations WHERE artifact=? ORDER BY sequence',
                                      (artifact,)).fetchall()
        return {'artifact': artifact, 'revoked': bool(rows),
                'observations': [{'operator': r['operator'], 'event_id': r['event_id'],
                    'source': r['source'], 'observed_unix': r['observed'],
                    'author_key_currently_trusted': self.trust.accepts(r['operator'], r['public_key'])} for r in rows],
                'scope': 'known authenticated operator revocations; no global completeness guarantee'}

    def audit(self, *, expected_head=None):
        """Replay stored evidence and receipt hashes without renewing old freshness.

        Historical signature validation uses each exchange's original observation
        time. Current pinned-key revocation is still enforced and may invalidate
        the authentication of older evidence; the conservative revoked flag stays.
        """
        with self._transaction() as connection:
            rows = connection.execute('SELECT * FROM watch_observations ORDER BY sequence').fetchall()
            stored_sources = {row['peer']: dict(row) for row in connection.execute('SELECT * FROM watch_sources')}
        previous = None
        last_observed = -1
        reconstructed_sources = {}
        for row in rows:
            receipt = json.loads(row['receipt'])
            body = {k: v for k, v in receipt.items() if k != 'receipt_id'}
            evidence = json.loads(row['evidence'])
            if (receipt.get('receipt_id') != fingerprint(body) or receipt.get('previous_receipt') != previous
                    or row['previous'] != previous or fingerprint(evidence) != row['id']
                    or receipt.get('evidence_id') != row['id']
                    or len(row['evidence'].encode()) != row['evidence_bytes']
                    or canonical_payload(evidence) != row['evidence']):
                raise ValueError('Revocation audit hash chain corrupted')
            manifest_request, manifest = validate_signed_exchange(evidence['manifest_exchange'], self.trust,
                client_peer=self.client_peer, server_peer=row['source'], now_unix=row['observed'])
            revocation_request, proof = validate_signed_exchange(evidence['revocation_exchange'], self.trust,
                client_peer=self.client_peer, server_peer=row['source'], now_unix=row['observed'])
            from services.federation.inventory import verify_revocation_proof
            result = verify_revocation_proof(proof, self.trust, expected_manifest=manifest)
            if (result['revocation_event_id'] != row['event_id'] or result['operator'] != row['operator']
                    or result['artifact'] != row['artifact']
                    or proof['chain'][-1]['event']['public_key'] != row['public_key']
                    or receipt.get('snapshot_id') != manifest['snapshot_id']
                    or receipt.get('source_peer') != row['source']
                    or receipt.get('operator') != row['operator'] or receipt.get('artifact') != row['artifact']
                    or receipt.get('revocation_event_id') != row['event_id']
                    or receipt.get('observed_unix') != row['observed']
                    or manifest_request.get('operation') != 'manifest'
                    or revocation_request.get('operation') != 'revocation'
                    or revocation_request.get('event_id') != row['event_id']
                    or manifest_request.get('snapshot_id') != manifest['snapshot_id']
                    or revocation_request.get('snapshot_id') != manifest['snapshot_id']):
                raise ValueError('Revocation audit semantic binding corrupted')
            if row['observed'] < last_observed:
                raise ValueError('Revocation audit observation clock rollback')
            issued = max(evidence['manifest_exchange']['response']['issued_unix'],
                         evidence['revocation_exchange']['response']['issued_unix'])
            earlier = reconstructed_sources.get(row['source'])
            if earlier and (manifest['count'] < earlier['count'] or issued < earlier['last_issued']
                    or (manifest['count'] == earlier['count'] and manifest['root'] != earlier['root'])):
                raise ValueError('Revocation audit source rollback or equivocation')
            reconstructed_sources[row['source']] = {'peer': row['source'], 'count': manifest['count'],
                'root': manifest['root'], 'last_issued': issued, 'last_observed': row['observed']}
            last_observed = row['observed']
            previous = fingerprint(receipt)
        if reconstructed_sources != stored_sources:
            raise ValueError('Revocation watch source cache corrupted')
        if expected_head is not None and previous != expected_head:
            raise ValueError('Revocation audit external head mismatch')
        return {'valid': True, 'observations': len(rows), 'head': previous,
                'scope': 'local retained evidence; external retention required to detect complete rewrite'}
