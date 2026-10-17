"""Narrative provenance, evidence integrity, lexical variation and expert cases."""
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import random

import pytest

from nablamath.calc.session import CalculationSession
from nablamath.superintelligence.synthetic_challenges import ADVANCED_20, CHALLENGES
from nablamath.superintelligence.synthetic_cot_unroller import (
    ContradictionDetector, GenerationConfig, SimulatedReasoningTrace,
    TextualReasoningFormatter, export_dataset, verify_dataset,
)
from nablamath.superintelligence.synthetic_nlg import ProceduralNarrator, WeightedGrammar


@pytest.fixture
def arithmetic_record():
    return SimulatedReasoningTrace(GenerationConfig(error_rate=1,depth=1)).generate('rational_domain')


def test_seeded_narration_has_reproducible_choices_and_preserves_mathematics(arithmetic_record):
    original = deepcopy(arithmetic_record)
    a = ProceduralNarrator(0).events(arithmetic_record)
    assert a == ProceduralNarrator(0).events(arithmetic_record)
    assert a != ProceduralNarrator(42).events(arithmetic_record)
    assert arithmetic_record == original
    for event in a:
        step = arithmetic_record['steps'][event['step']-1]
        assert event['receipt_id'] == step['receipt']['content_id']
        assert event['productions']


def test_state_machine_never_invents_a_correction_without_a_rejected_candidate():
    record = SimulatedReasoningTrace(GenerationConfig(error_rate=0,depth=2)).generate('matrix_inverse')
    events = ProceduralNarrator().events(record)
    for step in record['steps']:
        assert [e['state'] for e in events if e['step'] == step['index']] == ['plan','execute','confirm']


def test_rejected_candidates_have_a_complete_ordered_correction_sequence(arithmetic_record):
    events = ProceduralNarrator().events(arithmetic_record)
    for step in arithmetic_record['steps']:
        assert [e['state'] for e in events if e['step'] == step['index']] == [
            'plan','attempt','check','diagnose','correct','confirm']


@pytest.mark.parametrize('damage', ['accepted','observed','missing_difference','duplicate_difference','future_dependency'])
def test_narration_rejects_forged_evidence(arithmetic_record, damage):
    record = deepcopy(arithmetic_record)
    step = record['steps'][0]
    detection = step['error']['detection']
    if damage == 'accepted':
        detection['accepted'] = True
    elif damage == 'observed':
        detection['differences'][0]['observed'] = 'not the candidate'
    elif damage == 'missing_difference':
        detection['differences'] = []
    elif damage == 'duplicate_difference':
        detection['differences'].append(deepcopy(detection['differences'][0]))
    else:
        step['depends_on'] = [step['index']+1]
    with pytest.raises(ValueError):
        ProceduralNarrator().events(record)


def test_weighted_grammar_rejects_unknown_symbols_and_limits_recursion():
    with pytest.raises(ValueError,match='terminal'):
        WeightedGrammar({'start':((1,'<unknown>'),)})
    grammar = WeightedGrammar({'loop':((1,'<loop>'),)})
    with pytest.raises(ValueError,match='Orçamento'):
        grammar.expand('loop', {}, random.Random(0))


@pytest.mark.parametrize('template', ['{missing}', '{action.__class__}', '{action[secret]}'])
def test_grammar_accepts_only_closed_evidence_slots(template):
    grammar = WeightedGrammar({'start':((1,template),)})
    with pytest.raises(ValueError,match='Slot'):
        grammar.expand('start', {'action':'x'}, random.Random(0))


def test_math_braces_and_markup_are_inserted_as_data():
    grammar = WeightedGrammar({'start':((1,'Valor: {formula}'),)})
    text,_ = grammar.expand('start', {'formula':'{x in R} <opening>'}, random.Random(0))
    assert text == 'Valor: {x in R} <opening>'


def test_reference_rejection_is_distinct_from_a_partially_checked_candidate():
    with CalculationSession() as session:
        linear = session.execute('solve_linear',matrix=[[2,1],[1,3]],rhs=[1,2]).to_data()
        candidate = deepcopy(linear['result']); candidate['particular'][0] = '99'
        detection = ContradictionDetector.check(linear,candidate)
        assert not detection['accepted']
        assert detection['reference_check']['status'] == 'rejects_candidate'
        properties = session.execute('matrix_properties',matrix=[[2,0],[0,3]]).to_data()
        candidate = deepcopy(properties['result']); candidate['rank'] = 1
        detection = ContradictionDetector.check(properties,candidate)
        assert not detection['accepted']
        assert detection['reference_check']['status'] == 'holds_for_checked_claims'
        assert 'não cobrem' in detection['reference_check']['scope']


