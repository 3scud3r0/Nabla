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

from .migrations import CURRENT_SCHEMA_VERSION, migrate, validate_schema
from ..core.semantic_contracts import load_json, require_fields, require_digest


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


MAX_BACKUP_BYTES = 256 * 1024 * 1024


def _temporary(destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.' + destination.name + '.', dir=destination.parent)
    os.close(descriptor)
    return Path(name)


def _receipt(path):
    if path.stat().st_size > MAX_BACKUP_BYTES:
        raise ValueError('Backup excede 256 MiB')
    integrity = _integrity(path)
    if integrity != 'ok':
        raise ValueError(f'Backup SQLite corrompido: {integrity}')
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        version = validate_schema(db)
    raw = path.read_bytes()
    return BackupReceipt(version, hashlib.sha256(raw).hexdigest(), len(raw), integrity)


def backup_database(source: str | Path, destination: str | Path) -> BackupReceipt:
    """Copy a read-only snapshot, migrating the copy rather than the user's DB.

    The receipt is published last. An interrupted pair is explicitly unusable;
    neither an existing backup nor an unrelated temporary file is overwritten.
    """
    source, destination = Path(source), Path(destination)
    manifest = destination.with_suffix(destination.suffix + '.manifest.json')
    if not source.is_file() or source.is_symlink():
        raise ValueError('Origem deve ser um banco regular')
    if source.resolve() == destination.resolve():
        raise ValueError('Origem e destino do backup devem ser diferentes')
    if destination.exists() or destination.is_symlink() or manifest.exists() or manifest.is_symlink():
        raise FileExistsError(destination)
    temporary = _temporary(destination)
    manifest_temporary = _temporary(manifest)
    published = False
    try:
        with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)) as origin:
            validate_schema(origin)
            with closing(sqlite3.connect(temporary)) as target:
                # Bound the copy even if another writer grows the source.
                def progress(status, remaining, total):
                    if total * origin.execute('PRAGMA page_size').fetchone()[0] > MAX_BACKUP_BYTES:
                        raise ValueError('Backup excede 256 MiB')
                origin.backup(target, pages=256, progress=progress)
                migrate(target)
        receipt = _receipt(temporary)
        manifest_temporary.write_text(json.dumps(receipt.to_data(), sort_keys=True) + '\n', encoding='utf-8')
        os.link(temporary, destination)
        published = True
        os.link(manifest_temporary, manifest)
        return receipt
    except BaseException:
        if published:
            destination.unlink(missing_ok=True)
        raise
    finally:
        temporary.unlink(missing_ok=True)
        manifest_temporary.unlink(missing_ok=True)


def restore_database(backup: str | Path, destination: str | Path) -> BackupReceipt:
    """Validate staged bytes/schema, migrate v0/v1, and publish without clobbering."""
    backup, destination = Path(backup), Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    manifest_path = backup.with_suffix(backup.suffix + '.manifest.json')
    if backup.is_symlink() or manifest_path.is_symlink():
        raise ValueError('Backup e manifesto devem ser arquivos regulares')
    if backup.stat().st_size > MAX_BACKUP_BYTES or manifest_path.stat().st_size > 4096:
        raise ValueError('Backup ou manifesto excede orçamento')
    payload = load_json(manifest_path.read_text(encoding='utf-8'))
    require_fields(payload, {'schema_version', 'sha256', 'size_bytes', 'integrity_check'})
    require_digest(payload['sha256'])
    if (type(payload['schema_version']) is not int or payload['schema_version'] not in (0, 1)
            or type(payload['size_bytes']) is not int or not 0 < payload['size_bytes'] <= MAX_BACKUP_BYTES
            or payload['integrity_check'] != 'ok'):
        raise ValueError('Versão de backup ou manifesto incompatível')
    temporary = _temporary(destination)
    try:
        # Verify exactly the bytes we will publish, avoiding a second source read.
        with backup.open('rb') as source, temporary.open('wb') as target:
            copied = 0
            while block := source.read(1024 * 1024):
                copied += len(block)
                if copied > MAX_BACKUP_BYTES:
                    raise ValueError('Backup excede 256 MiB')
                target.write(block)
            target.flush()
            os.fsync(target.fileno())
        receipt = _receipt(temporary)
        if receipt.to_data() != payload:
            raise ValueError('Backup não corresponde ao manifesto ou schema real')
        with closing(sqlite3.connect(temporary)) as db:
            migrate(db)
        receipt = _receipt(temporary)
        os.link(temporary, destination)
        return receipt
    finally:
        temporary.unlink(missing_ok=True)


__all__ = ['BackupReceipt', 'backup_database', 'restore_database']
