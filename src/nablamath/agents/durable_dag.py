"""SQLite orchestration for finite, approved, replayable scientific DAGs.

All mutations use BEGIN IMMEDIATE. Opaque lease tokens fence late workers and
replays; they are local lease capabilities, not authenticated identities. A crash
may repeat a pure calculation after expiry, but cannot commit its result twice.
Only immutable completed dependency receipts can feed another action. No shell,
network, plugin or arbitrary source task exists in this protocol.
"""
from contextlib import closing, contextmanager
import copy
import json
from pathlib import Path
import secrets
import sqlite3
import time

from ..core.semantic_contracts import require_digest
from ..core.semantic_ir import canonical_json, fingerprint
from ..node.consent import Consent
from .bindings import resolve
from .dag_contracts import (
    DagBudget, FAILURE_CODES, TERMINAL_TASKS, experiment_from_data, finite_time,
    permissions_data, permissions_from_data, preflight_dag, replay_scientific_result,
    result_receipt, validate_worker,
)
from .human_approval import ApprovalLedger
from .dag_replay import committed_results


class LeaseConflict(ValueError):
    """A stale, expired, cancelled, wrong-owner or replaced lease cannot commit."""


class DagStore:
    SCHEMA_VERSION = 1

    def __init__(self, path, *, clock=time.time):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        with closing(self._connect()) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS dag_meta(version INTEGER NOT NULL);
                INSERT INTO dag_meta SELECT 1 WHERE NOT EXISTS(SELECT 1 FROM dag_meta);
                CREATE TABLE IF NOT EXISTS dag_runs(
                    run_id TEXT PRIMARY KEY, plan_json TEXT NOT NULL,
                    permissions_json TEXT NOT NULL, budget_json TEXT NOT NULL,
                    approvals_json TEXT NOT NULL, approval_head TEXT,
                    created REAL NOT NULL, deadline REAL NOT NULL, status TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0, total_attempts INTEGER NOT NULL DEFAULT 0,
                    result_bytes INTEGER NOT NULL DEFAULT 0, cancel_reason TEXT);
                CREATE TABLE IF NOT EXISTS dag_tasks(
                    run_id TEXT NOT NULL, action_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
                    status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                    available REAL NOT NULL, worker TEXT, token TEXT, expires REAL,
                    result_json TEXT, receipt_json TEXT, error_code TEXT,
                    resource_pool TEXT, reserved_cpu INTEGER NOT NULL DEFAULT 0,
                    reserved_memory INTEGER NOT NULL DEFAULT 0, reserved_tool TEXT,
                    PRIMARY KEY(run_id,action_id), FOREIGN KEY(run_id) REFERENCES dag_runs(run_id));
                CREATE TABLE IF NOT EXISTS dag_events(
                    run_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                    event_json TEXT NOT NULL, event_id TEXT NOT NULL,
                    PRIMARY KEY(run_id,sequence), FOREIGN KEY(run_id) REFERENCES dag_runs(run_id));
                CREATE INDEX IF NOT EXISTS dag_ready ON dag_tasks(run_id,status,ordinal);
            ''')
            columns = {row[1] for row in db.execute('PRAGMA table_info(dag_tasks)')}
            for name, declaration in (('resource_pool', 'TEXT'), ('reserved_cpu', 'INTEGER NOT NULL DEFAULT 0'),
                                      ('reserved_memory', 'INTEGER NOT NULL DEFAULT 0'), ('reserved_tool', 'TEXT')):
                if name not in columns:
                    db.execute(f'ALTER TABLE dag_tasks ADD COLUMN {name} {declaration}')
            rows = db.execute('SELECT version FROM dag_meta').fetchall()
            if len(rows) != 1 or rows[0][0] != self.SCHEMA_VERSION:
                raise ValueError('Unsupported durable DAG schema')

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    @contextmanager
    def _transaction(self):
        with closing(self._connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def _now(self):
        return finite_time(self._clock(), 'coordinator time')

    @staticmethod
    def _run(db, run_id):
        require_digest(run_id)
        row = db.execute('SELECT * FROM dag_runs WHERE run_id=?', (run_id,)).fetchone()
        if row is None:
            raise LookupError('Unknown scientific DAG run')
        return row

    @staticmethod
    def _contract(row):
        plan = experiment_from_data(json.loads(row['plan_json']))
        permissions = permissions_from_data(json.loads(row['permissions_json']))
        budget = DagBudget.from_data(json.loads(row['budget_json']))
        if preflight_dag(plan, permissions, budget) != row['run_id']:
            raise ValueError('Stored DAG contract commitment mismatch')
        return plan, permissions, budget

    @staticmethod
    def _approvals(row):
        ledger = ApprovalLedger.from_data(json.loads(row['approvals_json']))
        if ledger.head != row['approval_head']:
            raise ValueError('Stored approval head mismatch')
        return ledger

    def _event(self, db, run_id, kind, payload):
        last = db.execute('SELECT sequence,event_id FROM dag_events WHERE run_id=? ORDER BY sequence DESC LIMIT 1',
                          (run_id,)).fetchone()
        sequence = last['sequence']+1 if last else 0
        if sequence >= 200000:
            raise ValueError('Durable run audit-event budget exhausted')
        body = dict(schema_version=1, run_id=run_id, sequence=sequence, kind=kind,
                    payload=payload, previous=last['event_id'] if last else None)
        event_id = fingerprint(body)
        db.execute('INSERT INTO dag_events VALUES(?,?,?,?)',
                   (run_id, sequence, canonical_json(body), event_id))
        db.execute('UPDATE dag_runs SET revision=revision+1 WHERE run_id=?', (run_id,))
        return event_id

    @staticmethod
    def _require_consent(consent, now, on_battery):
        if not isinstance(consent, Consent) or type(on_battery) is not bool:
            raise ValueError('Explicit local consent and power state required')
        if (type(consent.contribute) is not bool or type(consent.allow_on_battery) is not bool
                or type(consent.allow_network) is not bool):
            raise ValueError('Consent capabilities must be booleans')
        if consent.expires_unix is not None and (type(consent.expires_unix) is not int or consent.expires_unix < 0):
            raise ValueError('Invalid consent expiry')
        if not consent.active(now) or on_battery and not consent.allow_on_battery:
            raise PermissionError('Node contribution consent is inactive or disallows battery work')

    def create(self, plan, permissions, budget, ledger):
        """Idempotently install one reviewed graph without resetting existing state."""
        run_id = preflight_dag(plan, permissions, budget)
        if not isinstance(ledger, ApprovalLedger):
            raise ValueError('Explicit action approval ledger required')
        snapshot = ledger.to_data()
        approvals = ApprovalLedger.from_data(snapshot)
        approvals.require(plan)
        with self._transaction() as db:
            now = self._now()
            existing = db.execute('SELECT * FROM dag_runs WHERE run_id=?', (run_id,)).fetchone()
            if existing is not None:
                self._contract(existing)
                return run_id
            db.execute('''INSERT INTO dag_runs
                (run_id,plan_json,permissions_json,budget_json,approvals_json,approval_head,created,deadline,status)
                VALUES(?,?,?,?,?,?,?,?,?)''',
                (run_id, canonical_json(plan.to_data()), canonical_json(permissions_data(permissions)),
                 canonical_json(budget.to_data()), canonical_json(snapshot), approvals.head,
                 now, now+budget.run_timeout_seconds, 'ready'))
            db.executemany('INSERT INTO dag_tasks(run_id,action_id,ordinal,status,available) VALUES(?,?,?,?,?)',
                           [(run_id, a.action_id, i, 'queued', now) for i, a in enumerate(plan.proposal.actions)])
            self._event(db, run_id, 'created', dict(plan_id=plan.content_id, approval_head=approvals.head))
        return run_id

    def update_approvals(self, run_id, ledger, *, expected_head):
        """Append a reviewed ledger extension; reject history replacement and stale CAS."""
        if not isinstance(ledger, ApprovalLedger):
            raise ValueError('ApprovalLedger required')
        updated = ledger.to_data()
        checked = ApprovalLedger.from_data(updated)
        with self._transaction() as db:
            row = self._run(db, run_id)
            plan, _, _ = self._contract(row)
            if row['approval_head'] != expected_head:
                raise ValueError('Stale durable approval head')
            old = json.loads(row['approvals_json'])
            if len(updated) < len(old) or updated[:len(old)] != old:
                raise ValueError('Approval history replacement or rollback refused')
            if updated == old:
                return row['status']
            status = row['status']
            if status not in {'completed', 'failed', 'cancelled', 'expired'}:
                try:
                    checked.require(plan)
                    status = 'running' if db.execute("SELECT 1 FROM dag_tasks WHERE run_id=? AND status='leased'", (run_id,)).fetchone() else 'ready'
                except PermissionError:
                    status = 'paused'
            db.execute('UPDATE dag_runs SET approvals_json=?,approval_head=?,status=? WHERE run_id=?',
                       (canonical_json(updated), checked.head, status, run_id))
            self._event(db, run_id, 'approval_update', dict(previous=expected_head, head=checked.head, status=status))
            return status

    def _block_dependants(self, db, run_id, plan):
        """Propagate failed/cancelled ancestors to every unstarted descendant."""
        rows = {r['action_id']: r for r in db.execute('SELECT * FROM dag_tasks WHERE run_id=?', (run_id,))}
        bad = {name for name, row in rows.items() if row['status'] in {'failed', 'blocked', 'cancelled'}}
        for action in plan.proposal.actions:
            row = rows[action.action_id]
            if row['status'] in {'queued', 'retry_wait'} and any(dep in bad for dep in action.depends_on):
                db.execute("UPDATE dag_tasks SET status='blocked',error_code='dependency_failed' WHERE run_id=? AND action_id=?",
                           (run_id, action.action_id))
                bad.add(action.action_id)
                self._event(db, run_id, 'dependency_blocked', dict(action_id=action.action_id))

    def _refresh_status(self, db, run_id):
        run = self._run(db, run_id)
        if run['status'] in {'paused', 'cancelled', 'expired'}:
            return run['status']
        states = [r[0] for r in db.execute('SELECT status FROM dag_tasks WHERE run_id=?', (run_id,))]
        if all(s == 'completed' for s in states):
            status = 'completed'
        elif all(s in TERMINAL_TASKS for s in states):
            status = 'failed'
        elif 'leased' in states:
            status = 'running'
        else:
            status = 'ready'
        db.execute('UPDATE dag_runs SET status=? WHERE run_id=?', (status, run_id))
        return status

    def _fail_task(self, db, run_id, task, budget, code, now):
        run = self._run(db, run_id)
        retry = task['attempts'] < budget.max_attempts_per_action and run['total_attempts'] < budget.max_total_attempts
        status = 'retry_wait' if retry else 'failed'
        db.execute('''UPDATE dag_tasks SET status=?,available=?,worker=NULL,token=NULL,expires=NULL,error_code=?
                      WHERE run_id=? AND action_id=?''',
                   (status, now+budget.retry_delay_seconds, code, run_id, task['action_id']))
        self._event(db, run_id, 'attempt_failed', dict(action_id=task['action_id'], attempt=task['attempts'],
                                                     code=code, status=status))

    def _maintain(self, db, run_id, now):
        run = self._run(db, run_id)
        plan, _, budget = self._contract(run)
        if run['status'] in {'completed', 'failed', 'cancelled', 'expired'}:
            return
        if now >= run['deadline']:
            db.execute("UPDATE dag_runs SET status='expired' WHERE run_id=?", (run_id,))
            db.execute("""UPDATE dag_tasks SET status='cancelled',worker=NULL,token=NULL,expires=NULL,error_code='run_expired'
                          WHERE run_id=? AND status NOT IN ('completed','failed','blocked','cancelled')""", (run_id,))
            self._event(db, run_id, 'run_expired', {})
            return
        expired = db.execute("SELECT * FROM dag_tasks WHERE run_id=? AND status='leased' AND expires<=?", (run_id, now)).fetchall()
        for task in expired:
            self._fail_task(db, run_id, task, budget, 'lease_expired', now)
        if run['total_attempts'] >= budget.max_total_attempts:
            exhausted = db.execute("SELECT action_id FROM dag_tasks WHERE run_id=? AND status IN ('queued','retry_wait')", (run_id,)).fetchall()
            for task in exhausted:
                db.execute("UPDATE dag_tasks SET status='failed',error_code='total_attempts' WHERE run_id=? AND action_id=?", (run_id, task['action_id']))
                self._event(db, run_id, 'attempt_budget', dict(action_id=task['action_id']))
        self._block_dependants(db, run_id, plan)
        self._refresh_status(db, run_id)

    def maintain(self, run_id):
        """Persist expiry/recovery without requiring an idle worker to claim work."""
        with self._transaction() as db:
            self._maintain(db, run_id, self._now())
            return self._run(db, run_id)['status']

    def claim(self, run_id, worker, *, consent, on_battery=False,
              pool_id=None, cpu_slots=1, memory_bytes=1):
        """Atomically lease one dependency-ready action and optional pooled resources."""
        validate_worker(worker)
        with self._transaction() as db:
            now = self._now()
            self._require_consent(consent, now, on_battery)
            return self._claim_in_transaction(db, run_id, worker, now, pool_id=pool_id,
                                              cpu_slots=cpu_slots, memory_bytes=memory_bytes)

    def _claim_in_transaction(self, db, run_id, worker, now, *, pool_id=None,
                              cpu_slots=1, memory_bytes=1):
        """Shared by direct claims and the fair scheduler inside one write lock."""
        self._maintain(db, run_id, now)
        run = self._run(db, run_id)
        if run['status'] in {'completed', 'failed', 'cancelled', 'expired', 'paused'}:
            return None
        plan, permissions, budget = self._contract(run)
        self._approvals(run).require(plan)
        rows = {r['action_id']: r for r in db.execute('SELECT * FROM dag_tasks WHERE run_id=?', (run_id,))}
        if sum(r['status'] == 'leased' for r in rows.values()) >= budget.max_parallel_actions:
            return None
        for action in plan.proposal.actions:
            task = rows[action.action_id]
            if task['status'] not in {'queued', 'retry_wait'} or task['available'] > now:
                continue
            if any(rows[dep]['status'] != 'completed' for dep in action.depends_on):
                continue
            results, _ = committed_results(plan, run_id, rows)
            arguments = resolve(action.arguments, results)
            from .tool_registry import scientific_registry
            scientific_registry().validate(action.tool, arguments, permissions)
            if pool_id is not None:
                from .dag_scheduler import capacity_available
                if not capacity_available(db, pool_id, action.tool, cpu_slots, memory_bytes, now):
                    continue
            token = secrets.token_hex(32)
            expires = min(now+budget.lease_seconds, run['deadline'])
            attempt = task['attempts']+1
            db.execute("""UPDATE dag_tasks SET status='leased',attempts=?,worker=?,token=?,expires=?,error_code=NULL
                          WHERE run_id=? AND action_id=?""", (attempt, worker, token, expires, run_id, action.action_id))
            db.execute('UPDATE dag_tasks SET resource_pool=?,reserved_cpu=?,reserved_memory=?,reserved_tool=? WHERE run_id=? AND action_id=?',
                       (pool_id, cpu_slots if pool_id else 0, memory_bytes if pool_id else 0,
                        action.tool if pool_id else None, run_id, action.action_id))
            db.execute("UPDATE dag_runs SET total_attempts=total_attempts+1,status='running' WHERE run_id=?", (run_id,))
            self._event(db, run_id, 'leased', dict(action_id=action.action_id, attempt=attempt,
                                                   lease_id=fingerprint(token), expires=expires,
                                                   resource_pool=pool_id, cpu_slots=cpu_slots if pool_id else 0,
                                                   memory_bytes=memory_bytes if pool_id else 0, tool=action.tool))
            return dict(schema_version=1, run_id=run_id, action_id=action.action_id,
                        tool=action.tool, arguments=arguments, worker=worker,
                        token=token, expires=expires, attempt=attempt,
                        permissions=permissions_data(permissions),
                        budget=budget.to_data(), approval_head=run['approval_head'])
        return None

    def _lease(self, db, run_id, action_id, worker, token, now, *, completed_ok=False):
        validate_worker(worker)
        require_digest(token)
        row = db.execute('SELECT * FROM dag_tasks WHERE run_id=? AND action_id=?', (run_id, action_id)).fetchone()
        if row is None or row['worker'] != worker or row['token'] != token:
            raise LeaseConflict('Lease owner or fencing token mismatch')
        if completed_ok and row['status'] == 'completed':
            return row
        if row['status'] != 'leased' or row['expires'] <= now:
            raise LeaseConflict('Lease no longer active')
        return row

    def heartbeat(self, run_id, action_id, worker, token, *, consent, on_battery=False):
        with self._transaction() as db:
            now = self._now()
            self._require_consent(consent, now, on_battery)
            self._maintain(db, run_id, now)
            run = self._run(db, run_id)
            plan, _, budget = self._contract(run)
            if run['status'] not in {'ready', 'running'}:
                raise LeaseConflict('Run no longer accepts heartbeats')
            self._approvals(run).require(plan)
            self._lease(db, run_id, action_id, worker, token, now)
            expires = min(now+budget.lease_seconds, run['deadline'])
            db.execute('UPDATE dag_tasks SET expires=? WHERE run_id=? AND action_id=?', (expires, run_id, action_id))
            self._event(db, run_id, 'heartbeat', dict(action_id=action_id, expires=expires))
            return expires

    def complete(self, run_id, action_id, worker, token, result, *, consent, on_battery=False):
        """Replay exact science and atomically commit once against the live lease.

        Inputs for replay are loaded from committed dependency results, never
        accepted from a worker-supplied lease dictionary. Approval and fencing
        are checked again after replay inside the write transaction.
        """
        now = self._now()
        self._require_consent(consent, now, on_battery)
        with closing(self._connect()) as db:
            run = self._run(db, run_id)
            plan, permissions, budget = self._contract(run)
            action = next((a for a in plan.proposal.actions if a.action_id == action_id), None)
            if action is None:
                raise LookupError('Unknown DAG action')
            rows = {r['action_id']: r for r in db.execute('SELECT * FROM dag_tasks WHERE run_id=?', (run_id,))}
            if any(rows[dep]['status'] != 'completed' for dep in action.depends_on):
                raise LeaseConflict('Dependency is not committed')
            results, verified_receipts = committed_results(plan, run_id, rows)
            arguments = resolve(action.arguments, results)
            dependencies = {dep: verified_receipts[dep]['receipt_id'] for dep in action.depends_on}
            self._lease(db, run_id, action_id, worker, token, now, completed_ok=True)
        raw = canonical_json(result)
        if len(raw.encode()) > min(budget.max_result_bytes, permissions.max_output_bytes):
            raise ValueError('Result exceeds per-action transport budget')
        if not replay_scientific_result(action.tool, arguments, result):
            raise ValueError('Worker result failed independent scientific replay')
        receipt = result_receipt(run_id=run_id, action=action, arguments=arguments,
                                 result=result, dependencies=dependencies)
        with self._transaction() as db:
            now = self._now()
            self._maintain(db, run_id, now)
            run = self._run(db, run_id)
            task = self._lease(db, run_id, action_id, worker, token, now, completed_ok=True)
            if task['status'] == 'completed':
                if task['result_json'] != raw:
                    raise LeaseConflict('Completed result cannot be replaced')
                return json.loads(task['receipt_json'])
            if run['status'] not in {'ready', 'running'}:
                raise LeaseConflict('Run no longer accepts results')
            self._approvals(run).require(plan)
            self._require_consent(consent, now, on_battery)
            if run['result_bytes']+len(raw.encode()) > budget.max_total_result_bytes:
                raise ValueError('Whole-run result budget exhausted')
            db.execute("""UPDATE dag_tasks SET status='completed',result_json=?,receipt_json=?,error_code=NULL
                          WHERE run_id=? AND action_id=?""", (raw, canonical_json(receipt), run_id, action_id))
            db.execute('UPDATE dag_runs SET result_bytes=result_bytes+? WHERE run_id=?', (len(raw.encode()), run_id))
            self._event(db, run_id, 'completed', dict(action_id=action_id, receipt_id=receipt['receipt_id']))
            self._refresh_status(db, run_id)
            return receipt

    def fail(self, run_id, action_id, worker, token, code):
        if code not in FAILURE_CODES:
            raise ValueError('Fixed non-sensitive failure code required')
        with self._transaction() as db:
            now = self._now()
            self._maintain(db, run_id, now)
            run = self._run(db, run_id)
            plan, _, budget = self._contract(run)
            task = self._lease(db, run_id, action_id, worker, token, now)
            self._fail_task(db, run_id, task, budget, code, now)
            self._block_dependants(db, run_id, plan)
            self._refresh_status(db, run_id)
            return self._run(db, run_id)['status']

    def cancel(self, run_id, *, reason, action_id=None):
        """Cancellation fences running workers and blocks descendants atomically."""
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1024:
            raise ValueError('Explicit bounded cancellation reason required')
        with self._transaction() as db:
            run = self._run(db, run_id)
            plan, _, _ = self._contract(run)
            if action_id is None:
                if run['status'] == 'completed':
                    raise ValueError('Completed DAG cannot be cancelled')
                if run['status'] == 'cancelled':
                    return 'cancelled'
                db.execute("UPDATE dag_runs SET status='cancelled',cancel_reason=? WHERE run_id=?", (reason, run_id))
                db.execute("""UPDATE dag_tasks SET status='cancelled',worker=NULL,token=NULL,expires=NULL,error_code='run_cancelled'
                              WHERE run_id=? AND status NOT IN ('completed','failed','blocked','cancelled')""", (run_id,))
            else:
                task = db.execute('SELECT * FROM dag_tasks WHERE run_id=? AND action_id=?', (run_id, action_id)).fetchone()
                if task is None:
                    raise LookupError('Unknown DAG action')
                if task['status'] == 'completed':
                    raise ValueError('Completed action cannot be cancelled')
                if task['status'] in {'failed', 'blocked', 'cancelled'}:
                    return task['status']
                db.execute("""UPDATE dag_tasks SET status='cancelled',worker=NULL,token=NULL,expires=NULL,error_code='action_cancelled'
                              WHERE run_id=? AND action_id=?""", (run_id, action_id))
                self._block_dependants(db, run_id, plan)
                self._refresh_status(db, run_id)
            self._event(db, run_id, 'cancelled', dict(action_id=action_id, reason=reason))
            return self._run(db, run_id)['status']

    def snapshot(self, run_id):
        """Consistent diagnostic checkpoint. Lease fencing tokens are never exported."""
        with closing(self._connect()) as db:
            db.execute('BEGIN')
            result = self._snapshot_in_transaction(db, run_id)
            db.commit()
            return result

    def _snapshot_in_transaction(self, db, run_id):
        """Shared by read snapshots and atomic recovery validation before commit."""
        run = self._run(db, run_id)
        plan, permissions, budget = self._contract(run)
        self._approvals(run)
        rows = db.execute('SELECT * FROM dag_tasks WHERE run_id=? ORDER BY ordinal', (run_id,)).fetchall()
        tasks = []
        for row in rows:
            tasks.append(dict(action_id=row['action_id'], status=row['status'], attempts=row['attempts'],
                              available=row['available'], expires=row['expires'], error_code=row['error_code'],
                              result=json.loads(row['result_json']) if row['result_json'] else None,
                              receipt=json.loads(row['receipt_json']) if row['receipt_json'] else None))
        events = [dict(json.loads(row['event_json']), event_id=row['event_id']) for row in
                  db.execute('SELECT * FROM dag_events WHERE run_id=? ORDER BY sequence', (run_id,))]
        body = dict(schema_version=1, run_id=run_id, plan=plan.to_data(),
                    permissions=permissions_data(permissions), budget=budget.to_data(),
                    approvals=json.loads(run['approvals_json']), approval_head=run['approval_head'],
                    created=run['created'], deadline=run['deadline'], status=run['status'],
                    revision=run['revision'], total_attempts=run['total_attempts'],
                    result_bytes=run['result_bytes'], tasks=tasks, events=events,
                    limitations='Local trusted tools; no hostile-code sandbox, authenticated identities or external side effects')
        return dict(body, snapshot_id=fingerprint(body))

    def inspect(self, run_id, **kwargs):
        from .dag_inspection import inspect_checkpoint
        return inspect_checkpoint(self.snapshot(run_id), now=self._now(), **kwargs)

    def verify(self, run_id, *, replay=True):
        from .dag_replay import verify_dag_snapshot
        return verify_dag_snapshot(self.snapshot(run_id), replay=replay)
