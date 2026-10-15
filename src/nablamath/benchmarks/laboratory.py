"""Reproducible simulated laboratory workload, not external scientific adoption."""
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from ..core.semantic_ir import canonical_json, fingerprint
from ..datasets.multimodal import build_sample
from ..datasets.schema import make_record
from ..datasets.semantic_fingerprint import semantic_fingerprint
from ..evaluation.lineage import audit_lineage
from ..evaluation.sealed import SealedEvaluation
from ..export.research_bundle import export_research_bundle, verify_research_bundle
from ..forge.reverse_builder import generate_task
from ..forge.solvers import solve_task
from ..forge.task_spec import FAMILIES, TaskSpec
from ..training import evaluate, verify_evaluation, compare_evaluations
from ..training.baselines import fit_nearest_neighbor, NearestNeighbor


class SolverReference:
    """Engineering upper reference; this is a solver, never a trained model."""
    content_id = 'laboratory-exact-solver-reference-v1'

    def predict(self, inputs):
        problem = next(m['content'] for m in inputs['modalities'] if m['kind'] == 'equation')
        return solve_task(TaskSpec(inputs['family'], problem, inputs['size']))


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(data) + '\n', encoding='utf-8')


def _protocol(per_family, seed):
    if type(per_family) is not int or not 1 <= per_family <= 64:
        raise ValueError('Expected 1–64 records per family')
    if type(seed) is not int or not 0 <= seed <= 2**31 - 1:
        raise ValueError('Expected bounded integer seed')
    return {'schema_version': 1, 'simulation': True, 'seed': seed,
            'per_family': per_family, 'sizes': [2, 3, 4],
            'families': list(FAMILIES), 'training_families': list(FAMILIES[:4]),
            'validation_families': list(FAMILIES[4:6]), 'test_families': list(FAMILIES[6:]),
            'models': ['nearest-all', 'nearest-text', 'exact-reference'],
            'selection_on_evaluation': False, 'family_holdout': True,
            'max_generation_attempts_per_family': per_family * 200,
            'scope': 'local simulated laboratory, synthetic tasks, no frontier model',
            'sealed_data_hidden_from_operator': False,
            'external_adoption_demonstrated': False}


def _generate(protocol):
    records, seen = [], set()
    for index, family in enumerate(FAMILIES):
        split = 'train' if index < 4 else 'validation' if index < 6 else 'test'
        accepted = 0
        for attempt in range(protocol['max_generation_attempts_per_family']):
            size = protocol['sizes'][accepted % len(protocol['sizes'])]
            generated = generate_task(family, protocol['seed'] + index * 100000 + attempt, size)
            record = make_record(generated.task, generated.witness, license_id='CC0-1.0',
                                 provenance='simulated laboratory constructor corpus v1',
                                 scope='bounded exact synthetic tasks',
                                 limitations='not an external benchmark or frontier model training', split=split)
            semantic = semantic_fingerprint(record)
            if semantic in seen:
                continue
            seen.add(semantic)
            records.append(record)
            accepted += 1
            if accepted == protocol['per_family']:
                break
        else:
            raise ValueError('Unique-task generation budget exhausted: ' + family)
    return records


def _lineage(records):
    return [{'id': r.content_id, 'split': r.to_data()['split'], 'parents': [],
             'groups': {'template': [r.task.family], 'semantic': [semantic_fingerprint(r)]}}
            for r in records]


def _cohorts(records):
    return {split: [build_sample(r) for r in records if r.to_data()['split'] == split]
            for split in ('train', 'validation', 'test')}


def _evaluate(models, cohorts, lineage):
    reports = {}
    for split in ('validation', 'test'):
        selected = cohorts['train'] + cohorts[split]
        ids = {s.record.content_id for s in selected}
        manifest = [row for row in lineage if row['id'] in ids]
        for name, model in models.items():
            reports[f'{split}-{name}'] = evaluate(
                model, cohorts[split], training_samples=cohorts['train'],
                benchmark_name='simulated-laboratory-' + split,
                modalities=('text',) if name == 'nearest-text' else ('text', 'equation', 'diagram'),
                lineage=manifest)
    return reports


