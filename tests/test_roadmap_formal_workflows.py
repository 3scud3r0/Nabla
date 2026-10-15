"""Controlled-language/review/portfolio integration with real SMT and forgery checks."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from nablamath.core.semantic_contracts import canonical_payload
from nablamath.core.semantic_ir import fingerprint
from nablamath.formal.autoformalization import (
    FormalizationDraft, FormalizationReview, parse_controlled_statement, parse_predicate,
)
from nablamath.formal.proof_repair import suggest_repairs, verify_repair
from nablamath.formal.proof_search_planner import (
    ProofBudget, ProofPlan, build_proof_plan, execute_proof_plan,
    replay_proof_run, validate_run_structure,
)
from nablamath.formal.lean_checker import LeanCheck
import nablamath.formal.proof_search_planner as planner


def reviewed(source='forall x in Q: prove x+1 > x', strategy='auto'):
    draft = FormalizationDraft(source, strategy)
    review = FormalizationReview(draft.content_id, 'test reviewer', True,
                                 'Controlled expression and declared domain checked')
    return draft, review


def smt_plan(draft):
    return build_proof_plan(draft, ProofBudget(backends=('smt',), max_attempts=1))


def rehash_run(run):
    for row in run['attempts']:
        if isinstance(row['receipt'], dict):
            row['receipt_content_id'] = fingerprint(row['receipt'])
    run['run_id'] = fingerprint({k: v for k, v in run.items() if k != 'run_id'})
    return run


def rehash_receipt(receipt):
    if 'receipt_id' in receipt:
        receipt['receipt_id'] = fingerprint({k: v for k, v in receipt.items() if k != 'receipt_id'})


@pytest.mark.parametrize('source', [
    'prove 1+1 == 2',
    'forall x,y in Q: prove x+y == y+x',
    'forall x in Q: prove x > 0 where x >= 1; x != 2',
    'forall x in Q: prove x/x == 1',
])
def test_controlled_draft_roundtrip(source):
    draft = FormalizationDraft(source)
    assert FormalizationDraft.from_json(draft.to_json()) == draft
    assert draft.to_data()['formal_proof'] is False
    assert draft.to_data()['natural_language_semantics_inferred'] is False
    assert draft.translation.statement == parse_controlled_statement(source)
    assert draft.to_data()['statement_id'] == draft.statement.content_id


@pytest.mark.parametrize('source', [
    'prove x == x', 'forall x,x in Q: prove x == x',
    'forall x,y in Q: prove x == x', 'forall x in R: prove x == x',
    'forall x in Q: prove x < 2 < 3', 'prove 1 == 1 # proof',
    'prove 1 == 1\nby sorry', 'prove 1 == 1 where ',
    'prove 1 == 1 where 2 == 2;', 'prove 1 == 1 where 2 == 2 where 3 == 3',
    'prove True', 'import Mathlib',
])
def test_controlled_grammar_rejects_ambiguity_and_source_injection(source):
    with pytest.raises((ValueError, SyntaxError)):
        FormalizationDraft(source)


def test_predicate_requires_single_relation():
    assert parse_predicate('1 <= 2').relation == 'le'
    for source in ('1', '1==', '==2', '1<2<3'):
        with pytest.raises(ValueError):
            parse_predicate(source)


def test_draft_commitment_rejects_ast_translation_and_version_forgery():
    draft, _ = reviewed()
    for path, replacement in [('source', 'forall x in Q: prove x+2 > x'),
                               ('strategy', 'ring'), ('formal_proof', True),
                               ('grammar', 'free-natural-language-v1')]:
        data = json.loads(draft.to_json())
        data[path] = replacement
        with pytest.raises(ValueError):
            FormalizationDraft.from_json(canonical_payload(data))
    data = json.loads(draft.to_json())
    data['translation']['source'] += '\naxiom fake : False'
    with pytest.raises(ValueError):
        FormalizationDraft.from_json(canonical_payload(data))


def test_review_binds_complete_draft_and_explicit_acceptance():
    draft, review = reviewed()
    review.require(draft)
    assert review.to_data()['reviewer_authenticated_by_library'] is False
    with pytest.raises(PermissionError):
        replace(review, accepted=False).require(draft)
    with pytest.raises(PermissionError):
        review.require(FormalizationDraft(draft.source, 'ring'))
    with pytest.raises(ValueError):
        replace(review, accepted=1)
    with pytest.raises(ValueError):
        replace(review, correspondence_notes='')


def test_repair_changes_only_tactic_and_invalidates_old_review():
    draft, review = reviewed('forall x in Q: prove x*x == x**2')
    repairs = suggest_repairs(draft, failure_kind='timeout', attempted=('auto', 'field'))
    assert repairs
    assert all(r.next_strategy not in ('auto', 'field') for r in repairs)
    for proposal in repairs:
        repaired = proposal.apply(draft)
        assert repaired.statement.to_data() == draft.statement.to_data()
        assert repaired.source == draft.source
        assert verify_repair(proposal.to_data(), draft)
        with pytest.raises(PermissionError):
            review.require(repaired)
    forged = repairs[0].to_data()
    forged['hypotheses_removed'] = True
    assert not verify_repair(forged, draft)
    stale = FormalizationDraft('forall x in Q: prove x*x == x*x')
    assert not verify_repair(repairs[0].to_data(), stale)


@pytest.mark.parametrize('status', ['counterexample', 'inconsistent_assumptions', 'proved', 'unsat', 'unavailable'])
def test_repair_never_masks_terminal_or_unavailable_outcomes(status):
    draft, _ = reviewed()
    assert suggest_repairs(draft, failure_kind=status) == ()


def test_budget_plan_deadlines_and_replay():
    draft, _ = reviewed()
    budget = ProofBudget(max_attempts=4, total_seconds=7, attempt_timeout_seconds=3)
    plan = build_proof_plan(draft, budget)
    rows = plan.to_data()['attempts']
    assert [row['timeout_seconds'] for row in rows] == [3, 3, 1]
    assert rows[0]['backend'] == 'smt'
    assert ProofPlan.from_json(plan.to_json()) == plan
    forged = json.loads(plan.to_json())
    forged['attempts'][0]['timeout_seconds'] = 4
    with pytest.raises(ValueError):
        ProofPlan.from_json(canonical_payload(forged))


@pytest.mark.parametrize('options', [
    {'max_attempts': True}, {'max_attempts': 9}, {'total_seconds': 0},
    {'attempt_timeout_seconds': 61}, {'backends': ('smt', 'smt')},
    {'backends': ('shell',)}, {'strategies': ('sorry',)}, {'strategies': ('ring', 'ring')},
])
def test_invalid_search_budgets(options):
    with pytest.raises(ValueError):
        ProofBudget(**options)


@pytest.mark.parametrize('source,status', [
    ('forall x in Q: prove x+1 > x', 'unsat'),
    ('forall x in Q: prove x > 0', 'counterexample'),
    ('forall x in Q: prove x > 0 where x < 0; x > 1', 'inconsistent_assumptions'),
    ('forall x in Q: prove x*x >= 0', 'unsupported'),
    ('forall x in Q: prove x/x == 1', 'unsupported'),
])
def test_real_smt_receipts_structure_and_semantic_reexecution(source, status):
    pytest.importorskip('z3')
    draft, review = reviewed(source)
    plan = smt_plan(draft)
    run = execute_proof_plan(draft, review, plan)
    assert run['attempts'][0]['status'] == status
    assert run['kernel_proved'] is False
    assert validate_run_structure(run, draft, review, plan)
    assert replay_proof_run(run, draft, review, plan)
    if status == 'counterexample':
        assert run['attempts'][0]['receipt']['exact_replay'] is True


def test_rehashed_counterexample_forgery_rejected_by_exact_arithmetic():
    pytest.importorskip('z3')
    draft, review = reviewed('forall x in Q: prove x > 0')
    plan = smt_plan(draft)
    run = execute_proof_plan(draft, review, plan)
    forged = deepcopy(run)
    forged['attempts'][0]['receipt']['witness']['x'] = '2'
    rehash_receipt(forged['attempts'][0]['receipt'])
    rehash_run(forged)
    assert not replay_proof_run(forged, draft, review, plan)
    with pytest.raises(ValueError, match='Counterexample'):
        validate_run_structure(forged, draft, review, plan)


def test_rehashed_false_unsat_requires_actual_solver_reexecution():
    pytest.importorskip('z3')
    draft, review = reviewed('forall x in Q: prove x > 0')
    plan = smt_plan(draft)
    run = execute_proof_plan(draft, review, plan)
    forged = deepcopy(run)
    row = forged['attempts'][0]
    row['status'] = row['receipt']['status'] = forged['stopped'] = 'unsat'
    row['receipt'].pop('witness')
    row['receipt'].pop('exact_replay')
    rehash_receipt(row['receipt'])
    rehash_run(forged)
    # Structural checks alone intentionally do not certify solver UNSAT.
    assert validate_run_structure(forged, draft, review, plan)
    assert not replay_proof_run(forged, draft, review, plan)


def fake_lean(translation, *, status='failed', axioms=()):
    return LeanCheck(status, translation.statement.content_id, translation.source_hash,
                     'test-double', tuple(axioms), 'controlled test backend', {}, strategy=translation.strategy)


def test_checkpoint_and_portfolio_exhaustion_with_checked_receipt_shapes(monkeypatch):
    draft, review = reviewed()
    budget = ProofBudget(backends=('lean',), strategies=('ring', 'norm_num'), max_attempts=2)
    plan = build_proof_plan(draft, budget)
    monkeypatch.setattr(planner, 'check_lean', lambda translation, **kwargs: fake_lean(translation))
    run = execute_proof_plan(draft, review, plan, stop_after=1)
    assert run['stopped'] == 'checkpoint'
    assert validate_run_structure(run, draft, review, plan)
    assert replay_proof_run(run, draft, review, plan)
    complete = execute_proof_plan(draft, review, plan)
    assert complete['stopped'] == 'portfolio_exhausted'
    assert len(complete['attempts']) == 2
    assert replay_proof_run(complete, draft, review, plan)


def test_lean_success_axiom_receipt_and_no_subsequent_attempts(monkeypatch):
    draft, review = reviewed()
    plan = build_proof_plan(draft, ProofBudget(backends=('lean',)))
    monkeypatch.setattr(planner, 'check_lean', lambda translation, **kwargs:
                        fake_lean(translation, status='proved', axioms=('propext',)))
    run = execute_proof_plan(draft, review, plan)
    assert run['kernel_proved'] is True
    assert run['stopped'] == 'proved'
    assert len(run['attempts']) == 1
    assert replay_proof_run(run, draft, review, plan)
    # A test double exercises receipt plumbing; no real Lean proof is claimed.
    forged = deepcopy(run)
    forged['attempts'][0]['receipt']['axioms'] = ['invented_axiom']
    rehash_receipt(forged['attempts'][0]['receipt'])
    rehash_run(forged)
    assert not replay_proof_run(forged, draft, review, plan)


def test_backend_status_and_receipt_substitution_rejected(monkeypatch):
    draft, review = reviewed()
    plan = smt_plan(draft)
    receipt = {'status': 'proved', 'backend': 'z3', 'formal_proof': False,
               'statement_id': draft.statement.content_id}
    monkeypatch.setattr(planner, 'solve_statement', lambda *a, **kw: receipt)
    with pytest.raises(ValueError, match='SMT backend'):
        execute_proof_plan(draft, review, plan)


def test_forged_empty_terminal_and_missing_attempts_rejected(monkeypatch):
    draft, review = reviewed()
    plan = build_proof_plan(draft, ProofBudget(backends=('lean',)))
    monkeypatch.setattr(planner, 'check_lean', lambda translation, **kwargs: fake_lean(translation))
    run = execute_proof_plan(draft, review, plan)
    for stopped in ('proved', 'portfolio_exhausted', 'checkpoint'):
        forged = deepcopy(run)
        forged['attempts'] = []
        forged['stopped'] = stopped
        rehash_run(forged)
        assert not replay_proof_run(forged, draft, review, plan)


def test_plan_and_review_must_match_exact_draft():
    draft, review = reviewed()
    plan = smt_plan(draft)
    with pytest.raises(PermissionError):
        execute_proof_plan(draft, replace(review, accepted=False), plan)
    other, other_review = reviewed('forall x in Q: prove x+2 > x')
    with pytest.raises(ValueError, match='regenerated'):
        execute_proof_plan(other, other_review, plan)
    with pytest.raises(ValueError):
        execute_proof_plan(draft, review, plan, stop_after=0)
