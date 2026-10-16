"""Finite Markov hitting events and moments over exact rational arithmetic.

Target states are stopped on first entry; they need not be absorbing in the
original chain. Unreachable targets and defective hitting probabilities remain
explicit. Conditional moments never stand in for unconditional finite means.
"""

from fractions import Fraction
from math import gcd

from ...core.semantic_ir import canonical_json, fingerprint, rational
from ..graph_theory.directed import strongly_connected_components
from ..linear_algebra import Matrix, solve_linear
from ..analysis.intervals import exact


def transition_matrix(transition):
    if not isinstance(transition, (list, tuple)) or not 1 <= len(transition) <= 24:
        raise ValueError('Transition matrix must have 1–24 states')
    size = len(transition)
    if any(not isinstance(row, (list, tuple)) or len(row) != size for row in transition):
        raise ValueError('Transition matrix must be square')
    rows = tuple(tuple(rational(value) for value in row) for row in transition)
    if any(value < 0 or value > 1 for row in rows for value in row):
        raise ValueError('Transition probabilities must lie in [0,1]')
    if any(sum(row, Fraction(0)) != 1 for row in rows):
        raise ValueError('Transition rows must sum exactly to one')
    return rows


def _solve(rows, rhs):
    if not rows:
        return ()
    solution = solve_linear(Matrix(tuple(tuple(value for value in row) for row in rows)), rhs)
    if solution.status != 'unique':
        raise ArithmeticError('Expected unique finite-chain linear system')
    values = tuple(exact(value) for value in solution.particular)
    if any(sum((a*b for a, b in zip(row, values)), Fraction(0)) != target
           for row, target in zip(rows, rhs)):
        raise ArithmeticError('Exact linear-system residual failed')
    return values


def _targets(targets, size):
    if not isinstance(targets, (list, tuple)) or not targets or len(targets) > size:
        raise ValueError('Nonempty target state list required')
    if any(type(value) is not int or not 0 <= value < size for value in targets):
        raise ValueError('Target indices must be valid integers')
    if len(set(targets)) != len(targets):
        raise ValueError('Duplicate target indices')
    return tuple(sorted(targets))


def _reachable_to_targets(rows, targets):
    reached = set(targets)
    while True:
        predecessors = {i for i, row in enumerate(rows)
                        if any(value > 0 and j in reached for j, value in enumerate(row))}
        if predecessors <= reached:
            return reached
        reached.update(predecessors)


def hitting_statistics(transition, targets):
    """Exact first-hit probabilities, conditional means and conditional variance.

    The hitting time is zero at target states. An unreachable target yields
    probability zero and undefined conditional moments. A probability below
    one gives infinite unconditional mean, represented by an explicit status.
    """
    rows = transition_matrix(transition)
    size = len(rows)
    targets = _targets(targets, size)
    reached = _reachable_to_targets(rows, targets)
    transient = tuple(sorted(reached-set(targets)))
    system = [[Fraction(i == j)-rows[state][other]
               for j, other in enumerate(transient)]
              for i, state in enumerate(transient)]
    rhs = [sum((rows[state][target] for target in targets), Fraction(0))
           for state in transient]
    probabilities = [Fraction(int(state in targets)) for state in range(size)]
    for state, value in zip(transient, _solve(system, rhs)):
        if not 0 < value <= 1:
            raise ArithmeticError('Invalid hitting probability')
        probabilities[state] = value
    # g_i = E[T 1_hit | X0=i]. Its recurrence is g = h + Qg.
    # This avoids dividing transition probabilities before elimination.
    g_solution = _solve(system, [probabilities[state] for state in transient])
    joint_first = [Fraction(0)]*size
    for state, value in zip(transient, g_solution):
        joint_first[state] = value
    # E[T² 1_hit] = h + 2Q E[T 1_hit] + Q E[T² 1_hit].
    second_rhs = [exact(probabilities[state] + 2*sum(
        (rows[state][other]*joint_first[other] for other in transient), Fraction(0)))
        for state in transient]
    joint_second = [Fraction(0)]*size
    for state, value in zip(transient, _solve(system, second_rhs)):
        joint_second[state] = value
    states = []
    for state in range(size):
        probability = probabilities[state]
        mean = exact(joint_first[state]/probability) if probability else None
        second = exact(joint_second[state]/probability) if probability else None
        variance = exact(second-mean*mean) if probability else None
        if variance is not None and variance < 0:
            raise ArithmeticError('Negative hitting-time variance')
        states.append({
            'state': state, 'probability': str(probability),
            'unconditional_mean_status': 'finite' if probability == 1 else 'infinite',
            'unconditional_mean': str(mean) if probability == 1 else None,
            'conditional_mean': None if mean is None else str(mean),
            'conditional_second_moment': None if second is None else str(second),
            'conditional_variance': None if variance is None else str(variance),
            'joint_first_moment': str(joint_first[state]),
            'joint_second_moment': str(joint_second[state]),
        })
    payload = {
        'profile': 'exact-markov-hitting-v1',
        'request': {'transition': [[str(v) for v in row] for row in rows], 'targets': list(targets)},
        'states': states,
        'reachable_states': sorted(reached), 'transient_subsystem': list(transient),
        'formal_proof': False,
        'scope': 'Finite rational chain, first entry into targets; conditional and unconditional moments are distinct',
    }
    return {**payload, 'certificate_id': fingerprint(payload)}


