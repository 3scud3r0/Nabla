import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class LocalCliTests(unittest.TestCase):
    def test_run_creates_reproducible_record(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "results.sqlite3"
            process = subprocess.run([sys.executable, "-m", "nablamath.cli", "run", "(x+x)/x",
                                      "--value", "x=3", "--db", str(db)],
                                     capture_output=True, text=True, check=False)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("Resultado exato: 2", process.stdout)


    def test_invalid_database_returns_operation_error_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            database=root/'invalid.db'
            database.write_bytes(b'not a SQLite database')
            before=database.read_bytes()
            for arguments in [
                ['backup',str(root/'backup.db'),'--db',str(database)],
                ['run','1+1','--db',str(database)],
            ]:
                with self.subTest(arguments=arguments):
                    process=subprocess.run([sys.executable,'-m','nablamath.cli',*arguments],
                        capture_output=True,text=True,timeout=10)
                    self.assertEqual(process.returncode,1)
                    self.assertIn('Erro:',process.stderr)
                    self.assertNotIn('Traceback',process.stderr)
                    self.assertEqual(database.read_bytes(),before)
            self.assertFalse((root/'backup.db').exists())


if __name__ == "__main__":
    unittest.main()
