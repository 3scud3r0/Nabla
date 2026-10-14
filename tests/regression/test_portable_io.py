"""Reproduce the Windows publication failure without relying on a Windows runner."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
import sqlite3
from nablamath.store.backup import backup_database,restore_database
from nablamath.research import calculate
from nablamath.storage import save_result

ROOT=Path(__file__).resolve().parents[2]


class PortableIOTests(unittest.TestCase):
    def test_publication_under_non_utf8_process_locale(self):
        script=r'''
import tempfile
from pathlib import Path
from nablamath.documents.document_model import Document,Section
from nablamath.documents.publication import publish,verify_publication
with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary)/'article'
    doc=Document('Portugu\u00eas e \u03b1', (Section('M\u00e9todo','Evid\u00eancia cient\u00edfica: \u03bb e \u2264'),))
    publish(doc,root)
    assert verify_publication(root)
'''
        environment={**os.environ,'PYTHONUTF8':'0','PYTHONCOERCECLOCALE':'0','LC_ALL':'C'}
        process=subprocess.run([sys.executable,'-c',script],env=environment,capture_output=True,timeout=30)
        self.assertEqual(process.returncode,0,process.stderr.decode(errors='replace'))

    def test_scientific_text_io_declares_encoding(self):
        directories=('documents','export','graphics')
        missing=[]
        for directory in directories:
            for path in (ROOT/'src/nablamath'/directory).rglob('*.py'):
                for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in {'read_text','write_text'}:
                        if not any(k.arg=='encoding' for k in node.keywords):missing.append((str(path),node.lineno))
        self.assertEqual(missing,[])

    def test_sqlite_backup_uri_handles_reserved_path_characters(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'espa\u00e7o # data';root.mkdir()
            database=root/'source #.db';backup=root/'backup #.db';restored=root/'restored #.db'
            save_result(database,calculate('1+1',{}))
            receipt=backup_database(database,backup)
            self.assertEqual(restore_database(backup,restored).sha256,receipt.sha256)