def verify_hitting_statistics(certificate):
    try:
        if not isinstance(certificate, dict) or len(canonical_json(certificate)) > 250_000:
            return False
        expected = hitting_statistics(**certificate['request'])
        return canonical_json(certificate) == canonical_json(expected)
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return False


def _period(rows, component):
    root = min(component)
    distance = {root: 0}
    frontier = [root]
    for state in frontier:
        for other in sorted(component):
            if rows[state][other] > 0 and other not in distance:
                distance[other] = distance[state]+1
                frontier.append(other)
    period = 0
    for state in component:
        for other in component:
            if rows[state][other] > 0:
                period = gcd(period, abs(distance[state]+1-distance[other]))
    if period < 1:
        raise ArithmeticError('Invalid recurrent-class period')
    return period


def stationary_classes(transition):
    """Extreme stationary distributions for every closed communicating class.

    All stationary distributions are convex mixtures of these extremes. A
    periodic class still has a stationary distribution; it does not imply
    convergence of the original step distributions.
    """
    rows = transition_matrix(transition)
    size = len(rows)
    graph = {state: [j for j, value in enumerate(row) if value > 0]
             for state, row in enumerate(rows)}
    components = sorted((tuple(sorted(c)) for c in strongly_connected_components(graph)))
    closed = [component for component in components
              if all(other in component or rows[state][other] == 0
                     for state in component for other in range(size))]
    results = []
    for component in closed:
        system = [[rows[state][other]-Fraction(state == other) for state in component]
                  for other in component[:-1]]
        system.append([Fraction(1)]*len(component))
        local = _solve(system, [Fraction(0)]*(len(component)-1)+[Fraction(1)])
        if any(value <= 0 for value in local):
            raise ArithmeticError('Closed irreducible class must have positive stationary mass')
        distribution = [Fraction(0)]*size
        for state, value in zip(component, local):
            distribution[state] = value
        if any(sum((distribution[i]*rows[i][j] for i in range(size)), Fraction(0)) != distribution[j]
               for j in range(size)):
            raise ArithmeticError('Stationary residual is nonzero')
        results.append({'states': list(component), 'period': _period(rows, component),
                        'distribution': [str(v) for v in distribution],
                        'mean_return_times': {str(state): str(exact(1/value))
                                              for state, value in zip(component, local)}})
    recurrent = {state for component in closed for state in component}
    payload = {
        'profile': 'exact-markov-stationary-classes-v1',
        'request': {'transition': [[str(v) for v in row] for row in rows]},
        'communicating_classes': [list(c) for c in components],
        'closed_classes': results,
        'transient_states': sorted(set(range(size))-recurrent),
        'unique_stationary_distribution': len(results) == 1,
        'formal_proof': False,
        'scope': 'Exact closed-class stationary extreme points; periodicity is not convergence',
    }
    return {**payload, 'certificate_id': fingerprint(payload)}


def verify_stationary_classes(certificate):
    try:
        if not isinstance(certificate, dict) or len(canonical_json(certificate)) > 250_000:
            return False
        expected = stationary_classes(**certificate['request'])
        return canonical_json(certificate) == canonical_json(expected)
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return False


def discounted_rewards(transition, rewards, discount):
    """Solve v=r+γPv exactly for 0<=γ<1 and return independently checked residuals."""
    rows = transition_matrix(transition)
    size = len(rows)
    if not isinstance(rewards, (list, tuple)) or len(rewards) != size:
        raise ValueError('Reward vector must match the state space')
    rewards = tuple(rational(value) for value in rewards)
    discount = rational(discount)
    if not 0 <= discount < 1:
        raise ValueError('Discount must lie in [0,1)')
    system = [[Fraction(i == j)-discount*rows[i][j] for j in range(size)] for i in range(size)]
    values = _solve(system, rewards)
    residuals = [exact(values[i]-rewards[i]-discount*sum(
        (rows[i][j]*values[j] for j in range(size)), Fraction(0))) for i in range(size)]
    if any(residuals):
        raise ArithmeticError('Discounted reward residual is nonzero')
    payload = {
        'profile': 'exact-markov-discounted-reward-v1',
        'request': {'transition': [[str(v) for v in row] for row in rows],
                    'rewards': [str(v) for v in rewards], 'discount': str(discount)},
        'values': [str(v) for v in values], 'residuals': [str(v) for v in residuals],
        'sup_norm_bound': str(exact(max(abs(v) for v in rewards)/(1-discount))),
        'formal_proof': False,
    }
    return {**payload, 'certificate_id': fingerprint(payload)}


def verify_discounted_rewards(certificate):
    try:
        if not isinstance(certificate, dict) or len(canonical_json(certificate)) > 250_000:
            return False
        expected = discounted_rewards(**certificate['request'])
        return canonical_json(certificate) == canonical_json(expected)
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return False
