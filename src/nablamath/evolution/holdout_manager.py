"""Persistent one-use holdouts. Trusted local filesystem, not secret-data isolation."""
from contextlib import closing
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
from ..core.semantic_ir import canonical_json, fingerprint
from ..worlds import ModelSpec
from .evaluator import evaluate_proposal, _model_id
from .proposal_validator import validate_proposal


class HoldoutManager:
    def __init__(self,path,contract):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.contract=contract
        contract.assert_current()
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS suites (id TEXT PRIMARY KEY, payload TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0)')
            db.execute('CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, suite TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS receipts (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')

    def register(self,cases,calibration,*,label):
        cases,calibration=tuple(cases),tuple(calibration)
        if not 5<=len(cases)<=64 or not 1<=len(calibration)<=64 or not label.strip():
            raise ValueError('Holdout 5–64, calibração 1–64 e rótulo obrigatórios')
        ids=[_model_id(m) for m in cases]; train=[_model_id(m) for m in calibration]
        if len(set(ids))!=len(ids) or len(set(train))!=len(train) or set(ids)&set(train):
            raise ValueError('Duplicatas ou contaminação')
        payload={'cases':[asdict(m) for m in cases],'calibration_ids':train,'label':label,
                 'contract_id':self.contract.contract_id}
        key=fingerprint(payload)
        try:
            with closing(sqlite3.connect(self.path)) as db,db:
                db.execute('INSERT INTO suites(id,payload) VALUES (?,?)',(key,canonical_json(payload)))
                db.executemany('INSERT INTO cases VALUES (?,?)',((i,key) for i in ids))
        except sqlite3.IntegrityError as exc:
            raise ValueError('Caso já reservado/usado neste gerenciador') from exc
        return key

    def evaluate_once(self,suite_id,candidate,baseline,calibration):
        validate_proposal(candidate,baseline,self.contract)
        calibration=tuple(calibration)
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT payload,consumed FROM suites WHERE id=?',(suite_id,)).fetchone()
            if row is None or row[1]:
                raise ValueError('Holdout ausente ou já consumido')
            payload=json.loads(row[0])
            if payload['contract_id']!=self.contract.contract_id or payload['calibration_ids']!=[_model_id(m) for m in calibration]:
                raise ValueError('Contrato ou calibração divergente')
            db.execute('UPDATE suites SET consumed=1 WHERE id=?',(suite_id,))
        # Consume before execution: a crash or invalid attempt cannot expose a reusable holdout.
        cases=tuple(ModelSpec(**m) for m in payload['cases'])
        report=evaluate_proposal(candidate.as_policy(),baseline.as_policy(),calibration,cases,
                    tolerance=self.contract.tolerance,alpha=self.contract.alpha/self.contract.max_generations,
                    max_derivative_calls=self.contract.max_derivative_calls)
        receipt={'schema_version':1,'suite_id':suite_id,'candidate':candidate.to_data(),'baseline':baseline.to_data(),
                 'calibration':[asdict(m) for m in calibration],'holdout':payload['cases'],
                 'contract':self.contract.to_data(),'contract_id':self.contract.contract_id,'evaluation':report}
        key=fingerprint(receipt)
        result={**receipt,'receipt_id':key}
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('INSERT INTO receipts VALUES (?,?)',(key,canonical_json(result)))
        return result

    def contains_receipt(self,receipt):
        with closing(sqlite3.connect(self.path)) as db:
            row=db.execute('SELECT payload FROM receipts WHERE id=?',(receipt['receipt_id'],)).fetchone()
        return row is not None and row[0]==canonical_json(receipt)
