from concurrent.futures import ThreadPoolExecutor
import base64
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile

import pytest

from nablamath.core.resource_profiles import ResourceProfile, ResourceReservations

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_wheel", ROOT / "tools/verify_wheel.py")
wheel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wheel)


def test_all_profiles_and_transactional_cooperative_reservations():
    profiles = [ResourceProfile.load(path) for path in sorted((ROOT / "configs/profiles").glob("*.yaml"))]
    assert len(profiles) == 5
    profile = next(p for p in profiles if p.name == "cpu_conservative")
    reservations = ResourceReservations(profile)
    with reservations.reserve(memory_bytes=profile.memory_bytes):
        assert reservations.used == (1, profile.memory_bytes, 0, 1)
        def blocked(_):
            with pytest.raises(ValueError):
                with reservations.reserve():
                    raise AssertionError("Admission should reject before work")
        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(blocked, range(16)))
    assert reservations.used == (0, 0, 0, 0)
    with pytest.raises(RuntimeError):
        with reservations.reserve():
            raise RuntimeError("Failed task releases its reservation")
    assert reservations.used == (0, 0, 0, 0)
    for request in [{"gpu_memory_bytes": 1}, {"distributed": True}, {"cpu_slots": True},
                    {"seconds": profile.max_task_seconds+1}, {"memory_bytes": -1}]:
        with pytest.raises(ValueError):
            with reservations.reserve(**request):
                pass


def test_profile_schema_never_coerces_versions(tmp_path):
    data = ResourceProfile("test", 1, 1024, 0, 1, 1).to_data()
    for field, value in [("schema_version", True), ("schema_version", 2), ("max_tasks", 0), ("distributed", 1)]:
        invalid = {**data, field: value}
        path = tmp_path / "invalid.yaml"
        path.write_text(json.dumps(invalid))
        with pytest.raises(ValueError):
            ResourceProfile.load(path)


def make_wheel(path, *, tamper=None, extra=None, unsafe=None):
    files = {"example/__init__.py": b"raise RuntimeError('must never execute')\n",
             "example-1.dist-info/METADATA": b"Metadata-Version: 2.1\nName: example\nVersion: 1\nRequires-Dist: sample>=1\n",
             "example-1.dist-info/WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n"}
    if unsafe:
        files[unsafe] = b"unsafe path"
    output = io.StringIO()
    writer = csv.writer(output)
    for name, raw in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b"=").decode()
        writer.writerow([name, "sha256="+digest, str(len(raw))])
    writer.writerow(["example-1.dist-info/RECORD", "", ""])
    files["example-1.dist-info/RECORD"] = output.getvalue().encode()
    if tamper:
        files[tamper] = b"tampered after RECORD"
    if extra:
        files[extra] = b"unrecorded"
    with zipfile.ZipFile(path, "w") as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)


def test_wheel_record_integrity_without_extracting_or_executing(tmp_path):
    path = tmp_path / "example.whl"
    make_wheel(path)
    report = wheel.verify_wheel(path)
    assert report["name"] == "example" and report["version"] == "1"
    assert report["files_verified"] == 3
    assert report["requires_dist"] == ["sample>=1"]
    assert list(tmp_path.iterdir()) == [path]
    for options in [{"tamper": "example/__init__.py"}, {"extra": "unrecorded.py"},
                    {"unsafe": "../escape.py"}, {"unsafe": "pkg/./alias.py"},
                    {"unsafe": "C:/escape.py"}, {"unsafe": "pkg\\escape.py"}]:
        make_wheel(path, **options)
        with pytest.raises(ValueError):
            wheel.verify_wheel(path)


def test_unbounded_record_and_duplicate_members_fail_closed(tmp_path):
    path = tmp_path / "example.whl"
    make_wheel(path)
    with pytest.warns(UserWarning, match="Duplicate name"):
        with zipfile.ZipFile(path, "a") as archive:
            archive.writestr("example-1.dist-info/RECORD", b"x,x,x\n" * 200000)
    with pytest.raises(ValueError):
        wheel.verify_wheel(path)
