"""Bounded disk-backed Forge generation with transactional restart checkpoints.

The SQLite database is the authoritative checkpoint. Each batch commits records
and its next index together. A failed generator/verifier/callback rolls back the
whole batch. Immutable JSONL exports are assembled in a sibling temporary folder
and renamed only after a complete export; existing destinations are never reused.

The name describes a streaming architecture, not a measured throughput claim.
Every invocation and export has explicit limits. No network or publication occurs.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile

from ..core.semantic_ir import canonical_json, fingerprint
from ..forge.deduplicate import semantic_fingerprint
from ..forge.reverse_builder import generate_task
from ..forge.solvers import solve_task
from ..forge.task_spec import FAMILIES, TaskSpec
from ..verify.trace import build_trace, VerificationTrace
from .semantic_leakage import LeakageAuditor
from .splits import SplitPolicy


class PipelineCorruption(ValueError):
    """Checkpoint, record or exported artifact failed independent validation."""


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'Invalid {name}')
    return value


def _text(value, name, maximum=4096):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'Invalid {name}')
    return value


def _json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise PipelineCorruption('Duplicate JSON field')
            result[key] = value
        return result
    try:
        return json.loads(text, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(PipelineCorruption('Nonfinite JSON')))
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise PipelineCorruption('Invalid checkpoint JSON') from exc


@dataclass(frozen=True)
class PipelineConfig:
    count: int
    seed: int
    license_id: str
    provenance: str
    families: tuple[str, ...] = FAMILIES
    sizes: tuple[int, ...] = (2, 3, 4)
    split_salt: str = 'forge-family-v1'

    def __post_init__(self):
        _integer(self.count, 'count', 1, 100000)
        _integer(self.seed, 'seed', 0, 2**63-1)
        _text(self.license_id, 'license_id', 256)
        _text(self.provenance, 'provenance')
        _text(self.split_salt, 'split_salt', 256)
        if (not isinstance(self.families, (tuple, list)) or not self.families
                or len(set(self.families)) != len(self.families)
                or any(f not in FAMILIES for f in self.families)):
            raise ValueError('Invalid generation families')
        if (not isinstance(self.sizes, (tuple, list)) or not self.sizes
                or len(set(self.sizes)) != len(self.sizes)
                or any(type(s) is not int or not 1 <= s <= 8 for s in self.sizes)):
            raise ValueError('Invalid generation sizes')
        object.__setattr__(self, 'families', tuple(self.families))
        object.__setattr__(self, 'sizes', tuple(self.sizes))

    def to_data(self):
        return {
            'schema_version': 1,
            'profile': 'transactional-forge-v1',
            'count': self.count,
            'seed': self.seed,
            'license_id': self.license_id,
            'provenance': self.provenance,
            'families': list(self.families),
            'sizes': list(self.sizes),
            'split_salt': self.split_salt,
        }

    @property
    def config_id(self):
        return fingerprint(self.to_data())

    @classmethod
    def from_data(cls, data):
        fields = {'schema_version', 'profile', 'count', 'seed', 'license_id', 'provenance',
                  'families', 'sizes', 'split_salt'}
        if (not isinstance(data, dict) or set(data) != fields or type(data['schema_version']) is not int or data['schema_version'] != 1
                or data['profile'] != 'transactional-forge-v1'):
            raise ValueError('Unsupported pipeline configuration')
        return cls(**{k: data[k] for k in fields - {'schema_version', 'profile'}})

    def source(self, index):
        _integer(index, 'source index', 0, self.count-1)
        family = self.families[index % len(self.families)]
        size = self.sizes[(index // len(self.families)) % len(self.sizes)]
        seed = int(fingerprint({'seed': self.seed, 'index': index, 'family': family, 'size': size})[:15], 16)
        return family, seed, size


def make_record(config, index):
    """Construct and independently verify the same canonical Forge v2 contracts."""
    family, seed, size = config.source(index)
    generated = generate_task(family, seed, size)
    task = generated.task
    witness = build_trace(task, generated.witness).to_data()
    solution = build_trace(task, solve_task(task)).to_data()
    if not witness['verification']['valid'] or not solution['verification']['valid']:
        raise ArithmeticError('Generated record failed independent verification')
    return {
        'schema_version': 2,
        'task': task.to_data(),
        'task_id': task.content_id,
        'semantic_id': semantic_fingerprint(task),
        'seed': seed,
        'generator_version': generated.generator_version,
        'witness_trace': witness,
        'solution_trace': solution,
        'split': SplitPolicy(salt=config.split_salt).split(task),
        'license_id': config.license_id,
        'provenance': config.provenance,
        'synthetic': True,
        'difficulty': {'label': 'uncalibrated'},
        'calibration_id': None,
    }


def validate_record(record, config, index, *, regenerate=True):
    try:
        if not isinstance(record, dict) or set(record) != {
            'schema_version', 'task', 'task_id', 'semantic_id', 'seed', 'generator_version',
            'witness_trace', 'solution_trace', 'split', 'license_id', 'provenance',
            'synthetic', 'difficulty', 'calibration_id',
        }:
            return False
        family, seed, size = config.source(index)
        task = TaskSpec.from_data(record['task'])
        if (task.family != family or task.size != size or record['seed'] != seed
                or type(record['seed']) is not int
                or type(record['schema_version']) is not int or record['schema_version'] != 2 or record['generator_version'] != 'inverse-v2'
                or record['task_id'] != task.content_id or record['semantic_id'] != semantic_fingerprint(task)
                or record['split'] != SplitPolicy(salt=config.split_salt).split(task)
                or record['license_id'] != config.license_id or record['provenance'] != config.provenance
                or record['synthetic'] is not True or record['difficulty'] != {'label': 'uncalibrated'}
                or record['calibration_id'] is not None):
            return False
        for key in ('witness_trace', 'solution_trace'):
            trace = VerificationTrace.from_data(record[key]).to_data()
            if trace['task_id'] != task.content_id or not trace['verification']['valid']:
                return False
        return not regenerate or canonical_json(record) == canonical_json(make_record(config, index))
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return False


class DatasetPipeline:
    """A single dataset checkpoint, supporting serialized concurrent writers.

    Generation happens inside BEGIN IMMEDIATE so concurrent process instances
    cannot duplicate an index or advance a checkpoint independently. No arbitrary
    worker-supplied records are accepted by the public generation method.
    """

    def __init__(self, directory, config, *, batch_size=32):
        if not isinstance(config, PipelineConfig):
            raise ValueError('PipelineConfig required')
        self.directory = Path(directory).absolute()
        if self.directory.is_symlink():
            raise ValueError('Checkpoint directory cannot be a symlink')
        self.directory.mkdir(parents=True, exist_ok=True)
        self.database = self.directory/'checkpoint.sqlite3'
        if self.database.is_symlink():
            raise ValueError('Checkpoint database cannot be a symlink')
        self.config = config
        self.batch_size = _integer(batch_size, 'batch size', 1, 1000)
        with closing(self._connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            db.execute('''CREATE TABLE IF NOT EXISTS records (
                source_index INTEGER PRIMARY KEY, task_id TEXT NOT NULL,
                semantic_id TEXT NOT NULL, split TEXT NOT NULL,
                payload TEXT NOT NULL, digest TEXT NOT NULL)''')
            existing = db.execute("SELECT substr(value,1,1048577) FROM metadata WHERE key='config'").fetchone()
            if existing is None:
                if db.execute('SELECT COUNT(*) FROM records').fetchone()[0]:
                    raise PipelineCorruption('Records exist without configuration')
                db.execute("INSERT INTO metadata VALUES ('config', ?)", (canonical_json(config.to_data()),))
                self._save_state(db, 0, '0'*64)
            elif _json(existing[0]) != config.to_data():
                raise ValueError('Checkpoint belongs to another configuration')
            self._check_state(db)

    def _connect(self):
        db = sqlite3.connect(self.database, timeout=30)
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA synchronous=FULL')
        return db

    def _save_state(self, db, next_index, chain):
        payload = {'schema_version': 1, 'config_id': self.config.config_id,
                   'next_index': next_index, 'chain': chain}
        data = {**payload, 'checkpoint_id': fingerprint(payload)}
        db.execute("INSERT OR REPLACE INTO metadata VALUES ('state', ?)", (canonical_json(data),))

    def _check_state(self, db):
        row = db.execute("SELECT substr(value,1,1048577) FROM metadata WHERE key='state'").fetchone()
        if row is None:
            raise PipelineCorruption('Missing checkpoint state')
        state = _json(row[0])
        if not isinstance(state, dict) or set(state) != {'schema_version', 'config_id', 'next_index', 'chain', 'checkpoint_id'}:
            raise PipelineCorruption('Invalid checkpoint fields')
        expected = {k: v for k, v in state.items() if k != 'checkpoint_id'}
        if state['checkpoint_id'] != fingerprint(expected) or state['config_id'] != self.config.config_id or type(state['schema_version']) is not int or state['schema_version'] != 1:
            raise PipelineCorruption('Checkpoint digest mismatch')
        _integer(state['next_index'], 'checkpoint index', 0, self.config.count)
        if not isinstance(state['chain'], str) or len(state['chain']) != 64 or any(c not in '0123456789abcdef' for c in state['chain']):
            raise PipelineCorruption('Invalid checkpoint chain')
        count, low, high = db.execute('SELECT COUNT(*), MIN(source_index), MAX(source_index) FROM records').fetchone()
        if count != state['next_index'] or (count and (low != 0 or high != count-1)):
            raise PipelineCorruption('Checkpoint index is not a contiguous record prefix')
        if count:
            row = db.execute('SELECT source_index,substr(payload,1,1048577),digest FROM records ORDER BY source_index DESC LIMIT 1').fetchone()
            if fingerprint(_json(row[1])) != row[2]:
                raise PipelineCorruption('Last committed record digest mismatch')
        elif state['chain'] != '0'*64:
            raise PipelineCorruption('Empty checkpoint has a nonempty chain')
        return state

    def checkpoint(self):
        with closing(self._connect()) as db, db:
            return dict(self._check_state(db))

    def generate(self, *, max_attempts=1000, before_commit=None):
        """Commit complete batches; callback failure rolls back its current batch.

        ``before_commit`` is a local fault-injection/monitor hook receiving the
        prospective checkpoint index. It never receives credentials or records.
        Successful earlier batches remain durable if a later batch fails.
        """
        _integer(max_attempts, 'max attempts per invocation', 1, 10000)
        if before_commit is not None and not callable(before_commit):
            raise ValueError('Callback must be callable')
        remaining = max_attempts
        while remaining:
            with closing(self._connect()) as db, db:
                db.execute('BEGIN IMMEDIATE')
                state = self._check_state(db)
                begin = state['next_index']
                end = min(self.config.count, begin+self.batch_size, begin+remaining)
                if begin == end:
                    return state
                chain = state['chain']
                for index in range(begin, end):
                    record = make_record(self.config, index)
                    payload = canonical_json(record)
                    if len(payload.encode('utf-8')) > 1048576:
                        raise ValueError('Generated record exceeds 1 MiB')
                    digest = fingerprint(record)
                    db.execute('INSERT INTO records VALUES (?,?,?,?,?,?)', (
                        index, record['task_id'], record['semantic_id'], record['split'], payload, digest))
                    chain = fingerprint({'previous': chain, 'source_index': index, 'record_digest': digest})
                self._save_state(db, end, chain)
                if before_commit is not None:
                    before_commit(end)
                remaining -= end-begin
        return self.checkpoint()

    def iter_records(self, *, max_records=100000):
        """Stream a stable read snapshot; close the iterator to release its connection."""
        _integer(max_records, 'read record limit', 1, 100000)
        with closing(self._connect()) as db:
            db.execute('BEGIN')
            state = self._check_state(db)
            if state['next_index'] > max_records:
                raise ValueError('Checkpoint exceeds caller read limit')
            cursor = db.execute('SELECT source_index,substr(payload,1,1048577),digest FROM records ORDER BY source_index')
            for index, payload, digest in cursor:
                if len(payload.encode('utf-8')) > 1048576:
                    raise PipelineCorruption('Stored record exceeds limit')
                record = _json(payload)
                if fingerprint(record) != digest:
                    raise PipelineCorruption('Stored record digest mismatch')
                yield index, record

    def audit(self, *, regenerate=True):
        """Verify every saved record, prefix chain and transitive identity split audit."""
        auditor = LeakageAuditor(max_records=self.config.count, max_nodes=max(2, self.config.count*2))
        chain = '0'*64
        with closing(self._connect()) as db:
            db.execute('BEGIN')
            state = self._check_state(db)
            rows = db.execute('SELECT source_index,task_id,semantic_id,split,substr(payload,1,1048577),digest FROM records ORDER BY source_index')
            for index, task_id, semantic_id, split, payload, digest in rows:
                if len(payload.encode('utf-8')) > 1048576:
                    raise PipelineCorruption('Stored record exceeds limit')
                record = _json(payload)
                if fingerprint(record) != digest or not validate_record(record, self.config, index, regenerate=regenerate):
                    raise PipelineCorruption('Record independent replay failed')
                if (task_id, semantic_id, split) != (record['task_id'], record['semantic_id'], record['split']):
                    raise PipelineCorruption('Indexed identities disagree with payload')
                chain = fingerprint({'previous': chain, 'source_index': index, 'record_digest': digest})
                auditor.add({'record_id': task_id, 'semantic_id': semantic_id, 'split': split, 'task': record['task']})
            if chain != state['chain']:
                raise PipelineCorruption('Checkpoint prefix chain mismatch')
        result = auditor.report()
        if not result['clean']:
            raise PipelineCorruption('Dataset contains cross-partition identity leakage')
        return {'checkpoint': state, 'leakage': result, 'regenerated': regenerate,
                'complete': state['next_index'] == self.config.count}

    def export(self, destination, *, require_complete=True, before_publish=None):
        """Write an immutable verified snapshot; never replace a user destination.

        The caller must use a private destination parent directory. Atomic rename
        protects ordinary failures, but hostile concurrent filesystem mutation is
        outside this local checkpoint contract.
        """
        destination = Path(destination).absolute()
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(destination)
        evidence = self.audit()
        if require_complete and not evidence['complete']:
            raise ValueError('Cannot export an incomplete dataset without explicit override')
        destination.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.dataset-export-', dir=destination.parent))
        try:
            counts = {'train': 0, 'validation': 0, 'test': 0}
            files = {}
            with closing(self._connect()) as db:
                db.execute('BEGIN')
                state = self._check_state(db)
                # Avoid exporting a checkpoint different from the audited prefix.
                if state != evidence['checkpoint']:
                    raise PipelineCorruption('Checkpoint changed during export preparation; retry')
                handles = {name: (stage/f'{name}.jsonl').open('w', encoding='utf-8', newline='\n')
                           for name in ('records', 'train', 'validation', 'test')}
                try:
                    for index, payload, digest in db.execute('SELECT source_index,substr(payload,1,1048577),digest FROM records ORDER BY source_index'):
                        record = _json(payload)
                        if fingerprint(record) != digest:
                            raise PipelineCorruption('Record changed during export')
                        line = canonical_json({'source_index': index, 'record': record})+'\n'
                        handles['records'].write(line)
                        handles[record['split']].write(line)
                        counts[record['split']] += 1
                    for handle in handles.values():
                        handle.flush()
                        os.fsync(handle.fileno())
                finally:
                    for handle in handles.values():
                        handle.close()
            for name in ('records', 'train', 'validation', 'test'):
                path = stage/f'{name}.jsonl'
                files[path.name] = _file_digest(path)
            card = {'schema_version': 1, 'config': self.config.to_data(), 'checkpoint': state,
                    'counts': counts, 'leakage': evidence['leakage'], 'complete': evidence['complete'],
                    'deduplication': 'duplicates retained with shared deterministic family split',
                    'throughput_claim': None}
            (stage/'card.json').write_text(canonical_json(card)+'\n', encoding='utf-8')
            files['card.json'] = _file_digest(stage/'card.json')
            manifest = {'schema_version': 1, 'files': files}
            (stage/'manifest.json').write_text(canonical_json(manifest)+'\n', encoding='utf-8')
            if before_publish is not None:
                before_publish(stage)
            if not verify_export(stage):
                raise PipelineCorruption('Export independent verification failed')
            if destination.exists() or destination.is_symlink():
                raise FileExistsError(destination)
            stage.rename(destination)
            return manifest
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def _file_digest(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        while True:
            block = handle.read(65536)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _bounded_json(path, maximum=1048576):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise PipelineCorruption('Invalid metadata file')
    return _json(path.read_text(encoding='utf-8'))


def _read_rows(path, *, max_rows):
    if path.is_symlink() or not path.is_file():
        raise PipelineCorruption('Invalid record file')
    with path.open('rb') as handle:
        index = 0
        while True:
            line = handle.readline(1048577)
            if not line:
                break
            if len(line) > 1048576 or not line.endswith(b'\n'):
                raise PipelineCorruption('Record line exceeds bounds or is incomplete')
            index += 1
            if index > max_rows:
                raise PipelineCorruption('Export exceeds configured record count')
            row = _json(line.decode('utf-8'))
            if not isinstance(row, dict) or set(row) != {'source_index', 'record'}:
                raise PipelineCorruption('Invalid export row wrapper')
            yield row


def verify_export(directory):
    """Validate hashes, regeneration, checkpoint chain, partitions and audit."""
    try:
        root = Path(directory)
        if root.is_symlink():
            return False
        manifest = _bounded_json(root/'manifest.json')
        expected_files = {'records.jsonl', 'train.jsonl', 'validation.jsonl', 'test.jsonl', 'card.json'}
        if (not isinstance(manifest, dict) or set(manifest) != {'schema_version', 'files'}
                or type(manifest['schema_version']) is not int or manifest['schema_version'] != 1 or not isinstance(manifest['files'], dict)
                or set(manifest['files']) != expected_files
                or {p.name for p in root.iterdir()} != expected_files | {'manifest.json'}):
            return False
        for name, digest in manifest['files'].items():
            path = root/name
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 16*1024**3:
                return False
            if _file_digest(path) != digest:
                return False
        card = _bounded_json(root/'card.json', maximum=16*1024**2)
        if set(card) != {'schema_version', 'config', 'checkpoint', 'counts', 'leakage', 'complete', 'deduplication', 'throughput_claim'}:
            return False
        config = PipelineConfig.from_data(card['config'])
        if not isinstance(card['counts'], dict) or set(card['counts']) != {'train', 'validation', 'test'}:
            return False
        for split_count in card['counts'].values():
            _integer(split_count, 'partition count', 0, config.count)
        state = card['checkpoint']
        if set(state) != {'schema_version', 'config_id', 'next_index', 'chain', 'checkpoint_id'}:
            return False
        payload = {k: v for k, v in state.items() if k != 'checkpoint_id'}
        if (state['checkpoint_id'] != fingerprint(payload) or state['config_id'] != config.config_id
                or type(state['schema_version']) is not int or state['schema_version'] != 1):
            return False
        _integer(state['next_index'], 'exported prefix', 0, config.count)
        if type(card['schema_version']) is not int or card['schema_version'] != 1 or card['complete'] is not (state['next_index'] == config.count):
            return False
        if card['throughput_claim'] is not None or card['deduplication'] != 'duplicates retained with shared deterministic family split':
            return False
        partitions = {split: iter(_read_rows(root/f'{split}.jsonl', max_rows=config.count))
                      for split in ('train', 'validation', 'test')}
        counts = {split: 0 for split in partitions}
        auditor = LeakageAuditor(max_records=config.count, max_nodes=max(2, config.count*2))
        chain, count = '0'*64, 0
        for row in _read_rows(root/'records.jsonl', max_rows=config.count):
            if type(row['source_index']) is not int or row['source_index'] != count or not validate_record(row['record'], config, count):
                return False
            record = row['record']
            split = record['split']
            if next(partitions[split], None) != row:
                return False
            counts[split] += 1
            count += 1
            chain = fingerprint({'previous': chain, 'source_index': row['source_index'], 'record_digest': fingerprint(record)})
            auditor.add({'record_id': record['task_id'], 'semantic_id': record['semantic_id'], 'split': split, 'task': record['task']})
        if any(next(rows, None) is not None for rows in partitions.values()):
            return False
        audit = auditor.report()
        return (count == state['next_index'] and chain == state['chain'] and counts == card['counts']
                and audit == card['leakage'] and audit['clean'])
    except (ValueError, TypeError, KeyError, OSError, ArithmeticError, StopIteration):
        return False
