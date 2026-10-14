"""Catálogo transacional de projetos locais, sem sincronização automática."""

from __future__ import annotations

from pathlib import Path
from contextlib import closing
import sqlite3


class Workspace:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS projects (name TEXT PRIMARY KEY, root_id TEXT NOT NULL)")

    def set_project(self, name: str, root_id: str) -> None:
        if not name.strip() or len(root_id) != 64 or any(c not in "0123456789abcdef" for c in root_id):
            raise ValueError("projeto inválido")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO projects VALUES (?,?) ON CONFLICT(name) DO UPDATE SET root_id=excluded.root_id",
                       (name, root_id))

    def projects(self) -> tuple[tuple[str, str], ...]:
        with closing(sqlite3.connect(self.path)) as db, db:
            return tuple(db.execute("SELECT name,root_id FROM projects ORDER BY name"))

    def remove(self, name: str) -> None:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM projects WHERE name=?", (name,))


__all__ = ["Workspace"]
