"""Independent analytic/structural checks for bounded physics profiles.

No fixture is presented as an authenticated physical experiment. Smooth Euler
contact transport and exact shock jump identities test distinct properties;
nonlinear elasticity is checked using prescribed strains, energy derivatives,
and analytic linear limits rather than mirroring the Newton implementation.
"""
import math

import pytest

from nablamath.physics.fluids.compressible import (
    ConservativeState,
    Euler1DConfig,
    PrimitiveState,
    normal_shock_downstream,
    physical_flux,
    rankine_hugoniot_residual,
    rusanov_flux,
    shock_tube_initial,
    solve_euler_1d,
)
from nablamath.physics.fluids.turbulence import (
    MixingLengthModel,
    ShearMeasurement,
    calibrate_mixing_length,
)
from nablamath.physics.fea.nonlinear import (
    AxialElement,
    CubicElasticMaterial,
    NonlinearBar,
    assemble_nonlinear_bar,
    solve_nonlinear_bar,
)


@pytest.mark.parametrize('gamma', [1.1, 1.4, 5/3, 2.0])
@pytest.mark.parametrize('velocity', [-20, 0, 30])
def test_ideal_gas_round_trip_and_analytic_energy(gamma, velocity):
    primitive = PrimitiveState(2, velocity, 100)
    conservative = primitive.conservative(gamma)
    assert conservative.density == 2
    assert conservative.momentum == 2*velocity
    assert conservative.energy == pytest.approx(100/(gamma-1)+velocity**2)
    actual = conservative.primitive(gamma)
    assert actual.density == pytest.approx(2)
    assert actual.velocity == pytest.approx(velocity)
    assert actual.pressure == pytest.approx(100)
    assert primitive.sound_speed(gamma) == pytest.approx(math.sqrt(gamma*50))


@pytest.mark.parametrize('args', [
    (0,0,1), (-1,0,1), (1,0,0), (1,0,-1),
    (1,math.nan,1), (True,0,1), (1,1e9,1), (1,0,math.inf),
])
def test_invalid_primitive_state(args):
    with pytest.raises(ValueError):
        PrimitiveState(*args)


@pytest.mark.parametrize('args', [(0,0,1), (1,2,1), (1,math.inf,1), (1,0,-1), (1,1e308,1)])
def test_invalid_conservative_state(args):
    with pytest.raises(ValueError):
        ConservativeState(*args)


@pytest.mark.parametrize('gamma', [0, 1, 3.1, True, math.nan])
def test_invalid_gas_gamma(gamma):
    with pytest.raises(ValueError):
        PrimitiveState(1,0,1).conservative(gamma)


def test_flux_consistency_with_independent_euler_formula():
    state = PrimitiveState(2,3,5).conservative(1.4)
    flux = physical_flux(state)
    expected_energy = 5/.4 + 2*9/2
    assert flux == pytest.approx((6,23,(expected_energy+5)*3))
    assert rusanov_flux(state,state) == pytest.approx(flux)


@pytest.mark.parametrize('boundary', ['periodic', 'outflow', 'reflecting'])
def test_uniform_stationary_state_is_exactly_preserved(boundary):
    initial = [PrimitiveState(1,0,1)]*12
    result = solve_euler_1d(initial,.1,config=Euler1DConfig(boundary=boundary))
    assert result.primitive_states == tuple(initial)
    assert result.conservation_residual == (0,0,0)
    assert result.to_data()['experimental_validation'] is False


def test_zero_duration_has_no_attempted_work():
    initial = [PrimitiveState(1,2,3)]*2
    result = solve_euler_1d(initial,0)
    assert result.steps == result.attempted_cell_updates == 0
    assert result.primitive_states[0].velocity == 2


def test_periodic_uniform_moving_state_and_conservation():
    state = PrimitiveState(1.2,-2.5,2)
    result = solve_euler_1d([state]*20,.1,config=Euler1DConfig(boundary='periodic'))
    for final in result.primitive_states:
        assert final.density == pytest.approx(state.density)
        assert final.velocity == pytest.approx(state.velocity)
        assert final.pressure == pytest.approx(state.pressure)
    assert result.boundary_transport == (0,0,0)
    assert max(map(abs,result.conservation_residual)) < 1e-13


