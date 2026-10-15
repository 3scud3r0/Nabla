import copy
from dataclasses import replace
import pytest
from nablamath.agents.experiment_planner import plan_experiment
from nablamath.agents.human_approval import ApprovalLedger, run_approved
from nablamath.agents.permissions import Permissions
from nablamath.agents.planner import Planner
from nablamath.agents.tool_registry import scientific_registry
from nablamath.singularity.evaluation.safety import assess_plan, evaluate_cases
from nablamath.singularity.evaluation.long_horizon import evaluate_project


@pytest.fixture
def setup_plan():
    registry = scientific_registry()
    permissions = Permissions(frozenset({'simulate'}))
    plan = plan_experiment(question='Decay', owner='reviewer', hypothesis='State decays',
        expected_observation='Finite trajectory', trials=[dict(id='trial', tool='simulate',
        arguments=dict(name='exponential_decay', initial=[1], steps=2))],
        registry=registry, permissions=permissions)
    return plan, registry, permissions


def approve(plan, ledger):
    return ledger.record(plan, 'trial', reviewer='human', decision='approve', reason='Reviewed protocol', expected_head=ledger.head)


def test_review_binding_and_revocation(setup_plan):
    plan, registry, permissions = setup_plan
    ledger = ApprovalLedger()
    assert not assess_plan(plan, registry, permissions, ledger)['allowed']
    approve(plan, ledger)
    assert assess_plan(plan, registry, permissions, ledger)['allowed']
    assert not ledger.approved(replace(plan, hypothesis='Changed'), 'trial')
    restored = ApprovalLedger.from_data(ledger.to_data())
    assert restored.approved(plan, 'trial')
    restored.record(plan, 'trial', reviewer='human', decision='revoke', reason='Recheck', expected_head=restored.head)
    with pytest.raises(PermissionError):
        restored.require(plan)
    with pytest.raises(ValueError):
        ledger.record(plan, 'trial', reviewer='human', decision='approve', reason='Stale', expected_head=None)


def test_replay_rejects_tamper(setup_plan):
    plan, _, _ = setup_plan
    ledger = ApprovalLedger()
    approve(plan, ledger)
    events = ledger.to_data()
    events[0]['approval']['reviewer'] = 'intruder'
    with pytest.raises(ValueError):
        ApprovalLedger.from_data(events)
    assert ledger.approved(plan, 'trial')


def test_preflight_closed_capabilities(setup_plan):
    plan, registry, permissions = setup_plan
    with pytest.raises(PermissionError):
        plan.preflight(registry, replace(permissions, allowed_tools=frozenset({'solve'})))
    with pytest.raises(ValueError):
        plan.preflight(registry, replace(permissions, max_input_bytes=10))
    denied = ApprovalLedger()
    allowed = ApprovalLedger()
    approve(plan, allowed)
    result = evaluate_cases([dict(id='deny', plan=plan, ledger=denied, expected_allowed=False),
                             dict(id='allow', plan=plan, ledger=allowed, expected_allowed=True)], registry, permissions)
    assert result['passed'] == result['total'] == 2


def test_gate_executes_nothing_without_approval(setup_plan):
    plan, registry, permissions = setup_plan
    class NeverRun:
        def __init__(self):
            self.registry, self.permissions = registry, permissions
        def run(self, *args, **kwargs):
            raise AssertionError('Must not run')
    with pytest.raises(PermissionError):
        run_approved(plan, ApprovalLedger(), NeverRun())


def test_long_horizon_replay_and_fork_rejection(setup_plan):
    plan, registry, permissions = setup_plan
    ledger = ApprovalLedger()
    head = approve(plan, ledger)
    report = run_approved(plan, ledger, Planner(registry, permissions))
    assert report['completed'], report
    result = evaluate_project(plan.proposal, [report, report], milestones=['trial'], approval_heads=[head])
    assert result['all_achieved']
    tampered = copy.deepcopy(report)
    tampered['receipts'][0]['result'] = {'fake': True}
    with pytest.raises(ValueError):
        evaluate_project(plan.proposal, [tampered], milestones=['trial'])
    with pytest.raises(ValueError):
        evaluate_project(plan.proposal, [report], milestones=['unknown'])


