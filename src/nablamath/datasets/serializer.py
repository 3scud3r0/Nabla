"""Strict versioned JSONL serialization; all imported solutions are rechecked."""
import json
from ..core.semantic_ir import canonical_json
from .schema import ScientificRecord
from .research_record import parse_record


def dumps(records):
    return ''.join(canonical_json(r.to_data())+'\n' for r in records)


def loads(text, *, max_records=10000):
    if len(text.encode()) > 64 * 1024 * 1024:
        raise ValueError('Dataset excede 64 MiB')
    lines = text.splitlines()
    if not lines or len(lines) > max_records or any(not line.strip() for line in lines):
        raise ValueError('Número de registros inválido')
    return tuple(parse_record(json.loads(line)) for line in lines)


def iter_load(stream, *, max_records=10000, max_line_bytes=4*1024*1024,
              max_total_bytes=64*1024*1024):
    """Bounded binary JSONL iterator; validates each record before yielding.

    Consumers requiring all-or-nothing import must stage the yielded records in
    their own transaction. A later invalid line can follow earlier valid rows.
    """
    if any(type(v) is not int or v <= 0 for v in (max_records, max_line_bytes, max_total_bytes)):
        raise ValueError('Limites positivos obrigatórios')
    count = total = 0
    while True:
        line = stream.readline(min(max_line_bytes, max_total_bytes-total)+1)
        if not isinstance(line, bytes):
            raise ValueError('Fluxo binário obrigatório')
        if not line:
            if not count:
                raise ValueError('Dataset vazio')
            return
        total += len(line)
        count += 1
        if total > max_total_bytes or len(line) > max_line_bytes or count > max_records:
            raise ValueError('Dataset excede orçamento')
        if not line.strip():
            raise ValueError('Registro vazio')
        try:
            yield parse_record(json.loads(line.decode('utf-8')))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError('JSONL UTF-8 inválido') from exc


def write_atomic(records, destination, *, max_records=10000, max_line_bytes=4*1024*1024,
                 max_total_bytes=64*1024*1024):
    """Stream a validated dataset to a new destination, atomically and without overwrite."""
    from pathlib import Path
    import os
    import tempfile
    if any(type(v) is not int or v <= 0 for v in (max_records, max_line_bytes, max_total_bytes)):
        raise ValueError('Limites positivos obrigatórios')
    path = Path(destination)
    count = total = 0
    descriptor, staging = tempfile.mkstemp(prefix='.nabla-jsonl-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            for record in records:
                # Recheck against the authoritative importer, including solutions.
                validated = parse_record(record.to_data())
                line = (canonical_json(validated.to_data())+'\n').encode('utf-8')
                count += 1
                total += len(line)
                if count > max_records or len(line) > max_line_bytes or total > max_total_bytes:
                    raise ValueError('Dataset excede orçamento')
                stream.write(line)
            if not count:
                raise ValueError('Dataset vazio')
            stream.flush()
            os.fsync(stream.fileno())
        # Link is atomic and fails if destination already exists (including symlinks).
        os.link(staging, path)
        return {'records': count, 'bytes': total}
    finally:
        os.unlink(staging)
