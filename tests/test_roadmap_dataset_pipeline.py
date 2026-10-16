"""Transactional, adversarial and replay tests for bounded dataset pipelines."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3

import pytest

from nablamath.core.semantic_ir import fingerprint, canonical_json
from nablamath.datasets.semantic_leakage import (
    LeakageRecord, LeakageAuditor, audit_records, replay_audit,
)
from nablamath.datasets.large_scale_pipeline import (
    PipelineConfig, DatasetPipeline, PipelineCorruption,
    make_record, validate_record, verify_export,
)
from nablamath.forge.reverse_builder import generate_task
from nablamath.forge.deduplicate import semantic_fingerprint


def identity(name):
    return fingerprint({'fixture': name})


def record(name, split, *, semantic=None, parents=()):
    return LeakageRecord(identity(name), split, identity(semantic or name), tuple(identity(p) for p in parents))


def config(**overrides):
    values = dict(count=12, seed=42, license_id='CC0-1.0', provenance='local test construction')
    values.update(overrides)
    return PipelineConfig(**values)


def pipeline(tmp_path, **kwargs):
    return DatasetPipeline(tmp_path/'work', config(**kwargs), batch_size=3)


def test_transitive_lineage_connects_disjoint_descendants():
    rows = [record('a', 'train', parents=('unknown',)),
            record('b', 'train', parents=('a',)),
            record('c', 'test', parents=('b',)),
            record('d', 'validation', parents=('unknown',))]
    result = audit_records(rows)
    assert not result['clean']
    assert len(result['cross_split_components']) == 1
    component = result['cross_split_components'][0]
    assert component['splits'] == ['test', 'train', 'validation']
    assert component['reasons'] == ['declared_lineage']
    assert set(component['record_ids']) == {identity(n) for n in 'abcd'}
    assert replay_audit(result, reversed(rows))
    assert not result['hidden_equivalences_detected']


def test_exact_and_semantic_leakage_reported_separately():
    rows = [record('a', 'train'), record('a', 'test'),
            record('b', 'validation', semantic='a')]
    result = audit_records(rows)
    assert result['cross_split_components'][0]['reasons'] == ['exact_identity', 'semantic_identity']
    assert result['unique_exact_ids'] == 2
    assert result['records_checked'] == 3


def test_namespaces_avoid_false_collision():
    # A record's exact ID must not equal another record's semantic namespace.
    rows = [record('a', 'train', semantic='b'), record('b', 'test', semantic='c')]
    assert audit_records(rows)['clean']


def test_single_partition_dependencies_and_cycles_are_finite():
    rows = [record('a', 'train', parents=('b',)), record('b', 'train', parents=('a',))]
    assert audit_records(rows)['clean']
    assert audit_records([])['clean']


def test_conflicting_exact_identity_declarations_rejected_atomically():
    auditor = LeakageAuditor()
    auditor.add(record('a', 'train', parents=('p',)))
    snapshot = auditor.to_data()
    with pytest.raises(ValueError, match='Conflicting'):
        auditor.add(record('a', 'test', semantic='other', parents=('p',)))
    assert auditor.to_data() == snapshot
    with pytest.raises(ValueError, match='Conflicting'):
        auditor.add(record('a', 'test', parents=('q',)))
    assert auditor.to_data() == snapshot


def test_graph_and_record_bounds_do_not_leave_partial_additions():
    auditor = LeakageAuditor(max_records=2, max_nodes=3)
    auditor.add(record('a', 'train'))
    snapshot = auditor.to_data()
    with pytest.raises(ValueError, match='node limit'):
        auditor.add(record('b', 'test'))
    assert auditor.to_data() == snapshot
    auditor = LeakageAuditor(max_records=1)
    auditor.add(record('a', 'train'))
    with pytest.raises(ValueError, match='Record limit'):
        auditor.add(record('b', 'test'))
    assert auditor.report()['records_checked'] == 1


@pytest.mark.parametrize('change', [
    {'record_id': 'bad'}, {'semantic_id': 'A'*64}, {'split': 'holdout'},
    {'parents': [identity('x'), identity('x')]}, {'parents': [identity('a')]},
    {'parents': [identity(str(n)) for n in range(129)]}, {'extra': 1},
])
def test_malformed_leakage_declarations_fail_closed(change):
    data = record('a', 'train').to_data(); data.update(change)
    with pytest.raises(ValueError):
        LeakageRecord.from_data(data)


def test_embedded_task_semantics_recomputed_not_trusted():
    task = generate_task('linear_system', 3, 2).task
    data = {'record_id': task.content_id, 'semantic_id': semantic_fingerprint(task),
            'split': 'train', 'task': task.to_data()}
    assert LeakageRecord.from_data(data).record_id == task.content_id
    data['semantic_id'] = identity('forged')
    with pytest.raises(ValueError, match='semantic'):
        LeakageRecord.from_data(data)
    data['semantic_id'] = semantic_fingerprint(task)
    data['record_id'] = identity('forged')
    with pytest.raises(ValueError, match='exact'):
        LeakageRecord.from_data(data)


def test_auditor_snapshot_canonical_roundtrip_and_tamper():
    auditor = LeakageAuditor().extend([record('b', 'test', parents=('a',)), record('a', 'train')])
    snapshot = auditor.to_data()
    restored = LeakageAuditor.from_data(snapshot)
    assert restored.to_data() == snapshot
    assert restored.report() == auditor.report()
    snapshot['records'][0]['split'] = 'validation'
    with pytest.raises(ValueError):
        LeakageAuditor.from_data(snapshot)
    report = auditor.report(); report['clean'] = True
    assert not replay_audit(report, [record('b', 'test', parents=('a',)), record('a', 'train')])


def test_configuration_roundtrip_and_random_access_source():
    cfg = config(count=2000)
    assert PipelineConfig.from_data(cfg.to_data()) == cfg
    assert cfg.source(1001) == cfg.source(1001)
    assert cfg.source(1001) != cfg.source(1002)
    assert cfg.config_id != config(seed=43).config_id
    with pytest.raises(ValueError): cfg.source(2000)
    with pytest.raises(ValueError): cfg.source(True)


@pytest.mark.parametrize('kwargs', [
    {'count': 0}, {'count': 100001}, {'count': True}, {'seed': -1},
    {'license_id': ''}, {'provenance': ''}, {'families': ('unknown',)},
    {'families': ('linear_system', 'linear_system')}, {'sizes': (0,)},
    {'sizes': (True,)}, {'sizes': (2, 2)}, {'split_salt': ''},
])
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError): config(**kwargs)


def test_make_record_uses_canonical_verified_forge_contracts():
    cfg = config()
    for index in range(8):
        row = make_record(cfg, index)
        assert row['schema_version'] == 2
        assert row['witness_trace']['verification']['valid']
        assert row['solution_trace']['verification']['valid']
        assert validate_record(row, cfg, index)
        assert row == make_record(cfg, index)
        forged = copy.deepcopy(row); forged['provenance'] = 'changed'
        assert not validate_record(forged, cfg, index)
        forged = copy.deepcopy(row); forged['semantic_id'] = identity('fake')
        assert not validate_record(forged, cfg, index)
        forged = copy.deepcopy(row); forged['extra'] = True
        assert not validate_record(forged, cfg, index)


def test_transactional_batch_resume_matches_uninterrupted_prefix(tmp_path):
    cfg = config(count=17)
    first = DatasetPipeline(tmp_path/'a', cfg, batch_size=3)
    assert first.generate(max_attempts=5)['next_index'] == 5
    resumed = DatasetPipeline(tmp_path/'a', cfg, batch_size=4)
    assert resumed.generate(max_attempts=7)['next_index'] == 12
    assert resumed.generate()['next_index'] == 17
    other = DatasetPipeline(tmp_path/'b', cfg, batch_size=6)
    other.generate()
    assert list(resumed.iter_records()) == list(other.iter_records())
    assert resumed.checkpoint() == other.checkpoint()
    assert resumed.audit()['complete']
    assert resumed.audit()['leakage']['clean']


def test_fault_rolls_back_current_batch_only_and_can_restart(tmp_path):
    data = pipeline(tmp_path, count=10)
    def fail(index):
        if index == 6:
            raise RuntimeError('injected precommit failure')
    with pytest.raises(RuntimeError, match='injected'):
        data.generate(before_commit=fail)
    assert data.checkpoint()['next_index'] == 3
    assert len(list(data.iter_records())) == 3
    restarted = DatasetPipeline(tmp_path/'work', config(count=10), batch_size=2)
    restarted.generate()
    assert restarted.checkpoint()['next_index'] == 10
    assert restarted.audit()['complete']


def test_generator_failure_is_atomic(tmp_path, monkeypatch):
    from nablamath.datasets import large_scale_pipeline as implementation
    data = pipeline(tmp_path)
    actual = implementation.make_record
    def broken(cfg, index):
        if index == 2:
            raise ArithmeticError('generator failure')
        return actual(cfg, index)
    monkeypatch.setattr(implementation, 'make_record', broken)
    with pytest.raises(ArithmeticError): data.generate()
    assert data.checkpoint()['next_index'] == 0
    assert list(data.iter_records()) == []
    monkeypatch.setattr(implementation, 'make_record', actual)
    data.generate()
    assert data.audit()['complete']


def test_configuration_mismatch_preserves_checkpoint(tmp_path):
    data = pipeline(tmp_path); data.generate(max_attempts=3)
    before = data.checkpoint()
    with pytest.raises(ValueError, match='another configuration'):
        DatasetPipeline(tmp_path/'work', config(seed=99))
    assert data.checkpoint() == before
    assert len(list(data.iter_records())) == 3


def test_two_concurrent_writers_serialize_without_duplicate_indices(tmp_path):
    data = pipeline(tmp_path, count=16)
    other = DatasetPipeline(tmp_path/'work', config(count=16), batch_size=2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(item.generate, max_attempts=8) for item in (data, other)]
        for future in futures: future.result(timeout=30)
    assert data.checkpoint()['next_index'] == 16
    assert [index for index, _ in data.iter_records()] == list(range(16))
    assert data.audit()['complete']


def mutate_database(data, statement, params=()):
    with sqlite3.connect(data.database) as db:
        db.execute(statement, params)


def test_missing_prefix_row_is_detected_before_resume(tmp_path):
    data = pipeline(tmp_path); data.generate(max_attempts=6)
    mutate_database(data, 'DELETE FROM records WHERE source_index=1')
    with pytest.raises(PipelineCorruption): data.checkpoint()
    with pytest.raises(PipelineCorruption): data.generate()


def test_historical_record_corruption_detected_by_stream_and_replay(tmp_path):
    data = pipeline(tmp_path); data.generate(max_attempts=6)
    mutate_database(data, "UPDATE records SET payload='{}' WHERE source_index=0")
    with pytest.raises(PipelineCorruption): list(data.iter_records())
    with pytest.raises(PipelineCorruption): data.audit()


def test_rehashed_historical_corruption_still_fails_regeneration(tmp_path):
    data = pipeline(tmp_path); data.generate(max_attempts=6)
    forged = make_record(data.config, 0); forged['provenance'] = 'forged'
    mutate_database(data, 'UPDATE records SET payload=?,digest=? WHERE source_index=0',
                    (canonical_json(forged), fingerprint(forged)))
    with pytest.raises(PipelineCorruption): data.audit()


def test_indexed_identity_corruption_fails_audit(tmp_path):
    data = pipeline(tmp_path); data.generate(max_attempts=6)
    mutate_database(data, 'UPDATE records SET semantic_id=? WHERE source_index=0', (identity('fake'),))
    with pytest.raises(PipelineCorruption, match='Indexed'):
        data.audit()


def test_checkpoint_checksum_and_prefix_chain_corruption(tmp_path):
    data = pipeline(tmp_path); data.generate(max_attempts=6)
    state = data.checkpoint(); state['chain'] = identity('fake')
    payload = {k: v for k, v in state.items() if k != 'checkpoint_id'}
    state['checkpoint_id'] = fingerprint(payload)
    mutate_database(data, "UPDATE metadata SET value=? WHERE key='state'", (canonical_json(state),))
    with pytest.raises(PipelineCorruption, match='chain'):
        data.audit()
    state['checkpoint_id'] = identity('bad')
    mutate_database(data, "UPDATE metadata SET value=? WHERE key='state'", (canonical_json(state),))
    with pytest.raises(PipelineCorruption, match='digest'):
        data.checkpoint()


def test_read_bounds_and_idempotent_completion(tmp_path):
    data = pipeline(tmp_path, count=6); data.generate()
    state = data.checkpoint()
    assert data.generate() == state
    with pytest.raises(ValueError): list(data.iter_records(max_records=5))
    with pytest.raises(ValueError): data.generate(max_attempts=0)
    with pytest.raises(ValueError): data.generate(max_attempts=True)
    assert data.checkpoint() == state


def test_export_is_deterministic_verified_and_never_overwrites(tmp_path):
    data = pipeline(tmp_path); data.generate()
    a, b = tmp_path/'export-a', tmp_path/'export-b'
    assert data.export(a) == data.export(b)
    assert verify_export(a) and verify_export(b)
    assert {p.name: p.read_bytes() for p in a.iterdir()} == {p.name: p.read_bytes() for p in b.iterdir()}
    with pytest.raises(FileExistsError): data.export(a)
    card = json.loads((a/'card.json').read_text())
    assert sum(card['counts'].values()) == 12
    assert card['complete'] and card['throughput_claim'] is None


def test_incomplete_export_requires_explicit_override(tmp_path):
    data = pipeline(tmp_path); data.generate(max_attempts=2)
    destination = tmp_path/'partial'
    with pytest.raises(ValueError, match='incomplete'): data.export(destination)
    assert not destination.exists()
    data.export(destination, require_complete=False)
    assert verify_export(destination)
    assert not json.loads((destination/'card.json').read_text())['complete']


def test_export_failure_and_stage_mutation_do_not_publish(tmp_path):
    data = pipeline(tmp_path, count=4); data.generate()
    def fail(stage):
        raise RuntimeError('injected export failure')
    with pytest.raises(RuntimeError): data.export(tmp_path/'failed', before_publish=fail)
    assert not (tmp_path/'failed').exists()
    assert list(tmp_path.glob('.dataset-export-*')) == []
    def corrupt(stage):
        (stage/'records.jsonl').write_text('{}\n')
    with pytest.raises(PipelineCorruption): data.export(tmp_path/'corrupted', before_publish=corrupt)
    assert not (tmp_path/'corrupted').exists()
    assert data.audit()['complete']


def rehash_manifest(root, name):
    import hashlib
    manifest = json.loads((root/'manifest.json').read_text())
    manifest['files'][name] = hashlib.sha256((root/name).read_bytes()).hexdigest()
    (root/'manifest.json').write_text(canonical_json(manifest)+'\n')


def test_export_tamper_rehashed_partition_still_rejected(tmp_path):
    data = pipeline(tmp_path, count=8); data.generate()
    root = tmp_path/'export'; data.export(root)
    (root/'train.jsonl').write_text('')
    rehash_manifest(root, 'train.jsonl')
    assert not verify_export(root)


def test_export_unknown_file_symlink_and_manifest_path_escape_rejected(tmp_path):
    data = pipeline(tmp_path, count=2); data.generate()
    root = tmp_path/'export'; data.export(root)
    (root/'extra').write_text('unexpected')
    assert not verify_export(root)
    (root/'extra').unlink()
    original = (root/'records.jsonl').read_bytes()
    (root/'records.jsonl').unlink()
    outside = tmp_path/'outside'; outside.write_bytes(original)
    (root/'records.jsonl').symlink_to(outside)
    assert not verify_export(root)
    (root/'records.jsonl').unlink(); (root/'records.jsonl').write_bytes(original)
    manifest = json.loads((root/'manifest.json').read_text())
    manifest['files']['../outside'] = manifest['files'].pop('records.jsonl')
    (root/'manifest.json').write_text(canonical_json(manifest))
    assert not verify_export(root)


def test_export_rehashed_card_changes_cannot_claim_false_completeness(tmp_path):
    data = pipeline(tmp_path); data.generate(max_attempts=3)
    root = tmp_path/'partial'; data.export(root, require_complete=False)
    card = json.loads((root/'card.json').read_text()); card['complete'] = True
    (root/'card.json').write_text(canonical_json(card))
    rehash_manifest(root, 'card.json')
    assert not verify_export(root)


def test_checkpoint_symlink_refused_without_touching_target(tmp_path):
    target = tmp_path/'target'; target.mkdir()
    link = tmp_path/'link'; link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError): DatasetPipeline(link, config())
    assert list(target.iterdir()) == []
    work = tmp_path/'work'; work.mkdir()
    database = tmp_path/'outside.db'; database.write_bytes(b'preserve')
    (work/'checkpoint.sqlite3').symlink_to(database)
    with pytest.raises(ValueError): DatasetPipeline(work, config())
    assert database.read_bytes() == b'preserve'


def test_plan_beyond_legacy_thousand_limit_remains_bounded_per_invocation(tmp_path):
    cfg = config(count=1001, families=('polynomial_integral',), sizes=(2,))
    data = DatasetPipeline(tmp_path/'larger', cfg, batch_size=100)
    state = data.generate(max_attempts=1000)
    assert state['next_index'] == 1000
    assert not data.audit(regenerate=False)['complete']
    data.generate(max_attempts=1)
    assert data.checkpoint()['next_index'] == 1001
    assert data.audit()['complete']
    rows = data.iter_records(max_records=1001)
    assert sum(1 for _ in rows) == 1001


def test_empty_prefix_export_is_valid_only_with_explicit_partial_override(tmp_path):
    data = pipeline(tmp_path)
    destination = tmp_path/'empty'
    data.export(destination, require_complete=False)
    assert verify_export(destination)
    assert (destination/'records.jsonl').read_bytes() == b''
    assert json.loads((destination/'card.json').read_text())['checkpoint']['next_index'] == 0


def test_export_destination_appearing_during_staging_is_preserved(tmp_path):
    data = pipeline(tmp_path, count=2); data.generate()
    destination = tmp_path/'claimed'
    def competing_writer(stage):
        destination.mkdir()
        (destination/'user-file').write_text('preserve')
    with pytest.raises(FileExistsError):
        data.export(destination, before_publish=competing_writer)
    assert (destination/'user-file').read_text() == 'preserve'
    assert list(tmp_path.glob('.dataset-export-*')) == []


def test_integer_contracts_reject_float_or_boolean_equivalents():
    cfg = config(count=2)
    data = cfg.to_data()
    data['schema_version'] = True
    with pytest.raises(ValueError):
        PipelineConfig.from_data(data)
    row = make_record(cfg, 0)
    row['schema_version'] = 2.0
    assert not validate_record(row, cfg, 0)
    assert not validate_record(row, cfg, 0, regenerate=False)
    snapshot = LeakageAuditor().to_data()
    snapshot['schema_version'] = True
    # A boolean version compares equal to integer 1 in Python, but is not the contract.
    with pytest.raises(ValueError):
        LeakageAuditor.from_data(snapshot)


def test_record_replay_distinguishes_canonical_numeric_types_inside_traces():
    cfg = config(count=2)
    row = make_record(cfg, 0)
    # Numeric values in JSON are byte-level contract fields, even when Python == accepts them.
    row['witness_trace']['schema_version'] = float(row['witness_trace']['schema_version'])
    assert not validate_record(row, cfg, 0)


def test_export_rejects_rehashed_boolean_counts(tmp_path):
    data = pipeline(tmp_path, count=1)
    data.generate()
    root = tmp_path/'boolean-counts'
    data.export(root)
    card = json.loads((root/'card.json').read_text())
    for split, count in card['counts'].items():
        card['counts'][split] = bool(count)
    (root/'card.json').write_text(canonical_json(card))
    rehash_manifest(root, 'card.json')
    assert not verify_export(root)


def test_export_nested_untrusted_metadata_fails_closed_without_recursion_error(tmp_path):
    root = tmp_path/'nested-metadata'
    root.mkdir()
    # Under the byte limit, but beyond the interpreter's safe JSON nesting depth.
    (root/'manifest.json').write_text('[' * 5000 + '0' + ']' * 5000)
    assert not verify_export(root)


def test_export_rehashed_boolean_checkpoint_version_rejected(tmp_path):
    data = pipeline(tmp_path, count=1)
    data.generate()
    root = tmp_path/'boolean-checkpoint'
    data.export(root)
    card = json.loads((root/'card.json').read_text())
    state = card['checkpoint']
    state['schema_version'] = True
    state['checkpoint_id'] = fingerprint({key: value for key, value in state.items() if key != 'checkpoint_id'})
    (root/'card.json').write_text(canonical_json(card))
    rehash_manifest(root, 'card.json')
    assert not verify_export(root)
