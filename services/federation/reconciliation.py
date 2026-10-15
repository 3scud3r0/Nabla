"""Durable anti-entropy over independently signed provenance events.

Missing parents remain pending across restarts. Conflicts are quarantined and
never majority-voted into truth. Delivery can be reordered, repeated or lost.
"""
import json
import sqlite3
from nablamath.core.semantic_contracts import canonical_payload
from nablamath.core.semantic_ir import fingerprint
from nablamath.knowledge.distributed_provenance import ProvenanceLog


class Reconciler:
    def __init__(self, path, log, *, max_pending=10000, max_total=100000):
        if (not isinstance(log,ProvenanceLog) or type(max_pending) is not int or max_pending<1
                or type(max_total) is not int or max_total<max_pending):
            raise ValueError('Invalid reconciliation configuration')
        self.log=log; self.max_pending=max_pending; self.max_total=max_total
        self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS inbox(id TEXT PRIMARY KEY,envelope TEXT NOT NULL,state TEXT NOT NULL,reason TEXT)')
        self.db.commit()

    def close(self):
        self.db.close()

    def receive(self,envelopes,*,now_unix):
        if type(envelopes) is not list or len(envelopes)>1000:
            raise ValueError('Bounded batch required')
        # Validate and bound every item before mutating any inbox state.
        batch=[(fingerprint(e),canonical_payload(e)) for e in envelopes]
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            total=self.db.execute('SELECT COUNT(*) FROM inbox').fetchone()[0]
            count=self.db.execute("SELECT COUNT(*) FROM inbox WHERE state='pending'").fetchone()[0]
            new=[row for row in dict(batch).items() if not self.db.execute('SELECT 1 FROM inbox WHERE id=?',(row[0],)).fetchone()]
            if count+len(new)>self.max_pending or total+len(new)>self.max_total:
                raise ValueError('Pending capacity exhausted')
            self.db.executemany("INSERT INTO inbox VALUES(?,?,'pending',NULL)",new)
        progress=True
        while progress:
            progress=False
            rows=self.db.execute("SELECT id,envelope FROM inbox WHERE state='pending' ORDER BY rowid").fetchall()
            for identifier,encoded in rows:
                try:
                    if not self.log.contains(identifier):
                        self.log.ingest(json.loads(encoded),now_unix=now_unix)
                    state,reason='accepted',None
                except ValueError as exc:
                    reason=str(exc)
                    if reason=='Missing causal parent':
                        continue
                    state='quarantined'
                with self.db:
                    self.db.execute('UPDATE inbox SET state=?,reason=? WHERE id=?',(state,reason,identifier))
                progress=True
        return self.report()

    def report(self):
        rows=self.db.execute('SELECT id,state,reason FROM inbox ORDER BY id').fetchall()
        return {'schema_version':1,'events':[dict(event_id=i,state=s,reason=r) for i,s,r in rows],
                'conflict_resolution':'retain signed histories; reject operator forks',
                'scope':'durable local delivery; independent multihost deployment unverified'}

    def missing(self,remote_ids):
        if type(remote_ids) is not list or len(remote_ids)>10000:
            raise ValueError('Bounded inventory required')
        known={fingerprint(e) for e in self.log.export()}
        for item in remote_ids:
            if type(item) is not str or len(item)!=64 or any(c not in '0123456789abcdef' for c in item):
                raise ValueError('Invalid inventory identifier')
        return sorted(set(remote_ids)-known)
