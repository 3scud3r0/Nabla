"""Deduplicate, preserve rejection reasons, partition and recheck candidates."""
from .schema import ScientificRecord
from .semantic_fingerprint import semantic_fingerprint
from .split_policy import assign
from .quality_gate import quality_gate


def curate(candidates, *, policy=None, asset_root=None):
    accepted, rejected, seen = [], [], set()
    for index, data in enumerate(candidates):
        try:
            record = data if isinstance(data, ScientificRecord) else ScientificRecord.from_data(data)
            key = semantic_fingerprint(record)
            if key in seen:
                raise ValueError('duplicate_semantics')
            if not quality_gate([record], asset_root=asset_root, require_partitions=False)['accepted']:
                raise ValueError('quality_gate_rejected')
            seen.add(key)
            accepted.append(record)
        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
            rejected.append({'index': index, 'reason': str(exc)})
    assigned = assign(accepted, policy)
    report = quality_gate(assigned, asset_root=asset_root)
    return assigned, {**report, 'rejected': rejected}
