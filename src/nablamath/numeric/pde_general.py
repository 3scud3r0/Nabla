"""Bounded 1D Poisson solver: -u''=f with Dirichlet endpoint values.

Other boundary kinds have contracts but are deliberately rejected by this solver.
No claim of a general PDE engine or physical validation is made.
"""
from dataclasses import dataclass
import math
from ..worlds.boundary_conditions import BoundaryCondition


def poisson_cartesian(shape,forcing,lengths=None):
    """Sparse second-order -Delta u=f, zero Dirichlet rectangle/cuboid."""
    import numpy as np
    from scipy.sparse import diags,eye,kron
    from scipy.sparse.linalg import spsolve
    from ..math._structured import numeric_array
    if not isinstance(shape,list) or not 1<=len(shape)<=3 or any(type(n) is not int or not 2<=n<=256 for n in shape) or math.prod(shape)>100000:raise ValueError('Cartesian grid budget exceeded')
    lengths=[1.]*len(shape) if lengths is None else lengths
    if len(lengths)!=len(shape) or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in lengths):raise ValueError('Positive Cartesian lengths required')
    array=numeric_array(forcing,maximum=100000)
    if array.shape!=tuple(shape):raise ValueError('Forcing shape differs from interior grid')
    operator=None
    for axis,(size,length) in enumerate(zip(shape,lengths)):
        h=length/(size+1);block=diags([-np.ones(size-1),2*np.ones(size),-np.ones(size-1)],[-1,0,1])/h**2
        term=None
        for i,n in enumerate(shape):term=(block if i==axis else eye(n)) if term is None else kron(term,block if i==axis else eye(n),format='csr')
        operator=term if operator is None else operator+term
    rhs=array.ravel();solution=spsolve(operator,rhs)
    if not np.isfinite(solution).all():raise ArithmeticError('Poisson solution is nonfinite')
    return {'interior_values':solution.reshape(shape).tolist(),'residual_inf':float(np.linalg.norm(operator@solution-rhs,np.inf)),
            'spacing':[l/(n+1) for n,l in zip(shape,lengths)],'boundary':'homogeneous Dirichlet',
            'scope':'Uniform Cartesian 1D/2D/3D second-order differences; discrete residual is not continuum error.'}


def poisson_fem_1d(nodes,forcing,left,right):
    """Piecewise-linear Galerkin FEM with Dirichlet/Neumann/Robin endpoints.

    Neumann values mean outward derivative; Robin means du/dn + alpha*u=value.
    """
    import numpy as np
    from scipy.sparse import lil_matrix
    from scipy.sparse.linalg import spsolve
    from ..math._structured import expression,sympy,numeric_array
    x=numeric_array(nodes,ndim=1,maximum=10000)
    if len(x)<2 or np.any(np.diff(x)<=0):raise ValueError('Strictly increasing FEM nodes required')
    f,(symbol,)=expression(forcing,['x']);sp=sympy();n=len(x);a=lil_matrix((n,n));rhs=np.zeros(n)
    q,w=np.polynomial.legendre.leggauss(4)
    for i,h in enumerate(np.diff(x)):
        a[i,i]+=1/h;a[i+1,i+1]+=1/h;a[i,i+1]-=1/h;a[i+1,i]-=1/h
        for t,weight in zip(q,w):
            value=float(f.subs(symbol,(x[i]+x[i+1])/2+h*t/2));rhs[i]+=h*weight/2*value*(1-t)/2;rhs[i+1]+=h*weight/2*value*(1+t)/2
    anchored=False
    for index,bc in ((0,left),(n-1,right)):
        if not isinstance(bc,dict) or set(bc)-{'kind','value','alpha'} or 'value' not in bc or not math.isfinite(bc['value']):raise ValueError('Closed finite boundary data required')
        kind=bc.get('kind')
        if kind=='dirichlet':
            column=a[:,index].toarray().ravel();rhs-=column*bc['value'];a[:,index]=0;a[index,:]=0;a[index,index]=1;rhs[index]=bc['value'];anchored=True
        elif kind=='neumann':rhs[index]+=bc['value']
        elif kind=='robin':
            alpha=bc.get('alpha',0.)
            if not math.isfinite(alpha) or alpha<0:raise ValueError('Nonnegative Robin coefficient required')
            a[index,index]+=alpha;rhs[index]+=bc['value'];anchored|=alpha>0
        else:raise ValueError('Unknown boundary kind')
    if not anchored:raise ValueError('Pure Neumann problem needs compatibility and a separate gauge; provide a Dirichlet or positive Robin anchor')
    matrix=a.tocsr();u=spsolve(matrix,rhs)
    if not np.isfinite(u).all():raise ArithmeticError('FEM solution is nonfinite')
    slopes=np.diff(u)/np.diff(x);jumps=np.r_[0,np.diff(slopes),0]
    return {'nodes':x.tolist(),'values':u.tolist(),'residual_inf':float(np.linalg.norm(matrix@u-rhs,np.inf)),
            'interior_flux_jumps':jumps.tolist(),'scope':'1D linear Galerkin FEM with Gaussian load quadrature; flux jumps are an estimator, not a certified bound.'}


