"""Exact block composition of independently witnessed linear systems (profile v1)."""
from ..core.semantic_ir import canonical_json, fingerprint
from ..verify.trace import verify_candidate
from .task_spec import TaskSpec, GeneratedProblem


def compose_linear_systems(components):
    components = tuple(components)
    if not 2 <= len(components) <= 8:
        raise ValueError('Require two to eight components')
    if any(not isinstance(c, GeneratedProblem) or c.task.family != 'linear_system' for c in components):
        raise ValueError('Only witnessed linear systems supported')
    size = sum(c.task.size for c in components)
    if size > 8:
        raise ValueError('Composite dimension exceeds eight')
    rows = [['0'] * size for _ in range(size)]
    rhs, solution, offset = [], [], 0
    for component in components:
        if not verify_candidate(component.task, component.witness).valid:
            raise ValueError('Invalid component witness')
        problem = component.task.problem
        for i, row in enumerate(problem['matrix']):
            rows[offset+i][offset:offset+component.task.size] = row
        rhs.extend(problem['rhs'])
        solution.extend(component.witness['solution'])
        offset += component.task.size
    task = TaskSpec('linear_system', {'matrix': rows, 'rhs': rhs}, size)
    witness = {'solution': solution}
    if not verify_candidate(task, witness).valid:
        raise ArithmeticError('Composite witness rejected')
    return {'schema_version': 1, 'profile': 'block-linear-v1', 'task': task.to_data(),
            'witness': witness, 'component_ids': [c.task.content_id for c in components],
            'composition_id': fingerprint({'task': task.to_data(), 'components': [c.task.content_id for c in components]})}


def replay_composition(report, components):
    """Rebuild from source components rather than trusting the receipt digest."""
    try:
        return compose_linear_systems(components) == report
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return False
