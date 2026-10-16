"""Exercise artifact integrity at the distribution boundary without execution."""
import base64
import csv
import hashlib
import importlib.util
import io
from pathlib import Path
import stat
import zipfile

import pytest

_spec = importlib.util.spec_from_file_location('verify_release_wheel', Path(__file__).resolve().parents[2] / 'tools/verify_wheel.py')
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
verify_wheel = _module.verify_wheel


def wheel(path, *, alteration=None):
    files = {'nablamath/__init__.py': b'__version__ = "0.1.0a1"\n',
             'nablamath-0.1.0a1.dist-info/METADATA': b'Metadata-Version: 2.1\nName: nablamath\nVersion: 0.1.0a1\n',
             'nablamath-0.1.0a1.dist-info/WHEEL': b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n'}
    record = 'nablamath-0.1.0a1.dist-info/RECORD'
    rows = [[name, 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(value).digest()).rstrip(b'=').decode(), str(len(value))] for name, value in files.items()]
    rows.append([record, '', ''])
    text = io.StringIO()
    csv.writer(text).writerows(rows)
    files[record] = text.getvalue().encode()
    if alteration == 'source':
        files['nablamath/__init__.py'] = b'print("changed")\n'
    if alteration == 'dependency':
        files['nablamath-0.1.0a1.dist-info/METADATA'] += b'Requires-Dist: unexpected-dependency\n'
    if alteration == 'unrecorded':
        files['extra.py'] = b'pass\n'
    if alteration == 'traversal':
        files['../outside.py'] = b'pass\n'
    if alteration == 'record':
        files[record] += b'missing.py,sha256=invalid,1\n'
    with zipfile.ZipFile(path, 'w') as archive:
        for name, value in files.items():
            archive.writestr(name, value)
        if alteration == 'symlink':
            info = zipfile.ZipInfo('link.py')
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, '../outside.py')
    return path


def test_valid_integrity_does_not_claim_publisher_authenticity(tmp_path):
    report = verify_wheel(wheel(tmp_path / 'valid.whl'))
    assert report['files_verified'] == 3
    assert report['name'] == 'nablamath'
    assert 'authenticity' in report['scope']


@pytest.mark.parametrize('alteration', ['source', 'dependency', 'unrecorded', 'traversal', 'record', 'symlink'])
def test_distribution_rejects_tampered_or_unsafe_members(tmp_path, alteration):
    with pytest.raises(ValueError):
        verify_wheel(wheel(tmp_path / 'tampered.whl', alteration=alteration))
