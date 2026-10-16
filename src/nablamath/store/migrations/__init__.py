"""Transactional SQLite schema migrations."""

from __future__ import annotations

import sqlite3

CURRENT_SCHEMA_VERSION = 1


def validate_schema(connection: sqlite3.Connection) -> int:
    """Validate the actual supported table, not merely its user_version label."""
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if not 0 <= version <= CURRENT_SCHEMA_VERSION:
        raise RuntimeError(
            f"Banco usa schema {version}, fora do suportado 0–{CURRENT_SCHEMA_VERSION}"
        )
    tables = connection.execute(
        "SELECT name,type FROM sqlite_master WHERE name NOT GLOB 'sqlite_*'"
    ).fetchall()
    if not tables and version == 0:
        return version
    if {tuple(row) for row in tables} != {('results', 'table')}:
        raise RuntimeError('Banco não corresponde ao schema de resultados suportado')
    columns = connection.execute('PRAGMA table_info(results)').fetchall()
    signature = [(row[1], row[2].upper(), row[3], row[5]) for row in columns]
    if signature != [('content_id', 'TEXT', 0, 1), ('payload', 'TEXT', 1, 0),
                     ('created_at', 'TEXT', 1, 0)]:
        raise RuntimeError('Estrutura da tabela results incompatível')
    if columns[2][4] != 'CURRENT_TIMESTAMP':
        raise RuntimeError('Default de created_at incompatível')
    return version


def migrate(connection: sqlite3.Connection) -> int:
    """Upgrade atomically without committing a caller's pending transaction."""
    connection.execute('SAVEPOINT nabla_schema_upgrade')
    try:
        version = validate_schema(connection)
        if version == 0:
            connection.execute('''CREATE TABLE IF NOT EXISTS results (
                content_id TEXT PRIMARY KEY, payload TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
            connection.execute('PRAGMA user_version = 1')
        validate_schema(connection)
        connection.execute('RELEASE SAVEPOINT nabla_schema_upgrade')
    except BaseException:
        connection.execute('ROLLBACK TO SAVEPOINT nabla_schema_upgrade')
        connection.execute('RELEASE SAVEPOINT nabla_schema_upgrade')
        raise
    return CURRENT_SCHEMA_VERSION


__all__ = ["CURRENT_SCHEMA_VERSION", "migrate", "validate_schema"]
