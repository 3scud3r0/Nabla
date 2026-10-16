"""Exact finite probability, discrete inference and rational Markov chains.

The module deliberately excludes continuous entropy, numerical quadrature and
empirical claims that would require approximation or external data. All mass
functions are normalized with rational identities, not float tolerances.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import comb
from typing import Sequence

from .laboratory import Polynomial, RationalMatrix, rational


MAX_SUPPORT = 512


@dataclass(frozen=True)
class FiniteDistribution:
    """An integer-valued finite probability law, mass exactly summing to one."""
    masses: tuple[tuple[int, Fraction], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.masses, (tuple, list)) or not 1 <= len(self.masses) <= MAX_SUPPORT:
            raise ValueError("Distribution support must have 1..512 entries")
        seen = set()
        cleaned = []
        for x, raw in self.masses:
            if type(x) is not int or x in seen:
                raise ValueError("Outcomes must be distinct integers")
            seen.add(x)
            mass = rational(raw)
            if mass < 0:
                raise ValueError("Probabilities cannot be negative")
            if mass:
                cleaned.append((x, mass))
        if sum((p for _, p in cleaned), Fraction(0)) != 1:
            raise ValueError("Probabilities must sum exactly to one")
        object.__setattr__(self, "masses", tuple(sorted(cleaned)))

    @classmethod
    def from_weights(cls, weights: dict[int, object]) -> FiniteDistribution:
        if not isinstance(weights, dict) or not 1 <= len(weights) <= MAX_SUPPORT:
            raise ValueError("Invalid distribution weight map")
        if any(type(x) is not int for x in weights):
            raise TypeError("Outcomes must be integers")
        parsed = {x: rational(p) for x, p in weights.items()}
        if any(w < 0 for w in parsed.values()):
            raise ValueError("Negative distribution weight")
        total = sum(parsed.values(), Fraction(0))
        if total <= 0:
            raise ValueError("At least one weight must be positive")
        return cls(tuple((x, w / total) for x, w in parsed.items()))

    @classmethod
    def certain(cls, outcome: int) -> FiniteDistribution:
        if type(outcome) is not int:
            raise TypeError("Certain outcome must be integer")
        return cls(((outcome, Fraction(1)),))

    @property
    def expected_value(self) -> Fraction:
        return sum((x * p for x, p in self.masses), Fraction(0))

    @property
    def variance(self) -> Fraction:
        mean = self.expected_value
        return sum(((x - mean)**2 * p for x, p in self.masses), Fraction(0))

    def raw_moment(self, order: int) -> Fraction:
        if type(order) is not int or not 0 <= order <= 16:
            raise ValueError("Moment order outside [0,16]")
        return sum((x**order * p for x, p in self.masses), Fraction(0))

    def central_moment(self, order: int) -> Fraction:
        if type(order) is not int or not 0 <= order <= 16:
            raise ValueError("Moment order outside [0,16]")
        mu = self.expected_value
        return sum(((x-mu)**order * p for x, p in self.masses), Fraction(0))

    def probability(self, outcome: int) -> Fraction:
        if type(outcome) is not int:
            raise TypeError("Outcome must be integer")
        return dict(self.masses).get(outcome, Fraction(0))

    def cdf(self, threshold: int | Fraction | str) -> Fraction:
        threshold = rational(threshold)
        return sum((p for x, p in self.masses if x <= threshold), Fraction(0))

    def quantile(self, probability: object) -> int:
        """Left-continuous generalized inverse F^-1(q), 0<q<=1."""
        q = rational(probability)
        if not 0 < q <= 1:
            raise ValueError("Quantile probability must lie in (0,1]")
        total = Fraction(0)
        for x, p in self.masses:
            total += p
            if total >= q:
                return x
        raise ArithmeticError("Distribution normalization invariant failed")

    def shift(self, offset: int) -> FiniteDistribution:
        if type(offset) is not int:
            raise TypeError("Offset must be integer")
        return FiniteDistribution(tuple((x+offset, p) for x, p in self.masses))

    def scale(self, factor: int) -> FiniteDistribution:
        if type(factor) is not int:
            raise TypeError("Scale factor must be integer")
        masses: dict[int, Fraction] = {}
        for x, p in self.masses:
            mapped = x * factor
            masses[mapped] = masses.get(mapped, Fraction(0)) + p
        return FiniteDistribution(tuple(masses.items()))

    def convolve(self, other: FiniteDistribution) -> FiniteDistribution:
        """Distribution of X+Y, assuming INDEPENDENT X and Y."""
        if not isinstance(other, FiniteDistribution):
            raise TypeError("Convolution requires another finite distribution")
        masses: dict[int, Fraction] = {}
        for x, px in self.masses:
            for y, py in other.masses:
                masses[x+y] = masses.get(x+y, Fraction(0)) + px*py
        if len(masses) > MAX_SUPPORT:
            raise ValueError("Convolution exceeds support limit")
        return FiniteDistribution(tuple(masses.items()))

    def iid_sum(self, count: int) -> FiniteDistribution:
        if type(count) is not int or not 0 <= count <= 128:
            raise ValueError("IID sum count must be in [0,128]")
        result, base = FiniteDistribution.certain(0), self
        while count:
            if count & 1:
                result = result.convolve(base)
            count >>= 1
            if count:
                base = base.convolve(base)
        return result

    def probability_generating_polynomial(self) -> Polynomial:
        """PGF for supports contained in 0..128 (nonnegative integer outcomes)."""
        if min(x for x, _ in self.masses) < 0 or max(x for x, _ in self.masses) > 128:
            raise ValueError("PGF polynomial needs exponents in [0,128]")
        values = dict(self.masses)
        return Polynomial(tuple(values.get(i, Fraction(0))
                                for i in range(max(values)+1)))

    def total_variation(self, other: FiniteDistribution) -> Fraction:
        """Exact total-variation distance: half the L1 distance."""
        if not isinstance(other, FiniteDistribution):
            raise TypeError("Expected a finite distribution")
        keys = set(dict(self.masses)) | set(dict(other.masses))
        return sum((abs(self.probability(x)-other.probability(x))
                    for x in keys), Fraction(0)) / 2

    def to_data(self) -> dict:
        return {
            "mass": [[x, str(p)] for x, p in self.masses],
            "expectation": str(self.expected_value),
            "variance": str(self.variance),
            "arithmetic": "exact-rational",
        }


@dataclass(frozen=True)
class JointDistribution:
    """Integer-valued (X,Y) joint probability law with exact marginals."""
    masses: tuple[tuple[int, int, Fraction], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.masses, (tuple, list)) or not 1 <= len(self.masses) <= MAX_SUPPORT:
            raise ValueError("Joint support outside budget")
        cleaned, seen = [], set()
        for x, y, raw in self.masses:
            if type(x) is not int or type(y) is not int or (x,y) in seen:
                raise ValueError("Joint outcomes must be distinct integer pairs")
            seen.add((x, y))
            p = rational(raw)
            if p < 0:
                raise ValueError("Negative probability")
            if p:
                cleaned.append((x, y, p))
        if sum((p for _, _, p in cleaned), Fraction(0)) != 1:
            raise ValueError("Joint distribution must be normalized")
        object.__setattr__(self, "masses", tuple(sorted(cleaned)))

    def marginal_x(self) -> FiniteDistribution:
        weights: dict[int, Fraction] = {}
        for x, _, p in self.masses:
            weights[x] = weights.get(x, Fraction(0)) + p
        return FiniteDistribution(tuple(weights.items()))

    def marginal_y(self) -> FiniteDistribution:
        weights: dict[int, Fraction] = {}
        for _, y, p in self.masses:
            weights[y] = weights.get(y, Fraction(0)) + p
        return FiniteDistribution(tuple(weights.items()))

    def covariance(self) -> Fraction:
        mu_x, mu_y = self.marginal_x().expected_value, self.marginal_y().expected_value
        return sum(((x-mu_x)*(y-mu_y)*p for x,y,p in self.masses), Fraction(0))

    def independent(self) -> bool:
        mx = self.marginal_x()
        my = self.marginal_y()
        table = {(x,y): p for x,y,p in self.masses}
        return all(table.get((x,y), 0) == px*py
                   for x,px in mx.masses for y,py in my.masses)

    def conditional_y_given_x(self, observed_x: int) -> FiniteDistribution:
        if type(observed_x) is not int:
            raise TypeError("Conditioning outcome must be integer")
        weighted = {y:p for x,y,p in self.masses if x == observed_x}
        if not weighted:
            raise ValueError("Cannot condition on zero-probability observation")
        return FiniteDistribution.from_weights(weighted)

    def to_data(self) -> dict:
        return {
            "joint_mass": [[x,y,str(p)] for x,y,p in self.masses],
            "marginal_x": self.marginal_x().to_data(),
            "marginal_y": self.marginal_y().to_data(),
            "covariance": str(self.covariance()),
            "independent": self.independent(),
        }


def binomial_law(trials: int, success_probability: object) -> FiniteDistribution:
    """Exact binomial mass, 0 <= n <= 128, p in [0,1]."""
    if type(trials) is not int or not 0 <= trials <= 128:
        raise ValueError("Binomial trials outside [0,128]")
    p = rational(success_probability)
    if not 0 <= p <= 1:
        raise ValueError("Success probability outside [0,1]")
    return FiniteDistribution(tuple(
        (k, Fraction(comb(trials, k))*p**k*(1-p)**(trials-k))
        for k in range(trials+1)
    ))


def poisson_binomial_law(probabilities: Sequence[object]) -> FiniteDistribution:
    """Distribution of independent non-identical Bernoulli variables."""
    if not isinstance(probabilities, (tuple, list)) or not 1 <= len(probabilities) <= 128:
        raise ValueError("Expected 1..128 Bernoulli probabilities")
    values = tuple(rational(p) for p in probabilities)
    if any(not 0 <= p <= 1 for p in values):
        raise ValueError("Bernoulli probability outside [0,1]")
    mass = [Fraction(1)]
    for p in values:
        next_mass = [Fraction(0)] * (len(mass)+1)
        for i, q in enumerate(mass):
            next_mass[i] += q*(1-p)
            next_mass[i+1] += q*p
        mass = next_mass
    return FiniteDistribution(tuple(enumerate(mass)))


def hypergeometric_probability(population: int, successes: int,
                               draws: int, observed: int) -> Fraction:
    """Exactly P(X=k) when sampling WITHOUT replacement."""
    if any(type(x) is not int for x in (population, successes, draws, observed)):
        raise TypeError("Hypergeometric parameters must be integers")
    if not 1 <= population <= 512 or not 0 <= successes <= population or not 0 <= draws <= population:
        raise ValueError("Hypergeometric population outside bounded domain")
    if not 0 <= observed <= draws or observed > successes or draws-observed > population-successes:
        return Fraction(0)
    return rational(Fraction(
        comb(successes, observed)*comb(population-successes,draws-observed),
        comb(population, draws),
    ))


def dirichlet_predictive(
    alpha: Sequence[object], counts: Sequence[int]
) -> dict:
    """Finite categorical Dirichlet conjugacy: posterior mean and predictive."""
    if not isinstance(alpha, (tuple, list)) or not isinstance(counts, (tuple, list)):
        raise ValueError("Parameters must be finite sequences")
    if not 1 <= len(alpha) == len(counts) <= 128:
        raise ValueError("Dirichlet dimensions must agree within budget")
    prior = tuple(rational(x) for x in alpha)
    if any(p <= 0 for p in prior) or any(type(k) is not int or not 0 <= k <= 10**6 for k in counts):
        raise ValueError("All concentrations positive and counts nonnegative")
    posterior = tuple(a+k for a,k in zip(prior,counts))
    mass = sum(posterior, Fraction(0))
    predictive = tuple(p/mass for p in posterior)
    if sum(predictive, Fraction(0)) != 1:
        raise ArithmeticError("Posterior normalization failed")
    return {
        "posterior_alpha": [str(p) for p in posterior],
        "predictive": [str(p) for p in predictive],
        "sample_size": sum(counts),
        "arithmetic": "exact-rational conjugate model",
    }


def unique_markov_stationary(transition: Sequence[Sequence[object]]) -> dict:
    """Unique stationary row distribution of a finite rational stochastic matrix.

    Reject chains with more than one stationary law. This is a *uniqueness*
    contract, not a convergence/mixing-time claim.
    """
    matrix = RationalMatrix(tuple(tuple(row) for row in transition))
    n, cols = matrix.shape
    if n > 31:
        raise ValueError("Stationary calculation limited to 31 states by augmented matrix budget")
    if n != cols or (n == 1 and matrix.rows[0][0] != 1):
        raise ValueError("Expected a square stochastic transition matrix")
    if any(any(p < 0 or p > 1 for p in row) or sum(row) != 1 for row in matrix.rows):
        raise ValueError("Transition rows must be stochastic")
    rows = []
    for j in range(n-1):
        rows.append(tuple(matrix.rows[i][j] - (1 if i == j else 0)
                          for i in range(n)))
    rows.append((1,)*n)
    solution = RationalMatrix(tuple(rows)).solve((0,)*(n-1)+(1,))
    if solution.nullspace:
        raise ValueError("Stationary distribution is not unique")
    pi = solution.particular
    if any(p < 0 for p in pi):
        raise ArithmeticError("Stationary distribution negative")
    for j in range(n):
        if sum((pi[i]*matrix.rows[i][j] for i in range(n)),Fraction(0)) != pi[j]:
            raise ArithmeticError("Stationary residual nonzero")
    return {
        "stationary": [str(p) for p in pi],
        "residual": "0",
        "uniqueness": True,
        "convergence_claimed": False,
    }


def markov_distribution_after(
    transition: Sequence[Sequence[object]], initial: Sequence[object],
    steps: int,
) -> dict:
    """Exact finite-state propagation of a distribution by repeated multiplication."""
    matrix = RationalMatrix(tuple(tuple(row) for row in transition))
    n, cols = matrix.shape
    if n != cols or len(initial) != n or type(steps) is not int or not 0 <= steps <= 256:
        raise ValueError("Markov shape, initial distribution or steps invalid")
    if any(any(x < 0 or x > 1 for x in row) or sum(row) != 1 for row in matrix.rows):
        raise ValueError("Expected row-stochastic matrix")
    distribution = [rational(x) for x in initial]
    if any(x < 0 for x in distribution) or sum(distribution) != 1:
        raise ValueError("Initial distribution must sum to one")
    for _ in range(steps):
        distribution = [
            rational(sum((distribution[i]*matrix.rows[i][j] for i in range(n)),
                         Fraction(0))) for j in range(n)
        ]
    if sum(distribution) != 1 or any(x < 0 for x in distribution):
        raise ArithmeticError("Markov probability conservation failed")
    return {
        "distribution": [str(p) for p in distribution],
        "steps": steps,
        "mass_conservation": True,
    }


__all__ = [
    "FiniteDistribution", "JointDistribution", "binomial_law",
    "poisson_binomial_law", "hypergeometric_probability",
    "dirichlet_predictive", "unique_markov_stationary",
    "markov_distribution_after",
]
