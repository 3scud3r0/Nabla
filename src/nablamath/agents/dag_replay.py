"""Independent bounded verification of durable DAG checkpoints and science.

Replay proves consistency with fixed local mathematical tools. Hash chains are
not signatures, and no checkpoint importer grants execution authority. The
SQLite database and node configuration remain trusted local state.
"""
from ..core.semantic_ir import canonical_json, fingerprint
from .bindings import resolve
from .dag_contracts import (
    DagBudget, RUN_STATES, TASK_STATES, experiment_from_data,
    permissions_from_data, preflight_dag, replay_scientific_result, result_receipt,
)
from .human_approval import ApprovalLedger


def committed_results(plan, run_id, rows, *, replay=True):
    """Validate receipts in topological order and return detached JSON results."""
    import json
    results = {}
    receipts = {}
    for action in plan.proposal.actions:
        row = rows[action.action_id]
        status = row['status']
        result = row.get('result') if isinstance(row, dict) else None
        receipt = row.get('receipt') if isinstance(row, dict) else None
        if 'result_json' in row.keys():
            result = json.loads(row['result_json']) if row['result_json'] else None
            receipt = json.loads(row['receipt_json']) if row['receipt_json'] else None
        if status != 'completed':
            if result is not None or receipt is not None:
                raise ValueError('Uncompleted task contains a committed result')
            continue
        if any(dep not in results for dep in action.depends_on):
            raise ValueError('Completed task has no completed dependency receipt')
        arguments = resolve(action.arguments, results)
        dependencies = {dep: receipts[dep]['receipt_id'] for dep in action.depends_on}
        expected = result_receipt(run_id=run_id, action=action, arguments=arguments,
                                  result=result, dependencies=dependencies)
        if receipt != expected:
            raise ValueError('Completed scientific receipt commitment mismatch')
        if replay and not replay_scientific_result(action.tool, arguments, result):
            raise ValueError('Completed result does not reproduce scientific calculation')
        results[action.action_id] = result
        receipts[action.action_id] = receipt
    return results, receipts


def verify_dag_snapshot(snapshot, *, replay=True):
    """Validate a finite checkpoint without executing worker-controlled callbacks."""
    try:
        fields = {'schema_version', 'run_id', 'plan', 'permissions', 'budget', 'approvals',
                  'approval_head', 'created', 'deadline', 'status', 'revision',
                  'total_attempts', 'result_bytes', 'tasks', 'events', 'limitations', 'snapshot_id'}
        if not isinstance(snapshot, dict) or set(snapshot) != fields:
            return False
        body = {key: value for key, value in snapshot.items() if key != 'snapshot_id'}
        if fingerprint(body) != snapshot['snapshot_id'] or type(body['schema_version']) is not int or body['schema_version'] != 1:
            return False
        plan = experiment_from_data(body['plan'])
        permissions = permissions_from_data(body['permissions'])
        budget = DagBudget.from_data(body['budget'])
        if preflight_dag(plan, permissions, budget) != body['run_id']:
            return False
        approvals = ApprovalLedger.from_data(body['approvals'])
        if approvals.head != body['approval_head'] or body['status'] not in RUN_STATES:
            return False
        if body['deadline'] != body['created']+budget.run_timeout_seconds:
            return False
        if (not isinstance(body['tasks'], list) or len(body['tasks']) != len(plan.proposal.actions)
                or not isinstance(body['events'], list) or not 1 <= len(body['events']) <= 200000):
            return False
        task_fields = {'action_id', 'status', 'attempts', 'available', 'expires', 'error_code', 'result', 'receipt'}
        rows = {}
        for action, row in zip(plan.proposal.actions, body['tasks']):
            if (not isinstance(row, dict) or set(row) != task_fields or row['action_id'] != action.action_id
                    or row['status'] not in TASK_STATES or type(row['attempts']) is not int
                    or not 0 <= row['attempts'] <= budget.max_attempts_per_action):
                return False
            rows[action.action_id] = row
        results, receipts = committed_results(plan, body['run_id'], rows, replay=replay)
        if body['result_bytes'] != sum(len(canonical_json(result).encode()) for result in results.values()):
            return False
        if (body['result_bytes'] > budget.max_total_result_bytes
                or any(len(canonical_json(result).encode()) > budget.max_result_bytes for result in results.values())):
            return False
        if body['total_attempts'] != sum(row['attempts'] for row in rows.values()) or body['total_attempts'] > budget.max_total_attempts:
            return False
        previous = None
        attempts = {action.action_id: 0 for action in plan.proposal.actions}
        completed = set()
        for sequence, event in enumerate(body['events']):
            if not isinstance(event, dict) or set(event) != {'schema_version', 'run_id', 'sequence', 'kind', 'payload', 'previous', 'event_id'}:
                return False
            data = {key: value for key, value in event.items() if key != 'event_id'}
            if (type(event['sequence']) is not int or event['sequence'] != sequence
                    or event['schema_version'] != 1 or event['previous'] != previous
                    or event['run_id'] != body['run_id'] or fingerprint(data) != event['event_id']):
                return False
            payload = event['payload']
            if sequence == 0 and (event['kind'] != 'created' or payload['plan_id'] != plan.content_id):
                return False
            if event['kind'] == 'leased':
                name = payload['action_id']
                if name not in attempts or name in completed:
                    return False
                attempts[name] += 1
                if payload['attempt'] != attempts[name]:
                    return False
            elif event['kind'] == 'completed':
                name = payload['action_id']
                if name in completed or name not in receipts or payload['receipt_id'] != receipts[name]['receipt_id']:
                    return False
                completed.add(name)
            previous = event['event_id']
        if (body['revision'] != len(body['events']) or completed != set(receipts)
                or any(attempts[name] != row['attempts'] for name, row in rows.items())):
            return False
        if body['status'] == 'completed' and len(results) != len(rows):
            return False
        if body['status'] == 'failed' and any(row['status'] not in {'completed', 'failed', 'blocked', 'cancelled'} for row in rows.values()):
            return False
        if body['status'] in {'cancelled', 'expired'} and any(row['status'] in {'queued', 'leased', 'retry_wait'} for row in rows.values()):
            return False
        for action in plan.proposal.actions:
            row = rows[action.action_id]
            if row['status'] == 'leased' and any(rows[dep]['status'] != 'completed' for dep in action.depends_on):
                return False
            if row['status'] == 'blocked' and not any(rows[dep]['status'] in {'failed', 'blocked', 'cancelled'} for dep in action.depends_on):
                return False
        return True
    except (ValueError, TypeError, KeyError, LookupError, ArithmeticError, AttributeError):
        return False
