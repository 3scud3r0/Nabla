"""Spatially flat FLRW perfect-fluid solutions in geometrized units c=G=1.

This is a bounded analytic Einstein-equation profile, not numerical relativity.
Stress-energy uses pressure p=w*rho, zero cosmological constant, t>0.
"""
from __future__ import annotations
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class FlatFLRW:
    equation_of_state: float = 0.0
    scale_at_unit_time: float = 1.0

    def __post_init__(self):
        if (not math.isfinite(self.equation_of_state)
                or not -1 < self.equation_of_state <= 1):
            raise ValueError("Supported perfect fluids require -1 < w <= 1")
        if not math.isfinite(self.scale_at_unit_time) or self.scale_at_unit_time <= 0:
            raise ValueError("Positive finite scale normalization required")

    @property
    def exponent(self):
        return 2 / (3 * (1 + self.equation_of_state))

    def _time(self, t):
        if isinstance(t, bool) or not math.isfinite(t) or t <= 0:
            raise ValueError("Cosmic time must be positive and finite")
        return float(t)

    def scale(self, t):
        return self.scale_at_unit_time * self._time(t) ** self.exponent

    def hubble(self, t):
        return self.exponent / self._time(t)

    def density(self, t):
        return 3 * self.hubble(t) ** 2 / (8 * math.pi)

    def pressure(self, t):
        return self.equation_of_state * self.density(t)

    def ricci_scalar(self, t):
        t = self._time(t)
        n = self.exponent
        return 6 * n * (2 * n - 1) / t ** 2

    def metric_diagonal(self, t):
        a2 = self.scale(t) ** 2
        return (-1.0, a2, a2, a2)

    def christoffel(self, t):
        """Gamma[upper][lower][lower] in comoving Cartesian coordinates."""
        a, h = self.scale(t), self.hubble(t)
        gamma = [[[0.0] * 4 for _ in range(4)] for _ in range(4)]
        for i in range(1, 4):
            gamma[0][i][i] = a * a * h
            gamma[i][0][i] = gamma[i][i][0] = h
        return tuple(tuple(tuple(row) for row in plane) for plane in gamma)

    def geodesic_acceleration(self, t, tangent):
        if len(tangent) != 4 or any(not math.isfinite(v) for v in tangent):
            raise ValueError("Four finite tangent components required")
        gamma = self.christoffel(t)
        return tuple(-sum(gamma[m][i][j] * tangent[i] * tangent[j]
                          for i in range(4) for j in range(4)) for m in range(4))

    def field_residuals(self, t):
        t = self._time(t)
        n, h, rho, p = self.exponent, self.hubble(t), self.density(t), self.pressure(t)
        hdot = -n / t ** 2
        rhodot = -2 * rho / t
        return {"friedmann": 3 * h * h - 8 * math.pi * rho,
                "acceleration": 2 * hdot + 3 * h * h + 8 * math.pi * p,
                "continuity": rhodot + 3 * h * (rho + p),
                "trace": self.ricci_scalar(t) - 8 * math.pi * (rho - 3 * p)}

    def radial_null_displacement(self, start, end):
        """Comoving light travel distance integral(dt/a); no observational fit."""
        start, end = self._time(start), self._time(end)
        if end < start:
            raise ValueError("End must not precede start")
        n, a = self.exponent, self.scale_at_unit_time
        if abs(n - 1) < 1e-14:
            return math.log(end / start) / a
        return (end ** (1 - n) - start ** (1 - n)) / ((1 - n) * a)
