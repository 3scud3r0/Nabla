"""Gated trials of fixed algorithm IDs, never generated source or plugins.

Candidate computation runs as repository-owned functions in a killable child
process. Frozen evaluation rechecks exact predictions. This is not hostile-code
isolation, secret holdout protection, authenticated reviewer identity, external
validation, or authorization to publish a selected candidate.
"""
import copy
import json
from threading import RLock
import time

from ..agents.experiment_planner import ExperimentPlan
from ..agents.human_approval import ApprovalLedger
from ..agents.permissions import Permissions
from ..agents.proposals import Action, Proposal
from ..agents.tool_registry import Tool, ToolRegistry
from ..core.semantic_ir import ScientificTask, canonical_json, fingerprint, rational
from ..evaluation.frozen import FrozenEvaluation
from .code_proposals import ALGORITHMS, CodeProposal


def _predict(task, algorithm):
    """Closed trusted implementation; no dynamic import or candidate callback."""
    if algorithm not in ALGORITHMS:
        raise PermissionError('Unknown algorithm')
    task = ScientificTask.from_data(task)
    if task.family == 'polynomial_integral':
        if algorithm == 'exact-rational-v1':
            from ..verify.certificate import solve
            result = solve(task)
        else:
            result = (0,) + tuple(rational(c)/(i+1) for i, c in enumerate(task.coefficients))
    elif task.family == 'linear_system':
        from ..math.linear_algebra import Matrix, solve_linear
        matrix = Matrix(tuple(tuple(rational(v) for v in row) for row in task.matrix))
        rhs = tuple(rational(v) for v in task.rhs)
        if algorithm == 'exact-rational-v1':
            solved = solve_linear(matrix, rhs)
            if solved.status != 'unique':
                raise ValueError('Unique solution required')
            result = solved.particular
        else:
            result = tuple(row[0] for row in (matrix.inverse() @ Matrix(tuple((v,) for v in rhs))).rows)
    else:
        raise ValueError('Unsupported frozen task family')
    return [str(value) for value in result]


def review_plan(candidate):
    """Bind human decisions to algorithm, implementation, cohort and all budgets."""
    if not isinstance(candidate, CodeProposal):
        raise ValueError('Typed code proposal required')
    arguments = candidate.to_data()
    proposal = Proposal('Review bounded algorithm trial',
                        (Action('trial', 'review_algorithm', canonical_json(arguments)),),
                        'Declarative built-in algorithms only; no generated code or external actions')
    return ExperimentPlan(proposal, candidate.owner, candidate.rationale,
                          'Frozen exact-task descriptive evaluation', 'secure-trial-v1')


def _registry():
    return ToolRegistry((Tool('predict', _predict, frozenset({'task', 'algorithm'}),
                               description='Fixed exact-rational algorithm IDs only'),))


class TrialCancelled(RuntimeError):
    pass


