"""Independent finite oracles for the added MSC computational profiles."""
from fractions import Fraction as F
import cmath
import importlib
import json
import math
from pathlib import Path
import random
import pytest

from nablamath.calc import CalculationSession,Notebook
from nablamath.ops.area_catalog import OPERATIONS

CASES=json.loads((Path(__file__).resolve().parents[1]/'examples/science/catalog_cases.json').read_text())


def test_all_63_major_codes_have_honest_inspectable_profiles():
    from nablamath.math.coverage import coverage,classification
    report=coverage();rows=report['classifications']
    assert len(rows)==63 and len({row['code'] for row in rows})==63
    assert {row['operation'] for row in rows if row['operation']}==set(OPERATIONS)
    assert report['scientific_completion_established'] is False
    assert all(row['entire_subject_implemented'] is False for row in rows)
    root=Path(__file__).resolve().parents[1]
    assert all((root/row['source']).is_file() for row in rows)
    assert classification('01')['coverage']=='documentary_only'
    assert classification('28')['operation']=='measure_theory'
    report['classifications'].clear()
    assert len(coverage()['classifications'])==63


@pytest.mark.parametrize('operation',sorted(OPERATIONS))
def test_each_new_area_has_a_receipt_closed_schema_and_notebook_replay(operation):
    from nablamath.calc.receipt import verify_receipt
    from nablamath.ai.agent_tools import tool_schemas
    calculation=CalculationSession().execute(operation,**CASES[operation])
    assert verify_receipt(calculation.to_data())
    notebook=Notebook(operation);notebook.append(calculation);assert notebook.replay()==1
    module=importlib.import_module('nablamath.ops.'+operation)
    assert module.calculate(**CASES[operation]).to_data()==calculation.to_data()
    jsonschema=pytest.importorskip('jsonschema')
    schema=next(row['inputSchema'] for row in tool_schemas() if row['name']==operation)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(CASES[operation])


def test_lattice_and_congruence_against_finite_definitions():
    from nablamath.ops.order_theory import order_theory
    from nablamath.ops.universal_algebra import universal_algebra
    relation=[[i==j or i==0 or j==4 for j in range(5)] for i in range(5)]
    result=order_theory(relation)
    assert result['is_lattice'] and result['joins'][1][2]==4 and result['meets'][1][2]==0
    assert len(result['covers'])==6
    with pytest.raises(ValueError,match='transitive'):
        order_theory([[True,True,False],[False,True,True],[False,False,True]])
    table=[[(i+j)%4 for j in range(4)] for i in range(4)]
    result=universal_algebra([table],generators=[1],partition=[0,1,0,1])
    assert result['generated_subalgebra']==[0,1,2,3]
    assert result['quotient_tables']==[[[0,1],[1,0]]]
    rejected=universal_algebra([table],partition=[0,0,1,1])
    assert rejected['congruence'] is False and rejected['counterexample']


def test_affine_scheme_cusp_and_polynomial_parser_rejects_code():
    from nablamath.ops.algebraic_geometry import algebraic_geometry
    singular=algebraic_geometry(['y**2-x**3'],['x','y'],[0,0])
    regular=algebraic_geometry(['y**2-x**3'],['x','y'],[1,1])
    assert singular['tangent_dimension']==2 and regular['tangent_dimension']==1
    assert regular['jacobian']==[[F(-3),F(2)]]
    assert sum(a*b for a,b in zip(regular['jacobian'][0],regular['tangent_basis'][0]))==0
    assert algebraic_geometry(['y-x*x'],['x','y'],[0,1])['tangent_basis'] is None
    for source in ['__import__("os")','x.__class__','x**1000','1/(x+1)']:
        with pytest.raises(ValueError):algebraic_geometry([source],['x'],[0])


def test_sl2_jacobi_killing_and_exact_bracket():
    from nablamath.ops.lie_algebra import lie_algebra
    c=[[[0,0,0],[0,2,0],[0,0,-2]],[[0,-2,0],[0,0,0],[1,0,0]],[[0,0,2],[-1,0,0],[0,0,0]]]
    result=lie_algebra(c,left=[0,1,0],right=[0,0,1])
    assert result['bracket']==[1,0,0] and result['center_basis']==[]
    assert result['killing_form']==[[8,0,0],[0,0,4],[0,4,0]]
    assert result['derived_dimension']==3 and result['semisimple_over_characteristic_zero']
    c[0][1][1]=3;c[1][0][1]=-3
    with pytest.raises(ValueError,match='Jacobi'):lie_algebra(c)


def test_graph_k0_sinks_loops_and_exact_integer_relations():
    from nablamath.ops.k_theory import k_theory
    assert k_theory([[0]])['K0_free_rank']==1
    assert k_theory([[1]])['K0_free_rank']==1
    assert k_theory([[2]])['K0_torsion']==[] and k_theory([[2]])['K0_free_rank']==0
    assert k_theory([[3]])['K0_torsion']==[2]
    assert k_theory([[0,1],[0,0]])['K0_free_rank']==1


