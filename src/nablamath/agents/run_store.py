"""Durable CAS checkpoints for replayable, trusted scientific tool plans.

This is not exactly-once execution of external side effects. A crash between a
pure tool call and its checkpoint may require reexecution. Resume accepts only
receipts reproducible by the known scientific tools.
"""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from ..core.semantic_ir import canonical_json
from .planner import verify_run


class RunStore:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS runs (proposal TEXT PRIMARY KEY, head TEXT NOT NULL, report TEXT NOT NULL)')

    def load(self,proposal_id):
        with closing(sqlite3.connect(self.path)) as db:
            row=db.execute('SELECT report FROM runs WHERE proposal=?',(proposal_id,)).fetchone()
        if row is None:return None
        report=json.loads(row[0])
        if not verify_run(report):raise ValueError('Checkpoint não reproduzível')
        return report

    def save(self,report,*,expected_head):
        if not verify_run(report):raise ValueError('Recibo não reproduzível; checkpoint recusado')
        raw=canonical_json(report)
        if len(raw.encode())>32*1024*1024:raise ValueError('Checkpoint excede limite')
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT head FROM runs WHERE proposal=?',(report['proposal_id'],)).fetchone()
            if (row[0] if row else None)!=expected_head:raise ValueError('Checkpoint alterado por outro executor')
            db.execute('INSERT OR REPLACE INTO runs VALUES (?,?,?)',(report['proposal_id'],report['final_receipt'],raw))