def test_integer_mutation_is_not_described_as_a_dimensional_or_physical_error():
    record = SimulatedReasoningTrace(GenerationConfig(depth=1,error_rate=1)).generate('nt_pell')
    text = TextualReasoningFormatter.translated_solution(record)
    assert 'deslizamento de índice' not in text
    assert 'fisicamente devem ser' not in text
    assert 'numerador correto' not in text


def test_generic_recipe_translation_has_no_embedded_api_request_json():
    record = SimulatedReasoningTrace(GenerationConfig(depth=1,error_rate=1)).generate('matrix_inverse')
    text = TextualReasoningFormatter.translated_solution(record)
    assert '"operation"' not in text and '"arguments"' not in text
    assert 'Dados:' in text and 'Recibo:' in text


def test_twenty_expert_profiles_cover_twenty_distinct_named_subfields():
    assert len(ADVANCED_20) == 20
    assert len({CHALLENGES[name].area for name in ADVANCED_20}) == 20
    assert all(CHALLENGES[name].burden for name in ADVANCED_20)


def test_expert_pell_solution_has_large_integers_and_exact_identity():
    record = SimulatedReasoningTrace(GenerationConfig(error_rate=0)).generate('challenge.arithmetic')
    largest = record['answer'][-1]
    x,y,d = int(largest['x']),int(largest['y']),largest['D']
    assert d == 661 and len(str(x)) > 30
    assert x*x-d*y*y == 1


def test_integral_topology_detects_torsion_and_its_cohomological_shift():
    pytest.importorskip('sympy')
    record = SimulatedReasoningTrace(GenerationConfig(error_rate=0)).generate('challenge.topology')
    h,coh = record['answer']['homology'],record['answer']['cohomology']
    assert h[1]['torsion'] == [2] and not h[2]['torsion']
    assert not coh[1]['torsion'] and coh[2]['torsion'] == [2]
    assert [entry['free_rank'] for entry in h] == [1,2,2]


def test_fredholm_solution_satisfies_every_polynomial_coefficient_and_is_a_contraction():
    record = SimulatedReasoningTrace(GenerationConfig(error_rate=0)).generate('challenge.fredholm')
    answer = record['answer']
    assert len(answer['coefficients']) == 12
    assert all(Fraction(v) == 0 for v in answer['residual_coefficients'])
    assert Fraction(answer['operator_norm_upper_bound_sup']) < 1
    assert record['steps'][0]['certificate']['independent_of_producing_solver']


def test_wording_seed_changes_only_narrative_artifacts_and_all_exports_replay(tmp_path):
    a,b = tmp_path/'a',tmp_path/'b'
    kwargs = dict(count=1,config=GenerationConfig(depth=1,error_rate=1),families=['matrix_inverse'])
    export_dataset(a,**kwargs,wording_seed=1)
    export_dataset(b,**kwargs,wording_seed=2)
    assert (a/'dataset.jsonl').read_bytes() == (b/'dataset.jsonl').read_bytes()
    assert (a/'amostras_traduzidas.txt').read_bytes() != (b/'amostras_traduzidas.txt').read_bytes()
    assert verify_dataset(a) and verify_dataset(b)
    pairs = [json.loads(line) for line in (a/'dpo_natural.jsonl').read_text().splitlines()]
    assert pairs and all(p['chosen'] != p['rejected'] for p in pairs)
    sft = json.loads((a/'sft_natural.jsonl').read_text())
    assert 'Dados dos subproblemas' in sft['messages'][0]['content']
    assert '"operation"' not in sft['messages'][0]['content']


def test_rehashing_an_invented_narrative_does_not_pass_verification(tmp_path):
    root = tmp_path/'data'
    export_dataset(root,count=1,config=GenerationConfig(depth=1),families=['matrix_inverse'])
    path = root/'narration.jsonl'
    row = json.loads(path.read_text())
    row['events'][0]['text'] = 'This mathematical theorem has been universally proved.'
    path.write_text(json.dumps(row)+'\n')
    manifest_path = root/'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['files'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest)+'\n')
    assert not verify_dataset(root)


def test_invalid_wording_seed_fails_before_creating_output(tmp_path):
    with pytest.raises(ValueError,match='wording_seed'):
        export_dataset(tmp_path/'data',count=1,wording_seed=True)
    assert not list(tmp_path.iterdir())
