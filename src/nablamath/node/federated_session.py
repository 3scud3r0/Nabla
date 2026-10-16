"""Consent-gated authenticated object admission with durable resource accounting.

Transport processes invoke this boundary with received bytes. It is not an OS
sandbox, transport listener or promise of independently deployed host validation.
"""
import json
import sqlite3
from ..network.signatures import MessageVerifier
from ..network.objects import KnowledgeObject
from ..core.semantic_contracts import canonical_payload
from ..core.semantic_ir import fingerprint
from .local import LocalNode
from .consent import ConsentStore
from .resources import ResourceBudget

AUDIENCE='node-object-admission-v1'


class FederatedSession:
    def __init__(self,path,node,consent,trust,budget):
        if not isinstance(node,LocalNode) or not isinstance(consent,ConsentStore) or not isinstance(budget,ResourceBudget):
            raise ValueError('Explicit node, consent and resource policy required')
        self.node=node;self.consent=consent;self.trust=trust;self.budget=budget
        self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS admissions(id TEXT PRIMARY KEY,peer TEXT,nonce TEXT,bytes INTEGER,receipt TEXT,UNIQUE(peer,nonce))')
        self.db.execute('CREATE TABLE IF NOT EXISTS session_clock(id INTEGER PRIMARY KEY CHECK(id=1),now INTEGER NOT NULL)')
        self.db.commit()

    def close(self):
        self.db.close()

    def receive(self,raw,*,now_unix,on_battery=False):
        if type(now_unix) is not int or now_unix<0 or type(on_battery) is not bool:
            raise ValueError('Invalid runtime observation')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            clock=self.db.execute('SELECT now FROM session_clock WHERE id=1').fetchone()
            if clock and now_unix<clock[0]:raise ValueError('Persistent clock rollback')
            self.db.execute('INSERT OR REPLACE INTO session_clock VALUES(1,?)',(now_unix,))
        consent=self.consent.load()
        if not consent.active(now_unix) or not consent.allow_network or (on_battery and not consent.allow_on_battery):
            raise PermissionError('Current local consent forbids network contribution')
        if type(raw) is not bytes or not 0<len(raw)<=1048576:
            raise ValueError('Bounded envelope bytes required')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            return self._admit(raw,now_unix,on_battery)

    def _admit(self,raw,now_unix,on_battery):
        clock=self.db.execute('SELECT now FROM session_clock WHERE id=1').fetchone()
        if clock and now_unix<clock[0]:raise ValueError('Concurrent clock rollback')
        consent=self.consent.load()
        if not consent.active(now_unix) or not consent.allow_network or (on_battery and not consent.allow_on_battery):
            raise PermissionError('Local consent revoked before admission')
        used=self.db.execute('SELECT COALESCE(SUM(bytes),0) FROM admissions').fetchone()[0]
        if used+len(raw)>self.budget.network_bytes:
            raise PermissionError('Session network admission quota exhausted')
        def pairs(items):
            result={}
            for k,v in items:
                if k in result:raise ValueError('Duplicate JSON key')
                result[k]=v
            return result
        envelope=json.loads(raw,object_pairs_hook=pairs)
        result=MessageVerifier(self.trust,AUDIENCE).verify(envelope,now_unix=now_unix)
        if not result['valid']:raise ValueError(result['reason'])
        payload=result['payload']
        if type(payload) is not dict or set(payload)!={'object','expected_id'}:
            raise ValueError('Invalid admission payload')
        item=KnowledgeObject.from_bytes(canonical_payload(payload['object']).encode())
        if item.object_id!=payload['expected_id']:
            raise ValueError('Object identifier mismatch')
        if self.db.execute('SELECT 1 FROM admissions WHERE peer=? AND nonce=?',
                           (result['peer_id'],envelope['nonce'])).fetchone():
            raise ValueError('Durable replay detected')
        receipt={'schema_version':1,'object_id':item.object_id,'peer':result['peer_id'],
                 'envelope_id':fingerprint(envelope),'admitted_bytes':len(raw),
                 'now_unix':now_unix,'scientific_validity_established':False,
                 'scope':'authenticated policy admission; network ingress bandwidth outside boundary'}
        identifier=fingerprint(receipt)
        # Content-store write is idempotent. A crash before audit commit may retry
        # the same object; it cannot rewrite its content-addressed identifier.
        self.node.ingest(item)
        self.db.execute('INSERT INTO admissions VALUES(?,?,?,?,?)',
                        (identifier,result['peer_id'],envelope['nonce'],len(raw),canonical_payload(receipt)))
        return {**receipt,'receipt_id':identifier}

    def telemetry(self):
        rows=self.db.execute('SELECT receipt FROM admissions ORDER BY rowid').fetchall()
        return {'receipts':[json.loads(r[0]) for r in rows],
                'total_admitted_bytes':sum(json.loads(r[0])['admitted_bytes'] for r in rows),
                'resource_enforcement':'admission byte budget; OS CPU/memory and disk quota enforcement not established'}
