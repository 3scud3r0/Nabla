"""Independent exact grading on reserved examples; negative gains are retained."""
import math
from ..core.semantic_ir import fingerprint, canonical_json
from ..verify.trace import verify_candidate, VERIFIER_VERSION
from ..datasets.multimodal import INPUT_MODALITIES
from .contamination import audit_contamination
from ..evaluation.lineage import verify_lineage_report


def _wilson(successes, total):
    z = 1.959963984540054
    p = successes/total
    center = (p+z*z/(2*total))/(1+z*z/total)
    half = z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/(1+z*z/total)
    return [max(0.,center-half), min(1.,center+half)]


def evaluate(model, samples, *, training_samples, benchmark_name, model_id=None,
             modalities=INPUT_MODALITIES, family_holdout=True, lineage=None):
    training_samples, samples = tuple(training_samples), tuple(samples)
    if not benchmark_name.strip() or not 1 <= len(samples) <= 10000:
        raise ValueError('Benchmark nomeado e não vazio obrigatório')
    audit = audit_contamination(training_samples, samples, family_holdout=family_holdout, lineage=lineage)
    if not audit['clean']:
        raise ValueError('Contaminação ou partições inválidas: '+str(audit))
    if hasattr(model, 'training_ids') and set(model.training_ids) != {s.record.task.content_id for s in training_samples}:
        raise ValueError('Manifesto de treino não corresponde ao modelo')
    model_id = model_id or getattr(model, 'content_id', None)
    if not isinstance(model_id, str) or not model_id:
        raise ValueError('Modelo externo requer identificador de versão explícito')
    rows = []
    for sample in samples:
        inputs = sample.inputs(modalities)
        try:
            candidate = model.predict(inputs)
            canonical_json(candidate)
            verification = verify_candidate(sample.record.task, candidate).to_data()
            error = None
        except Exception as exc:
            candidate, error = None, str(exc)[:1000]
            verification = verify_candidate(sample.record.task, candidate).to_data()
        rows.append({'task_id': sample.record.task.content_id, 'candidate': candidate,
                     'valid': verification['valid'], 'verification': verification, 'error': error})
    successes = sum(row['valid'] for row in rows)
    payload = {'schema_version': 1, 'benchmark': benchmark_name, 'model_id': model_id,
               'training_ids': sorted(s.record.task.content_id for s in training_samples),
               'evaluation_ids': [s.record.task.content_id for s in samples], 'modalities': list(modalities),
               'successes': successes, 'total': len(rows), 'accuracy': successes/len(rows),
               'accuracy_wilson_95': _wilson(successes, len(rows)), 'results': rows,
               'contamination': audit, 'verifier_version': VERIFIER_VERSION,
               'external_count': sum(s.record.to_data()['origin']=='external' for s in samples),
               'provenance_independently_authenticated': False,
               'scope': 'exact correctness on supplied held-out tasks; not general scientific capability'}
    return {**payload, 'evaluation_id': fingerprint(payload)}


def verify_evaluation(report, samples, *, training_samples=None):
    try:
        payload = {k:v for k,v in report.items() if k != 'evaluation_id'}
        if fingerprint(payload) != report['evaluation_id']:
            return False
        samples = tuple(samples)
        lineage = report['contamination'].get('lineage')
        if lineage is not None:
            if not verify_lineage_report(lineage) or not lineage['clean']:
                return False
            declared = {row['id']: row['split'] for row in lineage['manifest']}
            if any(declared.get(s.record.content_id) != s.record.to_data()['split'] for s in samples):
                return False
        if training_samples is not None:
            training_samples = tuple(training_samples)
            audit = audit_contamination(training_samples, samples,
                     family_holdout=report['contamination']['family_holdout_required'],
                     lineage=report['contamination'].get('lineage', {}).get('manifest'))
            if audit != report['contamination'] or not audit['clean']:
                return False
            if report['training_ids'] != sorted(s.record.task.content_id for s in training_samples):
                return False
        if report['external_count'] != sum(s.record.to_data()['origin']=='external' for s in samples):
            return False
        tasks = {s.record.task.content_id: s.record.task for s in samples}
        if (report['total'] != len(samples) or len(tasks) != len(samples)
                or report['evaluation_ids'] != [r['task_id'] for r in report['results']]
                or set(report['evaluation_ids']) != set(tasks)):
            return False
        for row in report['results']:
            verification = verify_candidate(tasks[row['task_id']], row['candidate']).to_data()
            if row['verification'] != verification or row['valid'] != verification['valid']:
                return False
        successes = sum(r['valid'] for r in report['results'])
        return (report['successes'] == successes and report['accuracy'] == successes/len(samples)
                and report['accuracy_wilson_95'] == _wilson(successes, len(samples))
                and report['verifier_version'] == VERIFIER_VERSION)
    except (ValueError, KeyError, TypeError, ZeroDivisionError):
        return False


def compare_evaluations(baseline, candidate):
    keys = ('evaluation_ids', 'benchmark', 'training_ids', 'verifier_version', 'contamination')
    if any(baseline[k] != candidate[k] for k in keys):
        raise ValueError('Avaliações devem usar o mesmo benchmark e treino')
    better = sum(not a['valid'] and b['valid'] for a,b in zip(baseline['results'], candidate['results']))
    worse = sum(a['valid'] and not b['valid'] for a,b in zip(baseline['results'], candidate['results']))
    n = better+worse
    # Exact paired sign test on discordant outcomes.
    p = min(1., 2*sum(math.comb(n,k) for k in range(min(better,worse)+1))/2**n) if n else 1.
    gain = candidate['accuracy']-baseline['accuracy']
    return {'accuracy_gain': gain, 'improved_examples': better, 'regressed_examples': worse,
            'paired_exact_p_value': p, 'positive_gain_observed': gain > 0,
            'significant_at_0_05': p < .05, 'negative_or_zero_result_retained': gain <= 0,
            'baseline_evaluation_id': baseline['evaluation_id'], 'candidate_evaluation_id': candidate['evaluation_id']}
