"""Independent reference identities for the newly authored mathematical engines."""
import pytest
pytest.importorskip('sympy')
pytest.importorskip('numpy')
pytest.importorskip('scipy')
import sympy as sp
from nablamath.ops import advanced_calculus_manifold as m
from nablamath.ops import abstract_algebra_crypto as a
from nablamath.ops import stochastic_and_information as s


def test_general_tensor_algebra_and_metric_compatibility():
    geometry=m.MetricTensor(['r','theta'],[[1,0],[0,'r*r']])
    tensor=m.TensorField.from_components(['r','theta'],[1,-1],[[1,0],[0,1]])
    assert tensor.contract(0,1).to_data()['components']=='2'
    assert tensor.permute([1,0]).variance==(-1,1)
    assert all(v==0 for v in geometry.covariant(tensor).entries)
    assert geometry.metric_compatibility()['compatible']
    assert geometry.laplace_beltrami('r*r')=='4'
    assert geometry.signature({'r':2,'theta':0})['kind']=='riemannian'
    assert geometry.killing_equations(['0','1'])['is_killing']
    assert m.ChristoffelSymbols(geometry).torsion()['zero']
    assert geometry.first_bianchi()['verified']


def test_sphere_einstein_bianchi_and_kretschmann():
    geometry=m.MetricTensor(['u','v'],[[1,0],[0,'sin(u)**2']])
    assert geometry.scalar_curvature==2
    assert geometry.sectional_curvature(['1','0'],['0','1'])['curvature']=='1'
    assert m.RiemannCurvature(geometry).kretschmann()=='4'
    assert m.RiemannCurvature(geometry).symmetries()['verified']
    assert m.EinsteinTensor(geometry).divergence()['zero']
    assert all(value=='0' for row in m.EinsteinTensor(geometry).components() for value in row)
    assert m.MetricTensor(['t','x'],[[-1,0],[0,1]]).signature({'t':0,'x':0})['kind']=='lorentzian'


def test_forms_simplex_and_hodge_laplacian():
    form=m.DifferentialForm(['x','y'],{'0':'x*y','1':'x*x'})
    assert form.nilpotence_check()['verified']
    assert m.DifferentialForm(['x','y'],{'':'x*x+y*y'}).hodge_laplacian([[1,0],[0,1]]).components=={'':'-4'}
    assert m.integrate_simplex(['x','y'],{'0,1':'1'},[[0,0],[1,0],[0,1]])['integral']=='1/2'
    assert m.stokes_simplex(['x','y'],{'1':'x'},[[0,0],[1,0],[0,1]])['identity_verified']
    assert m.integrate_simplex(['x','y'],{'0,1':'1'},[[0,0],[0,1],[1,0]])['integral']=='-1/2'


def test_noether_legendre_and_mechanical_trajectory():
    noether=m.noether_point_symmetry('(x_v*x_v+y_v*y_v)/2',['x','y'],['-y','x'])
    assert noether['is_symmetry'] and noether['off_shell_identity_verified']
    assert sp.expand(sp.sympify(noether['charge'])-(sp.Symbol('x')*sp.Symbol('y_v')-sp.Symbol('y')*sp.Symbol('x_v')))==0
    assert m.quadratic_legendre('(q_v*q_v-q*q)/2',['q'])['hamiltonian']=='q**2/2 + q_p**2/2'
    solver=m.EulerLagrangeSolver('(q_v*q_v-q*q)/2',['q'])
    result=solver.solve([1],[0],duration=sp.pi.evalf().__float__()/2,samples=5)
    assert result['states'][-1]==pytest.approx([0,-1],abs=1e-8)
    assert result['maximum_energy_drift']<1e-8


def test_flat_geodesics_jacobi_and_transport():
    metric=[[1,0],[0,1]];coords=['x','y']
    result=m.geodesic_flow(coords,metric,[0,0],[1,2],samples=3)
    assert result['states'][-1]==pytest.approx([1,2,1,2])
    assert m.exponential_map(coords,metric,[0,0],[2,3])['point']==pytest.approx([2,3])
    inverse=m.logarithm_map(coords,metric,[0,0],[2,3])
    assert inverse['converged'] and inverse['tangent']==pytest.approx([2,3])
    transported=m.parallel_transport_curve(coords,metric,['s','s*s'],[3,4],samples=3)
    assert transported['vectors'][-1]==pytest.approx([3,4])
    result=m.jacobi_field(coords,metric,[0,0],[1,0],[0,1],[0,2],samples=3)
    assert result['states'][-1][4:6]==pytest.approx([0,3])


