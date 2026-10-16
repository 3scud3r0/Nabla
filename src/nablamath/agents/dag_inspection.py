"""Read-only explanations of durable scientific DAG and pooled admission state.

These reports expose fixed action IDs, counters and reasons, not raw scientific
expressions, participant identities or result bodies. They are point-in-time
explanations, not lease promises; the write transaction is authoritative.
Critical-path lengths count actions, not measured runtimes or promised speedup.
"""
from collections import Counter

from ..core.semantic_ir import fingerprint
from ..node.consent import Consent
from .dag_contracts import DagBudget, experiment_from_data, finite_time
from .dag_replay import verify_dag_snapshot
from .human_approval import ApprovalLedger


def _pool_reason(pool, tool, cpu_slots, memory_bytes):
    if pool is None:
        return []
    if not isinstance(pool, dict) or 'snapshot_id' not in pool:
        raise ValueError('Committed pool snapshot required')
    body = {key: value for key, value in pool.items() if key != 'snapshot_id'}
    if fingerprint(body) != pool['snapshot_id']:
        raise ValueError('Pool snapshot commitment mismatch')
    profile = pool['configuration']['profile']
    limits = pool['configuration']['tool_limits']
    used = pool['usage']
    reasons = []
    if tool not in limits:
        reasons.append('tool_not_admitted_by_pool')
    elif used['tools'].get(tool, 0) >= limits[tool]:
        reasons.append('pool_tool_quota')
    if used['cpu_slots']+cpu_slots > profile['cpu_slots']:
        reasons.append('pool_cpu_quota')
    if used['memory_bytes']+memory_bytes > profile['memory_bytes']:
        reasons.append('pool_memory_quota')
    if used['active_tasks'] >= profile['max_tasks']:
        reasons.append('pool_task_quota')
    return reasons


def inspect_checkpoint(snapshot, *, now, consent=None, on_battery=False,
                       pool_snapshot=None, cpu_slots=1, memory_bytes=1):
    """Explain every action without dispatch, mutation, polling or arbitrary code."""
    if not verify_dag_snapshot(snapshot, replay=False):
        raise ValueError('DAG checkpoint failed structural and receipt verification')
    now = finite_time(now, 'inspection time')
    if type(on_battery) is not bool:
        raise ValueError('Explicit boolean power state required')
    if type(cpu_slots) is not int or cpu_slots < 1 or type(memory_bytes) is not int or memory_bytes < 1:
        raise ValueError('Positive integer declared resources required')
    if consent is not None and not isinstance(consent, Consent):
        raise ValueError('Typed local consent required')
    plan = experiment_from_data(snapshot['plan'])
    budget = DagBudget.from_data(snapshot['budget'])
    ledger = ApprovalLedger.from_data(snapshot['approvals'])
    tasks = {row['action_id']: row for row in snapshot['tasks']}
    active = sum(row['status'] == 'leased' for row in tasks.values())
    run_reasons = []
    if snapshot['status'] in {'completed', 'failed', 'cancelled', 'expired'}:
        run_reasons.append('run_'+snapshot['status'])
    if now >= snapshot['deadline']:
        run_reasons.append('run_deadline')
    if snapshot['status'] == 'paused':
        run_reasons.append('review_paused')
    if any(not ledger.approved(plan, action.action_id) for action in plan.proposal.actions):
        run_reasons.append('human_review_required')
    if snapshot['total_attempts'] >= budget.max_total_attempts:
        run_reasons.append('whole_run_attempt_budget')
    consent_checked = consent is not None
    if consent is not None:
        if (type(consent.contribute) is not bool or type(consent.allow_on_battery) is not bool
                or type(consent.allow_network) is not bool
                or consent.expires_unix is not None and (type(consent.expires_unix) is not int or consent.expires_unix < 0)):
            raise ValueError('Invalid consent capabilities or expiry')
        if not consent.active(now):
            run_reasons.append('node_consent_inactive')
        if on_battery and not consent.allow_on_battery:
            run_reasons.append('node_battery_disallowed')
    levels = {}
    remaining_depth = {}
    reports = []
    for action in plan.proposal.actions:
        task = tasks[action.action_id]
        levels[action.action_id] = 1+max((levels[dep] for dep in action.depends_on), default=0)
        if task['status'] == 'completed':
            remaining_depth[action.action_id] = 0
        elif task['status'] in {'failed', 'blocked', 'cancelled'} or any(remaining_depth[dep] is None for dep in action.depends_on):
            remaining_depth[action.action_id] = None
        else:
            remaining_depth[action.action_id] = 1+max((remaining_depth[dep] for dep in action.depends_on), default=0)
        reasons = list(run_reasons)
        if task['status'] in {'completed', 'failed', 'blocked', 'cancelled'}:
            reasons.append('action_'+task['status'])
        elif task['status'] == 'leased':
            reasons.append('action_already_leased')
            if task['expires'] is not None and now >= task['expires']:
                reasons.append('lease_needs_recovery')
        else:
            if task['available'] > now:
                reasons.append('retry_backoff')
            if task['attempts'] >= budget.max_attempts_per_action:
                reasons.append('action_attempt_budget')
            if active >= budget.max_parallel_actions:
                reasons.append('run_parallel_quota')
        waiting = [dep for dep in action.depends_on if tasks[dep]['status'] != 'completed']
        if waiting:
            reasons.append('dependencies_not_completed')
        if task['status'] in {'queued', 'retry_wait'}:
            reasons.extend(_pool_reason(pool_snapshot, action.tool, cpu_slots, memory_bytes))
        reports.append(dict(action_id=action.action_id, tool=action.tool, status=task['status'],
                            attempts=task['attempts'], remaining_attempts=max(0, budget.max_attempts_per_action-task['attempts']),
                            waiting_on=waiting, ready_now=not reasons, reasons=reasons,
                            retry_after_seconds=max(0., task['available']-now),
                            graph_level=levels[action.action_id], remaining_path_actions=remaining_depth[action.action_id]))
    counts = dict(sorted(Counter(row['status'] for row in tasks.values()).items()))
    completable = all(value is not None for value in remaining_depth.values()) and snapshot['status'] not in {'failed', 'cancelled', 'expired'}
    body = dict(schema_version=1, run_id=snapshot['run_id'], checkpoint_id=snapshot['snapshot_id'],
                status=snapshot['status'], counts=counts, actions=reports,
                ready_actions=[row['action_id'] for row in reports if row['ready_now']],
                completed_actions=counts.get('completed', 0), total_actions=len(tasks),
                completion_possible=completable, consent_checked=consent_checked,
                remaining_attempt_budget=max(0, budget.max_total_attempts-snapshot['total_attempts']),
                remaining_result_bytes=max(0, budget.max_total_result_bytes-snapshot['result_bytes']),
                remaining_run_seconds=max(0., snapshot['deadline']-now),
                graph_depth=max(levels.values()),
                remaining_critical_path_actions=max((v for v in remaining_depth.values() if v is not None), default=0),
                limitations='Point-in-time cooperative admission explanation; no runtime, authenticity or generalization guarantee')
    return dict(body, inspection_id=fingerprint(body))
