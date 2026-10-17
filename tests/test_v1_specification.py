"""Concrete class contracts from the five-module engineering specification."""
import io
import json
import math
from pathlib import Path
import pytest
pytest.importorskip('numpy')
pytest.importorskip('sympy')
pytest.importorskip('scipy')
import numpy as np

from nablamath.ops import abstract_algebra_crypto as a
from nablamath.ops import stochastic_and_information as s
from nablamath.calc import CalculationSession
from nablamath.artifacts.bundle import create_bundle


def test_jacobian_group_laws_match_affine_reference():
    curve=a.ExtensionCurve(a.GaloisField(11,(0,1)),1,0)
    points=[[x,y] for x in range(11) for y in range(11) if (y*y-x*x*x-x)%11==0]
    for point in points:
        projective=a.EllipticCurvePoint.affine(curve,point)
        assert projective.double().to_affine()==curve.add(point,point)
        for scalar in range(-3,7):assert projective.multiply(scalar).to_affine()==curve.multiply(scalar,point)
        for other in points:
            assert projective.add(a.EllipticCurvePoint.affine(curve,other)).to_affine()==curve.add(point,other)


def test_own_buchberger_agrees_with_independent_cas_normal_forms():
    import sympy as sp
    for generators in (['x*y-1','y*y-1'],['x*x+y*y-1','x-y'],['x*x','x*y','y*y'],['x','x-1']):
        ideal=a.PolynomialIdeal(generators,['x','y'],order='lex')
        result=ideal.basis();x,y=sp.symbols('x y')
        expected=sp.groebner(ideal.generators,x,y,order='lex',domain=sp.QQ)
        obtained=sp.groebner(result['_polynomials'],x,y,order='lex',domain=sp.QQ)
        assert list(obtained)==list(expected)
        assert result['s_criterion_verified']
    assert a.PolynomialIdeal(['x*x-1'],['x']).contains('x*x*x-x')['member']


def test_lie_generators_structure_and_bch_nilpotent_exactness():
    import sympy as sp
    algebra=a.LieAlgebra('so3')
    constants=algebra.structure_constants()['constants']
    assert constants[0][1][2]=='1'
    for kind in ('su2','su3'):
        algebra=a.LieAlgebra(kind)
        for matrix in algebra.basis:assert matrix.H==-matrix and sp.trace(matrix)==0
        assert algebra.structure_constants()['constants']
    x=sp.Matrix([[0,1,0],[0,0,0],[0,0,0]])
    y=sp.Matrix([[0,0,0],[0,0,1],[0,0,0]])
    z=a.MatrixExponentialBCH.bch(x,y)
    assert z.exp()==x.exp()*y.exp()


@pytest.mark.parametrize('kind',['BN254','BLS12-381'])
def test_standard_pairing_bilinearity_and_subgroup_validation(kind):
    pytest.importorskip('py_ecc')
    pairing=a.BilinearPairing(kind);backend=pairing.backend
    assert pairing.verify_product([{'sign':1},{'sign':-1}])['identity']
    value=backend.pairing(backend.G2,backend.G1)
    assert backend.pairing(backend.G2,backend.multiply(backend.G1,2))==value**2
    assert pairing.evaluate()['coefficients']==[int(v) for v in value.coeffs]
    with pytest.raises(ValueError):pairing.g1([0,0])


def test_ito_milstein_brownian_replay_and_noncommuting_rejection():
    calculus=s.ItoCalculus(['x'],['0'],[['x']],convention='stratonovich')
    assert calculus.lemma('x*x')['drift']=='2*x**2'
    assert calculus.ito_to_stratonovich()==['0']
    solver=s.SDESolver(['x'],['0'],[['1']])
    result=solver.solve([0],steps=4,seed=42,store_increments=True,method='milstein')
    replay=solver.solve([0],steps=4,increments=result['increments'],method='euler_maruyama')
    assert result['states']==replay['states']
    assert result['increments_sha256']==replay['increments_sha256']
    noncommuting=s.SDESolver(['x','y'],['0','0'],[['1','0'],['0','x']])
    with pytest.raises(ValueError,match='commuting'):noncommuting.solve([0,0],steps=4,method='milstein')
    assert solver.coupled_refinement([0],coarse_steps=4)['terminal_rms_difference']<1e-14


def test_variable_fokker_planck_stationary_and_information_classes():
    fp=s.FokkerPlanckPDE([-1,0,1],[0,0,0],[.5,.5,.5])
    result=fp.solve([0,1,0],duration=.5,steps=5)
    assert result['maximum_mass_drift']<1e-12
    assert min(min(row) for row in result['density'])>=0
    assert fp.stationary()['density']==pytest.approx([1/3]*3)
    assert s.InformationMetrics.cross_entropy([.5,.5],[.5,.5])['cross_entropy']==pytest.approx(1)
    assert s.CopulaEngine.gumbel([.2,.7],1)['cdf']==pytest.approx(.14)
    sample=s.CopulaEngine.sample_gaussian([[1,0],[0,1]],samples=100,seed=3)
    assert len(sample['uniforms'])==100
    assert len(s.CopulaEngine.empirical_dependence(sample['uniforms'])['kendall_tau'])==2


