"""Training-only curricula, a small learning baseline and independent evaluations."""
from .registry import ModelRegistry
from .baselines import fit_nearest_neighbor
from .evaluation import evaluate, verify_evaluation, compare_evaluations
from .ablation import run_ablations

__all__ = ['ModelRegistry', 'fit_nearest_neighbor', 'evaluate', 'verify_evaluation', 'compare_evaluations', 'run_ablations']
