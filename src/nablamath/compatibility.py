"""Machine-readable support contract and local runtime diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
import json
import platform
from pathlib import Path
import subprocess
import re
import shutil
import sys
from typing import Any


@dataclass(frozen=True)
class CompatibilityReport:
    compatible: bool
    package_version: str
    python_version: str
    python_supported: bool
    operating_system: str
    operating_system_supported: bool
    pdflatex_available: bool
    lean_available: bool
    problems: tuple[str, ...]

    def to_data(self) -> dict[str, object]:
        return {
            "compatible": self.compatible,
            "package_version": self.package_version,
            "python_version": self.python_version,
            "python_supported": self.python_supported,
            "operating_system": self.operating_system,
            "operating_system_supported": self.operating_system_supported,
            "pdflatex_available": self.pdflatex_available,
            "lean_available": self.lean_available,
            "problems": list(self.problems),
        }


def support_contract() -> dict[str, Any]:
    """Load the support matrix shipped inside the installed wheel."""
    resource = files("nablamath").joinpath("compatibility.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    if type(payload.get("schema_version")) is not int or payload.get("schema_version") != 1:
        raise RuntimeError("Versão desconhecida do contrato de compatibilidade")
    return payload


def _version_pair(value: str) -> tuple[int, int]:
    major, minor, *_ = value.split(".")
    return int(major), int(minor)


def normalize_os(system: str) -> str:
    names = {"Linux": "linux", "Windows": "windows", "Darwin": "macos"}
    return names.get(system, system.strip().lower() or "unknown")


def formal_runtime_report(project: str | Path = "lean") -> dict[str, object]:
    """Probe the pinned compiler locally; never download or run Lake resolution.

    Compiler compatibility is distinct from a successful proof or a built
    Mathlib. An existing Mathlib artifact remains unverified until replay.
    """
    from .formal.lean_checker import find_lake

    project = Path(project).resolve()
    pin_path = project / "lean-toolchain"
    if not pin_path.is_file():
        return {"status": "unavailable", "reason": "Pinned Lean project missing",
                "mathlib_status": "unverified", "version": None}
    match = re.fullmatch(r"leanprover/lean4:v([0-9]+\.[0-9]+\.[0-9]+)",
                         pin_path.read_text(encoding="utf-8").strip())
    if match is None:
        return {"status": "incompatible", "reason": "Unsupported toolchain pin",
                "mathlib_status": "unverified", "version": None}
    lake = find_lake(project)
    compiler = lake.parent / ("lean.exe" if sys.platform == "win32" else "lean") if lake else None
    if compiler is None or not compiler.is_file():
        return {"status": "unavailable", "reason": "Pinned compiler not installed",
                "mathlib_status": "unverified", "version": None}
    try:
        result = subprocess.run([str(compiler), "--version"], capture_output=True,
                                text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "unverified", "reason": "Compiler probe failed or timed out",
                "mathlib_status": "unverified", "version": None}
    version = re.search(r"Lean \(version ([0-9]+\.[0-9]+\.[0-9]+)(?:[ ,)]|$)", result.stdout)
    actual = version.group(1) if version else None
    status = "available" if result.returncode == 0 and actual == match.group(1) else "incompatible"
    return {"status": status, "reason": "Compiler version probe only",
            "mathlib_status": "unverified", "version": actual}


def runtime_report(
    *,
    python_version: tuple[int, int] | None = None,
    operating_system: str | None = None,
) -> CompatibilityReport:
    """Compare a runtime with the versioned contract without network access."""
    contract = support_contract()
    python = contract["python"]
    current_python = python_version or (sys.version_info.major, sys.version_info.minor)
    python_supported = (
        _version_pair(python["minimum"]) <= current_python
        < _version_pair(python["maximum_exclusive"])
    )
    current_os = normalize_os(operating_system or platform.system())
    os_supported = current_os in contract["operating_systems"]["supported"]
    problems: list[str] = []
    if not python_supported:
        problems.append(
            f"Python {current_python[0]}.{current_python[1]} fora do intervalo "
            f">={python['minimum']},<{python['maximum_exclusive']}"
        )
    if not os_supported:
        problems.append(f"Sistema operacional {current_os!r} não faz parte da matriz suportada")
    return CompatibilityReport(
        compatible=not problems,
        package_version=str(contract["package_version"]),
        python_version=f"{current_python[0]}.{current_python[1]}",
        python_supported=python_supported,
        operating_system=current_os,
        operating_system_supported=os_supported,
        pdflatex_available=shutil.which("pdflatex") is not None,
        lean_available=formal_runtime_report()["status"] == "available",
        problems=tuple(problems),
    )


__all__ = ["CompatibilityReport", "normalize_os", "runtime_report", "support_contract", "formal_runtime_report"]
