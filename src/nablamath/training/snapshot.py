"""Content-addressed opaque model/data snapshots; never unpickle or execute weights."""
from pathlib import Path

from ..core.semantic_contracts import canonical_payload, load_json, require_digest, require_fields, require_text
from ..store.blobs import BlobStore


class SnapshotStore:
    def __init__(self, root: Path):
        self.blobs = BlobStore(root)

    def capture(self, *, weights: bytes, datasets: dict, code_id: str, license_id: str, parents=()):
        require_digest(code_id)
        require_text(license_id, "license_id")
        if (not isinstance(weights, bytes) or not weights or len(weights) > 64*1024*1024
                or not isinstance(datasets, dict) or not 1 <= len(datasets) <= 128
                or not isinstance(parents, (tuple, list)) or len(parents) > 64):
            raise ValueError("Bounded opaque weights, datasets and parent IDs required")
        for name, raw in datasets.items():
            require_text(name, "dataset name", limit=128)
            if not isinstance(raw, bytes) or not raw or len(raw) > 64*1024*1024:
                raise ValueError("Dataset must contain bounded bytes")
        if len(weights) + sum(len(raw) for raw in datasets.values()) > 256*1024*1024:
            raise ValueError("Snapshot byte budget exceeded")
        parent_ids = sorted(require_digest(p) for p in parents)
        if len(set(parent_ids)) != len(parent_ids):
            raise ValueError("Duplicate snapshot parent")
        # Referenced parent snapshots must be present and intact before writing.
        for parent in parent_ids:
            self.get(parent)
        manifest = {"schema_version": 1, "weights": self.blobs.put(weights),
                    "datasets": {name: self.blobs.put(raw) for name, raw in sorted(datasets.items())},
                    "code_id": code_id, "license_id": license_id, "parents": parent_ids}
        return self.blobs.put(canonical_payload(manifest).encode("utf-8"))

    def get(self, snapshot_id: str):
        manifest = load_json(self.blobs.get(require_digest(snapshot_id)).decode("utf-8"))
        require_fields(manifest, {"schema_version", "weights", "datasets", "code_id", "license_id", "parents"})
        if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
            raise ValueError("Unsupported snapshot version")
        require_digest(manifest["code_id"])
        require_text(manifest["license_id"], "license_id")
        if not isinstance(manifest["datasets"], dict) or not 1 <= len(manifest["datasets"]) <= 128:
            raise ValueError("Invalid snapshot dataset references")
        if not isinstance(manifest["parents"], list) or len(manifest["parents"]) > 64:
            raise ValueError("Invalid snapshot parent references")
        for parent in manifest["parents"]:
            require_digest(parent)
            self.blobs.get(parent)
        if len(set(manifest["parents"])) != len(manifest["parents"]):
            raise ValueError("Duplicate snapshot parent")
        size = len(self.blobs.get(require_digest(manifest["weights"])))
        if not 1 <= size <= 64*1024*1024:
            raise ValueError("Invalid weights size")
        for name, identifier in manifest["datasets"].items():
            require_text(name, "dataset name", limit=128)
            length = len(self.blobs.get(require_digest(identifier)))
            if not 1 <= length <= 64*1024*1024:
                raise ValueError("Invalid dataset size")
            size += length
        if size > 256*1024*1024:
            raise ValueError("Snapshot byte budget exceeded")
        return manifest
