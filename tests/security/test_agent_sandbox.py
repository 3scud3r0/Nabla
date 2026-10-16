"""Negative boundary tests: no source execution, ambient capability, or silent retry."""
from dataclasses import replace
import copy
from itertools import repeat
import json

import pytest

from nablamath.agents.experiment_planner import plan_experiment
from nablamath.agents.human_approval import ApprovalLedger
from nablamath.agents.permissions import Permissions
from nablamath.agents.secure_execution import (
    SecureSession, SessionCancelled, deny_untrusted_code, verify_session_snapshot,
)
from nablamath.agents.tool_registry import scientific_registry
from nablamath.core.semantic_ir import ScientificTask, fingerprint
from nablamath.evaluation.frozen import FrozenEvaluation
from nablamath.evolution.code_proposals import (
    CodeProposal, TrialBudget, validate_lineage,
)
from nablamath.evolution.secure_trials import (
    SecureTrialRunner, review_plan, verify_trial_history,
)
from nablamath.verification.independence import IndependencePolicy
from services.worker.isolation import (
    IsolationPolicy, capabilities, require_isolation, run_untrusted,
)


@pytest.fixture
def protocol():
    tasks = [ScientificTask('linear_system', matrix=((2, 1), (1, 2)), rhs=(3, 3)),
             ScientificTask('polynomial_integral', coefficients=(2, 3))]
    lineage = [dict(id=t.content_id, split='test', parents=[], groups={}) for t in tasks]
    lineage.append(dict(id='separate-training', split='train', parents=[], groups={}))
    baseline = [dict(task_id=t.content_id, values=['0', '0'] if t.family == 'linear_system'
                     else ['0', '0', '0']) for t in tasks]
    return FrozenEvaluation.freeze(tasks=tasks, lineage=lineage, baseline=baseline,
        policy='Fixed descriptive exact correctness; no release authorization',
        actors=IndependencePolicy('author', 'solver', 'evaluator', 'reviewer'))


def candidate_for(protocol, **kwargs):
    return CodeProposal.create(protocol, algorithm='exact-rational-v1', owner='author',
                               rationale='Compare fixed exact implementations', **kwargs)


def authorize(candidate, ledger):
    plan = review_plan(candidate)
    ledger.record(plan, 'trial', reviewer='human', decision='approve',
                  reason='Reviewed frozen contract and budget', expected_head=ledger.head)
    return plan


@pytest.mark.parametrize('source', [
    '', '1+1', 'import os; os.system("echo escape")',
    '__import__("pathlib").Path("/tmp/escape").write_text("x")',
    'open("/etc/passwd").read()', 'while True: pass',
    'lambda: 1', b'bytecode', {'source': 'pass'},
])
def test_no_arbitrary_source_executes(source, tmp_path):
    for entrypoint in (run_untrusted, deny_untrusted_code):
        with pytest.raises(PermissionError):
            entrypoint(source)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('field', ['allow_network', 'allow_filesystem_write', 'allow_arbitrary_code'])
def test_isolation_configuration_cannot_enable_unavailable_capability(field):
    with pytest.raises(ValueError):
        IsolationPolicy(**{field: True})
    with pytest.raises(ValueError):
        IsolationPolicy(**{field: 0})


def test_isolation_policy_is_not_an_os_sandbox():
    policy = IsolationPolicy()
    info = capabilities(policy)
    assert not info['os_sandbox']
    assert not info['arbitrary_code']
    assert IsolationPolicy.from_data(policy.to_data()) == policy
    assert policy.permissions({'solve', 'verify'}).max_calls == policy.max_calls
    for tools in ({'shell'}, {'solve', 'network'}, set()):
        with pytest.raises(PermissionError):
            policy.permissions(tools)
    with pytest.raises(ValueError):
        IsolationPolicy.from_data({**policy.to_data(), 'backend': 'pretend-container'})
    for kwargs in ({'arbitrary_code': True}, {'network': True}, {'filesystem_write': True}):
        with pytest.raises(PermissionError):
            require_isolation(**kwargs)
    assert require_isolation()


@pytest.mark.parametrize('changes', [
    dict(max_tasks=True), dict(max_tasks=101), dict(max_attempts=0),
    dict(max_attempts=9), dict(max_input_bytes=0), dict(max_output_bytes=1048577),
    dict(timeout_seconds=True), dict(timeout_seconds=float('nan')),
    dict(timeout_seconds=float('inf')), dict(timeout_seconds='10'),
])
def test_invalid_trial_budgets(changes):
    with pytest.raises(ValueError):
        TrialBudget(**changes)


