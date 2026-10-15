"""Validate wheel RECORD integrity without extracting or executing package code.

This validates artifact consistency, not publisher authenticity or code safety.
"""
import argparse
import base64
import csv
from email.parser import BytesParser
import hashlib
import io
from pathlib import Path, PurePosixPath
import stat
import zipfile


def verify_wheel(path):
    path = Path(path)
    if path.stat().st_size > 64*1024*1024:
        raise ValueError("Compressed wheel exceeds budget")
    with zipfile.ZipFile(path) as archive:
        entries, total, names = {}, 0, set()
        for member in archive.infolist():
            name = member.filename
            parts = PurePosixPath(name).parts
            if (not parts or name.startswith("/") or "\\" in name or ".." in parts
                    or ":" in parts[0] or stat.S_ISLNK(member.external_attr >> 16)
                    or member.flag_bits & 1 or name in names
                    or PurePosixPath(name).as_posix() != name.rstrip("/")):
                raise ValueError("Unsafe or duplicate wheel member")
            names.add(name)
            if len(names) > 10000:
                raise ValueError("Wheel entry count exceeds budget")
            if member.is_dir():
                continue
            total += member.file_size
            if member.file_size > 64*1024*1024 or total > 256*1024*1024 or len(entries) >= 10000:
                raise ValueError("Uncompressed wheel exceeds budget")
            entries[name] = member
        record_names = [name for name in entries if name.endswith(".dist-info/RECORD")]
        if len(record_names) != 1:
            raise ValueError("Exactly one wheel RECORD required")
        record_name = record_names[0]
        prefix = record_name.rsplit("/", 1)[0]
        metadata_name, wheel_name = prefix + "/METADATA", prefix + "/WHEEL"
        if metadata_name not in entries or wheel_name not in entries:
            raise ValueError("Wheel metadata missing")
        if any(entries[name].file_size > 1_000_000 for name in (record_name, metadata_name, wheel_name)):
            raise ValueError("Wheel metadata exceeds budget")
        records = csv.reader(io.StringIO(archive.read(record_name).decode("utf-8")))
        seen = set()
        for row in records:
            if len(seen) >= len(entries) or len(row) != 3 or row[0] in seen or row[0] not in entries:
                raise ValueError("Invalid RECORD member")
            name, expected, size = row
            seen.add(name)
            if name == record_name:
                if expected or size:
                    raise ValueError("RECORD must not hash itself")
                continue
            content = archive.read(name)
            digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
            if expected != "sha256=" + digest or size != str(len(content)):
                raise ValueError("Wheel RECORD checksum or size mismatch")
        if seen != set(entries):
            raise ValueError("Unrecorded wheel member")
        metadata = BytesParser().parsebytes(archive.read(metadata_name))
        if not metadata.get("Name") or not metadata.get("Version"):
            raise ValueError("Package identity missing")
        return {"schema_version": 1, "name": metadata["Name"], "version": metadata["Version"],
                "wheel_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "files_verified": len(entries)-1, "requires_dist": metadata.get_all("Requires-Dist", []),
                "scope": "wheel RECORD integrity only; publisher authenticity and dependency safety not established"}


def main(argv=None):
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(verify_wheel(args.wheel), sort_keys=True))
        return 0
    except (ValueError, OSError, zipfile.BadZipFile, UnicodeError) as error:
        print(f"Invalid wheel: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
