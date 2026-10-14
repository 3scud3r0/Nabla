"""Fixed solver policies and immutable analytic evaluators on separated holdouts."""
from dataclasses import dataclass, asdict
import math

from ..core.semantic_ir import fingerprint
from ..worlds import ModelSpec, simulate


@dataclass(frozen=True)
class SolverPolicy:
    method: str
    steps: int

    def __post_init__(self):
        if self.method not in {'euler', 'rk4'} or type(self.steps) is not int or not 2 <= self.steps <= 10000:
            raise ValueError('Politica de integracao invalida')

    @property
    def policy_id(self):
        return fingerprint(asdict(self))

    @property
    def derivative_calls(self):
        return self.steps * (4 if self.method == 'rk4' else 1)


def _model_id(model: ModelSpec) -> str:
    return fingerprint(asdict(model))


def _loss(policy: SolverPolicy, model: ModelSpec) -> float:
    try:
        loss = simulate(model, steps=policy.steps, method=policy.method)['max_component_error']
        return loss if math.isfinite(loss) else math.inf
    except (ValueError, OverflowError):
        return math.inf


def select_on_calibration(candidates: tuple[SolverPolicy, ...], calibration: tuple[ModelSpec, ...],
                          *, max_derivative_calls: int = 400) -> SolverPolicy:
    if not 1 <= len(candidates) <= 32 or not 1 <= len(calibration) <= 64:
        raise ValueError('Orcamento de candidatos/calibracao invalido')
    eligible = [p for p in candidates if p.derivative_calls <= max_derivative_calls]
    if not eligible:
        raise ValueError('Nenhuma politica cabe no orcamento')
    return min(eligible, key=lambda p: (max(_loss(p, m) for m in calibration), p.derivative_calls, p.policy_id))


def evaluate_proposal(candidate: SolverPolicy, baseline: SolverPolicy, calibration: tuple[ModelSpec, ...],
                      holdout: tuple[ModelSpec, ...], *, tolerance: float = 1e-5, alpha: float = .05,
                      max_derivative_calls: int = 400) -> dict:
    if not 1 <= len(calibration) <= 64 or not 5 <= len(holdout) <= 64:
        raise ValueError('Calibracao requer 1..64 casos e holdout 5..64')
    if not math.isfinite(tolerance) or tolerance <= 0 or not 0 < alpha < 1:
        raise ValueError('Tolerancia ou alpha invalidos')
    train_ids, test_ids = [_model_id(m) for m in calibration], [_model_id(m) for m in holdout]
    if len(set(train_ids)) != len(train_ids) or len(set(test_ids)) != len(test_ids) or set(train_ids) & set(test_ids):
        raise ValueError('Casos repetidos ou contaminacao entre calibracao e holdout')
    base_losses = tuple(_loss(baseline, m) for m in holdout)
    losses = tuple(_loss(candidate, m) for m in holdout)
    wins = sum(a < b for a, b in zip(losses, base_losses))
    losses_count = sum(a > b for a, b in zip(losses, base_losses))
    decisive = wins + losses_count
    # Exact one-sided paired sign test under iid Bernoulli(1/2) null. This is
    # descriptive evidence only for these declared model cases, not general RSI.
    p_value = sum(math.comb(decisive, k) for k in range(wins, decisive+1))/2**decisive if decisive else 1.0
    finite = all(math.isfinite(v) for v in losses + base_losses)
    accepted = (finite and candidate.derivative_calls <= max_derivative_calls and losses_count == 0
                and wins > 0 and max(losses) <= tolerance and p_value <= alpha)
    def safe(values):
        return [v if math.isfinite(v) else None for v in values]
    return {'candidate_id': candidate.policy_id, 'baseline_id': baseline.policy_id,
            'candidate': asdict(candidate), 'baseline': asdict(baseline),
            'calibration_ids': train_ids, 'holdout_ids': test_ids,
            'candidate_errors': safe(losses), 'baseline_errors': safe(base_losses),
            'wins': wins, 'regressions': losses_count, 'ties': len(holdout)-decisive,
            'sign_test_p_value': p_value, 'alpha': alpha, 'tolerance': tolerance,
            'candidate_derivative_calls': candidate.derivative_calls,
            'baseline_derivative_calls': baseline.derivative_calls, 'budget': max_derivative_calls,
            'accepted': accepted, 'rollback_policy': asdict(baseline),
            'evaluator_version': 'analytic-policy-v1',
            'limitations': 'Selecao entre Euler/RK4; casos sinteticos nao garantem independencia estatistica, ganho geral ou autoedicao de codigo.'}
