"""Bounded, transitive split audit of declared derivations and templates.

Identifiers are declarations, not inferred semantic equivalence or authenticated
provenance. External parents still connect siblings when their records are absent.
"""
from collections import defaultdict
from collections.abc import Mapping
from ..core.semantic_ir import fingerprint


def audit_lineage(entries, *, max_records=10000, max_links=100000):
    if type(max_records) is not int or not 1 <= max_records <= 100000:
        raise ValueError('Invalid record budget')
    if type(max_links) is not int or not 1 <= max_links <= 1000000:
        raise ValueError('Invalid link budget')
    rows, parent, owners = {}, {}, {}
    links = 0

    def identifier(value):
        if not isinstance(value, str) or not value.strip() or len(value) > 512:
            raise ValueError('Nonempty bounded identifiers required')
        return value

    def find(key):
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[max(a, b)] = min(a, b)

    for entry in entries:
        if len(rows) >= max_records:
            raise ValueError('Record budget exceeded')
        if not isinstance(entry, Mapping) or set(entry) != {'id', 'split', 'parents', 'groups'}:
            raise ValueError('Expected id, split, parents and groups')
        key = identifier(entry['id'])
        if key in rows or entry['split'] not in ('train', 'validation', 'test'):
            raise ValueError('Duplicate identifier or invalid split')
        if not isinstance(entry['parents'], (list, tuple)) or not isinstance(entry['groups'], Mapping):
            raise ValueError('Invalid lineage declarations')
        row = {'id': key, 'split': entry['split'], 'parents': [], 'groups': {}}
        find(key)
        for ancestor in entry['parents']:
            ancestor = identifier(ancestor)
            links += 1
            if links > max_links:
                raise ValueError('Link budget exceeded')
            row['parents'].append(ancestor)
            union(key, ancestor)
        for kind, values in entry['groups'].items():
            if kind not in ('template', 'semantic', 'source', 'derivation') or not isinstance(values, (list, tuple)):
                raise ValueError('Invalid group kind or values')
            row['groups'][kind] = []
            for value in values:
                value = identifier(value)
                links += 1
                if links > max_links:
                    raise ValueError('Link budget exceeded')
                row['groups'][kind].append(value)
                # Namespaces prevent a template named X matching source X.
                token = (kind, value)
                if token in owners:
                    union(key, owners[token])
                else:
                    owners[token] = key
            row['groups'][kind] = sorted(set(row['groups'][kind]))
        row['parents'] = sorted(set(row['parents']))
        rows[key] = row
    components = defaultdict(list)
    for key in sorted(rows):
        components[find(key)].append(key)
    conflicts = []
    for members in components.values():
        splits = sorted({rows[key]['split'] for key in members})
        if len(splits) > 1:
            conflicts.append({'members': members, 'splits': splits})
    manifest = [rows[key] for key in sorted(rows)]
    return {'schema_version': 1, 'manifest_id': fingerprint(manifest),
            'manifest': manifest, 'clean': not conflicts,
            'conflicts': sorted(conflicts, key=lambda row: row['members']),
            'record_count': len(rows), 'component_count': len(components),
            'scope': 'declared lineage and namespaced groups only',
            'provenance_authenticated': False,
            'undeclared_equivalence_excluded': False}


def verify_lineage_report(report):
    try:
        return audit_lineage(report['manifest']) == report
    except (ValueError, KeyError, TypeError):
        return False
