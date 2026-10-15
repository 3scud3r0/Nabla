"""Retrain modality ablations on identical training/evaluation cohorts."""
from ..datasets.multimodal import INPUT_MODALITIES
from .baselines import fit_nearest_neighbor
from .evaluation import evaluate, compare_evaluations


def run_ablations(training, evaluation, *, benchmark_name, trainer=fit_nearest_neighbor,
                  variants=None, family_holdout=True, lineage=None):
    training, evaluation = tuple(training), tuple(evaluation)
    lineage = tuple(lineage) if lineage is not None else None
    variants = variants or {'all': INPUT_MODALITIES, 'text_only': ('text',),
                            'without_diagram': ('text','equation'), 'diagram_only': ('diagram',)}
    if 'all' not in variants or not variants:
        raise ValueError('Ablation requer baseline all')
    reports = {}
    for name, modalities in variants.items():
        model = trainer(training, modalities=tuple(modalities))
        reports[name] = evaluate(model, evaluation, training_samples=training,
                                  benchmark_name=benchmark_name, modalities=tuple(modalities),
                                  family_holdout=family_holdout, lineage=lineage)
    comparisons = {name: compare_evaluations(reports['all'], report) for name,report in reports.items() if name != 'all'}
    return {'schema_version': 1, 'reports': reports, 'comparisons_to_all': comparisons,
            'selection_performed': False, 'limitations': 'Repeated holdout use is for reporting; do not tune on these results.'}
