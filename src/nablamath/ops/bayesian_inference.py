"""Finite exact Bayes and conjugate Beta-Binomial inference."""
from fractions import Fraction
from ..core.semantic_ir import rational
from ..math.statistics.bayesian import posterior, predictive


def beta_binomial(successes, trials, *, alpha=1, beta=1):
    if type(successes) is not int or type(trials) is not int or not 0 <= successes <= trials <= 1000000:
        raise ValueError('Require 0 <= successes <= trials <= 1000000')
    alpha, beta = rational(alpha), rational(beta)
    if min(alpha, beta) <= 0:
        raise ValueError('Beta shape parameters must be positive')
    a, b = alpha+successes, beta+trials-successes
    return {'alpha': str(a), 'beta': str(b), 'mean': str(a/(a+b)),
            'variance': str(a*b/((a+b)**2*(a+b+1))), 'predictive_success': str(a/(a+b)),
            'model': 'iid_bernoulli_with_beta_prior', 'arithmetic': 'exact_rational'}


__all__ = ['posterior', 'predictive', 'beta_binomial']
