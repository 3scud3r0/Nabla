"""Stable finite canonical ensembles, entropy, energy and heat capacity (82)."""
import math
from ._area_utils import calculate as _calculate


def statistical_mechanics(energies, *, temperature=1., boltzmann=1., degeneracies=None):
    if not isinstance(energies,list) or not 1<=len(energies)<=4096 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1e12 for v in energies):
        raise ValueError('Require bounded finite energy levels')
    if any(type(v) not in (int,float) or not math.isfinite(v) or not 1e-12<=v<=1e12 for v in (temperature,boltzmann)):
        raise ValueError('Temperature and Boltzmann constant must be positive and bounded')
    degeneracies = [1]*len(energies) if degeneracies is None else degeneracies
    if not isinstance(degeneracies,list) or len(degeneracies)!=len(energies) or any(type(v) is not int or not 1<=v<=10**12 for v in degeneracies):
        raise ValueError('Degeneracies must be positive integer multiplicities')
    beta = 1/(boltzmann*temperature)
    # Shift energies before multiplying beta: common offsets cannot erase gaps.
    ground = min(energies)
    log_weights = [math.log(g)-beta*(e-ground) for g,e in zip(degeneracies,energies)]
    maximum = max(log_weights);weights = [math.exp(value-maximum) for value in log_weights];total = math.fsum(weights)
    probabilities = [w/total for w in weights]
    log_z = maximum+math.log(total)-beta*ground
    shifted = [e-ground for e in energies]
    mean_shift = math.fsum(p*e for p,e in zip(probabilities,shifted))
    mean = ground+mean_shift
    variance = math.fsum(p*(e-mean_shift)**2 for p,e in zip(probabilities,shifted))
    entropy = boltzmann*math.fsum(p*(math.log(g)-math.log(p)) for p,g in zip(probabilities,degeneracies) if p)
    return {'probabilities':probabilities,'log_partition':log_z,
            'partition':math.exp(log_z) if -700<log_z<700 else None,
            'mean_energy':mean,'energy_variance':variance,'entropy':entropy,
            'heat_capacity':variance/(boltzmann*temperature**2),'free_energy':-boltzmann*temperature*log_z,
            'scope':'Finite canonical ensemble in caller-consistent units; no thermodynamic-limit or physical calibration claim.'}


def calculate(**arguments):return _calculate('statistical_mechanics',**arguments)
