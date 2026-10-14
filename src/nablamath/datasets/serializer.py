"""Strict versioned JSONL serialization; all imported solutions are rechecked."""
import json
from ..core.semantic_ir import canonical_json
from .schema import ScientificRecord


def dumps(records):
    return ''.join(canonical_json(r.to_data())+'\n' for r in records)


def loads(text, *, max_records=10000):
    if len(text.encode()) > 64 * 1024 * 1024:
        raise ValueError('Dataset excede 64 MiB')
    lines = text.splitlines()
    if not lines or len(lines) > max_records or any(not line.strip() for line in lines):
        raise ValueError('Número de registros inválido')
    return tuple(ScientificRecord.from_data(json.loads(line)) for line in lines)
