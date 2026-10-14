"""Bounded numerical experiments with analytic references and declared SI units."""
from .validation import ModelSpec, simulate, convergence_study

__all__ = ["ModelSpec", "simulate", "convergence_study"]
