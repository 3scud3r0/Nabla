"""Exact weighted-graph Dirichlet problems and harmonic energy (31)."""
from ._area_utils import matrix,scalar,calculate as _calculate
from ..math.linear_algebra.matrices import Matrix


def potential_theory(conductance, boundary):
    c = matrix(conductance,square=True);n = len(c)
    if any(c[i][j]<0 or c[i][j]!=c[j][i] or (i==j and c[i][j]) for i in range(n) for j in range(n)):
        raise ValueError('Conductances must be symmetric, nonnegative and loop-free')
    if not isinstance(boundary,dict) or not boundary:
        raise ValueError('Dirichlet boundary values are required')
    fixed = {}
    for key,value in boundary.items():
        if not isinstance(key,str) or not key.isdecimal() or str(int(key))!=key or not 0<=int(key)<n:
            raise ValueError('Boundary keys must be canonical vertex index strings')
        fixed[int(key)] = scalar(value)
    seen = set(fixed);stack = list(seen)
    while stack:
        i = stack.pop()
        for j in range(n):
            if c[i][j] and j not in seen:seen.add(j);stack.append(j)
    if len(seen)!=n:raise ValueError('Every connected component requires a boundary anchor')
    free = [i for i in range(n) if i not in fixed];values = [fixed.get(i,0) for i in range(n)]
    if free:
        laplacian = [[sum(c[i]) if i==j else -c[i][j] for j in free] for i in free]
        rhs = [sum(c[i][j]*v for j,v in fixed.items()) for i in free]
        solution = Matrix(tuple(tuple(row) for row in laplacian)).inverse()@Matrix(tuple((v,) for v in rhs))
        for i,row in zip(free,solution.rows):values[i] = row[0]
    residuals = [sum(c[i][j]*(values[i]-values[j]) for j in range(n)) for i in free]
    energy = sum(c[i][j]*(values[i]-values[j])**2 for i in range(n) for j in range(i+1,n))
    return {'values':values,'interior_residuals':residuals,'energy':energy,
            'maximum_principle_verified':all(min(fixed.values())<=v<=max(fixed.values()) for v in values),
            'scope':'Finite resistor/graph potential model; not a continuum boundary regularity proof.'}


def calculate(**arguments):return _calculate('potential_theory',**arguments)


def green_function(distance,dimension=3):
    import math
    if type(distance) not in (int,float) or not math.isfinite(distance) or distance<=0:raise ValueError('Positive finite separation required')
    if dimension==3:return {'value':1/(4*math.pi*distance),'operator':'-Laplacian','domain':'free space R^3'}
    if dimension==2:return {'value':-math.log(distance)/(2*math.pi),'operator':'-Laplacian','domain':'free space R^2; logarithmic reference scale one'}
    raise ValueError('Green function supports dimensions two and three')


def boundary_single_layer(vertices,values):
    """Constant-panel collocation for the 2D Laplace single-layer potential."""
    import numpy as np
    from ..math._structured import numeric_array
    p=numeric_array(vertices,ndim=2,maximum=512);f=numeric_array(values,ndim=1,maximum=256)
    if p.shape[1]!=2 or not 3<=len(p)<=256 or len(f)!=len(p):raise ValueError('Closed polygon and panel boundary values required')
    end=np.roll(p,-1,axis=0);length=np.linalg.norm(end-p,axis=1)
    if np.any(length<=1e-12):raise ValueError('Degenerate boundary panel')
    centers=(p+end)/2;distance=np.linalg.norm(centers[:,None,:]-centers[None,:,:],axis=2)
    if np.any(distance[np.triu_indices(len(p),1)]<=1e-12):raise ValueError('Coincident collocation points')
    np.fill_diagonal(distance,1)
    matrix=-np.log(distance)*length[None,:]/(2*np.pi)
    np.fill_diagonal(matrix,length*(1-np.log(length/2))/(2*np.pi))
    density=np.linalg.solve(matrix,f)
    return {'density':density.tolist(),'centers':centers.tolist(),'residual_inf':float(np.linalg.norm(matrix@density-f,np.inf)),
            'scope':'Polygonal midpoint collocation; exact self-panel logarithmic integral, approximate off-diagonal quadrature, no certified error bound.'}
