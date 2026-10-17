"""Independent small scientific oracles and receipt replay for the new catalog."""
import math
from copy import deepcopy
from fractions import Fraction
import pytest
from nablamath.calc import CalculationSession, Notebook
from nablamath.calc.receipt import receipt, verify_receipt
from nablamath.ops.autograd import differentiate_graph
from nablamath.ops.mcmc import metropolis_hastings, sample_normal
from nablamath.ops.tensor_math import tensor_operation
from nablamath.ops.bayesian_inference import beta_binomial
from nablamath.domain.bioinformatics import align_sequences, gc_content
from nablamath.domain.geospatial import haversine, to_web_mercator, from_web_mercator, ndvi
from nablamath.domain.quantum import simulate_circuit, apply_channel

CASES = {
    'tensor': {'kind':'matmul','values':[[1,2],[3,4]],'other':[[2],[1]]},
    'autograd': {'inputs':{'x':3},'nodes':[{'op':'input','name':'x'},{'op':'multiply','args':[0,0]}],'output':1},
    'beta_binomial': {'successes':2,'trials':3},
    'mcmc_normal': {'mean':0,'standard_deviation':1,'samples':20,'seed':17},
    'sequence_align': {'first':'ACGT','second':'AGT'},
    'geo_distance': {'first':[0,0],'second':[90,0]},
    'quantum_circuit': {'qubits':2,'gates':[{'gate':'H','target':0},{'gate':'CX','control':0,'target':1}], 'shots':20,'seed':9},
}


def test_all_new_operations_replay_and_snapshot(tmp_path):
    notebook = Notebook('Scientific ecosystem')
    for operation,arguments in CASES.items():
        calculation = CalculationSession().execute(operation,**arguments)
        data = calculation.to_data()
        assert verify_receipt(data)
        notebook.append(calculation)
        corrupted = deepcopy(data); corrupted['result'] = None
        assert not verify_receipt(corrupted)
    path = tmp_path/'notebook.json'; notebook.save(path)
    assert Notebook.load(path).replay() == len(CASES)


def test_tensor_broadcast_matmul_and_budget():
    assert tensor_operation('multiply',[[1],[2]],other=[3,4])['values'] == [[3,4],[6,8]]
    assert tensor_operation('matmul',[[1,2],[3,4]],other=[[2],[1]])['values'] == [[4],[10]]
    assert tensor_operation('sum',[[1,2],[3,4]],axis=0)['values'] == [4,6]
    assert tensor_operation('transpose',[[1,2],[3,4]])['values'] == [[1,3],[2,4]]
    with pytest.raises(ValueError,match='Broadcast'):
        tensor_operation('add',[[1]]*101,other=[1]*100)
    with pytest.raises(ValueError):
        tensor_operation('reshape',[1,2],shape=[3])


def test_shared_dynamic_graph_and_malformed_references():
    # f(x,y) = x*x + x*y, df/dx=2x+y, df/dy=x.
    nodes = [{'op':'input','name':'x'},{'op':'input','name':'y'},
             {'op':'multiply','args':[0,0]},{'op':'multiply','args':[0,1]},
             {'op':'add','args':[2,3]}]
    result = differentiate_graph(nodes,{'x':3,'y':4},4)
    assert result['value'] == 21 and result['gradient'] == {'x':10,'y':3}
    with pytest.raises(ValueError):
        differentiate_graph([{'op':'add','args':[0,0]}],{'x':1},0)
    with pytest.raises(ValueError):
        differentiate_graph([{'op':'eval','value':'__import__("os")'}],{'x':1},0)


def test_seeded_mcmc_moments_and_rejection():
    result = sample_normal(2,1,samples=12000,burn_in=1000,seed=31)
    values = [v[0] for v in result['samples']]
    assert abs(sum(values)/len(values)-2) < 0.08
    assert abs(sum((v-2)**2 for v in values)/len(values)-1) < 0.12
    assert 0 < result['acceptance_rate'] < 1
    assert sample_normal(0,1,samples=10,seed=3) == sample_normal(0,1,samples=10,seed=3)
    with pytest.raises(ValueError):
        metropolis_hastings(lambda x: math.nan,[0])
    with pytest.raises(ValueError):
        sample_normal(0,0)
    with pytest.raises(ValueError):
        sample_normal(0,1,samples=True)


