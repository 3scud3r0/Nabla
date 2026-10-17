"""Independent transform, complex-analysis, geometry and algebra oracles."""
import cmath
from fractions import Fraction
import math
import pytest

from nablamath.ops.spectral import fft,haar,convolve,spectral
from nablamath.ops.complex_analysis import contour_integral,conformal_map
from nablamath.ops.differential_geometry import differential_geometry
from nablamath.ops.abstract_algebra import primality,verify_pocklington,abstract_algebra
from nablamath.calc import CalculationSession,Notebook

NEW_CASES = {
    'spectral':{'kind':'fft','values':[1,0,0,0]},
    'complex_analysis':{'kind':'contour','source':'1','contour':[[0,0],[1,0],[1,1],[0,1]],'closed':True},
    'differential_geometry':{'metric':[[1,0],[0,1]]},
    'abstract_algebra':{'kind':'primality','n':97},
}


@pytest.mark.parametrize('size',[1,2,3,5,8,13,64,127])
def test_fft_matches_independent_direct_dft_and_inverse(size):
    values = [complex(math.sin(i),math.cos(2*i)) for i in range(size)]
    expected = [sum(value*cmath.exp(-2j*math.pi*k*i/size) for i,value in enumerate(values)) for k in range(size)]
    assert fft(values) == pytest.approx(expected,abs=2e-10)
    assert fft(fft(values),inverse=True) == pytest.approx(values,abs=2e-12)


def test_wavelet_energy_roundtrip_numpy_fft_and_convolution():
    values = [1.,2.,3.,4.,5.,6.,7.,8.]
    transformed = haar(values,levels=2)
    assert sum(abs(v)**2 for v in transformed) == pytest.approx(sum(v*v for v in values))
    assert haar(transformed,levels=2,inverse=True) == pytest.approx(values)
    assert convolve([1,2,3],[4,5]) == pytest.approx([4,13,22,15])
    np = pytest.importorskip('numpy')
    assert fft(values) == pytest.approx(np.fft.fft(values))
    pywt = pytest.importorskip('pywt')
    reference = pywt.wavedec(values,'haar',mode='periodization',level=2)
    assert transformed == pytest.approx(np.concatenate(reference))


def test_signal_filter_and_stft_have_independent_frequency_reference():
    values = [math.sin(2*math.pi*i/32)+.5*math.sin(2*math.pi*8*i/32) for i in range(32)]
    result = spectral('lowpass',values,sample_rate=32,cutoff=2)
    assert [v[0] for v in result['values']] == pytest.approx([math.sin(2*math.pi*i/32) for i in range(32)],abs=1e-12)
    stft = spectral('stft',values,window_size=8,hop=4)
    assert len(stft['frames']) == 7 and stft['times'] == list(range(0,25,4))
    with pytest.raises(ValueError):
        haar([1,2,3])


def test_contour_residue_theorem_and_conformal_derivative():
    vertices = [cmath.exp(2j*math.pi*k/16) for k in range(17)]
    result = contour_integral('1/z',vertices,tolerance=1e-9)
    assert complex(*result['value']) == pytest.approx(2j*math.pi,abs=1e-8)
    assert result['estimated_absolute_error'] < 1e-9
    assert contour_integral('z**2',[[0,0],[1,1]])['value'] == pytest.approx([-2/3,2/3])
    mapped = conformal_map([0,1],[[1,0],0,1,1])
    assert mapped['values'] == [[0.,0.],[.5,0.]] and mapped['derivatives'] == [[1.,0.],[.25,0.]]
    with pytest.raises(ValueError):
        contour_integral('__import__("os").system("echo bad")',[[0,0],[1,0]])
    with pytest.raises(ZeroDivisionError):
        conformal_map([-1],[1,0,1,1])


def test_metric_jet_polar_connection_flatness_and_lorentz_signature():
    # g=diag(1,r^2) at r=2, exact coordinate two-jet.
    first = [[[0,0],[0,4]],[[0,0],[0,0]]]
    second = [[[[0,0],[0,2]],[[0,0],[0,0]]],[[[0,0],[0,0]],[[0,0],[0,0]]]]
    result = differential_geometry([[1,0],[0,4]],first=first,second=second)
    assert result['christoffel'][0][1][1] == '-2'
    assert result['christoffel'][1][0][1] == '1/2'
    assert result['scalar_curvature'] == '0'
    assert differential_geometry([[-1,0],[0,1]])['scalar_curvature'] == '0'


def test_symbolic_sphere_has_known_scalar_curvature():
    pytest.importorskip('sympy')
    result = differential_geometry([[1,0],[0,'sin(theta)**2']],coordinates=['theta','phi'])
    assert result['scalar_curvature'] == '2'
    assert result['christoffel'][0][1][1] in {'-sin(2*theta)/2','-sin(theta)*cos(theta)'}
    with pytest.raises(ValueError):
        differential_geometry([[1,0],[0,'r**2']],coordinates=['r','phi'],point={'r':0,'phi':0})
    with pytest.raises(ValueError,match='Real metric'):
        differential_geometry([['I']],coordinates=['x'])
    with pytest.raises(ValueError,match='finite real'):
        differential_geometry([[1]],coordinates=['x'],point={'x':'sqrt(-1)'})


def test_large_prime_evidence_modular_arithmetic_and_galois_inverse():
    assert all(primality(n)['classification'] == 'neither_prime_nor_composite' for n in (0,1))
    known = 2**127-1
    result = primality(str(known),rounds=12)
    assert result['classification'] == 'probable_prime' and len(result['bases']) == 12
    assert primality(str(known*101))['classification'] == 'composite'
    assert abstract_algebra('modular_power',value=7,exponent=12345,modulus=1009)['value'] == str(pow(7,12345,1009))
    inverse = abstract_algebra('galois',prime=2,polynomial=[1,1,1],left=[0,1],field_operation='inverse')
    product = abstract_algebra('galois',prime=2,polynomial=[1,1,1],left=[0,1],right=inverse['coefficients'])
    assert product['coefficients'] == [1]
    certificate = {'n':65537,'factors':[{'prime':2,'exponent':16,'witness':3}]}
    assert verify_pocklington(certificate)
    certificate['n'] = 65535
    assert not verify_pocklington(certificate)


def test_all_added_operations_have_session_receipts_and_notebook_replay(tmp_path):
    notebook = Notebook('Advanced scientific layers')
    for operation,arguments in NEW_CASES.items():
        calculation = CalculationSession().execute(operation,**arguments)
        notebook.append(calculation)
        assert CalculationSession.replay_request(calculation.to_data()['request']).to_data() == calculation.to_data()
    path = tmp_path/'advanced.notebook.json'; notebook.save(path)
    assert Notebook.load(path).replay() == 4
