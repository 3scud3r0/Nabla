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
