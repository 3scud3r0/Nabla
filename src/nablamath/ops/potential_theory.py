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
