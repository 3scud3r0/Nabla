"""Executable exact nonlinear learning and partition-isolation contracts."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from itertools import repeat
import sqlite3
import pytest
from nablamath.core.semantic_ir import fingerprint
from nablamath.training.symbolic_beam import (
    Sample,Term,SearchBudget,SymbolicModel,binary,fit_affine,score_model,
    search,replay_search,sample_digest,validate_samples)
from nablamath.training.symbolic_protocol import (
    split_lineage,freeze_experiment,verify_experiment,train_and_select,
    replay_selection,TestLedger,verify_final_report)


def sample(identifier,x,y,split='train',group=None):
    features=x if isinstance(x,tuple) else (x,)
    return Sample(str(identifier),str(group or identifier),features,Fraction(y),split)


def quadratic_data():
    return ([sample('train-'+str(x),x,2*x*x+3) for x in range(-4,5)],
            [sample('validation-'+str(x),x,2*x*x+3,'validation') for x in (5,6)],
            [sample('test-'+str(x),x,2*x*x+3,'test') for x in (7,8)])


def experiment_fixture():
    training,validation,test=quadratic_data()
    budget=SearchBudget(depth=2,beam_width=4,max_evaluations=40,operations=('add','multiply'))
    ablation=SearchBudget(depth=1,beam_width=4,max_evaluations=40,operations=('add','multiply'))
    experiment=freeze_experiment((*training,*validation,*test),owner='test maintainer',budget=budget,ablation_budgets=(ablation,))
    return experiment,training,validation,test


def test_term_evaluation_exact_without_source_execution():
    x=Term('variable'); y=Term('variable',variable=1)
    term=binary('multiply',binary('add',x,y),Term('reciprocal',(x,)))
    assert term.evaluate((Fraction(2),Fraction(3)))==Fraction(5,2)
    assert Term.from_data(term.to_data())==term
    assert Term('negate',(x,)).evaluate((2,))==-2
    assert Term('one').evaluate((2,))==1
    with pytest.raises(ValueError,match='zero'):term.evaluate((0,3))
    with pytest.raises(ValueError,match='schema'):y.evaluate((1,))
    with pytest.raises(ValueError):Term('__import__')


@pytest.mark.parametrize('operation,args,index',[
    ('multiply',(),0),('one',(Term('one'),),0),('variable',(),True),
    ('variable',(),8),('one',(),1),('reciprocal',('source',),0)])
def test_term_grammar_rejects_wrong_arity_and_indices(operation,args,index):
    with pytest.raises(ValueError):Term(operation,args,index)


def test_commutative_canonicalization_is_stable():
    x,y=Term('variable'),Term('variable',variable=1)
    assert binary('multiply',x,y)==binary('multiply',y,x)
    ordered=sorted((x,y),key=lambda t:t.term_id)
    with pytest.raises(ValueError,match='canonical'):Term('add',tuple(reversed(ordered)))


def test_parser_rejects_depth_and_extra_fields():
    data=Term('variable').to_data();data['source']='unsafe'
    with pytest.raises(ValueError):Term.from_data(data)
    term=Term('variable')
    for _ in range(5):term=Term('negate',(term,))
    with pytest.raises(ValueError,match='budget'):Term('negate',(term,))
    with pytest.raises(ValueError):Term('add',repeat(Term('one')))


def test_sample_binds_content_and_immutable_exact_features():
    features=[1,2]; item=Sample('id','lineage',features,'3/2','train');features[0]=99
    assert item.features==(Fraction(1),Fraction(2))
    assert Sample.from_data(item.to_data())==item
    assert replace(item,target=Fraction(2)).content_id!=item.content_id
    with pytest.raises(ValueError):replace(item,features=(float('nan'),))
    with pytest.raises(ValueError):replace(item,features=())
    with pytest.raises(ValueError):replace(item,split='hidden')
    with pytest.raises(ValueError):replace(item,features=repeat(1))


def test_exact_affine_training_and_constant_rank_deficiency():
    rows=[sample(str(x),x,3*x+2) for x in range(4)]
    model,mse=fit_affine(Term('variable'),rows)
    assert model.slope==3 and model.intercept==2 and mse==0
    constant,mse=fit_affine(Term('one'),rows)
    assert constant.slope==0 and constant.intercept==Fraction(13,2)
    assert mse==Fraction(45,4)
    assert SymbolicModel.from_data(model.to_data())==model
    assert SymbolicModel.from_data(model.to_data()).content_id==model.content_id
    with pytest.raises(ValueError):fit_affine(Term('variable'),[replace(rows[0],split='test')])


def test_affine_parameters_ignore_observation_order():
    rows=[sample(str(x),x,3*x+2) for x in range(4)]
    assert fit_affine(Term('variable'),rows)==fit_affine(Term('variable'),reversed(rows))


def test_nonlinear_grammar_finds_quadratic_exactly():
    training,validation,test=quadratic_data()
    report=search(training,budget=SearchBudget(depth=2,beam_width=4,max_evaluations=40,operations=('add','multiply')))
    winner=SymbolicModel.from_data(report['candidates'][0]['model'])
    assert report['candidates'][0]['training_mse']=='0'
    assert score_model(winner,test)['mse']=='0'
    assert score_model(winner,validation)['exact_matches']==2
    assert winner.term.operation=='multiply'
    assert replay_search(report,training)


def test_multivariate_product_not_merely_linear_regression():
    rows=[sample(f'{x}:{y}',(x,y),3*x*y-2) for x in (-2,-1,1,2) for y in (-3,1,3)]
    report=search(rows,budget=SearchBudget(depth=2,beam_width=4,max_evaluations=60,operations=('multiply',)))
    winner=SymbolicModel.from_data(report['candidates'][0]['model'])
    assert winner.predict((4,5))==58
    assert score_model(winner,rows)['mse']=='0'


def test_reciprocal_grammar_has_real_domain_guards():
    rows=[sample(str(x),x,Fraction(3,x)+2) for x in (-3,-2,-1,1,2,3)]
    report=search(rows,budget=SearchBudget(depth=2,beam_width=4,max_evaluations=40,operations=('reciprocal',)))
    winner=SymbolicModel.from_data(report['candidates'][0]['model'])
    assert winner.predict((4,))==Fraction(11,4)
    result=score_model(winner,[sample('zero',0,0,'test'),sample('valid',4,Fraction(11,4),'test')])
    assert result['mse'] is None and result['domain_failures']==['zero']
    assert result['total']==2 and result['exact_matches']==1


def test_domain_failures_recorded_without_claiming_success():
    rows=[sample(str(x),x,x) for x in (-1,0,1)]
    report=search(rows,budget=SearchBudget(depth=2,operations=('reciprocal',)))
    assert any('zero' in row['reason'] for row in report['failures'])
    assert report['attempted']==len(report['candidates'])+len(report['failures'])


@pytest.mark.parametrize('kwargs',[{'depth':0},{'depth':6},{'beam_width':0},{'max_evaluations':10001},
    {'complexity_penalty':'-1'},{'operations':('execute',)},{'operations':('multiply','multiply')}])
def test_search_contract_bounds(kwargs):
    with pytest.raises(ValueError):SearchBudget(**kwargs)


def test_evaluation_budget_is_exactly_enforced():
    rows=[sample(str(x),(x,x+1),x*x) for x in range(4)]
    report=search(rows,budget=SearchBudget(depth=4,beam_width=8,max_evaluations=3))
    assert report['attempted']==3 and report['budget_exhausted']
    assert len(report['candidates'])==3


def test_search_replay_rejects_rehashed_forgery_and_changed_training():
    rows=[sample(str(x),x,x*x) for x in range(4)]
    report=search(rows,budget=SearchBudget(depth=2))
    forged=deepcopy(report);forged['candidates'][0]['training_mse']='999'
    forged['search_id']=fingerprint({k:v for k,v in forged.items() if k!='search_id'})
    assert not replay_search(forged,rows)
    changed=[replace(rows[0],target=Fraction(123)),*rows[1:]]
    assert not replay_search(report,changed)
    assert search(reversed(rows),budget=SearchBudget(depth=2))==report


def test_training_refuses_duplicate_identity_mixed_schema_and_wrong_split():
    a=sample('a',1,2)
    for rows in ([a,a],[a,sample('b',(1,2),3)],[replace(a,split='validation')]):
        with pytest.raises(ValueError):search(rows)
    with pytest.raises(ValueError):validate_samples(repeat(a))


def test_lineage_split_deterministic_and_label_independent():
    rows=[sample(f'{group}-{i}',group*10+i,i,group=str(group)) for group in range(6) for i in range(2)]
    first=split_lineage(rows,seed=7,validation_groups=2,test_groups=1)
    second=split_lineage(reversed(rows),seed=7,validation_groups=2,test_groups=1)
    assert first==second
    assignment={s.group:s.split for s in first}
    changed=split_lineage([replace(s,target=Fraction(999)) for s in rows],seed=7,validation_groups=2,test_groups=1)
    assert {s.group:s.split for s in changed}==assignment
    assert {s.split for s in first}=={'train','validation','test'}
    assert all(len({s.split for s in first if s.group==group})==1 for group in assignment)


def test_lineage_split_requires_sufficient_independent_groups():
    rows=[sample('a',1,2,group='same'),sample('b',2,3,group='same')]
    with pytest.raises(ValueError):split_lineage(rows,seed=0)
    with pytest.raises(ValueError):split_lineage(rows,seed=True)


def test_freeze_rejects_semantic_and_lineage_leakage():
    experiment,training,validation,test=experiment_fixture()
    assert verify_experiment(experiment,(*training,*validation,*test))
    bad=replace(test[0],group=training[0].group)
    with pytest.raises(ValueError,match='Lineage'):freeze_experiment((*training,*validation,bad,test[1]),owner='o',budget=SearchBudget())
    bad=replace(test[0],features=training[0].features)
    with pytest.raises(ValueError,match='Identical input'):freeze_experiment((*training,*validation,bad,test[1]),owner='o',budget=SearchBudget())


def test_selection_and_ablation_are_blind_to_test_values():
    experiment,training,validation,test=experiment_fixture()
    selection=train_and_select(experiment,training,validation)
    assert selection['test_observed'] is False
    assert selection['ablations'][0]['validation']['mse']!='0'
    assert SymbolicModel.from_data(selection['selected_model']).predict((7,))==101
    assert replay_selection(selection,experiment,training,validation)
    # A modified frozen test changes the experiment binding, but cannot alter
    # fitting or selected parameters because test data is not an input here.
    changed=[replace(s,target=Fraction(-999)) for s in test]
    other=freeze_experiment((*training,*validation,*changed),owner=experiment['owner'],budget=SearchBudget(**experiment['budget']),
        ablation_budgets=[SearchBudget(**b) for b in experiment['ablation_budgets']])
    otherselection=train_and_select(other,training,validation)
    assert otherselection['selected_model']==selection['selected_model']
    assert otherselection['search']==selection['search']


def test_validation_cannot_be_substituted_after_freeze():
    experiment,training,validation,test=experiment_fixture()
    with pytest.raises(ValueError,match='frozen'):train_and_select(experiment,training,[replace(validation[0],target=Fraction(99)),validation[1]])
    with pytest.raises(ValueError,match='partition'):train_and_select(experiment,training,test)
    assert not verify_experiment(experiment,(*training,*validation,*[replace(s,target=Fraction(-1)) for s in test]))


def test_durable_test_once_and_report_replay(tmp_path):
    experiment,training,validation,test=experiment_fixture(); selection=train_and_select(experiment,training,validation)
    path=tmp_path/'test-ledger.sqlite'; ledger=TestLedger(path)
    report=ledger.evaluate_once(selection,experiment,training=training,validation=validation,test=test)
    assert report['test']['mse']=='0'
    assert report['ablations'][0]['test']['mse']!='0'
    assert verify_final_report(report,selection,experiment,training=training,validation=validation,test=test)
    ledger.close();ledger=TestLedger(path)
    assert ledger.get(experiment['experiment_id'])['report']==report
    with pytest.raises(PermissionError,match='consumed'):ledger.evaluate_once(selection,experiment,training=training,validation=validation,test=test)
    ledger.close()


def test_report_replay_rejects_rehashed_test_success(tmp_path):
    experiment,training,validation,test=experiment_fixture(); selection=train_and_select(experiment,training,validation)
    ledger=TestLedger(tmp_path/'ledger')
    report=ledger.evaluate_once(selection,experiment,training=training,validation=validation,test=test)
    forged=deepcopy(report);forged['test']['mse']='1'
    forged['report_id']=fingerprint({k:v for k,v in forged.items() if k!='report_id'})
    assert not verify_final_report(forged,selection,experiment,training=training,validation=validation,test=test)
    ledger.close()


def test_ledger_refuses_forged_selection_without_consuming_test(tmp_path):
    experiment,training,validation,test=experiment_fixture(); selection=train_and_select(experiment,training,validation)
    forged=deepcopy(selection);forged['selected_model']['intercept']='999'
    forged['selection_id']=fingerprint({k:v for k,v in forged.items() if k!='selection_id'})
    ledger=TestLedger(tmp_path/'ledger')
    with pytest.raises(ValueError,match='replay'):ledger.evaluate_once(forged,experiment,training=training,validation=validation,test=test)
    with pytest.raises(KeyError):ledger.get(experiment['experiment_id'])
    assert ledger.evaluate_once(selection,experiment,training=training,validation=validation,test=test)['test']['mse']=='0'
    ledger.close()


def test_interrupted_reservation_stays_consumed(tmp_path):
    experiment,training,validation,test=experiment_fixture(); selection=train_and_select(experiment,training,validation)
    ledger=TestLedger(tmp_path/'ledger')
    with ledger.db:ledger.db.execute("INSERT INTO tests VALUES(?,?,'reserved',NULL)",(experiment['experiment_id'],selection['selection_id']))
    with pytest.raises(PermissionError):ledger.evaluate_once(selection,experiment,training=training,validation=validation,test=test)
    assert ledger.get(experiment['experiment_id'])['state']=='reserved'
    ledger.close()


from nablamath.training.sparse_symbolic import (
    SparseBudget,SparseModel,fit_sparse,sparse_search,replay_sparse_search,
    freeze_sparse_experiment,train_sparse_and_select)
from nablamath.training.symbolic_stability import (
    Interval,term_interval,predict_interval,sensitivity_report,replay_sensitivity,
    jackknife_lineage,replay_jackknife)


def sparse_fixture():
    def target(x,y):return 2*x*x+3*x*y-4
    training=[sample(f'train:{x}:{y}',(x,y),target(x,y),group=f'lineage:{x}') for x in (-2,-1,1,2) for y in (-3,1,3)]
    validation=[sample(f'validation:{x}:{y}',(x,y),target(x,y),'validation') for x,y in ((3,2),(4,-1))]
    test=[sample(f'test:{x}:{y}',(x,y),target(x,y),'test') for x,y in ((5,2),(6,-2))]
    grammar=SearchBudget(depth=2,beam_width=4,max_evaluations=60,operations=('add','multiply'))
    sparse=SparseBudget(max_terms=3,max_dictionary=20,max_fits=100,complexity_penalty='0')
    experiment=freeze_sparse_experiment((*training,*validation,*test),owner='synthetic protocol owner',grammar_budget=grammar,sparse_budget=sparse,
            ablation_budgets=(SearchBudget(depth=1,beam_width=4,max_evaluations=60,operations=('add','multiply')),))
    return experiment,training,validation,test


def test_sparse_exact_fit_represents_multiple_nonlinear_features():
    experiment,training,validation,test=sparse_fixture()
    x,y=Term('variable'),Term('variable',variable=1)
    model,mse=fit_sparse((binary('multiply',x,x),binary('multiply',x,y)),training)
    assert mse==0 and model.predict((5,2))==76
    assert SparseModel.from_data(model.to_data())==model
    assert model.complexity==7
    assert model.training_content_id==sample_digest(training)
    assert score_model(model,test)['mse']=='0'


def test_sparse_gram_solver_rejects_collinear_features():
    rows=[sample(str(x),(x,2*x),x*x) for x in range(-3,4)]
    with pytest.raises(ValueError,match='Rank-deficient'):
        fit_sparse((Term('variable'),Term('variable',variable=1)),rows)
    with pytest.raises(ValueError,match='Constant'):fit_sparse((Term('one'),),rows)
    with pytest.raises(ValueError,match='Repeated'):fit_sparse((Term('variable'),Term('variable')),rows)


def test_sparse_constant_model_has_no_unneeded_terms():
    rows=[sample(str(x),x,3) for x in range(4)]
    report=sparse_search(rows,grammar_budget=SearchBudget(depth=2),sparse_budget=SparseBudget(max_terms=3))
    winner=SparseModel.from_data(report['candidates'][0]['model'])
    assert winner.terms==() and winner.intercept==3
    assert len(report['candidates'])==1
    assert winner.predict((99,))==3


def test_sparse_search_real_gain_over_single_feature():
    experiment,training,validation,test=sparse_fixture()
    report=sparse_search(training,grammar_budget=SearchBudget(**experiment['budget']),sparse_budget=SparseBudget(**experiment['sparse_budget']))
    initial=Fraction(report['candidates'][0]['training_mse'])
    best=report['candidates'][-1]
    assert Fraction(best['training_mse'])<initial
    assert best['training_mse']=='0'
    assert report['grammar_search']['candidates'][0]['training_mse']!='0'
    assert score_model(SparseModel.from_data(best['model']),test)['mse']=='0'
    assert replay_sparse_search(report,training)


def test_sparse_search_budget_and_rank_failure_audit():
    rows=[sample(str(x),(x,2*x),x*x) for x in range(-3,4)]
    report=sparse_search(rows,grammar_budget=SearchBudget(depth=2),sparse_budget=SparseBudget(max_terms=3,max_fits=4))
    assert report['fits']<=4 and report['budget_exhausted']
    assert report['fits']==len(report['considered'])+len(report['failures'])
    full=sparse_search(rows,grammar_budget=SearchBudget(depth=2),sparse_budget=SparseBudget(max_terms=2,max_fits=100,complexity_penalty='0'))
    assert any('Rank-deficient' in row['reason'] for row in full['failures'])


@pytest.mark.parametrize('kwargs',[{'max_terms':7},{'max_fits':513},{'max_dictionary':65},{'max_terms':True},{'complexity_penalty':'-1'}])
def test_sparse_budget_contracts(kwargs):
    with pytest.raises(ValueError):SparseBudget(**kwargs)


def test_sparse_model_parser_cannot_load_arbitrary_class():
    from nablamath.training.symbolic_beam import load_model
    with pytest.raises(ValueError):load_model({'version':'python-module','class':'exec'})
    experiment,training,validation,test=sparse_fixture()
    model,_=fit_sparse((Term('variable'),),training)
    data=model.to_data();data['weights']=[]
    with pytest.raises(ValueError):SparseModel.from_data(data)
    data=model.to_data();data['training_ids']=list(reversed(data['training_ids']))
    with pytest.raises(ValueError):SparseModel.from_data(data)


def test_sparse_validation_selection_and_final_test_once(tmp_path):
    experiment,training,validation,test=sparse_fixture()
    assert verify_experiment(experiment,(*training,*validation,*test))
    selection=train_sparse_and_select(experiment,training,validation)
    assert selection['test_observed'] is False
    assert replay_selection(selection,experiment,training,validation)
    ledger=TestLedger(tmp_path/'sparse-ledger')
    report=ledger.evaluate_once(selection,experiment,training=training,validation=validation,test=test)
    assert report['test']['mse']=='0'
    assert report['ablations'][0]['test']['mse']!='0'
    assert verify_final_report(report,selection,experiment,training=training,validation=validation,test=test)
    with pytest.raises(PermissionError):ledger.evaluate_once(selection,experiment,training=training,validation=validation,test=test)
    ledger.close()


def test_sparse_replay_rejects_rehashed_coefficients():
    experiment,training,validation,test=sparse_fixture()
    report=sparse_search(training,grammar_budget=SearchBudget(**experiment['budget']),sparse_budget=SparseBudget(**experiment['sparse_budget']))
    report['candidates'][-1]['model']['weights'][0]='999'
    report['search_id']=fingerprint({k:v for k,v in report.items() if k!='search_id'})
    assert not replay_sparse_search(report,training)


def test_sparse_train_partition_is_never_validation():
    experiment,training,validation,test=sparse_fixture()
    with pytest.raises(ValueError):sparse_search(validation)
    with pytest.raises(ValueError):fit_sparse((Term('variable'),),test)
    changed=deepcopy(experiment);changed['sparse_budget']['max_terms']=1
    assert not verify_experiment(changed,(*training,*validation,*test))


def test_interval_basic_arithmetic_exact_and_signed():
    a,b=Interval(-2,3),Interval(-4,-1)
    assert a.add(b)==Interval(-6,2)
    assert a.negate()==Interval(-3,2)
    assert a.multiply(b)==Interval(-12,8)
    assert Interval(-4,-2).reciprocal()==Interval(Fraction(-1,2),Fraction(-1,4))
    assert Interval(2,4).reciprocal()==Interval(Fraction(1,4),Fraction(1,2))
    assert a.contains(Fraction(3,2)) and not a.contains(4)
    with pytest.raises(ValueError):Interval(3,2)
    with pytest.raises(ValueError):Interval(-1,1).reciprocal()


def test_interval_product_encloses_all_grid_predictions():
    x,y=Term('variable'),Term('variable',variable=1)
    term=binary('multiply',binary('add',x,y),Term('negate',(x,)))
    boxes=(Interval(-2,3),Interval(-1,4)); result=term_interval(term,boxes)
    for a in range(-4,7):
        for b in range(-2,9):
            assert result.contains(term.evaluate((Fraction(a,2),Fraction(b,2))))
    with pytest.raises(ValueError):term_interval(y,(Interval(0,1),))
    with pytest.raises(ValueError):term_interval(x,repeat(Interval(0,1)))


def test_affine_negative_slope_interval_is_ordered():
    rows=[sample(str(x),x,-3*x+2) for x in range(-2,3)]
    model,mse=fit_affine(Term('variable'),rows)
    interval=predict_interval(model,(Interval(-1,2),))
    assert interval==Interval(-4,5)
    report=sensitivity_report(model,[(0,),(2,)],radii=('1/10',))
    assert report['failures']==0
    assert report['points'][0]['enclosure']==['17/10','23/10']
    assert replay_sensitivity(report,model)
    report['points'][0]['enclosure']=['0','0']
    report['sensitivity_id']=fingerprint({k:v for k,v in report.items() if k!='sensitivity_id'})
    assert not replay_sensitivity(report,model)


def test_sparse_interval_encloses_multiple_terms():
    experiment,training,validation,test=sparse_fixture()
    x,y=Term('variable'),Term('variable',variable=1)
    model,_=fit_sparse((binary('multiply',x,x),binary('multiply',x,y)),training)
    enclosure=predict_interval(model,(Interval(1,3),Interval(-2,2)))
    for a in (1,2,3):
        for b in (-2,-1,0,1,2):assert enclosure.contains(model.predict((a,b)))
    report=sensitivity_report(model,[(2,1)],radii=('1/10','1/5'))
    assert replay_sensitivity(report,model)


def test_sensitivity_records_singular_boxes_without_dropping_rows():
    rows=[sample(str(x),x,Fraction(1,x)) for x in (1,2,3)]
    model,_=fit_affine(Term('reciprocal',(Term('variable'),)),rows)
    report=sensitivity_report(model,[(0,),(2,)],radii=(1,))
    assert report['failures']==1
    assert report['points'][0]['status']=='domain_or_arithmetic_failure'
    assert report['points'][1]['status']=='enclosed'
    with pytest.raises(ValueError):sensitivity_report(model,[(2,)],radii=(-1,))
    with pytest.raises(ValueError):sensitivity_report(model,[(2,),(2,)],radii=(1,))


def test_jackknife_refits_lineage_groups_and_replays():
    training=[sample(str(x),x,2*x*x+3,group='group-'+str(abs(x))) for x in (-3,-2,-1,1,2,3)]
    validation=[sample('val-'+str(x),x,2*x*x+3,'validation') for x in (4,5)]
    budget=SearchBudget(depth=2,beam_width=4,max_evaluations=40,operations=('multiply',))
    report=jackknife_lineage(training,validation,budget=budget,probe_points=[(6,)])
    assert len(report['fits'])==3
    assert report['prediction_ranges'][0]['minimum']=='75'
    assert report['prediction_ranges'][0]['maximum']=='75'
    for row in report['fits']:
        model=SymbolicModel.from_data(row['model'])
        assert not {s.identifier for s in training if s.group==row['omitted_group']}&set(model.training_ids)
    assert replay_jackknife(report,training,validation)


def test_jackknife_does_not_accept_test_or_leaking_validation():
    training=[sample(str(x),x,x*x,group=str(x)) for x in range(3)]
    validation=[sample('v',4,16,'validation')]
    budget=SearchBudget(depth=2,beam_width=4,max_evaluations=40)
    with pytest.raises(ValueError):jackknife_lineage(training,[replace(validation[0],split='test')],budget=budget,probe_points=[(5,)])
    with pytest.raises(ValueError):jackknife_lineage(training,[replace(validation[0],group='0')],budget=budget,probe_points=[(5,)])
    with pytest.raises(ValueError):jackknife_lineage(training,validation,budget=SearchBudget(max_evaluations=129),probe_points=[(5,)])
    with pytest.raises(ValueError):jackknife_lineage(training,validation,budget=budget,probe_points=repeat((5,)))


from nablamath.training.symbolic_derivatives import (
    Differential,term_differential,model_differential,differential_report,replay_differentials)


def test_exact_second_order_multivariate_derivatives():
    x,y=Term('variable'),Term('variable',variable=1)
    term=binary('add',binary('multiply',x,x),binary('multiply',x,y))
    result=term_differential(term,(2,3))
    assert result.value==10
    assert result.gradient==(7,2)
    assert result.hessian==((2,1),(1,0))
    assert result.to_data()=={'value':'10','gradient':['7','2'],'hessian':[['2','1'],['1','0']]}


def test_reciprocal_chain_rule_includes_second_derivative():
    x=Term('variable');term=Term('reciprocal',(x,))
    result=term_differential(term,(2,))
    assert result.value==Fraction(1,2)
    assert result.gradient==(Fraction(-1,4),)
    assert result.hessian==((Fraction(1,4),),)
    with pytest.raises(ValueError,match='zero'):term_differential(term,(0,))
    # 1/(x*x) has derivative -2/x^3 and second derivative 6/x^4.
    squared=Term('reciprocal',(binary('multiply',x,x),))
    result=term_differential(squared,(2,))
    assert result.gradient==(Fraction(-1,4),)
    assert result.hessian==((Fraction(3,8),),)


def test_sparse_model_derivative_matches_generating_polynomial():
    experiment,training,validation,test=sparse_fixture()
    x,y=Term('variable'),Term('variable',variable=1)
    model,_=fit_sparse((binary('multiply',x,x),binary('multiply',x,y)),training)
    result=model_differential(model,(5,2))
    assert result.value==76
    assert result.gradient==(26,15)
    assert result.hessian==((4,3),(3,0))
    report=differential_report(model,[(5,2),(6,-2)])
    assert report['failures']==0 and replay_differentials(report,model)
    report['points'][0]['gradient']=['0','0']
    report['differential_id']=fingerprint({k:v for k,v in report.items() if k!='differential_id'})
    assert not replay_differentials(report,model)


def test_constant_sparse_differential_retains_feature_dimension():
    model,_=fit_sparse((),[sample(str(i),(i,i+1),4) for i in range(3)])
    result=model_differential(model,(100,200))
    assert result.value==4 and result.gradient==(0,0)
    assert result.hessian==((0,0),(0,0))


def test_affine_model_derivative_scales_and_translates():
    model,_=fit_affine(Term('variable'),[sample(str(i),i,-3*i+7) for i in range(3)])
    result=model_differential(model,(2,))
    assert result.value==1 and result.gradient==(-3,) and result.hessian==((0,),)
    report=differential_report(model,[(2,)])
    assert replay_differentials(report,model)


def test_quadratic_gradient_metamorphic_symmetric_difference_exact():
    x,y=Term('variable'),Term('variable',variable=1)
    term=binary('add',binary('multiply',x,x),binary('multiply',x,y))
    point=(Fraction(7,3),Fraction(-5,2)); step=Fraction(1,100)
    result=term_differential(term,point)
    for dimension in range(2):
        plus=list(point);minus=list(point);plus[dimension]+=step;minus[dimension]-=step
        derivative=(term.evaluate(plus)-term.evaluate(minus))/(2*step)
        second=(term.evaluate(plus)-2*term.evaluate(point)+term.evaluate(minus))/(step*step)
        assert derivative==result.gradient[dimension]
        assert second==result.hessian[dimension][dimension]


def test_differential_contract_rejects_asymmetric_and_unbounded_data():
    with pytest.raises(ValueError,match='symmetric'):Differential(1,(1,2),((1,2),(3,4)))
    with pytest.raises(ValueError):Differential(1,(1,),((1,2),))
    with pytest.raises(ValueError):term_differential(Term('variable'),repeat(1))
    with pytest.raises(ValueError):model_differential(object(),(1,))
    with pytest.raises(ValueError):differential_report(object(),repeat((1,)))


def test_derivative_report_retains_singular_points():
    term=Term('reciprocal',(Term('variable'),))
    model,_=fit_affine(term,[sample(str(i),i,Fraction(1,i)) for i in (1,2,3)])
    report=differential_report(model,[(0,),(1,)])
    assert report['failures']==1 and len(report['points'])==2
    assert report['points'][0]['status']=='domain_or_arithmetic_failure'
    assert report['points'][1]['gradient']==['-1']
    assert replay_differentials(report,model)


def test_durable_ledger_concurrent_admission_serializes(tmp_path):
    import concurrent.futures
    experiment,training,validation,test=experiment_fixture();selection=train_and_select(experiment,training,validation)
    path=tmp_path/'concurrent-ledger'
    TestLedger(path).close()
    def attempt():
        ledger=TestLedger(path)
        try:
            try:
                ledger.evaluate_once(selection,experiment,training=training,validation=validation,test=test)
                return 'accepted'
            except PermissionError:return 'consumed'
        finally:ledger.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(lambda _:attempt(),range(2)))
    assert sorted(outcomes)==['accepted','consumed']


def test_ledger_capacity_is_durable_and_fail_closed(tmp_path):
    experiment,training,validation,test=experiment_fixture();selection=train_and_select(experiment,training,validation)
    ledger=TestLedger(tmp_path/'capacity',capacity=1)
    with ledger.db:ledger.db.execute("INSERT INTO tests VALUES('other','other','failed',NULL)")
    with pytest.raises(PermissionError,match='capacity'):ledger.evaluate_once(selection,experiment,training=training,validation=validation,test=test)
    with pytest.raises(KeyError):ledger.get(experiment['experiment_id'])
    ledger.close()


def test_failed_score_consumes_final_test_reservation(tmp_path,monkeypatch):
    import nablamath.training.symbolic_protocol as protocol
    experiment,training,validation,test=experiment_fixture();selection=train_and_select(experiment,training,validation)
    ledger=TestLedger(tmp_path/'failed-run')
    original=protocol.score_model
    def failing(model,rows):
        if rows[0].split=='test':raise RuntimeError('injected disk/worker failure')
        return original(model,rows)
    monkeypatch.setattr(protocol,'score_model',failing)
    with pytest.raises(RuntimeError):ledger.evaluate_once(selection,experiment,training=training,validation=validation,test=test)
    assert ledger.get(experiment['experiment_id'])['state']=='failed'
    monkeypatch.setattr(protocol,'score_model',original)
    with pytest.raises(PermissionError):ledger.evaluate_once(selection,experiment,training=training,validation=validation,test=test)
    ledger.close()


def test_full_experiment_replay_blocks_rehashed_false_group_contract(tmp_path):
    experiment,training,validation,test=experiment_fixture()
    forged=deepcopy(experiment);forged['groups']['invented-group']='test'
    forged['experiment_id']=fingerprint({k:v for k,v in forged.items() if k!='experiment_id'})
    # Unused metadata cannot make it through final freeze reconstruction.
    selection=train_and_select(forged,training,validation)
    ledger=TestLedger(tmp_path/'forged-contract')
    with pytest.raises(ValueError,match='Experiment replay'):ledger.evaluate_once(selection,forged,training=training,validation=validation,test=test)
    ledger.close()


from nablamath.training.forge_symbolic import (
    component_inputs,training_components,IntegralComponentPredictor,freeze_campaign,
    select_campaign,evaluate_campaign_once,replay_campaign_report)
from nablamath.forge.reverse_builder import generate_task
from nablamath.datasets.schema import make_record


def forge_campaign_fixture():
    # Entirely separate from laboratory-run seed951017 and its original48 cases.
    # Train degree2, validation degree3, final testdegree4; generator still shares
    # many coefficient/order pairs, explicitly counted by campaign metadata.
    records=[];seen=set()
    for seed in range(955000,955040):
        generated=generate_task('polynomial_integral',seed,3)
        if generated.task.content_id in seen:continue
        seen.add(generated.task.content_id)
        records.append(make_record(generated.task,generated.witness,license_id='MIT',provenance=f'fresh synthetic campaign seed={seed}',
           scope='within-family integral component learning',limitations='strong grammar and component priors; no cross-family inference',split='train'))
        if len(records)==12:break
    validation=[generate_task('polynomial_integral',seed,4).task for seed in range(956000,956006)]
    test=[generate_task('polynomial_integral',seed,5).task for seed in range(957000,957024)]
    budget=SearchBudget(depth=3,beam_width=12,max_evaluations=200,operations=('multiply','reciprocal'))
    baseline=SearchBudget(depth=1,beam_width=12,max_evaluations=200,operations=('multiply','reciprocal'))
    campaign=freeze_campaign(records,validation,test,owner='declared synthetic campaign maintainer',budget=budget,ablation_budgets=(baseline,))
    return campaign,records,validation,test


def test_forge_labels_only_consumed_from_train_traces():
    campaign,records,validation,test=forge_campaign_fixture()
    components=training_components(records)
    assert len(components)==36
    first=records[0];task=first.task
    assert {s.group for s in components}=={r.task.content_id for r in records}
    assert component_inputs(task)[0][1]==1
    assert all(s.split=='train' for s in components)
    with pytest.raises(ValueError,match='train traces'):training_components([first.with_split('validation')])
    with pytest.raises(ValueError,match='train traces'):training_components([first.with_split('test')])
    with pytest.raises(ValueError,match='Duplicate'):training_components([first,first])


def test_forge_learned_rule_predicts_without_witness_solver_or_verifier(monkeypatch):
    import nablamath.training.forge_symbolic as module
    campaign,records,validation,test=forge_campaign_fixture()
    selection=select_campaign(campaign,records,validation)
    model=SymbolicModel.from_data(selection['selected_model']);predictor=IntegralComponentPredictor(model)
    def forbidden(*args,**kwargs):raise AssertionError('prediction accessed evaluation oracle')
    monkeypatch.setattr(module,'verify_candidate',forbidden)
    # Predictor receives a TaskSpec with no witness or target trace.
    candidate=predictor.predict(test[0])
    assert len(candidate['coefficients'])==6 and candidate['coefficients'][0]=='0'
    assert model.slope==1 and model.intercept==0
    assert model.term.operation=='multiply'


def test_forge_fresh_degree_holdout_and_declared_ablation(tmp_path):
    campaign,records,validation,test=forge_campaign_fixture()
    selection=select_campaign(campaign,records,validation)
    assert selection['test_observed'] is False
    ledger=TestLedger(tmp_path/'fresh-forge-test')
    report=evaluate_campaign_once(ledger,campaign,selection,records=records,validation_tasks=validation,test_tasks=test)
    assert report['test']['passed']==report['test']['total']==24
    assert report['ablations'][0]['test']['passed']==0
    assert report['priors']['input_features']==['coefficient','exponent_plus_one']
    assert campaign['component_input_overlap_with_train']['test']>0
    assert all(task.size==5 for task in test)
    assert all(record.task.size==3 for record in records)
    assert replay_campaign_report(report,campaign,selection,records=records,validation_tasks=validation,test_tasks=test)
    ledger.close();ledger=TestLedger(tmp_path/'fresh-forge-test')
    with pytest.raises(PermissionError,match='consumed'):evaluate_campaign_once(ledger,campaign,selection,records=records,validation_tasks=validation,test_tasks=test)
    ledger.close()


def test_forge_campaign_rejects_task_and_declared_lineage_leakage():
    campaign,records,validation,test=forge_campaign_fixture();budget=SearchBudget(**campaign['budget'])
    with pytest.raises(ValueError,match='Task leakage'):
        freeze_campaign(records,validation,[records[0].task],owner='owner',budget=budget)
    lineage={records[0].task.content_id:'shared-parent',validation[0].content_id:'shared-parent'}
    with pytest.raises(ValueError,match='Lineage leakage'):
        freeze_campaign(records,validation,test,owner='owner',budget=budget,lineage=lineage)
    with pytest.raises(ValueError,match='Unknown'):
        freeze_campaign(records,validation,test,owner='owner',budget=budget,lineage={'unknown':'parent'})


def test_forge_contract_cannot_change_labels_or_search_after_selection(tmp_path):
    campaign,records,validation,test=forge_campaign_fixture();selection=select_campaign(campaign,records,validation)
    forged=deepcopy(selection);forged['selected_model']['slope']='999'
    forged['selection_id']=fingerprint({k:v for k,v in forged.items() if k!='selection_id'})
    ledger=TestLedger(tmp_path/'forged-forge-selection')
    with pytest.raises(ValueError,match='replay'):evaluate_campaign_once(ledger,campaign,forged,records=records,validation_tasks=validation,test_tasks=test)
    with pytest.raises(KeyError):ledger.get(campaign['campaign_id'])
    ledger.close()


def test_forge_published_report_is_regraded_not_hash_only(tmp_path):
    campaign,records,validation,test=forge_campaign_fixture();selection=select_campaign(campaign,records,validation)
    ledger=TestLedger(tmp_path/'replay-forge')
    report=evaluate_campaign_once(ledger,campaign,selection,records=records,validation_tasks=validation,test_tasks=test)
    report['test']['passed']=23
    report['report_id']=fingerprint({k:v for k,v in report.items() if k!='report_id'})
    assert not replay_campaign_report(report,campaign,selection,records=records,validation_tasks=validation,test_tasks=test)
    ledger.close()


def test_testledger_completion_bound_to_reserved_experiment_and_selection(tmp_path):
    experiment,training,validation,test=experiment_fixture();selection=train_and_select(experiment,training,validation)
    source=TestLedger(tmp_path/'source-report')
    report=source.evaluate_once(selection,experiment,training=training,validation=validation,test=test);source.close()
    ledger=TestLedger(tmp_path/'binding');ledger.reserve(experiment['experiment_id'],selection['selection_id'])
    forged=deepcopy(report);forged['experiment_id']='a'*64
    forged['report_id']=fingerprint({k:v for k,v in forged.items() if k!='report_id'})
    with pytest.raises(ValueError,match='experiment'):ledger.finish(experiment['experiment_id'],forged)
    forged=deepcopy(report);forged['selection_id']='b'*64
    forged['report_id']=fingerprint({k:v for k,v in forged.items() if k!='report_id'})
    with pytest.raises(ValueError,match='selection'):ledger.finish(experiment['experiment_id'],forged)
    assert ledger.get(experiment['experiment_id'])['state']=='reserved'
    ledger.finish(experiment['experiment_id'],report)
    assert ledger.get(experiment['experiment_id'])['report']==report
    with pytest.raises(PermissionError):ledger.finish(experiment['experiment_id'],report)
    ledger.close()
