"""Execute validated proposals with capability checks and a chained audit trail."""
import time
from ..core.semantic_ir import fingerprint
from .proposals import Proposal


class Planner:
    def __init__(self, registry, permissions):
        self.registry, self.permissions = registry, permissions

    def run(self, proposal):
        if not isinstance(proposal, Proposal):
            proposal = Proposal.from_data(proposal)
        if len(proposal.actions) > self.permissions.max_calls:
            raise ValueError('Plano excede número de chamadas')
        # Validate every action before executing any side effect.
        for action in proposal.actions:
            self.registry.validate(action.tool, action.arguments, self.permissions)
        receipts, previous = [], proposal.content_id
        start = time.monotonic()
        for action in proposal.actions:
            if time.monotonic()-start >= self.permissions.timeout_seconds:
                status, result = 'timeout', {'error': 'Orçamento total esgotado'}
            else:
                from dataclasses import replace
                remaining = self.permissions.timeout_seconds-(time.monotonic()-start)
                try:
                    result = self.registry.execute(action.tool, action.arguments,
                                                   replace(self.permissions, timeout_seconds=remaining))
                    status = 'completed'
                except (ValueError, TimeoutError, OSError, TypeError) as exc:
                    status, result = 'failed', {'error': str(exc)}
            receipt = {'action_id': action.action_id, 'tool': action.tool, 'status': status,
                       'arguments': action.arguments, 'result': result, 'previous': previous}
            previous = fingerprint(receipt)
            receipts.append({**receipt, 'receipt_id': previous})
            if status != 'completed':
                break
        return {'proposal': proposal.to_data(), 'proposal_id': proposal.content_id,
                'receipts': receipts, 'completed': len(receipts) == len(proposal.actions) and all(r['status']=='completed' for r in receipts),
                'final_receipt': previous, 'limitations': 'Trusted registered tools; no general autonomous scientific discovery.'}


def verify_run(report, *, replay_science=True):
    try:
        proposal = Proposal.from_data(report['proposal'])
        if proposal.content_id != report['proposal_id'] or len(report['receipts']) > len(proposal.actions):
            return False
        previous = proposal.content_id
        for action, receipt in zip(proposal.actions, report['receipts']):
            data = {k:v for k,v in receipt.items() if k != 'receipt_id'}
            if (data['previous'] != previous or data['action_id'] != action.action_id or data['tool'] != action.tool
                    or data['arguments'] != action.arguments or fingerprint(data) != receipt['receipt_id']):
                return False
            if data['status'] not in {'completed','failed','timeout'}:
                return False
            if replay_science and data['status']=='completed':
                from .tool_registry import _solve, _world
                from ..core.semantic_ir import canonical_json
                operation = {'solve': _solve, 'simulate': _world}.get(action.tool)
                if operation is None or canonical_json(operation(**action.arguments)) != canonical_json(data['result']):
                    return False
            previous = receipt['receipt_id']
        completed = len(report['receipts']) == len(proposal.actions) and all(r['status']=='completed' for r in report['receipts'])
        return report['final_receipt'] == previous and report['completed'] == completed
    except (ValueError, KeyError, TypeError):
        return False
