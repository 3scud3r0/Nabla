"""Machine-readable support contract and local runtime diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.resources import files
import json
import platform
import shutil
import subprocess
import re
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
    integrations: dict[str, dict[str, object]] = field(default_factory=dict)

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
            "integrations": self.integrations,
        }


def support_contract() -> dict[str, Any]:
    """Load the support matrix shipped inside the installed wheel."""
    resource = files("nablamath").joinpath("compatibility.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise RuntimeError("Versão desconhecida do contrato de compatibilidade")
    return payload


def _version_pair(value: str) -> tuple[int, int]:
    major, minor, *_ = value.split(".")
    return int(major), int(minor)


def normalize_os(system: str) -> str:
    names = {"Linux": "linux", "Windows": "windows", "Darwin": "macos"}
    return names.get(system, system.strip().lower() or "unknown")


def integration_report(*, probe: bool = False) -> dict[str, dict[str, object]]:
    """Separate discovery from a bounded version probe; never imply a proof/build."""
    contract = support_contract()
    reports = {}
    for name in ('lean', 'pdflatex'):
        executable = shutil.which(name)
        row = {'status': 'unverified' if executable else 'unavailable',
               'executable': executable, 'version': None,
               'scope': 'executable discovery only; scientific workflow not tested'}
        if executable and probe:
            try:
                result = subprocess.run([executable, '--version'], capture_output=True,
                                        text=True, timeout=5, check=False)
                output = (result.stdout + result.stderr)[:4096]
                row['version'] = output.splitlines()[0] if output else ''
                row['status'] = 'available' if result.returncode == 0 else 'incompatible'
                if name == 'lean' and result.returncode == 0:
                    expected = contract['lean']['toolchain'].removeprefix('v')
                    actual = re.search(r'Lean \(version (\d+\.\d+\.\d+)(?:[, )])', output)
                    if actual is None or actual[1] != expected:
                        row['status'] = 'incompatible'
                row['scope'] = 'bounded version probe only; no proof, dependency build or PDF validation'
            except (OSError, subprocess.TimeoutExpired) as error:
                row['status'] = 'unavailable'
                row['diagnostic'] = type(error).__name__
        reports[name] = row
    return reports


def runtime_report(
    *,
    python_version: tuple[int, int] | None = None,
    operating_system: str | None = None,
    probe: bool = False,
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
        lean_available=shutil.which("lean") is not None,
        problems=tuple(problems),
        integrations=integration_report(probe=probe),
    )


__all__ = ["CompatibilityReport", "normalize_os", "runtime_report", "support_contract", "integration_report"]