def test_candidate_identity_lineage_and_exact_serialization(protocol):
    root = candidate_for(protocol)
    child = root.descendant(algorithm='alternate-rational-v1', rationale='Independent exact strategy')
    assert root.proposal_id != child.proposal_id
    assert child.parent_id == root.proposal_id
    assert child.generation == 1
    assert validate_lineage([root, child])['head'] == child.proposal_id
    assert CodeProposal.from_data(child.to_data(), expected_id=child.proposal_id) == child
    data = child.to_data()
    data['budget']['max_tasks'] += 1
    with pytest.raises(ValueError, match='commitment'):
        CodeProposal.from_data(data, expected_id=child.proposal_id)
    with pytest.raises(ValueError):
        CodeProposal.from_data({**child.to_data(), 'source': 'pass'}, expected_id=child.proposal_id)
    with pytest.raises(ValueError):
        validate_lineage([child])
    with pytest.raises(ValueError):
        validate_lineage([root, replace(child, owner='other')])
    with pytest.raises(ValueError):
        validate_lineage(repeat(root))


@pytest.mark.parametrize('algorithm', ['shell', 'module:callback', '/bin/sh', 'python', 'exact-rational-v2'])
def test_no_dynamic_algorithm_resolution(protocol, algorithm):
    with pytest.raises(ValueError):
        CodeProposal.create(protocol, algorithm=algorithm, owner='author', rationale='Untrusted')


def test_candidate_cohort_and_implementation_commitments(protocol):
    candidate = candidate_for(protocol)
    with pytest.raises(ValueError, match='implementation changed'):
        replace(candidate, implementation_id='0'*64).preflight(protocol)
    with pytest.raises(ValueError, match='different frozen'):
        replace(candidate, protocol_id='0'*64).preflight(protocol)
    with pytest.raises(ValueError, match='task budget'):
        candidate_for(protocol, budget=TrialBudget(max_tasks=1))
    with pytest.raises(ValueError, match='input budget'):
        candidate_for(protocol, budget=TrialBudget(max_input_bytes=10))


@pytest.mark.parametrize('algorithm', ['exact-rational-v1', 'alternate-rational-v1'])
def test_trusted_trials_replay_frozen_evaluation(protocol, algorithm):
    candidate = CodeProposal.create(protocol, algorithm=algorithm, owner='author', rationale='Reviewed')
    ledger = ApprovalLedger()
    authorize(candidate, ledger)
    runner = SecureTrialRunner(candidate, protocol, ledger)
    result = runner.run()
    assert result['status'] == 'completed', result
    assert result['evaluation']['candidate_correct'] == 2
    assert result['evaluation']['decision'] == 'descriptive_only'
    assert runner.verify_history()
    detached = runner.history()
    detached[0]['predictions'][0]['values'][0] = '999'
    assert runner.verify_history()
    assert not verify_trial_history(detached, candidate, protocol)
    with pytest.raises(ValueError):
        runner.run(expected_head=runner.head, retry_reason='Cherry-pick')


def test_trial_requires_approval_and_budget_change_invalidates_it(protocol):
    candidate = candidate_for(protocol)
    ledger = ApprovalLedger()
    runner = SecureTrialRunner(candidate, protocol, ledger)
    with pytest.raises(PermissionError):
        runner.run()
    assert runner.history() == []
    authorize(candidate, ledger)
    changed = replace(candidate, budget=TrialBudget(max_tasks=3))
    with pytest.raises(PermissionError):
        SecureTrialRunner(changed, protocol, ledger).run()


def test_cancellation_retry_requires_explicit_reason_and_cas(protocol):
    candidate = candidate_for(protocol, budget=TrialBudget(max_attempts=2))
    ledger = ApprovalLedger()
    authorize(candidate, ledger)
    runner = SecureTrialRunner(candidate, protocol, ledger)
    cancelled = runner.run(cancelled=lambda: True)
    assert cancelled['status'] == 'cancelled'
    assert cancelled['predictions'] == []
    assert runner.verify_history()
    with pytest.raises(ValueError, match='Stale'):
        runner.run(retry_reason='Retry')
    with pytest.raises(ValueError, match='reason'):
        runner.run(expected_head=runner.head)
    result = runner.run(expected_head=runner.head, retry_reason='User cleared cancellation')
    assert result['status'] == 'completed'
    assert runner.verify_history()
    assert result['previous'] == cancelled['attempt_id']


def test_revocation_blocks_next_trial_and_does_not_consume_attempt(protocol):
    candidate = candidate_for(protocol)
    ledger = ApprovalLedger()
    plan = authorize(candidate, ledger)
    ledger.record(plan, 'trial', reviewer='human', decision='revoke', reason='Recheck cohort', expected_head=ledger.head)
    runner = SecureTrialRunner(candidate, protocol, ledger)
    with pytest.raises(PermissionError):
        runner.run()
    assert runner.history() == []


