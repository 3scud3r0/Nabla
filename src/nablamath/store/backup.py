"""Verified online backup and conservative restore for the local SQLite store."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3

from .migrations import CURRENT_SCHEMA_VERSION, migrate


@dataclass(frozen=True)
class BackupReceipt:
    schema_version: int
    sha256: str
    size_bytes: int
    integrity_check: str

    def to_data(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "integrity_check": self.integrity_check,
        }


def _integrity(path: Path) -> str:
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        return str(connection.execute("PRAGMA integrity_check").fetchone()[0])


def backup_database(source: str | Path, destination: str | Path) -> BackupReceipt:
    """Create a consistent SQLite backup plus a hash receipt."""
    source, destination = Path(source), Path(destination)
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.resolve() == destination.resolve():
        raise ValueError("Origem e destino do backup devem ser diferentes")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(source)) as origin, closing(sqlite3.connect(temporary)) as target:
            migrate(origin)
            origin.backup(target)
        integrity = _integrity(temporary)
        if integrity != "ok":
            raise RuntimeError(f"Backup SQLite falhou na integridade: {integrity}")
        raw = temporary.read_bytes()
        receipt = BackupReceipt(
            CURRENT_SCHEMA_VERSION,
            hashlib.sha256(raw).hexdigest(),
            len(raw),
            integrity,
        )
        temporary.replace(destination)
        destination.with_suffix(destination.suffix + ".manifest.json").write_text(
            json.dumps(receipt.to_data(), sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return receipt
    finally:
        temporary.unlink(missing_ok=True)


def restore_database(backup: str | Path, destination: str | Path) -> BackupReceipt:
    """Restore only a receipt-verified backup and never overwrite a database."""
    backup, destination = Path(backup), Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    manifest_path = backup.with_suffix(backup.suffix + ".manifest.json")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw = backup.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != payload.get("sha256") or len(raw) != payload.get("size_bytes"):
        raise ValueError("Backup não corresponde ao manifesto")
    if payload.get("schema_version") != CURRENT_SCHEMA_VERSION:
        raise ValueError("Versão de backup incompatível")
    integrity = _integrity(backup)
    if integrity != "ok":
        raise ValueError(f"Backup SQLite corrompido: {integrity}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        temporary.write_bytes(raw)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return BackupReceipt(CURRENT_SCHEMA_VERSION, digest, len(raw), integrity)


__all__ = ["BackupReceipt", "backup_database", "restore_database"]
