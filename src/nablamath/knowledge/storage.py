"""Durable content-addressed signed snapshot exchange, quarantine and delta inventory."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from ..core.semantic_ir import canonical_json,fingerprint
from .identity import PeerTrust,PeerKey,verify_signed_snapshot
from .federation import SignedFederation


class SnapshotStore:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, envelope TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS quarantine (id TEXT PRIMARY KEY, reason TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS trust (peer TEXT NOT NULL, key TEXT NOT NULL, revoked INTEGER NOT NULL, PRIMARY KEY(peer,key))')

    def trust(self):
        with closing(sqlite3.connect(self.path)) as db:
            rows=db.execute('SELECT peer,key,revoked FROM trust ORDER BY peer,key').fetchall()
        return PeerTrust(PeerKey(peer,key,bool(revoked)) for peer,key,revoked in rows)

    def pin(self,key):
        trust=self.trust();trust.pin(key)
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT revoked FROM trust WHERE peer=? AND key=?',(key.peer_id,key.public_key)).fetchone()
            if existing and existing[0] and not key.revoked:raise ValueError('Chave revogada')
            db.execute('INSERT OR REPLACE INTO trust VALUES (?,?,?)',(key.peer_id,key.public_key,int(key.revoked)))

    def ingest(self,envelope):
        raw=canonical_json(envelope)
        if len(raw.encode())>32*1024*1024:raise ValueError('Envelope excede limite')
        identifier=fingerprint(envelope)
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('BEGIN IMMEDIATE')
            trust=PeerTrust(PeerKey(peer,key,bool(revoked)) for peer,key,revoked in db.execute('SELECT peer,key,revoked FROM trust'))
            verification=verify_signed_snapshot(envelope,trust)
            if verification['valid']:
                db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?)',(identifier,raw))
            else:
                db.execute('INSERT OR REPLACE INTO quarantine VALUES (?,?)',(identifier,verification.get('reason','invalid evidence')))
        return {**verification,'envelope_id':identifier,'quarantined':not verification['valid']}

    def inventory(self):
        with closing(sqlite3.connect(self.path)) as db:
            return tuple(row[0] for row in db.execute('SELECT id FROM snapshots ORDER BY id'))

    def delta(self,known=(),*,limit=100):
        known=set(known)
        if len(known)>10000 or type(limit) is not int or not 1<=limit<=100:raise ValueError('Orçamento de sincronização inválido')
        trust=self.trust();result=[]
        with closing(sqlite3.connect(self.path)) as db:
            for identifier,raw in db.execute('SELECT id,envelope FROM snapshots ORDER BY id'):
                if identifier in known:continue
                envelope=json.loads(raw)
                if fingerprint(envelope)!=identifier or not verify_signed_snapshot(envelope,trust)['valid']:
                    raise ValueError('Snapshot persistido alterado ou confiança revogada')
                result.append(envelope)
                if len(result)==limit:break
        return result

    def reconcile(self,*,metadata=None):
        federation=SignedFederation(self.trust())
        known=set()
        while True:
            page=self.delta(known)
            if not page:break
            for envelope in page:
                known.add(fingerprint(envelope));federation.ingest(envelope)
        return federation.reconcile(metadata=metadata)

    def quarantined(self):
        with closing(sqlite3.connect(self.path)) as db:
            return tuple({'envelope_id':i,'reason':r} for i,r in db.execute('SELECT id,reason FROM quarantine ORDER BY id'))
