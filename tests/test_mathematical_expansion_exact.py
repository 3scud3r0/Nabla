"""Independent finite references for the advanced mathematical expansion.

Authored at the user's request. These tests were deliberately NOT executed as
part of this delivery; their existence is not validation evidence.
"""
from fractions import Fraction as F
import pytest


@pytest.fixture
def sp():
    return pytest.importorskip('sympy')


def test_natural_deduction_identity_and_undischarged_assumption():
    from nablamath.math.logic.proof_theory import check_proof
    proof={'rule':'imp_intro','assumption':'P','premises':[{'rule':'assumption','formula':'P'}]}
    assert check_proof(proof,expected=['imp','P','P'])['accepted']
    with pytest.raises(ValueError,match='Undischarged'):
        check_proof({'rule':'assumption','formula':'P'})
    with pytest.raises(ValueError,match='different'):
        check_proof(proof,expected=['imp','P','Q'])


def test_disjunction_elimination_checks_both_branches():
    from nablamath.math.logic.proof_theory import check_proof
    assumptions=[['or','P','Q'],['imp','P','R'],['imp','Q','R']]
    proof={'rule':'or_elim','premises':[{'rule':'assumption','formula':v} for v in assumptions]}
    assert check_proof(proof,assumptions,expected='R')['conclusion']=='R'
    proof['premises'][2]={'rule':'assumption','formula':'R'}
    with pytest.raises(ValueError):check_proof(proof,assumptions)


def test_constructive_curry_howard_and_capture():
    from nablamath.math.logic.constructive import type_check
    identity={'op':'lambda','name':'x','type':'P','body':{'op':'var','name':'x'}}
    assert type_check(identity,expected=['imp','P','P'])['accepted']
    with pytest.raises(ValueError,match='Unbound'):
        type_check({'op':'var','name':'x'})
    application={'op':'apply','function':identity,'argument':{'op':'var','name':'q'}}
    with pytest.raises(ValueError,match='mismatch'):type_check(application,{'q':'Q'})


def test_finite_model_quantifier_order():
    from nablamath.math.logic.model_theory import satisfies
    equal={'op':'equal','left':{'var':'x'},'right':{'var':'y'}}
    true={'op':'forall','variable':'x','body':{'op':'exists','variable':'y','body':equal}}
    false={'op':'exists','variable':'y','body':{'op':'forall','variable':'x','body':equal}}
    assert satisfies([0,1],{},true)['satisfied']
    assert not satisfies([0,1],{},false)['satisfied']
    with pytest.raises(ValueError,match='unbound'):satisfies([0,1],{},equal)


def test_hereditary_sets_and_infinite_progression():
    from nablamath.math.set_theory.axiomatic import finite_set_operations,axiom_instance
    from nablamath.math.set_theory.finite import IntegerProgression
    result=finite_set_operations([[],[[]]],[[[]],[]])
    assert result['equal'] and result['extensionality_verified']
    assert axiom_instance('foundation',[[[],[[]]]])['witness']==[]
    naturals=IntegerProgression(3,1,lower=0)
    assert naturals.prefix(4)==[1,4,7,10]
    assert naturals.contains(100) and not naturals.contains(-2)
    with pytest.raises(ValueError):axiom_instance('infinity',[[]])


def test_group_representations_decomposition_and_intertwiners(sp):
    from nablamath.math.algebra.representations import representation,intertwiners,decompose_character
    table=[[0,1],[1,0]];regular=[[[1,0],[0,1]],[[0,1],[1,0]]]
    assert representation(table,regular)['character']==['2','0']
    assert intertwiners(regular,regular)['dimension']==2
    irreps=[[[[1]],[[1]]],[[[1]],[[-1]]]]
    result=decompose_character(table,regular,irreps)
    assert result['multiplicities']==[1,1] and result['complete_irreducible_family']
    with pytest.raises(ValueError):representation(table,[[[1]],[[2]]])


def test_module_smith_and_rational_kernel(sp):
    from nablamath.math.algebra.modules import presentation,rational_homomorphism,finite_free_resolution
    assert presentation([[2,0],[0,6]])['torsion']==[2,6]
    assert presentation([],generators=3)['free_rank']==3
    assert rational_homomorphism([[1,2],[2,4]])['rank']==1
    assert finite_free_resolution([[1,2],[2,4]])['quotient_dimension']==1


