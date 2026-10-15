"""Execute validated proposals with capability checks and a chained audit trail."""
import time
from ..core.semantic_ir import fingerprint
from .proposals import Proposal
from .bindings import resolve, references


class Planner:
    def __init__(self, registry, permissions):
        self.registry, self.permissions = registry, permissions

    def run(self, proposal, *, store=None, stop_after=None):
        if not isinstance(proposal, Proposal):
            proposal = Proposal.from_data(proposal)
        if len(proposal.actions) > self.permissions.max_calls:
            raise ValueError('Plano excede número de chamadas')
        # Validate every action before executing any side effect.
        for action in proposal.actions:
            self.registry.validate(action.tool, action.arguments, self.permissions)
        if stop_after is not None and (type(stop_after) is not int or not 1 <= stop_after <= 100):
            raise ValueError('Pausa requer 1–100 ações')
        saved = store.load(proposal.content_id) if store is not None else None
        if saved is not None and any(r['status'] != 'completed' for r in saved['receipts']):
            raise ValueError('Execução anterior falhou; criar nova proposta explícita para repetir')
        receipts = list(saved['receipts']) if saved else []
        previous = saved['final_receipt'] if saved else proposal.content_id
        expected_head = saved['final_receipt'] if saved else None
        results = {r['action_id']:r['result'] for r in receipts}
        start = time.monotonic()
        completed_before = len(receipts)
        for action in proposal.actions[completed_before:]:
            if stop_after is not None and len(receipts)-completed_before >= stop_after:
                break
            if time.monotonic()-start >= self.permissions.timeout_seconds:
                status, result = 'timeout', {'error': 'Orçamento total esgotado'}
            else:
                from dataclasses import replace
                remaining = self.permissions.timeout_seconds-(time.monotonic()-start)
                try:
                    arguments = resolve(action.arguments, results)
                    result = self.registry.execute(action.tool, arguments,
                                                   replace(self.permissions, timeout_seconds=remaining))
                    status = 'completed'
                except (ValueError, TimeoutError, OSError, TypeError) as exc:
                    status, result = 'failed', {'error': str(exc)}
            receipt = {'action_id': action.action_id, 'tool': action.tool, 'status': status,
                       'arguments': action.arguments, 'result': result, 'previous': previous}
            if status == 'completed':
                results[action.action_id] = result
                if references(action.arguments):
                    receipt['resolved_arguments'] = arguments
            previous = fingerprint(receipt)
            receipts.append({**receipt, 'receipt_id': previous})
            if store is not None:
                checkpoint = self._report(proposal, receipts, previous)
                store.save(checkpoint, expected_head=expected_head)
                expected_head = previous
            if status != 'completed':
                break
        return self._report(proposal, receipts, previous)

    @staticmethod
    def _report(proposal, receipts, previous):
        return {'proposal': proposal.to_data(), 'proposal_id': proposal.content_id,
                'receipts': receipts, 'completed': len(receipts) == len(proposal.actions) and all(r['status']=='completed' for r in receipts),
                'final_receipt': previous, 'limitations': 'Trusted registered tools; no general autonomous scientific discovery.'}


def verify_run(report, *, replay_science=True):
    try:
        proposal = Proposal.from_data(report['proposal'])
        if proposal.content_id != report['proposal_id'] or len(report['receipts']) > len(proposal.actions):
            return False
        previous = proposal.content_id
        results = {}
        stopped = False
        for action, receipt in zip(proposal.actions, report['receipts']):
            if stopped:
                return False
            data = {k:v for k,v in receipt.items() if k != 'receipt_id'}
            if (data['previous'] != previous or data['action_id'] != action.action_id or data['tool'] != action.tool
                    or data['arguments'] != action.arguments or fingerprint(data) != receipt['receipt_id']):
                return False
            if data['status'] not in {'completed','failed','timeout'}:
                return False
            if data['status'] == 'completed':
                arguments = resolve(action.arguments, results)
                if references(action.arguments) and data.get('resolved_arguments') != arguments:
                    return False
                results[action.action_id] = data['result']
            else:
                stopped = True
            if replay_science and data['status']=='completed':
                from .tool_registry import _solve, _world, _verify
                from ..core.semantic_ir import canonical_json
                operation = {'solve': _solve, 'simulate': _world, 'verify': _verify}.get(action.tool)
                if operation is None or canonical_json(operation(**arguments)) != canonical_json(data['result']):
                    return False
            previous = receipt['receipt_id']
        completed = len(report['receipts']) == len(proposal.actions) and all(r['status']=='completed' for r in report['receipts'])
        return report['final_receipt'] == previous and report['completed'] == completed
    except (ValueError, KeyError, TypeError):
        return False