def test_budget_and_long_horizon_resume(setup_plan):
    _, registry, permissions = setup_plan
    trials = [dict(id=name, tool='simulate', arguments=dict(name='exponential_decay', initial=[1], steps=2))
              for name in ('first', 'second')]
    with pytest.raises(ValueError):
        plan_experiment(question='Decay', owner='human', hypothesis='Decay', expected_observation='Trajectory',
                        trials=trials, registry=registry, permissions=replace(permissions, max_calls=1))
    plan = plan_experiment(question='Decay', owner='human', hypothesis='Decay', expected_observation='Trajectory',
                           trials=trials, registry=registry, permissions=permissions)
    planner = Planner(registry, permissions)
    partial = planner.run(plan.proposal, stop_after=1)
    complete = planner.run(plan.proposal)
    result = evaluate_project(plan.proposal, [partial, complete], milestones=['first', 'second'])
    assert result['checkpoints'][0]['completed_milestones'] == ['first']
    assert result['all_achieved']
    with pytest.raises(ValueError, match='rollback'):
        evaluate_project(plan.proposal, [complete, partial], milestones=['first'])


def test_approval_history_rejects_reordering_and_unknown_actions(setup_plan):
    plan, _, _ = setup_plan
    ledger = ApprovalLedger()
    with pytest.raises(ValueError, match='Unknown'):
        ledger.record(plan, 'other', reviewer='human', decision='approve', reason='Review', expected_head=None)
    approve(plan, ledger)
    ledger.record(plan, 'trial', reviewer='human', decision='reject', reason='Changed assessment', expected_head=ledger.head)
    with pytest.raises(ValueError):
        ApprovalLedger.from_data(list(reversed(ledger.to_data())))
    assert not ledger.approved(plan, 'trial')


def test_concurrent_same_head_has_exactly_one_winner(setup_plan, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from nablamath.agents import human_approval as module
    plan, _, _ = setup_plan
    ledger = ApprovalLedger()
    hashing, second_started = Event(), Event()
    original = module.fingerprint
    def controlled_fingerprint(value):
        if not hashing.is_set():
            hashing.set()
            assert second_started.wait(5)
        return original(value)
    monkeypatch.setattr(module, 'fingerprint', controlled_fingerprint)
    def write(second=False):
        if second:
            second_started.set()
        try:
            ledger.record(plan, 'trial', reviewer='human', decision='approve', reason='Reviewed', expected_head=None)
            return 'committed'
        except ValueError:
            return 'stale'
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(write)
        assert hashing.wait(5)
        second = pool.submit(write, True)
        assert sorted((first.result(5), second.result(5))) == ['committed', 'stale']
    assert len(ledger.to_data()) == 1
    assert ApprovalLedger.from_data(ledger.to_data()).approved(plan, 'trial')


def test_unbounded_inputs_are_consumed_only_to_limits(setup_plan):
    from itertools import repeat
    plan, registry, permissions = setup_plan
    ledger = ApprovalLedger()
    approve(plan, ledger)
    case = dict(id='same', plan=plan, ledger=ledger, expected_allowed=True)
    with pytest.raises(ValueError):
        evaluate_cases(repeat(case), registry, permissions)
    report = Planner(registry, permissions).run(plan.proposal)
    with pytest.raises(ValueError):
        evaluate_project(plan.proposal, repeat(report), milestones=['trial'])
    with pytest.raises(ValueError):
        evaluate_project(plan.proposal, [report], milestones=repeat('trial'))
    with pytest.raises(ValueError):
        evaluate_project(plan.proposal, [report], milestones=['trial'], approval_heads=repeat('a'*64))
