"""Learn an integral component rule from Forge train traces, grade fresh tasks.

This study deliberately declares strong priors: coefficientwise prediction,
explicit exponent-plus-one input, exact rational arithmetic, reciprocal/product
feature grammar and zero integration constant. The coefficient rule is fitted,
not programmed into predict. It is not cross-family generalization, an LLM,
or evidence that a learned model discovered integration without domain priors.
"""
from fractions import Fraction
import json
from ..core.semantic_ir import fingerprint,canonical_json,rational
from ..forge.task_spec import TaskSpec
from ..datasets.schema import ScientificRecord
from ..verify.trace import verify_candidate,VERIFIER_VERSION
from ._bounded import bounded_tuple
from .symbolic_beam import (Sample,Term,SearchBudget,SymbolicModel,search,
                           replay_search,score_model,_number)
from .symbolic_protocol import TestLedger

PRIORS={'family':'polynomial_integral','input_features':['coefficient','exponent_plus_one'],
        'output_assembly':'zero integration constant followed by predicted components',
        'numeric_domain':'exact rationals','grammar':'closed bounded symbolic grammar',
        'claim_scope':'fresh synthetic task holdout within one family; no original reserved benchmark used'}

_PRIOR_JSON=canonical_json(PRIORS)

def _priors():return json.loads(_PRIOR_JSON)

def _tasks(tasks):
    tasks=bounded_tuple(tasks,128,label='Forge tasks')
    if not tasks or any(not isinstance(t,TaskSpec) or t.family!='polynomial_integral' for t in tasks):
        raise ValueError('Bounded polynomial integral tasks required')
    if len({t.content_id for t in tasks})!=len(tasks):raise ValueError('Duplicate Forge task')
    return tuple(sorted(tasks,key=lambda t:t.content_id))


def component_inputs(task):
    if not isinstance(task,TaskSpec) or task.family!='polynomial_integral':raise ValueError('Polynomial integral task required')
    return tuple((rational(c),Fraction(index+1)) for index,c in enumerate(task.problem['coefficients']))


def _lineage(lineage):
    if lineage is None:return {}
    if type(lineage) is not dict or len(lineage)>384:raise ValueError('Bounded lineage mapping required')
    if any(type(k) is not str or type(v) is not str or not v.strip() or len(v)>128 for k,v in lineage.items()):raise ValueError('Declared lineage mapping required')
    return dict(lineage)

def training_components(records,*,lineage=None):
    records=bounded_tuple(records,128,label='Forge training records')
    if not records or any(not isinstance(r,ScientificRecord) for r in records):raise ValueError('Verified scientific training records required')
    task_ids=[r.task.content_id for r in records]
    if len(set(task_ids))!=len(task_ids):raise ValueError('Duplicate training task')
    lineage=_lineage(lineage)
    if set(lineage)-set(task_ids):raise ValueError('Unknown training lineage task')
    rows=[]
    for record in records:
        data=record.to_data()
        if data['split']!='train':raise ValueError('Labels may only come from train traces')
        task=record.task; inputs=component_inputs(task)
        candidate=data['trace']['candidate']
        if not verify_candidate(task,candidate).valid:raise ValueError('Training trace failed independent verification')
        labels=candidate['coefficients']
        if len(labels)!=len(inputs)+1:raise ValueError('Integral trace component shape mismatch')
        group=lineage.get(task.content_id,task.content_id)
        for index,features in enumerate(inputs):
            rows.append(Sample(task.content_id+':'+str(index),group,features,rational(labels[index+1]),'train'))
    # The common learner's sample cap applies to expanded component records.
    if len(rows)>512:raise ValueError('Expanded training component budget exceeded')
    return tuple(sorted(rows,key=lambda r:r.identifier))


class IntegralComponentPredictor:
    def __init__(self,model):
        if not isinstance(model,SymbolicModel):raise ValueError('Fitted closed symbolic model required')
        self.model=model

    @property
    def content_id(self):return fingerprint({'model_id':self.model.content_id,'priors':_priors()})

    def predict(self,task):
        # No trace, witness, solver, integration routine or verifier is consulted.
        return {'coefficients':['0',*(str(self.model.predict(features)) for features in component_inputs(task))]}


