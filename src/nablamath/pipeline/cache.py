"""Cache local de blobs com chave versionada de entrada; falha em corrupção."""

import json
from pathlib import Path

from .provenance import provenance_id
from ..store.blobs import BlobStore


class LocalCache:
    def __init__(self, root: Path):
        self.blobs = BlobStore(root / "blobs")
        self.index = root / "index"

    def put(self, version: str, parameters: dict, dependencies: list[str], output: dict) -> str:
        key = provenance_id(version, parameters, dependencies)
        digest = self.blobs.put(json.dumps(output, sort_keys=True, allow_nan=False).encode())
        self.index.mkdir(parents=True, exist_ok=True)
        entry = self.index / key
        if entry.exists() and entry.read_text(encoding='utf-8') != digest:
            raise ValueError("Resultado divergente para mesmos parâmetros e versão")
        entry.write_text(digest, encoding="ascii")
        return key

    def get(self, key: str) -> dict | None:
        entry = self.index / key
        if not entry.exists():
            return None
        return json.loads(self.blobs.get(entry.read_text(encoding="ascii")))