def test_k0_determinantal_divisors_match_independent_smith_normal_form():
    sp=pytest.importorskip('sympy')
    from sympy.matrices.normalforms import smith_normal_form
    from nablamath.ops.k_theory import k_theory
    rng=random.Random(127)
    for n in (2,3,4):
        for _ in range(6):
            adjacency=[[rng.randrange(4) for _ in range(n)] for _ in range(n)]
            result=k_theory(adjacency)
            diagonal=smith_normal_form(sp.Matrix(result['presentation']),domain=sp.ZZ)
            reference=[abs(int(diagonal[i,i])) for i in range(min(diagonal.shape)) if diagonal[i,i]]
            assert result['invariant_factors']==reference


def test_finite_measure_conditioning_tower_and_null_atoms():
    from nablamath.ops.measure_theory import measure_theory
    result=measure_theory([1,0,3],[2,999,4],partition=[0,1,0])
    assert result['conditional_expectation']==[F(7,2),0,F(7,2)]
    assert result['integral']==14 and result['tower_integral_verified']
    assert result['sigma_algebra_size']==4


def test_so3_known_quarter_turn_and_small_angle():
    from nablamath.ops.lie_groups import lie_groups
    result=lie_groups([0,0,math.pi/2])
    assert [row[0] for row in result['rotation']]==pytest.approx([0,1,0],abs=1e-15)
    assert result['quaternion_wxyz']==pytest.approx([math.sqrt(.5),0,0,math.sqrt(.5)])
    assert lie_groups([1e-12,0,0])['orthogonality_residual']<1e-15


def test_dirichlet_chain_harmonicity_and_missing_anchor_refusal():
    from nablamath.ops.potential_theory import potential_theory
    c=[[0,1,0],[1,0,1],[0,1,0]]
    result=potential_theory(c,{'0':0,'2':1})
    assert result['values']==[0,F(1,2),1] and result['energy']==F(1,2)
    assert result['interior_residuals']==[0] and result['maximum_principle_verified']
    with pytest.raises(ValueError,match='anchor'):potential_theory([[0,0],[0,0]],{'0':0})


def test_gamma_beta_error_functions_and_recurrence():
    from nablamath.ops.special_functions import special_functions
    from nablamath.ops.difference_equations import difference_equations
    assert special_functions('gamma',5)['value']==24
    assert special_functions('gamma',-.5)['value']==pytest.approx(-2*math.sqrt(math.pi))
    assert special_functions('beta',1,y=2)['value']==pytest.approx(.5)
    assert special_functions('erf',1)['value']+special_functions('erfc',1)['value']==pytest.approx(1)
    assert difference_equations([1,1],[0,1],50)['value']==12586269025
    assert difference_equations([1],[2],10,forcing=3)['value']==32


def test_barycentric_cubic_and_exact_transforms():
    from nablamath.ops.approximation_theory import approximation_theory
    from nablamath.ops.integral_transforms import integral_transforms
    nodes=[-1,0,1,2]
    assert approximation_theory(nodes,[x**3 for x in nodes],[-2,'1/2',3])['values']==[-8,F(1,8),27]
    assert approximation_theory([0],[3],[9])['weights']==[F(1)]
    assert isinstance(approximation_theory([0],[3],[9])['weights'][0],F)
    assert integral_transforms('laplace_polynomial',[0,0,1],2)['value']==F(1,4)
    assert integral_transforms('mellin_unit_polynomial',[1,1],2)['value']==F(5,6)
    assert integral_transforms('z_finite',[1,2,3],2)['value']==F(11,4)


def test_fredholm_coefficients_satisfy_the_full_polynomial_identity():
    from nablamath.ops.integral_equations import integral_equations
    result=integral_equations([[0,0],[0,1]],[1])
    a,b=result['coefficients']
    # u=1+x*integral(t*(a+b*t),0,1).
    assert a==1 and b==a/2+b/3 and result['residual_coefficients']==[0,0]
    with pytest.raises(ValueError,match='singular'):integral_equations([[1]],[1])


def test_multicomplex_polynomial_jacobian_and_local_only_inverse():
    from nablamath.ops.several_complex_variables import several_complex_variables
    result=several_complex_variables(['z**2+w','w**2'],['z','w'],[[1,1],1])
    assert result['values']==[['1','2'],['1','0']]
    assert result['jacobian_determinant']==['4','4'] and result['locally_biholomorphic']
    assert not several_complex_variables(['z**2'],['z'],[0])['locally_biholomorphic']


