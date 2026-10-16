"""Lineage-separated train/validation selection and durable once-only test use.

This boundary prevents accidental repeated scoring through this ledger. It cannot
hide local files from their owner or make synthetic tasks externally independent.
"""
from dataclasses import replace
import json
import sqlite3
from ..core.semantic_ir import fingerprint
from ..core.semantic_contracts import canonical_payload
from ._bounded import bounded_tuple
from .symbolic_beam import (Sample, SearchBudget, SymbolicModel, search,
                            validate_samples, sample_digest, score_model, _number,
                            replay_search,load_model)


def split_lineage(samples,*,seed,validation_groups=1,test_groups=1):
    """Hash-order entire lineage groups, independently of labels and input order."""
    samples=validate_samples(samples)
    if type(seed) is not int or type(validation_groups) is not int or type(test_groups) is not int or min(validation_groups,test_groups)<1:
        raise ValueError('Seed and positive group counts required')
    groups=sorted({s.group for s in samples},key=lambda group:(fingerprint({'seed':seed,'group':group}),group))
    if len(groups)<=validation_groups+test_groups:
        raise ValueError('At least one group per partition required')
    assignments={g:('test' if i<test_groups else 'validation' if i<test_groups+validation_groups else 'train') for i,g in enumerate(groups)}
    return tuple(replace(s,split=assignments[s.group]) for s in samples)


def freeze_experiment(samples,*,owner,budget,ablation_budgets=()):
    samples=validate_samples(samples)
    if type(owner) is not str or not owner.strip() or len(owner)>128 or not isinstance(budget,SearchBudget):
        raise ValueError('Owner and grammar budget required')
    ablations=bounded_tuple(ablation_budgets,8,label='ablation configurations')
    if any(not isinstance(b,SearchBudget) for b in ablations):raise ValueError('Typed ablation budgets required')
    group_partitions={}; partitions={}
    for split in ('train','validation','test'):
        rows=validate_samples([s for s in samples if s.split==split],split=split)
        partitions[split]={'ids':[s.identifier for s in rows],'content_id':sample_digest(rows)}
        for sample in rows:
            if sample.group in group_partitions and group_partitions[sample.group]!=split:
                raise ValueError('Lineage group crosses partitions')
            group_partitions[sample.group]=split
    semantic={}
    for s in samples:
        key=fingerprint([str(x) for x in s.features])
        if key in semantic and semantic[key]!=s.split:raise ValueError('Identical input crosses partitions')
        semantic[key]=s.split
    budgets=[budget.to_data(),*(b.to_data() for b in ablations)]
    if len({fingerprint(b) for b in budgets})!=len(budgets):raise ValueError('Duplicate ablation configuration')
    data={'version':'symbolic-experiment-v1','owner':owner,'partitions':partitions,
          'groups':dict(sorted(group_partitions.items())),'budget':budget.to_data(),
          'ablation_budgets':[b.to_data() for b in ablations],
          'selection_rule':'validation_mse_then_term_size_then_model_id; primary grammar only',
          'scope':'caller-supplied frozen cases; independent data authenticity not established'}
    return {**data,'experiment_id':fingerprint(data)}


def verify_experiment(experiment,samples):
    try:
        if experiment.get('version')=='sparse-symbolic-experiment-v1':
            from .sparse_symbolic import freeze_sparse_experiment,SparseBudget
            return freeze_sparse_experiment(samples,owner=experiment['owner'],grammar_budget=SearchBudget(**experiment['budget']),sparse_budget=SparseBudget(**experiment['sparse_budget']),ablation_budgets=[SearchBudget(**b) for b in experiment['ablation_budgets']])==experiment
        return freeze_experiment(samples,owner=experiment['owner'],budget=SearchBudget(**experiment['budget']),
            ablation_budgets=[SearchBudget(**b) for b in experiment['ablation_budgets']])==experiment
    except (ValueError,TypeError,KeyError):return False


def _partition(experiment,samples,split):
    rows=validate_samples(samples,split=split)
    expected=experiment['partitions'][split]
    if [s.identifier for s in rows]!=expected['ids'] or sample_digest(rows)!=expected['content_id']:
        raise ValueError('Partition differs from frozen experiment')
    if any(experiment['groups'].get(s.group)!=split for s in rows):
        raise ValueError('Lineage partition differs from experiment')
    return rows


