"""Numerical references and adversarial cases, authored but not executed."""
import math
import pytest


@pytest.fixture
def np():
    pytest.importorskip('scipy');pytest.importorskip('sympy')
    return pytest.importorskip('numpy')


def test_so_su_se3_exponential_and_frechet(np):
    from nablamath.ops.lie_groups import matrix_group,se3_adjoint
    result=matrix_group('SO',[[0,-math.pi/2],[math.pi/2,0]])
    assert np.allclose(result['matrix'],[[0,-1],[1,0]],atol=1e-12)
    derivative=matrix_group('SL',[[0,0],[0,0]],direction=[[1,0],[0,-1]])
    assert np.allclose(derivative['frechet_derivative'],[[1,0],[0,-1]])
    su=matrix_group('SU',[[[0,1],0],[0,[0,-1]]])['matrix']
    assert su[0][0][0]==pytest.approx(math.cos(1)) and su[0][0][1]==pytest.approx(math.sin(1))
    assert np.allclose(se3_adjoint(np.eye(4).tolist()),np.eye(6))
    with pytest.raises(ValueError):matrix_group('SO',[[1,0],[0,0]])


def test_parallel_transport_and_euclidean_geodesic(np):
    from nablamath.math.geometry.fiber_bundles import parallel_transport
    from nablamath.ops.differential_geometry import geodesic,coordinate_pullback,covariant_derivative
    result=parallel_transport(['x'],[[['1']]],['t'],[1.],duration=1.,steps=5)
    assert result['vectors'][-1][0]==pytest.approx(math.exp(-1),rel=1e-7)
    orbit=geodesic([[1,0],[0,1]],['x','y'],[0,0],[1,2],duration=2,steps=4)
    assert np.allclose(orbit['states'][-1],[2,4,1,2],atol=1e-10)
    pullback=coordinate_pullback([[1,0],[0,1]],['x','y'],['u','v'],['u','2*v'])
    assert pullback['metric']==[['1','0'],['0','4']]
    assert covariant_derivative([[1]],['x'],['x*x'])['components']==[['2*x']]


def test_adaptive_vector_stiff_solution_and_event(np):
    from nablamath.numeric.stiff_ode import solve_stiff_system
    result=solve_stiff_system(['-10*x','-y'],['x','y'],[1.,1.],duration=1.,steps=10)
    assert result['values'][-1][0]==pytest.approx(math.exp(-10),rel=1e-5)
    assert result['values'][-1][1]==pytest.approx(math.exp(-1),rel=1e-6)
    event=solve_stiff_system(['-1'],['x'],[1.],duration=2.,events=[{'source':'x','terminal':True,'direction':-1}])
    assert event['event_times'][0][0]==pytest.approx(1.,abs=1e-8)


def test_cartesian_poisson_manufactured_sine_eigenfunction(np):
    from nablamath.numeric.pde_general import poisson_cartesian
    n=8;grid=np.arange(1,n+1)/(n+1);u=np.sin(np.pi*grid)[:,None]*np.sin(np.pi*grid)[None,:]
    eigenvalue=8*(n+1)**2*math.sin(math.pi/(2*(n+1)))**2
    solution=poisson_cartesian([n,n],(eigenvalue*u).tolist())
    assert np.allclose(solution['interior_values'],u,atol=1e-12)
    assert solution['residual_inf']<1e-10


def test_fem_dirichlet_neumann_robin_and_unanchored_rejection(np):
    from nablamath.numeric.pde_general import poisson_fem_1d,adaptive_poisson_1d
    nodes=np.linspace(0,1,9).tolist();zero={'kind':'dirichlet','value':0.}
    result=poisson_fem_1d(nodes,'2',zero,zero)
    assert np.allclose(result['values'],[x*(1-x) for x in nodes],atol=1e-12)
    linear=poisson_fem_1d(nodes,'0',zero,{'kind':'neumann','value':1.})
    assert np.allclose(linear['values'],nodes)
    robin=poisson_fem_1d(nodes,'0',zero,{'kind':'robin','alpha':1.,'value':2.})
    assert np.allclose(robin['values'],nodes)
    adaptive=adaptive_poisson_1d('0',zero,{'kind':'dirichlet','value':1.})
    assert adaptive['requested_estimator_reached']
    with pytest.raises(ValueError,match='Pure Neumann'):
        poisson_fem_1d(nodes,'0',{'kind':'neumann','value':0.},{'kind':'neumann','value':0.})


