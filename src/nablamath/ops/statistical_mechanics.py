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


def microcanonical(energies,lower,upper,degeneracies=None,boltzmann=1.):
    if not isinstance(energies,list) or not 1<=len(energies)<=4096 or any(type(e) not in (int,float) or not math.isfinite(e) for e in energies) or not lower<=upper or not math.isfinite(boltzmann) or boltzmann<=0:raise ValueError('Invalid microcanonical shell')
    g=[1]*len(energies) if degeneracies is None else degeneracies
    if len(g)!=len(energies) or any(type(v) is not int or not 1<=v<=10**12 for v in g):raise ValueError('Invalid multiplicities')
    selected=[multiplicity if lower<=e<=upper else 0 for e,multiplicity in zip(energies,g)];count=sum(selected)
    if not count:raise ValueError('Empty microcanonical energy shell')
    return {'state_count':count,'level_probabilities':[v/count for v in selected],'entropy':boltzmann*math.log(count)}


def grand_canonical(energies,particle_numbers,chemical_potential=0.,temperature=1.,boltzmann=1.,degeneracies=None):
    if len(energies)!=len(particle_numbers) or any(type(n) is not int or n<0 for n in particle_numbers) or not math.isfinite(chemical_potential):raise ValueError('Invalid particle-sector data')
    shifted=[e-chemical_potential*n for e,n in zip(energies,particle_numbers)]
    result=statistical_mechanics(shifted,temperature=temperature,boltzmann=boltzmann,degeneracies=degeneracies)
    result['mean_particles']=math.fsum(p*n for p,n in zip(result['probabilities'],particle_numbers));result['mean_physical_energy']=math.fsum(p*e for p,e in zip(result['probabilities'],energies));result['potential_kind']='grand potential'
    result['mean_effective_energy']=result.pop('mean_energy')
    result['grand_potential']=result.pop('free_energy')
    result['effective_energy_temperature_derivative']=result.pop('heat_capacity')
    result['scope']='Finite grand-canonical ensemble; effective energy is E-mu*N. Its temperature derivative is not labelled physical heat capacity.'
    return result


def ising_chain(size,coupling=1.,field=0.,temperature=1.,periodic=True):
    from itertools import product
    if type(size) is not int or not 1<=size<=16 or not all(math.isfinite(v) for v in (coupling,field,temperature)) or temperature<=0 or type(periodic) is not bool:raise ValueError('Finite Ising enumeration budget exceeded')
    states=list(product((-1,1),repeat=size));energies=[]
    for state in states:
        pairs=sum(state[i]*state[i+1] for i in range(size-1))+(state[-1]*state[0] if periodic and size>1 else 0)
        energies.append(-coupling*pairs-field*sum(state))
    # The ensemble permits at most 4096 levels; combine equal energy/magnetization sectors.
    sectors={}
    for state,energy in zip(states,energies):sectors[energy,sum(state)]=sectors.get((energy,sum(state)),0)+1
    result=statistical_mechanics([key[0] for key in sectors],temperature=temperature,degeneracies=list(sectors.values()))
    result['magnetization_per_site']=sum(p*key[1]/size for p,key in zip(result['probabilities'],sectors));result['size']=size
    return result
