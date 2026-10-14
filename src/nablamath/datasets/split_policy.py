"""Family-held-out split policy; seed variants cannot cross reserved partitions."""
from dataclasses import dataclass
from .splits import SplitPolicy
from .semantic_fingerprint import semantic_fingerprint


def assign(records, policy=None):
    policy = policy or SplitPolicy()
    return tuple(record.with_split(policy.split(record.task)) for record in records)


def audit(records):
    seen, overlaps = {}, []
    for record in records:
        split = record.to_data()['split']
        if split == 'unassigned':
            overlaps.append({'scope': 'unassigned', 'key': record.content_id})
        for scope, key in [('semantic', semantic_fingerprint(record)), ('family', record.task.family)]:
            index = (scope, key)
            if index in seen and seen[index] != split:
                overlaps.append({'scope': scope, 'key': key})
            seen[index] = split
    return {'clean': not overlaps, 'overlaps': overlaps, 'scope': 'local_semantics_and_families'}