def test_chain_exactness_homotopy_and_ext(sp):
    from nablamath.math.algebra.homological import chain_complex,cyclic_ext_tor,chain_homotopy
    assert chain_complex([1,2,1],[[[1,0]],[[0],[2]]])['exact']
    assert cyclic_ext_tor(6,9)['tor1_order']==3
    assert chain_homotopy([1,1],[[[1]]],[[[1]],[[1]]],[[[0]],[[0]]],[[[1]]])['chain_homotopic']
    with pytest.raises(ValueError,match='squared'):
        chain_complex([1,1,1],[[[1]],[[1]]])


def test_schemes_dimension_elimination_saturation_and_primary(sp):
    from nablamath.math.geometry.schemes import affine_scheme,eliminate,saturate,univariate_primary,projective_chart
    assert affine_scheme(['y**2-x**3'],['x','y'])['dimension']==1
    assert affine_scheme(['1'],['x'])['empty']
    eliminated=eliminate(['x-y','y*y-1'],['x','y'],['x'])['generators']
    assert eliminated==['y**2 - 1']
    assert saturate(['x*y'],['x','y'],'x')['generators']==['y']
    primary=univariate_primary('(x-1)**2*(x+2)')
    assert len(primary['primary_ideals'])==2 and primary['reduced'] is False
    assert projective_chart(['x*x+y*y-z*z'],['x','y','z'],2)['variables']==['x','y']
    with pytest.raises(ValueError,match='homogeneous'):projective_chart(['x+1'],['x','y'],0)


def test_cech_sections_and_circle_nerve(sp):
    from nablamath.math.geometry.sheaves import global_sections,cech_cohomology
    maps=[{'from':'A','to':'C','matrix':[[1]]},{'from':'B','to':'C','matrix':[[1]]}]
    assert global_sections({'A':1,'B':1,'C':1},maps)['dimension']==1
    result=cech_cohomology(2,{'0':'A','1':'B','0,1':'C'},{'A':1,'B':1,'C':1},maps)
    assert result['dimensions']==[1,0]


def test_exterior_algebra_pullback_and_stokes_reference(sp):
    from nablamath.math.geometry.differential_forms import exterior_derivative,wedge,pullback,integrate_box
    d=exterior_derivative(['x','y'],{'0':'x*y'})
    assert d=={'0,1':'-x'} and exterior_derivative(['x','y'],d)=={}
    assert wedge(['x','y'],{'0':'1'},{'1':'1'})=={'0,1':'1'}
    assert wedge(['x','y'],{'1':'1'},{'0':'1'})=={'0,1':'-1'}
    assert pullback(['u'],['x','y'],['u','u**2'],{'1':'x'})=={'0':'2*u**2'}
    # Integral of d(x dy) over the unit square equals boundary integral 1.
    assert integrate_box(['x','y'],exterior_derivative(['x','y'],{'1':'x'}),[[0,1],[0,1]])['integral']=='1'


def test_bundle_cocycles_sections_and_gauge(sp):
    from nablamath.math.geometry.fiber_bundles import verify_bundle,compatible_sections,gauge_connection
    transitions=[{'from':'A','to':'B','matrix':[[2]]},{'from':'B','to':'C','matrix':[[3]]},{'from':'A','to':'C','matrix':[[6]]}]
    assert verify_bundle(['A','B','C'],transitions,[['A','B','C']])['compatible']
    assert compatible_sections(transitions,{'A':[1],'B':[2],'C':[6]})
    assert gauge_connection(['x'],[[['0']]],[['exp(x)']])['connection']==[[['1']]]
    transitions[-1]['matrix']=[[5]]
    with pytest.raises(ValueError,match='Cocycle'):verify_bundle(['A','B','C'],transitions,[['A','B','C']])


def test_distributions_and_sobolev_exact_references(sp):
    from nablamath.math.analysis.distributions import dirac_pairing,derivative,regular_pairing
    from nablamath.math.analysis.sobolev import polynomial_norm
    assert dirac_pairing([{'weight':1,'point':0,'order':1}],'x+x**3')['pairing']=='-1'
    assert derivative([{'weight':1,'point':2,'order':0}],2)[0]['order']==2
    assert regular_pairing('x','x',0,1)['pairing']=='1/3'
    result=polynomial_norm('x*(1-x)',order=1)
    assert F(result['norm_squared'])==F(11,30) and result['zero_trace']
    assert result['poincare_constant']=='1/pi'


