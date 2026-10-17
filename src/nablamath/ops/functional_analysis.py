"""Exact finite weighted-Hilbert projection, Bessel and Pythagoras identities (46)."""
from ._area_utils import matrix,vector,calculate as _calculate
from ..math.linear_algebra.matrices import Matrix


def functional_analysis(basis, target, *, weights=None):
    basis,target = matrix(basis),vector(target,maximum=32);n = len(target)
    if len(basis[0])!=n:raise ValueError('Basis and target dimensions differ')
    weights = vector(weights,maximum=32) if weights is not None else [1]*n
    if len(weights)!=n or any(w<=0 for w in weights):raise ValueError('Hilbert weights must be positive')
    inner = lambda a,b:sum(w*x*y for w,x,y in zip(weights,a,b))
    gram = [[inner(a,b) for b in basis] for a in basis]
    rhs = [inner(a,target) for a in basis]
    coefficients = [row[0] for row in (Matrix(tuple(tuple(row) for row in gram)).inverse()@Matrix(tuple((v,) for v in rhs))).rows]
    projection = [sum(coefficient*row[i] for coefficient,row in zip(coefficients,basis)) for i in range(n)]
    residual = [a-b for a,b in zip(target,projection)]
    orthogonality = [inner(row,residual) for row in basis]
    return {'coefficients':coefficients,'projection':projection,'residual':residual,'gram':gram,
            'orthogonality':orthogonality,'norm_squared':inner(target,target),
            'projection_norm_squared':inner(projection,projection),'residual_norm_squared':inner(residual,residual),
            'pythagoras_verified':inner(target,target)==inner(projection,projection)+inner(residual,residual),
            'scope':'Finite-dimensional rational Hilbert space and independent basis; no infinite-dimensional convergence claim.'}


def calculate(**arguments):return _calculate('functional_analysis',**arguments)
