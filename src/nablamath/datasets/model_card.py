"""Evidence-bound dataset cards retain negative and missing evaluations."""
from collections import Counter
from ..verify.trace import VERIFIER_VERSION


def model_card(records, quality, *, evaluations=()):
    records = tuple(records)
    rows = [r.to_data() for r in records]
    evaluations = tuple(evaluations)
    if evaluations:
        from .multimodal import build_sample
        from ..training.evaluation import verify_evaluation
        samples = {r.task.content_id:build_sample(r) for r in records}
        for report in evaluations:
            try:
                evaluation = [samples[key] for key in report['evaluation_ids']]
                training = [samples[key] for key in report['training_ids']]
            except KeyError as exc:
                raise ValueError('Avaliação não pertence ao dataset') from exc
            if not verify_evaluation(report,evaluation,training_samples=training):
                raise ValueError('Avaliação não reproduzível na ficha')
    return {'schema_version': 1, 'count': len(rows), 'synthetic_count': sum(r['synthetic'] for r in rows),
            'licenses': sorted({r['license_id'] for r in rows}),
            'sources': sorted({r['provenance'] for r in rows}),
            'scopes': sorted({r['scope'] for r in rows}),
            'limitations': sorted({r['limitations'] for r in rows}),
            'splits': dict(Counter(r['split'] for r in rows)),
            'families': dict(Counter(r.task.family for r in records)),
            'verifier_version': VERIFIER_VERSION, 'quality': quality,
            'evaluations': list(evaluations),
            'training_gain': 'not_established' if not evaluations else 'see_evaluation_results',
            'formal_certificate_scope': 'associated statements; not automatic proofs of dataset tasks'}
