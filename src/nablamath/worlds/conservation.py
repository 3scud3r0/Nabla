"""Quantitative invariant/flux diagnostics without assuming all mass is conserved."""
import math


def check_conservation(result, *, tolerance=1e-6):
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('Tolerância positiva obrigatória')
    if result['model'] == 'harmonic_oscillator':
        rate = result['rate']
        energies = [(state[1]**2+(rate*state[0])**2)/2 for _,state in result['trajectory']]
        residual = max(abs(value-energies[0]) for value in energies)
        return {'quantity': 'energy_per_unit_mass', 'unit': 'm^2/s^2', 'residual': residual,
                'within_tolerance': residual <= tolerance, 'tolerance': tolerance}
    if result['model'] == 'heat_1d':
        residual = result['flux_balance_residual']
        return {'quantity': 'heat_balance_with_boundary_flux', 'unit': 'K*m', 'residual': residual,
                'energy_nonincreasing': result['max_energy_increase'] <= tolerance,
                'within_tolerance': residual <= tolerance and result['max_energy_increase'] <= tolerance,
                'tolerance': tolerance}
    raise ValueError('Modelo não declara uma quantidade conservada')
