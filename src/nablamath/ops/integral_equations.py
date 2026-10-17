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


def numerical_integral_equation(kernel,rhs,*,lower=0.,upper=1.,coupling=1.,nodes=32,kind='fredholm',regularization=0.):
    import numpy as np
    from ..math._structured import expression,sympy
    if type(nodes) is not int or not 4<=nodes<=256 or not lower<upper or not np.isfinite([lower,upper,coupling,regularization]).all() or regularization<0:raise ValueError('Invalid quadrature equation parameters')
    sp=sympy();k,(x,t)=expression(kernel,['x','t']);f,(z,)=expression(rhs,['x'])
    if kind=='fredholm':
        points,weights=np.polynomial.legendre.leggauss(nodes);points=(lower+upper)/2+(upper-lower)*points/2;weights*=((upper-lower)/2)
        quadrature=np.broadcast_to(weights,(nodes,nodes)).copy()
    elif kind=='volterra':
        points=np.linspace(lower,upper,nodes);h=(upper-lower)/(nodes-1);quadrature=np.zeros((nodes,nodes))
        for i in range(1,nodes):quadrature[i,:i+1]=h;quadrature[i,0]=h/2;quadrature[i,i]=h/2
    else:raise ValueError('Unsupported integral equation kind')
    values=np.array([[float(k.subs({x:float(a),t:float(b)})) for b in points] for a in points]);b=np.array([float(f.subs(z,float(a))) for a in points])
    system=np.eye(nodes)-coupling*values*quadrature
    if not np.isfinite(system).all() or not np.isfinite(b).all():raise ValueError('Kernel or rhs undefined at quadrature nodes')
    solution=np.linalg.solve(system.T@system+regularization*np.eye(nodes),system.T@b) if regularization else np.linalg.solve(system,b)
    return {'points':points.tolist(),'values':solution.tolist(),'residual_inf':float(np.linalg.norm(system@solution-b,np.inf)),
            'condition_number':float(np.linalg.cond(system)),'regularization':regularization,
            'scope':'Second-kind Nystrom discretization; optional Tikhonov regularization. Residual is discrete, not a continuum error bound.'}