def test_gauge_pure_gradient_curvature():
    gauge=m.gauge_transform(['x','y'],[[[0]],[[0]]],[['exp(x*y)']])
    assert gauge['connection']==[[['y']],[['x']]]
    assert m.connection_curvature(['x','y'],gauge['connection'])['components']=={'0,1':[['0']]}


def test_new_finite_polynomial_algorithms():
    f=a.GaloisField(3,(1,0,1));x=a.FieldPolynomial(f,[0,1])
    polynomial=x*x+1
    assert not polynomial.is_irreducible()  # x^2+1 splits over GF(9).
    dividend=(x+1)*(x+2)
    quotient,remainder=dividend.divmod(x+1)
    assert not remainder and quotient==x+2
    gcd_value,left,right=dividend.extended_gcd(x+1)
    assert left*dividend+right*(x+1)==gcd_value
    assert len(polynomial.roots())==2
    element=f.element([0,1])
    assert a.minimal_polynomial(f,element)==[1,0,1]
    assert a.field_trace(f,element)==f.element(0)
    assert a.field_norm(f,element)==f.element(1)
    assert len(a.frobenius_orbit(f,element))==2
    assert a.finite_field_logarithm(f,element,element**3)['exponent']==3
    result=a.finite_field_matrix([[1,1],[1,2]],f,rhs=[1,0])
    assert result['rank']==2 and result['consistent']
    solution=[f.element(v) for v in result['particular']]
    assert solution[0]+solution[1]==f.element(1)
    assert solution[0]+2*solution[1]==f.element(0)


def test_curve_references_encoding_and_discrete_log():
    assert a.tonelli_shanks(10,13)==6
    assert a.tonelli_shanks(2,13) is None
    count=a.count_curve_prime_field(11,1,0)
    assert count['points']==12
    curve=a.ExtensionCurve(a.GaloisField(11,(0,1)),1,0)
    assert a.curve_point_order(curve,[5,3])==3
    assert a.elliptic_discrete_log(curve,[5,3],curve.multiply(2,[5,3]),3)['exponent']==2
    encoded=a.sec1_compress(11,1,0,[5,3])
    assert a.sec1_decompress(11,1,0,encoded)==[5,3]


def test_new_information_gaussian_and_kalman_references():
    result=s.gaussian_channel_capacity([1,1],2)
    assert result['capacity_bits']==pytest.approx(1) and result['power']==pytest.approx([1,1])
    assert s.markov_entropy_rate([[.5,.5],[.5,.5]])['entropy_rate_bits']==pytest.approx(1)
    assert s.mutual_information([[.5,0],[0,.5]])['mutual_information']==pytest.approx(1)
    assert s.conditional_mutual_information([[[.5],[0]],[[0],[.5]]])['conditional_mutual_information']==pytest.approx(1)
    assert s.renyi_entropy([.5,.5],2)['entropy']==pytest.approx(1)
    assert s.jensen_shannon([1,0],[0,1])['divergence']==pytest.approx(1)
    transition=s.linear_sde_transition([[-1]],[[2]],1)
    assert transition['transition'][0][0]==pytest.approx(float(sp.exp(-1)))
    assert transition['covariance'][0][0]==pytest.approx(2*(1-float(sp.exp(-2))))
    result=s.kalman_filter([[1],[2]],[[1]],[[1]],[[0]],[[1]],[0],[[1]])
    assert result['filtered'][0]['mean']==pytest.approx([.5])
    assert result['filtered'][1]['mean']==pytest.approx([1])
    assert result['filtered'][1]['covariance'][0][0]==pytest.approx(1/3)
    smoothed=s.rts_smoother(result,[[1]])
    assert smoothed['smoothed'][0]['mean']==pytest.approx([1])


def test_exact_gaussian_process_samples_and_continuous_entropy():
    bridge=s.brownian_bridge(2,3,1,[0,.5,1],paths=3)
    assert all(row[0]==2 and row[-1]==3 for row in bridge['paths'])
    ou=s.ornstein_uhlenbeck(1,0,1,0,[0,.5,1])
    assert ou['paths'][0][-1]==pytest.approx(float(sp.exp(-1)))
    assert s.continuous_information('0','x',0,1)['entropy_nats']==pytest.approx(0)