def test_template_ast_skip_literals_and_safe_dynamic_operations():
    from nablamath.publishing.living_papers_compiler import TypstTemplateEngine
    bundle=create_bundle([CalculationSession().execute('beta_binomial',successes=1,trials=2).to_data()])
    source='// #nabla-val("ignored")\n`#nabla-val("ignored")`\n#nabla-val("m")\n#nabla-calc("beta_binomial", {"successes": 2, "trials": 3})'
    engine=TypstTemplateEngine()
    nodes=engine.parse(source)
    assert [n.kind for n in nodes if n.kind!='literal']==['val','calc']
    result=engine.evaluate(source,bundle,bindings={'m':'/receipts/0/result/mean'})
    assert len(result['bundle']['receipts'])==2 and result['executed'][0]['operation']=='beta_binomial'
    assert '#text(' in result['source']


def test_xmp_encrypted_pdf_and_reactive_typst_compiler(tmp_path):
    pytest.importorskip('typst');pytest.importorskip('pypdf')
    from nablamath.publishing.living_papers_compiler import LivingPaperCompiler,VerifiablePDFWriter,ProvenanceBadgeGenerator
    bundle=create_bundle([CalculationSession().execute('beta_binomial',successes=1,trials=2).to_data()])
    template=tmp_path/'paper.typ';template.write_text('= Nabla scientific paper\nMean: #nabla-val("m")\n')
    compiler=LivingPaperCompiler(template,bundle,tmp_path/'paper.pdf',bindings={'m':'/receipts/0/result/mean'})
    built=compiler.build()
    assert VerifiablePDFWriter.inspect(built.pdf)['bundle']==bundle
    assert not compiler.build().changed
    encrypted=tmp_path/'encrypted.pdf'
    VerifiablePDFWriter.write(built.pdf,encrypted,bundle,password='fixture-password')
    assert VerifiablePDFWriter.inspect(encrypted,password='fixture-password')['encrypted']
    with pytest.raises(ValueError):VerifiablePDFWriter.inspect(encrypted,password='wrong')
    svg=ProvenanceBadgeGenerator.svg(bundle['content_id'],timestamp='2026-10-17T12:00:00+02:00')
    assert '2026-10-17T10:00:00Z' in svg
    with compiler.watch(delay=.05) as watch:
        # The initial build can be a cached unchanged revision; a new session
        # receipt forces the next revision without changing the original bundle.
        with compiler.session() as session:
            session.execute('beta_binomial',successes=0,trials=3)
        updated=watch.wait_for_build(timeout=30)
        assert updated.experiment_hash!=bundle['content_id']


def test_new_surfaces_glb_animation_and_embedded_three(tmp_path):
    from nablamath.graphics.spatial_engine_3d import SurfaceFactory,GLTFExporter,Standalone3DViewer,VectorFieldVisualizer
    sphere=SurfaceFactory.icosphere(subdivisions=1)
    assert sphere.topology()['closed_oriented_surface']
    assert sphere.topology()['euler_characteristic']==2
    assert sphere.signed_volume()>0
    ellipsoid=SurfaceFactory.ellipsoid([[1,0,0],[0,4,0],[0,0,9]],subdivisions=1)
    assert ellipsoid.signed_volume()==pytest.approx(sphere.signed_volume()/6)
    x=np.linspace(-1.5,1.5,7);grid=np.stack(np.meshgrid(x,x,x,indexing='ij'))
    implicit=SurfaceFactory.implicit(np.sum(grid*grid,axis=0),1,origin=(-1.5,)*3,spacing=(.5,)*3)
    assert implicit.surface_area()>5
    record=CalculationSession().execute('beta_binomial',successes=1,trials=2).to_data()
    frames=[sphere.vertices,tuple(tuple(1.1*v for v in p) for p in sphere.vertices)]
    exporter=GLTFExporter();data,binary=exporter.document(sphere,record,frames=frames,times=[0,1])
    assert data['animations'][0]['channels'][0]['target']['path']=='weights'
    assert data['buffers'][0]['byteLength']==len(binary)
    path=exporter.write(sphere,tmp_path/'animated.glb',audit_receipt=record,frames=frames,times=[0,1])
    assert path.read_bytes().startswith(b'glTF')
    html=Standalone3DViewer().source(sphere,record,frames=frames,times=[0,1])
    assert 'data:text/javascript;base64,' in html and 'OrbitControls' in html
    assert 'id="colormap"' in html and 'id="time"' in html
    stream=VectorFieldVisualizer.streamline(['-y','x','0'],[1,0,0],duration=math.pi/2,samples=10)
    assert stream['points'][-1]==pytest.approx([0,1,0],abs=1e-7)
    tube=VectorFieldVisualizer.tube(stream['points'])
    assert tube.surface_area()>0