def _validate_learning_partitions(training,validation):
    if {s.identifier for s in training}&{s.identifier for s in validation}:
        raise ValueError('Training-validation identity overlap')
    if {s.group for s in training}&{s.group for s in validation}:
        raise ValueError('Training-validation lineage overlap')
    if {s.features for s in training}&{s.features for s in validation}:
        raise ValueError('Training-validation input overlap')
    if len(training[0].features)!=len(validation[0].features):
        raise ValueError('Training-validation schema mismatch')


def _validation_selection(report,validation):
    scores=[]
    for candidate in report['candidates']:
        model=SymbolicModel.from_data(candidate['model']); result=score_model(model,validation)
        scores.append({'model_id':model.content_id,'model':model.to_data(),'validation':result,'term_size':model.term.size})
    valid=[s for s in scores if s['validation']['mse'] is not None]
    if not valid:raise ValueError('No candidate defined over validation partition')
    winner=min(valid,key=lambda r:(_number(r['validation']['mse']),r['term_size'],r['model_id']))
    return scores,winner


def train_and_select(experiment,training,validation):
    """No test inputs accepted by this entrypoint; all fitting uses train only."""
    payload={k:v for k,v in experiment.items() if k!='experiment_id'}
    if fingerprint(payload)!=experiment['experiment_id']:raise ValueError('Corrupt experiment')
    training=_partition(experiment,training,'train'); validation=_partition(experiment,validation,'validation')
    _validate_learning_partitions(training,validation)
    primary=search(training,budget=SearchBudget(**experiment['budget']))
    scores,winner=_validation_selection(primary,validation)
    ablations=[]
    for data in experiment['ablation_budgets']:
        report=search(training,budget=SearchBudget(**data))
        try:
            candidate_scores,selected=_validation_selection(report,validation)
            outcome={'selected_model_id':selected['model_id'],'validation':selected['validation']}
        except ValueError:
            outcome={'selected_model_id':None,'validation':None}
        ablations.append({'search':report,**outcome})
    data={'version':'symbolic-selection-v1','experiment_id':experiment['experiment_id'],'search':primary,
          'validation_content_id':sample_digest(validation),'candidate_scores':scores,
          'selected_model':winner['model'],'selected_model_id':winner['model_id'],
          'ablations':ablations,'test_observed':False,
          'scope':'validation selects primary grammar candidate; ablations never choose test winner'}
    return {**data,'selection_id':fingerprint(data)}


def replay_selection(selection,experiment,training,validation):
    try:
        if selection.get('version')=='sparse-selection-v1':
            from .sparse_symbolic import train_sparse_and_select
            return train_sparse_and_select(experiment,training,validation)==selection
        return train_and_select(experiment,training,validation)==selection
    except (ValueError,TypeError,KeyError):return False


