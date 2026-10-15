"""Conditional empirical resource frontier, derived only from validated measurements."""
from ..core.semantic_ir import fingerprint
from .difficulty import validate_calibration


def resource_frontier(report, tasks):
    tasks = tuple(tasks)
    if not validate_calibration(report, tasks):
        raise ValueError('Invalid calibration evidence')
    rows = []
    for task in tasks:
        observations = [r for r in report['observations'] if r['task_id'] == task.content_id]
        successful = [r for r in observations if r['status'] == 'completed']
        rows.append({'task_id': task.content_id, 'family': task.family,
                     'minimum_verified_lines': min((r['executed_python_lines'] for r in successful), default=None),
                     'completed_strategies': sorted(r['strategy'] for r in successful),
                     'censored': len(successful) < len(observations)})
    rows.sort(key=lambda r: (r['minimum_verified_lines'] is None, r['minimum_verified_lines'] or 0, r['task_id']))
    payload = {'schema_version': 1, 'calibration_id': report['calibration_id'], 'rows': rows,
               'scope': 'measured solver and Python-line budget only; not intrinsic difficulty'}
    return {**payload, 'frontier_id': fingerprint(payload)}
