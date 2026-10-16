"""Independent finite enumerations and correlated-cluster adversarial examples."""
from copy import deepcopy
from fractions import Fraction as F
from itertools import repeat
import math

import pytest

from nablamath.core.semantic_ir import fingerprint
from nablamath.evaluation.clustered import (
    PairedMeasurement as M, cluster_bootstrap, paired_randomization,
    domain_summary, measurements, verify_cluster_report, zero_failure_sample_size,
)


def row(index,*,group=None,domain='math',candidate=0,baseline=1,weight=1):
    return M(fingerprint({'task':index}),str(index) if group is None else group,domain,candidate,baseline,weight)


def test_exact_sign_flip_matches_independent_counting_for_three_identical_improvements():
    rows=[row(i) for i in range(3)]
    report=paired_randomization(rows)
    assert report['randomizations']==8 and report['extreme']==2
    assert report['two_sided_p']=='1/4'
    assert report['null_assumption_externally_validated'] is False
    assert verify_cluster_report(report,rows,kind='randomization')


def test_dependent_replicates_are_one_exchangeability_unit():
    independent=[row(i) for i in range(8)]
    dependent=[row(i,group='one dependent source') for i in range(8)]
    assert paired_randomization(independent)['two_sided_p']=='1/128'
    assert paired_randomization(dependent)['two_sided_p']=='1'
    assert paired_randomization(dependent)['cluster_count']==1
    with pytest.raises(ValueError,match='at least two'):
        cluster_bootstrap(dependent,repetitions=32)


def test_zero_difference_has_probability_one_and_degenerate_bootstrap():
    rows=[row(i,candidate=F(1,3),baseline=F(1,3)) for i in range(4)]
    assert paired_randomization(rows)['two_sided_p']=='1'
    report=cluster_bootstrap(rows,repetitions=32)
    assert report['weighted_improvement']=='0' and report['interval']==['0','0']


def test_bootstrap_is_deterministic_cluster_preserving_and_immutable():
    rows=[row(i,group=str(i//2),candidate=0,baseline=i+1,weight=(i%2)+1) for i in range(8)]
    first=cluster_bootstrap(rows,repetitions=128,seed=12)
    assert first==cluster_bootstrap(reversed(rows),repetitions=128,seed=12)
    assert first['cluster_count']==4 and first['observation_count']==8
    assert F(first['interval'][0])<=F(first['interval'][1])
    assert first['report_id']!=cluster_bootstrap(rows,repetitions=128,seed=13)['report_id']
    assert verify_cluster_report(first,rows,kind='bootstrap',repetitions=128,seed=12)
    first['interval']=['-10','10']
    first['report_id']=fingerprint({k:v for k,v in first.items() if k!='report_id'})
    assert not verify_cluster_report(first,rows,kind='bootstrap',repetitions=128,seed=12)


def test_monte_carlo_plus_one_never_reports_zero_and_is_reproducible():
    rows=[row(i) for i in range(32)]
    first=paired_randomization(rows,mode='monte_carlo',repetitions=64,seed=3)
    assert F(first['two_sided_p'])>=F(1,65)
    assert first==paired_randomization(rows,mode='monte_carlo',repetitions=64,seed=3)
    with pytest.raises(ValueError,match='enumeration'):
        paired_randomization(rows,mode='exact')


def test_domain_macro_and_micro_answer_distinct_declared_questions():
    rows=[row(0,domain='rare',candidate=0,baseline=10),
          row(1,domain='common',candidate=2,baseline=1),
          row(2,domain='common',candidate=2,baseline=1)]
    report=domain_summary(rows)
    assert report['macro_domain_improvement']=='9/2'
    assert report['micro_improvement']=='8/3'
    assert report['domain_comparability_established'] is False
    assert verify_cluster_report(report,rows,kind='domains')


def test_weighted_loss_and_negative_improvement_are_retained():
    rows=[row(0,candidate=3,baseline=1,weight=3),row(1,candidate=0,baseline=1,weight=1)]
    report=domain_summary(rows)
    assert report['micro_improvement']=='-5/4'
    assert paired_randomization(rows)['observed_weighted_sum']=='5'


@pytest.mark.parametrize('field,value', [('weight',0),('weight',True),('candidate_loss',-1),
    ('candidate_loss',.5),('baseline_loss','nan'),('baseline_loss',str(2**40)),
    ('domain',''),('group',''),('task_id','fake')])
def test_measurement_contracts_refuse_ambiguous_values(field,value):
    data=dict(task_id='a'*64,group='g',domain='d',candidate_loss=0,baseline_loss=1,weight=1)
    data[field]=value
    with pytest.raises(ValueError):M(**data)


def test_duplicate_rows_infinite_inputs_and_split_clusters_are_rejected():
    value=row(1)
    for values in ([value,value],repeat(value),[],[value,row(2,group='1',domain='other')]):
        with pytest.raises(ValueError):measurements(values)


@pytest.mark.parametrize('kwargs',[{'repetitions':True},{'repetitions':31},{'repetitions':4097},
    {'seed':-1},{'seed':True},{'coverage':'1'},{'coverage':'0'},{'coverage':.95}])
def test_bootstrap_budget_and_confidence_refusals(kwargs):
    with pytest.raises(ValueError):cluster_bootstrap([row(0),row(1)],**kwargs)


def test_randomization_mode_and_budget_refusals():
    rows=[row(0),row(1)]
    with pytest.raises(ValueError):paired_randomization(rows,mode='asymptotic-unverified')
    with pytest.raises(ValueError):paired_randomization(rows,mode='monte_carlo',repetitions=1)
    with pytest.raises(ValueError):paired_randomization(rows,seed=True)
    assert not verify_cluster_report({},rows,kind='missing')


@pytest.mark.parametrize('rate,alpha', [('1/100','1/20'),('1/10','1/20'),('1/2','1/16'),('1/1000','1/10')])
def test_zero_failure_sample_planning_has_exact_minimal_binomial_bound(rate,alpha):
    result=zero_failure_sample_size(maximum_failure_rate=rate,alpha=alpha)
    n=result['sample_size']
    assert (1-F(rate))**n<=F(alpha)
    assert n==1 or (1-F(rate))**(n-1)>F(alpha)
    assert result['actual_trials_executed']==0 and result['actual_independence_established'] is False


@pytest.mark.parametrize('rate,alpha,maximum', [('0','1/20',100),('1','1/20',100),
    ('1/10000','1/20',10),('1/100','0',100),(.01,'1/20',1000),('1/100','1/20',True)])
def test_power_planning_never_converts_invalid_or_infeasible_budget_to_success(rate,alpha,maximum):
    with pytest.raises(ValueError):zero_failure_sample_size(maximum_failure_rate=rate,alpha=alpha,maximum=maximum)


@pytest.mark.parametrize('value',[None,1,True])
def test_measurement_collection_invalid_iterable_normalizes_validation(value):
    with pytest.raises(ValueError,match='iterable'):
        measurements(value)
