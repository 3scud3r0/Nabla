"""Portable JSONL export without overwriting an existing artifact."""
from pathlib import Path
from ..datasets.serializer import dumps, loads


def write_jsonl(records, destination):
    records = tuple(records)
    text = dumps(records)
    loads(text)
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        handle.write(text)
    return path


def read_jsonl(source):
    path = Path(source)
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('Dataset excede limite')
    return loads(path.read_text(encoding='utf-8'))