def test_euler_smooth_contact_transport_refines_against_exact_advection():
    # Constant pressure and velocity: any advected positive density is an
    # exact ideal-Euler contact field, giving an independent analytic reference.
    errors = []
    for cells in (24,48):
        initial = [PrimitiveState(1+.2*math.sin(2*math.pi*(i+.5)/cells),1,1)
                   for i in range(cells)]
        result = solve_euler_1d(initial,.1,config=Euler1DConfig(boundary='periodic'))
        error = sum(abs(s.density-(1+.2*math.sin(2*math.pi*(x-.1))))
                    for x,s in zip(result.cell_centers_m,result.primitive_states))/cells
        errors.append(error)
        assert max(map(abs,result.conservation_residual)) < 1e-12
        assert max(abs(s.velocity-1) for s in result.primitive_states) < 1e-12
        assert max(abs(s.pressure-1) for s in result.primitive_states) < 1e-12
    assert errors[1] < .65*errors[0]


def test_sod_shock_tube_positive_and_near_analytic_contact_plateau():
    initial = shock_tube_initial(120,PrimitiveState(1,0,1),PrimitiveState(.125,0,.1))
    result = solve_euler_1d(initial,.15)
    states = result.primitive_states
    assert all(s.density > 0 and s.pressure > 0 for s in states)
    # Standard ideal-gas Sod Riemann star state (gamma=1.4): p*=.30313,
    # u*=.92745; x~.571 lies between the rarefaction tail and contact.
    center = states[68]
    assert center.pressure == pytest.approx(.30313,abs=.02)
    assert center.velocity == pytest.approx(.92745,abs=.04)
    assert max(map(abs,result.conservation_residual)) < 1e-12


def test_reflecting_walls_conserve_mass_energy_and_account_momentum():
    initial = shock_tube_initial(30,PrimitiveState(1,.5,1),PrimitiveState(.5,-.2,.5))
    result = solve_euler_1d(initial,.05,config=Euler1DConfig(boundary='reflecting'))
    assert result.final_integrals[0] == pytest.approx(result.initial_integrals[0],abs=1e-13)
    assert result.final_integrals[2] == pytest.approx(result.initial_integrals[2],abs=1e-13)
    assert result.boundary_transport[0] == result.boundary_transport[2] == 0
    assert max(map(abs,result.conservation_residual)) < 1e-12


@pytest.mark.parametrize('mach', [1.01, 2, 5, 20])
def test_normal_shock_matches_independent_rankine_hugoniot_and_entropy(mach):
    gamma = 1.4
    upstream = PrimitiveState(1,mach*math.sqrt(gamma),1)
    downstream = normal_shock_downstream(upstream,gamma)
    assert downstream.density > upstream.density
    assert downstream.pressure > upstream.pressure
    assert downstream.velocity/downstream.sound_speed(gamma) < 1
    # Ideal-gas entropy grows across the physically admissible compression shock.
    assert downstream.pressure/downstream.density**gamma > .999999999999
    residual = rankine_hugoniot_residual(upstream,downstream,0,gamma)
    scales = physical_flux(upstream.conservative(gamma),gamma)
    assert all(abs(r) < 1e-12*max(1,abs(s)) for r,s in zip(residual,scales))


def test_moving_contact_rankine_hugoniot_identity():
    assert rankine_hugoniot_residual(PrimitiveState(1,2,3),PrimitiveState(4,2,3),2) == pytest.approx((0,0,0))


@pytest.mark.parametrize('kwargs', [
    {'cfl':0}, {'cfl':.6}, {'boundary':'fixed'}, {'max_steps':True},
    {'max_cell_updates':0}, {'length_m':-1}, {'max_halvings':100},
])
def test_invalid_euler_configuration(kwargs):
    with pytest.raises(ValueError):
        Euler1DConfig(**kwargs)


