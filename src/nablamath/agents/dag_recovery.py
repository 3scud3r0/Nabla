"""Bounded checkpoint archives and explicit reviewed local DAG recovery.

Archives contain scientific data and declared review metadata, never lease
fencing tokens. A recovered node still needs fresh contribution consent. Restore
requires an externally supplied checkpoint commitment and a current explicit
ApprovalLedger; a file's self-hash does not authenticate its author.

Restoring to a separate database can repeat pure calculations on two copies.
This protocol therefore supports only fixed scientific tools, never external
side effects or an exactly-once distributed publication/instrument guarantee.
"""
from contextlib import closing
import json
import os
from pathlib import Path
import tempfile

from ..core.semantic_contracts import require_digest
from ..core.semantic_ir import canonical_json, fingerprint
from .dag_contracts import DagBudget, experiment_from_data, permissions_from_data, preflight_dag
from .dag_replay import verify_dag_snapshot
from .durable_dag import DagStore
from .human_approval import ApprovalLedger

MAX_ARCHIVE_BYTES = 67108864


def _archive(snapshot):
    if not verify_dag_snapshot(snapshot):
        raise ValueError('Only scientifically replayed checkpoints can be archived')
    body = dict(schema_version=1, kind='approved-scientific-dag-checkpoint', checkpoint=snapshot)
    result = dict(body, archive_id=fingerprint(body))
    raw = canonical_json(result).encode('utf-8')
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise ValueError('Checkpoint archive exceeds bounded transport size')
    return result, raw


def export_checkpoint(store, run_id, path, *, overwrite=False):
    """Atomically publish a complete JSON archive with fsync and no partial target."""
    if not isinstance(store, DagStore) or type(overwrite) is not bool:
        raise ValueError('Durable DAG store and explicit overwrite flag required')
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    archive, raw = _archive(store.snapshot(run_id))
    descriptor, temporary = tempfile.mkstemp(prefix='.dag-checkpoint-', dir=target.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, target)
        else:
            # Linking the new inode fails atomically if a user file exists;
            # exists()+replace() would have an overwrite race here.
            os.link(temporary, target)
        return dict(archive_id=archive['archive_id'], snapshot_id=archive['checkpoint']['snapshot_id'],
                    run_id=run_id, bytes=len(raw))
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def load_checkpoint(path, *, expected_archive_id):
    require_digest(expected_archive_id)
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_ARCHIVE_BYTES+1)
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise ValueError('Checkpoint archive exceeds bounded transport size')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate archive JSON key')
            result[key] = value
        return result
    data = json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite archive number')))
    if (not isinstance(data, dict) or set(data) != {'schema_version', 'kind', 'checkpoint', 'archive_id'}
            or type(data['schema_version']) is not int or data['schema_version'] != 1
            or data['kind'] != 'approved-scientific-dag-checkpoint'):
        raise ValueError('Unknown checkpoint archive schema')
    body = {key: value for key, value in data.items() if key != 'archive_id'}
    if fingerprint(body) != data['archive_id'] or data['archive_id'] != expected_archive_id:
        raise ValueError('Checkpoint archive does not match externally expected commitment')
    if not verify_dag_snapshot(data['checkpoint']):
        raise ValueError('Archived DAG checkpoint failed scientific replay')
    return data['checkpoint']


