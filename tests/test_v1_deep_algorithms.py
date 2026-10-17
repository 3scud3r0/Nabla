"""Independent identities and adversarial checks for the dense v1 modules."""
import itertools
import json
import math
import pytest
np = pytest.importorskip('numpy')
sp = pytest.importorskip('sympy')
pytest.importorskip('scipy')
from nablamath.ops import advanced_calculus_manifold as g
from nablamath.ops import abstract_algebra_crypto as a
from nablamath.ops import stochastic_and_information as s
from nablamath.graphics import spatial_engine_3d as v
from nablamath.calc import CalculationSession


@pytest.fixture
def triangle():
    return v.MeshData(((0.,0.,0.),(1.,0.,0.),(0.,1.,0.)),((0,1,2),),(0.,1.,2.))


@pytest.fixture
def receipt():
    return CalculationSession().execute('beta_binomial',successes=2,trials=3).to_data()


def test_cartan_polar_frame_and_minkowski_spin():
    frame=g.OrthonormalFrame(['r','theta'],[[1,0],[0,'r*r']],[[1,0],[0,'1/r']],[1,1])
    assert frame.cartan_torsion()['torsion_free']
    assert frame.metric_skew_symmetry()['verified']
    assert all(value=='0' for matrix in frame.curvature_forms()['components'].values() for row in matrix for value in row)
    tetrad=g.OrthonormalFrame(['t','x','y','z'],np.diag([-1,1,1,1]).tolist(),np.eye(4,dtype=int).tolist(),[-1,1,1,1])
    assert g.SpinConnection(tetrad).compatibility()['verified']
    with pytest.raises(ValueError):g.OrthonormalFrame(['x','y'],[[1,0],[0,1]],[[2,0],[0,1]],[1,1])


def test_symplectic_pullback_hamiltonian_invariance():
    geometry=g.SymplecticGeometry(['q','p'],[[0,-1],[1,0]])
    assert geometry.hamiltonian_vector('(q*q+p*p)/2')['components']==['p','-q']
    assert geometry.bracket('q','p')==1
    assert geometry.preserves(['p','-q'])['preserves_two_form']
    transformed=geometry.pullback(['x','y'],['2*x','y/2'])
    assert transformed.matrix==geometry.matrix
    with pytest.raises(ValueError):g.SymplecticGeometry(['q','p'],[[0,0],[0,0]])


def test_symplectic_midpoint_energy_and_dirac_constraints():
    system=g.HamiltonianSystem('(q*q+p*p)/2',['q'],['p'])
    flow=system.midpoint([1.,0.],duration=2.,steps=40)
    assert flow['maximum_energy_drift']<1e-10
    assert flow['maximum_symplectic_residual']<1e-12
    assert system.liouville_identity()['zero']
    assert system.dirac_bracket('q','p',['q','p'])['bracket']=='0'


@pytest.mark.parametrize('prime,precision,value',[(3,8,3),(5,6,10),(2,9,4)])
def test_padic_exp_log_exact_finite_precision(prime,precision,value):
    x=a.PadicInteger(prime,precision,value)
    assert x.exponential().logarithm().residue==x.residue
    unit=a.PadicInteger(prime,precision,prime+1)
    assert (unit*unit.inverse()).residue==1
    lift=unit.teichmuller()
    assert pow(lift.residue,prime,lift.modulus)==lift.residue


def test_shamir_threshold_reconstruction_and_inconsistent_extra_share():
    field=a.GaloisField(101,(0,1));scheme=a.ShamirSecretSharing(field,3)
    shares=scheme.split(42,[7,13],[1,2,3,4,5])
    for subset in itertools.combinations(shares,3):assert scheme.recover(subset)==field.element(42)
    assert sum((weight*y for weight,(_,y) in zip(a.lagrange_weights_at_zero(field,[1,2,3]),shares)),field.element(0))==field.element(42)
    with pytest.raises(ValueError):scheme.recover([*shares[:3],(shares[3][0],shares[3][1]+1)])
    with pytest.raises(ValueError):scheme.split(1,[1,2],[1,1,2])
    with pytest.raises(ValueError):a.FieldElement(field,[1])