def test_topological_presentations_integral_torsion_and_cup(sp):
    from nablamath.math.topology.homotopy import fundamental_group
    from nablamath.math.topology.homology import integral_homology,cup_product
    circle=[[0,1],[1,2],[0,2]]
    assert fundamental_group(circle)['free_group_rank_if_graph']==1
    assert integral_homology(circle,1)=={'free_rank':1,'torsion':[]}
    assert integral_homology([[0,1,2]],1)=={'free_rank':0,'torsion':[]}
    rp2=[[0,1,2],[0,1,3],[0,2,4],[0,3,5],[0,4,5],[1,2,5],[1,3,4],[1,4,5],[2,3,4],[2,3,5]]
    assert integral_homology(rp2,1)=={'free_rank':0,'torsion':[2]}
    product=cup_product([[0,1,2]],1,[1,2,3],1,[4,5,6])
    # Vertex ordering is repr ordering: edges 01,02,12, so cup(012)=a01*b12.
    assert product['cochain']==['6']


def test_orders_universal_signature_and_free_algebra():
    from nablamath.ops.order_theory import heyting_algebra,boolean_bitset
    from nablamath.ops.universal_algebra import finite_signature,congruences,free_term_algebra
    assert heyting_algebra([[True,True],[False,True]])['implication']==[[1,1],[0,1]]
    assert boolean_bitset(3,3,5)['intersection']==1
    addition={'plus':{'arity':2,'values':[0,1,1,0]}}
    result=finite_signature(2,addition,identities=[[{'op':'plus','args':['x','y']},{'op':'plus','args':['y','x']}]])
    assert result['identities'][0]['holds']
    assert len(congruences([[0,1],[1,0]])['partitions'])==2
    assert len(free_term_algebra([[0,1],[1,0]],generators=1)['term_functions'])==2


def test_galois_extension_and_exact_spectral(sp):
    from nablamath.math.algebra.galois import polynomial_galois
    from nablamath.math.algebra.extensions import AlgebraicField,number_field
    from nablamath.math.linear_algebra.exact_spectral import algebraic_spectral
    assert polynomial_galois([-2,0,0,1])['order']==6
    field=AlgebraicField((1,1,0,0,1))
    assert field.alpha**4+field.alpha+1==field.element((0,))
    assert number_field(['sqrt(2)','sqrt(3)'])['degree']==4
    result=algebraic_spectral([[0,2],[1,0]])
    assert result['diagonalizable_over_algebraic_closure']
    assert sum(g['algebraic_multiplicity'] for g in result['eigenspaces'])==2


def test_lie_radicals_pbw_roots_and_k_groups(sp):
    from nablamath.ops.lie_algebra import lie_decomposition,pbw_reduce,root_system
    from nablamath.ops.k_theory import finite_field_higher_k,k_groups
    affine=[[[0,0],[0,1]],[[0,-1],[0,0]]]
    result=lie_decomposition(affine)
    assert len(result['solvable_radical_basis'])==2 and len(result['nilpotent_radical_basis'])==1 and result['levi_basis']==[]
    normal=pbw_reduce(affine,[1,0])['terms']
    assert {'word':[1],'coefficient':'-1'} in normal and {'word':[0,1],'coefficient':'1'} in normal
    assert len(root_system([[2,-1],[-1,2]])['roots'])==6
    assert finite_field_higher_k(3,3)['cyclic_order']==8
    assert k_groups('complex_sphere',2)['K0_rank']==2


def test_domain_preserving_integration_and_variation(sp):
    from nablamath.math.calculus.risch import integrate_elementary
    from nablamath.ops.variational_calculus import euler_lagrange_fields,euler_lagrange_density
    result=integrate_elementary('1/(1+x*x)',rational_only=True)
    assert result['derivative_identity_checked'] and 'atan' in result['primitive']
    assert integrate_elementary('x/x',rational_only=True)['original_domain_conditions']==['x != 0']
    ode=euler_lagrange_fields('(q_1**2-q_0**2)/2',['t'],['q'])['equations'][0]
    assert sp.expand(sp.sympify(ode)+sp.Symbol('q_0')+sp.Symbol('q_2'))==0
    pde=euler_lagrange_density('(u_d0**2+u_d1**2)/2',['x','y'],['u'])['equations'][0]
    assert sp.expand(sp.sympify(pde)+sp.Symbol('u_d0d0')+sp.Symbol('u_d1d1'))==0


