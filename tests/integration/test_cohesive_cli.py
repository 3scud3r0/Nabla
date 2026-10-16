"""CLI discovery and end-to-end alpha cohesion smoke (offline)."""
import json
import subprocess
import sys
import unittest

from nablamath.calc.catalog import catalog


class CohesiveCliTests(unittest.TestCase):
    def test_catalog_command_matches_runtime_and_returns_json(self):
        result = subprocess.run(
            [sys.executable, "-m", "nablamath.cli", "catalog"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), catalog())

    def test_finite_math_cli_receipt_matches_session(self):
        from nablamath.calc import CalculationSession
        result = subprocess.run(
            [sys.executable, "-m", "nablamath.cli", "calc", "nt_modular_roots",
             "--arguments", '{"a":2,"prime":7}'],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt, CalculationSession().execute(
            "nt_modular_roots", a=2, prime=7).to_data())

    def test_cohesion_runner_returns_machine_readable_success(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, str(root / "tools" / "cohesion_smoke.py")],
            capture_output=True, text=True, timeout=40, cwd=root,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data["passed"])
        self.assertIn("desktop_adapter", data["checks"])
        self.assertIn("cli_catalog", data["checks"])


if __name__ == "__main__":
    unittest.main()