def _controls(records, cohorts, reports):
    from ..datasets.store import RecordStore
    rows = _lineage(records)
    # An external missing ancestor connects records with otherwise distinct tasks.
    next(row for row in rows if row['split'] == 'train')['parents'] = ['missing-shared-original']
    next(row for row in rows if row['split'] == 'test')['parents'] = ['missing-shared-original']
    lineage_rejected = not audit_lineage(rows)['clean']
    forged = copy.deepcopy(reports['test-exact-reference'])
    forged['successes'] += 1
    forged['evaluation_id'] = fingerprint({k: v for k, v in forged.items() if k != 'evaluation_id'})
    metric_rejected = not verify_evaluation(forged, cohorts['test'], training_samples=cohorts['train'])
    with tempfile.TemporaryDirectory(prefix='nabla-lab-control-') as directory:
        store = RecordStore(Path(directory) / 'records.sqlite3')
        original = next(r for r in records if r.to_data()['split'] == 'train')
        store.ingest([original], batch_id='initial')
        unrelated = next(r for r in records if r.to_data()['split'] == 'test')
        try:
            store.ingest([unrelated, original.with_split('test')], batch_id='must-rollback')
            rollback = False
        except ValueError:
            rollback = [r.content_id for r in store.records()] == [original.content_id]
        root = Path(directory) / 'release'
        export_research_bundle(records, root, parquet=False, require_training_splits=True)
        card = json.loads((root / 'card.json').read_text(encoding='utf-8'))
        card['training_gain'] = 'established-by-simulated-frontier-lab'
        _save(root / 'card.json', card)
        manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
        manifest['files']['card.json'] = hashlib.sha256((root / 'card.json').read_bytes()).hexdigest()
        _save(root / 'manifest.json', manifest)
        card_rejected = not verify_research_bundle(root)
    return {'transitive_lineage_leak_rejected': lineage_rejected,
            'rehash_forged_success_count_rejected': metric_rejected,
            'conflicting_batch_fully_rolled_back': rollback,
            'rehash_unsupported_training_claim_rejected': card_rejected}


def _summary(protocol, records, reports, controls):
    result = {'schema_version': 1, 'simulation': True,
              'protocol_id': fingerprint(protocol), 'record_count': len(records),
              'split_counts': dict(sorted(Counter(r.to_data()['split'] for r in records).items())),
              'family_counts': dict(sorted(Counter(r.task.family for r in records).items())),
              'evaluations': {name: {'successes': r['successes'], 'total': r['total'],
                                    'accuracy': r['accuracy'], 'evaluation_id': r['evaluation_id']}
                              for name, r in sorted(reports.items())},
              'comparisons': {split: compare_evaluations(reports[split + '-nearest-text'],
                                                       reports[split + '-nearest-all'])
                              for split in ('validation', 'test')},
              'controls': controls, 'all_negative_controls_passed': all(controls.values()),
              'external_lab_adoption': False, 'frontier_model_gain_established': False,
              'external_learning_gain_established': False,
              'vision_completion_percent': None,
              'limitations': 'Synthetic constructor corpus; no real laboratory users, independent review, observed physical validation or frontier models. Solver reference is not a learned model. Commitments do not hide data from the local operator.'}
    return result


