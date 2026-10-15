"""Synthetic transfer checks exercise protocol; they are not external benchmark wins."""
import dataclasses
import pytest
from nablamath.training.reasoning_finetune import ReasoningProtocol, fit_reasoning, freeze_protocol
from nablamath.training.cross_domain_eval import TransferCase, evaluate_transfer
from nablamath.singularity.evaluation.generalization import assess_generalization
from nablamath.core.semantic_ir import fingerprint


def study():
    rows=[{'id':str(i),'features':[i/10],'target':2*i/10+1,'split':'train'} for i in range(-10,11)]
    model=fit_reasoning(rows,freeze_protocol(rows,owner='owner',epochs=1000,learning_rate=.1,l2=0))
    train=[TransferCase(r['id'],'linear_training','synthetic',tuple(r['features']),r['target'],'train-'+r['id']) for r in rows]
    test=[TransferCase('holdout-'+str(i),'linear_transfer','synthetic-transfer',(i/7,),2*i/7+1,'held-'+str(i)) for i in range(20,40)]
    return model,train,test


def test_frozen_family_holdout_scores_actual_predictions():
    model,train,test=study()
    report=evaluate_transfer(model,test,training_cases=train,benchmark='synthetic-linear-transfer-v1',tolerance=1e-5,required_domains=['synthetic-transfer'])
    assert report['passed']==20
    assert report['domains']['synthetic-transfer']['wilson_95'][0]<1
    gate=assess_generalization([report],minimum_accuracy=.9)
    assert gate['accepted']
    assert gate['external_review_performed'] is False


@pytest.mark.parametrize('field,value',[('family','linear_training'),('semantic_id','train-0'),('task_id','0')])
def test_leakage_rejected(field,value):
    model,train,test=study(); test[0]=dataclasses.replace(test[0],**{field:value})
    with pytest.raises(ValueError):evaluate_transfer(model,test,training_cases=train,benchmark='frozen')


def test_negative_transfer_retained_and_gate_fails():
    model,train,test=study()
    test=[dataclasses.replace(c,expected=-100) for c in test]
    report=evaluate_transfer(model,test,training_cases=train,benchmark='negative')
    assert report['passed']==0
    assert not assess_generalization([report])['accepted']
    with pytest.raises(ValueError):assess_generalization([report,report])
    report['passed']=20
    with pytest.raises(ValueError):assess_generalization([report])


def test_rehashed_inconsistent_metrics_rejected():
    model,train,test=study(); report=evaluate_transfer(model,test,training_cases=train,benchmark='frozen',tolerance=1e-5)
    report['domains']['synthetic-transfer']['passed']=0
    report['evaluation_id']=fingerprint({k:v for k,v in report.items() if k!='evaluation_id'})
    with pytest.raises(ValueError):assess_generalization([report])


def test_rehashed_flags_and_omitted_domains_are_rejected():
    model,train,test=study()
    report=evaluate_transfer(model,test,training_cases=train,benchmark='frozen',tolerance=1e-5)
    report['results'][0]['passed']=False
    report['evaluation_id']=fingerprint({k:v for k,v in report.items() if k!='evaluation_id'})
    with pytest.raises(ValueError,match='Outcome'):assess_generalization([report])
    report=evaluate_transfer(model,test,training_cases=train,benchmark='frozen',tolerance=1e-5)
    report['domains']={}
    report['evaluation_id']=fingerprint({k:v for k,v in report.items() if k!='evaluation_id'})
    with pytest.raises(ValueError,match='Omitted'):assess_generalization([report])
