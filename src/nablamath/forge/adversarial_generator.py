"""Controlled RHS perturbations expose reuse of stale answers; no hardness claim."""
from ..core.semantic_ir import rational, fingerprint
from ..verify.trace import verify_candidate
from .task_spec import TaskSpec
from .solvers import solve_task


def stale_solution_challenge(task, *, row=0, delta='1'):
    if task.family != 'linear_system' or type(row) is not int or not 0 <= row < task.size:
        raise ValueError('Linear system and valid row required')
    delta = rational(delta)
    if delta == 0:
        raise ValueError('Nonzero perturbation required')
    original = solve_task(task)
    problem = task.problem
    problem['rhs'][row] = str(rational(problem['rhs'][row]) + delta)
    changed = TaskSpec('linear_system', problem, task.size)
    stale = verify_candidate(changed, original).to_data()
    answer = solve_task(changed)
    verified = verify_candidate(changed, answer).to_data()
    if stale['valid'] or not verified['valid']:
        raise ArithmeticError('Adversarial challenge invariant violated')
    payload = {'schema_version': 1, 'profile': 'stale-rhs-v1', 'source_id': task.content_id,
               'task': changed.to_data(), 'row': row, 'delta': str(delta),
               'stale_candidate': original, 'stale_verification': stale,
               'solution': answer, 'verification': verified, 'hardness_established': False}
    return {**payload, 'challenge_id': fingerprint(payload)}


def replay_challenge(report, source_task):
    """Reexecute perturbation, solution and both verifier decisions."""
    try:
        return stale_solution_challenge(source_task, row=report['row'], delta=report['delta']) == report
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return False