def run_laboratory_workload(destination, *, per_family=24, seed=951017, parquet=True):
    """Write protocol before generation/evaluation; publish a verified closed bundle."""
    protocol = _protocol(per_family, seed)
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.laboratory-', dir=destination.parent))
    try:
        _save(stage / 'protocol.json', protocol)
        records = sorted(_generate(protocol), key=lambda r: r.content_id)
        cohorts = _cohorts(records)
        lineage = _lineage(records)
        _save(stage / 'lineage.json', audit_lineage(lineage))
        export_research_bundle(records, stage / 'dataset', parquet=parquet, require_training_splits=True)
        commitments = {}
        for split in ('validation', 'test'):
            raw = (stage / 'dataset' / (split + '.jsonl')).read_bytes()
            sealed = SealedEvaluation.commit(raw, item_count=len(cohorts[split]),
                                             policy='fixed before model fitting; no tuning on outcomes')
            commitments[split] = {'sha256': sealed.commitment, 'count': sealed.item_count,
                                  'policy': sealed.policy}
        _save(stage / 'commitments.json', commitments)
        models = {'nearest-all': fit_nearest_neighbor(cohorts['train']),
                  'nearest-text': fit_nearest_neighbor(cohorts['train'], modalities=('text',)),
                  'exact-reference': SolverReference()}
        for name in ('nearest-all', 'nearest-text'):
            _save(stage / 'models' / (name + '.json'), models[name].to_data())
        reports = _evaluate(models, cohorts, lineage)
        for name, report in reports.items():
            _save(stage / 'evaluations' / (name + '.json'), report)
        controls = _controls(records, cohorts, reports)
        summary = _summary(protocol, records, reports, controls)
        _save(stage / 'summary.json', summary)
        _save(stage / 'manifest.json', {'schema_version': 1, 'files': {
            p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(stage.rglob('*')) if p.is_file()}})
        if not verify_laboratory_workload(stage):
            raise ValueError('Laboratory replay failed')
        stage.rename(destination)
        return summary
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def verify_laboratory_workload(directory):
    """Replay tasks, model inference, commitments, contamination and controls."""
    from ..datasets.serializer import iter_load
    from ..evaluation.lineage import verify_lineage_report
    try:
        root = Path(directory)
        paths = []
        total_bytes = 0
        for path in root.rglob('*'):
            if len(paths) >= 100 or path.is_symlink():
                return False
            paths.append(path)
            if path.is_file():
                total_bytes += path.stat().st_size
                if path.stat().st_size > 64 * 1024 * 1024 or total_bytes > 256 * 1024 * 1024:
                    return False
        def read(name):
            path = root / name
            if path.stat().st_size > 32 * 1024 * 1024:
                raise ValueError('Artifact too large')
            return json.loads(path.read_text(encoding='utf-8'))
        manifest = read('manifest.json')
        actual = {p.relative_to(root).as_posix() for p in paths if p.is_file() and p != root / 'manifest.json'}
        if manifest['schema_version'] != 1 or set(manifest['files']) != actual:
            return False
        for name in actual:
            path = root / name
            if path.stat().st_size > 64 * 1024 * 1024 or hashlib.sha256(path.read_bytes()).hexdigest() != manifest['files'][name]:
                return False
        protocol = read('protocol.json')
        if protocol != _protocol(protocol['per_family'], protocol['seed']):
            return False
        if not verify_research_bundle(root / 'dataset'):
            return False
        with (root / 'dataset/records.jsonl').open('rb') as stream:
            records = list(iter_load(stream))
        # Protocol declares the constructors/seeds, not merely arbitrary valid tasks.
        if [r.to_data() for r in records] != [r.to_data() for r in sorted(_generate(protocol), key=lambda r: r.content_id)]:
            return False
        lineage = read('lineage.json')
        if lineage != audit_lineage(_lineage(records)) or not verify_lineage_report(lineage) or not lineage['clean']:
            return False
        cohorts = _cohorts(records)
        commitments = read('commitments.json')
        if set(commitments) != {'validation', 'test'}:
            return False
        for split, value in commitments.items():
            sealed = SealedEvaluation.commit((root / 'dataset' / (split + '.jsonl')).read_bytes(),
                                             item_count=len(cohorts[split]),
                                             policy='fixed before model fitting; no tuning on outcomes')
            if value != {'sha256': sealed.commitment, 'count': sealed.item_count, 'policy': sealed.policy}:
                return False
        models = {'exact-reference': SolverReference()}
        for name in ('nearest-all', 'nearest-text'):
            models[name] = NearestNeighbor.from_data(read('models/' + name + '.json'))
            expected = fit_nearest_neighbor(cohorts['train'], modalities=('text',) if name == 'nearest-text' else ('text', 'equation', 'diagram'))
            if models[name].content_id != expected.content_id:
                return False
        reports = _evaluate(models, cohorts, lineage['manifest'])
        expected = {'protocol.json', 'lineage.json', 'commitments.json', 'summary.json'}
        expected.update('models/' + name + '.json' for name in ('nearest-all', 'nearest-text'))
        expected.update('evaluations/' + name + '.json' for name in reports)
        expected.update('dataset/' + p.name for p in (root / 'dataset').iterdir())
        if actual != expected:
            return False
        if any(read('evaluations/' + name + '.json') != report for name, report in reports.items()):
            return False
        controls = _controls(records, cohorts, reports)
        return read('summary.json') == _summary(protocol, records, reports, controls)
    except (ValueError, KeyError, TypeError, OSError, StopIteration, RuntimeError, IndexError, OverflowError):
        return False