def test_lll_and_hensel_certificates():
    basis=[[1,1,1],[-1,0,2],[3,5,6]]
    reduced=a.IntegerLattice(basis).lll()
    transform=sp.Matrix(reduced['unimodular_transform'])
    assert transform*sp.Matrix(basis)==sp.Matrix(reduced['basis'])
    assert abs(transform.det())==1 and reduced['lovasz_verified']
    lifted=a.hensel_lift_root([-2,0,1],7,3,8)
    assert (lifted['root']**2-2)%7**8==0


def test_characteristic_function_exact_symmetry_and_entropy_power():
    result=s.empirical_characteristic_function([-1,1],[-1,0,1])
    assert result['imaginary']==pytest.approx([0,0,0],abs=1e-15)
    assert result['real']==pytest.approx([math.cos(1),1,math.cos(1)])
    weighted=s.empirical_characteristic_function([-1,1],[math.pi/2],weights=[.25,.75])
    assert weighted['imaginary_mean_variance']==pytest.approx([1.25])
    assert s.entropy_power([[4,0],[0,9]])['entropy_power']==pytest.approx(6)
    with pytest.raises(ValueError):s.empirical_characteristic_function([0,1],[0],weights=[1,1])


def test_exact_ctmc_hitting_and_transition():
    chain=s.ContinuousTimeMarkovChain([[-2,2],[0,0]])
    first=chain.hitting([1])['states'][0]
    assert first['hitting_probability']=='1' and first['conditional_mean']=='1/2'
    assert first['conditional_variance']=='1/4'
    transition=chain.transition(1)
    matrix=np.asarray(transition['transition'])
    assert matrix[0,0]==pytest.approx(math.exp(-2))
    assert matrix.sum(axis=1)==pytest.approx([1,1])


def test_survival_ties_and_permutation_exchangeability():
    result=s.SurvivalAnalysis.kaplan_meier([1,2,2,3],[1,1,0,1])
    rows=result['table']
    assert [r['survival'] for r in rows]==pytest.approx([.75,.5,0])
    exact=s.permutation_mean_test([1,2],[3,4],method='exact')
    assert exact['p_value']==pytest.approx(1/3)
    boot=s.bootstrap_interval([1,2,3,4,5],replicates=1000,seed=7)
    assert boot==s.bootstrap_interval([1,2,3,4,5],replicates=1000,seed=7)


def test_gaussian_conditioning_mixture_and_transport():
    result=s.conditional_gaussian([0,0],[[1,.5],[.5,1]],[0],[2])
    assert np.asarray(result['mean'])==pytest.approx([1])
    assert np.asarray(result['covariance'])==pytest.approx(np.array([[.75]]))
    mixture=s.GaussianMixture([.5,.5],[[-2],[2]],[[[1]],[[1]]])
    assert np.asarray(mixture.responsibilities([[0]]))==pytest.approx(np.array([[.5,.5]]))
    assert np.asarray(mixture.moments()['covariance'])==pytest.approx(np.array([[5]]))
    distance=s.gaussian_wasserstein([0],[[1]],[3],[[4]])
    assert distance['squared_distance']==pytest.approx(10)


