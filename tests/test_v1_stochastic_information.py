"""Analytic references, conservation, positivity and statistical contracts."""
import math
import pytest
np = pytest.importorskip("numpy")
pytest.importorskip("scipy")
pytest.importorskip("sympy")
from nablamath.ops import stochastic_and_information as s


def test_stratonovich_geometric_brownian_conversion():
    result=s.stochastic_generator(['x'],['0'],[['x']],'x*x',convention='stratonovich')
    assert result['ito_drift']==['x/2']
    assert result['backward']=='2*x**2'
    assert result['fokker_planck']=='9*x**2/2'
    assert s.stochastic_generator(['x'],['0'],[['1']],'x*x')['fokker_planck']=='1'


def test_multivariate_generator_cross_diffusion():
    result=s.stochastic_generator(['x','y'],['0','0'],[['1'],['1']],'x*y')
    assert result['backward']=='1'
    assert result['fokker_planck']=='1'


def test_fokker_planck_mass_positivity_and_stationarity():
    result=s.fokker_planck_1d([0,0,1,0,0],.1,.2,1,.1,100)
    assert result['mass']==pytest.approx(1,abs=1e-13)
    assert result['minimum']>=0
    steady=s.fokker_planck_1d([.2]*5,0,.2,1,.1,100)
    assert steady['density']==pytest.approx([.2]*5)


def test_gaussian_entropy_and_kl_closed_form():
    result=s.gaussian_information([0],[[1]],[1],[[2]])
    assert result['entropy_nats']==pytest.approx(.5*math.log(2*math.pi*math.e))
    assert result['kl_nats']==pytest.approx(.5*math.log(2))
    assert s.gaussian_information([1,2],[[2,1],[1,2]],[1,2],[[2,1],[1,2]])['kl_nats']==pytest.approx(0,abs=1e-14)


def test_discrete_entropy_kl_and_support():
    assert s.discrete_information([.5,.5],[.5,.5])['entropy']==pytest.approx(1)
    assert s.discrete_information([1,0],[0,1])['kl_infinite']
    assert s.discrete_information([1,0],[0,1])['kl'] is None
    assert s.discrete_information([.5,.5],[.25,.75])['kl']>0


def test_channel_capacity_binary_symmetric_and_erasure():
    result=s.channel_capacity([[.9,.1],[.1,.9]])
    entropy=-.1*math.log2(.1)-.9*math.log2(.9)
    assert result['converged'] and result['capacity_bits']==pytest.approx(1-entropy)
    assert s.channel_capacity([[1,0],[0,1]])['capacity_bits']==pytest.approx(1)
    assert s.channel_capacity([[.7,.3],[.7,.3]])['capacity_bits']==pytest.approx(0,abs=1e-14)
    result=s.channel_capacity([[1,0],[.5,.5]],max_iterations=1)
    assert not result['converged'] and result['upper_bits']>=result['capacity_bits']


def test_gp_exact_interpolation_and_schur_covariance():
    result=s.gaussian_process([[0],[1]],[1,-1],[[0],[1]],noise=0)
    assert result['mean']==pytest.approx([1,-1],abs=1e-12)
    assert np.max(np.abs(result['covariance']))<1e-12
    result=s.gaussian_process([[0]],[2],[[1]],noise=.1)
    assert result['mean'][0]==pytest.approx(2*math.exp(-.5)/1.1)
    assert result['covariance'][0][0]==pytest.approx(1-math.exp(-1)/1.1)


def test_copula_independence_and_clayton_analytic():
    assert s.gaussian_copula([.2,.7],[[1,0],[0,1]])['log_density']==pytest.approx(0)
    assert s.clayton_copula([.2,.7],0)['cdf']==pytest.approx(.14)
    assert s.clayton_copula([.2,.7],1e-15)['cdf']==pytest.approx(.14)
    result=s.clayton_copula([.5,.5],1)
    assert result['cdf']==pytest.approx(1/3)
    assert math.exp(result['log_density'])==pytest.approx(32/27)
    assert math.isfinite(s.clayton_copula([1e-200,.8],100)['log_density'])


@pytest.mark.parametrize('call',[
    lambda:s.fokker_planck_1d([1,0],0,1,1,1,1),
    lambda:s.fokker_planck_1d([-1,2],0,1,1,.1,1),
    lambda:s.gaussian_information([0],[[0]]),
    lambda:s.gaussian_information([0],[[1]],reference_mean=[0]),
    lambda:s.discrete_information([1,1]),lambda:s.discrete_information([1],base=1),
    lambda:s.channel_capacity([[1,1]]),
    lambda:s.gaussian_process([[0],[0]],[1,2],[[1]],noise=0),
    lambda:s.gaussian_copula([0,.5],[[1,0],[0,1]]),
    lambda:s.gaussian_copula([.2,.5],[[1,2],[2,1]]),
    lambda:s.clayton_copula([.5],-1),
    lambda:s.stochastic_generator(['x'],[0],[[1]],'x',convention='other'),
])
def test_rejections(call):
    with pytest.raises(ValueError):call()


def test_information_receipt():
    from nablamath.calc.receipt import verify_receipt
    result=s.calculate('channel',channel=[[1,0],[0,1]])
    assert verify_receipt(result.to_data())
