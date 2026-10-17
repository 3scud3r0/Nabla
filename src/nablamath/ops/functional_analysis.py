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


def orthogonal_series(coefficients,weights,tail_bound):
    from ._area_utils import scalar
    c,w=vector(coefficients,maximum=4096),vector(weights,maximum=4096);bound=scalar(tail_bound)
    if len(c)!=len(w) or any(v<=0 for v in w) or bound<0:raise ValueError('Positive basis norms and nonnegative tail bound required')
    norm=sum(a*a*b for a,b in zip(c,w))
    return {'truncation_norm_squared':norm,'full_norm_squared_interval':[norm,norm+bound*bound],
            'error_norm_upper_bound':bound,'conditional_on':'Orthogonality/completeness and the supplied certified tail bound; no inferred convergence.'}


def contraction_fixed_point(matrix,offset,tolerance=1e-10,max_iterations=10000):
    import numpy as np
    from ..math._structured import numeric_array
    a,b=numeric_array(matrix,ndim=2,maximum=4096),numeric_array(offset,ndim=1,maximum=64)
    if a.shape!=(len(b),len(b)) or not 0<tolerance<1 or type(max_iterations) is not int or not 1<=max_iterations<=100000:raise ValueError('Invalid fixed-point data')
    q=float(np.linalg.norm(a,np.inf))
    if q>=1:raise ValueError('Infinity-norm contraction was not established')
    current=np.zeros(len(b))
    for iteration in range(1,max_iterations+1):
        new=a@current+b;bound=q/(1-q)*float(np.linalg.norm(new-current,np.inf));current=new
        if bound<=tolerance:return {'fixed_point':current.tolist(),'iterations':iteration,'a_posteriori_bound':bound,'contraction_factor':q,'arithmetic':'floating_point; rounding not enclosed'}
    raise ArithmeticError('Contraction iteration budget exhausted')
