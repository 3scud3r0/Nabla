"""Persistent release state with compare-and-swap promotion and known-policy rollback."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from ..core.semantic_ir import canonical_json
from .policy_genome import PolicyGenome
from .lineage import Lineage
from .release_gate import release_gate


class PolicyStore:
    def __init__(self,path,baseline):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
            row=db.execute('SELECT payload FROM state WHERE id=1').fetchone()
            if row is None:
                lineage=Lineage();lineage.append(action='baseline',genome_id=baseline.genome_id)
                data={'active':baseline.genome_id,'genomes':{baseline.genome_id:baseline.to_data()},'events':lineage.events}
                db.execute('INSERT INTO state VALUES (1,?)',(canonical_json(data),))

    def snapshot(self):
        with closing(sqlite3.connect(self.path)) as db:
            data=json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
        Lineage(data['events'])
        if data['active'] not in data['genomes']:
            raise ValueError('Estado ativo ausente')
        for key,value in data['genomes'].items():
            if PolicyGenome.from_data(value).genome_id!=key:
                raise ValueError('Genoma adulterado')
        return data

    def promote(self,candidate,receipt,contract,*,manager,expected_active):
        gate=release_gate(receipt,contract,manager=manager)
        if not gate['accepted'] or receipt['candidate']!=candidate.to_data():
            raise ValueError('Liberação rejeitada: '+str(gate))
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('BEGIN IMMEDIATE')
            data=json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
            if data['active']!=expected_active or candidate.parent_id!=expected_active:
                raise ValueError('Política ativa mudou ou pai divergente')
            lineage=Lineage(data['events']);lineage.append(action='accepted',genome_id=candidate.genome_id,receipt_id=receipt['receipt_id'])
            data['active']=candidate.genome_id;data['genomes'][candidate.genome_id]=candidate.to_data();data['events']=lineage.events
            db.execute('UPDATE state SET payload=? WHERE id=1',(canonical_json(data),))
        return gate

    def record_rejection(self,candidate,receipt,contract,*,manager,expected_active):
        gate=release_gate(receipt,contract,manager=manager)
        if gate['accepted'] or not manager.contains_receipt(receipt):
            raise ValueError('Recibo não é uma rejeição emitida pelo gerenciador')
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('BEGIN IMMEDIATE')
            data=json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
            if data['active']!=expected_active or candidate.parent_id!=expected_active:
                raise ValueError('Estado ativo divergente')
            lineage=Lineage(data['events'])
            lineage.append(action='rejected',genome_id=candidate.genome_id,receipt_id=receipt['receipt_id'])
            data['events']=lineage.events
            db.execute('UPDATE state SET payload=? WHERE id=1',(canonical_json(data),))
        return gate

    def rollback(self,target_id,*,expected_active,reason):
        if not reason.strip():
            raise ValueError('Reversão requer justificativa')
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('BEGIN IMMEDIATE')
            data=json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
            if data['active']!=expected_active or target_id not in data['genomes'] or target_id==expected_active:
                raise ValueError('Estado alterado ou alvo desconhecido')
            parent=data['genomes'][expected_active]['parent_id']
            ancestors=set()
            while parent:
                ancestors.add(parent); parent=data['genomes'][parent]['parent_id']
            if target_id not in ancestors:
                raise ValueError('Reversão só permite ancestral aceito')
            lineage=Lineage(data['events']);lineage.append(action='rollback',genome_id=target_id,receipt_id=__import__('hashlib').sha256(reason.encode()).hexdigest())
            data['active']=target_id;data['events']=lineage.events
            db.execute('UPDATE state SET payload=? WHERE id=1',(canonical_json(data),))
        return self.snapshot()
