"""Local semantic and constructor leakage checks with explicit audit scope."""
from collections import Counter
from ..datasets.semantic_fingerprint import semantic_fingerprint
from ..evaluation.lineage import audit_lineage


def audit_contamination(training, evaluation, *, family_holdout=True, lineage=None):
    training, evaluation = tuple(training), tuple(evaluation)
    train_semantics = {semantic_fingerprint(s.record) for s in training}
    eval_semantics = [semantic_fingerprint(s.record) for s in evaluation]
    duplicates = sorted(key for key, count in Counter(eval_semantics).items() if count > 1)
    overlap = sorted(train_semantics & set(eval_semantics))
    families = sorted({s.record.task.family for s in training} & {s.record.task.family for s in evaluation})
    wrong_split = [s.record.content_id for s in training if s.record.to_data()['split'] != 'train']
    wrong_split += [s.record.content_id for s in evaluation if s.record.to_data()['split'] not in {'validation','test'}]
    result = {'clean': not overlap and not duplicates and not wrong_split and (not family_holdout or not families),
            'semantic_overlap': overlap, 'evaluation_duplicates': duplicates, 'family_overlap': families,
            'wrong_split': wrong_split, 'family_holdout_required': family_holdout,
            'scope': 'local normalized tasks and declared families; external corpora not inspected'}
    if lineage is not None:
        report = audit_lineage(lineage)
        expected = {s.record.content_id: s.record.to_data()['split'] for s in training + evaluation}
        declared = {row['id']: row['split'] for row in report['manifest']}
        if declared != expected:
            raise ValueError('Lineage must cover exactly the supplied records and splits')
        result['lineage'] = report
        result['clean'] = result['clean'] and report['clean']
    return result