def test_conjugate_posterior_matches_closed_form():
    result = beta_binomial(3,5,alpha='1/2',beta='1/2')
    assert result['alpha'] == '7/2' and result['beta'] == '5/2'
    assert Fraction(result['mean']) == Fraction(7,12)
    assert Fraction(result['variance']) == Fraction(35,1008)
    with pytest.raises(ValueError):
        beta_binomial(6,5)


def test_sequence_alignment_and_gc():
    result = align_sequences('ACGT','AGT')
    assert result['score'] == 2 and result['first'] == 'ACGT' and result['second'] == 'A-GT'
    assert gc_content('ACGC') == 0.75
    assert align_sequences('AAA','AAA')['score'] == 3
    with pytest.raises(ValueError):
        align_sequences('AC-G','ACG')
    with pytest.raises(ValueError):
        gc_content('ANG')


def test_geospatial_oracles():
    assert haversine([0,0],[90,0]) == pytest.approx(6371008.8*math.pi/2)
    assert haversine([179,0],[-179,0]) == pytest.approx(6371008.8*math.pi/90)
    assert from_web_mercator(*to_web_mercator(-43.2,-22.9)) == pytest.approx((-43.2,-22.9))
    with pytest.raises(ValueError):
        to_web_mercator(0,90)
    np = pytest.importorskip('numpy')
    raster = ndvi([3,0,99],[1,0,1],nodata=99)
    assert raster[0] == .5 and np.isnan(raster[1:]).all()


def test_bell_density_trace_and_amplitude_damping():
    result = simulate_circuit(2,[{'gate':'H','target':0},{'gate':'CX','control':0,'target':1}],shots=100,seed=7,density_matrix=True)
    assert result['probabilities'] == pytest.approx([.5,0,0,.5])
    assert set(result['counts']) == {'00','11'} and sum(result['counts'].values()) == 100
    density = result['density_matrix']
    assert sum(density[i][i][0] for i in range(4)) == pytest.approx(1)
    np = pytest.importorskip('numpy')
    gamma = .25
    channel = [np.array([[1,0],[0,math.sqrt(1-gamma)]]),np.array([[0,math.sqrt(gamma)],[0,0]])]
    assert apply_channel([[0,0],[0,1]],channel) == pytest.approx(np.diag([.25,.75]))
    with pytest.raises(ValueError):
        apply_channel([[1,0],[0,-1]],channel)
    with pytest.raises(ValueError):
        simulate_circuit(1,[{'gate':'CX','control':0,'target':0}])


def test_lp_milp_and_nonlinear_independent_optima():
    pytest.importorskip('scipy')
    from nablamath.ops.convex_optimization import minimize_linear, minimize_nonlinear
    lp = minimize_linear([-1,-1],constraints=[[1,2]],upper=[3],bounds=[(0,2),(0,2)])
    assert lp['success'] and lp['value'] == pytest.approx(-2.5) and lp['max_constraint_violation'] < 1e-8
    mip = minimize_linear([-1,-1],constraints=[[1,2]],upper=[3],bounds=[(0,2),(0,2)],integrality=[1,1])
    assert mip['success'] and mip['value'] == pytest.approx(-2)
    infeasible = minimize_linear([1],constraints=[[1]],lower=[2],upper=[3],bounds=[(0,1)])
    assert not infeasible['success'] and infeasible['point'] is None
    nonlinear = minimize_nonlinear(lambda x: (x[0]-3)**2,[0])
    assert nonlinear['success'] and nonlinear['point'][0] == pytest.approx(3,abs=1e-5)


def test_observation_receipt_detaches_input_and_rejects_tampering():
    source = {'x':[1,2]}; record = receipt('external',source,3)
    source['x'][0] = 99
    assert record['inputs']['x'] == [1,2] and verify_receipt(record)
    assert record['replayable'] is False
    record['formal_proof'] = True
    assert not verify_receipt(record)


def test_rehashed_invalid_calculation_fails_closed():
    from nablamath.core.semantic_ir import fingerprint
    data = CalculationSession().evaluate('1').to_data()
    data['request']['arguments']['source'] = '1/0'
    body = {k:v for k,v in data.items() if k != 'content_id'}
    data['content_id'] = fingerprint(body)
    assert not verify_receipt(data)
