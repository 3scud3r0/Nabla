"""Predeclared studies retain negative outcomes and reject post-hoc mutation."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import sqlite3

import pytest

from nablamath.benchmarks.preregistration import RegisteredComparison, StudyLedger
from nablamath.core.semantic_contracts import canonical_payload
from nablamath.core.semantic_ir import ScientificTask, fingerprint
from nablamath.evaluation.frozen import FrozenEvaluation
from nablamath.verification.independence import IndependencePolicy


def fixture(n=8):
    tasks = [ScientificTask('linear_system', matrix=((1,),), rhs=(i+1,)) for i in range(n)]
    lineage = [{'id': t.content_id, 'split': 'test', 'parents': [], 'groups': {}} for t in tasks]
    lineage.append({'id': 'separate-training', 'split': 'train', 'parents': [], 'groups': {}})
    predictions = [{'task_id':t.content_id, 'values':['0']} for t in tasks]
    protocol = FrozenEvaluation.freeze(tasks=tasks, lineage=lineage, baseline=predictions,
        policy='Fixed constructed exact linear cohort; not novel held-out science',
        actors=IndependencePolicy('proposer','solver','evaluator','reviewer'))
    reference = {'protocol_id':protocol.protocol_id, 'predictions':predictions}
    candidate = {'protocol_id':protocol.protocol_id, 'predictions':[
        {'task_id':t.content_id, 'values':[str(i+1)]} for i,t in enumerate(tasks)]}
    models = {'reference':fingerprint({'algorithm':'constant-zero'}),
              'candidate':fingerprint({'algorithm':'exact-solver'})}
    study = RegisteredComparison.register(protocol, models=models, owner='declared operator',
        reference_model='reference', minimum_delta='1/4', alpha='1/20')
    return study, protocol, {'reference':reference,'candidate':candidate}


def test_exact_paired_sign_test_and_no_inferential_overclaim():
    study, protocol, submissions = fixture()
    result = study.score(protocol, submissions)
    pair = result['comparisons']['candidate']
    assert pair['wins'] == 8 and pair['losses'] == 0
    assert pair['one_sided_sign_p'] == '1/256' and pair['delta'] == '1'
    assert pair['descriptive_threshold_met']
    assert pair['inferential_assumptions_validated'] is False
    assert result['scientific_gain_established'] is False
    assert study.replay(result, protocol, submissions)
    result['comparisons']['candidate']['delta'] = '1/2'
    result['result_id'] = fingerprint({k:v for k,v in result.items() if k!='result_id'})
    assert not study.replay(result, protocol, submissions)


def test_negative_outcome_and_model_coverage_are_preserved():
    study, protocol, submissions = fixture(3)
    submissions['candidate'] = deepcopy(submissions['reference'])
    result = study.score(protocol, submissions)
    assert not result['comparisons']['candidate']['descriptive_threshold_met']
    assert result['comparisons']['candidate']['one_sided_sign_p'] == '1'
    for name in ('candidate','reference'):
        bad = deepcopy(submissions)
        bad.pop(name)
        with pytest.raises(ValueError):
            study.score(protocol,bad)
    bad = deepcopy(submissions)
    bad['unregistered'] = bad['candidate']
    with pytest.raises(ValueError):
        study.score(protocol,bad)


@pytest.mark.parametrize('key,value', [('schema_version',True),('alpha','0'),('alpha','1'),
    ('alpha',0.05),('minimum_delta','-1/2'),('primary_metric','chosen-after-scoring'),
    ('stopping_rule','stop after first success'),('reference_model','missing')])
def test_registration_rejects_invalid_or_posthoc_protocol(key,value):
    study,_,_ = fixture()
    data = study.to_data()
    data[key] = value
    with pytest.raises(ValueError):
        RegisteredComparison(canonical_payload(data))


def test_registration_snapshots_models_and_protocol_binding():
    study, protocol, submissions = fixture()
    assert RegisteredComparison(study.manifest_json) == study
    models = study.to_data()['models']
    registered = RegisteredComparison.register(protocol, models=models, owner='op',reference_model='reference')
    identifier = registered.study_id
    models['candidate'] = '0'*64
    assert registered.study_id == identifier
    other = fixture(2)[1]
    with pytest.raises(ValueError):
        study.score(other,submissions)


def test_registration_precedes_outcome_and_results_cannot_be_replaced(tmp_path):
    study,protocol,submissions = fixture()
    ledger = StudyLedger(tmp_path/'studies.sqlite3')
    with pytest.raises(ValueError,match='Register'):
        ledger.record(study,protocol,submissions)
    assert ledger.register(study)
    assert not ledger.register(study)
    ledger.record(study,protocol,submissions)
    assert ledger.replay(study,protocol)
    with pytest.raises(ValueError,match='already'):
        ledger.record(study,protocol,submissions)
    assert StudyLedger(ledger.path).replay(study,protocol)


def test_concurrent_outcome_admission_commits_exactly_one(tmp_path):
    study,protocol,submissions = fixture()
    path = tmp_path/'concurrent.sqlite3'
    ledger = StudyLedger(path)
    ledger.register(study)
    def attempt(_):
        try:
            StudyLedger(path).record(study,protocol,submissions)
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(attempt,range(4))) == 1
    assert ledger.replay(study,protocol)


def test_database_corruption_is_rejected_after_rehash(tmp_path):
    study,protocol,submissions = fixture()
    ledger = StudyLedger(tmp_path/'corrupt.sqlite3')
    ledger.register(study)
    ledger.record(study,protocol,submissions)
    with sqlite3.connect(ledger.path) as db:
        data=json.loads(db.execute('SELECT result FROM outcomes').fetchone()[0])
        data['report']['scientific_gain_established'] = True
        data['report']['result_id']=fingerprint({k:v for k,v in data['report'].items() if k!='result_id'})
        db.execute('UPDATE outcomes SET result=?',(canonical_payload(data),))
    assert not ledger.replay(study,protocol)


def test_ledger_rejects_oversized_corrupt_results_without_decoding(tmp_path):
    study,protocol,submissions=fixture(2)
    ledger=StudyLedger(tmp_path/'oversized.sqlite3')
    ledger.register(study)
    ledger.record(study,protocol,submissions)
    with sqlite3.connect(ledger.path) as db:
        db.execute('UPDATE outcomes SET result=?',(' '*1_000_001,))
    assert not ledger.replay(study,protocol)
