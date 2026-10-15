"""The shared bounded Euler/RK4 kernels and explicit diffusion stability rule."""
from ...math.equations.ode import euler_step, rk4_step, integrate
import math


def diffusion_ratio(diffusivity, dt, dx):
    if any(isinstance(v, bool) or not math.isfinite(v) or v <= 0 for v in (diffusivity, dt, dx)):
        raise ValueError('Parâmetros de passo inválidos')
    ratio = diffusivity*dt/dx**2
    if ratio > 0.5:
        raise ValueError('FTCS instável: diffusivity*dt/dx^2 deve ser <= 0.5')
    return ratio

from .adaptive import integrate_adaptive
