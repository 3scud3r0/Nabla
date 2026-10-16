"""Actual alpha-v0 fixture upgrade, rollback and no-clobber restore semantics."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest
from nablamath.storage import load_result
from nablamath.store.backup import backup_database, restore_database
from nablamath.store.migrations import migrate

FIXTURE = Path(__file__).resolve().parents[1]/'fixtures/alpha-v0/results.sql'


def legacy(path):
    with closing(sqlite3.connect(path)) as db:
        db.executescript(FIXTURE.read_text())
        return db.execute('SELECT content_id,payload FROM results').fetchone()


def test_backup_copies_and_migrates_alpha_without_touching_original(tmp_path):
    source = tmp_path/'alpha.db'
    identifier, raw = legacy(source)
    original = source.read_bytes()
    receipt = backup_database(source, tmp_path/'backup.db')
    assert receipt.schema_version == 1
    assert source.read_bytes() == original
    restore_database(tmp_path/'backup.db', tmp_path/'restored.db')
    assert load_result(tmp_path/'restored.db', identifier) == json.loads(raw)
    with pytest.raises(FileExistsError):
        backup_database(source, tmp_path/'backup.db')


def test_restore_real_v0_receipt_upgrades_staged_copy(tmp_path):
    source = tmp_path/'alpha.db'
    identifier, raw = legacy(source)
    original = source.read_bytes()
    manifest = {'schema_version': 0, 'sha256': hashlib.sha256(original).hexdigest(),
                'size_bytes': len(original), 'integrity_check': 'ok'}
    source.with_suffix('.db.manifest.json').write_text(json.dumps(manifest))
    receipt = restore_database(source, tmp_path/'restored.db')
    assert receipt.schema_version == 1
    assert source.read_bytes() == original
    assert load_result(tmp_path/'restored.db', identifier) == json.loads(raw)


def test_migration_never_commits_a_callers_transaction():
    with closing(sqlite3.connect(':memory:')) as db:
        db.execute('BEGIN')
        migrate(db)
        db.execute("INSERT INTO results(content_id,payload) VALUES ('id','payload')")
        db.rollback()
        assert db.execute('PRAGMA user_version').fetchone()[0] == 0
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='results'").fetchall()


@pytest.mark.parametrize('version', [0, 1, 999])
def test_mislabeled_schema_is_refused_without_mutation(tmp_path, version):
    source = tmp_path/'bad.db'
    with closing(sqlite3.connect(source)) as db:
        db.execute('CREATE TABLE results(content_id TEXT, payload BLOB)')
        db.execute(f'PRAGMA user_version={version}')
        db.commit()
    before = source.read_bytes()
    with pytest.raises(RuntimeError):
        backup_database(source, tmp_path/'backup.db')
    assert source.read_bytes() == before
    assert not (tmp_path/'backup.db').exists()


def test_rehashed_backup_cannot_lie_about_its_schema(tmp_path):
    source = tmp_path/'alpha.db'
    legacy(source)
    original = source.read_bytes()
    source.with_suffix('.db.manifest.json').write_text(json.dumps({
        'schema_version': 1, 'sha256': hashlib.sha256(original).hexdigest(),
        'size_bytes': len(original), 'integrity_check': 'ok'}))
    with pytest.raises(ValueError, match='schema real'):
        restore_database(source, tmp_path/'restored.db')
    assert not (tmp_path/'restored.db').exists()


def test_restore_ignores_unrelated_tmp_file_and_refuses_symlink(tmp_path):
    source = tmp_path/'source.db'
    legacy(source)
    backup_database(source, tmp_path/'backup.db')
    sentinel = tmp_path/'restored.db.tmp'
    sentinel.write_bytes(b'personal data')
    restore_database(tmp_path/'backup.db', tmp_path/'restored.db')
    assert sentinel.read_bytes() == b'personal data'
    try:
        (tmp_path/'link.db').symlink_to(tmp_path/'missing.db')
    except OSError:
        pytest.skip('Symlink privilege unavailable on this platform')
    with pytest.raises(FileExistsError):
        restore_database(tmp_path/'backup.db', tmp_path/'link.db')


def test_migration_accepts_builtin_row_factory():
    with closing(sqlite3.connect(':memory:')) as db:
        db.row_factory=sqlite3.Row
        assert migrate(db)==1
        assert migrate(db)==1


def test_migration_refuses_mislabeled_table_missing_insert_default():
    with closing(sqlite3.connect(':memory:')) as db:
        db.execute('CREATE TABLE results(content_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL)')
        db.execute('PRAGMA user_version=1')
        with pytest.raises(RuntimeError,match='Default'):
            migrate(db)
