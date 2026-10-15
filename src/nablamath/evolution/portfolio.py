"""Controlled evolution of exact solver strategies across Forge task families.

Selection uses calibration only. Each reserved semantic holdout is consumed before
measurement, including failed attempts. The evaluator and policies are local
trusted code; this is not hostile-code isolation or unrestricted self-improvement.
"""
from dataclasses import dataclass
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from ..core.semantic_ir import canonical_json,fingerprint
from ..forge.task_spec import FAMILIES,TaskSpec
from ..forge.deduplicate import semantic_fingerprint
from ..forge.difficulty import measure
from .statistical_tests import paired_sign_test,practical_effect


@dataclass(frozen=True)
class PortfolioPolicy:
    strategies: tuple[tuple[str,str],...]

    def __post_init__(self):
        rows=tuple(sorted(tuple(row) for row in self.strategies))
        if not rows or len({f for f,_ in rows})!=len(rows) or any(f not in FAMILIES or s not in ('exact','alternate') for f,s in rows):
            raise ValueError('Estratégias tipadas por família obrigatórias')
        object.__setattr__(self,'strategies',rows)

    @property
    def policy_id(self):return fingerprint(self.to_data())

    def to_data(self):return {'schema_version':1,'strategies':[list(row) for row in self.strategies]}

    def strategy(self,family):
        if family not in dict(self.strategies):raise ValueError('Família fora da política')
        return dict(self.strategies)[family]


def contract_digest():
    root=Path(__file__).resolve().parents[1]
    files=('evolution/portfolio.py','forge/difficulty.py','forge/solvers.py','verify/trace.py','evolution/statistical_tests.py')
    return fingerprint({p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in files})


def select_portfolio(calibration,*,budget=100000):
    calibration=tuple(calibration)
    if not 1<=len(calibration)<=64 or len({semantic_fingerprint(t) for t in calibration})!=len(calibration):
        raise ValueError('Calibração única limitada obrigatória')
    rows=[];selected=[]
    for family in sorted({t.family for t in calibration}):
        options=[]
        for strategy in ('exact','alternate'):
            measured=[measure(t,strategy,budget) for t in calibration if t.family==family]
            rows.extend(measured)
            if all(r['status']=='completed' and r['verification']['valid'] for r in measured):
                options.append((sum(r['executed_python_lines'] for r in measured),strategy))
        if not options:raise ValueError('Nenhuma estratégia correta dentro do orçamento')
        selected.append((family,min(options)[1]))
    return PortfolioPolicy(tuple(selected)),rows


