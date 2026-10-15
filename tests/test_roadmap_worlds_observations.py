"""Analytic and exact checks; synthetic samples are never experimental evidence."""
from fractions import Fraction
import math
import pytest
from nablamath.worlds.boundary_conditions import BoundaryCondition as BC
from nablamath.numeric.pde_general import Poisson1D, solve_poisson_1d
from nablamath.worlds.validation_observational import Observation, compare_measurements
from nablamath.worlds.uncertainty_quantification import constant_acceleration
from nablamath.core.units import Quantity, METER, KILOMETER, SECOND
from nablamath.core.uncertainty import UncertainQuantity as UQ


def test_boundary_contracts():
    assert BC('dirichlet', 2).residual(2, 7) == 0
    assert BC('neumann', -3).residual(9, -3) == 0
    assert BC('robin', 8, 2, 3).residual(1, 2) == 0
    assert BC('neumann', 0).to_data()['derivative_convention'] == 'positive_x'


@pytest.mark.parametrize('args', [('periodic', 0), ('robin', 0, 0, 0), ('dirichlet', math.nan), ('neumann', True)])
def test_invalid_boundary(args):
    with pytest.raises(ValueError):
        BC(*args)


def test_poisson_manufactured_quadratic_nonzero_boundaries():
    # u = 3 + 2x + x(2-x), hence -u'' = 2.
    p = Poisson1D(2, BC('dirichlet', 3), BC('dirichlet', 7))
    result = solve_poisson_1d(p, lambda x: 2, cells=31)
    for x, y in zip(result['positions'], result['values']):
        assert y == pytest.approx(3+2*x+x*(2-x), abs=2e-13)
    assert result['experimental_validation'] is False


def test_poisson_sinusoidal_second_order():
    p = Poisson1D(1, BC('dirichlet', 0), BC('dirichlet', 0))
    errors = []
    for cells in (16, 32):
        result = solve_poisson_1d(p, lambda x: math.pi**2*math.sin(math.pi*x), cells=cells)
        errors.append(max(abs(y-math.sin(math.pi*x)) for x,y in zip(result['positions'],result['values'])))
    assert 3.9 < errors[0]/errors[1] < 4.1


@pytest.mark.parametrize('length', [0, -1, True, math.inf])
def test_invalid_poisson_domain(length):
    with pytest.raises(ValueError):
        Poisson1D(length, BC('dirichlet', 0), BC('dirichlet', 0))


def test_poisson_rejects_unsupported_boundaries_and_nonfinite_forcing():
    with pytest.raises(ValueError):
        Poisson1D(1, BC('neumann', 0), BC('dirichlet', 0))
    p = Poisson1D(1, BC('dirichlet', 0), BC('dirichlet', 0))
    with pytest.raises(ValueError):
        solve_poisson_1d(p, lambda _: math.nan)
    # A single interior cell receives both endpoint contributions.
    assert solve_poisson_1d(Poisson1D(1,BC('dirichlet',2),BC('dirichlet',4)), lambda _: 0,cells=2)['values'] == (2,3,4)


def test_measurement_exact_unit_conversion_and_bias():
    observations = [Observation('a',Quantity(1,KILOMETER),Quantity(2,METER),'synthetic fixture',True),
                    Observation('b',Quantity(1000,METER),Quantity(2,METER),'synthetic fixture',True)]
    result = compare_measurements(observations,[Quantity(1001,METER),Quantity(999,METER)],tolerance=Quantity(0,METER))
    assert result['mean_signed_residual'] == '0'
    assert result['mean_absolute_residual'] == '1/1000'
    assert result['coverage_fraction'] == '1'
    assert result['evidence'] == 'synthetic_comparison'
    assert result['independent_provenance_verified'] is False


def test_measurement_mismatch_and_duplicate_rejected():
    o = Observation('a', Quantity(1,METER),Quantity(0,METER),'lab declaration')
    with pytest.raises(ValueError):
        compare_measurements([o],[Quantity(1,SECOND)],tolerance=Quantity(0,METER))
    with pytest.raises(ValueError):
        compare_measurements([o,o],[Quantity(1,METER)]*2,tolerance=Quantity(0,METER))
    with pytest.raises(ValueError):
        Observation('a',Quantity(1,METER),Quantity(-1,METER),'lab')
    with pytest.raises(ValueError):
        Observation('a',Quantity(1,METER),Quantity(0,METER),'')


def test_constant_acceleration_exact_point_solution():
    result = constant_acceleration(UQ.around(1000,0,METER), UQ.around(2,0,METER/SECOND),
                                   UQ.around(3,0,METER/SECOND**2), UQ.around(2,0,SECOND))
    assert result['position'].interval.lower == result['position'].interval.upper == 1010
    assert result['velocity'].interval.lower == result['velocity'].interval.upper == 8


def test_uncertain_propagation_encloses_corner_solutions():
    result = constant_acceleration(UQ.around(1,1,METER), UQ.around(0,2,METER/SECOND),
                                   UQ.around(0,3,METER/SECOND**2), UQ.around(2,1,SECOND))
    interval = result['position'].interval
    for x in (0,2):
        for v in (-2,2):
            for a in (-3,3):
                for t in (1,3):
                    value = x+v*t+Fraction(1,2)*a*t*t
                    assert interval.lower <= value <= interval.upper
    assert result['experimental_validation'] is False


def test_uncertain_rejects_negative_time_and_units():
    inputs = [UQ.around(0,0,METER),UQ.around(0,0,METER/SECOND),UQ.around(0,0,METER/SECOND**2)]
    with pytest.raises(ValueError):
        constant_acceleration(*inputs,UQ.around(0,1,SECOND))
    with pytest.raises(ValueError):
        constant_acceleration(*inputs,UQ.around(1,0,METER))