def test_euler_budgets_and_bad_duration_are_explicit_failures():
    initial = [PrimitiveState(1,0,1)]*10
    with pytest.raises(ArithmeticError,match='step budget'):
        solve_euler_1d(initial,1,config=Euler1DConfig(max_steps=1))
    with pytest.raises(ArithmeticError,match='cell-update budget'):
        solve_euler_1d(initial,.1,config=Euler1DConfig(max_cell_updates=5))
    for duration in (-1,math.nan,True):
        with pytest.raises(ValueError):
            solve_euler_1d(initial,duration)
    with pytest.raises(ValueError):
        solve_euler_1d(initial[:1],.1)


def test_shock_initial_requires_face_alignment_and_supersonic_jump():
    state = PrimitiveState(1,0,1)
    with pytest.raises(ValueError):
        shock_tube_initial(10,state,state,discontinuity_fraction=.25)
    with pytest.raises(ValueError):
        normal_shock_downstream(state)


def test_mixing_length_matches_analytic_closure_and_gradient_sign():
    model = MixingLengthModel(kappa=.4)
    result = model.evaluate(.1,-10)
    assert result.mixing_length_m == pytest.approx(.04)
    assert result.eddy_viscosity_m2_s == pytest.approx(.016)
    assert result.shear_stress_pa(2,.001) == pytest.approx(-.34)
    assert result.cap_active is False


def test_van_driest_wall_limit_and_stable_tiny_wall_units():
    model = MixingLengthModel()
    assert model.evaluate(0,10,wall_units=0).eddy_viscosity_m2_s == 0
    tiny = model.evaluate(1,1,wall_units=1e-12)
    assert tiny.mixing_length_m > 0
    assert tiny.mixing_length_m == pytest.approx(.41e-12/26,rel=1e-12)
    assert model.evaluate(1,1,wall_units=1e6).mixing_length_m == pytest.approx(.41)


def test_mixing_length_cap_is_reported():
    result = MixingLengthModel(max_eddy_viscosity_m2_s=.01).evaluate(1,100)
    assert result.cap_active is True
    assert result.eddy_viscosity_m2_s == .01


def _shear_samples(kappa=.42):
    rows = []
    for i,(y,g) in enumerate(((.02,4),(.04,-3),(.08,2),(.1,-1))):
        rho,nu = 1.2,.0001
        tau = rho*(nu+(kappa*y)**2*abs(g))*g
        rows.append(ShearMeasurement(str(i),y,g,tau,rho,nu,'synthetic analytic closure',True,weight=i+1))
    return rows


def test_calibration_recovers_prescribed_parameter_and_retains_evidence_scope():
    result = calibrate_mixing_length(_shear_samples())
    assert result.model.kappa == pytest.approx(.42,abs=1e-14)
    assert result.weighted_squared_residual_pa2 < 1e-28
    assert result.parameter_at_bound is False
    data = result.to_data()
    assert data['synthetic_present'] is True
    assert data['source_authenticity_verified'] is False
    assert data['holdout_validation_performed'] is False
    assert all(row['source'] == 'synthetic analytic closure' for row in data['comparisons'])


def test_calibration_constrained_optimum_is_declared():
    result = calibrate_mixing_length(_shear_samples(.8),minimum_kappa=.2,maximum_kappa=.5)
    assert result.model.kappa == .5
    assert result.parameter_at_bound is True
    assert result.weighted_squared_residual_pa2 > 0


def test_calibration_rejects_degenerate_duplicate_and_capped_measurements():
    samples = _shear_samples()
    with pytest.raises(ValueError,match='unique'):
        calibrate_mixing_length([samples[0],samples[0]])
    zeros = [ShearMeasurement(str(i),0,1,0,1,0,'fixture',True) for i in range(2)]
    with pytest.raises(ValueError,match='unidentifiable'):
        calibrate_mixing_length(zeros)
    with pytest.raises(ValueError,match='cap'):
        calibrate_mixing_length(samples,max_eddy_viscosity_m2_s=1e-8)


