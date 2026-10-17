"""Linear bundle cocycles on an explicitly supplied finite chart nerve."""
from itertools import combinations
from .._structured import rational_matrix, sympy, data


def verify_bundle(charts, transitions, triples=()):
    sp=sympy()
    if not isinstance(charts,list) or not 1<=len(charts)<=32 or len(set(charts))!=len(charts) or any(type(v) is not str for v in charts):raise ValueError('Distinct chart labels required')
    matrices={}
    for edge in transitions:
        if set(edge)!={'from','to','matrix'} or edge['from'] not in charts or edge['to'] not in charts:raise ValueError('Invalid chart transition')
        key=(edge['from'],edge['to'])
        if key in matrices:raise ValueError('Duplicate transition')
        m=rational_matrix(edge['matrix'],maximum=16)
        if m.rows!=m.cols or m.det()==0:raise ValueError('Transition must be invertible')
        matrices[key]=m
    if not matrices:raise ValueError('At least one transition required')
    rank=next(iter(matrices.values())).rows
    if any(m.shape!=(rank,rank) for m in matrices.values()):raise ValueError('Bundle ranks differ')
    for (a,b),m in matrices.items():
        if a==b and m!=sp.eye(rank):raise ValueError('Identity chart transition required')
        if (b,a) in matrices and matrices[b,a]*m!=sp.eye(rank):raise ValueError('Inverse transition mismatch')
    for triple in triples:
        if len(triple)!=3 or any(v not in charts for v in triple):raise ValueError('Invalid triple overlap')
        a,b,c=triple
        if any(key not in matrices for key in ((a,b),(b,c),(a,c))):raise ValueError('Missing transition on declared triple')
        if matrices[b,c]*matrices[a,b]!=matrices[a,c]:raise ValueError('Cocycle condition failed')
    return {'rank':rank,'declared_triples_checked':len(triples),'compatible':True,
            'scope':'Constant GL(Q) transitions on supplied overlaps; geometric cover validity is an explicit hypothesis.'}


def compatible_sections(transitions, sections):
    for edge in transitions:
        a,b=edge['from'],edge['to'];m=rational_matrix(edge['matrix'])
        if a not in sections or b not in sections:raise ValueError('A section on every transition endpoint is required')
        left=rational_matrix([[v] for v in sections[a]]);right=rational_matrix([[v] for v in sections[b]])
        if m*left!=right:return False
    return True


def gauge_connection(coordinates,connection,gauge):
    """A' = g^-1 A g + g^-1 dg, with symbolic matrices, chart-local only."""
    from .._structured import expression,names
    sp=sympy();coordinates=names(coordinates,8)
    g=sp.Matrix([[expression(v,coordinates)[0] for v in row] for row in gauge]);n=g.rows
    if not 1<=n<=8 or g.cols!=n or len(connection)!=len(coordinates) or sp.simplify(g.det())==0:raise ValueError('Invalid local gauge/connection')
    inverse=g.inv();output=[]
    for name,raw in zip(coordinates,connection):
        a=sp.Matrix([[expression(v,coordinates)[0] for v in row] for row in raw])
        if a.shape!=(n,n):raise ValueError('Connection rank mismatch')
        output.append((inverse*a*g+inverse*g.diff(sp.Symbol(name))).applyfunc(sp.simplify))
    return {'connection':data(output),'invertible_where':str(g.det())+' != 0'}


def parallel_transport(coordinates,connection,path,initial,duration=1.,steps=100):
    from .._structured import expression,sympy,numeric_array
    from scipy.integrate import solve_ivp
    import numpy as np
    sp=sympy();n=len(coordinates)
    if len(connection)!=n or len(path)!=n or type(steps) is not int or not 1<=steps<=10000 or not 0<duration<=10000:raise ValueError('Invalid connection/path data')
    curve=[expression(v,['t'])[0] for v in path];t=sp.Symbol('t');derivatives=[sp.diff(v,t) for v in curve]
    symbols=tuple(map(sp.Symbol,coordinates));rank=len(initial)
    matrices=[sp.Matrix([[expression(v,coordinates)[0] for v in row] for row in raw]) for raw in connection]
    if not 1<=rank<=16 or any(a.shape!=(rank,rank) for a in matrices):raise ValueError('Connection rank differs from transported vector')
    substitution=dict(zip(symbols,curve));operator=sum((d*a.subs(substitution,simultaneous=True) for d,a in zip(derivatives,matrices)),sp.zeros(rank))
    def rhs(time,y):return -np.array(operator.subs(t,time),dtype=float)@y
    solution=solve_ivp(rhs,(0,duration),numeric_array(initial,ndim=1),t_eval=np.linspace(0,duration,steps+1),rtol=1e-9,atol=1e-11)
    if not solution.success or not np.isfinite(solution.y).all():raise ArithmeticError('Parallel transport failed')
    return {'times':solution.t.tolist(),'vectors':solution.y.T.tolist(),'convention':'dV/dt + A_i(x(t))*dx_i/dt*V=0','scope':'Numerical transport in one supplied chart.'}