def test_radon_nikodym_ito_and_linear_duality(sp):
    from nablamath.ops.measure_theory import radon_nikodym
    from nablamath.math.probability.ito import multivariate_ito
    from nablamath.ops.convex_optimization import verify_linear_certificate
    assert radon_nikodym([1,2,0],[3,4,0])['density']==[F(3),F(2),F(0)]
    with pytest.raises(ValueError,match='absolutely'):radon_nikodym([0],[1])
    ito=multivariate_ito('x*x+y*y',['0','0'],[['1','0'],['0','1']],['x','y'])
    assert ito['dt']=='2'
    good=verify_linear_certificate([1],[[1]],[2],[2],[1])
    bad=verify_linear_certificate([1],[[1]],[2],[3],[1])
    assert good['optimal'] and not bad['optimal'] and bad['duality_gap']=='1'


def test_presented_categories_and_finite_adjunction():
    from nablamath.math.category_theory.categories import PresentedCategory,Morphism,discrete_category
    from nablamath.math.category_theory.functors import identity_functor,adjunction
    category=PresentedCategory(('A',),(Morphism('a','A','A'),),((('a','a'),('a',)),))
    assert category.equal(['a','a','a'],['a'])['equal']
    assert category.compose(category.identity('A'),['a'])=={'source':'A','arrows':['a']}
    inverse=PresentedCategory(('A',),(Morphism('a','A','A'),Morphism('b','A','A')),((('a','b'),{'source':'A','arrows':[]}),))
    assert inverse.equal(['a','b'],inverse.identity('A'))['equal']
    discrete=discrete_category(('A','B'));identity=identity_functor(discrete)
    result=adjunction(identity,identity,discrete.identities,discrete.identities)
    assert result['adjunction'] and result['equivalence']


def test_elliptic_rational_addition_and_degree_two_isogeny():
    from nablamath.math.number_theory.elliptic_curves import EllipticCurveQ,two_isogeny
    curve=EllipticCurveQ(-2,0)
    assert curve.contains([2,2]) and curve.add([2,2],[2,-2]) is None
    assert two_isogeny(0,-2,[2,2])['point']==['1','3']


def test_permutation_group_uses_generator_representation(sp):
    from nablamath.math.algebra.groups import permutation_group
    group=permutation_group([[1,0,2],[1,2,0]])
    assert group['order']==6 and group['solvable'] and not group['abelian']


def test_continuous_measure_laplace_and_mobius_poles(sp):
    from nablamath.ops.measure_theory import continuous_integral
    from nablamath.ops.integral_transforms import symbolic_transform
    from nablamath.ops.complex_analysis import meromorphic_analysis
    assert continuous_integral('2*x','x',0,1)['integral']=='2/3'
    transform=symbolic_transform('laplace','1')
    assert transform['expression']=='1/s' and transform['evaluated']
    assert meromorphic_analysis('1/z')['residue']=='1'


def test_zero_dimensional_radical_and_primary_decomposition(sp):
    from nablamath.math.geometry.schemes import zero_dimensional_radical,zero_dimensional_primary
    radical=zero_dimensional_radical(['x*x','y'],['x','y'])
    assert radical['generators']==['x','y'] and radical['original_quotient_dimension']==2
    points=['x*y','x*x-x','y*y-y']
    decomposition=zero_dimensional_primary(points,['x','y'])
    assert len(decomposition['primary_ideals'])==3
    with pytest.raises(ValueError,match='Zero-dimensional'):zero_dimensional_radical(['x*y'],['x','y'])


def test_rational_cohomology_and_cup_class(sp):
    from nablamath.math.topology.homology import cohomology_basis,cup_class
    circle=[[0,1],[1,2],[0,2]]
    assert cohomology_basis(circle,1)['dimension']==1
    assert cup_class(circle,0,[1,1,1],1,[1,0,0])['coefficient_field']=='Q'
    with pytest.raises(ValueError,match='cocycles'):
        cup_class([[0,1,2]],1,[1,0,0],0,[1,1,1])


def test_integer_fragment_distinguishes_integer_and_real_solutions(sp):
    pytest.importorskip('z3')
    from nablamath.math.logic.model_theory import decide_linear_integers
    goal={'left':'2*x','relation':'ne','right':'1'}
    assert decide_linear_integers(goal,['x'])['status']=='valid_in_fragment'
    refuted=decide_linear_integers({'left':'x','relation':'gt','right':'0'},['x'])
    assert refuted['status']=='counterexample' and refuted['witness']['x']<=0
    with pytest.raises(ValueError,match='Nonlinear'):
        decide_linear_integers({'left':'x*x','relation':'ge','right':'0'},['x'])
