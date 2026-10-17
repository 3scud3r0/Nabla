"""Seeded random-walk Metropolis-Hastings for caller-supplied log densities."""
import math
import random


def metropolis_hastings(log_density, initial, *, samples=1000, burn_in=100,
                        thin=1, proposal_scale=1.0, seed=0):
    if (type(samples) is not int or not 1 <= samples <= 100000
            or type(burn_in) is not int or not 0 <= burn_in <= 100000
            or type(thin) is not int or not 1 <= thin <= 100
            or burn_in + samples*thin > 1000000 or type(seed) is not int):
        raise ValueError('Invalid MCMC budget or seed')
    scale = float(proposal_scale)
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('Proposal scale must be positive and finite')
    state = tuple(float(x) for x in initial)
    if not 1 <= len(state) <= 32 or not all(math.isfinite(x) for x in state):
        raise ValueError('Initial state must contain 1–32 finite coordinates')
    score = float(log_density(state))
    if not math.isfinite(score):
        raise ValueError('Initial state must have finite log density')
    rng, accepted, chain = random.Random(seed), 0, []
    total = burn_in + samples*thin
    for step in range(total):
        proposal = tuple(x + rng.gauss(0, scale) for x in state)
        proposed = float(log_density(proposal))
        if math.isnan(proposed) or proposed == math.inf:
            raise ValueError('Log density returned NaN or positive infinity')
        if proposed != -math.inf and math.log(max(rng.random(), 1e-300)) < min(0.0, proposed-score):
            state, score = proposal, proposed
            accepted += 1
        if step >= burn_in and (step-burn_in+1) % thin == 0:
            chain.append(list(state))
    means = [sum(row[i] for row in chain)/samples for i in range(len(state))]
    return {'samples': chain, 'mean': means, 'acceptance_rate': accepted/total,
            'seed': seed, 'burn_in': burn_in, 'thin': thin, 'proposal_scale': scale,
            'algorithm': 'random_walk_metropolis',
            'limitations': 'Finite correlated samples; convergence and effective sample size are not established.'}


def sample_normal(mean, standard_deviation, **options):
    mean, sd = float(mean), float(standard_deviation)
    if not math.isfinite(mean) or not math.isfinite(sd) or sd <= 0:
        raise ValueError('Normal parameters must be finite with positive standard deviation')
    return metropolis_hastings(lambda x: -0.5*((x[0]-mean)/sd)**2,
                               [mean], **options)
