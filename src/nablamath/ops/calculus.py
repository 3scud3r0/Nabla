"""Calculus adapters preserving domain checks and exact arithmetic."""
from ..math.calculus import derivative, primitive, definite_integral, limit, series
from ..math.analysis.quadrature import certified_polynomial_integral
from ..math.analysis.intervals import polynomial_range

__all__ = ['derivative', 'primitive', 'definite_integral', 'limit', 'series',
           'certified_polynomial_integral', 'polynomial_range']
