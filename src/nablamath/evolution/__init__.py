"""Controlled numerical-policy selection; no code rewriting or general RSI claims."""
from .evaluator import SolverPolicy, evaluate_proposal, select_on_calibration

__all__ = ["SolverPolicy", "evaluate_proposal", "select_on_calibration"]
