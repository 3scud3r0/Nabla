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
