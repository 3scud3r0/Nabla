import copy
import pytest
from nablamath.forge.reverse_builder import generate_task
from nablamath.forge.compositional_generator import compose_linear_systems
from nablamath.forge.adversarial_generator import stale_solution_challenge
from nablamath.forge.difficulty_calibration import resource_frontier
from nablamath.forge.difficulty import calibrate
from nablamath.forge.novelty_index import NoveltyIndex
from nablamath.forge.task_spec import TaskSpec, GeneratedProblem
from nablamath.verify.trace import verify_candidate
from nablamath.core.semantic_ir import canonical_json
from nablamath.falsifier.property_engine import check_properties, replay_properties
from nablamath.discovery.lab_protocol import preregister, evaluate_registration
from nablamath.discovery.hypothesis import Hypothesis, Observation, ObservationSet


def test_composition_exact_and_deterministic():
    parts = [generate_task('linear_system', seed, 2) for seed in (1, 2)]
    result = compose_linear_systems(parts)
    assert result == compose_linear_systems(parts)
    assert verify_candidate(TaskSpec.from_data(result['task']), result['witness']).valid
    assert TaskSpec.from_data(result['task']).size == 4
    assert len(result['component_ids']) == 2


def test_composition_rejects_forged_witness_and_oversize():
    item = generate_task('linear_system', 3, 2)
    bad = GeneratedProblem(item.task, canonical_json({'solution': ['100', '100']}), 3)
    with pytest.raises(ValueError):
        compose_linear_systems([item, bad])
    with pytest.raises(ValueError):
        compose_linear_systems([generate_task('linear_system', 1, 5)] * 2)
    with pytest.raises(ValueError):
        compose_linear_systems([generate_task('polynomial_integral', 1, 2)] * 2)


@pytest.mark.parametrize('row,delta', [(0, '1'), (1, '-3/2'), (2, '7')])
def test_adversarial_stale_answer_is_refuted(row, delta):
    task = generate_task('linear_system', 9, 3).task
    report = stale_solution_challenge(task, row=row, delta=delta)
    assert report == stale_solution_challenge(task, row=row, delta=delta)
    assert not report['stale_verification']['valid']
    assert report['verification']['valid']
    assert not report['hardness_established']
    assert report['source_id'] != TaskSpec.from_data(report['task']).content_id


def test_adversarial_requires_actual_change():
    task = generate_task('linear_system', 1, 2).task
    for kwargs in ({'delta': '0'}, {'row': True}, {'row': 2}):
        with pytest.raises(ValueError):
            stale_solution_challenge(task, **kwargs)


def test_calibration_frontier_rejects_tampering_and_retains_censoring():
    tasks = [generate_task('linear_system', 3, 2).task]
    measured = calibrate(tasks, budget=1)
    result = resource_frontier(measured, tasks)
    assert result['rows'][0]['censored']
    assert result['rows'][0]['minimum_verified_lines'] is None
    measured['observations'][0]['budget'] = 1000
    with pytest.raises(ValueError):
        resource_frontier(measured, tasks)


def test_local_novelty_equivalent_row_scaling_and_roundtrip():
    task = generate_task('linear_system', 4, 2).task
    p = task.problem
    from fractions import Fraction
    p['matrix'][0] = [str(2*Fraction(v)) for v in p['matrix'][0]]
    p['rhs'][0] = str(2*Fraction(p['rhs'][0]))
    equivalent = TaskSpec('linear_system', p, 2)
    index = NoveltyIndex([task])
    result = index.compare(equivalent)
    assert result['local_matches'] == [task.content_id]
    assert not result['global_novelty_established']
    assert NoveltyIndex.from_data(index.to_data()).compare(equivalent) == result
    data = index.to_data(); data['corpus_id'] = 'tampered'
    with pytest.raises(ValueError):
        NoveltyIndex.from_data(data)
    assert NoveltyIndex().compare(task)['status'] == 'novelty_not_established'


def test_properties_retain_domain_refutations_nulls_and_budget():
    report = check_properties([
        {'name': 'commutative', 'left': 'x+1', 'right': '1+x'},
        {'name': 'domain', 'left': 'x/x', 'right': '1'},
        {'name': 'false', 'left': 'x+1', 'right': 'x'},
        {'name': 'budget', 'left': 'x+y', 'right': 'y+x'},
    ], radius=3, budget=2)
    assert report['refuted'] == ['domain', 'false']
    assert report['attempts'][-1]['result']['status'] == 'budget_exhausted'
    assert replay_properties(report)
    report['attempts'][0]['result']['formal_proof'] = True
    assert not replay_properties(report)


def test_property_names_unique():
    p = {'name': 'x', 'left': 'x', 'right': 'x'}
    with pytest.raises(ValueError):
        check_properties([p, p])


def test_frozen_protocol_records_null_and_refuted_results():
    hs = [Hypothesis('x', 'linear identity'), Hypothesis('x*x', 'quadratic')]
    calibration = ObservationSet((Observation(0, 0),), 'fixture', 'calibration')
    holdout = ObservationSet((Observation(2, 2), Observation(3, 3)), 'fixture', 'holdout')
    registration = preregister(hs, calibration, protocol='freeze both models before holdout')
    report = evaluate_registration(registration, hs, calibration, holdout)
    assert [r['accepted_on_supplied_holdout'] for r in report['results']] == [True, False]
    assert report == evaluate_registration(registration, hs, calibration, holdout)
    assert report['synthetic'] and not report['external_authentication']
    changed = copy.deepcopy(registration); changed['max_failures'] = 2
    with pytest.raises(ValueError):
        evaluate_registration(changed, hs, calibration, holdout)
    with pytest.raises(ValueError):
        evaluate_registration(registration, list(reversed(hs)), calibration, holdout)
    leaked = ObservationSet((Observation(0, 0),), 'fixture', 'holdout')
    with pytest.raises(ValueError):
        evaluate_registration(registration, hs, calibration, leaked)


def test_composition_and_adversarial_receipts_reexecute_not_just_hash():
    from nablamath.forge.compositional_generator import replay_composition
    from nablamath.forge.adversarial_generator import replay_challenge
    parts = [generate_task('linear_system', s, 2) for s in (7, 8)]
    composition = compose_linear_systems(parts)
    assert replay_composition(composition, parts)
    composition['witness']['solution'][0] = '999'
    assert not replay_composition(composition, parts)
    challenge = stale_solution_challenge(parts[0].task)
    assert replay_challenge(challenge, parts[0].task)
    challenge['verification']['valid'] = False
    assert not replay_challenge(challenge, parts[0].task)


def test_successful_calibration_frontier_contains_actual_verified_cost():
    tasks = [generate_task('polynomial_integral', 3, 2).task]
    report = calibrate(tasks, budget=100000)
    frontier = resource_frontier(report, tasks)
    assert frontier['rows'][0]['minimum_verified_lines'] > 0
    assert frontier['rows'][0]['completed_strategies'] == ['alternate', 'exact']
    assert frontier['rows'][0]['censored'] is False