def restore_checkpoint(store, snapshot, ledger, *, expected_snapshot_id):
    """Restore into an absent run, fencing every old lease and preserving budgets.

    Attempts and the original whole-run deadline are never reset. A previously
    leased action consumes its prior attempt and becomes a delayed retry only if
    its frozen budget permits. Completed receipts are kept without reexecution.
    Existing destination runs are never overwritten or implicitly merged.
    """
    if not isinstance(store, DagStore) or not isinstance(ledger, ApprovalLedger):
        raise ValueError('Durable DAG store and fresh explicit approval ledger required')
    require_digest(expected_snapshot_id)
    if not isinstance(snapshot, dict) or snapshot.get('snapshot_id') != expected_snapshot_id or not verify_dag_snapshot(snapshot):
        raise ValueError('Recovery checkpoint commitment or replay mismatch')
    plan = experiment_from_data(snapshot['plan'])
    permissions = permissions_from_data(snapshot['permissions'])
    budget = DagBudget.from_data(snapshot['budget'])
    run_id = preflight_dag(plan, permissions, budget)
    history = ledger.to_data()
    checked = ApprovalLedger.from_data(history)
    checked.require(plan)
    now = store._now()
    with store._transaction() as db:
        if db.execute('SELECT 1 FROM dag_runs WHERE run_id=?', (run_id,)).fetchone():
            raise ValueError('Destination run exists; explicit checkpoint comparison required')
        status = snapshot['status']
        if status in {'running', 'paused'}:
            status = 'ready'
        db.execute('''INSERT INTO dag_runs(run_id,plan_json,permissions_json,budget_json,approvals_json,
            approval_head,created,deadline,status,revision,total_attempts,result_bytes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
            (run_id, canonical_json(snapshot['plan']), canonical_json(snapshot['permissions']),
             canonical_json(snapshot['budget']), canonical_json(history), checked.head,
             snapshot['created'], snapshot['deadline'], status, snapshot['revision'],
             snapshot['total_attempts'], snapshot['result_bytes']))
        for ordinal, task in enumerate(snapshot['tasks']):
            task_status, code, available = task['status'], task['error_code'], task['available']
            if task_status == 'leased':
                eligible = (task['attempts'] < budget.max_attempts_per_action
                            and snapshot['total_attempts'] < budget.max_total_attempts)
                task_status = 'retry_wait' if eligible else 'failed'
                code = 'lease_expired'
                available = now+budget.retry_delay_seconds
            db.execute('''INSERT INTO dag_tasks(run_id,action_id,ordinal,status,attempts,available,
                result_json,receipt_json,error_code) VALUES(?,?,?,?,?,?,?,?,?)''',
                (run_id, task['action_id'], ordinal, task_status, task['attempts'], available,
                 canonical_json(task['result']) if task['result'] is not None else None,
                 canonical_json(task['receipt']) if task['receipt'] is not None else None, code))
        for event in snapshot['events']:
            body = {key: value for key, value in event.items() if key != 'event_id'}
            db.execute('INSERT INTO dag_events VALUES(?,?,?,?)', (run_id, event['sequence'], canonical_json(body), event['event_id']))
        store._event(db, run_id, 'restored', dict(snapshot_id=expected_snapshot_id,
                                                previous_approval_head=snapshot['approval_head'],
                                                approval_head=checked.head, old_leases_fenced=True))
        store._block_dependants(db, run_id, plan)
        store._maintain(db, run_id, now)
        store._refresh_status(db, run_id)
        if not verify_dag_snapshot(store._snapshot_in_transaction(db, run_id)):
            raise ValueError('Restored checkpoint did not satisfy replay invariants')
    return run_id


def compare_checkpoints(left, right):
    """Report branch progress and conflicts without merging budgets or authority."""
    if not verify_dag_snapshot(left) or not verify_dag_snapshot(right):
        raise ValueError('Both checkpoints require scientific replay')
    if left['run_id'] != right['run_id']:
        raise ValueError('Checkpoints have different frozen run contracts')
    a = {row['action_id']: row for row in left['tasks']}
    b = {row['action_id']: row for row in right['tasks']}
    shared, left_only, right_only, conflicts = [], [], [], []
    for name in a:
        ac = a[name]['status'] == 'completed'
        bc = b[name]['status'] == 'completed'
        if ac and bc:
            (shared if a[name]['receipt'] == b[name]['receipt'] else conflicts).append(name)
        elif ac:
            left_only.append(name)
        elif bc:
            right_only.append(name)
    return dict(run_id=left['run_id'], shared_completed=shared, left_only_completed=left_only,
                right_only_completed=right_only, conflicting_receipts=conflicts,
                same_scientific_progress=not left_only and not right_only and not conflicts,
                automatic_merge=False,
                limitations='Attempts, deadlines, approvals and audit histories are not merged')