class PortfolioCampaign:
    def __init__(self,path,baseline,*,alpha=.05,max_generations=8,minimum_effect=.05,budget=100000):
        if (not 0<alpha<1 or type(max_generations) is not int or not 1<=max_generations<=32
                or not 0<=minimum_effect<=1 or type(budget) is not int or not 1<=budget<=2000000):
            raise ValueError('Contrato de campanha inválido')
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        contract={'evaluator':contract_digest(),'alpha':alpha,'max_generations':max_generations,
                       'minimum_effect':minimum_effect,'budget':budget,'baseline':baseline.to_data()}
        self._contract_json=canonical_json(contract)
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS reserved (semantic TEXT PRIMARY KEY)')
            db.execute('CREATE TABLE IF NOT EXISTS evaluations (generation INTEGER PRIMARY KEY, receipt TEXT)')
            db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)',('contract',canonical_json(self.contract)))
            db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)',('active',canonical_json(baseline.to_data())))
            if db.execute('SELECT value FROM metadata WHERE key=?',('contract',)).fetchone()[0]!=canonical_json(self.contract):
                raise ValueError('Contrato persistido divergente')

    @property
    def contract(self):
        return json.loads(self._contract_json)

    def active(self):
        with closing(sqlite3.connect(self.path)) as db:
            data=json.loads(db.execute('SELECT value FROM metadata WHERE key=?',('active',)).fetchone()[0])
        return PortfolioPolicy(tuple(tuple(row) for row in data['strategies']))

    def evaluate(self,candidate,calibration,holdout):
        calibration,holdout=tuple(calibration),tuple(holdout)
        if contract_digest()!=self.contract['evaluator']:raise ValueError('Avaliador alterado')
        train={semantic_fingerprint(t) for t in calibration};test=[semantic_fingerprint(t) for t in holdout]
        if (not 1<=len(calibration)<=64 or not 5<=len(holdout)<=64 or len(set(test))!=len(test) or train&set(test)
                or {t.family for t in holdout}!={f for f,_ in candidate.strategies}):
            raise ValueError('Holdout deve ser novo e cobrir todas as famílias da política')
        baseline=self.active()
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('BEGIN IMMEDIATE')
            generation=db.execute('SELECT COUNT(*) FROM evaluations').fetchone()[0]+1
            if generation>self.contract['max_generations']:raise ValueError('Gerações esgotadas')
            try:db.executemany('INSERT INTO reserved VALUES (?)',((key,) for key in test))
            except sqlite3.IntegrityError as exc:raise ValueError('Holdout já usado nesta campanha') from exc
            db.execute('INSERT INTO evaluations VALUES (?,NULL)',(generation,))
        measurements=[]
        for task in holdout:
            a=measure(task,candidate.strategy(task.family),self.contract['budget'])
            b=measure(task,baseline.strategy(task.family),self.contract['budget'])
            measurements.append({'task':task.to_data(),'candidate':a,'baseline':b})
        valid=all(r[k]['status']=='completed' and r[k]['verification']['valid'] for r in measurements for k in ('candidate','baseline'))
        a=[r['candidate']['executed_python_lines'] for r in measurements];b=[r['baseline']['executed_python_lines'] for r in measurements]
        statistics=paired_sign_test(a,b,alpha=self.contract['alpha']/self.contract['max_generations'])
        effect=practical_effect(a,b,minimum_relative_reduction=self.contract['minimum_effect'])
        accepted=valid and statistics['significant'] and statistics['regressions']==0 and effect['passed']
        payload={'schema_version':1,'generation':generation,'contract':self.contract,'candidate':candidate.to_data(),
                 'baseline':baseline.to_data(),'measurements':measurements,'statistics':statistics,'effect':effect,
                 'accepted':accepted,'calibration_ids':sorted(train),
                 'scope':'exact/alternate solver strategies, measured local Python work; no broad algorithm synthesis'}
        receipt={**payload,'receipt_id':fingerprint(payload)}
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('UPDATE evaluations SET receipt=? WHERE generation=?',(canonical_json(receipt),generation))
        return receipt

    def promote(self,receipt):
        if contract_digest()!=self.contract['evaluator']:raise ValueError('Avaliador alterado')
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('BEGIN IMMEDIATE')
            issued=db.execute('SELECT receipt FROM evaluations WHERE generation=?',(receipt['generation'],)).fetchone()
            active=db.execute('SELECT value FROM metadata WHERE key=?',('active',)).fetchone()[0]
            if not issued or issued[0]!=canonical_json(receipt) or not receipt['accepted'] or active!=canonical_json(receipt['baseline']):
                raise ValueError('Recibo não autorizado, rejeitado ou baseline desatualizado')
            db.execute('UPDATE metadata SET value=? WHERE key=?',(canonical_json(receipt['candidate']),'active'))
        return self.active()

    def rollback(self,policy_id,*,reason):
        """Restore a previously accepted version and keep a chained operator event."""
        if not isinstance(reason,str) or not reason.strip():raise ValueError('Motivo de reversão obrigatório')
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('BEGIN IMMEDIATE')
            versions={fingerprint(self.contract['baseline']):self.contract['baseline']}
            for (raw,) in db.execute('SELECT receipt FROM evaluations WHERE receipt IS NOT NULL ORDER BY generation'):
                receipt=json.loads(raw)
                if receipt['accepted']:versions[fingerprint(receipt['candidate'])]=receipt['candidate']
            if policy_id not in versions:raise ValueError('Política não pertence às versões aceitas desta campanha')
            old=db.execute('SELECT value FROM metadata WHERE key=?',('active',)).fetchone()[0]
            if old==canonical_json(versions[policy_id]):raise ValueError('Política já ativa')
            previous=db.execute('SELECT value FROM metadata WHERE key=?',('rollback_events',)).fetchone()
            events=json.loads(previous[0]) if previous else []
            event={'from':fingerprint(json.loads(old)),'to':policy_id,'reason':reason,
                   'previous':events[-1]['event_id'] if events else None}
            events.append({**event,'event_id':fingerprint(event)})
            db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('rollback_events',canonical_json(events)))
            db.execute('UPDATE metadata SET value=? WHERE key=?',(canonical_json(versions[policy_id]),'active'))
        return events[-1]
