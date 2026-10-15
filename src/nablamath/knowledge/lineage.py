"""Immutable bounded dependency DAG, reusable for claims, datasets and models."""
from collections import deque
from dataclasses import dataclass

from ..core.semantic_contracts import canonical_payload, load_json, require_fields, require_digest
from ..core.semantic_ir import fingerprint


@dataclass(frozen=True)
class LineageGraph:
    manifest_json: str

    def __post_init__(self):
        data = load_json(self.manifest_json)
        require_fields(data, {"schema_version", "nodes"})
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ValueError("Unsupported lineage version")
        rows = data["nodes"]
        if not isinstance(rows, list) or not 1 <= len(rows) <= 4096:
            raise ValueError("Lineage requires 1–4096 nodes")
        nodes, links = {}, 0
        for row in rows:
            require_fields(row, {"id", "parents"})
            key = require_digest(row["id"])
            parents = row["parents"]
            if not isinstance(parents, list) or len(parents) > 256 or key in nodes:
                raise ValueError("Duplicate node or invalid parents")
            parents = [require_digest(parent) for parent in parents]
            if len(set(parents)) != len(parents):
                raise ValueError("Duplicate parent")
            nodes[key] = sorted(parents)
            links += len(parents)
        if links > 32768 or any(p not in nodes for parents in nodes.values() for p in parents):
            raise ValueError("Missing parent or link budget exceeded")
        children = {key: [] for key in nodes}
        degree = {key: len(parents) for key, parents in nodes.items()}
        for key, parents in nodes.items():
            for parent in parents:
                children[parent].append(key)
        pending = deque(key for key in nodes if not degree[key])
        visited = 0
        while pending:
            visited += 1
            for child in children[pending.popleft()]:
                degree[child] -= 1
                if not degree[child]:
                    pending.append(child)
        if visited != len(nodes):
            raise ValueError("Cyclic lineage")
        object.__setattr__(self, "manifest_json", canonical_payload({"schema_version": 1,
            "nodes": [{"id": key, "parents": nodes[key]} for key in sorted(nodes)]}))

    @classmethod
    def create(cls, nodes):
        return cls(canonical_payload({"schema_version": 1, "nodes": nodes}))

    def to_data(self):
        return load_json(self.manifest_json)

    @property
    def content_id(self):
        return fingerprint(self.to_data())

    def descendants(self, identifier):
        nodes = {row["id"]: row["parents"] for row in self.to_data()["nodes"]}
        require_digest(identifier)
        if identifier not in nodes:
            raise ValueError("Unknown lineage node")
        children = {key: [] for key in nodes}
        for key, parents in nodes.items():
            for parent in parents:
                children[parent].append(key)
        found, pending = set(), [identifier]
        while pending:
            for child in children[pending.pop()]:
                if child not in found:
                    found.add(child)
                    pending.append(child)
        return tuple(sorted(found))
