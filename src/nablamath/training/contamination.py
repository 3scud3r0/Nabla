"""Local semantic and constructor leakage checks with explicit audit scope."""
from ..datasets.semantic_fingerprint import semantic_fingerprint


def audit_contamination(training, evaluation, *, family_holdout=True):
    training, evaluation = tuple(training), tuple(evaluation)
    train_semantics = {semantic_fingerprint(s.record) for s in training}
    eval_semantics = [semantic_fingerprint(s.record) for s in evaluation]
    duplicates = sorted({key for key in eval_semantics if eval_semantics.count(key) > 1})
    overlap = sorted(train_semantics & set(eval_semantics))
    families = sorted({s.record.task.family for s in training} & {s.record.task.family for s in evaluation})
    wrong_split = [s.record.content_id for s in training if s.record.to_data()['split'] != 'train']
    wrong_split += [s.record.content_id for s in evaluation if s.record.to_data()['split'] not in {'validation','test'}]
    return {'clean': not overlap and not duplicates and not wrong_split and (not family_holdout or not families),
            'semantic_overlap': overlap, 'evaluation_duplicates': duplicates, 'family_overlap': families,
            'wrong_split': wrong_split, 'family_holdout_required': family_holdout,
            'scope': 'local normalized tasks and declared families; external corpora not inspected'}