def adaptive_poisson_1d(forcing,left,right,*,length=1.,tolerance=1e-3,max_nodes=1025):
    import numpy as np
    if not math.isfinite(length) or length<=0 or not 0<tolerance<1 or type(max_nodes) is not int or not 5<=max_nodes<=10000:raise ValueError('Invalid adaptive FEM budget')
    nodes=np.linspace(0,length,5)
    while True:
        solution=poisson_fem_1d(nodes.tolist(),forcing,left,right);jumps=np.abs(solution['interior_flux_jumps']);h=np.diff(nodes)
        indicators=np.sqrt(h)*(jumps[:-1]+jumps[1:])/2;estimate=float(np.linalg.norm(indicators))
        if estimate<=tolerance:return {**solution,'flux_estimator':estimate,'requested_estimator_reached':True}
        marked=indicators>=.5*max(indicators);midpoints=(nodes[:-1]+nodes[1:])/2
        additions=midpoints[marked]
        if len(nodes)+len(additions)>max_nodes:return {**solution,'flux_estimator':estimate,'requested_estimator_reached':False,'reason':'node budget exhausted'}
        nodes=np.sort(np.r_[nodes,additions])


@dataclass(frozen=True)
class Poisson1D:
    length: float
    left: BoundaryCondition
    right: BoundaryCondition

    def __post_init__(self):
        if isinstance(self.length, bool) or not math.isfinite(self.length) or not 1e-9 <= self.length <= 1e9:
            raise ValueError('Finite bounded positive length required')
        if not all(isinstance(b, BoundaryCondition) for b in (self.left, self.right)):
            raise ValueError('Boundary contracts required')
        if any(b.kind != 'dirichlet' for b in (self.left, self.right)):
            raise ValueError('This solver supports Dirichlet endpoints only')

    def to_data(self):
        return {'schema_version': 1, 'equation': '-u_xx=f', 'length': self.length,
                'left': self.left.to_data(), 'right': self.right.to_data(),
                'coordinates': 'caller-consistent units'}


def solve_poisson_1d(problem, forcing, *, cells=32):
    """Second-order central differences and O(n) Thomas elimination."""
    if not isinstance(problem, Poisson1D) or type(cells) is not int or not 2 <= cells <= 100000:
        raise ValueError('Poisson1D and 2..100000 cells required')
    h = problem.length/cells
    xs = tuple(i*h for i in range(cells+1))
    rhs = []
    for x in xs[1:-1]:
        value = forcing(x)
        if isinstance(value, bool) or not math.isfinite(value):
            raise ValueError('Nonfinite forcing')
        rhs.append(float(value)*h*h)
    rhs[0] += problem.left.value
    rhs[-1] += problem.right.value
    diagonal = [2.0]*(cells-1)
    for i in range(1, cells-1):
        factor = -1.0/diagonal[i-1]
        diagonal[i] += factor
        rhs[i] -= factor*rhs[i-1]
    interior = [0.0]*(cells-1)
    interior[-1] = rhs[-1]/diagonal[-1]
    for i in range(cells-3, -1, -1):
        interior[i] = (rhs[i]+interior[i+1])/diagonal[i]
    values = (problem.left.value, *interior, problem.right.value)
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Solution overflow')
    return {'schema_version': 1, 'problem': problem.to_data(), 'positions': xs,
            'values': values, 'cells': cells, 'method': 'central_difference_thomas',
            'experimental_validation': False}