def test_bvh_barycentric_and_closest_points(triangle):
    hit=v.MeshBVH(triangle).intersect([.25,.25,2],[0,0,-1])
    assert hit is not None and hit.distance==pytest.approx(2)
    assert v.MeshBVH(triangle).interpolate_scalar(hit)==pytest.approx(.75)
    closest=v.MeshSampling.closest_points(triangle,[[.25,.25,2],[2,0,0]])
    assert closest[0]['distance']==pytest.approx(2)
    assert closest[0]['point']==pytest.approx([.25,.25,0])
    assert closest[1]['point']==pytest.approx([1,0,0])
    assert v.integrate_vertex_field(triangle,[0,1,2])['integral']==pytest.approx(.5)
    sample=v.MeshSampling.surface(triangle,10000,seed=4)
    assert np.asarray(sample['points']).mean(axis=0)==pytest.approx([1/3,1/3,0],abs=.006)
    assert np.asarray(sample['barycentric']).sum(axis=1)==pytest.approx(np.ones(10000))


def test_subdivision_clipping_and_scalar_contours(triangle):
    refined=v.MeshProcessor.loop_subdivide(triangle)
    assert len(refined.triangles)==4
    sphere=v.SurfaceFactory.icosphere(subdivisions=1)
    clipped=v.MeshClipper.clip(sphere,[0,0,1],.11,cap=True)
    assert clipped.topology()['closed_oriented_surface']
    assert min(p[2] for p in clipped.vertices)>=.11-1e-10
    contours=v.ScalarContours.extract(triangle,[.5])
    assert contours
    assert v.MeshSampling.sampled_distance(triangle,triangle,20)['sampled_hausdorff_lower_estimate']<1e-12


def test_volume_interpolation_hydrogen_and_camera():
    grid=np.indices((3,3,3)).sum(axis=0)
    volume=v.VolumeField(grid)
    assert volume.sample([[.2,.3,.4]])==pytest.approx([.9])
    assert volume.integral()['integral']==pytest.approx(24)
    with pytest.raises(ValueError):volume.sample([[3,0,0]])
    orbital=v.QuantumFieldVisualizer.hydrogen_orbital([[0,0,0]],1,0,0)
    assert orbital['density'][0]==pytest.approx(1/math.pi)
    path=v.CameraPath.orbit(samples=9)
    camera=path.sample([0,2.5,5])
    assert np.linalg.norm(camera['quaternions_xyzw'],axis=1)==pytest.approx([1,1,1])
    assert np.linalg.norm(camera['forward'],axis=1)==pytest.approx([1,1,1])


def test_timeline_and_spatial_artifact_tamper(triangle,receipt,tmp_path):
    frames=[triangle.vertices,(np.asarray(triangle.vertices)+[0,0,1]).tolist()]
    timeline=v.SceneTimeline(triangle,frames,[0,2],[receipt,receipt])
    assert np.asarray(timeline.sample(1)['mesh'].vertices)[:,2]==pytest.approx([.5]*3)
    assert np.asarray(timeline.velocity(1)['vectors'])[:,2]==pytest.approx([.5]*3)
    assert timeline.interpolation_quality()['minimum_area_estimate']==pytest.approx(.5)
    experiment=v.SpatialExperiment(triangle,[receipt],frames=frames,times=[0,2])
    destination=tmp_path/'spatial'
    experiment.build(destination)
    assert v.SpatialExperiment.verify(destination)
    inspected=v.GLTFInspector.inspect(destination/'scene.glb')
    assert inspected
    (destination/'mesh.json').write_text('{}')
    assert not v.SpatialExperiment.verify(destination)


def test_native_mathml_and_safe_publication_table():
    from nablamath.publishing.living_papers_compiler import ScientificEquation,equation_mathml,PublicationTable
    import xml.etree.ElementTree as ET
    markup=equation_mathml(ScientificEquation('sqrt(x)/(1+x*x)',['x']))
    assert ET.fromstring(markup).tag.endswith('math') and 'mfrac' in markup
    table=PublicationTable(['Label','Value'],[['=CMD()',1],['<tag>',3]],units=['','m'])
    assert "'=CMD()" in table.csv() and '&lt;tag&gt;' in table.html()
    assert table.column_summary('Value')['sample_variance']==2
    with pytest.raises(ValueError):PublicationTable(['x'],[[float('inf')]])
