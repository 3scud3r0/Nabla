"""Dataset semantic identity delegates to the exact Forge canonicalization."""
from ..forge.deduplicate import semantic_fingerprint as task_fingerprint


def semantic_fingerprint(record):
    return task_fingerprint(record.task)