@pytest.mark.parametrize('kwargs', [
    {'kappa':0}, {'damping_a_plus':0}, {'max_eddy_viscosity_m2_s':-1},
    {'kappa':True}, {'max_wall_distance_m':math.inf},
])
def test_invalid_mixing_length_models(kwargs):
    with pytest.raises(ValueError):
        MixingLengthModel(**kwargs)


@pytest.mark.parametrize('args', [(-1,1,None), (1,math.nan,None), (1,1,-1), (1,1,math.inf)])
def test_invalid_shear_evaluation(args):
    with pytest.raises(ValueError):
        MixingLengthModel().evaluate(args[0],args[1],wall_units=args[2])


def test_cubic_material_stress_tangent_energy_derivative():
    material = CubicElasticMaterial(100,300)
    eps,h = .03,1e-6
    assert material.stress_pa(eps) == pytest.approx(100*eps+300*eps**3)
    finite_tangent = (material.stress_pa(eps+h)-material.stress_pa(eps-h))/(2*h)
    assert material.tangent_pa(eps) == pytest.approx(finite_tangent,rel=1e-10)
    energy_derivative = (material.energy_density_j_m3(eps+h)-material.energy_density_j_m3(eps-h))/(2*h)
    assert material.stress_pa(eps) == pytest.approx(energy_derivative,rel=1e-9)
    assert material.stress_pa(-eps) == -material.stress_pa(eps)


@pytest.mark.parametrize('elements', [1, 2, 10, 100])
@pytest.mark.parametrize('force', [-2, 0, 2])
def test_nonlinear_fe_reduces_to_independent_linear_bar_formula(elements,force):
    bar = NonlinearBar.uniform(2,.5,CubicElasticMaterial(1000),force,elements=elements)
    result = solve_nonlinear_bar(bar,load_steps=2)
    exact_end = force*2/(.5*1000)
    assert result.displacements_m[-1] == pytest.approx(exact_end,abs=1e-13)
    for i,u in enumerate(result.displacements_m):
        assert u == pytest.approx(exact_end*i/elements,abs=1e-13)
    assert result.reaction_n == pytest.approx(-force,abs=1e-10)
    assert result.strain_energy_j == pytest.approx(force*exact_end/2,abs=1e-13)
    assert result.total_potential_energy_j == pytest.approx(-force*exact_end/2,abs=1e-13)
    assert result.to_data()['experimental_validation'] is False


def test_nonlinear_uniform_bar_prescribed_strain_and_force():
    material = CubicElasticMaterial(50,3000)
    strain = .04
    force = .2*(50*strain+3000*strain**3)
    result = solve_nonlinear_bar(NonlinearBar.uniform(3,.2,material,force,elements=5))
    assert result.displacements_m[-1] == pytest.approx(3*strain,rel=1e-9)
    assert result.element_strains == pytest.approx([strain]*5,rel=1e-9)
    assert result.reaction_n == pytest.approx(-force,rel=1e-9)
    assert result.residual_norm_n < 1e-9


def test_heterogeneous_series_elements_and_internal_nodal_loads():
    # Prescribe strains; compute loads independently from the constitutive law.
    strains = (.02,-.01,.03)
    lengths = (1,2,.5)
    areas = (.5,.3,.8)
    young = (100,200,50)
    hardening = (1000,500,300)
    axial = [a*(e*s+h*s**3) for a,e,h,s in zip(areas,young,hardening,strains)]
    loads = (0,axial[0]-axial[1],axial[1]-axial[2],axial[2])
    elements = tuple(AxialElement(l,a,CubicElasticMaterial(e,h)) for l,a,e,h in zip(lengths,areas,young,hardening))
    result = solve_nonlinear_bar(NonlinearBar(elements,loads),load_steps=6)
    assert result.element_strains == pytest.approx(strains,abs=1e-10)
    assert result.reaction_n == pytest.approx(-sum(loads),abs=1e-9)
    expected_u = [0]
    for length,strain in zip(lengths,strains):
        expected_u.append(expected_u[-1]+length*strain)
    assert result.displacements_m == pytest.approx(expected_u,abs=1e-10)


