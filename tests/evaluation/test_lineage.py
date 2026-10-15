import copy
import pytest
from nablamath.evaluation.lineage import audit_lineage, verify_lineage_report


def row(key, split='train', parents=(), **groups):
    return dict(id=key, split=split, parents=list(parents), groups=groups)


def test_transitive_leakage_through_missing_ancestor_and_template():
    report = audit_lineage([
        row('train', parents=['unpublished-original']),
        row('image', parents=['unpublished-original'], template=['geometry-v1']),
        row('test', 'test', template=['geometry-v1']),
        row('independent', 'test', source=['different-book']),
    ])
    assert not report['clean']
    assert report['conflicts'] == [{'members': ['image', 'test', 'train'], 'splits': ['test', 'train']}]
    assert report['component_count'] == 2
    assert verify_lineage_report(report)
    changed = copy.deepcopy(report)
    changed['clean'] = True
    assert not verify_lineage_report(changed)


def test_namespaces_order_and_cycles_are_safe():
    entries = [row('a', parents=['b'], source=['same']), row('b', parents=['a']),
               row('c', 'test', template=['same'])]
    report = audit_lineage(entries)
    assert report['clean']
    assert report == audit_lineage(reversed(entries))
    assert not report['provenance_authenticated']
    assert not report['undeclared_equivalence_excluded']


@pytest.mark.parametrize('entries', [
    [row('a'), row('a')], [row('a', 'unknown')],
    [row('')], [row('a', template='not-a-list')],
    [row('a', arbitrary=['x'])],
])
def test_invalid_manifests_fail_closed(entries):
    with pytest.raises(ValueError):
        audit_lineage(entries)


def test_budgets_also_apply_to_generators_and_external_links():
    with pytest.raises(ValueError, match='Record budget'):
        audit_lineage((row(str(i)) for i in range(3)), max_records=2)
    with pytest.raises(ValueError, match='Link budget'):
        audit_lineage([row('a', parents=['x', 'y'])], max_links=1)


def test_validation_test_overlap_is_also_rejected():
    report = audit_lineage([row('a', 'validation', semantic=['exact-task']),
                            row('b', 'test', semantic=['exact-task'])])
    assert not report['clean']


def test_training_gate_binds_lineage_and_replays_it():
    from nablamath.core.semantic_ir import fingerprint
    from nablamath.forge.reverse_builder import generate_task
    from nablamath.datasets.schema import make_record
    from nablamath.datasets.multimodal import build_sample
    from nablamath.training import evaluate, verify_evaluation, compare_evaluations
    from nablamath.training import run_ablations

    def sample(family, split):
        generated = generate_task(family, 42, 2)
        record = make_record(generated.task, generated.witness, license_id='CC0-1.0',
                             provenance='fixture', scope='exact', limitations='synthetic', split=split)
        return build_sample(record)

    class Model:
        content_id = 'empty-v1'
        def predict(self, inputs):
            return {}

    training = [sample('polynomial_integral', 'train')]
    evaluation = [sample('linear_system', 'test')]
    entries = [row(s.record.content_id, s.record.to_data()['split'], template=[s.record.task.family])
               for s in training + evaluation]
    report = evaluate(Model(), evaluation, training_samples=training, benchmark_name='lineage', lineage=entries)
    assert verify_evaluation(report, evaluation, training_samples=training)
    ablations = run_ablations(training, evaluation, benchmark_name='lineage',
                             lineage=iter(entries), variants={'all': ('text',), 'equation': ('equation',)})
    assert all(verify_evaluation(item, evaluation, training_samples=training)
               for item in ablations['reports'].values())
    forged = copy.deepcopy(report)
    forged['contamination']['lineage']['component_count'] = 0
    forged['evaluation_id'] = fingerprint({k: v for k, v in forged.items() if k != 'evaluation_id'})
    assert not verify_evaluation(forged, evaluation)
    with pytest.raises(ValueError, match='exactly'):
        evaluate(Model(), evaluation, training_samples=training, benchmark_name='lineage', lineage=entries[:1])
    leaked = copy.deepcopy(entries)
    for entry in leaked:
        entry['groups'] = {'source': ['shared-original']}
    with pytest.raises(ValueError, match='Contaminação'):
        evaluate(Model(), evaluation, training_samples=training, benchmark_name='lineage', lineage=leaked)
    legacy = evaluate(Model(), evaluation, training_samples=training, benchmark_name='lineage')
    with pytest.raises(ValueError):
        compare_evaluations(report, legacy)