class SecureTrialRunner:
    """A fixed candidate and protocol with bounded explicit retry attempts.

    Failed attempts consume budget. Retries require a reason and the prior
    committed attempt head. Successful trials cannot be retried to cherry-pick
    favorable timing. Evaluation is descriptive and never auto-releases code.
    """
    def __init__(self, candidate, protocol, ledger):
        if not isinstance(candidate, CodeProposal) or not isinstance(protocol, FrozenEvaluation):
            raise ValueError('Typed proposal and frozen protocol required')
        if not isinstance(ledger, ApprovalLedger):
            raise ValueError('Explicit human approval ledger required')
        candidate.preflight(protocol)
        self._candidate = candidate
        self._protocol = protocol
        self._ledger = ledger
        self._review = review_plan(candidate)
        self._attempts = []
        self._lock = RLock()

    @property
    def head(self):
        with self._lock:
            return self._attempts[-1]['attempt_id'] if self._attempts else None

    def history(self):
        with self._lock:
            return copy.deepcopy(self._attempts)

    def run(self, *, cancelled=lambda: False, retry_reason=None, expected_head=None):
        with self._lock:
            if self.head != expected_head:
                raise ValueError('Stale trial attempt head')
            if len(self._attempts) >= self._candidate.budget.max_attempts:
                raise ValueError('Trial attempt budget exhausted')
            if self._attempts:
                if self._attempts[-1]['status'] == 'completed':
                    raise ValueError('Completed trial cannot be repeated')
                if not isinstance(retry_reason, str) or not retry_reason.strip() or len(retry_reason) > 1024:
                    raise ValueError('Failed trial retry requires an explicit bounded reason')
            elif retry_reason is not None:
                raise ValueError('Initial trial is not a retry')
            self._candidate.preflight(self._protocol)
            self._ledger.require(self._review)
            start = time.monotonic()
            body = dict(schema_version=1, proposal_id=self._candidate.proposal_id,
                        protocol_id=self._protocol.protocol_id,
                        implementation_id=self._candidate.implementation_id,
                        index=len(self._attempts)+1, previous=self.head,
                        retry_reason=retry_reason, predictions=[], evaluation=None,
                        status='failed', error=None)
            try:
                tasks = json.loads(self._protocol.protocol_json)['tasks']
                for row in tasks:
                    if cancelled():
                        raise TrialCancelled('Trial cancelled before next task')
                    # Revocation takes effect at each task boundary.
                    self._ledger.require(self._review)
                    remaining = self._candidate.budget.timeout_seconds-(time.monotonic()-start)
                    if remaining <= 0:
                        raise TimeoutError('Whole-trial deadline exhausted')
                    permissions = Permissions(frozenset({'predict'}), 1, remaining,
                                              self._candidate.budget.max_input_bytes,
                                              self._candidate.budget.max_output_bytes)
                    values = _registry().execute('predict', dict(task=row, algorithm=self._candidate.algorithm), permissions)
                    prediction = dict(task_id=ScientificTask.from_data(row).content_id, values=values)
                    proposed = body['predictions'] + [prediction]
                    if len(canonical_json(proposed).encode()) > self._candidate.budget.max_output_bytes:
                        raise ValueError('Cumulative predictions exceed output budget')
                    body['predictions'] = proposed
                if cancelled():
                    raise TrialCancelled('Trial cancelled before evaluation')
                self._ledger.require(self._review)
                if time.monotonic()-start >= self._candidate.budget.timeout_seconds:
                    raise TimeoutError('Whole-trial deadline exhausted')
                submission = dict(protocol_id=self._protocol.protocol_id, predictions=body['predictions'])
                evaluation = self._protocol.evaluate(submission)
                if len(canonical_json(dict(predictions=body['predictions'], evaluation=evaluation)).encode()) > self._candidate.budget.max_output_bytes:
                    raise ValueError('Evaluation artifacts exceed cumulative output budget')
                if time.monotonic()-start >= self._candidate.budget.timeout_seconds:
                    raise TimeoutError('Evaluation exceeded whole-trial deadline; result not accepted')
                body['evaluation'] = evaluation
                body['status'] = 'completed'
            except TrialCancelled as exc:
                body['status'], body['error'] = 'cancelled', str(exc)
            except (ValueError, TypeError, PermissionError, TimeoutError, ArithmeticError, OSError) as exc:
                body['error'] = type(exc).__name__+': '+str(exc)[:1024]
            result = dict(body, attempt_id=fingerprint(body))
            self._attempts.append(result)
            return copy.deepcopy(result)

    def verify_history(self):
        with self._lock:
            return verify_trial_history(copy.deepcopy(self._attempts), self._candidate, self._protocol)


def verify_trial_history(history, candidate, protocol):
    """Replay finite local evidence, not authorization or provenance signatures."""
    try:
        candidate.preflight(protocol)
        if not isinstance(history, list) or not 1 <= len(history) <= candidate.budget.max_attempts:
            return False
        previous = None
        completed = False
        fields = {'schema_version', 'proposal_id', 'protocol_id', 'implementation_id',
                  'index', 'previous', 'retry_reason', 'predictions', 'evaluation',
                  'status', 'error', 'attempt_id'}
        for index, attempt in enumerate(history, 1):
            if not isinstance(attempt, dict) or set(attempt) != fields:
                return False
            body = {k: v for k, v in attempt.items() if k != 'attempt_id'}
            if (completed or type(body['schema_version']) is not int or body['schema_version'] != 1
                    or type(body['index']) is not int or fingerprint(body) != attempt['attempt_id']
                    or body['proposal_id'] != candidate.proposal_id
                    or body['protocol_id'] != protocol.protocol_id
                    or body['implementation_id'] != candidate.implementation_id
                    or body['index'] != index or body['previous'] != previous
                    or body['status'] not in {'completed', 'failed', 'cancelled'}):
                return False
            if index == 1 and body['retry_reason'] is not None:
                return False
            if index > 1 and (not isinstance(body['retry_reason'], str) or not body['retry_reason'].strip()):
                return False
            if not isinstance(body['predictions'], list) or len(body['predictions']) > candidate.budget.max_tasks:
                return False
            if len(canonical_json(body['predictions']).encode()) > candidate.budget.max_output_bytes:
                return False
            if body['status'] == 'completed':
                if body['error'] is not None:
                    return False
                if len(canonical_json(dict(predictions=body['predictions'], evaluation=body['evaluation'])).encode()) > candidate.budget.max_output_bytes:
                    return False
                submission = dict(protocol_id=protocol.protocol_id, predictions=body['predictions'])
                if not protocol.verify_report(body['evaluation'], submission):
                    return False
                # Verify that the registered algorithm, rather than a supplied
                # prediction vector, actually produces these exact outputs.
                tasks = json.loads(protocol.protocol_json)['tasks']
                expected = [dict(task_id=ScientificTask.from_data(row).content_id,
                                 values=_predict(row, candidate.algorithm)) for row in tasks]
                if expected != body['predictions']:
                    return False
                completed = True
            elif body['evaluation'] is not None or not isinstance(body['error'], str) or not body['error']:
                return False
            previous = attempt['attempt_id']
        return True
    except (ValueError, TypeError, KeyError, ArithmeticError, OSError):
        return False
