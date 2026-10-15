"""Signed multi-operator provenance with persistent causal chains and revocations.

Admission requires configured issuer keys. Distinct keys are not evidence of
independent humans; this log deliberately makes no Sybil resistance claim.
"""
import json
import sqlite3
from ..core.semantic_contracts import canonical_payload
from ..core.semantic_ir import fingerprint
from ..network.signatures import sign_message, MessageVerifier

AUDIENCE = 'distributed-provenance-v1'


def provenance_event(private_key, *, operator, artifact, action, previous=None,
                     references=(), nonce, issued_unix, expires_unix):
    payload = dict(kind=AUDIENCE, artifact=artifact, action=action,
                   previous=previous, references=list(references))
    validate_payload(payload)
    return sign_message(payload, private_key, peer_id=operator, audience=AUDIENCE,
                        nonce=nonce, issued_unix=issued_unix, expires_unix=expires_unix)


def _digest(value):
    if type(value) is not str or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Expected SHA256 identifier')


def validate_payload(payload):
    if type(payload) is not dict or set(payload)!={'kind','artifact','action','previous','references'}:
        raise ValueError('Invalid provenance fields')
    if payload['kind'] != AUDIENCE or payload['action'] not in {'publish','endorse','revoke'}:
        raise ValueError('Invalid provenance action')
    _digest(payload['artifact'])
    if payload['previous'] is not None:
        _digest(payload['previous'])
    refs=payload['references']
    if type(refs) is not list or len(refs)>128:
        raise ValueError('Invalid references')
    for value in refs:
        _digest(value)
    if len(set(refs))!=len(refs):
        raise ValueError('Duplicate references')
    if payload['action']=='revoke' and payload['previous'] is None:
        raise ValueError('Revocation requires previous event')


class ProvenanceLog:
    def __init__(self, path, trust, *, capacity=10000):
        if type(capacity) is not int or capacity<1:
            raise ValueError('Invalid event capacity')
        self.trust, self.capacity = trust, capacity
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, operator TEXT NOT NULL,
          nonce TEXT NOT NULL, artifact TEXT NOT NULL, previous TEXT, action TEXT NOT NULL,
          envelope TEXT NOT NULL, UNIQUE(operator,nonce));
        CREATE UNIQUE INDEX IF NOT EXISTS one_child ON events(previous) WHERE previous IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS one_root ON events(operator,artifact) WHERE previous IS NULL;
        CREATE TABLE IF NOT EXISTS clock(id INTEGER PRIMARY KEY CHECK(id=1), now INTEGER NOT NULL);
        ''')

    def close(self):
        self.db.close()

    def ingest(self, envelope, *, now_unix):
        encoded=canonical_payload(envelope)
        result=MessageVerifier(self.trust,AUDIENCE).verify(envelope,now_unix=now_unix)
        if not result['valid']:
            raise ValueError(result['reason'])
        payload=result['payload']; validate_payload(payload)
        identifier=fingerprint(envelope)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            clock=self.db.execute('SELECT now FROM clock WHERE id=1').fetchone()
            if clock and now_unix<clock[0]:
                raise ValueError('Clock rollback')
            existing=self.db.execute('SELECT envelope FROM events WHERE id=?',(identifier,)).fetchone()
            if existing:
                self.db.execute('INSERT OR REPLACE INTO clock VALUES(1,?)',(now_unix,))
                return identifier
            if self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]>=self.capacity:
                raise ValueError('Event capacity exhausted')
            parent=payload['previous']
            if parent is not None:
                row=self.db.execute('SELECT operator,artifact,action FROM events WHERE id=?',(parent,)).fetchone()
                if row is None:
                    raise ValueError('Missing causal parent')
                if row[:2] != (result['peer_id'],payload['artifact']):
                    raise ValueError('Cannot rewrite another operator or artifact')
                if row[2]=='revoke':
                    raise ValueError('Revoked chain is terminal')
                if self.db.execute('SELECT 1 FROM events WHERE previous=?',(parent,)).fetchone():
                    raise ValueError('Operator chain fork')
            elif self.db.execute('SELECT 1 FROM events WHERE operator=? AND artifact=?',
                                 (result['peer_id'],payload['artifact'])).fetchone():
                raise ValueError('Root already exists')
            try:
                self.db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?)',
                                (identifier,result['peer_id'],envelope['nonce'],payload['artifact'],
                                 parent,payload['action'],encoded))
            except sqlite3.IntegrityError as exc:
                raise ValueError('Persistent replay detected') from exc
            self.db.execute('INSERT OR REPLACE INTO clock VALUES(1,?)',(now_unix,))
        return identifier

    def contains(self, identifier):
        _digest(identifier)
        return self.db.execute('SELECT 1 FROM events WHERE id=?',(identifier,)).fetchone() is not None

    def export(self):
        # ROWID preserves causal insertion order, not a global chronology claim.
        return [json.loads(row[0]) for row in self.db.execute('SELECT envelope FROM events ORDER BY rowid')]

    def status(self, artifact):
        _digest(artifact)
        rows=self.db.execute('''SELECT e.id,e.operator,e.action FROM events e
          WHERE artifact=? AND NOT EXISTS(SELECT 1 FROM events c WHERE c.previous=e.id)
          ORDER BY e.operator''',(artifact,)).fetchall()
        return {'artifact':artifact,'operators':[{'event_id':r[0],'operator':r[1],
                  'revoked':r[2]=='revoke','action':r[2]} for r in rows],
                'scientific_validity_established':False,'operator_independence_established':False}