def test_assembled_tangent_and_force_are_energy_derivatives():
    bar = NonlinearBar.uniform(2,.5,CubicElasticMaterial(100,3000),1,elements=3)
    u = (0,.01,.015,.025)
    assembly = assemble_nonlinear_bar(bar,u)
    h = 1e-7
    for j in range(1,4):
        plus,minus = list(u),list(u)
        plus[j] += h
        minus[j] -= h
        ap,am = assemble_nonlinear_bar(bar,plus),assemble_nonlinear_bar(bar,minus)
        numerical_force = (ap.strain_energy_j-am.strain_energy_j)/(2*h)
        assert assembly.internal_forces_n[j] == pytest.approx(numerical_force,rel=1e-8)
        for i in range(1,4):
            numerical = (ap.internal_forces_n[i]-am.internal_forces_n[i])/(2*h)
            expected = assembly.free_diagonal_n_m[i-1] if i == j else (
                assembly.free_offdiagonal_n_m[min(i,j)-1] if abs(i-j) == 1 else 0)
            assert numerical == pytest.approx(expected,rel=1e-8,abs=1e-8)


def test_strong_nonlinearity_uses_backtracking_and_continuation_agrees():
    bar = NonlinearBar.uniform(1,1,CubicElasticMaterial(1,100000),1,elements=3)
    direct = solve_nonlinear_bar(bar,load_steps=1)
    continued = solve_nonlinear_bar(bar,load_steps=12)
    assert any(alpha < 1 for alpha in direct.continuation[0].accepted_line_search_factors)
    assert direct.displacements_m == pytest.approx(continued.displacements_m,abs=1e-10)
    eps = direct.displacements_m[-1]
    assert eps+100000*eps**3 == pytest.approx(1,abs=1e-9)


def test_one_newton_update_can_converge_on_linear_material():
    bar = NonlinearBar.uniform(1,1,CubicElasticMaterial(100),1,elements=2)
    result = solve_nonlinear_bar(bar,load_steps=1,max_newton_iterations=1)
    assert result.continuation[0].newton_iterations == 1
    assert result.displacements_m[-1] == pytest.approx(.01)


def test_nonlinear_failures_never_masquerade_as_converged_results():
    material = CubicElasticMaterial(100,10000)
    bar = NonlinearBar.uniform(1,1,material,1,elements=3)
    with pytest.raises(ArithmeticError,match='element-evaluation'):
        solve_nonlinear_bar(bar,max_element_evaluations=2)
    with pytest.raises(ArithmeticError,match='Newton iteration'):
        solve_nonlinear_bar(bar,load_steps=1,max_newton_iterations=1)
    impossible = NonlinearBar.uniform(1,1,CubicElasticMaterial(1,maximum_abs_strain=.01),1,elements=2)
    with pytest.raises(ArithmeticError):
        solve_nonlinear_bar(impossible,load_steps=1,max_line_searches=5)


@pytest.mark.parametrize('kwargs', [
    {'young_pa':0}, {'young_pa':True}, {'young_pa':1,'hardening_pa':-1},
    {'young_pa':1,'maximum_abs_strain':.5}, {'young_pa':math.nan},
])
def test_invalid_material_contracts(kwargs):
    with pytest.raises(ValueError):
        CubicElasticMaterial(**kwargs)


def test_invalid_fe_mesh_load_displacement_and_solver_contracts():
    material = CubicElasticMaterial(100)
    with pytest.raises(ValueError):
        AxialElement(0,1,material)
    with pytest.raises(ValueError):
        NonlinearBar((AxialElement(1,1,material),),(1,1))
    bar = NonlinearBar.uniform(1,1,material,1,elements=2)
    for values in ((0,0), (1,0,0), (0,math.nan,0)):
        with pytest.raises(ValueError):
            assemble_nonlinear_bar(bar,values)
    for kwargs in ({'load_steps':True}, {'absolute_tolerance_n':0}, {'relative_tolerance':-.1}):
        with pytest.raises(ValueError):
            solve_nonlinear_bar(bar,**kwargs)
    with pytest.raises(ValueError):
        material.stress_pa(.2)
