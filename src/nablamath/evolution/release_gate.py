"""Replay every release evaluation against the frozen contract and trusted local vault."""
from ..core.semantic_ir import fingerprint,canonical_json
from ..worlds import ModelSpec
from .policy_genome import PolicyGenome
from .proposal_validator import EvaluationContract,validate_proposal
from .evaluator import evaluate_proposal
from .statistical_tests import paired_sign_test


def release_gate(receipt,contract,*,manager):
    try:
        contract.assert_current()
        payload={k:v for k,v in receipt.items() if k!='receipt_id'}
        if fingerprint(payload)!=receipt['receipt_id'] or not manager.contains_receipt(receipt):
            raise ValueError('Recibo não emitido pelo gerenciador confiável')
        if receipt['contract_id']!=contract.contract_id or receipt['contract']!=contract.to_data():
            raise ValueError('Contrato divergente')
        candidate,baseline=(PolicyGenome.from_data(receipt[name]) for name in ('candidate','baseline'))
        validate_proposal(candidate,baseline,contract)
        actual=evaluate_proposal(candidate.as_policy(),baseline.as_policy(),
                  tuple(ModelSpec(**m) for m in receipt['calibration']),tuple(ModelSpec(**m) for m in receipt['holdout']),
                  tolerance=contract.tolerance,alpha=contract.alpha/contract.max_generations,max_derivative_calls=contract.max_derivative_calls)
        if canonical_json(actual)!=canonical_json(receipt['evaluation']):
            raise ValueError('Avaliação reexecutada divergiu')
        statistics=paired_sign_test(actual['candidate_errors'],actual['baseline_errors'],alpha=contract.alpha/contract.max_generations)
        accepted=actual['accepted'] and statistics['valid'] and statistics['significant']
        return {'accepted':accepted,'receipt_id':receipt['receipt_id'],'statistics':statistics,
                'reason':'passed' if accepted else 'regression_budget_tolerance_or_significance_gate',
                'scope':'bounded ODE policies, not arbitrary code self-improvement'}
    except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
        return {'accepted':False,'reason':str(exc)}


def verify_policy_receipt(receipt):
    """Scientific replay alone; release authorization additionally needs the manager."""
    try:
        payload={k:v for k,v in receipt.items() if k!='receipt_id'}
        if fingerprint(payload)!=receipt['receipt_id']:
            return False
        contract=EvaluationContract(**receipt['contract'])
        contract.assert_current()
        candidate,baseline=(PolicyGenome.from_data(receipt[name]) for name in ('candidate','baseline'))
        validate_proposal(candidate,baseline,contract)
        actual=evaluate_proposal(candidate.as_policy(),baseline.as_policy(),
                  tuple(ModelSpec(**m) for m in receipt['calibration']),tuple(ModelSpec(**m) for m in receipt['holdout']),
                  tolerance=contract.tolerance,alpha=contract.alpha/contract.max_generations,
                  max_derivative_calls=contract.max_derivative_calls)
        return canonical_json(actual)==canonical_json(receipt['evaluation']) and receipt['contract_id']==contract.contract_id
    except (ValueError,KeyError,TypeError,ArithmeticError):
        return False
