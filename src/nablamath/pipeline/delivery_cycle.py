"""Integrated local dataset, exact algebra, learning and conservation rehearsal.

A fixed protocol is written before training or grading. Every final-test outcome
is retained, and no predictor is fitted on validation/test labels. Declared
reviewer labels are local engineering fixtures. This is not external scientific
acceptance, a private benchmark, an empirical experiment or a remote publication.
"""
from __future__ import annotations

import hashlib
from contextlib import closing
import math
import sqlite3
from pathlib import Path

from ..core.semantic_contracts import canonical_payload,load_json,require_digest,require_fields
from ..core.semantic_ir import fingerprint
from ..datasets.schema import make_record,ScientificRecord
from ..datasets.revision_store import DatasetLedger
from ..datasets.revision_release import verify_release
from ..datasets.revision_quality import (RevisionQualityPolicy,ReleaseReview,assess_revision,
    release_reviewed_revision,verify_assessment)
from ..forge.reverse_builder import generate_task
from ..forge.solvers import solve_task
from ..forge.task_spec import TaskSpec
from ..math.polynomials.univariate import Polynomial
from ..math.polynomials.real_roots import isolate_real_roots,verify_root_isolation
from ..training.symbolic_beam import SearchBudget
from ..training.symbolic_protocol import TestLedger
from ..training.forge_symbolic import (freeze_campaign,select_campaign,evaluate_campaign_once,
                                      replay_campaign_report)
from ..physics.fluids.shallow_water_2d import WaterGrid,WaterField,WaterState,simulate_water
from ..evaluation.clustered import PairedMeasurement,paired_randomization,domain_summary

VERSION='integrated-delivery-cycle-v1'
FILES=('protocol.json','training.json','campaign.json','selection.json','learning.json',
       'assessment.json','release-receipt.json','roots.json','water.json','statistics.json','summary.json')
SCOPE='finite local engineering rehearsal; no external science, private holdout, original48 improvement or empirical validation'


def _save(path,data):
    with Path(path).open('x',encoding='utf-8') as stream:
        stream.write(canonical_payload(data)+'\n')


