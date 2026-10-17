"""The demonstration must fail on wrong answers and cover the public catalog."""
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('scientist_demonstration',ROOT/'examples/science/reproduce.py')
science=importlib.util.module_from_spec(spec)
spec.loader.exec_module(science)


def test_scientist_full_experiment_and_reserved_points(tmp_path):
    destination=tmp_path/'experiment'
    report=science.run(destination)
    assert report['passed']
    assert report['catalog_operations']==104
    assert report['notebook_replayed_cells']==104
    assert report['finite_campaign']['independently_checked_cases']==176
    assert report['forge']['solver_verifier_runs']==16
    assert report['negative_controls']['count']==9
    assert report['physical_models']['idealized_models']==16
    assert report['physical_models']['diffusion_refinement_ratio']>3.8
    assert report['formal']['status']=='not_requested'
    assert report['hypothesis']['wrong_law_rejected']
    assert report['interfaces']['http_receipts']==104
    assert report['interfaces']['cli_receipts']==104
    assert all(row['valid'] for row in report['artifacts'])
    assert len(list(destination.glob('*.svg')))==2
    assert len(list(destination.glob('*.html')))==2
    assert json.loads((destination/'report.json').read_text())==report
    with pytest.raises(FileExistsError):
        science.run(destination)


def test_reference_is_independent_of_a_forged_receipt():
    with pytest.raises(AssertionError,match='reference mismatch'):
        science.reference_check('analysis_integral',{'integral':'2/3'})
    with pytest.raises(AssertionError,match='Bisection bracket'):
        science.reference_check('analysis_root',{'interval':{'lower':'2','upper':'3'}})
    with pytest.raises(AssertionError,match='Analytic exponential'):
        science.reference_check('ode_adaptive',{'final':[1.]})


def test_removed_operation_cannot_silently_reduce_coverage(tmp_path):
    cases=json.loads((ROOT/'examples/science/catalog_cases.json').read_text())
    cases.pop('nt_pell')
    path=tmp_path/'incomplete.json'
    path.write_text(json.dumps(cases))
    with pytest.raises(AssertionError,match='coverage mismatch'):
        science.run(tmp_path/'experiment',cases_path=path)
    assert not (tmp_path/'experiment').exists()


def test_explicit_formal_request_cannot_succeed_without_toolchain(tmp_path):
    with pytest.raises(AssertionError,match='Pinned Lean failed'):
        science.formal_experiment(tmp_path,tmp_path/'missing-project')
    assert not (tmp_path/'formal.json').exists()