class TestLedger:
    """Durable test admission serialized across connections with BEGIN IMMEDIATE.

    Reservation is committed before scoring. Interrupted runs remain consumed;
    reading a committed report is allowed, but rescoring is not. The authority
    must preserve this ledger and assign one experiment per scientific question.
    Creating another ledger is not an independent replication.
    """
    __test__=False

    def __init__(self,path,*,capacity=1000):
        if type(capacity) is not int or not 1<=capacity<=100000:
            raise ValueError('Bounded experiment ledger capacity required')
        self.capacity=capacity
        self.db=sqlite3.connect(path,timeout=10)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS tests(experiment TEXT PRIMARY KEY,selection TEXT NOT NULL,state TEXT NOT NULL,report TEXT)')
        self.db.commit()

    def close(self):self.db.close()

    def evaluate_once(self,selection,experiment,*,training,validation,test):
        # Recompute selection before reading final labels; metadata hashes alone
        # cannot establish that a claimed search or validation score is genuine.
        training=validate_samples(training,split='train');validation=validate_samples(validation,split='validation')
        if not replay_selection(selection,experiment,training,validation):
            raise ValueError('Selection replay failed')
        test=_partition(experiment,test,'test')
        if not verify_experiment(experiment,(*training,*validation,*test)):
            raise ValueError('Experiment replay failed')
        identifier=experiment['experiment_id']
        self.reserve(identifier,selection['selection_id'])
        try:
            model=load_model(selection['selected_model'])
            primary=score_model(model,test)
            ablations=[]
            for row in selection['ablations']:
                selected=row['selected_model_id']
                candidate=next((r for r in row['search']['candidates'] if r['model_id']==selected),None)
                result=score_model(load_model(candidate['model']),test) if candidate else None
                ablations.append({'search_id':row['search']['search_id'],'selected_model_id':selected,'test':result})
            data={'version':'symbolic-final-test-v1','experiment_id':identifier,'selection_id':selection['selection_id'],
                  'model_id':model.content_id,'test_content_id':sample_digest(test),'test':primary,
                  'ablations':ablations,'test_use':'once per durable experiment ledger',
                  'scope':'supplied frozen finite data; no novelty, AGI, or external benchmark claim'}
            report={**data,'report_id':fingerprint(data)}
            self.finish(identifier,report)
            return report
        except Exception:
            self.fail(identifier)
            raise

    def reserve(self,experiment_id,selection_id):
        for digest in (experiment_id,selection_id):
            if type(digest) is not str or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError('Content-addressed experiment and selection required')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            if self.db.execute('SELECT 1 FROM tests WHERE experiment=?',(experiment_id,)).fetchone():
                raise PermissionError('Final test already consumed')
            if self.db.execute('SELECT COUNT(*) FROM tests').fetchone()[0]>=self.capacity:
                raise PermissionError('Ledger capacity exhausted')
            self.db.execute("INSERT INTO tests VALUES(?,?,'reserved',NULL)",(experiment_id,selection_id))

    def finish(self,experiment_id,report):
        # Completion binds bookkeeping to the reservation; mathematical replay
        # remains the responsibility of the report-specific independent checker.
        schemas={
            'symbolic-final-test-v1':({'version','experiment_id','selection_id','model_id','test_content_id','test','ablations','test_use','scope','report_id'},'experiment_id'),
            'forge-symbolic-final-v1':({'version','campaign_id','selection_id','model_id','test','priors','ablations','test_use','scope','report_id'},'campaign_id')}
        if type(report) is not dict or type(report.get('version')) is not str or report['version'] not in schemas:
            raise ValueError('Known final-test report schema required')
        fields,identity=schemas[report['version']]
        if set(report)!=fields or report[identity]!=experiment_id:
            raise ValueError('Report does not match reserved experiment')
        if report['report_id']!=fingerprint({k:v for k,v in report.items() if k!='report_id'}):
            raise ValueError('Final report integrity mismatch')
        encoded=canonical_payload(report)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row=self.db.execute('SELECT selection,state FROM tests WHERE experiment=?',(experiment_id,)).fetchone()
            if row is None or row[1]!='reserved':raise PermissionError('Only a reserved test can be completed')
            if row[0]!=report['selection_id']:raise ValueError('Report selection differs from reservation')
            self.db.execute("UPDATE tests SET state='completed',report=? WHERE experiment=?",(encoded,experiment_id))

    def fail(self,experiment_id):
        with self.db:
            changed=self.db.execute("UPDATE tests SET state='failed' WHERE experiment=? AND state='reserved'",(experiment_id,)).rowcount
            if changed!=1:raise PermissionError('Only a reserved test can fail')

    def get(self,experiment_id):
        row=self.db.execute('SELECT selection,state,report FROM tests WHERE experiment=?',(experiment_id,)).fetchone()
        if row is None:raise KeyError(experiment_id)
        return {'selection_id':row[0],'state':row[1],'report':json.loads(row[2]) if row[2] else None}


def verify_final_report(report,selection,experiment,*,training,validation,test):
    """Pure replay of an existing report; never authorizes another test selection."""
    try:
        if not replay_selection(selection,experiment,training,validation):return False
        test=_partition(experiment,test,'test')
        if not verify_experiment(experiment,(*training,*validation,*test)):return False
        model=load_model(selection['selected_model'])
        if report['experiment_id']!=experiment['experiment_id'] or report['selection_id']!=selection['selection_id'] or report['model_id']!=model.content_id:
            return False
        if report['test_content_id']!=sample_digest(test) or report['test']!=score_model(model,test):return False
        expected=[]
        for row in selection['ablations']:
            candidate=next((r for r in row['search']['candidates'] if r['model_id']==row['selected_model_id']),None)
            expected.append({'search_id':row['search']['search_id'],'selected_model_id':row['selected_model_id'],
                             'test':score_model(load_model(candidate['model']),test) if candidate else None})
        return report['ablations']==expected and fingerprint({k:v for k,v in report.items() if k!='report_id'})==report['report_id']
    except (ValueError,TypeError,KeyError):return False
