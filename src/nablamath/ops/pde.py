"""Heat diffusion with explicit stability checks and analytic reference."""
from ..worlds.model_spec import HeatModelSpec
from ..worlds.pde import solve_heat

__all__ = ['HeatModelSpec', 'solve_heat']
