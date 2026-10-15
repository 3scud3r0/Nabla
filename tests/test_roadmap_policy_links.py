import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("policy_links", ROOT / "tools/check_policy_links.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def test_policy_references_resolve():
    assert checker.check_links([ROOT / path for path in checker.POLICIES]) >= 20


def test_broken_and_escaping_local_references_are_rejected(tmp_path):
    document = tmp_path / "policy.md"
    target = tmp_path / "evidence file.md"
    target.write_text("Evidence")
    document.write_text("[Valid](evidence%20file.md)\n[External](https://example.com)")
    assert checker.check_links([document], root=tmp_path) == 1
    for text in ["[Missing](missing.md)", "[Escape](../outside.md)", ""]:
        document.write_text(text)
        with pytest.raises(ValueError):
            checker.check_links([document], root=tmp_path)