def test_trial_history_hash_and_algorithm_provenance(protocol):
    candidate = candidate_for(protocol)
    ledger = ApprovalLedger()
    authorize(candidate, ledger)
    runner = SecureTrialRunner(candidate, protocol, ledger)
    result = runner.run()
    tampered = copy.deepcopy(result)
    tampered['evaluation']['candidate_correct'] = 0
    body = {k: v for k, v in tampered.items() if k != 'attempt_id'}
    tampered['attempt_id'] = fingerprint(body)
    assert not verify_trial_history([tampered], candidate, protocol)
    tampered = copy.deepcopy(result)
    tampered['previous'] = '0'*64
    assert not verify_trial_history([tampered], candidate, protocol)
    assert not verify_trial_history([result, result], candidate, protocol)


@pytest.fixture
def session_setup():
    permissions = Permissions(frozenset({'simulate'}), max_calls=2, timeout_seconds=30)
    plan = plan_experiment(question='Bounded decay', owner='author', hypothesis='State decays',
        expected_observation='Two finite trajectories', trials=[dict(id=name, tool='simulate',
        arguments=dict(name='exponential_decay', initial=[1], steps=2)) for name in ('first', 'second')],
        registry=scientific_registry(), permissions=permissions)
    ledger = ApprovalLedger()
    for action in plan.proposal.actions:
        ledger.record(plan, action.action_id, reviewer='human', decision='approve', reason='Reviewed', expected_head=ledger.head)
    return plan, ledger, permissions


def test_session_checkpoints_and_snapshot_tampering(session_setup):
    plan, ledger, permissions = session_setup
    session = SecureSession(plan, ledger, permissions)
    initial = session.snapshot()
    assert verify_session_snapshot(initial)
    first = session.advance()
    assert session.status == 'paused' and len(first['receipts']) == 1
    assert verify_session_snapshot(session.snapshot())
    first['receipts'].clear()
    assert len(session.snapshot()['report']['receipts']) == 1
    second = session.advance()
    assert second['completed'] and session.status == 'completed'
    snapshot = session.snapshot()
    assert verify_session_snapshot(snapshot)
    snapshot['report']['completed'] = False
    assert not verify_session_snapshot(snapshot)
    with pytest.raises(ValueError):
        session.advance()
    with pytest.raises(ValueError):
        session.cancel('Too late')


def test_session_revocation_is_checked_between_actions(session_setup):
    plan, ledger, permissions = session_setup
    session = SecureSession(plan, ledger, permissions)
    session.advance()
    ledger.record(plan, 'second', reviewer='human', decision='revoke', reason='Pause review', expected_head=ledger.head)
    with pytest.raises(PermissionError):
        session.advance()
    assert session.status == 'paused'
    assert session.snapshot()['attempts'] == 1
    session.cancel('Human cancelled remaining work')
    with pytest.raises(SessionCancelled):
        session.advance()


def test_session_whole_deadline_prevents_dispatch(session_setup, monkeypatch):
    from nablamath.agents import secure_execution as module
    plan, ledger, permissions = session_setup
    session = SecureSession(plan, ledger, permissions)
    monkeypatch.setattr(module.time, 'monotonic', lambda: session._started+31)
    with pytest.raises(TimeoutError):
        session.advance()
    assert session.status == 'expired'
    assert session.snapshot()['attempts'] == 0


def test_cumulative_output_budget_failure_is_replayable(protocol):
    # Every individual predictor vector fits, but complete task IDs and accumulated
    # vectors exceed this budget. No oversized partial prediction is retained.
    candidate = candidate_for(protocol, budget=TrialBudget(max_output_bytes=120))
    ledger = ApprovalLedger()
    authorize(candidate, ledger)
    runner = SecureTrialRunner(candidate, protocol, ledger)
    result = runner.run()
    assert result['status'] == 'failed'
    assert 'output budget' in result['error']
    assert len(json.dumps(result['predictions'], separators=(',', ':')).encode()) <= 120
    assert runner.verify_history()


def test_final_evaluation_output_budget_is_enforced(protocol):
    candidate = candidate_for(protocol, budget=TrialBudget(max_output_bytes=500))
    ledger = ApprovalLedger()
    authorize(candidate, ledger)
    runner = SecureTrialRunner(candidate, protocol, ledger)
    result = runner.run()
    assert result['status'] == 'failed'
    assert result['evaluation'] is None
    assert 'Evaluation artifacts' in result['error']
    assert runner.verify_history()


def test_trial_total_deadline_fails_closed_before_predictor(protocol, monkeypatch):
    from nablamath.evolution import secure_trials as module
    candidate = candidate_for(protocol, budget=TrialBudget(timeout_seconds=1))
    ledger = ApprovalLedger()
    authorize(candidate, ledger)
    runner = SecureTrialRunner(candidate, protocol, ledger)
    clock = iter([0, 2])
    monkeypatch.setattr(module.time, 'monotonic', lambda: next(clock))
    result = runner.run()
    assert result['status'] == 'failed'
    assert 'TimeoutError' in result['error']
    assert result['predictions'] == []
    assert runner.verify_history()