def test_reed_solomon_and_ntt_new_discrete_algorithms():
    f=a.GaloisField(7,(0,1));code=a.ReedSolomonCode(f,list(range(7)),3)
    encoded=code.encode([1,2,3]);encoded[1]=[0];encoded[4]=[0]
    recovered=code.decode(encoded)
    assert recovered['decoded'] and recovered['message']==[[1],[2],[3]]
    assert recovered['error_positions']==[1,4]
    data=[1,2,3,4,5,6,7,8]
    transformed=a.number_theoretic_transform(data,17)['values']
    assert a.number_theoretic_transform(transformed,17,inverse=True)['values']==data
    result=a.negacyclic_convolution([1,2,3,4],[2,1,0,1],17)['coefficients']
    brute=[0]*4
    for i,x in enumerate([1,2,3,4]):
        for j,y in enumerate([2,1,0,1]):
            brute[(i+j)%4]+=x*y*(1 if i+j<4 else -1)
    assert result==[v%17 for v in brute]


def test_factorization_inseparability_and_weil_isogeny():
    f=a.GaloisField(3,(0,1));x=a.FieldPolynomial(f,[0,1])
    result=a.factor_field_polynomial((x+1)*(x+1)*(x*x+1))
    assert result['reconstruction_verified'] and sorted(v['multiplicity'] for v in result['factors'])==[1,2]
    inseparable=a.square_free_factorization((x+1)*(x+1)*(x+1))
    assert len(inseparable)==1 and inseparable[0][1]==3
    extension=a.GaloisField(11,(1,0,1));curve=a.ExtensionCurve(extension,1,0)
    p=[5,3];q=[[6,0],[0,3]]
    pair=a.weil_pairing(curve,p,q,3)
    assert pair!=extension.element(1) and pair**3==extension.element(1)
    assert a.weil_pairing(curve,q,p,3)==pair.inverse()
    isogeny=a.VeluIsogeny(curve,p,3)
    assert isogeny.evaluate(p) is None
    assert isogeny.evaluate(curve.multiply(2,q))==isogeny.codomain.multiply(2,isogeny.evaluate(q))


def test_surface_fem_and_relativistic_field_references():
    from nablamath.ops import advanced_calculus_manifold as m
    model=m.SurfaceFiniteElements([[0,0,0],[1,0,0],[1,1,0],[0,1,0]],[[0,1,2],[0,2,3]])
    assert model.gradient([0,1,1,0])==[[1.,0.,0.],[1.,0.,0.]]
    assert model.de_rham_incidence()['nilpotent']
    assert model.heat([1,0,0,0],steps=4)['maximum_mass_drift']<1e-12
    metric=[[-1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]];coords=['t','x','y','z']
    assert m.adm_decomposition(coords,metric)['reconstruction_verified']
    maxwell=m.maxwell_field_stress(coords,metric,['0','-2*t','0','0'])
    assert maxwell['stress_tensor'][0][0]=='2' and maxwell['bianchi_verified']
    assert m.scalar_field_stress(coords,metric,'t')['field_equation']=='0'
    assert m.perfect_fluid_stress(coords,metric,'3','1',['1','0','0','0'])['stress_tensor'][0][0]=='3'


def test_gp_gradients_transport_and_fisher_new_engines():
    for kernel in ('rbf','matern32','matern52'):
        gp=s.GaussianProcessRegressor([[0],[1]],[1,-1],kernel=kernel,noise=.01)
        gradient=gp.mean_gradient([[.3]])['gradient'][0][0]
        epsilon=1e-5
        derivative=(gp.predict([[.3+epsilon]])['mean'][0]-gp.predict([[.3-epsilon]])['mean'][0])/(2*epsilon)
        assert gradient==pytest.approx(derivative,rel=1e-5)
    assert s.wasserstein_discrete_1d([0],[1],[2],[1])['distance']==pytest.approx(2)
    transport=s.sinkhorn_transport([[0,1],[1,0]],[.5,.5],[.5,.5])
    assert transport['converged'] and transport['maximum_marginal_residual']<1e-9
    assert s.StatisticalInformationGeometry.categorical([.5,.5])['fisher']==[[4.]]
    for family,param in [('clayton',2.),('gumbel',2.)]:
        sampled=s.copula_sample(family,2,samples=5000,parameter=param,seed=3)
        uniforms=np.asarray(sampled['uniforms'])
        assert uniforms.mean()==pytest.approx(.5,abs=.02)
        dependence=s.CopulaEngine.empirical_dependence(uniforms)
        expected=param/(param+2) if family=='clayton' else 1-1/param
        assert dependence['kendall_tau'][0][1]==pytest.approx(expected,abs=.04)
