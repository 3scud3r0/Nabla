"""Deterministic family-diverse selection with explicit measured utility receipts."""
import math
from ..core.semantic_ir import fingerprint
from .difficulty import difficulty_profile


def build_curriculum(calibration, tasks, *, utility, limit):
    """Utility is a per-task observation with score and content-addressed evidence.

    Selection alternates families, ordering within each by observed utility. It
    does not claim improvement on held-out learners or causal training benefit.
    """
    tasks = tuple(tasks)
    profile = difficulty_profile(calibration, tasks)
    if type(limit) is not int or not 1 <= limit <= len(tasks) or set(utility) != {task.content_id for task in tasks}:
        raise ValueError('Bounded limit and utility for every supplied task required')
    queues = {}
    for row in profile['profiles']:
        observation = utility[row['task_id']]
        if set(observation) != {'score', 'evidence'} or type(observation['score']) not in (int, float) or not math.isfinite(observation['score']) or not observation['evidence'] or any(key != fingerprint(value) for key, value in observation['evidence'].items()):
            raise ValueError('Finite utility and content-addressed measurement evidence required')
        queues.setdefault(row['family'], []).append(row['task_id'])
    for queue in queues.values():
        queue.sort(key=lambda key: (-utility[key]['score'], key))
    selected = []
    while len(selected) < limit:
        for family in sorted(queues):
            if queues[family] and len(selected) < limit:
                selected.append(queues[family].pop(0))
    payload = {'schema_version': 1, 'profile_id': profile['profile_id'], 'selected_task_ids': selected,
               'utility': utility, 'limit': limit, 'policy': 'sorted_family_round_robin_then_observed_utility',
               'utility_scope': 'operator-supplied measurements; no causal or held-out learning claim'}
    return {**payload, 'curriculum_id': fingerprint(payload)}


def replay_curriculum(report, calibration, tasks):
    try:
        return report == build_curriculum(calibration, tasks, utility=report['utility'], limit=report['limit'])
    except (ValueError, TypeError, KeyError):
        return False