def test_finite_group_characters_match_independent_multivariate_dft():
    from nablamath.ops.abstract_harmonic_analysis import abstract_harmonic_analysis
    orders=[2,3];values=[1,2,3,4,5,6]
    reference=[sum(values[3*x+y]*cmath.exp(-2j*math.pi*(a*x/2+b*y/3)) for x in range(2) for y in range(3)) for a in range(2) for b in range(3)]
    result=abstract_harmonic_analysis(orders,values)
    assert [complex(*pair) for pair in result['values']]==pytest.approx(reference,abs=1e-12)
    restored=abstract_harmonic_analysis(orders,result['values'],inverse=True)
    assert [complex(*pair) for pair in restored['values']]==pytest.approx(values)


def test_weighted_hilbert_and_resolvent_identities():
    from nablamath.ops.functional_analysis import functional_analysis
    from nablamath.ops.operator_theory import operator_theory
    result=functional_analysis([[1,1]],[1,2],weights=[1,3])
    assert result['projection']==[F(7,4),F(7,4)]
    assert result['orthogonality']==[0] and result['pythagoras_verified']
    operator=operator_theory([[1,0],[0,0]],parameter=2)
    assert operator['orthogonal_projection'] and operator['resolvent']==((1,0),(0,F(1,2)))
    assert operator_theory([[-1,0],[0,1]])['positive_definite'] is False


def test_euler_lagrange_against_independent_mechanics_equation():
    from nablamath.ops.variational_calculus import variational_calculus
    from nablamath.expression import evaluate,parse_expr
    result=variational_calculus('(t+1)*v**2/2-q**2/2')
    expression=parse_expr(result['euler_lagrange'])
    for t,q,v,a in [(0,2,3,4),(2,-3,7,-1),(5,0,2,0)]:
        assert evaluate(expression,{'t':t,'q':q,'v':v,'a':a})==(t+1)*a+v+q


def test_sphere_torus_projective_plane_and_singular_vertex_links():
    from nablamath.ops.manifold_topology import manifold_topology
    sphere=manifold_topology([[0,1,2],[0,1,3],[0,2,3],[1,2,3]])
    assert sphere['closed'] and sphere['components'][0]['orientable_genus']==0
    facets=[]
    index=lambda i,j:(i%3)*3+j%3
    for i in range(3):
        for j in range(3):
            a,b,c,d=index(i,j),index(i+1,j),index(i,j+1),index(i+1,j+1)
            facets.extend([[a,b,c],[b,d,c]])
    torus=manifold_topology(facets)
    assert torus['closed'] and torus['euler_characteristic']==0 and torus['components'][0]['orientable_genus']==1
    rp=[[0,1,2],[0,1,3],[0,2,4],[0,3,5],[0,4,5],[1,2,5],[1,3,4],[1,4,5],[2,3,4],[2,3,5]]
    projective=manifold_topology(rp)
    assert projective['closed'] and not projective['orientable'] and projective['components'][0]['nonorientable_crosscaps']==1
    assert not manifold_topology([[0,1,2],[0,3,4]])['is_surface_with_boundary']


def test_discrete_hodge_theorem_and_exact_harmonic_projection():
    from nablamath.ops.global_analysis import global_analysis
    circle=global_analysis([[0,1],[0,2],[1,2]],degree=1,form=[1,0,0])
    assert circle['harmonic_dimension']==circle['betti_number']==1
    assert circle['harmonic_projection']==[F(1,3),F(-1,3),F(1,3)]
    assert global_analysis([[0,1,2]],degree=1)['harmonic_dimension']==0
    disconnected=global_analysis([[0],[1]],form=[5,7])
    assert disconnected['harmonic_dimension']==2 and disconnected['harmonic_projection']==[5,7]


def test_canonical_ensemble_stability_ground_degeneracy_and_geophysics():
    from nablamath.ops.statistical_mechanics import statistical_mechanics
    from nablamath.ops.geophysics import geophysics
    result=statistical_mechanics([0,math.log(3)])
    assert result['probabilities']==pytest.approx([.75,.25])
    low=statistical_mechanics([0,1000],temperature=1e-12,degeneracies=[2,1])
    assert low['entropy']==pytest.approx(math.log(2)) and low['heat_capacity']==0
    base=statistical_mechanics([0,1]);shifted=statistical_mechanics([1e10,1e10+1])
    assert shifted['probabilities']==base['probabilities'] and shifted['energy_variance']==base['energy_variance']
    layers=geophysics('vertical_seismic',thicknesses=[100,200],velocities=[1000,2000],densities=[2000,2000])
    assert layers['two_way_times_seconds']==[.2,.4] and layers['reflection_coefficients']==pytest.approx([1/3])
    slab=geophysics('bouguer_slab',density=2670,height=100)
    assert slab['gravity_m_s2']==pytest.approx(2*math.pi*6.67430e-11*2670*100)