def test_sde_coupled_brownian_and_deterministic_milstein(np):
    from nablamath.math.probability.stochastic import sde_system,sde_refinement
    path=sde_system(['0'],[['1']],['x'],[0.],duration=1.,steps=2,increments=[[.25],[-.1]])
    assert path['trajectory'][-1][0]==pytest.approx(.15)
    zero=sde_system(['0'],[['0']],['x'],[2.],steps=4,method='milstein')
    assert zero['trajectory']==[[2.]]*5
    pair=sde_refinement(['0'],[['1']],['x'],[0.],steps=4,seed=19)
    assert pair['coupled_final_difference']<1e-12
    with pytest.raises(ValueError,match='independent scalar'):
        sde_system(['0','0'],[['x','y'],['0','y']],['x','y'],[1.,1.],method='milstein')


def test_nystrom_fredholm_and_volterra_constant_kernel(np):
    from nablamath.ops.integral_equations import numerical_integral_equation
    fredholm=numerical_integral_equation('1/2','1',nodes=8)
    assert np.allclose(fredholm['values'],2.,atol=1e-12)
    volterra=numerical_integral_equation('1','1',kind='volterra',nodes=64)
    assert volterra['values'][-1]==pytest.approx(math.e,rel=5e-5)
    assert volterra['residual_inf']<1e-10


def test_splines_chebyshev_minimax_and_pade(np):
    from nablamath.ops.approximation_theory import spline,chebyshev_fit,remez_grid,pade
    assert spline([0,1,2],[1,3,5],[.25,1.5])['values']==pytest.approx([1.5,4.])
    fit=chebyshev_fit([-1,0,1],[1,0,1],2,[-.5,.5])
    assert fit['values']==pytest.approx([.25,.25])
    minimax=remez_grid([-1,0,1],[1,0,1],0)
    assert minimax['grid_max_error']==pytest.approx(.5)
    rational=pade([1,1,.5,1/6],1)
    assert rational['numerator_descending'][-1]/rational['denominator_descending'][-1]==pytest.approx(1.)
    with pytest.raises(ValueError):spline([0,1],[0,1],[2.])


def test_fft_nufft_and_wavelet_inverse(np):
    from nablamath.ops.spectral import multidimensional_fft,nonuniform_dft,sampling_diagnostics,wavelet_transform
    fft=multidimensional_fft([[1,0],[0,0]])
    assert np.allclose(fft['real'],np.ones((2,2))) and fft['parseval_residual']<1e-12
    direct=nonuniform_dft([0,.25,.5,.75],[1,1,1,1],[0,1])
    assert np.allclose(direct['values'],[[4,0],[0,0]],atol=1e-12)
    assert sampling_diagnostics([1,1,1,1],4)['nyquist_frequency']==2
    pytest.importorskip('pywt')
    signal=np.arange(32).tolist();coefficients=wavelet_transform(signal,'db2',level=2)['coefficients']
    assert np.allclose(wavelet_transform(coefficients,'db2',inverse=True)['values'],signal,atol=1e-12)


def test_group_convolution_and_harmonic_blocks(np):
    from nablamath.ops.abstract_harmonic_analysis import group_convolution,group_fourier
    table=[[0,1],[1,0]]
    assert np.allclose(group_convolution(table,[1,0],[3,4]),[[3,0],[4,0]])
    result=group_fourier(table,[2,1],[[[[1]],[[1]]],[[[1]],[[-1]]]])
    assert result['blocks']==[[[[3.,0.]]],[[[1.,0.]]]]


def test_ensembles_ising_and_grand_potential(np):
    from nablamath.ops.statistical_mechanics import microcanonical,grand_canonical,ising_chain
    shell=microcanonical([0,1,2],.5,1.5,degeneracies=[1,3,1])
    assert shell['state_count']==3 and shell['entropy']==pytest.approx(math.log(3))
    grand=grand_canonical([0,0],[0,1],chemical_potential=0.)
    assert grand['mean_particles']==pytest.approx(.5)
    ising=ising_chain(2,coupling=1,field=0,periodic=False)
    assert ising['mean_energy']==pytest.approx(-math.tanh(1.))
    assert ising['magnetization_per_site']==pytest.approx(0.,abs=1e-12)


