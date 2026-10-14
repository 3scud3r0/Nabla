"""Training-only deterministic curriculum; test labels never tune difficulty."""
from ..core.semantic_ir import fingerprint


def curriculum(samples, *, seed=0):
    samples = tuple(samples)
    if type(seed) is not int or len(samples) > 10000:
        raise ValueError('Seed ou orçamento inválido')
    if any(s.record.to_data()['split'] != 'train' for s in samples):
        raise ValueError('Currículo só aceita treino')
    ranks = {'easy': 0, 'medium': 1, 'hard': 2, 'uncalibrated': 3}
    return tuple(sorted(samples, key=lambda s: (
        ranks[s.record.to_data()['difficulty']['label']], s.record.task.size,
        fingerprint({'seed': seed, 'task_id': s.record.task.content_id}))))
