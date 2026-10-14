"""Bounded numerical experiments with analytic references and declared SI units."""
from .validation import ModelSpec, simulate, convergence_study

__all__ = ["ModelSpec", "simulate", "convergence_study"]

from .model_spec import HeatModelSpec
from .pde import solve_heat
from .convergence import heat_convergence
from .validation import compare_observations
__all__ += ["HeatModelSpec", "solve_heat", "heat_convergence", "compare_observations"]
