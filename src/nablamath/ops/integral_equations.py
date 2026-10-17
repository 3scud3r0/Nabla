"""Exact second-kind Fredholm equations with finite-rank polynomial kernels (45)."""
from ._area_utils import matrix,vector,scalar,calculate as _calculate
from ..math.linear_algebra.matrices import Matrix


def integral_equations(kernel, rhs, *, lower=0, upper=1, coupling=1):
    kernel,rhs = matrix(kernel,maximum=12),vector(rhs,maximum=12)
    a,b,lam = scalar(lower),scalar(upper),scalar(coupling)
    if not a<b:raise ValueError('Integral bounds must be increasing')
    degree = max(len(kernel),len(rhs));f = rhs+[0]*(degree-len(rhs))
    moments = [((b**(j+1)-a**(j+1))/(j+1)) for j in range(len(kernel[0])+degree)]
    operator = [[sum(kernel[i][j]*moments[j+k] for j in range(len(kernel[i]))) if i<len(kernel) else 0 for k in range(degree)] for i in range(degree)]
    system = [[int(i==j)-lam*operator[i][j] for j in range(degree)] for i in range(degree)]
    solution = Matrix(tuple(tuple(row) for row in system)).inverse()@Matrix(tuple((v,) for v in f))
    coefficients = [row[0] for row in solution.rows]
    residual = [coefficients[i]-f[i]-lam*sum(operator[i][j]*coefficients[j] for j in range(degree)) for i in range(degree)]
    return {'coefficients':coefficients,'residual_coefficients':residual,'unique_solution':True,
            'convention':'u(x) = rhs(x) + coupling * integral(kernel(x,t)*u(t), lower, upper); ascending powers',
            'scope':'Polynomial finite-rank Fredholm kernel; singular systems rejected, no general integral-equation solver claim.'}


def calculate(**arguments):return _calculate('integral_equations',**arguments)
