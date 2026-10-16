import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nablamath.cli import main
from nablamath.research import calculate
from nablamath.storage import load_result, save_result
from nablamath.store.backup import backup_database, restore_database


class BackupRestoreTests(unittest.TestCase):
    def test_backup_restore_preserves_records_and_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, backup, restored = root / "source.db", root / "backup.db", root / "restored.db"
            result = calculate("x+x", {"x": 4})
            save_result(source, result)
            receipt = backup_database(source, backup)
            restored_receipt = restore_database(backup, restored)
            self.assertEqual(receipt.sha256, restored_receipt.sha256)
            self.assertEqual(load_result(restored, result.content_id), result.to_data())
            with closing(sqlite3.connect(restored)) as connection, connection:
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)

    def test_restore_refuses_tampering_and_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, backup = root / "source.db", root / "backup.db"
            save_result(source, calculate("1+1", {}))
            backup_database(source, backup)
            with self.assertRaises(FileExistsError):
                restore_database(backup, source)
            raw = bytearray(backup.read_bytes())
            raw[-1] ^= 1
            backup.write_bytes(raw)
            with self.assertRaises(ValueError):
                restore_database(backup, root / "tampered.db")

    def test_future_schema_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "future.db"
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.execute("PRAGMA user_version=999")
            with self.assertRaises(RuntimeError):
                save_result(database, calculate("1+1", {}))

    def test_cli_backup_and_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, backup, restored = root / "source.db", root / "backup.db", root / "restored.db"
            result = calculate("2+2", {})
            save_result(source, result)
            self.assertEqual(main(["backup", str(backup), "--db", str(source)]), 0)
            self.assertEqual(main(["restore", str(backup), "--db", str(restored)]), 0)
            self.assertEqual(load_result(restored, result.content_id), result.to_data())


if __name__ == "__main__":
    unittest.main()


def test_restore_rejects_rehashed_manifest_contract_changes(tmp_path):
    import pytest
    source, backup = tmp_path / 'source.db', tmp_path / 'backup.db'
    save_result(source, calculate('2+2', {}))
    backup_database(source, backup)
    manifest = backup.with_suffix('.db.manifest.json')
    original = json.loads(manifest.read_text())
    for field, value in [('schema_version', True), ('size_bytes', True),
                         ('integrity_check', 'not checked'), ('extra', 'ignored')]:
        manifest.write_text(json.dumps({**original, field: value}))
        with pytest.raises(ValueError):
            restore_database(backup, tmp_path / 'invalid.db')
        assert not (tmp_path / 'invalid.db').exists()
    manifest.write_text('{"schema_version":999,' + json.dumps(original)[1:])
    with pytest.raises(ValueError, match='Duplicate'):
        restore_database(backup, tmp_path / 'invalid.db')


def test_restore_checks_real_schema_and_keeps_unrelated_temporary_file(tmp_path):
    import hashlib
    import pytest
    source, backup = tmp_path / 'source.db', tmp_path / 'backup.db'
    save_result(source, calculate('2+2', {}))
    backup_database(source, backup)
    with closing(sqlite3.connect(backup)) as connection, connection:
        connection.execute('PRAGMA user_version=999')
    manifest = backup.with_suffix('.db.manifest.json')
    data = json.loads(manifest.read_text())
    data['sha256'] = hashlib.sha256(backup.read_bytes()).hexdigest()
    data['size_bytes'] = backup.stat().st_size
    manifest.write_text(json.dumps(data))
    sentinel = tmp_path / 'restored.db.tmp'
    sentinel.write_text('keep this file')
    with pytest.raises(ValueError, match='Schema'):
        restore_database(backup, tmp_path / 'restored.db')
    assert sentinel.read_text() == 'keep this file'
    assert not (tmp_path / 'restored.db').exists()
    assert not list(tmp_path.glob('.nabla-restore-*'))


def test_restore_never_overwrites_concurrent_destination(tmp_path, monkeypatch):
    import os
    import pytest
    from nablamath.store import backup as module
    source, backup, target = tmp_path / 'source.db', tmp_path / 'backup.db', tmp_path / 'restored.db'
    save_result(source, calculate('2+2', {}))
    backup_database(source, backup)
    link = os.link
    def competing_writer(temporary, destination):
        destination.write_bytes(b'concurrent user file')
        return link(temporary, destination)
    monkeypatch.setattr(module.os, 'link', competing_writer)
    with pytest.raises(FileExistsError):
        restore_database(backup, target)
    assert target.read_bytes() == b'concurrent user file'
    assert not list(tmp_path.glob('.nabla-restore-*'))


def test_backup_preserves_unrelated_tmp_and_refuses_concurrent_writer(tmp_path):
    import pytest
    source, backup = tmp_path / 'source.db', tmp_path / 'backup.db'
    save_result(source, calculate('2+2', {}))
    sentinel = tmp_path / 'backup.db.tmp'
    sentinel.write_text('user data')
    backup_database(source, backup)
    assert sentinel.read_text() == 'user data'
    lock = tmp_path / 'backup.db.backup.lock'
    lock.write_text('another writer')
    previous = backup.read_bytes()
    with pytest.raises(FileExistsError):
        backup_database(source, backup)
    assert backup.read_bytes() == previous
    assert lock.read_text() == 'another writer'
    assert not list(tmp_path.glob('.nabla-backup-*'))
