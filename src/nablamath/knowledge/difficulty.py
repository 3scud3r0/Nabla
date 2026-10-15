"""Knowledge-facing difficulty profiles backed by replayed solver observations."""
from ..core.semantic_ir import fingerprint
from ..forge.difficulty import validate_calibration


def difficulty_profile(calibration, tasks):
    tasks = tuple(tasks)
    if not validate_calibration(calibration, tasks):
        raise ValueError('Calibration cannot be replayed against supplied tasks')
    rows = []
    for task in tasks:
        observations = [row for row in calibration['observations'] if row['task_id'] == task.content_id]
        rows.append({'task_id': task.content_id, 'family': task.family,
                     'label': calibration['ratings'][task.content_id]['label'],
                     'verified_successes': sum(row['status'] == 'completed' for row in observations),
                     'attempts': len(observations),
                     'budgets': sorted({row['budget'] for row in observations})})
    payload = {'schema_version': 1, 'calibration_id': calibration['calibration_id'],
               'profiles': rows, 'scope': 'supplied tasks, measured Python interpreter, declared solver versions only'}
    return {**payload, 'profile_id': fingerprint(payload)}
