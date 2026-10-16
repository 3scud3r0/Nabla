"""Verified online backup and conservative restore for the local SQLite store."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import json
import os
import tempfile
from pathlib import Path
import sqlite3

from ..core.semantic_contracts import load_json, require_fields, require_digest

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
    lock = destination.with_name(destination.name + ".backup.lock")
    lock_descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    temporary = None
    manifest_temporary = None
    try:
        descriptor, name = tempfile.mkstemp(prefix=".nabla-backup-", suffix=".db", dir=destination.parent)
        os.close(descriptor)
        temporary = Path(name)
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
        descriptor, name = tempfile.mkstemp(prefix=".nabla-backup-", suffix=".json", dir=destination.parent)
        manifest_temporary = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(receipt.to_data(), sort_keys=True, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(destination)
        manifest_temporary.replace(destination.with_suffix(destination.suffix + ".manifest.json"))
        return receipt
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if manifest_temporary is not None:
            manifest_temporary.unlink(missing_ok=True)
        os.close(lock_descriptor)
        lock.unlink()


def restore_database(backup: str | Path, destination: str | Path) -> BackupReceipt:
    """Restore only a receipt-verified backup and never overwrite a database."""
    backup, destination = Path(backup), Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    manifest_path = backup.with_suffix(backup.suffix + ".manifest.json")
    if manifest_path.stat().st_size > 4096:
        raise ValueError("Manifesto de backup excede o limite")
    payload = load_json(manifest_path.read_text(encoding="utf-8"), max_bytes=4096)
    require_fields(payload, {"schema_version", "sha256", "size_bytes", "integrity_check"})
    require_digest(payload["sha256"])
    if (type(payload["schema_version"]) is not int
            or type(payload["size_bytes"]) is not int or payload["size_bytes"] < 0
            or payload["integrity_check"] != "ok"):
        raise ValueError("Contrato de manifesto de backup inválido")
    raw = backup.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != payload.get("sha256") or len(raw) != payload.get("size_bytes"):
        raise ValueError("Backup não corresponde ao manifesto")
    if payload.get("schema_version") != CURRENT_SCHEMA_VERSION:
        raise ValueError("Versão de backup incompatível")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Validate the exact bytes to publish, rather than rereading a mutable source.
    descriptor, name = tempfile.mkstemp(prefix=".nabla-restore-", suffix=".db", dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        integrity = _integrity(temporary)
        if integrity != "ok":
            raise ValueError(f"Backup SQLite corrompido: {integrity}")
        with closing(sqlite3.connect(temporary.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version != payload["schema_version"]:
            raise ValueError("Schema SQLite diverge do manifesto")
        # Atomic no-clobber publication: a concurrent creator must win safely.
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return BackupReceipt(CURRENT_SCHEMA_VERSION, digest, len(raw), integrity)


__all__ = ["BackupReceipt", "backup_database", "restore_database"]
