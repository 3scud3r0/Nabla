"""Reproducible local-alpha cohesion smoke with explicit pass/fail evidence.

Run after editable or wheel installation:
    python tools/cohesion_smoke.py --output .nabla/cohesion.json
    python tools/cohesion_smoke.py --check-source-bundles

No network or optional scientific toolchain is required. A successful run
does not authorize the separate Lean, Windows, security or 1.0 release gates.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from importlib import metadata


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run(*, check_source_bundles: bool = False) -> dict:
    from nablamath import __version__
    from nablamath.calc import CalculationSession, Notebook
    from nablamath.calc.catalog import catalog
    from nablamath.desktop.app import LocalResearch
    from nablamath.stability import validate_public_api

    result = {"schema_version": 1, "package_version": __version__,
              "scope": "local CPU contract/CLI/desktop/notebook smoke, not scientific 1.0 acceptance"}
    checks: dict[str, dict] = {}
    result["checks"] = checks

    installed = metadata.version("nablamath")
    _check(installed == __version__, "Installed wheel/metadata version mismatch")
    checks["installed_version"] = {"passed": True, "version": installed}

    contract = validate_public_api()
    declared = catalog()
    _check(contract["operations"] == len(declared["operations"]),
           "Public operation count differs from installed catalog")
    _check(contract["operations"] >= 69,
           "Expanded mathematical operation catalog is incomplete")
    checks["catalog"] = {"passed": True, "operations": len(declared["operations"])}

    session = CalculationSession(precision=34)
    cases = (
        ("evaluate", {"source": "x*x+1", "values": {"x": 3}}, ("value", "10")),
        ("nt_primality", {"n": 97}, ("prime", True)),
        ("nt_factorization", {"n": 12}, ("totient", 4)),
        ("ff_extension", {"prime": 2, "modulus": [1, 1, 1],
                          "element": [0, 1]}, ("field_size", 4)),
        ("analysis_integral", {"coefficients": [0, 0, 1],
                               "lower": 0, "upper": 1}, ("integral", "1/3")),
        ("graph_max_flow", {"vertices": ["s", "t"],
                            "edges": [["s", "t", "3/2"]],
                            "source": "s", "sink": "t"}, ("cut_capacity", "3/2")),
        ("prob_stationary", {"transition": [["1/2", "1/2"],
                                           ["1/4", "3/4"]]}, ("uniqueness", True)),
    )
    with tempfile.TemporaryDirectory(prefix="nabla-cohesion-") as directory:
        destination = Path(directory) / "cohesion.notebook.json"
        notebook = Notebook("Nabla local-alpha cohesion")
        for operation, arguments, (field, expected) in cases:
            receipt = session.execute(operation, **arguments)
            data = receipt.to_data()
            _check(data["result"][field] == expected,
                   f"Incorrect exact mathematics: {operation}/{field}")
            _check(data["request"]["operation"] == operation,
                   f"Operation receipt mismatch: {operation}")
            _check(data["formal_proof"] is False,
                   "Computational results cannot claim a formal proof")
            notebook.append(receipt)
        notebook.save(destination)
        _check(Notebook.load(destination).replay() == len(cases),
               "Notebook did not reexecute all receipts")
        checks["session_and_notebook"] = {"passed": True, "cases": len(cases)}

        desktop = LocalResearch(Path(directory) / "data")
        _check(desktop.scientific_catalog() == declared,
               "Desktop catalog is inconsistent with the installed session catalog")
        desktop_receipt = desktop.scientific_calculation(
            {"operation": "analysis_integral",
             "arguments": {"coefficients": [0, 0, 1], "lower": 0, "upper": 1}})
        _check(desktop_receipt["result"]["integral"] == "1/3",
               "Desktop mathematical calculation diverges")
        _check(desktop.count() == 0,
               "New scientific receipts must not be stored in incompatible legacy SQLite format")
        checks["desktop_adapter"] = {"passed": True}

    catalog_cli = subprocess.run(
        [sys.executable, "-m", "nablamath.cli", "catalog"], capture_output=True,
        text=True, check=False, timeout=25,
    )
    _check(catalog_cli.returncode == 0,
           "CLI catalog failed: " + catalog_cli.stderr[:400])
    _check(json.loads(catalog_cli.stdout) == declared,
           "CLI catalog differs from session/desktop catalog")
    checks["cli_catalog"] = {"passed": True}

    calc_cli = subprocess.run(
        [sys.executable, "-m", "nablamath.cli", "calc", "nt_modular_roots",
         "--arguments", '{"a":2,"prime":7}'], capture_output=True,
        text=True, check=False, timeout=25,
    )
    _check(calc_cli.returncode == 0,
           "CLI scientific calculation failed: " + calc_cli.stderr[:400])
    _check(json.loads(calc_cli.stdout)["result"]["roots"] == [3, 4],
           "CLI modular roots differ from exact API")
    checks["cli_calculate"] = {"passed": True}

    if check_source_bundles:
        root = Path(__file__).resolve().parents[1]
        for name, builder in (
            ("math_bundle", "build_math_bundle.py"),
            ("source_bundle", "build_nabla_bundle.py"),
        ):
            proc = subprocess.run(
                [sys.executable, str(root / "tools" / builder), "--check"],
                cwd=root, capture_output=True, text=True, check=False, timeout=120,
            )
            _check(proc.returncode == 0,
                   f"Source bundle gate {name} failed: " + (proc.stdout + proc.stderr)[-800:])
            checks[name] = {"passed": True}

    result["passed"] = True
    result["limitations"] = [
        "No substitute for independent mathematical review",
        "No Lean/SMT, GPU, Windows installation or experimental-science acceptance",
        "No assurance of current generated bundles unless --check-source-bundles was specified",
        "Release signature and external provenance require separate approval",
    ]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        help="Write JSON to a NEW file; do not overwrite earlier evidence")
    parser.add_argument("--check-source-bundles", action="store_true",
                        help="Require both checked-in generated source bundles be current")
    args = parser.parse_args(argv)
    try:
        result = run(check_source_bundles=args.check_source_bundles)
    except (AssertionError, ValueError, TypeError, RuntimeError, OSError,
            ArithmeticError, subprocess.TimeoutExpired) as exc:
        result = {"schema_version": 1, "passed": False, "error": str(exc)}
        status = 1
    else:
        status = 0
    content = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(content + "\n")
    print(content)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
