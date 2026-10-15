"""Versioned content-addressed scientific DAG, independent of filesystem paths.

Integrity is not mathematical validity. Replay and review are separate operations.
JSON strings and tuples retain immutable snapshots of caller-owned data.
"""
from __future__ import annotations

from dataclasses import dataclass

from .semantic_contracts import (
    canonical_payload, load_json, require_digest, require_fields, require_text,
)
from .semantic_ir import fingerprint


@dataclass(frozen=True)
class ArtifactNode:
    kind: str
    algorithm: str
    payload_json: str
    parents: tuple[str, ...] = ()

    def __post_init__(self):
        require_text(self.kind, "kind", limit=128)
        require_text(self.algorithm, "algorithm", limit=256)
        payload = load_json(self.payload_json)
        if not isinstance(payload, dict):
            raise ValueError("Node payload must be an object")
        object.__setattr__(self, "payload_json", canonical_payload(payload))
        if not isinstance(self.parents, (tuple, list)) or len(self.parents) > 256:
            raise ValueError("Invalid parent list")
        parents = tuple(require_digest(p) for p in self.parents)
        if len(set(parents)) != len(parents):
            raise ValueError("Duplicate parent")
        object.__setattr__(self, "parents", tuple(sorted(parents)))

    @classmethod
    def create(cls, kind: str, algorithm: str, payload: dict, parents=()):
        return cls(kind, algorithm, canonical_payload(payload), parents)

    @property
    def payload(self) -> dict:
        return load_json(self.payload_json)

    def to_data(self) -> dict:
        return {"kind": self.kind, "algorithm": self.algorithm,
                "payload": self.payload, "parents": list(self.parents)}

    @property
    def content_id(self) -> str:
        return fingerprint(self.to_data())

    @classmethod
    def from_data(cls, data):
        require_fields(data, {"kind", "algorithm", "payload", "parents"})
        if not isinstance(data["parents"], list):
            raise ValueError("Serialized parents must be a list")
        return cls.create(data["kind"], data["algorithm"], data["payload"], data["parents"])


@dataclass(frozen=True)
class ScientificArtifact:
    statement: str
    source: str
    license_id: str
    nodes: tuple[ArtifactNode, ...]
    roots: tuple[str, ...]
    schema_version: int = 1

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported scientific artifact version")
        for name in ("statement", "source", "license_id"):
            require_text(getattr(self, name), name)
        if not isinstance(self.nodes, (tuple, list)) or not 1 <= len(self.nodes) <= 256:
            raise ValueError("Artifact requires 1 to 256 nodes")
        if any(not isinstance(n, ArtifactNode) for n in self.nodes):
            raise ValueError("Expected artifact nodes")
        nodes = tuple(sorted(self.nodes, key=lambda n: n.content_id))
        indexed = {n.content_id: n for n in nodes}
        if len(indexed) != len(nodes):
            raise ValueError("Duplicate node")
        if not isinstance(self.roots, (tuple, list)) or not 1 <= len(self.roots) <= len(nodes):
            raise ValueError("Invalid artifact roots")
        roots = tuple(require_digest(r) for r in self.roots)
        if len(set(roots)) != len(roots):
            raise ValueError("Duplicate root")
        reached, active = set(), set()

        def visit(key):
            if key not in indexed:
                raise ValueError("Dangling artifact reference")
            if key in active:
                raise ValueError("Cyclic artifact")
            if key in reached:
                return
            active.add(key)
            for parent in indexed[key].parents:
                visit(parent)
            active.remove(key)
            reached.add(key)

        for root in roots:
            visit(root)
        if reached != set(indexed):
            raise ValueError("Unreachable artifact node")
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "roots", tuple(sorted(roots)))
        canonical_payload(self.to_data())

    def to_data(self):
        return {"schema_version": self.schema_version, "statement": self.statement,
                "source": self.source, "license_id": self.license_id,
                "nodes": [n.to_data() for n in self.nodes], "roots": list(self.roots)}

    @property
    def content_id(self):
        return fingerprint(self.to_data())

    def to_json(self):
        return canonical_payload({**self.to_data(), "content_id": self.content_id})

    @classmethod
    def from_json(cls, raw):
        data = load_json(raw)
        require_fields(data, {"schema_version", "statement", "source", "license_id", "nodes", "roots", "content_id"})
        if not isinstance(data["nodes"], list) or not 1 <= len(data["nodes"]) <= 256:
            raise ValueError("Invalid serialized nodes")
        artifact = cls(data["statement"], data["source"], data["license_id"],
                       tuple(ArtifactNode.from_data(n) for n in data["nodes"]),
                       data["roots"], data["schema_version"])
        if require_digest(data["content_id"]) != artifact.content_id:
            raise ValueError("Scientific artifact digest mismatch")
        return artifact
