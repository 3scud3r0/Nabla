"""Finite-dimensional rational Lie algebras, Jacobi, center and Killing form (17)."""
from fractions import Fraction
from ._area_utils import vector,nullspace,rref,calculate as _calculate
from ..math.linear_algebra.matrices import Matrix


def lie_algebra(structure, *, left=None, right=None):
    if not isinstance(structure,list) or not 1<=len(structure)<=6:
        raise ValueError('Lie dimension must be 1–6')
    n = len(structure)
    if any(not isinstance(layer,list) or len(layer)!=n for layer in structure):raise ValueError('Invalid structure constants')
    c = [[vector(row,maximum=n) for row in layer] for layer in structure]
    if any(len(row)!=n for layer in c for row in layer):raise ValueError('Invalid structure constants')
    if any(c[i][j][k]!=-c[j][i][k] for i in range(n) for j in range(n) for k in range(n)):
        raise ValueError('Bracket must be antisymmetric')
    for i in range(n):
        for j in range(n):
            for k in range(n):
                for out in range(n):
                    value = sum(c[j][k][m]*c[i][m][out]+c[k][i][m]*c[j][m][out]+c[i][j][m]*c[k][m][out] for m in range(n))
                    if value:raise ValueError('Structure constants violate Jacobi')
    killing = [[sum(c[i][b][a]*c[j][a][b] for a in range(n) for b in range(n)) for j in range(n)] for i in range(n)]
    central_constraints = [[c[i][j][k] for i in range(n)] for j in range(n) for k in range(n)]
    derived_columns = [[c[i][j][k] for i in range(n) for j in range(n)] for k in range(n)]
    result = {'dimension':n,'jacobi_verified':True,'killing_form':killing,
              'center_basis':nullspace(central_constraints,n),'derived_dimension':len(rref(derived_columns)[1]),
              'semisimple_over_characteristic_zero':bool(Matrix(tuple(tuple(row) for row in killing)).determinant())}
    if (left is None)!=(right is None):raise ValueError('Bracket requires both vectors')
    if left is not None:
        a,b = vector(left,maximum=n),vector(right,maximum=n)
        if len(a)!=n or len(b)!=n:raise ValueError('Bracket vector dimensions differ')
        result['bracket'] = [sum((a[i]*b[j]*c[i][j][k] for i in range(n) for j in range(n)),Fraction(0)) for k in range(n)]
    return result


def calculate(**arguments):return _calculate('lie_algebra',**arguments)
