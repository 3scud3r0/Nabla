"""No-slip plane-channel Stokes profile with a convergent finite-difference solve.

Unidirectional steady incompressible flow reduces Navier-Stokes to nu*u''=-g.
No claim of general two-dimensional nonperiodic pressure projection is made.
"""
import math


def channel_velocity(*, height, viscosity, forcing, cells):
    if (any(not math.isfinite(v) for v in (height, viscosity, forcing))
            or height <= 0 or viscosity <= 0
            or type(cells) is not int or not 2 <= cells <= 100_000):
        raise ValueError("Positive geometry/viscosity and bounded grid required")
    dy = height / cells
    # Thomas elimination for -u[i-1]+2u[i]-u[i+1]=g*dy²/nu.
    count = cells - 1
    diagonal = [2.0] * count
    rhs = [forcing * dy * dy / viscosity] * count
    for i in range(1, count):
        multiplier = -1 / diagonal[i - 1]
        diagonal[i] += multiplier
        rhs[i] -= multiplier * rhs[i - 1]
    interior = [0.0] * count
    interior[-1] = rhs[-1] / diagonal[-1]
    for i in range(count - 2, -1, -1):
        interior[i] = (rhs[i] + interior[i + 1]) / diagonal[i]
    return {"y": tuple(i * dy for i in range(cells + 1)),
            "velocity": (0.0, *interior, 0.0), "boundary": "stationary-no-slip",
            "units": "caller-consistent", "scope": "steady-unidirectional-Stokes"}
