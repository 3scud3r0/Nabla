"""Replayable semantic corpus comparison; absence never establishes global novelty."""
from ..core.semantic_ir import fingerprint
from .deduplicate import semantic_fingerprint
from .task_spec import TaskSpec


class NoveltyIndex:
    def __init__(self, tasks=()):
        self._tasks = {}
        for task in tasks:
            self.add(task)

    def add(self, task):
        if not isinstance(task, TaskSpec):
            raise ValueError('TaskSpec required')
        self._tasks[task.content_id] = task

    def compare(self, task):
        key = semantic_fingerprint(task)
        matches = sorted(t.content_id for t in self._tasks.values() if semantic_fingerprint(t) == key)
        return {'task_id': task.content_id, 'local_matches': matches,
                'corpus_id': self.to_data()['corpus_id'], 'global_novelty_established': False,
                'status': 'local_equivalent_found' if matches else 'novelty_not_established'}

    def to_data(self):
        payload = {'schema_version': 1, 'tasks': [self._tasks[k].to_data() for k in sorted(self._tasks)]}
        return {**payload, 'corpus_id': fingerprint(payload)}

    @classmethod
    def from_data(cls, data):
        if not isinstance(data, dict) or set(data) != {'schema_version', 'tasks', 'corpus_id'} or data['schema_version'] != 1:
            raise ValueError('Invalid corpus schema')
        if not isinstance(data['tasks'], list) or len(data['tasks']) > 10000:
            raise ValueError('Corpus size invalid')
        result = cls(TaskSpec.from_data(t) for t in data['tasks'])
        if result.to_data() != data:
            raise ValueError('Corpus not canonical or corrupted')
        return result
