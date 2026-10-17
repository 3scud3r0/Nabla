"""Exact linear algebra from Nabla's existing rational engine."""
from ..math.linear_algebra import (Matrix, identity, solve_linear, lu_decomposition,
                                   orthogonal_basis, condition_number_inf, characteristic_polynomial)
from ..math.statistics.multivariate import exact_least_squares as least_squares

__all__ = ['Matrix', 'identity', 'solve_linear', 'lu_decomposition', 'orthogonal_basis',
           'condition_number_inf', 'characteristic_polynomial', 'least_squares']
