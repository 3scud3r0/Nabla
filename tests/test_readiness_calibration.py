"""Scientific checks do not silently promote readiness or discard failures."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from nablamath.benchmarks import readiness as r
from nablamath.core.semantic_ir import fingerprint

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT/'docs/acceptance/evidence_matrix.json'


def test_integration_campaign_exact_reproducible_and_seeded():
    first = r.integration_metamorphisms(cases=25, seed=41)
    assert first == r.integration_metamorphisms(cases=25, seed=41)
    assert first['passed'] and first['executed'] == 25
    assert first['corpus_chain'] != r.integration_metamorphisms(cases=25, seed=42)['corpus_chain']


def test_differential_campaign_uses_real_optional_sympy():
    pytest.importorskip('sympy')
    first = r.differential_arithmetic(cases=64, seed=19)
    assert first['passed'] and first['executed'] == 64
    assert first['disagreements'] == []
    assert first == r.differential_arithmetic(cases=64, seed=19)
    assert first['fit_on_cases'] is False


def test_differential_campaign_retains_disagreement(monkeypatch):
    pytest.importorskip('sympy')
    original = r.evaluate
    monkeypatch.setattr(r, 'evaluate', lambda expr, values: original(expr, values)+1)
    result = r.differential_arithmetic(cases=5)
    assert not result['passed'] and result['executed'] == 5
    assert len(result['disagreements']) == 5
    assert [item['index'] for item in result['disagreements']] == list(range(5))


def test_integration_campaign_retains_failed_certificates(monkeypatch):
    original = r.integrate_rational
    class Failed:
        def __init__(self, value):
            self.value = value
        def __getattr__(self, name):
            return getattr(self.value, name)
        def verify(self):
            return False
    monkeypatch.setattr(r, 'integrate_rational', lambda *a, **kw: Failed(original(*a, **kw)))
    result = r.integration_metamorphisms(cases=4)
    assert not result['passed'] and len(result['failures']) == 4


@pytest.mark.parametrize('value', [True, False, 0, -1, 100001, 2.5, '5'])
def test_counts_reject_unbounded_or_coerced_inputs(value):
    with pytest.raises(ValueError):
        r.differential_arithmetic(cases=value)
    with pytest.raises(ValueError):
        r.integration_metamorphisms(cases=value)


@pytest.mark.parametrize('seed', [True, -1, 2**32, '1', 1.5])
def test_seed_is_explicit_bounded_integer(seed):
    with pytest.raises(ValueError):
        r.integration_metamorphisms(cases=1, seed=seed)


def test_matrix_readout_never_promotes_partial_to_validated():
    result = r.roadmap_readiness(MATRIX)
    assert sum(result['counts'].values()) == 213
    assert result['full_readiness_established'] is False
    assert result['independent_evidence_authenticated'] is False
    assert len(result['unresolved_ids']) == 213-result['counts']['validated']


def test_duplicate_matrix_id_and_unsupported_status_rejected(tmp_path):
    data = json.loads(MATRIX.read_text())
    for mutation in ('duplicate', 'status', 'review'):
        copy = deepcopy(data)
        if mutation == 'duplicate':
            copy['requirements'][1]['id'] = 1
        elif mutation == 'status':
            copy['requirements'][0]['status'] = 'tested'
        else:
            copy['requirements'][0].update(status='validated', reviewer=None)
        path = tmp_path/(mutation+'.json')
        path.write_text(json.dumps(copy))
        with pytest.raises(ValueError):
            r.roadmap_readiness(path)


def test_laboratory_absence_is_not_success(tmp_path):
    report = r.laboratory_readout(tmp_path)
    assert report['available'] is False
    assert report['all_jobs_passed'] is False
    assert report['scientific_generalization_established'] is False


def test_laboratory_readout_keeps_negative_scores(tmp_path):
    (tmp_path/'workload').mkdir()
    (tmp_path/'summary.json').write_text(json.dumps({'all_jobs_passed': False,
        'selected_phase_profiles_passed': 10, 'jobs': [{'job':'science','status':'failed'}]}))
    scores = {'test-learned': {'correct':0, 'total':48}}
    (tmp_path/'workload/summary.json').write_text(json.dumps({'evaluations': scores}))
    report = r.laboratory_readout(tmp_path)
    assert report['available'] and not report['all_jobs_passed']
    assert report['learned_results'] == scores
    assert not report['scientific_generalization_established']


def test_finite_success_does_not_claim_full_calibration(tmp_path):
    pytest.importorskip('sympy')
    report = r.calibrate(matrix_path=MATRIX, laboratory_directory=tmp_path,
                         cases=8, integration_cases=8)
    assert report['finite_checks_passed']
    assert report['fully_calibrated_and_ready'] is False
    assert r.verify_report_structure(report)
    assert not report['laboratory']['all_jobs_passed']
    # Rehashing a global success flag cannot convert a finite result to certification.
    forged = deepcopy(report)
    forged['fully_calibrated_and_ready'] = True
    forged['report_id'] = fingerprint({k:v for k,v in forged.items() if k != 'report_id'})
    assert not r.verify_report_structure(forged)
    forged = deepcopy(report)
    forged['checks']['differential']['passed'] = False
    forged['report_id'] = fingerprint({k:v for k,v in forged.items() if k != 'report_id'})
    assert not r.verify_report_structure(forged)
    report['protocol']['seed'] += 1
    assert not r.verify_report_structure(report)


def test_report_structure_rejects_empty_or_coerced_success(tmp_path):
    pytest.importorskip('sympy')
    original = r.calibrate(matrix_path=MATRIX, laboratory_directory=tmp_path,
                           cases=2, integration_cases=2)
    for mutation in ('empty', 'coerced', 'count', 'status'):
        report = deepcopy(original)
        if mutation == 'empty':
            report['checks'] = {}
        elif mutation == 'coerced':
            report['checks']['integration']['passed'] = 1
        elif mutation == 'count':
            report['checks']['integration']['executed'] = 0
        else:
            report['checks']['integration']['status'] = 'failed'
        report['report_id'] = fingerprint({k:v for k,v in report.items() if k != 'report_id'})
        assert not r.verify_report_structure(report)
