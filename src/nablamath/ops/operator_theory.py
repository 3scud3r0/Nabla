"""Finite real rational operators: adjoints, norms, positivity and resolvents (47)."""
from ._area_utils import matrix as _matrix,scalar,calculate as _calculate
from ..math.linear_algebra.matrices import Matrix,identity
from ..math.linear_algebra.solvers import characteristic_polynomial


def operator_theory(matrix, *, parameter=None):
    rows = _matrix(matrix,square=True);a = Matrix(tuple(tuple(row) for row in rows));n = len(rows)
    adjoint = a.transpose();symmetric = a==adjoint
    minors = [Matrix(tuple(tuple(row[:k]) for row in rows[:k])).determinant() for k in range(1,n+1)] if symmetric else None
    result = {'adjoint':adjoint.rows,'self_adjoint':symmetric,'normal':a@adjoint==adjoint@a,
              'orthogonal_projection':symmetric and a@a==a,
              'positive_definite':all(v>0 for v in minors) if symmetric else None,
              'norm_one':max(sum(abs(rows[i][j]) for i in range(n)) for j in range(n)),
              'norm_infinity':max(sum(abs(v) for v in row) for row in rows),
              'hilbert_schmidt_squared':sum(v*v for row in rows for v in row),
              'characteristic_coefficients':characteristic_polynomial(a),
              'gershgorin_discs':[[rows[i][i],sum(abs(rows[i][j]) for j in range(n) if j!=i)] for i in range(n)],
              'scope':'Finite-dimensional operators; induced 1/infinity norms, not an infinite-dimensional spectral theorem.'}
    if parameter is not None:
        value = scalar(parameter);unit = identity(n)
        resolvent = Matrix(tuple(tuple(value*unit.rows[i][j]-rows[i][j] for j in range(n)) for i in range(n))).inverse()
        result['resolvent'] = resolvent.rows
    return result


def calculate(**arguments):return _calculate('operator_theory',**arguments)
