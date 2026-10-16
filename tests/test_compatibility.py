import unittest

from nablamath import __version__
from nablamath.compatibility import normalize_os, runtime_report, support_contract


class CompatibilityTests(unittest.TestCase):
    def test_packaged_contract_matches_package(self):
        contract = support_contract()
        self.assertEqual(contract["package_version"], __version__)
        self.assertEqual(contract["schema_version"], 1)

    def test_supported_runtime(self):
        report = runtime_report(python_version=(3, 10), operating_system="Linux")
        self.assertTrue(report.compatible)
        self.assertEqual(report.operating_system, "linux")
        self.assertEqual(report.problems, ())

    def test_unsupported_runtime_is_explicit(self):
        report = runtime_report(python_version=(3, 15), operating_system="Plan9")
        self.assertFalse(report.compatible)
        self.assertFalse(report.python_supported)
        self.assertFalse(report.operating_system_supported)
        self.assertEqual(len(report.problems), 2)

    def test_os_names_are_normalized(self):
        self.assertEqual(normalize_os("Windows"), "windows")
        self.assertEqual(normalize_os("Darwin"), "macos")


if __name__ == "__main__":
    unittest.main()


def test_formal_diagnostic_distinguishes_missing_project(tmp_path):
    from nablamath.compatibility import formal_runtime_report
    report = formal_runtime_report(tmp_path)
    assert report['status'] == 'unavailable'
    assert report['mathlib_status'] == 'unverified'


def test_formal_diagnostic_rejects_unpinned_toolchain(tmp_path):
    from nablamath.compatibility import formal_runtime_report
    (tmp_path / 'lean-toolchain').write_text('leanprover/lean4:nightly')
    assert formal_runtime_report(tmp_path)['status'] == 'incompatible'


def test_formal_diagnostic_does_not_call_mathlib_available(monkeypatch, tmp_path):
    import subprocess
    from nablamath import compatibility
    from nablamath.formal import lean_checker
    (tmp_path / 'lean-toolchain').write_text('leanprover/lean4:v4.34.0')
    compiler = tmp_path / ('lean.exe' if compatibility.sys.platform == 'win32' else 'lean')
    compiler.touch()
    monkeypatch.setattr(lean_checker, 'find_lake', lambda project: tmp_path / 'lake')
    monkeypatch.setattr(compatibility.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(a, 0, 'Lean (version 4.34.0, x86_64-unknown-linux-gnu)'))
    report = compatibility.formal_runtime_report(tmp_path)
    assert report['status'] == 'available'
    assert report['version'] == '4.34.0'
    assert report['mathlib_status'] == 'unverified'
    monkeypatch.setattr(compatibility.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(a, 0, 'Lean (version 4.33.0, test)'))
    assert compatibility.formal_runtime_report(tmp_path)['status'] == 'incompatible'
