"""Protect the dashboard against false greens, omitted gaps and stale evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('vision_dashboard', ROOT/'tools/vision_readiness.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def row():
    return {'id': 1, 'target': 'core', 'requirement': '**P0**: actual acceptance',
        'status': 'partial', 'remaining': 'Independent physical experiment required',
        'implementation': ['src/core.py'], 'tests': ['tests/test_sample.py'],
        'evidence': ['docs/local.json'], 'reviewer': None, 'release': None}


def junit(tmp_path, xml):
    path = tmp_path/'results.xml'
    path.write_text(xml)
    return r.read_junit(path)


def test_junit_retains_every_outcome_and_skip_reason(tmp_path):
    result = junit(tmp_path, '''<testsuites><testsuite tests="4"><testcase classname="tests.test_sample" name="ok"/>
    <testcase classname="tests.test_sample" name="bad"><failure message="wrong answer"/></testcase>
    <testcase classname="tests.test_sample" name="missing"><skipped message="GPU unavailable"/></testcase>
    <testcase classname="tests.test_sample" name="broken"><error message="collection"/></testcase>
    </testsuite></testsuites>''')
    assert result['counts'] == {'passed': 1, 'failed': 1, 'skipped': 1, 'error': 1}
    assert result['cases'][2]['reason'] == 'GPU unavailable'
    assert result['sha256'] == r.digest(tmp_path/'results.xml')


@pytest.mark.parametrize('xml', ['<broken>', '<testsuites/>', '<testsuite errors="1"/>'])
def test_empty_corrupt_and_collection_only_results_cannot_be_green(tmp_path, xml):
    assert r.read_junit(tmp_path/'absent.xml')['available'] is False
    assert junit(tmp_path, xml)['errors']


@pytest.mark.parametrize('reference,expected', [
    ('tests/test_sample.py', 2), ('tests/test_sample.py::test_value', 1),
    ('tests/test_sample.py::Suite::test_value', 1), ('tests/test_sam.py', 0),
    ('tests/test_sample_extra.py', 0), ('lean/Kernel.lean', 0),
])
def test_module_matching_does_not_confuse_prefixes_or_lose_classes(reference, expected):
    cases = [{'classname': 'tests.test_sample.Suite', 'name': 'test_value[x]'},
             {'classname': 'tests.test_sample', 'name': 'other'}]
    assert len(r.matched_cases(reference, cases)) == expected


def test_passing_tests_never_hide_original_acceptance_gap():
    observation = {'cases': [{'classname': 'tests.test_sample', 'name': 'ok', 'status': 'passed'}]}
    result = r.requirement_report({'requirements': [row()]}, observation)[0]
    assert result['remaining'] == row()['remaining']
    assert result['declared_status'] == 'partial'
    assert result['independent_evidence_authenticated'] is False
    assert result['tests'][0]['counts'] == {'passed': 1}
    assert any('not closed' in gap for gap in result['gaps'])
    assert any('reviewer' in gap for gap in result['gaps'])


@pytest.mark.parametrize('status', ['failed', 'error', 'skipped'])
def test_failed_or_skipped_linked_tests_always_remain_gaps(status):
    observed = {'cases': [{'classname': 'tests.test_sample', 'name': 'ok', 'status': status}]}
    result = r.requirement_report({'requirements': [row()]}, observed)[0]
    assert any('failed' in g or 'skipped' in g for g in result['gaps'])


def test_missing_test_reference_is_not_a_pass():
    result = r.requirement_report({'requirements': [row()]}, {'cases': []})[0]
    assert result['tests'][0]['observed_this_run'] is False
    assert any('not observed' in gap for gap in result['gaps'])


def test_declared_validation_is_not_independent_identity_authentication():
    data = row()
    data.update(status='validated', reviewer='claimed reviewer', release='claimed release')
    result = r.requirement_report({'requirements': [data]}, {'cases': []})[0]
    assert result['independent_evidence_authenticated'] is False


def test_all_213_original_requirements_are_in_report_without_rewriting():
    matrix = json.loads((ROOT/r.MATRIX).read_text())
    snapshot = copy.deepcopy(matrix)
    rows = r.requirement_report(matrix, {'cases': []})
    assert [x['id'] for x in rows] == list(range(1, 214))
    for original, actual in zip(matrix['requirements'], rows):
        assert actual['acceptance'] == original['requirement']
        assert actual['remaining'] == original['remaining']
        assert actual['evidence'] == original['evidence']
    assert matrix == snapshot


def test_subprocess_failure_is_retained_with_exact_log(tmp_path):
    step = r.run_step('negative', [sys.executable, '-c', 'print("observed failure");raise SystemExit(7)'], tmp_path)
    assert step['exit_code'] == 7 and step['status'] == 'failed'
    assert 'observed failure' in (tmp_path/'negative.log').read_text()
    assert step['log_sha256'] == r.digest(tmp_path/'negative.log')


def test_timeout_is_distinct_from_failure_and_keeps_output(tmp_path):
    step = r.run_step('timeout', [sys.executable, '-c', 'import time;print("started",flush=True);time.sleep(20)'], tmp_path, timeout=.2)
    assert step['status'] == 'timeout' and step['exit_code'] is None
    assert 'started' in (tmp_path/'timeout.log').read_text()


def test_unavailable_program_is_distinct(tmp_path):
    step = r.run_step('missing', [str(tmp_path/'not-an-executable')], tmp_path)
    assert step['status'] == 'unavailable'


def test_giant_markdown_contains_every_original_gap():
    matrix = json.loads((ROOT/r.MATRIX).read_text())
    report = {'created_utc': 'fixed', 'tests': {'counts': {}}, 'matrix_statuses': {'partial': 213},
              'steps': [], 'requirements': r.requirement_report(matrix, {'cases': []})}
    text = r.markdown(report)
    assert text.count('\n### ') == 213
    for row_ in matrix['requirements']:
        assert row_['remaining'] in text
    assert 'não estabelecida' in text


def test_benchmark_results_preserve_zero_scores_and_missing_campaigns(tmp_path):
    directory = tmp_path/'laboratory/workload'
    directory.mkdir(parents=True)
    data = {'evaluations': {'heldout-model': {'successes': 0, 'total': 48}}}
    (directory/'summary.json').write_text(json.dumps(data))
    result = r.benchmark_results(tmp_path)
    assert result['original_workload']['result'] == data
    assert result['calibration']['available'] is False
    assert result['longley']['available'] is False


def test_malformed_benchmark_is_not_reported_as_available(tmp_path):
    (tmp_path/'longley.json').write_text('{broken')
    result = r.benchmark_results(tmp_path)
    assert not result['longley']['available'] and result['longley']['error']


def test_markdown_displays_failed_generalization_instead_of_hiding_it():
    report = {'created_utc': 'fixed', 'tests': {'counts': {}}, 'matrix_statuses': {},
              'steps': [], 'requirements': [], 'benchmarks': {
                  'original_workload': {'available': True, 'result': {
                      'evaluations': {'heldout-model': {'successes': 0, 'total': 48}}}}}}
    text = r.markdown(report)
    assert '"successes": 0' in text and '"total": 48' in text
