"""Idempotent, bounded import of a hash-pinned historical ZIP into a new directory.

Never executes imported code. Existing destinations are verified, never merged
or overwritten. A failed extraction leaves the existing destination untouched.
"""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import os
import shutil
import stat
import tempfile
import zipfile


def import_pinned_archive(archive, destination, *, expected_sha256,
                          max_files=10000, max_bytes=128 * 1024 * 1024):
    archive, destination = Path(archive), Path(destination)
    if (isinstance(max_files, bool) or not isinstance(max_files, int) or max_files < 1
            or isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1):
        raise ValueError('Positive resource budgets required')
    if archive.stat().st_size > max_bytes:
        raise ValueError('Compressed archive exceeds budget')
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError('Pinned archive hash mismatch')
    entries = {}
    with zipfile.ZipFile(archive) as source:
        total = 0
        seen = set()
        for member in source.infolist():
            name = member.filename.rstrip('/')
            path = PurePosixPath(name)
            if (not name or path.is_absolute() or '..' in path.parts or '\\' in name
                    or ':' in name or path.as_posix() != name or name.casefold() in seen
                    or stat.S_ISLNK(member.external_attr >> 16) or member.flag_bits & 1):
                raise ValueError('Unsafe, case-colliding or encrypted archive entry')
            seen.add(name.casefold())
            if len(seen) > max_files:
                raise ValueError('Archive file count exceeds budget')
            if member.is_dir():
                continue
            total += member.file_size
            if total > max_bytes:
                raise ValueError('Uncompressed archive exceeds budget')
            data = source.read(member)
            if len(data) != member.file_size:
                raise ValueError('Archive size mismatch')
            entries[name] = data
    # File/directory collisions are rejected before modifying the destination.
    for name in entries:
        if any(parent.as_posix() in entries for parent in PurePosixPath(name).parents if parent.as_posix() != '.'):
            raise ValueError('Archive file/directory collision')
    if destination.is_symlink() or any(p.is_symlink() for p in destination.parents):
        raise ValueError('Destination symlink not allowed')
    if destination.exists():
        if not destination.is_dir():
            raise ValueError('Destination must be a directory')
        paths = list(destination.rglob('*'))
        if any(p.is_symlink() for p in paths):
            raise ValueError('Existing destination contains symlinks')
        existing = {p.relative_to(destination).as_posix(): p.read_bytes()
                    for p in paths if p.is_file()}
        if existing != entries:
            raise ValueError('Existing destination differs; import into a separate directory')
        return {'files': len(entries), 'changed': False, 'archive_sha256': expected_sha256}
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.nabla-import-', dir=destination.parent))
    try:
        for name, data in sorted(entries.items()):
            target = temporary.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        # rename is atomic on this filesystem; refuses a non-empty concurrent target.
        os.rename(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return {'files': len(entries), 'changed': True, 'archive_sha256': expected_sha256}
