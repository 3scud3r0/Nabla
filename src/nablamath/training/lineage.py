"""Expand verified snapshot parent references into a bounded immutable DAG."""
from ..knowledge.lineage import LineageGraph


def snapshot_lineage(store, roots):
    if not isinstance(roots, (list, tuple)) or not 1 <= len(roots) <= 256:
        raise ValueError("Bounded snapshot roots required")
    nodes, pending = {}, list(roots)
    while pending:
        key = pending.pop()
        if key in nodes:
            continue
        if len(nodes) >= 4096:
            raise ValueError("Snapshot lineage budget exceeded")
        manifest = store.get(key)
        nodes[key] = {"id": key, "parents": manifest["parents"]}
        pending.extend(manifest["parents"])
    return LineageGraph.create(list(nodes.values()))
