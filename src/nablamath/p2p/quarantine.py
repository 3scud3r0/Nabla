"""Quarentena local limitada para bytes ainda não confiáveis."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


class Quarantine:
    def __init__(self, root: str | Path, max_item_bytes: int = 8 * 1024 * 1024):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_item_bytes = max_item_bytes

    def add(self, raw: bytes, *, reason: str, source: str) -> str:
        if not raw or len(raw) > self.max_item_bytes or not reason.strip() or not source.strip():
            raise ValueError("item de quarentena inválido")
        identifier = hashlib.sha256(raw).hexdigest()
        path = self.root / identifier
        path.mkdir(exist_ok=True)
        (path / "payload.bin").write_bytes(raw)
        (path / "metadata.json").write_text(json.dumps({"reason": reason, "source": source},
                                                        sort_keys=True, separators=(",", ":")) + "\n", encoding='utf-8')
        return identifier

    def remove(self, identifier: str) -> None:
        path = self.root / identifier
        for name in ("payload.bin", "metadata.json"):
            try: (path / name).unlink()
            except FileNotFoundError: pass
        try: path.rmdir()
        except FileNotFoundError: pass

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(path.name for path in self.root.iterdir() if path.is_dir()))


__all__ = ["Quarantine"]