def test_gaussian_hierarchy_conjugacy_and_posterior_reproducibility(np):
    from nablamath.ops.bayesian_inference import conjugate_update,gaussian_hierarchy,sample_posterior
    assert conjugate_update('gamma_poisson',[2,3],{'shape':1,'rate':1})['mean']=='2'
    normal=conjugate_update('normal_known_variance',[1],{'mean':0,'variance':1,'observation_variance':1})
    assert normal=={'mean':'1/2','variance':'1/2'}
    result=gaussian_hierarchy([[1]],[1],[0],[[1]])
    assert np.allclose(result['posterior_mean'],[.5]) and np.allclose(result['posterior_covariance'],[[.5]])
    config=dict(log_density='-x*x/2',variables=['x'],initials=[[-1.],[1.]],samples=8,burn_in=4,seed=12)
    assert sample_posterior(**config)==sample_posterior(**config)


def test_implicit_ad_and_linear_solve_vjp(np):
    from nablamath.ops.autograd import implicit_derivative,linear_solve_vjp,expression_derivatives
    result=implicit_derivative(['y*y-x'],['x'],['y'],[4,2])
    assert result['jacobian']==[['1/4']]
    assert expression_derivatives('x**3',['x'],[2],order=3)['derivatives']['3']=='6'
    vjp=linear_solve_vjp([[2,0],[0,4]],[2,8],[1,1])
    assert np.allclose(vjp['rhs_cotangent'],[.5,.25])
    assert np.allclose(vjp['matrix_cotangent'],[[-.5,-1],[-.25,-.5]])


def test_boundary_potential_and_inverse_gravity(np):
    from nablamath.ops.potential_theory import green_function,boundary_single_layer
    from nablamath.ops.geophysics import gravity_point_masses,tikhonov_inversion,acoustic_wave_2d
    assert green_function(2)['value']==pytest.approx(1/(8*math.pi))
    theta=np.linspace(0,2*np.pi,8,endpoint=False);vertices=np.c_[np.cos(theta),np.sin(theta)].tolist()
    assert boundary_single_layer(vertices,[1.]*8)['residual_inf']<1e-10
    field=gravity_point_masses([[0,0,0]],[1.],[[1.,0,0]])
    assert field['acceleration_m_s2'][0][0]==pytest.approx(-6.67430e-11)
    inverse=tikhonov_inversion([[1]],[2],regularization=1.)
    assert inverse['estimate']==pytest.approx([1.])
    assert np.allclose(acoustic_wave_2d(np.zeros((5,5)).tolist(),1.,1.,.2,2)['final'],0)
    with pytest.raises(ValueError,match='CFL'):acoustic_wave_2d(np.zeros((5,5)).tolist(),1.,1.,1.,2)


def test_conic_program_reference_when_solver_installed(np):
    cp=pytest.importorskip('cvxpy')
    if not {'CLARABEL','SCS','CVXOPT'}&set(cp.installed_solvers()):pytest.skip('No supported conic solver installed')
    from nablamath.ops.convex_optimization import conic_program
    # min x subject [[x,1],[1,x]] >= 0, whose exact optimum is x=1.
    result=conic_program([1.],semidefinite=[[[0,1],[1,0]],[[1,0],[0,1]]])
    assert result['point'][0]==pytest.approx(1.,abs=1e-4)
    assert result['max_constraint_violation']<1e-4


def test_continuous_remez_error_certificate(np):
    from fractions import Fraction
    from nablamath.ops.approximation_theory import remez_polynomial
    from nablamath.math.analysis.intervals import verify_polynomial_range
    result=remez_polynomial([0,0,1],0)
    assert result['exchange_converged']
    assert float(Fraction(result['coefficients'][0]))==pytest.approx(.5)
    assert verify_polynomial_range(result['error_range_certificate'])
    assert Fraction(result['uniform_error_upper_bound'])>=Fraction(1,2)


def test_adaptive_brownian_grid_and_degenerate_chain_diagnostics(np):
    from nablamath.math.probability.stochastic import adaptive_sde
    from nablamath.ops.bayesian_inference import posterior_diagnostics
    result=adaptive_sde(['0'],[['1']],['x'],[0.],max_steps=16,seed=42)
    assert result['requested_estimator_reached'] and result['refinement_difference']<1e-12
    diagnostics=posterior_diagnostics(np.zeros((2,8,1)).tolist())
    assert diagnostics['rank_normalized_split_rhat']==[None] and diagnostics['effective_sample_size']==[None]
