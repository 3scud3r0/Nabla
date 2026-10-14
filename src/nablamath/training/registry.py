"""Registro SQLite local de manifests de modelo; não executa treinamento."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from contextlib import closing
import sqlite3


class ModelRegistry:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS models (model_id TEXT PRIMARY KEY, manifest_json TEXT NOT NULL)")

    def register(self, manifest: dict[str, object]) -> str:
        required = {"architecture", "parent_ids", "dataset_ids", "training_code_id", "evaluation_ids", "license"}
        if set(manifest) != required or not all(isinstance(manifest[key], str) and manifest[key] for key in ("architecture", "training_code_id", "license")):
            raise ValueError("manifesto de modelo inválido")
        for key in ("parent_ids", "dataset_ids", "evaluation_ids"):
            values = manifest[key]
            if not isinstance(values, list) or values != sorted(set(values)):
                raise ValueError(f"{key} deve ser uma lista ordenada e única")
        raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        identifier = hashlib.sha256(raw.encode()).hexdigest()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT OR IGNORE INTO models VALUES (?,?)", (identifier, raw))
        return identifier

    def get(self, model_id: str) -> dict[str, object]:
        with closing(sqlite3.connect(self.path)) as db, db:
            row = db.execute("SELECT manifest_json FROM models WHERE model_id=?", (model_id,)).fetchone()
        if row is None:
            raise KeyError(model_id)
        return json.loads(row[0])


__all__ = ["ModelRegistry"]
