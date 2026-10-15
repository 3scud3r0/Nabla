"""Transactional, replay-checked record staging with persistent split isolation."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from ..core.semantic_ir import canonical_json, fingerprint
from .schema import ScientificRecord
from .research_record import ResearchRecord,parse_record
from .semantic_fingerprint import semantic_fingerprint


class RecordStore:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, semantic TEXT NOT NULL, split TEXT NOT NULL, payload TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS semantic_records ON records(semantic)')
            db.execute('CREATE TABLE IF NOT EXISTS batches (id TEXT PRIMARY KEY, count INTEGER NOT NULL)')

    def ingest(self,records,*,batch_id,max_records=10000):
        if not isinstance(batch_id,str) or not batch_id.strip() or len(batch_id)>256 or type(max_records) is not int or not 1<=max_records<=100000:
            raise ValueError('Identificador e orçamento de lote obrigatórios')
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT count FROM batches WHERE id=?',(batch_id,)).fetchone()
            if old:raise ValueError('Lote já confirmado; não repetir ingestão')
            count=0
            for record in records:
                count+=1
                if count>max_records:raise ValueError('Lote excede orçamento')
                if not isinstance(record,(ScientificRecord,ResearchRecord)):raise ValueError('Registro científico obrigatório')
                data=record.to_data();record=parse_record(data)
                key=record.semantic_id if isinstance(record,ResearchRecord) else semantic_fingerprint(record)
                split=data['split'];payload=canonical_json(data)
                if len(payload.encode())>4*1024*1024:raise ValueError('Registro excede limite')
                conflicting=db.execute('SELECT split FROM records WHERE semantic=? AND split<>?',(key,split)).fetchone()
                if conflicting:raise ValueError('Vazamento semântico entre partições')
                existing=db.execute('SELECT payload FROM records WHERE id=?',(record.content_id,)).fetchone()
                if existing and existing[0]!=payload:raise ValueError('ID em conflito')
                db.execute('INSERT OR IGNORE INTO records VALUES (?,?,?,?)',(record.content_id,key,split,payload))
            if not count:raise ValueError('Lote vazio')
            db.execute('INSERT INTO batches VALUES (?,?)',(batch_id,count))
        return {'batch_id':batch_id,'submitted':count,'committed':True}

    def records(self,*,split=None,batch_size=128):
        if split not in (None,'train','validation','test') or type(batch_size) is not int or not 1<=batch_size<=1000:
            raise ValueError('Filtro ou lote inválido')
        with closing(sqlite3.connect(self.path)) as db:
            cursor=db.execute('SELECT payload FROM records'+(' WHERE split=?' if split else '')+' ORDER BY id',(split,) if split else ())
            while True:
                rows=cursor.fetchmany(batch_size)
                if not rows:return
                for row in rows:yield parse_record(json.loads(row[0]))

    def export_jsonl(self,destination,**limits):
        from .serializer import write_atomic
        return write_atomic(self.records(),destination,**limits)