def grade_tasks(model,tasks):
    tasks=_tasks(tasks);predictor=IntegralComponentPredictor(model);rows=[]
    for task in tasks:
        try:
            candidate=predictor.predict(task);error=None
        except ValueError as exc:
            candidate=None;error=str(exc)
        receipt=verify_candidate(task,candidate).to_data()
        rows.append({'task_id':task.content_id,'candidate':candidate,'verification':receipt,'valid':receipt['valid'],'error':error})
    return {'predictor_id':predictor.content_id,'passed':sum(r['valid'] for r in rows),'total':len(rows),
            'results':rows,'verifier_version':VERIFIER_VERSION}


def freeze_campaign(records,validation_tasks,test_tasks,*,owner,budget,lineage=None,ablation_budgets=()):
    records=bounded_tuple(records,128,label='Forge training records')
    lineage=_lineage(lineage)
    ablation_budgets=bounded_tuple(ablation_budgets,4,label='campaign ablations')
    if any(not isinstance(b,SearchBudget) for b in ablation_budgets):raise ValueError('Typed ablation budgets required')
    components=training_components(records,lineage={k:v for k,v in lineage.items() if k in {r.task.content_id for r in records}})
    validation_tasks=_tasks(validation_tasks);test_tasks=_tasks(test_tasks)
    if type(owner) is not str or not owner.strip() or not isinstance(budget,SearchBudget):raise ValueError('Owner and grammar budget required')
    groups={'train':{r.task.content_id for r in records},'validation':{t.content_id for t in validation_tasks},'test':{t.content_id for t in test_tasks}}
    if any(groups[a]&groups[b] for a,b in (('train','validation'),('train','test'),('validation','test'))):raise ValueError('Task leakage between campaign partitions')
    # Exact problem identities deduplicate tasks; source lineage declarations
    # additionally prevent splitting alternate records of the same source group.
    lineage=_lineage(lineage)
    if any(type(k) is not str or type(v) is not str or not v.strip() for k,v in lineage.items()):raise ValueError('Declared lineage mapping required')
    if set(lineage)-set().union(*groups.values()):raise ValueError('Unknown campaign lineage task')
    group_ids={split:{lineage.get(task,task) for task in ids} for split,ids in groups.items()}
    if any(group_ids[a]&group_ids[b] for a,b in (('train','validation'),('train','test'),('validation','test'))):raise ValueError('Lineage leakage between campaign partitions')
    train_inputs={point for r in records for point in component_inputs(r.task)}
    overlap={split:sum(point in train_inputs for task in tasks for point in component_inputs(task))
             for split,tasks in [('validation',validation_tasks),('test',test_tasks)]}
    data={'version':'forge-symbolic-campaign-v1','owner':owner,'budget':budget.to_data(),'priors':_priors(),
          'component_input_overlap_with_train':overlap,'train_record_ids':sorted(r.content_id for r in records),'task_ids':{k:sorted(v) for k,v in groups.items()},
          'ablation_budgets':[b.to_data() for b in ablation_budgets],'training_components_id':fingerprint([r.to_data() for r in components]),'lineage':dict(sorted(lineage.items())),
          'selection_rule':'validation_verified_tasks_desc_then_training_mse_then_term_size_then_model_id'}
    return {**data,'campaign_id':fingerprint(data)}