def _read(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Regular cycle artifact required')
    with path.open('rb') as stream:
        raw=stream.read(1_000_001)
    if len(raw)>1_000_000:
        raise ValueError('Cycle artifact byte budget exceeded')
    return load_json(raw.decode('utf-8'))


def _protocol(seed,train_count,validation_count,test_count):
    for value,name,limit in [(seed,'seed',2**31-10000),(train_count,'training count',16),
                             (validation_count,'validation count',8),(test_count,'test count',24)]:
        minimum=0 if name=='seed' else 2
        if type(value) is not int or not minimum<=value<=limit:
            raise ValueError('Invalid '+name)
    return {'version':VERSION,'seed':seed,'train_count':train_count,
            'validation_count':validation_count,'test_count':test_count,
            'train_size':3,'validation_size':4,'test_size':5,
            'validation_seed_offset':1000,'test_seed_offset':2000,
            'budget':SearchBudget(depth=3,beam_width=12,max_evaluations=200,
                                 operations=('multiply','reciprocal')).to_data(),
            'ablation_depth':1,'stopping_rule':'one fixed campaign, retain all outcomes, no score-selected retries',
            'scope':SCOPE,'role_labels_are_local_fixtures':True}


def _tasks(protocol,split):
    offset={'train':0,'validation':protocol['validation_seed_offset'],'test':protocol['test_seed_offset']}[split]
    return tuple(generate_task('polynomial_integral',protocol['seed']+offset+i,
                               protocol[split+'_size']).task for i in range(protocol[split+'_count']))


def _water():
    grid=WaterGrid(4,4,boundary_x='periodic',boundary_y='periodic')
    initial=WaterField.sample(grid,lambda x,y:WaterState.primitive(
        1+.01*math.cos(2*math.pi*x)*math.cos(2*math.pi*y)))
    return simulate_water(initial,.01,max_steps=100).to_data()


def _statistics(protocol,learning):
    primary=learning['test']['results']
    alternative=learning['ablations'][0]['test']['results']
    other={row['task_id']:row['valid'] for row in alternative}
    measurements=[PairedMeasurement(row['task_id'],row['task_id'],'synthetic-polynomial-integral',
                     0 if row['valid'] else 1,0 if other[row['task_id']] else 1) for row in primary]
    mode='exact' if len(measurements)<=16 else 'monte_carlo'
    return {'domains':domain_summary(measurements),
            'paired_randomization':paired_randomization(measurements,mode=mode,repetitions=128,seed=protocol['seed']),
            'scope':'task clusters and grammar priors are declared; exchangeability/external novelty unvalidated'}


def run_delivery_cycle(destination,*,seed=981023,train_count=6,validation_count=3,test_count=4):
    protocol=_protocol(seed,train_count,validation_count,test_count)
    root=Path(destination)
    root.mkdir(parents=True,exist_ok=False)
    _save(root/'protocol.json',protocol)
    records=tuple(make_record(task,solve_task(task),license_id='MIT',provenance='synthetic local delivery protocol',
                 scope='exact polynomial integral',limitations='not observed data; strong grammar priors',split='train')
                  for task in _tasks(protocol,'train'))
    _save(root/'training.json',[row.to_data() for row in records])
    ledger=DatasetLedger(root/'datasets.sqlite3',dataset='delivery-integrals-v1')
    first=ledger.commit(expected_head=None,actor='local fixture curator',reason='initial fixed training batch',add=records[:2])
    final=first if len(records)==2 else ledger.commit(expected_head=first.content_id,actor='local fixture curator',
                           reason='remaining predeclared training records',add=records[2:])
    policy=RevisionQualityPolicy(('MIT',),required_splits=('train',),minimum_records=2,minimum_families=1)
    assessment=assess_revision(ledger,expected_head=final.content_id,policy=policy)
    _save(root/'assessment.json',assessment)
    review=ReleaseReview(final.content_id,assessment['assessment_id'],'local scripted review fixture',True,
                         'Engineering fixture; no authenticated human review claimed')
    release=release_reviewed_revision(ledger,root/'training-release',expected_head=final.content_id,
                                     assessment=assessment,review=review,policy=policy)
    _save(root/'release-receipt.json',release)
    budget=SearchBudget(**protocol['budget'])
    ablation=SearchBudget(**{**protocol['budget'],'depth':1})
    validation,test=_tasks(protocol,'validation'),_tasks(protocol,'test')
    campaign=freeze_campaign(records,validation,test,owner='local fixture operator',budget=budget,
                              ablation_budgets=(ablation,))
    _save(root/'campaign.json',campaign)
    selection=select_campaign(campaign,records,validation)
    _save(root/'selection.json',selection)
    test_ledger=TestLedger(root/'test-ledger.sqlite3')
    try:
        learning=evaluate_campaign_once(test_ledger,campaign,selection,records=records,
                                        validation_tasks=validation,test_tasks=test)
    finally:
        test_ledger.close()
    _save(root/'learning.json',learning)
    roots=isolate_real_roots(Polynomial((-2,0,1)),precision_bits=16).to_data()
    _save(root/'roots.json',roots)
    water=_water()
    _save(root/'water.json',water)
    statistics=_statistics(protocol,learning)
    _save(root/'statistics.json',statistics)
    summary={'version':VERSION,'protocol_id':fingerprint(protocol),'revision_id':final.content_id,
             'dataset_release_id':release['manifest']['release_id'],'campaign_id':campaign['campaign_id'],
             'primary_correct':learning['test']['passed'],'ablation_correct':learning['ablations'][0]['test']['passed'],
             'test_tasks':len(test),'root_certificate_verified':verify_root_isolation(roots),
             'water_max_conservation_residual':max(abs(x) for x in water['conservation_residual']),
             'original_reserved48_used':False,'fully_calibrated_and_ready':False,'scope':SCOPE}
    _save(root/'summary.json',summary)
    files={path.relative_to(root).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
           for path in sorted(root.rglob('*')) if path.is_file()}
    manifest={'version':VERSION,'files':files,'scope':SCOPE}
    manifest={**manifest,'run_id':fingerprint(manifest)}
    _save(root/'manifest.json',manifest)
    if not verify_delivery_cycle(root,expected_run_id=manifest['run_id']):
        raise ValueError('Integrated delivery cycle failed independent replay')
    return {**summary,'run_id':manifest['run_id']}


def verify_delivery_cycle(directory,*,expected_run_id):
    """Require a caller-pinned run ID; hashes alone do not authenticate its issuer."""
    try:
        require_digest(expected_run_id)
        root=Path(directory)
        if root.is_symlink() or not root.is_dir():
            return False
        manifest=_read(root/'manifest.json')
        require_fields(manifest,{'version','files','scope','run_id'})
        if (manifest['version']!=VERSION or manifest['scope']!=SCOPE or manifest['run_id']!=expected_run_id
            or fingerprint({k:v for k,v in manifest.items() if k!='run_id'})!=expected_run_id):
            return False
        expected_files=set(FILES)|{'datasets.sqlite3','test-ledger.sqlite3',
                                  'training-release/content/manifest.json','training-release/content/records.jsonl'}
        if set(manifest['files'])!=expected_files:
            return False
        actual=set()
        for path in root.rglob('*'):
            if path.is_symlink():
                return False
            if path.is_file() and path!=root/'manifest.json':
                actual.add(path.relative_to(root).as_posix())
        if actual!=expected_files:
            return False
        for name,digest in manifest['files'].items():
            require_digest(digest)
            path=root/name
            maximum=64*1024*1024 if name.endswith('.sqlite3') else 1_000_000
            if path.stat().st_size>maximum or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                return False
        protocol=_read(root/'protocol.json')
        if protocol!=_protocol(protocol['seed'],protocol['train_count'],protocol['validation_count'],protocol['test_count']):
            return False
        records=tuple(ScientificRecord.from_data(row) for row in _read(root/'training.json'))
        expected_tasks=_tasks(protocol,'train')
        if sorted(r.task.content_id for r in records)!=sorted(t.content_id for t in expected_tasks):
            return False
        assessment=_read(root/'assessment.json')
        revision_id=assessment['revision_id']
        ledger=DatasetLedger.open_read_only(root/'datasets.sqlite3',dataset='delivery-integrals-v1')
        _,stored=ledger.checkout(expected_head=revision_id)
        if {r.content_id for r in records}!={r.content_id for r in stored}:
            return False
        policy=RevisionQualityPolicy(('MIT',),required_splits=('train',),minimum_records=2,minimum_families=1)
        if not verify_assessment(assessment,ledger,expected_head=revision_id,policy=policy):
            return False
        release=_read(root/'release-receipt.json')
        require_fields(release,{'manifest','assessment','review','scope','receipt_id'})
        if (release['scope']!='local reviewed data-only release; no remote publication or authenticated human review'
            or release['assessment']!=assessment or release['review']['accepted'] is not True
            or release['review']['review_identity_authenticated'] is not False
            or release['review']['revision_id']!=revision_id
            or release['review']['assessment_id']!=assessment['assessment_id']):
            return False
        if verify_release(root/'training-release',expected_revision=revision_id,
                          expected_release=release['manifest']['release_id'])!=release['manifest']:
            return False
        if fingerprint({k:v for k,v in release.items() if k!='receipt_id'})!=release['receipt_id']:
            return False
        campaign,selection,learning=(_read(root/name) for name in ('campaign.json','selection.json','learning.json'))
        expected_campaign=freeze_campaign(records,_tasks(protocol,'validation'),_tasks(protocol,'test'),
            owner='local fixture operator',budget=SearchBudget(**protocol['budget']),
            ablation_budgets=(SearchBudget(**{**protocol['budget'],'depth':1}),))
        if campaign!=expected_campaign:
            return False
        if not replay_campaign_report(learning,campaign,selection,records=records,
                     validation_tasks=_tasks(protocol,'validation'),test_tasks=_tasks(protocol,'test')):
            return False
        with closing(sqlite3.connect((root/'test-ledger.sqlite3').resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
            tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'tests' not in tables:
                return False
            saved=db.execute('SELECT selection,state,substr(report,1,1000001) FROM tests WHERE experiment=?',
                             (campaign['campaign_id'],)).fetchone()
            if (saved is None or saved[0]!=selection['selection_id'] or saved[1]!='completed'
                or load_json(saved[2])!=learning):
                return False
        roots=_read(root/'roots.json')
        if (roots!=isolate_real_roots(Polynomial((-2,0,1)),precision_bits=16).to_data()
            or not verify_root_isolation(roots) or _read(root/'water.json')!=_water()):
            return False
        if _read(root/'statistics.json')!=_statistics(protocol,learning):
            return False
        summary=_read(root/'summary.json')
        expected={'version':VERSION,'protocol_id':fingerprint(protocol),'revision_id':revision_id,
             'dataset_release_id':release['manifest']['release_id'],'campaign_id':campaign['campaign_id'],
             'primary_correct':learning['test']['passed'],'ablation_correct':learning['ablations'][0]['test']['passed'],
             'test_tasks':protocol['test_count'],'root_certificate_verified':True,
             'water_max_conservation_residual':max(abs(x) for x in _water()['conservation_residual']),
             'original_reserved48_used':False,'fully_calibrated_and_ready':False,'scope':SCOPE}
        return summary==expected
    except (ValueError,TypeError,KeyError,ArithmeticError,OSError,sqlite3.Error,RecursionError):
        return False
