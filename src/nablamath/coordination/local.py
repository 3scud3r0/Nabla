"""Coordenador SQLite local para tarefas racionais; sem serviço de rede/identidade."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from contextlib import closing
import time

from ..research import calculate
from ..core.semantic_contracts import require_digest, require_text
from ..verification.consensus import receipt_consensus


class LocalCoordinator:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY, expression TEXT NOT NULL, values_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', result_id TEXT);
            CREATE TABLE IF NOT EXISTS leases (
                task_id TEXT NOT NULL, worker TEXT NOT NULL, expires REAL NOT NULL,
                result_id TEXT, PRIMARY KEY(task_id,worker));
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=30)

    def add(self, expression: str, values: dict[str, str | int], *, max_pending: int = 10000) -> str:
        if type(max_pending) is not int or not 1 <= max_pending <= 10000:
            raise ValueError("Cota de tarefas inválida")
        calculated = calculate(expression, values)  # valida antes de oferecer tarefa
        normalized = {k: str(v) for k,v in calculated.values.items()}
        canonical = json.dumps([expression, normalized], sort_keys=True, separators=(",", ":"))
        identifier = hashlib.sha256(canonical.encode()).hexdigest()
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM tasks WHERE task_id=?", (identifier,)).fetchone():
                return identifier
            if db.execute("SELECT COUNT(*) FROM tasks WHERE status='pending'").fetchone()[0] >= max_pending:
                raise ValueError("Cota de tarefas pendentes esgotada")
            db.execute("INSERT OR IGNORE INTO tasks (task_id,expression,values_json) VALUES (?,?,?)",
                       (identifier, expression, json.dumps(normalized, sort_keys=True)))
        return identifier

    def lease(self, worker: str, seconds: int = 60) -> dict | None:
        if not isinstance(worker, str) or not worker.strip() or len(worker) > 128 or type(seconds) is not int or not 1 <= seconds <= 3600:
            raise ValueError("Trabalhador ou prazo inválidos")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            now = time.time()
            tasks = db.execute("SELECT task_id,expression,values_json FROM tasks WHERE status='pending' ORDER BY task_id")
            for task_id, expression, values_json in tasks:
                occupied = db.execute("SELECT worker,expires,result_id FROM leases WHERE task_id=?", (task_id,)).fetchall()
                if any(name == worker and (result is not None or expires > now) for name, expires, result in occupied):
                    continue
                if sum(result is not None or expires > now for _, expires, result in occupied) >= 2:
                    continue
                db.execute("INSERT INTO leases VALUES (?,?,?,NULL) ON CONFLICT(task_id,worker) DO UPDATE SET expires=excluded.expires",
                           (task_id,worker,now+seconds))
                return {"task_id": task_id, "expression": expression, "values": json.loads(values_json),
                        "lease_expires_unix": now+seconds}
        return None

    def submit(self, worker: str, task_id: str, result_id: str) -> str:
        """Reexecuta o cálculo localmente; aceita consenso só de duas IDs de worker distintas."""
        require_text(worker, "worker", limit=128)
        require_digest(task_id)
        require_digest(result_id)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            task = db.execute("SELECT expression,values_json,status FROM tasks WHERE task_id=?",
                              (task_id,)).fetchone()
            lease = db.execute("SELECT expires,result_id FROM leases WHERE task_id=? AND worker=?",
                               (task_id,worker)).fetchone()
            if task is not None and lease is not None and task[2] in {"pending", "verified"} and lease[1] == result_id:
                return "verified" if task[2] == "verified" else "awaiting_second_worker"
            if task is None or lease is None or task[2] != "pending" or lease[1] is not None or lease[0] <= time.time():
                raise ValueError("Tarefa ou lease inválido/expirado")
            expected = calculate(task[0], json.loads(task[1])).content_id
            if result_id != expected:
                raise ValueError("Resultado do trabalhador não passou na reexecução")
            db.execute("UPDATE leases SET result_id=? WHERE task_id=? AND worker=?",
                       (result_id,task_id,worker))
            receipts = db.execute("SELECT worker,result_id FROM leases WHERE task_id=? AND result_id IS NOT NULL",
                                  (task_id,)).fetchall()
            agreement = receipt_consensus([{"participant_id": name, "result_id": identifier}
                                           for name, identifier in receipts], expected_result_id=expected)
            if agreement["quorum_met"]:
                db.execute("UPDATE tasks SET status='verified',result_id=? WHERE task_id=?",
                           (result_id,task_id))
                return "verified"
            return "awaiting_second_worker"

    def heartbeat(self, worker: str, task_id: str, seconds: int = 60) -> float:
        require_text(worker, "worker", limit=128)
        require_digest(task_id)
        if type(seconds) is not int or not 1 <= seconds <= 3600:
            raise ValueError("Prazo inválido")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            now = time.time()
            cursor = db.execute("""UPDATE leases SET expires=? WHERE task_id=? AND worker=?
                AND expires>? AND result_id IS NULL
                AND EXISTS (SELECT 1 FROM tasks WHERE tasks.task_id=leases.task_id AND status='pending')""",
                (now+seconds, task_id, worker, now))
            if cursor.rowcount != 1:
                raise ValueError("Lease ausente, concluído ou expirado")
        return now+seconds

    def cancel(self, task_id: str) -> str:
        require_digest(task_id)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None or row[0] == "verified":
                raise ValueError("Tarefa inexistente ou já verificada")
            db.execute("UPDATE tasks SET status='cancelled' WHERE task_id=?", (task_id,))
        return "cancelled"

    def status(self, task_id: str) -> str | None:
        with closing(self._connect()) as db, db:
            row = db.execute("SELECT status FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        return row[0] if row else None
