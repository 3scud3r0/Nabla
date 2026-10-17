"""Independent chart identities, orientations and refusal contracts."""
import pytest
pytest.importorskip("sympy")
pytest.importorskip("numpy")
pytest.importorskip("scipy")
from nablamath.ops import advanced_calculus_manifold as m


def test_lie_bracket_and_antisymmetry():
    assert m.lie_bracket(['x','y'],['0','x'],['y','0'])['components']==['x','-y']
    assert m.lie_bracket(['x','y'],['y','0'],['0','x'])['components']==['-x','y']


def test_cartan_and_contraction():
    assert m.interior_product(['x','y'],['1','2'],{'0,1':'x'})=={'1':'x','0':'-2*x'}
    assert m.lie_derivative(['x','y'],['x','y'],{'0':'x','1':'y'})=={'0':'2*x','1':'2*y'}
    assert m.lie_derivative(['x'],['x'],{'':'x*x'})=={'':'2*x**2'}


def test_hodge_euclidean_and_lorentzian():
    assert m.hodge_star(['x','y'],[[1,0],[0,1]],{'0':'1'})['components']=={'1':'1'}
    assert m.hodge_star(['x','y'],[[1,0],[0,1]],{'1':'1'})['components']=={'0':'-1'}
    assert m.hodge_star(['t','x'],[[-1,0],[0,1]],{'0':'1'})['components']=={'1':'-1'}
    assert m.hodge_star(['x','y'],[[1,0],[0,1]],{'0':'1'},-1)['components']=={'1':'-1'}


def test_stokes_rectangle_and_three_cube():
    result=m.stokes_box(['x','y'],{'1':'x'},[[0,2],[0,3]])
    assert result['identity_verified'] and result['boundary']=='6' and result['interior']=='6'
    cube=m.stokes_box(['x','y','z'],{'1,2':'x','0,2':'-y','0,1':'z'},[[0,1]]*3)
    assert cube['identity_verified'] and cube['boundary']=='3'


def test_sphere_curvature_and_covariant_derivative():
    result=m.symbolic_metric([[1,0],[0,'sin(theta)**2']],['theta','phi'])
    assert result['scalar_curvature']=='2'
    result=m.covariant_derivative([[1,0],[0,1]],['x','y'],['x*x','x*y'])
    assert result['components']==[['2*x','0'],['y','x']]


def test_exterior_nilpotence_pullback_and_variation():
    form=m.exterior_derivative(['x','y','z'],{'0':'y*z','1':'x*z'})
    assert m.exterior_derivative(['x','y','z'],form)=={}
    assert m.pullback(['t'],['x','y'],['t','t*t'],{'1':'x'})=={'0':'2*t**2'}
    result=m.euler_lagrange_fields('(q_1*q_1-q_0*q_0)/2',['t'],['q'])
    assert result['equations']==['-q_0 - q_2']
    assert m.euler_lagrange_density('(u_d0*u_d0-u_d1*u_d1)/2',['t','x'],['u'])['equations']==['-u_d0d0 + u_d1d1']


def test_geodesic_straight_line():
    result=m.geodesic([[1,0],[0,1]],['x','y'],[0,0],[1,2],duration=1,steps=4)
    assert result['states'][-1]==pytest.approx([1,2,1,2])


@pytest.mark.parametrize('call',[
    lambda:m.hodge_star(['x'],[[0]],{'':'1'}),
    lambda:m.hodge_star(['x'],[[1]],{'':'1'},0),
    lambda:m.stokes_box(['x','y'],{'':'1'},[[0,1]]*2),
    lambda:m.stokes_box(['x'],{'':'x'},[[1,0]]),
    lambda:m.lie_bracket(['x'],['__import__("os")'],['1']),
    lambda:m.interior_product(['x'],[],{'0':'1'}),
])
def test_invalid_manifold_inputs(call):
    with pytest.raises(ValueError):call()


def test_manifold_receipt():
    from nablamath.calc.receipt import verify_receipt
    record=m.calculate('stokes',coordinates=['x','y'],components={'1':'x'},bounds=[[0,1],[0,1]])
    assert verify_receipt(record.to_data())
    assert record.to_data()['result']['result']['identity_verified']
