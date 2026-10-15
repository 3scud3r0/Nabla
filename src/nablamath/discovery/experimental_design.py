"""Select unsampled points by exact disagreement between competing models."""
from ..core.semantic_ir import rational


def propose_experiment(hypotheses, candidates, *, observed=(), uncertainty='1'):
    hypotheses,candidates=tuple(hypotheses),tuple(rational(x) for x in candidates)
    noise=rational(uncertainty)
    if not 2<=len(hypotheses)<=16 or not 1<=len(candidates)<=256 or noise<=0:
        raise ValueError('Modelos, pontos e incerteza fora dos limites')
    if len({(h.input_unit.to_data().__repr__(),h.output_unit.to_data().__repr__()) for h in hypotheses})!=1:
        raise ValueError('Modelos devem compartilhar unidades')
    seen={rational(x) for x in observed}; rows=[]; skipped=[]
    for x in sorted(set(candidates)-seen):
        try:
            predictions=tuple(h.predict(x) for h in hypotheses)
            mean=sum(predictions)/len(predictions)
            variance=sum((y-mean)**2 for y in predictions)/len(predictions)
            rows.append({'x':str(x),'predictions':[str(y) for y in predictions],'utility':str(variance/noise**2)})
        except (ValueError,ArithmeticError):
            skipped.append(str(x))
    rows.sort(key=lambda r:(-rational(r['utility']),rational(r['x'])))
    return {'selected':rows[0] if rows else None,'ranked':rows,'skipped_undefined_or_outside_domain':skipped,
            'criterion':'model_disagreement_over_declared_noise_squared','experiment_performed':False}


def propose_constrained_experiment(hypotheses, candidates, *, costs, budget,
                                   excluded=(), observed=(), uncertainty='1'):
    """Rank finite feasible experiments by disagreement per declared positive cost.

    Costs/exclusions are caller-supplied constraints, not a certification that an
    experiment is physically feasible or safe. No instrument is operated here.
    """
    candidates = tuple(rational(x) for x in candidates)
    budget = rational(budget)
    if budget <= 0 or len(set(candidates)) != len(candidates):
        raise ValueError('Orçamento positivo e candidatos únicos obrigatórios')
    normalized = {}
    for point, cost in costs.items():
        point, cost = rational(point), rational(cost)
        if point in normalized or cost <= 0:
            raise ValueError('Custo positivo único por candidato obrigatório')
        normalized[point] = cost
    if set(normalized) != set(candidates):
        raise ValueError('Custos devem cobrir exatamente os candidatos')
    blocked = {rational(x) for x in excluded}
    feasible = [x for x in candidates if x not in blocked and normalized[x] <= budget]
    skipped = [{'x': str(x), 'reason': 'excluded' if x in blocked else 'over_budget'}
               for x in candidates if x not in feasible]
    # Validate hypotheses and uncertainty even when all candidates are excluded.
    report = propose_experiment(hypotheses, candidates, observed=observed, uncertainty=uncertainty)
    ranked = []
    for row in report['ranked']:
        point = rational(row['x'])
        if point in feasible:
            ranked.append({**row, 'cost': str(normalized[point]),
                           'utility_per_cost': str(rational(row['utility'])/normalized[point])})
    ranked.sort(key=lambda row: (-rational(row['utility_per_cost']), rational(row['x'])))
    return {**report, 'ranked': ranked, 'selected': ranked[0] if ranked else None,
            'budget': str(budget), 'skipped_constraints': skipped,
            'criterion': 'model_disagreement_over_noise_squared_per_declared_cost',
            'physical_feasibility_verified': False}
