"""Bounded, transitive leakage audit for declared dataset identities.

This module computes connected components of records linked by exact identity,
verified local semantic identity, or explicit lineage. A shared unknown ancestor
still connects its descendants. It does not infer unrecorded dependencies or
mathematical equivalences beyond the existing Forge semantic fingerprint.

All supplied records must be well formed. Invalid identity declarations are
errors, rather than evidence of a clean dataset. The optional embedded TaskSpec
is re-parsed and its content and semantic identifiers are independently checked.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from ..core.semantic_ir import fingerprint
from ..forge.deduplicate import semantic_fingerprint
from ..forge.task_spec import TaskSpec

SPLITS = frozenset({'train', 'validation', 'test'})


def _identifier(value, field):
    if (not isinstance(value, str) or len(value) != 64
            or any(c not in '0123456789abcdef' for c in value)):
        raise ValueError(f'{field} must be a lowercase SHA-256 identifier')
    return value


def _bounded_integer(value, field, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(f'{field} outside supported bounds')
    return value


@dataclass(frozen=True)
class LeakageRecord:
    """One occurrence in a partition, with separate exact and semantic namespaces."""

    record_id: str
    split: str
    semantic_id: str
    parents: tuple[str, ...] = ()

    def __post_init__(self):
        _identifier(self.record_id, 'record_id')
        _identifier(self.semantic_id, 'semantic_id')
        if self.split not in SPLITS:
            raise ValueError('Unknown dataset partition')
        if not isinstance(self.parents, (tuple, list)) or len(self.parents) > 128:
            raise ValueError('At most 128 lineage parents supported')
        normalized = tuple(_identifier(p, 'parent') for p in self.parents)
        if len(set(normalized)) != len(normalized):
            raise ValueError('Duplicate lineage parents')
        if self.record_id in normalized:
            raise ValueError('A record cannot list itself as a parent')
        object.__setattr__(self, 'parents', tuple(sorted(normalized)))

    def to_data(self):
        return {
            'record_id': self.record_id,
            'split': self.split,
            'semantic_id': self.semantic_id,
            'parents': list(self.parents),
        }

    @classmethod
    def from_data(cls, data):
        if not isinstance(data, Mapping):
            raise ValueError('Record mapping required')
        permitted = {'record_id', 'split', 'semantic_id', 'parents', 'task'}
        if set(data) - permitted or not {'record_id', 'split', 'semantic_id'} <= set(data):
            raise ValueError('Unexpected or missing leakage record fields')
        result = cls(data['record_id'], data['split'], data['semantic_id'], data.get('parents', ()))
        if 'task' in data:
            task = TaskSpec.from_data(data['task'])
            if task.content_id != result.record_id:
                raise ValueError('Embedded task does not match exact identifier')
            if semantic_fingerprint(task) != result.semantic_id:
                raise ValueError('Embedded task does not match semantic identifier')
        return result


class _DisjointSet:
    """Union by size with path compression; identities carry explicit namespaces."""

    def __init__(self, max_nodes):
        self.parents = {}
        self.sizes = {}
        self.max_nodes = max_nodes

    def add(self, node):
        if node in self.parents:
            return
        if len(self.parents) == self.max_nodes:
            raise ValueError('Identity graph exceeds node limit')
        self.parents[node] = node
        self.sizes[node] = 1

    def find(self, node):
        root = node
        while self.parents[root] != root:
            root = self.parents[root]
        while node != root:
            parent = self.parents[node]
            self.parents[node] = root
            node = parent
        return root

    def union(self, left, right):
        self.add(left)
        self.add(right)
        a, b = self.find(left), self.find(right)
        if a == b:
            return
        if self.sizes[a] < self.sizes[b]:
            a, b = b, a
        self.parents[b] = a
        self.sizes[a] += self.sizes[b]


class LeakageAuditor:
    """Incremental ingestion with deterministic full-component reports.

    Memory is bounded by explicit record and graph limits. The object is local
    and does not publish records or query external corpora. ``add`` validates an
    entire record before changing state, including a conservative graph budget.
    """

    def __init__(self, *, max_records=100000, max_nodes=400000):
        self.max_records = _bounded_integer(max_records, 'max_records', 1, 1000000)
        self.max_nodes = _bounded_integer(max_nodes, 'max_nodes', 2, 4000000)
        self._records = []
        self._graph = _DisjointSet(self.max_nodes)
        self._declarations = {}

    def add(self, value):
        record = value if isinstance(value, LeakageRecord) else LeakageRecord.from_data(value)
        if len(self._records) == self.max_records:
            raise ValueError('Record limit exceeded')
        declaration = (record.semantic_id, record.parents)
        previous = self._declarations.get(record.record_id)
        if previous is not None and previous != declaration:
            raise ValueError('Conflicting semantic or lineage declarations for exact identity')
        exact = ('exact', record.record_id)
        semantic = ('semantic', record.semantic_id)
        lineage = [('exact', parent) for parent in record.parents]
        missing = {node for node in [exact, semantic, *lineage] if node not in self._graph.parents}
        if len(self._graph.parents) + len(missing) > self.max_nodes:
            raise ValueError('Identity graph exceeds node limit')
        # No mutation precedes the validation and budget checks above.
        self._graph.union(exact, semantic)
        for parent in lineage:
            self._graph.union(exact, parent)
        self._declarations[record.record_id] = declaration
        self._records.append(record)

    def extend(self, records: Iterable):
        """Ingest incrementally; earlier valid additions survive later errors."""
        for record in records:
            self.add(record)
        return self

    def report(self):
        groups = {}
        for record in self._records:
            root = self._graph.find(('exact', record.record_id))
            groups.setdefault(root, []).append(record)
        components = []
        for records in groups.values():
            splits = sorted({r.split for r in records})
            ids = sorted({r.record_id for r in records})
            semantics = sorted({r.semantic_id for r in records})
            parents = sorted({p for r in records for p in r.parents})
            if len(splits) < 2:
                continue
            components.append({
                'component_id': fingerprint({'record_ids': ids, 'semantic_ids': semantics, 'parents': parents}),
                'record_ids': ids,
                'semantic_ids': semantics,
                'declared_parents': parents,
                'splits': splits,
                'occurrences': len(records),
                'reasons': self._reasons(records),
            })
        components.sort(key=lambda item: item['component_id'])
        payload = {
            'schema_version': 1,
            'clean': not components,
            'records_checked': len(self._records),
            'unique_exact_ids': len(self._declarations),
            'identity_nodes': len(self._graph.parents),
            'cross_split_components': components,
            'scope': 'exact, declared local semantic identities and transitive declared lineage',
            'hidden_equivalences_detected': False,
        }
        return {**payload, 'audit_id': fingerprint(payload)}

    @staticmethod
    def _reasons(records):
        exact, semantic = {}, {}
        for record in records:
            exact.setdefault(record.record_id, set()).add(record.split)
            semantic.setdefault(record.semantic_id, set()).add(record.split)
        reasons = []
        if any(len(splits) > 1 for splits in exact.values()):
            reasons.append('exact_identity')
        if any(len(splits) > 1 for splits in semantic.values()):
            reasons.append('semantic_identity')
        if any(r.parents for r in records):
            reasons.append('declared_lineage')
        return reasons

    def to_data(self):
        records = sorted((r.to_data() for r in self._records),
                         key=lambda r: (r['record_id'], r['split'], r['semantic_id'], r['parents']))
        payload = {
            'schema_version': 1,
            'max_records': self.max_records,
            'max_nodes': self.max_nodes,
            'records': records,
        }
        return {**payload, 'snapshot_id': fingerprint(payload)}

    @classmethod
    def from_data(cls, data):
        expected = {'schema_version', 'max_records', 'max_nodes', 'records', 'snapshot_id'}
        if not isinstance(data, dict) or set(data) != expected or type(data['schema_version']) is not int or data['schema_version'] != 1:
            raise ValueError('Invalid auditor snapshot')
        if not isinstance(data['records'], list):
            raise ValueError('Snapshot records must be a list')
        auditor = cls(max_records=data['max_records'], max_nodes=data['max_nodes'])
        auditor.extend(data['records'])
        if auditor.to_data() != data:
            raise ValueError('Snapshot checksum or canonical order mismatch')
        return auditor


def audit_records(records, *, max_records=100000, max_nodes=400000):
    return LeakageAuditor(max_records=max_records, max_nodes=max_nodes).extend(records).report()


def replay_audit(report, records):
    """Recompute connectivity rather than trusting a report's digest."""
    try:
        return audit_records(records) == report
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return False
