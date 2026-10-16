"""Persistent weighted-fair scientific DAG admission and resource reservations.

Reservations share the exact fenced task lease: completion, failure, cancellation
and expiry release CPU/memory/tool capacity through the task's status. Amounts
are declared cooperative admission, not OS usage measurement or hostile-code
containment. Fairness applies to cooperating local callers sharing SQLite.
"""
from contextlib import closing
import json

from ..core.resource_profiles import ResourceProfile
from ..core.semantic_contracts import require_text
from ..core.semantic_ir import canonical_json, fingerprint
from .dag_contracts import SCIENTIFIC_TOOLS, validate_worker
from .durable_dag import DagStore


def _configuration(profile, tool_limits):
    if not isinstance(profile, ResourceProfile):
        raise ValueError('ResourceProfile required')
    if not isinstance(tool_limits, dict) or not tool_limits or not set(tool_limits) <= SCIENTIFIC_TOOLS:
        raise ValueError('Explicit fixed scientific tool quotas required')
    if any(type(value) is not int or not 1 <= value <= 4096 for value in tool_limits.values()):
        raise ValueError('Tool quotas must be integers between one and 4096')
    return dict(profile=profile.to_data(), tool_limits=dict(sorted(tool_limits.items())))


def _pool(db, pool_id):
    require_text(pool_id, 'pool', limit=128)
    row = db.execute('SELECT * FROM dag_pools WHERE pool_id=?', (pool_id,)).fetchone()
    if row is None:
        raise LookupError('Unknown persistent resource pool')
    configuration = json.loads(row['configuration_json'])
    data = dict(configuration['profile'])
    version = data.pop('schema_version')
    if type(version) is not int or version != 1:
        raise ValueError('Unknown resource profile schema')
    profile = ResourceProfile(**data)
    expected = _configuration(profile, configuration['tool_limits'])
    if expected != configuration or fingerprint(expected) != row['configuration_id']:
        raise ValueError('Persistent pool configuration commitment mismatch')
    return row, profile, configuration['tool_limits']


def _usage(db, pool_id, now):
    rows = db.execute("""SELECT reserved_cpu,reserved_memory,reserved_tool FROM dag_tasks
                         WHERE resource_pool=? AND status='leased' AND expires>?""", (pool_id, now)).fetchall()
    tools = {tool: 0 for tool in SCIENTIFIC_TOOLS}
    for row in rows:
        if row['reserved_tool'] not in SCIENTIFIC_TOOLS or row['reserved_cpu'] < 1 or row['reserved_memory'] < 1:
            raise ValueError('Invalid persistent resource reservation')
        tools[row['reserved_tool']] += 1
    return dict(cpu_slots=sum(row['reserved_cpu'] for row in rows),
                memory_bytes=sum(row['reserved_memory'] for row in rows), active_tasks=len(rows), tools=tools)


def capacity_available(db, pool_id, tool, cpu_slots, memory_bytes, now):
    """Called under the DAG write lock immediately before its fenced lease insert."""
    if type(cpu_slots) is not int or cpu_slots < 1 or type(memory_bytes) is not int or memory_bytes < 1:
        raise ValueError('Positive integer CPU and memory reservations required')
    _, profile, limits = _pool(db, pool_id)
    used = _usage(db, pool_id, now)
    return (tool in limits and used['cpu_slots']+cpu_slots <= profile.cpu_slots
            and used['memory_bytes']+memory_bytes <= profile.memory_bytes
            and used['active_tasks']+1 <= profile.max_tasks and used['tools'][tool]+1 <= limits[tool])