def select_campaign(campaign,records,validation_tasks):
    records=bounded_tuple(records,128,label='Forge training records');validation_tasks=_tasks(validation_tasks)
    if fingerprint({k:v for k,v in campaign.items() if k!='campaign_id'})!=campaign['campaign_id'] or campaign['priors']!=_priors():
        raise ValueError('Corrupt campaign')
    if sorted(r.content_id for r in records)!=campaign['train_record_ids'] or [t.content_id for t in validation_tasks]!=campaign['task_ids']['validation']:
        raise ValueError('Campaign partition changed')
    components=training_components(records,lineage={k:v for k,v in campaign['lineage'].items() if k in campaign['task_ids']['train']})
    if fingerprint([r.to_data() for r in components])!=campaign['training_components_id']:raise ValueError('Training labels changed')
    def select(budget):
        report=search(components,budget=SearchBudget(**budget));scores=[]
        for row in report['candidates']:
            model=SymbolicModel.from_data(row['model']);grade=grade_tasks(model,validation_tasks)
            scores.append({'model_id':model.content_id,'validation':grade,'training_mse':row['training_mse'],'size':model.term.size})
        if not scores:raise ValueError('No fitted campaign model')
        winner=min(scores,key=lambda r:(-r['validation']['passed'],_number(r['training_mse']),r['size'],r['model_id']))
        model=next(r['model'] for r in report['candidates'] if r['model_id']==winner['model_id'])
        return report,scores,model
    report,scores,model=select(campaign['budget'])
    ablations=[]
    for budget in campaign['ablation_budgets']:
        ablation,scores_ablation,model_ablation=select(budget)
        ablations.append({'search':ablation,'selected_model':model_ablation,
                          'selected_model_id':SymbolicModel.from_data(model_ablation).content_id,
                          'validation_scores':scores_ablation})
    data={'version':'forge-symbolic-selection-v1','campaign_id':campaign['campaign_id'],'search':report,
          'validation_scores':scores,'selected_model':model,'selected_model_id':SymbolicModel.from_data(model).content_id,
          'ablations':ablations,'test_observed':False}
    return {**data,'selection_id':fingerprint(data)}


def evaluate_campaign_once(ledger,campaign,selection,*,records,validation_tasks,test_tasks):
    if not isinstance(ledger,TestLedger):raise ValueError('Durable TestLedger required')
    records=bounded_tuple(records,128,label='Forge training records');validation_tasks=_tasks(validation_tasks);test_tasks=_tasks(test_tasks)
    frozen=freeze_campaign(records,validation_tasks,test_tasks,owner=campaign['owner'],budget=SearchBudget(**campaign['budget']),lineage=campaign['lineage'],ablation_budgets=[SearchBudget(**b) for b in campaign['ablation_budgets']])
    if frozen!=campaign or select_campaign(campaign,records,validation_tasks)!=selection:raise ValueError('Campaign or selection replay failed')
    ledger.reserve(campaign['campaign_id'],selection['selection_id'])
    try:
        model=SymbolicModel.from_data(selection['selected_model']);grade=grade_tasks(model,test_tasks)
        data={'version':'forge-symbolic-final-v1','campaign_id':campaign['campaign_id'],'selection_id':selection['selection_id'],
              'model_id':model.content_id,'test':grade,'priors':_priors(),
              'ablations':[{'model_id':r['selected_model_id'],'test':grade_tasks(SymbolicModel.from_data(r['selected_model']),test_tasks)} for r in selection['ablations']],'test_use':'once per campaign ledger',
              'scope':'fresh within-family synthetic tasks; no cross-family claim; original reserved48 untouched'}
        report={**data,'report_id':fingerprint(data)};ledger.finish(campaign['campaign_id'],report)
        return report
    except Exception:
        ledger.fail(campaign['campaign_id']);raise


def replay_campaign_report(report,campaign,selection,*,records,validation_tasks,test_tasks):
    """Regrade published model predictions without granting another test selection."""
    try:
        records=bounded_tuple(records,128,label='Forge training records');validation_tasks=_tasks(validation_tasks);test_tasks=_tasks(test_tasks)
        frozen=freeze_campaign(records,validation_tasks,test_tasks,owner=campaign['owner'],budget=SearchBudget(**campaign['budget']),lineage=campaign['lineage'],
                               ablation_budgets=[SearchBudget(**b) for b in campaign['ablation_budgets']])
        if frozen!=campaign or select_campaign(campaign,records,validation_tasks)!=selection:return False
        model=SymbolicModel.from_data(selection['selected_model'])
        expected={'version':'forge-symbolic-final-v1','campaign_id':campaign['campaign_id'],'selection_id':selection['selection_id'],
                  'model_id':model.content_id,'test':grade_tasks(model,test_tasks),'priors':_priors(),
                  'ablations':[{'model_id':r['selected_model_id'],'test':grade_tasks(SymbolicModel.from_data(r['selected_model']),test_tasks)} for r in selection['ablations']],
                  'test_use':'once per campaign ledger',
                  'scope':'fresh within-family synthetic tasks; no cross-family claim; original reserved48 untouched'}
        return report=={**expected,'report_id':fingerprint(expected)}
    except (ValueError,TypeError,KeyError):return False
