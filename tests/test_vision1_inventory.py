"""The release inventory must preserve each criterion and detect missing files."""
import importlib.util
from pathlib import Path
import pytest

_spec = importlib.util.spec_from_file_location('vision1_inventory', Path(__file__).resolve().parents[1] / 'tools/vision1_inventory.py')
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


def test_missing_file_never_becomes_accepted(tmp_path):
    (tmp_path / 'vision1.md').write_text('| `missing.py` | existente | real behavior | replay required |\n')
    report = _module.inventory(tmp_path)
    assert report['missing'] == ['missing.py']
    assert report['files'][0]['expected_content'] == 'real behavior'
    assert report['files'][0]['acceptance'] == 'replay required'
    assert report['files'][0]['acceptance_status'] == 'requires-evidence'
    assert report['release_accepted'] is False


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'folder\\windows'])
def test_inventory_rejects_unsafe_paths(tmp_path, name):
    (tmp_path / 'vision1.md').write_text(f'| `{name}` | behavior | criterion |\n')
    with pytest.raises(ValueError):
        _module.inventory(tmp_path)


def test_real_inventory_has_every_planned_file():
    report = _module.inventory()
    assert report['total'] == 212
    assert not report['missing']
    assert sum(r['kind'] == 'generated-proof' for r in report['files']) == 60
    assert all(r['bytes'] > 0 and len(r['sha256']) == 64 for r in report['files'])
    assert not report['release_accepted']
