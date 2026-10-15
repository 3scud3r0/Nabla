"""Governance receipts preserve scope and reject stale or altered evidence."""
from copy import deepcopy
import pytest
from nablamath.core.semantic_ir import fingerprint
from nablamath.knowledge.replication_protocol import ReplicationProtocol
from nablamath.discovery.independent_replication import record_replication, replay_replication
from nablamath.documents.document_model import Document, Section
from nablamath.documents.editorial_review import review_document, replay_editorial_review
from nablamath.knowledge.novelty import assess_relative_novelty, replay_novelty
from nablamath.knowledge.literature import LiteratureCorpus, LiteratureEntry
from nablamath.documents.citations import Citation
from nablamath.discovery.hypothesis import Hypothesis
from nablamath.forge.reverse_builder import generate_task
from nablamath.forge.difficulty import calibrate
from nablamath.knowledge.difficulty import difficulty_profile
from nablamath.knowledge.curriculum import build_curriculum, replay_curriculum


def artifact(value):
    return {fingerprint(value): value}


def protocol():
    return ReplicationProtocol('revision-1', 'owner', ('author',), 'accuracy', .8, 1.,
        tuple(artifact({'input': [1, 2]})), 'Execute frozen holdout and compute exact match')


def replication(**changes):
    args = dict(replicator='third-party', affiliations=['declared institution'], conflicts=[],
                measured=.9, evidence=artifact({'correct': 9, 'total': 10}),
                source_evidence=artifact({'input': [1, 2]}))
    args.update(changes)
    return record_replication(protocol(), **args)


def test_protocol_roundtrip_and_tampering():
    saved = protocol().to_data()
    assert ReplicationProtocol.from_data(saved) == protocol()
    saved['maximum'] = .9
    with pytest.raises(ValueError):
        ReplicationProtocol.from_data(saved)


@pytest.mark.parametrize('minimum,maximum', [(float('nan'), 1), (0, float('inf')), (2, 1), (True, 1)])
def test_protocol_rejects_bad_intervals(minimum, maximum):
    row = protocol().to_data()
    row.pop('protocol_id')
    row.update(minimum=minimum, maximum=maximum)
    with pytest.raises(ValueError):
        ReplicationProtocol(**row)


def test_negative_replication_and_replay():
    result = replication(measured=.1)
    assert result['outcome'] == 'negative_result'
    assert replay_replication(result, protocol())
    assert not result['external_identity_verified']
    result['outcome'] = 'within_preregistered_interval'
    assert not replay_replication(result, protocol())


@pytest.mark.parametrize('changes', [dict(replicator='author'), dict(conflicts=['author']),
    dict(evidence={'invented': {'count': 10}}), dict(source_evidence=artifact({'wrong': 1})),
    dict(measured=float('nan')), dict(affiliations=[])])
def test_replication_rejects_invalid_claims(changes):
    with pytest.raises(ValueError):
        replication(**changes)


def test_editorial_checks_resolve_evidence_and_bind_document_revision():
    evidence = artifact({'observed': 3})
    document = Document('Report', (Section('Result', 'Local measured result', tuple(evidence)),))
    review = review_document(document, reviewer='editor', authors=['author'], evidence=evidence)
    assert review['local_checks_passed'] and not review['visual_inspection_declared']
    assert replay_editorial_review(review, document)
    changed = Document('Changed', document.sections)
    assert not replay_editorial_review(review, changed)
    review['scientific_claims_validated'] = True
    assert not replay_editorial_review(review, document)


def test_editorial_missing_evidence_and_visual_defects():
    evidence = artifact({'pdf': 'artifact fixture'})
    document = Document('Report', (Section('Result', 'Claim', ('missing',)),))
    review = review_document(document, reviewer='editor', authors=['author'], evidence=evidence,
        visual_review={'artifact_id': next(iter(evidence)), 'notes': 'Operator inspected page 1', 'defects': ['clipped equation']})
    assert {issue['kind'] for issue in review['issues']} == {'unresolved_evidence', 'visual_defects'}
    assert not review['local_checks_passed']
    assert replay_editorial_review(review, document)
    with pytest.raises(ValueError):
        review_document(document, reviewer='author', authors=['author'], evidence=evidence)


