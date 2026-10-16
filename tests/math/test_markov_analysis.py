"""Finite-chain results checked against analytic laws and exact residuals."""

from copy import deepcopy
from fractions import Fraction

import pytest

from nablamath.calc.notebook import Notebook
from nablamath.calc.session import CalculationSession
from nablamath.core.semantic_ir import fingerprint
from nablamath.math.probability.absorption import (
    hitting_statistics,verify_hitting_statistics,stationary_classes,
    verify_stationary_classes,discounted_rewards,verify_discounted_rewards,
)


@pytest.mark.parametrize('p', ['1/2','1/3','1/7','3/4','1'])
def test_geometric_hitting_moments(p):
    p = Fraction(p)
    receipt = hitting_statistics([[1-p,p],[0,1]],[1])
    start, target = receipt['states']
    assert start['probability'] == '1'
    assert Fraction(start['unconditional_mean']) == 1/p
    assert Fraction(start['conditional_variance']) == (1-p)/p**2
    assert Fraction(start['conditional_second_moment']) == (2-p)/p**2
    assert target['unconditional_mean'] == '0'
    assert verify_hitting_statistics(receipt)


def test_defective_hitting_keeps_conditional_and_unconditional_separate():
    receipt = hitting_statistics([['1/2','1/4','1/4'],[0,1,0],[0,0,1]],[1])
    start, target, dead = receipt['states']
    assert start['probability'] == '1/2'
    assert start['unconditional_mean_status'] == 'infinite'
    assert start['unconditional_mean'] is None
    assert start['conditional_mean'] == '2'
    assert start['conditional_variance'] == '2'
    assert dead['probability'] == '0'
    assert dead['conditional_mean'] is None
    assert target['conditional_mean'] == '0'


def test_targets_are_stopping_states_even_when_original_chain_returns():
    receipt = hitting_statistics([[0,1],[1,0]],[1])
    assert receipt['states'][0]['unconditional_mean'] == '1'
    assert receipt['states'][1]['unconditional_mean'] == '0'
    all_targets = hitting_statistics([[0,1],[1,0]],[0,1])
    assert all(row['conditional_mean'] == '0' for row in all_targets['states'])


def test_birth_death_gambler_ruin_formula():
    size = 7
    rows = [[Fraction() for _ in range(size)] for _ in range(size)]
    rows[0][0] = rows[-1][-1] = Fraction(1)
    for i in range(1,size-1):
        rows[i][i-1] = rows[i][i+1] = Fraction(1,2)
    result = hitting_statistics(rows,[size-1])
    for i,row in enumerate(result['states']):
        assert Fraction(row['probability']) == Fraction(i,size-1)
    exit_result = hitting_statistics(rows,[0,size-1])
    for i,row in enumerate(exit_result['states']):
        assert Fraction(row['unconditional_mean']) == i*(size-1-i)


def test_periodic_stationarity_is_not_claimed_as_convergence():
    receipt = stationary_classes([[0,1],[1,0]])
    assert receipt['unique_stationary_distribution']
    assert receipt['closed_classes'][0]['period'] == 2
    assert receipt['closed_classes'][0]['distribution'] == ['1/2','1/2']
    assert receipt['closed_classes'][0]['mean_return_times'] == {'0':'2','1':'2'}
    assert verify_stationary_classes(receipt)


def test_multiple_recurrent_classes_and_transient_states():
    receipt = stationary_classes([[0,'1/3','2/3'],[0,1,0],[0,0,1]])
    assert not receipt['unique_stationary_distribution']
    assert receipt['transient_states'] == [0]
    assert [row['distribution'] for row in receipt['closed_classes']] == [['0','1','0'],['0','0','1']]
    assert all(row['period'] == 1 for row in receipt['closed_classes'])


def test_stationary_distribution_matches_independent_symbolic_nullspace():
    sympy = pytest.importorskip('sympy')
    transition = [['1/2','1/3','1/6'],['1/4','1/2','1/4'],['1/3','1/3','1/3']]
    oracle = sympy.Matrix(transition).T-sympy.eye(3)
    vector = oracle.nullspace()[0]
    expected = vector/sum(vector)
    actual = stationary_classes(transition)['closed_classes'][0]['distribution']
    assert actual == [str(value) for value in expected]


@pytest.mark.parametrize('discount', ['0','1/2','9/10'])
def test_discounted_reward_matches_geometric_series(discount):
    discount = Fraction(discount)
    receipt = discounted_rewards([[1]],[3],discount)
    assert receipt['values'] == [str(3/(1-discount))]
    assert receipt['residuals'] == ['0']
    assert verify_discounted_rewards(receipt)
    paired = discounted_rewards([[0,1],[0,1]],[2,1],discount)
    assert Fraction(paired['values'][0]) == 2+discount/(1-discount)


@pytest.mark.parametrize('transition', [[],[[1,0]],[[1,0],[0,'1/2']],[[True]],[[1.0]],[[-1,2],[0,1]]])
def test_invalid_transition_matrices(transition):
    with pytest.raises(ValueError):
        hitting_statistics(transition,[0])
    with pytest.raises(ValueError):
        stationary_classes(transition)


@pytest.mark.parametrize('targets', [[],[True],[2],[0,0],['0']])
def test_invalid_targets(targets):
    with pytest.raises(ValueError):
        hitting_statistics([[1,0],[0,1]],targets)


@pytest.mark.parametrize('discount', [1,-1,'3/2',True,0.5])
def test_invalid_discount(discount):
    with pytest.raises(ValueError):
        discounted_rewards([[1]],[1],discount)


@pytest.mark.parametrize('factory,verifier,mutate', [
    (lambda: hitting_statistics([['1/2','1/2'],[0,1]],[1]),verify_hitting_statistics,
     lambda r:r['states'][0].update(conditional_mean='0')),
    (lambda: stationary_classes([[0,1],[1,0]]),verify_stationary_classes,
     lambda r:r['closed_classes'][0].update(period=1)),
    (lambda: discounted_rewards([[1]],[3],'1/2'),verify_discounted_rewards,
     lambda r:r.update(values=['0'])),
])
def test_rehashed_forgery_is_rejected(factory,verifier,mutate):
    receipt = deepcopy(factory())
    mutate(receipt)
    receipt['certificate_id'] = fingerprint({k:v for k,v in receipt.items() if k != 'certificate_id'})
    assert not verifier(receipt)
    assert not verifier({})
    assert not verifier(None)


def test_new_public_operations_replay_in_notebooks(tmp_path):
    from test_maturity_expansion import CATALOG_CASES
    names = ('polynomial_range','certified_integral','certified_function',
             'markov_hitting','markov_stationary','markov_rewards')
    notebook = Notebook('Certified analysis and finite chains')
    for name in names:
        notebook.append(CalculationSession().execute(name,**CATALOG_CASES[name]))
    assert notebook.replay() == len(names)
    path = tmp_path/'notebook.json'
    notebook.save(path)
    assert Notebook.load(path).to_data() == notebook.to_data()
