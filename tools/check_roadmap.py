"""Check all 213 source requirements and local evidence links, without scoring science."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def validate_matrix(matrix: dict, root: Path = ROOT) -> dict:
    if (not isinstance(matrix, dict) or type(matrix.get("schema_version")) is not int
            or matrix["schema_version"] != 1):
        raise ValueError("Unsupported matrix version")

    def local_path(name):
        if not isinstance(name, str) or not name or Path(name).is_absolute():
            raise ValueError("Expected repository-relative path")
        resolved = (root / name).resolve()
        if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
            raise ValueError(f"Unavailable repository evidence: {name}")
        return resolved

    raw = local_path(matrix["source"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != matrix["source_sha256"]:
        raise ValueError("Roadmap source digest mismatch")
    source = re.findall(r"^(\d+)\. \*\*(.*?)\*\* — (.+)$", raw.decode("utf-8"), re.M)
    if [int(key) for key, _, _ in source] != list(range(1, 214)):
        raise ValueError("Expected all 213 original requirements")
    rows = matrix["requirements"]
    if not isinstance(rows, list) or len(rows) != len(source):
        raise ValueError("Incomplete requirement matrix")
    counts = {"planned": 0, "partial": 0, "validated": 0}
    for row, (key, target, requirement) in zip(rows, source):
        if (type(row["id"]) is not int or row["id"] != int(key)
                or row["target"] != target or row["requirement"] != requirement):
            raise ValueError("Requirement was omitted, reordered or rewritten")
        status = row["status"]
        if status not in counts:
            raise ValueError("Unknown requirement status")
        counts[status] += 1
        for field in ("implementation", "tests", "evidence"):
            if not isinstance(row[field], list):
                raise ValueError("Evidence references must be lists")
            for name in row[field]:
                local_path(name)
        if status != "planned" and not (row["implementation"] and row["tests"] and row["profile"]):
            raise ValueError("Implemented profiles require code and tests")
        if status == "validated" and not (row["evidence"] and row["reviewer"] and row["release"]):
            raise ValueError("Validation requires evidence, independent reviewer and release")
        if not isinstance(row["remaining"], str) or not row["remaining"].strip():
            raise ValueError("Remaining scope must be explicit")
    return {"requirements": len(rows), "statuses": counts,
            "scope": "traceability only; no scientific completion percentage"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=ROOT / "docs/acceptance/evidence_matrix.json")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(validate_matrix(json.loads(args.matrix.read_text(encoding="utf-8"))), sort_keys=True))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"Invalid roadmap: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
