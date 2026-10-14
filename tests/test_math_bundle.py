from pathlib import Path
import subprocess
import sys
import unittest
import tempfile
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_math_bundle import build_bundle, mathematical_sources  # noqa: E402
import build_math_bundle as bundle_module


class MathematicalBundleTests(unittest.TestCase):
    def test_bundle_is_complete_deterministic_and_current(self):
        bundle = (ROOT / "math.txt").read_text(encoding="utf-8")
        self.assertEqual(bundle, build_bundle())
        self.assertGreaterEqual(len(mathematical_sources()), 80)
        self.assertGreater(bundle.count("\n"), 4_000)
        for source in mathematical_sources():
            marker = f"BEGIN FILE: {source.relative_to(ROOT).as_posix()}"
            self.assertEqual(bundle.count(marker), 1)

    def test_dependency_caches_are_not_distributed_as_project_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'Proof.lean').write_text('example : True := by trivial\n')
            for cache in ('.lake','.git','__pycache__'):
                (root/cache).mkdir()
                (root/cache/'Foreign.lean').write_text('dependency source\n')
            with patch.object(bundle_module,'ROOT',root), patch.object(bundle_module,'DIRECTORIES',(root,)), patch.object(bundle_module,'FILES',()):
                self.assertEqual(mathematical_sources(),(root/'Proof.lean',))

    def test_check_command_is_read_only_and_succeeds(self):
        process = subprocess.run(
            [sys.executable, "tools/build_math_bundle.py", "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)


if __name__ == "__main__":
    unittest.main()