def test_relative_novelty_resolves_reviewed_sources_without_global_claim():
    corpus = LiteratureCorpus([LiteratureEntry(Citation('source', 'Identity', ('Author',), 2020),
        'Local identity', ('identity',), 'supplied fixture', 'CC0', 'x+x')], provenance='test metadata')
    hypothesis = Hypothesis('2*x', 'local algebra')
    report = assess_relative_novelty(hypothesis, corpus, query='identity', reviewer='reviewer', references_consulted=['source'])
    assert report['screen']['status'] == 'local_equivalent_found'
    assert report['review_coverage'] == 1
    assert not report['global_novelty_established']
    assert replay_novelty(report, hypothesis, corpus)
    with pytest.raises(ValueError):
        assess_relative_novelty(hypothesis, corpus, query='identity', reviewer='reviewer', references_consulted=['fabricated'])
    report['screen']['status'] = 'novel'
    assert not replay_novelty(report, hypothesis, corpus)


def test_empty_corpus_never_proves_novelty():
    report = assess_relative_novelty(Hypothesis('x', 'fixture'), LiteratureCorpus([], provenance='empty'),
        query='identity', reviewer='reviewer', references_consulted=[])
    assert report['review_coverage'] is None
    assert report['screen']['status'] == 'novelty_not_established'


def test_curriculum_balances_families_and_replays_measurements():
    tasks = [generate_task(family, seed, 2).task for family in ('linear_system', 'factored_polynomial') for seed in (1, 2)]
    calibration = calibrate(tasks, budget=100000)
    utility = {task.content_id: {'score': i, 'evidence': artifact({'measured_gain': i, 'task': task.content_id})} for i, task in enumerate(tasks)}
    report = build_curriculum(calibration, tasks, utility=utility, limit=2)
    by_id = {task.content_id: task for task in tasks}
    assert len({by_id[key].family for key in report['selected_task_ids']}) == 2
    assert replay_curriculum(report, calibration, tasks)
    report['selected_task_ids'].reverse()
    assert not replay_curriculum(report, calibration, tasks)
    bad = deepcopy(calibration)
    bad['observations'][0]['candidate'] = 'invented'
    with pytest.raises(ValueError):
        difficulty_profile(bad, tasks)
    utility[tasks[0].content_id]['evidence'] = {'bad': {}}
    with pytest.raises(ValueError):
        build_curriculum(calibration, tasks, utility=utility, limit=2)


def test_replication_is_bound_to_frozen_protocol_not_just_rehashed_receipt():
    report = replication()
    changed = protocol().to_data()
    changed.pop('protocol_id')
    changed['maximum'] = .85
    assert not replay_replication(report, ReplicationProtocol(**changed))
    # Updating the receipt hash alone cannot promote a negative outcome.
    report = replication(measured=.1)
    report['outcome'] = 'within_preregistered_interval'
    report.pop('replication_id')
    report['replication_id'] = fingerprint(report)
    assert not replay_replication(report, protocol())


def test_editorial_visual_artifact_must_resolve_and_evidence_must_hash():
    document = Document('Report', (Section('Notes', 'Text'),))
    with pytest.raises(ValueError):
        review_document(document, reviewer='editor', authors=['author'], evidence={'false': {'value': 1}})
    with pytest.raises(ValueError):
        review_document(document, reviewer='editor', authors=['author'], evidence={},
            visual_review={'artifact_id': 'absent', 'notes': 'Looked', 'defects': []})
    review = review_document(document, reviewer='editor', authors=['author'], evidence={})
    assert review['issues'] == [{'kind': 'section_without_evidence'}]


def test_difficulty_and_curriculum_keep_unresolved_budget_outcomes():
    tasks = [generate_task('linear_system', 9, 2).task]
    calibration = calibrate(tasks, budget=1)
    profile = difficulty_profile(calibration, tasks)
    assert profile['profiles'][0]['label'] == 'unresolved_within_budget'
    assert profile['profiles'][0]['verified_successes'] == 0
    utility = {tasks[0].content_id: {'score': -1, 'evidence': artifact({'failure': 'budget exhausted'})}}
    report = build_curriculum(calibration, tasks, utility=utility, limit=1)
    assert replay_curriculum(report, calibration, tasks)
    with pytest.raises(ValueError):
        build_curriculum(calibration, tasks, utility=utility, limit=True)