class FairDagScheduler:
    """Lease adds 1/weight to persistent virtual finish; ready runs sort by finish.

    Dependencies, backoff, paused approvals and occupied quotas are skipped
    without charging fairness debt. Ties use enrollment order and immutable ID.
    """
    def __init__(self, store):
        if not isinstance(store, DagStore):
            raise ValueError('Durable DAG coordinator required')
        self.store = store
        with closing(store._connect()) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS dag_pools(pool_id TEXT PRIMARY KEY,
                    configuration_json TEXT NOT NULL,configuration_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS dag_schedule(pool_id TEXT NOT NULL,run_id TEXT NOT NULL,
                    weight INTEGER NOT NULL,virtual_finish REAL NOT NULL,enrollment INTEGER NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,dispatches INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(pool_id,run_id),FOREIGN KEY(run_id) REFERENCES dag_runs(run_id));
                CREATE TABLE IF NOT EXISTS dag_pool_events(pool_id TEXT NOT NULL,sequence INTEGER NOT NULL,
                    event_json TEXT NOT NULL,event_id TEXT NOT NULL,PRIMARY KEY(pool_id,sequence));
            ''')

    def _event(self, db, pool_id, kind, payload):
        last = db.execute('SELECT sequence,event_id FROM dag_pool_events WHERE pool_id=? ORDER BY sequence DESC LIMIT 1', (pool_id,)).fetchone()
        body = dict(schema_version=1, pool_id=pool_id, sequence=last['sequence']+1 if last else 0,
                    kind=kind, payload=payload, previous=last['event_id'] if last else None)
        db.execute('INSERT INTO dag_pool_events VALUES(?,?,?,?)', (pool_id, body['sequence'], canonical_json(body), fingerprint(body)))

    def register_pool(self, pool_id, profile, *, tool_limits):
        require_text(pool_id, 'pool', limit=128)
        configuration = _configuration(profile, tool_limits)
        configuration_id = fingerprint(configuration)
        with self.store._transaction() as db:
            existing = db.execute('SELECT configuration_id FROM dag_pools WHERE pool_id=?', (pool_id,)).fetchone()
            if existing is not None:
                _pool(db, pool_id)
                if existing['configuration_id'] != configuration_id:
                    raise ValueError('Existing pool requires explicit CAS resize')
                return configuration_id
            db.execute('INSERT INTO dag_pools VALUES(?,?,?)', (pool_id, canonical_json(configuration), configuration_id))
            self._event(db, pool_id, 'registered', dict(configuration_id=configuration_id))
            return configuration_id

    def resize_pool(self, pool_id, profile, *, tool_limits, expected_configuration_id):
        configuration = _configuration(profile, tool_limits)
        configuration_id = fingerprint(configuration)
        with self.store._transaction() as db:
            previous, _, _ = _pool(db, pool_id)
            if previous['configuration_id'] != expected_configuration_id:
                raise ValueError('Stale resource pool configuration')
            used = _usage(db, pool_id, self.store._now())
            if (used['cpu_slots'] > profile.cpu_slots or used['memory_bytes'] > profile.memory_bytes
                    or used['active_tasks'] > profile.max_tasks
                    or any(count > tool_limits.get(tool, 0) for tool, count in used['tools'].items())):
                raise ValueError('Pool resize would strand active reservations')
            db.execute('UPDATE dag_pools SET configuration_json=?,configuration_id=? WHERE pool_id=?', (canonical_json(configuration), configuration_id, pool_id))
            self._event(db, pool_id, 'resized', dict(previous=expected_configuration_id, configuration_id=configuration_id))
            return configuration_id

    def enroll(self, pool_id, run_id, *, weight=1):
        if type(weight) is not int or not 1 <= weight <= 100:
            raise ValueError('Fairness weight must be an integer between one and 100')
        with self.store._transaction() as db:
            _pool(db, pool_id)
            self.store._contract(self.store._run(db, run_id))
            existing = db.execute('SELECT * FROM dag_schedule WHERE pool_id=? AND run_id=?', (pool_id, run_id)).fetchone()
            if existing:
                if existing['weight'] != weight:
                    raise ValueError('Changing fairness weight requires explicit reweight')
                if not existing['active']:
                    db.execute('UPDATE dag_schedule SET active=1 WHERE pool_id=? AND run_id=?', (pool_id, run_id))
                    self._event(db, pool_id, 'resumed', dict(run_id=run_id))
                return
            if db.execute('SELECT COUNT(*) FROM dag_schedule WHERE pool_id=?', (pool_id,)).fetchone()[0] >= 1000:
                raise ValueError('Pool enrollment quota reached')
            enrollment = db.execute('SELECT COALESCE(MAX(enrollment),-1)+1 FROM dag_schedule WHERE pool_id=?', (pool_id,)).fetchone()[0]
            floor = db.execute('SELECT COALESCE(MIN(virtual_finish),0) FROM dag_schedule WHERE pool_id=? AND active=1', (pool_id,)).fetchone()[0]
            db.execute('INSERT INTO dag_schedule(pool_id,run_id,weight,virtual_finish,enrollment) VALUES(?,?,?,?,?)', (pool_id, run_id, weight, floor, enrollment))
            self._event(db, pool_id, 'enrolled', dict(run_id=run_id, weight=weight, virtual_finish=floor))

    def reweight(self, pool_id, run_id, *, weight, expected_weight):
        if type(weight) is not int or not 1 <= weight <= 100:
            raise ValueError('Invalid fairness weight')
        with self.store._transaction() as db:
            _pool(db, pool_id)
            row = db.execute('SELECT weight FROM dag_schedule WHERE pool_id=? AND run_id=?', (pool_id, run_id)).fetchone()
            if row is None:
                raise LookupError('Run is not enrolled')
            if row['weight'] != expected_weight:
                raise ValueError('Stale fairness weight')
            db.execute('UPDATE dag_schedule SET weight=? WHERE pool_id=? AND run_id=?', (weight, pool_id, run_id))
            self._event(db, pool_id, 'reweighted', dict(run_id=run_id, previous=expected_weight, weight=weight))

    def suspend(self, pool_id, run_id):
        """Stop dispatch without invalidating existing fenced scientific leases."""
        with self.store._transaction() as db:
            _pool(db, pool_id)
            row = db.execute('SELECT active FROM dag_schedule WHERE pool_id=? AND run_id=?', (pool_id, run_id)).fetchone()
            if row is None:
                raise LookupError('Run is not enrolled')
            if row['active']:
                db.execute('UPDATE dag_schedule SET active=0 WHERE pool_id=? AND run_id=?', (pool_id, run_id))
                self._event(db, pool_id, 'suspended', dict(run_id=run_id))

    def claim_next(self, pool_id, worker, *, consent, on_battery=False, cpu_slots=1, memory_bytes=1):
        validate_worker(worker)
        with self.store._transaction() as db:
            now = self.store._now()
            self.store._require_consent(consent, now, on_battery)
            _pool(db, pool_id)
            candidates = db.execute('SELECT * FROM dag_schedule WHERE pool_id=? AND active=1 ORDER BY virtual_finish,enrollment,run_id', (pool_id,)).fetchall()
            for row in candidates:
                lease = self.store._claim_in_transaction(db, row['run_id'], worker, now, pool_id=pool_id, cpu_slots=cpu_slots, memory_bytes=memory_bytes)
                if lease is None:
                    run = self.store._run(db, row['run_id'])
                    if run['status'] in {'completed', 'failed', 'cancelled', 'expired'}:
                        db.execute('UPDATE dag_schedule SET active=0 WHERE pool_id=? AND run_id=?', (pool_id, row['run_id']))
                        self._event(db, pool_id, 'terminal', dict(run_id=row['run_id'], status=run['status']))
                    continue
                finish = row['virtual_finish']+1/row['weight']
                db.execute('UPDATE dag_schedule SET virtual_finish=?,dispatches=dispatches+1 WHERE pool_id=? AND run_id=?', (finish, pool_id, row['run_id']))
                self._event(db, pool_id, 'dispatched', dict(run_id=row['run_id'], action_id=lease['action_id'], attempt=lease['attempt'], virtual_finish=finish, cpu_slots=cpu_slots, memory_bytes=memory_bytes))
                lease['resource_pool'] = pool_id
                return lease
            return None

    def recover(self, pool_id):
        """Recover expired leases after restart without resetting fairness debt."""
        with self.store._transaction() as db:
            _pool(db, pool_id)
            rows = db.execute('SELECT run_id FROM dag_schedule WHERE pool_id=?', (pool_id,)).fetchall()
            for row in rows:
                self.store._maintain(db, row['run_id'], self.store._now())
        return self.snapshot(pool_id)

    def snapshot(self, pool_id):
        with closing(self.store._connect()) as db:
            db.execute('BEGIN')
            row, _, _ = _pool(db, pool_id)
            queue = [dict(item) for item in db.execute('SELECT run_id,weight,virtual_finish,enrollment,active,dispatches FROM dag_schedule WHERE pool_id=? ORDER BY enrollment,run_id', (pool_id,))]
            events = [dict(json.loads(item['event_json']), event_id=item['event_id']) for item in db.execute('SELECT * FROM dag_pool_events WHERE pool_id=? ORDER BY sequence', (pool_id,))]
            body = dict(schema_version=1, pool_id=pool_id, configuration=json.loads(row['configuration_json']),
                        configuration_id=row['configuration_id'], usage=_usage(db, pool_id, self.store._now()), queue=queue, events=events,
                        limitations='Persistent cooperative admission; no OS measurement or authenticated multi-host fairness')
            db.commit()
            return dict(body, snapshot_id=fingerprint(body))

    def verify(self, pool_id):
        """Replay fairness debt, configuration lineage and queue transitions."""
        try:
            snapshot = self.snapshot(pool_id)
            previous = None
            expected = {}
            configuration_id = None
            for sequence, event in enumerate(snapshot['events']):
                body = {key: value for key, value in event.items() if key != 'event_id'}
                if (event['sequence'] != sequence or event['previous'] != previous
                        or event['pool_id'] != pool_id or fingerprint(body) != event['event_id']):
                    return False
                kind, payload = event['kind'], event['payload']
                if sequence == 0 and kind != 'registered':
                    return False
                if kind == 'registered':
                    if configuration_id is not None:
                        return False
                    configuration_id = payload['configuration_id']
                elif kind == 'resized':
                    if payload['previous'] != configuration_id:
                        return False
                    configuration_id = payload['configuration_id']
                elif kind == 'enrolled':
                    name = payload['run_id']
                    if name in expected:
                        return False
                    expected[name] = dict(run_id=name, weight=payload['weight'],
                                          virtual_finish=payload['virtual_finish'],
                                          enrollment=len(expected), active=1, dispatches=0)
                elif kind in {'resumed', 'suspended', 'terminal'}:
                    expected[payload['run_id']]['active'] = 1 if kind == 'resumed' else 0
                elif kind == 'reweighted':
                    row = expected[payload['run_id']]
                    if row['weight'] != payload['previous']:
                        return False
                    row['weight'] = payload['weight']
                elif kind == 'dispatched':
                    row = expected[payload['run_id']]
                    if not row['active']:
                        return False
                    row['virtual_finish'] += 1/row['weight']
                    row['dispatches'] += 1
                    if row['virtual_finish'] != payload['virtual_finish']:
                        return False
                else:
                    return False
                previous = event['event_id']
            if configuration_id != snapshot['configuration_id']:
                return False
            if snapshot['queue'] != sorted(expected.values(), key=lambda row: (row['enrollment'], row['run_id'])):
                return False
            used = snapshot['usage']
            configuration = snapshot['configuration']
            profile = configuration['profile']
            return (used['cpu_slots'] <= profile['cpu_slots']
                    and used['memory_bytes'] <= profile['memory_bytes']
                    and used['active_tasks'] <= profile['max_tasks']
                    and all(count <= configuration['tool_limits'].get(tool, 0) for tool, count in used['tools'].items()))
        except (ValueError, KeyError, TypeError, LookupError, ArithmeticError):
            return False
