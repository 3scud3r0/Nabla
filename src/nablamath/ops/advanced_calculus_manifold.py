"""Local manifold calculus, with explicit chart/orientation contracts.

Symbolic inputs use Nabla's closed AST grammar. These algorithms operate on
smooth expressions on a single nonsingular chart; global atlas compatibility,
regularity at singularities and physical interpretation remain hypotheses.
"""
from itertools import combinations

from ..math._structured import expression, names, sympy
from ..math.geometry.differential_forms import (
    _form, exterior_derivative, wedge, pullback, integrate_box,
)
from .differential_geometry import symbolic_metric, covariant_derivative, geodesic
from .variational_calculus import euler_lagrange_fields, euler_lagrange_density


def _vector(coordinates, vector):
    coordinates = names(coordinates, 4)
    if len(vector) != len(coordinates):
        raise ValueError('One vector component per coordinate required')
    return coordinates, [expression(v, coordinates)[0] for v in vector]


def interior_product(coordinates, vector, components):
    """Contract a differential k-form with a vector in its first argument."""
    coordinates, values = _vector(coordinates, vector)
    _, form = _form(coordinates, components)
    sp = sympy()
    result = {}
    for indices, coefficient in form.items():
        for position, index in enumerate(indices):
            key = indices[:position] + indices[position + 1:]
            result[key] = result.get(key, 0) + (-1)**position * values[index] * coefficient
    return {','.join(map(str, k)): str(sp.simplify(v))
            for k, v in result.items() if sp.simplify(v) != 0}


def lie_bracket(coordinates, left, right):
    """[X,Y]^i = X^j partial_j Y^i - Y^j partial_j X^i."""
    coordinates, x = _vector(coordinates, left)
    _, y = _vector(coordinates, right)
    sp = sympy()
    symbols = list(map(sp.Symbol, coordinates))
    return {'components': [str(sp.simplify(sum(
        x[j]*sp.diff(y[i], symbols[j]) - y[j]*sp.diff(x[i], symbols[j])
        for j in range(len(x))))) for i in range(len(x))]}


def lie_derivative(coordinates, vector, components):
    """Lie derivative of a differential form by Cartan's formula."""
    first = interior_product(coordinates, vector, exterior_derivative(coordinates, components))
    second = exterior_derivative(coordinates, interior_product(coordinates, vector, components))
    sp = sympy()
    result = {}
    for key in first.keys() | second.keys():
        value = sp.simplify(expression(first.get(key, 0), coordinates)[0]
                            + expression(second.get(key, 0), coordinates)[0])
        if value != 0:
            result[key] = str(value)
    return result


def hodge_star(coordinates, metric, components, orientation=1):
    """Hodge dual for a nondegenerate real metric; abs(det g) convention.

The result is conditional on nondegeneracy and constant metric signature on
this chart. Orientation is +1 or -1 relative to the coordinate ordering.
"""
    coordinates = names(coordinates, 4)
    if type(orientation) is not int or orientation not in (-1, 1):
        raise ValueError('Orientation must be +1 or -1')
    sp = sympy()
    _, form = _form(coordinates, components)
    n = len(coordinates)
    if len(metric) != n or any(len(row) != n for row in metric):
        raise ValueError('Square metric matching chart dimension required')
    g = sp.Matrix([[expression(v, coordinates)[0] for v in row] for row in metric])
    if any(sp.simplify(g[i,j]-g[j,i]) != 0 for i in range(n) for j in range(n)):
        raise ValueError('Symmetric metric required')
    determinant = sp.simplify(g.det())
    if determinant == 0:
        raise ValueError('Degenerate metric')
    inverse = g.inv()
    degree = len(next(iter(form))) if form else 0
    result = {}
    for raised in combinations(range(n), degree):
        coefficient = sum(value * inverse.extract(raised, original).det()
                          for original, value in form.items())
        complement = tuple(i for i in range(n) if i not in raised)
        sign = (-1)**sum(i > j for i in raised for j in complement)
        value = sp.simplify(orientation * sign * sp.sqrt(sp.Abs(determinant)) * coefficient)
        if value != 0:
            result[','.join(map(str, complement))] = str(value)
    return {'components': result, 'nondegenerate_where': str(determinant)+' != 0',
            'orientation': orientation, 'scope': 'Local chart with constant signature'}


def stokes_box(coordinates, components, bounds):
    """Independently integrate dω and oriented faces of a rectangular box.

ω must have degree n-1. Smoothness on the closed box is a caller hypothesis;
unevaluated integrals or nonfinite expressions never become a certificate.
"""
    coordinates = names(coordinates, 4)
    _, form = _form(coordinates, components)
    n = len(coordinates)
    if any(len(key) != n-1 for key in form):
        raise ValueError('Stokes requires an (n-1)-form')
    sp = sympy()
    if len(bounds) != n or any(len(b) != 2 for b in bounds):
        raise ValueError('One increasing interval per coordinate required')
    intervals = [[expression(v, coordinates)[0] for v in b] for b in bounds]
    if any(a.free_symbols or b.free_symbols or (b-a).is_positive is not True
           for a,b in intervals):
        raise ValueError('Finite constant increasing intervals required')
    volume = integrate_box(coordinates, exterior_derivative(coordinates, components), bounds)
    boundary = sp.Integer(0)
    faces = []
    for i, name in enumerate(coordinates):
        key = tuple(j for j in range(n) if j != i)
        coefficient = form.get(key, sp.Integer(0))
        for endpoint, side in ((intervals[i][0], -1), (intervals[i][1], 1)):
            value = coefficient.subs(sp.Symbol(name), endpoint) * side * (-1)**i
            for j, other in enumerate(coordinates):
                if j != i:
                    value = sp.integrate(value, (sp.Symbol(other), *intervals[j]))
            boundary += value
            faces.append({'axis': i, 'side': side, 'integral': str(value)})
    interior = expression(volume['integral'], coordinates)[0] if volume['evaluated'] else None
    evaluated = interior is not None and not boundary.has(sp.Integral)
    finite = evaluated and not (interior-boundary).has(sp.nan, sp.zoo, sp.oo, -sp.oo)
    return {'interior': volume['integral'], 'boundary': str(sp.simplify(boundary)),
            'faces': faces, 'identity_verified': bool(finite and sp.simplify(interior-boundary) == 0),
            'hypotheses': 'Form is smooth on the closed box; standard outward orientation'}


def calculate(action, **parameters):
    """Run a registered manifold action through CalculationSession receipts."""
    from .advanced_math import calculate as audited
    return audited('manifold.'+action, **parameters)


__all__ = ['symbolic_metric', 'covariant_derivative', 'geodesic',
           'exterior_derivative', 'wedge', 'pullback', 'integrate_box',
           'euler_lagrange_fields', 'euler_lagrange_density', 'interior_product',
           'lie_bracket', 'lie_derivative', 'hodge_star', 'stokes_box', 'calculate']

# General tensor fields and independent local Riemannian algorithms.
from dataclasses import dataclass
from itertools import product
from functools import cached_property


def _indices(dimension, rank):
    return product(range(dimension), repeat=rank)


def _tensor_shape(value):
    """Infer a rectangular nested-list shape without materializing object arrays."""
    if not isinstance(value, (list, tuple)):
        return ()
    if not value:
        raise ValueError('Empty tensor axes are not supported')
    shapes = [_tensor_shape(v) for v in value]
    if any(s != shapes[0] for s in shapes):
        raise ValueError('Ragged tensor components')
    return (len(value),) + shapes[0]


def _nested(components, dimension, rank):
    def visit(prefix):
        if len(prefix) == rank:
            return str(components[prefix])
        return [visit(prefix+(i,)) for i in range(dimension)]
    return visit(())


@dataclass(frozen=True)
class TensorField:
    """Dense symbolic tensor on one coordinate chart.

    Variance is a tuple of +1 (contravariant) and -1 (covariant) slots, in the
    exact component order. Rank zero is permitted. Components are immutable
    SymPy expressions parsed through the same closed grammar as the rest of
    this module. Storage is bounded by 4**5 scalar entries.
    """
    coordinates: tuple
    variance: tuple
    entries: tuple

    def __post_init__(self):
        coordinates = names(self.coordinates, 4)
        if (not isinstance(self.variance, tuple) or len(self.variance)>5
                or any(type(v) is not int or v not in (-1,1) for v in self.variance)):
            raise ValueError('Tensor rank <=5 with variance +/-1 required')
        if len(self.entries) != len(coordinates)**len(self.variance):
            raise ValueError('Tensor entry count does not match rank/dimension')
        allowed = set(map(sympy().Symbol, coordinates))
        converted = []
        for value in self.entries:
            parsed = value if isinstance(value, sympy().Expr) else expression(value,coordinates)[0]
            if not parsed.free_symbols <= allowed:
                raise ValueError('Tensor contains symbols outside the chart')
            converted.append(parsed)
        object.__setattr__(self,'coordinates',coordinates)
        object.__setattr__(self,'entries',tuple(converted))

    @classmethod
    def from_components(cls, coordinates, variance, components):
        coordinates = names(coordinates,4)
        variance = tuple(variance)
        if _tensor_shape(components) != (len(coordinates),)*len(variance):
            raise ValueError('Component shape does not match tensor variance')
        entries=[]
        for index in _indices(len(coordinates),len(variance)):
            value=components
            for i in index:
                value=value[i]
            entries.append(expression(value,coordinates)[0])
        return cls(coordinates,variance,tuple(entries))

    @property
    def dimension(self):
        return len(self.coordinates)

    @property
    def rank(self):
        return len(self.variance)

    def at(self, index):
        if len(index)!=self.rank or any(type(i) is not int or not 0<=i<self.dimension for i in index):
            raise ValueError('Tensor index outside its shape')
        offset=0
        for i in index:
            offset=offset*self.dimension+i
        return self.entries[offset]

    def to_data(self):
        values={index:self.at(index) for index in _indices(self.dimension,self.rank)}
        return {'coordinates':list(self.coordinates),'variance':list(self.variance),
                'components':_nested(values,self.dimension,self.rank)}

    def _compatible(self, other):
        if not isinstance(other,TensorField) or self.coordinates!=other.coordinates:
            raise ValueError('Tensor charts differ')

    def add(self, other):
        self._compatible(other)
        if self.variance!=other.variance:
            raise ValueError('Cannot add tensors with different variance')
        sp=sympy()
        return TensorField(self.coordinates,self.variance,
                           tuple(sp.simplify(a+b) for a,b in zip(self.entries,other.entries)))

    def scale(self, scalar):
        sp=sympy()
        value=expression(scalar,self.coordinates)[0]
        return TensorField(self.coordinates,self.variance,
                           tuple(sp.simplify(value*v) for v in self.entries))

    def tensor_product(self, other):
        self._compatible(other)
        if self.rank+other.rank>5:
            raise ValueError('Tensor product rank budget exceeded')
        return TensorField(self.coordinates,self.variance+other.variance,
                           tuple(a*b for a in self.entries for b in other.entries))

    def permute(self, permutation):
        if sorted(permutation)!=list(range(self.rank)):
            raise ValueError('A permutation of tensor slots is required')
        inverse=[permutation.index(i) for i in range(self.rank)]
        values=tuple(self.at(tuple(index[inverse[j]] for j in range(self.rank)))
                     for index in _indices(self.dimension,self.rank))
        return TensorField(self.coordinates,tuple(self.variance[i] for i in permutation),values)

    def contract(self, first, second):
        if type(first) is not int or type(second) is not int or not 0<=first<self.rank or not 0<=second<self.rank or first==second:
            raise ValueError('Two distinct valid tensor slots required')
        if self.variance[first]==self.variance[second]:
            raise ValueError('Contraction requires opposite variance; raise/lower first')
        retained=[i for i in range(self.rank) if i not in (first,second)]
        result=[]
        for reduced in _indices(self.dimension,self.rank-2):
            index=[0]*self.rank
            for slot,value in zip(retained,reduced):index[slot]=value
            total=0
            for i in range(self.dimension):
                index[first]=index[second]=i
                total+=self.at(tuple(index))
            result.append(sympy().simplify(total))
        return TensorField(self.coordinates,tuple(self.variance[i] for i in retained),tuple(result))

    def symmetrize(self, first, second, *, alternating=False):
        if type(first) is not int or type(second) is not int or not 0<=first<self.rank or not 0<=second<self.rank or first==second:
            raise ValueError('Two distinct valid slots required')
        if self.variance[first]!=self.variance[second]:
            raise ValueError('Symmetrization slots need equal variance')
        permutation=list(range(self.rank))
        permutation[first],permutation[second]=permutation[second],permutation[first]
        swapped=self.permute(permutation)
        return self.add(swapped.scale(-1 if alternating else 1)).scale('1/2')


class MetricGeometry:
    """Independent Levi–Civita geometry for symbolic metrics in dimension <=4.

    Cached properties avoid repeated matrix inversions and symbolic curvature
    construction. A supplied chart domain must exclude det(g)=0 and poles.
    Tensor algebra is exact at the symbolic level; ODE trajectories remain
    floating-point approximations with solver tolerances reported separately.
    """
    def __init__(self, coordinates, metric):
        self.coordinates=names(coordinates,4)
        self.symbols=tuple(map(sympy().Symbol,self.coordinates))
        self.dimension=len(self.coordinates)
        if _tensor_shape(metric)!=(self.dimension,self.dimension):
            raise ValueError('Square chart metric required')
        self.metric=sympy().ImmutableMatrix([[expression(v,self.coordinates)[0] for v in row] for row in metric])
        if any(sympy().simplify(self.metric[i,j]-self.metric[j,i])!=0
               for i in range(self.dimension) for j in range(self.dimension)):
            raise ValueError('Metric must be symmetric')
        if self.determinant==0:
            raise ValueError('Metric is identically degenerate')

    @cached_property
    def determinant(self):
        return sympy().simplify(self.metric.det())

    @cached_property
    def inverse(self):
        return self.metric.inv().applyfunc(sympy().simplify)

    @cached_property
    def christoffel(self):
        sp=sympy();n=self.dimension;x=self.symbols;g=self.metric;inv=self.inverse
        return tuple(tuple(tuple(sp.simplify(sum(inv[a,l]*(sp.diff(g[l,j],x[i])
                    +sp.diff(g[l,i],x[j])-sp.diff(g[i,j],x[l])) for l in range(n))/2)
                    for j in range(n)) for i in range(n)) for a in range(n))

    @cached_property
    def riemann(self):
        sp=sympy();n=self.dimension;x=self.symbols;gamma=self.christoffel
        return tuple(tuple(tuple(tuple(sp.simplify(
            sp.diff(gamma[a][d][b],x[c])-sp.diff(gamma[a][c][b],x[d])
            +sum(gamma[a][c][e]*gamma[e][d][b]-gamma[a][d][e]*gamma[e][c][b] for e in range(n)))
            for d in range(n)) for c in range(n)) for b in range(n)) for a in range(n))

    @cached_property
    def ricci(self):
        sp=sympy();n=self.dimension
        return sp.Matrix(n,n,lambda i,j:sp.simplify(sum(self.riemann[a][i][a][j] for a in range(n))))

    @cached_property
    def scalar_curvature(self):
        n=self.dimension
        return sympy().simplify(sum(self.inverse[i,j]*self.ricci[i,j] for i in range(n) for j in range(n)))

    def einstein_tensor(self, cosmological_constant=0):
        value=expression(cosmological_constant,self.coordinates)[0]
        matrix=self.ricci-self.scalar_curvature*self.metric/2+value*self.metric
        return [[str(sympy().simplify(v)) for v in row] for row in matrix.tolist()]

    def lower_curvature(self):
        n=self.dimension;sp=sympy()
        return [[[[str(sp.simplify(sum(self.metric[a,e]*self.riemann[e][b][c][d]
                    for e in range(n)))) for d in range(n)] for c in range(n)]
                    for b in range(n)] for a in range(n)]

    def weyl_tensor(self):
        """Trace-free covariant Weyl tensor; identically zero below dimension 3."""
        sp=sympy();n=self.dimension
        if n<3:
            return [[[['0' for _ in range(n)] for _ in range(n)] for _ in range(n)] for _ in range(n)]
        result=[]
        for a in range(n):
            layer=[]
            for b in range(n):
                rows=[]
                for c in range(n):
                    row=[]
                    for d in range(n):
                        curvature=sum(self.metric[a,e]*self.riemann[e][b][c][d] for e in range(n))
                        trace=(self.metric[a,c]*self.ricci[b,d]-self.metric[a,d]*self.ricci[b,c]
                               -self.metric[b,c]*self.ricci[a,d]+self.metric[b,d]*self.ricci[a,c])/(n-2)
                        scalar=self.scalar_curvature*(self.metric[a,c]*self.metric[b,d]
                                  -self.metric[a,d]*self.metric[b,c])/((n-1)*(n-2))
                        row.append(str(sp.simplify(curvature-trace+scalar)))
                    rows.append(row)
                layer.append(rows)
            result.append(layer)
        return result

    def change_index(self, tensor, slot):
        """Raise or lower one tensor slot by the inverse metric or metric."""
        if not isinstance(tensor,TensorField) or tensor.coordinates!=self.coordinates:
            raise ValueError('Tensor must use this metric chart')
        if type(slot) is not int or not 0<=slot<tensor.rank:
            raise ValueError('Tensor slot outside its rank')
        matrix=self.inverse if tensor.variance[slot]==-1 else self.metric
        entries=[]
        for index in _indices(self.dimension,tensor.rank):
            value=0
            for contracted in range(self.dimension):
                old=list(index);old[slot]=contracted
                value+=matrix[index[slot],contracted]*tensor.at(tuple(old))
            entries.append(sympy().simplify(value))
        variance=list(tensor.variance);variance[slot]*=-1
        return TensorField(self.coordinates,tuple(variance),tuple(entries))

    def covariant(self, tensor):
        """Append the derivative's covariant slot to an arbitrary tensor."""
        if not isinstance(tensor,TensorField) or tensor.coordinates!=self.coordinates or tensor.rank>=5:
            raise ValueError('Compatible tensor of rank below five required')
        n=self.dimension;gamma=self.christoffel;sp=sympy();entries=[]
        for index in _indices(n,tensor.rank+1):
            original,derivative=index[:-1],index[-1]
            value=sp.diff(tensor.at(original),self.symbols[derivative])
            for slot,variance in enumerate(tensor.variance):
                for k in range(n):
                    replacement=list(original);replacement[slot]=k
                    factor=(gamma[original[slot]][derivative][k] if variance==1
                            else -gamma[k][derivative][original[slot]])
                    value+=factor*tensor.at(tuple(replacement))
            entries.append(sp.simplify(value))
        return TensorField(self.coordinates,tensor.variance+(-1,),tuple(entries))

    def divergence(self, tensor, slot=0):
        if tensor.rank==0 or tensor.variance[slot]!=1:
            raise ValueError('Divergence slot must be contravariant')
        return self.covariant(tensor).contract(slot,tensor.rank)

    def gradient(self, scalar):
        value=expression(scalar,self.coordinates)[0]
        differential=TensorField(self.coordinates,(-1,),tuple(sympy().diff(value,x) for x in self.symbols))
        return self.change_index(differential,0)

    def hessian(self, scalar):
        value=expression(scalar,self.coordinates)[0]
        differential=TensorField(self.coordinates,(-1,),tuple(sympy().diff(value,x) for x in self.symbols))
        return self.covariant(differential)

    def laplace_beltrami(self, scalar):
        hessian=self.hessian(scalar)
        n=self.dimension
        return str(sympy().simplify(sum(self.inverse[i,j]*hessian.at((i,j))
                                       for i in range(n) for j in range(n))))

    def metric_compatibility(self):
        tensor=TensorField(self.coordinates,(-1,-1),tuple(self.metric))
        derivative=self.covariant(tensor)
        residual=[str(sympy().simplify(v)) for v in derivative.entries]
        return {'compatible':all(v=='0' for v in residual),'residuals':residual}

    def first_bianchi(self):
        n=self.dimension;sp=sympy();failures=[]
        for a,b,c,d in _indices(n,4):
            value=sp.simplify(self.riemann[a][b][c][d]+self.riemann[a][c][d][b]+self.riemann[a][d][b][c])
            if value!=0:
                failures.append({'indices':[a,b,c,d],'residual':str(value)})
        return {'verified':not failures,'failures':failures}

    def sectional_curvature(self, left, right):
        _,u=_vector(self.coordinates,left);_,v=_vector(self.coordinates,right)
        sp=sympy();g=self.metric;n=self.dimension
        inner=lambda a,b:sum(g[i,j]*a[i]*b[j] for i in range(n) for j in range(n))
        denominator=sp.simplify(inner(u,u)*inner(v,v)-inner(u,v)**2)
        if denominator==0:
            raise ValueError('Sectional plane is degenerate')
        numerator=sum(g[a,e]*self.riemann[e][b][c][d]*u[a]*v[b]*u[c]*v[d]
                      for a,b,c,d,e in _indices(n,5))
        return {'curvature':str(sp.simplify(numerator/denominator)),
                'defined_where':str(denominator)+' != 0'}

    def killing_equations(self, vector):
        _,values=_vector(self.coordinates,vector)
        tensor=TensorField(self.coordinates,(1,),tuple(values))
        covariant=self.change_index(tensor,0)
        derivative=self.covariant(covariant)
        residuals=[[str(sympy().simplify(derivative.at((i,j))+derivative.at((j,i))))
                    for j in range(self.dimension)] for i in range(self.dimension)]
        return {'residuals':residuals,'is_killing':all(v=='0' for row in residuals for v in row)}

    def volume_density(self):
        return str(sympy().sqrt(sympy().Abs(self.determinant)))

    def to_data(self, *, curvature=True):
        result={'coordinates':list(self.coordinates),'determinant':str(self.determinant),
                'inverse':[[str(v) for v in row] for row in self.inverse.tolist()],
                'christoffel':[[list(map(str,row)) for row in layer] for layer in self.christoffel],
                'domain_hypothesis':str(self.determinant)+' != 0; chart expressions smooth'}
        if curvature:
            result.update({'riemann':[[[list(map(str,row)) for row in plane] for plane in layer] for layer in self.riemann],
                           'ricci':[[str(v) for v in row] for row in self.ricci.tolist()],
                           'scalar_curvature':str(self.scalar_curvature)})
        return result


def lie_tensor(coordinates, vector, variance, components):
    """Coordinate Lie derivative of a general mixed tensor, without a connection."""
    coordinates,flow=_vector(coordinates,vector)
    tensor=TensorField.from_components(coordinates,variance,components)
    sp=sympy();x=tuple(map(sp.Symbol,coordinates));n=len(x);entries=[]
    for index in _indices(n,tensor.rank):
        value=sum(flow[j]*sp.diff(tensor.at(index),x[j]) for j in range(n))
        for slot,sign in enumerate(tensor.variance):
            for j in range(n):
                changed=list(index);changed[slot]=j
                factor=(-sp.diff(flow[index[slot]],x[j]) if sign==1 else sp.diff(flow[j],x[index[slot]]))
                value+=factor*tensor.at(tuple(changed))
        entries.append(sp.simplify(value))
    return TensorField(coordinates,tensor.variance,tuple(entries)).to_data()


def tensor_calculus(coordinates, variance, components, operation, *, metric=None,
                    slots=None, scalar=1, other=None, other_variance=None):
    """Closed JSON-friendly tensor API suitable for audited catalog integration."""
    tensor=TensorField.from_components(coordinates,variance,components)
    if operation=='scale':result=tensor.scale(scalar)
    elif operation=='permute':result=tensor.permute(slots)
    elif operation=='contract':
        if slots is None or len(slots)!=2:raise ValueError('Two contraction slots required')
        result=tensor.contract(*slots)
    elif operation in ('symmetric','alternating'):
        if slots is None or len(slots)!=2:raise ValueError('Two symmetrization slots required')
        result=tensor.symmetrize(*slots,alternating=operation=='alternating')
    elif operation in ('add','product'):
        second=TensorField.from_components(coordinates,other_variance,other)
        result=tensor.add(second) if operation=='add' else tensor.tensor_product(second)
    elif operation in ('covariant','raise_lower','divergence'):
        geometry=MetricGeometry(coordinates,metric)
        if operation=='covariant':result=geometry.covariant(tensor)
        elif operation=='raise_lower':result=geometry.change_index(tensor,slots[0])
        else:result=geometry.divergence(tensor,0 if slots is None else slots[0])
    else:raise ValueError('Unsupported tensor operation')
    return result.to_data()


def _numerical_metric(geometry):
    """Compile only previously validated SymPy trees into numerical kernels."""
    import numpy as np
    sp=sympy()
    n=geometry.dimension
    gamma=sp.lambdify(geometry.symbols,geometry.christoffel,modules='numpy',cse=True)
    metric=sp.lambdify(geometry.symbols,geometry.metric,modules='numpy',cse=True)
    def evaluate(position):
        position=np.asarray(position,dtype=float)
        if position.shape!=(n,) or not np.isfinite(position).all():
            raise ValueError('Finite chart position required')
        with np.errstate(all='raise'):
            matrix=np.asarray(metric(*position),dtype=float)
            connection=np.asarray(gamma(*position),dtype=float)
        if not np.isfinite(matrix).all() or not np.isfinite(connection).all() or abs(np.linalg.det(matrix))<1e-14:
            raise ArithmeticError('Trajectory reached a singular or ill-conditioned chart')
        return matrix,connection
    return evaluate


def geodesic_flow(coordinates, metric, position, velocity, duration=1., samples=101,
                  rtol=1e-9, atol=1e-11, method='DOP853'):
    """Numerical geodesic flow with metric-energy drift diagnostics.

    Integration is local. A small energy drift is a diagnostic, not an a priori
    error bound or proof that the trajectory stayed in the intended manifold.
    Chart singularities encountered in numerical RHS evaluation are rejected.
    """
    import numpy as np
    from scipy.integrate import solve_ivp
    geometry=MetricGeometry(coordinates,metric)
    n=geometry.dimension
    initial=np.asarray(list(position)+list(velocity),dtype=float)
    if initial.shape!=(2*n,) or not np.isfinite(initial).all():
        raise ValueError('Finite chart position and velocity required')
    if type(samples) is not int or not 2<=samples<=10001:
        raise ValueError('2–10001 trajectory samples required')
    if type(duration) not in (int,float) or not 0<duration<=10000:
        raise ValueError('Positive finite integration duration up to 10000 required')
    if not 0<rtol<=.1 or not 0<atol<=.1 or method not in ('RK45','DOP853','Radau','BDF'):
        raise ValueError('Invalid tolerances or integration method')
    evaluate=_numerical_metric(geometry)
    def rhs(time,state):
        _,connection=evaluate(state[:n])
        return np.concatenate((state[n:],-np.einsum('aij,i,j->a',connection,state[n:],state[n:])))
    result=solve_ivp(rhs,(0,float(duration)),initial,method=method,
                     t_eval=np.linspace(0,duration,samples),rtol=rtol,atol=atol)
    if not result.success or not np.isfinite(result.y).all():
        raise ArithmeticError('Geodesic integration failed: '+result.message)
    energies=[]
    for state in result.y.T:
        g,_=evaluate(state[:n]);energies.append(float(state[n:]@g@state[n:]))
    energy_drift=max(abs(e-energies[0]) for e in energies)
    return {'times':result.t.tolist(),'states':result.y.T.tolist(),'metric_energy':energies,
            'maximum_energy_drift':energy_drift,'evaluations':result.nfev,
            'solver':method,'rtol':rtol,'atol':atol,
            'scope':'Local floating-point trajectory; energy drift is a diagnostic only'}


def parallel_transport_curve(coordinates, metric, path, vector, duration=1., samples=101,
                             parameter='s'):
    """Transport a tangent vector along a supplied differentiable chart curve."""
    import numpy as np
    from scipy.integrate import solve_ivp
    geometry=MetricGeometry(coordinates,metric)
    n=geometry.dimension
    if len(path)!=n or len(vector)!=n or parameter in coordinates:
        raise ValueError('Curve/vector dimensions differ or parameter collides with chart')
    if type(samples) is not int or not 2<=samples<=10001 or not 0<duration<=10000:
        raise ValueError('Curve integration budget exceeded')
    sp=sympy();s=sp.Symbol(parameter)
    functions=[expression(v,[parameter])[0] for v in path]
    positions=sp.lambdify((s,),functions,modules='numpy',cse=True)
    velocities=sp.lambdify((s,),[sp.diff(v,s) for v in functions],modules='numpy',cse=True)
    evaluate=_numerical_metric(geometry)
    initial=np.asarray(vector,dtype=float)
    if initial.shape!=(n,) or not np.isfinite(initial).all():
        raise ValueError('Finite initial vector required')
    def rhs(time,state):
        point=np.asarray(positions(time),dtype=float)
        tangent=np.asarray(velocities(time),dtype=float)
        _,connection=evaluate(point)
        return -np.einsum('aij,i,j->a',connection,tangent,state)
    solution=solve_ivp(rhs,(0,duration),initial,t_eval=np.linspace(0,duration,samples),rtol=1e-9,atol=1e-11)
    if not solution.success or not np.isfinite(solution.y).all():
        raise ArithmeticError('Parallel transport failed: '+solution.message)
    norm=[];points=[]
    for time,value in zip(solution.t,solution.y.T):
        point=np.asarray(positions(time),dtype=float);g,_=evaluate(point)
        points.append(point.tolist());norm.append(float(value@g@value))
    return {'times':solution.t.tolist(),'positions':points,'vectors':solution.y.T.tolist(),
            'squared_norm':norm,'maximum_norm_drift':max(abs(v-norm[0]) for v in norm),
            'scope':'Numerical parallel transport along the declared local chart curve'}


def exponential_map(coordinates, metric, base, tangent, *, steps=101):
    """exp_base(tangent) from a unit-time geodesic; not a global inverse chart."""
    result=geodesic_flow(coordinates,metric,base,tangent,duration=1.,samples=steps)
    n=len(coordinates)
    return {'point':result['states'][-1][:n],'velocity':result['states'][-1][n:],
            'maximum_energy_drift':result['maximum_energy_drift'],
            'scope':'Local numerical exponential map, no cut-locus or injectivity certificate'}


def logarithm_map(coordinates, metric, base, target, initial_tangent=None, tolerance=1e-7,
                  max_evaluations=100):
    """Shooting inverse of the exponential map with an explicit endpoint residual.

    Multiple geodesics can connect the same points. Success identifies the local
    branch reached by the chosen initial tangent; it does not prove uniqueness
    or that this geodesic minimizes distance.
    """
    import numpy as np
    from scipy.optimize import least_squares
    n=len(names(coordinates,4))
    start=np.asarray(base,dtype=float);end=np.asarray(target,dtype=float)
    guess=end-start if initial_tangent is None else np.asarray(initial_tangent,dtype=float)
    if start.shape!=(n,) or end.shape!=(n,) or guess.shape!=(n,) or not np.isfinite(np.concatenate((start,end,guess))).all():
        raise ValueError('Finite base/target/guess in the chart required')
    if not 0<tolerance<.1 or type(max_evaluations) is not int or not 1<=max_evaluations<=1000:
        raise ValueError('Invalid shooting convergence budget')
    def residual(tangent):
        return np.asarray(exponential_map(coordinates,metric,start,tangent,steps=2)['point'])-end
    solution=least_squares(residual,guess,xtol=tolerance,ftol=tolerance,gtol=tolerance,max_nfev=max_evaluations)
    error=float(np.linalg.norm(residual(solution.x)))
    return {'tangent':solution.x.tolist(),'endpoint_error':error,
            'converged':bool(solution.success and error<=tolerance),
            'evaluations':solution.nfev,'branch':'Initial-guess-dependent local shooting branch'}


def jacobi_field(coordinates, metric, position, velocity, displacement, covariant_velocity,
                 duration=1., samples=101):
    """Integrate a Jacobi field together with its base geodesic.

    W=D_t J. Equations are D_t W + R(J,V)V=0 under this module's Riemann
    convention. The result diagnoses infinitesimal geodesic separation only;
    finite perturbation errors are not bounded by the Jacobi approximation.
    """
    import numpy as np
    from scipy.integrate import solve_ivp
    geometry=MetricGeometry(coordinates,metric);n=geometry.dimension
    if any(len(v)!=n for v in (position,velocity,displacement,covariant_velocity)):
        raise ValueError('Four matching tangent/position vectors required')
    initial=np.asarray(list(position)+list(velocity)+list(displacement)+list(covariant_velocity),dtype=float)
    if not np.isfinite(initial).all() or not 0<duration<=1000 or type(samples) is not int or not 2<=samples<=10001:
        raise ValueError('Invalid Jacobi initial data or sample budget')
    evaluate=_numerical_metric(geometry)
    curvature=sympy().lambdify(geometry.symbols,geometry.riemann,modules='numpy',cse=True)
    def rhs(time,state):
        x,v,j,w=np.split(state,4)
        _,gamma=evaluate(x)
        riemann=np.asarray(curvature(*x),dtype=float)
        acceleration=-np.einsum('aij,i,j->a',gamma,v,v)
        derivative=w-np.einsum('aij,i,j->a',gamma,v,j)
        second=-np.einsum('aij,i,j->a',gamma,v,w)-np.einsum('abcd,b,c,d->a',riemann,v,j,v)
        return np.concatenate((v,acceleration,derivative,second))
    solution=solve_ivp(rhs,(0,duration),initial,t_eval=np.linspace(0,duration,samples),rtol=1e-9,atol=1e-11)
    if not solution.success or not np.isfinite(solution.y).all():
        raise ArithmeticError('Jacobi field integration failed: '+solution.message)
    return {'times':solution.t.tolist(),'states':solution.y.T.tolist(),
            'ordering':['position','velocity','jacobi','covariant_jacobi_velocity'],
            'scope':'Local linearized geodesic separation; no global conjugate-point certificate'}


def connection_curvature(coordinates, connection):
    """Curvature F_ij=∂i A_j-∂j A_i+[A_i,A_j] of a matrix connection."""
    coordinates=names(coordinates,4);sp=sympy();n=len(coordinates)
    if not isinstance(connection,(list,tuple)) or len(connection)!=n:
        raise ValueError('One connection matrix per coordinate required')
    rank=len(connection[0])
    if not 1<=rank<=4 or any(_tensor_shape(a)!=(rank,rank) for a in connection):
        raise ValueError('Square connection matrices of rank 1–4 required')
    matrices=[sp.Matrix([[expression(v,coordinates)[0] for v in row] for row in a]) for a in connection]
    result={}
    for i in range(n):
        for j in range(i+1,n):
            value=matrices[j].diff(sp.Symbol(coordinates[i]))-matrices[i].diff(sp.Symbol(coordinates[j]))
            value+=matrices[i]*matrices[j]-matrices[j]*matrices[i]
            result[f'{i},{j}']=[[str(sp.simplify(v)) for v in row] for row in value.tolist()]
    return {'components':result,'rank':rank,'convention':'F=dA+A wedge A'}


def gauge_transform(coordinates, connection, gauge):
    """A' = G^-1 A G + G^-1 dG for an invertible matrix gauge field."""
    coordinates=names(coordinates,4);sp=sympy();n=len(coordinates)
    if len(connection)!=n or not isinstance(gauge,(list,tuple)) or not 1<=len(gauge)<=4:
        raise ValueError('Invalid connection/gauge dimensions')
    rank=len(gauge)
    if _tensor_shape(gauge)!=(rank,rank) or any(_tensor_shape(a)!=(rank,rank) for a in connection):
        raise ValueError('Gauge and connection matrix shapes differ')
    g=sp.Matrix([[expression(v,coordinates)[0] for v in row] for row in gauge])
    if sp.simplify(g.det())==0:
        raise ValueError('Gauge matrix is identically singular')
    inverse=g.inv();out=[]
    for i,matrix in enumerate(connection):
        a=sp.Matrix([[expression(v,coordinates)[0] for v in row] for row in matrix])
        changed=inverse*a*g+inverse*g.diff(sp.Symbol(coordinates[i]))
        out.append([[str(sp.simplify(v)) for v in row] for row in changed.tolist()])
    return {'connection':out,'invertible_where':str(sp.simplify(g.det()))+' != 0'}


def integrate_simplex(coordinates, components, vertices):
    """Integrate a k-form over an oriented affine k-simplex in chart space.

    Vertices are in orientation order. Degenerate simplices give zero through
    their pullback rather than inventing a normal direction. The symbolic
    backend may return unevaluated integrals for non-polynomial coefficients.
    """
    coordinates=names(coordinates,4);sp=sympy();n=len(coordinates)
    if not isinstance(vertices,(list,tuple)) or not 1<=len(vertices)<=n+1:
        raise ValueError('A simplex needs between one and n+1 vertices')
    k=len(vertices)-1
    if any(len(v)!=n for v in vertices):
        raise ValueError('Simplex vertex dimension differs from chart')
    _,form=_form(coordinates,components)
    if any(len(index)!=k for index in form):
        raise ValueError('Form degree differs from simplex dimension')
    points=[[expression(v,coordinates)[0] for v in row] for row in vertices]
    if any(v.free_symbols or v.is_real is False for row in points for v in row):
        raise ValueError('Constant real simplex vertices required')
    if k==0:
        value=form.get((),sp.Integer(0)).subs(dict(zip(map(sp.Symbol,coordinates),points[0])),simultaneous=True)
        return {'integral':str(value),'evaluated':True,'dimension':0}
    parameters=[f'simplex{i}' for i in range(k)]
    if set(parameters)&set(coordinates):
        raise ValueError('Reserved simplex parameter collides with chart')
    mapping=[str(points[0][i]+sum(sp.Symbol(parameters[j])*(points[j+1][i]-points[0][i]) for j in range(k))) for i in range(n)]
    transformed=pullback(parameters,coordinates,mapping,components)
    coefficient=expression(transformed.get(','.join(map(str,range(k))),'0'),parameters)[0]
    for j in reversed(range(k)):
        upper=1-sum(sp.Symbol(parameters[i]) for i in range(j))
        coefficient=sp.integrate(coefficient,(sp.Symbol(parameters[j]),0,upper))
    return {'integral':str(sp.simplify(coefficient)),'evaluated':not coefficient.has(sp.Integral),'dimension':k}


def stokes_simplex(coordinates, components, vertices):
    """Compare independently integrated oriented simplex boundary and dω."""
    sp=sympy();dimension=len(vertices)-1
    if dimension<1:
        raise ValueError('Stokes simplex dimension must be positive')
    interior=integrate_simplex(coordinates,exterior_derivative(coordinates,components),vertices)
    faces=[];boundary=sp.Integer(0);evaluated=interior['evaluated']
    for i in range(len(vertices)):
        face=integrate_simplex(coordinates,components,vertices[:i]+vertices[i+1:])
        evaluated=bool(evaluated and face['evaluated'])
        if face['evaluated']:
            boundary+=(-1)**i*expression(face['integral'],coordinates)[0]
        faces.append({'omitted_vertex':i,'orientation':(-1)**i,**face})
    interior_value=expression(interior['integral'],coordinates)[0] if interior['evaluated'] else None
    difference=sp.simplify(interior_value-boundary) if evaluated else None
    finite=difference is not None and not difference.has(sp.nan,sp.zoo,sp.oo,-sp.oo)
    return {'interior':interior['integral'],'boundary':str(sp.simplify(boundary)) if evaluated else None,
            'identity_verified':bool(finite and difference==0),'faces':faces,
            'hypotheses':'Smooth form on the closed affine simplex and its boundary'}


def noether_point_symmetry(lagrangian, fields, generators, boundary_term='0', time='t'):
    """First-order point-symmetry Noether charge with an explicit residual.

    Transformation is δq_i=η_i(t,q), δt=0 and δL=D_t B(t,q). The returned
    charge is Σ p_i η_i-B. Conservation is conditional on the Euler–Lagrange
    equations and a zero symmetry residual; no minimization claim is made.
    """
    fields=names(fields,4)
    if len(generators)!=len(fields):
        raise ValueError('One symmetry generator per dependent coordinate required')
    sp=sympy()
    variables=[time]+list(fields)+[f'{f}_v' for f in fields]+[f'{f}_a' for f in fields]
    names(variables,16)
    value,symbols=expression(lagrangian,variables);s=dict(zip(variables,symbols))
    if any(value.has(s[f'{f}_a']) for f in fields):
        raise ValueError('Noether API accepts first-order Lagrangians only')
    allowed=[time]+list(fields)
    eta=[expression(v,allowed)[0] for v in generators]
    boundary=expression(boundary_term,allowed)[0]
    def total(f):
        return sp.diff(f,s[time])+sum(s[f'{q}_v']*sp.diff(f,s[q])+s[f'{q}_a']*sp.diff(f,s[f'{q}_v']) for q in fields)
    momenta=[sp.diff(value,s[f'{q}_v']) for q in fields]
    variation=sum(e*sp.diff(value,s[q])+total(e)*p for q,e,p in zip(fields,eta,momenta))
    residual=sp.simplify(variation-total(boundary))
    charge=sp.simplify(sum(p*e for p,e in zip(momenta,eta))-boundary)
    equations=[sp.simplify(total(p)-sp.diff(value,s[q])) for q,p in zip(fields,momenta)]
    identity=sp.simplify(total(charge)-sum(e*equation for e,equation in zip(eta,equations))-residual)
    return {'charge':str(charge),'symmetry_residual':str(residual),'is_symmetry':residual==0,
            'euler_lagrange':list(map(str,equations)),'off_shell_identity_verified':identity==0,
            'hypotheses':'On-shell charge conservation requires all returned Euler–Lagrange equations'}


def quadratic_legendre(lagrangian, fields, momenta=None, time='t'):
    """Legendre transform of a Lagrangian at most quadratic in velocities.

    A nonsingular velocity Hessian determines a local algebraic inverse. It
    need not be positive definite, and regularity does not imply a stable
    Hamiltonian or a globally minimizing action.
    """
    fields=names(fields,4)
    momenta=list(momenta) if momenta is not None else [f'{f}_p' for f in fields]
    if len(momenta)!=len(fields):
        raise ValueError('One momentum variable per field required')
    variables=[time]+list(fields)+[f'{f}_v' for f in fields]+momenta
    names(variables,16)
    sp=sympy();value,symbols=expression(lagrangian,variables);s=dict(zip(variables,symbols))
    if any(value.has(s[p]) for p in momenta):
        raise ValueError('Lagrangian must not already depend on canonical momenta')
    velocities=[s[f'{f}_v'] for f in fields]
    if not value.is_polynomial(*velocities) or sp.Poly(value,*velocities).total_degree()>2:
        raise ValueError('Lagrangian must be polynomial of velocity degree at most two')
    hessian=sp.hessian(value,velocities)
    determinant=sp.simplify(hessian.det())
    if determinant==0:
        raise ValueError('Singular Legendre transform; constrained mechanics needs a separate analysis')
    linear=sp.Matrix([sp.diff(value,v).subs(dict.fromkeys(velocities,0),simultaneous=True) for v in velocities])
    solved=hessian.inv()*(sp.Matrix([s[p] for p in momenta])-linear)
    substitution=dict(zip(velocities,solved))
    hamiltonian=sp.simplify(sum(s[p]*v for p,v in zip(momenta,solved))-value.subs(substitution,simultaneous=True))
    return {'hamiltonian':str(hamiltonian),'velocities':list(map(str,solved)),
            'regular_where':str(determinant)+' != 0',
            'hamilton_equations':{'coordinates':[str(sp.diff(hamiltonian,s[p])) for p in momenta],
                                  'momenta':[str(-sp.diff(hamiltonian,s[f])) for f in fields]}}


__all__ += ['TensorField','MetricGeometry','tensor_calculus','lie_tensor',
            'geodesic_flow','parallel_transport_curve','exponential_map','logarithm_map',
            'jacobi_field','connection_curvature','gauge_transform','integrate_simplex',
            'stokes_simplex','noether_point_symmetry','quadratic_legendre']


class MetricTensor(MetricGeometry):
    """Metric with explicit pointwise signature and tangent-space invariants.

    Coordinates carry no implicit positivity assumptions. Signature evaluation
    requires a complete real point away from poles. This avoids declaring a
    symbolic metric Riemannian on every chart merely from a single sample.
    """
    def at(self, point):
        if not isinstance(point,dict) or set(point)!=set(self.coordinates):
            raise ValueError('Bind every chart coordinate exactly once')
        substitutions={symbol:expression(point[name],self.coordinates)[0]
                       for name,symbol in zip(self.coordinates,self.symbols)}
        if any(value.free_symbols or value.is_real is not True or value.is_finite is not True
               for value in substitutions.values()):
            raise ValueError('Finite real constant point coordinates required')
        matrix=self.metric.subs(substitutions,simultaneous=True).applyfunc(sympy().simplify)
        if any(v.is_real is not True or v.is_finite is not True for v in matrix):
            raise ValueError('Metric is not finite and real at this point')
        if sympy().simplify(matrix.det())==0:
            raise ValueError('Metric is degenerate at this point')
        return matrix

    def signature(self, point):
        matrix=self.at(point);positive=negative=0
        for value,multiplicity in matrix.eigenvals().items():
            if value.is_positive is True:positive+=multiplicity
            elif value.is_negative is True:negative+=multiplicity
            else:
                raise ArithmeticError('Exact eigenvalue sign could not be certified at this point')
        kind=('riemannian' if negative==0 else 'lorentzian' if negative==1 or positive==1 else 'pseudo_riemannian')
        return {'positive':positive,'negative':negative,'zero':0,'kind':kind,
                'scope':'Pointwise exact inertia; signature constancy on a chart is a separate hypothesis'}

    def inner_product(self, left, right):
        _,u=_vector(self.coordinates,left);_,v=_vector(self.coordinates,right)
        return str(sympy().simplify(sum(self.metric[i,j]*u[i]*v[j]
                                       for i in range(self.dimension) for j in range(self.dimension))))

    def normalize(self, vector, sign=1):
        if type(sign) is not int or sign not in (-1,1):raise ValueError('Norm sign must be +1 or -1')
        _,v=_vector(self.coordinates,vector)
        squared=expression(self.inner_product(vector,vector),self.coordinates)[0]
        if squared==0:raise ValueError('Cannot normalize a null vector')
        norm=sympy().sqrt(sign*squared)
        return {'vector':[str(sympy().simplify(value/norm)) for value in v],
                'norm_sign':sign,'valid_where':str(sign*squared)+' > 0'}

    def volume_form(self, orientation=1):
        if type(orientation) is not int or orientation not in (-1,1):raise ValueError('Orientation is +/-1')
        return DifferentialForm(self.coordinates,{','.join(map(str,range(self.dimension))):str(orientation*sympy().sqrt(sympy().Abs(self.determinant)))})

    def tensor(self):
        return TensorField(self.coordinates,(-1,-1),tuple(self.metric))

    def inverse_tensor(self):
        return TensorField(self.coordinates,(1,1),tuple(self.inverse))


class DifferentialForm:
    """Immutable homogeneous coordinate form with algebraic identity checks."""
    def __init__(self, coordinates, components, *, degree=None):
        coordinates,parsed=_form(coordinates,components)
        inferred=len(next(iter(parsed))) if parsed else (0 if degree is None else degree)
        if type(inferred) is not int or not 0<=inferred<=len(coordinates):
            raise ValueError('Form degree outside chart dimension')
        if degree is not None and (type(degree) is not int or degree!=inferred):
            raise ValueError('Declared form degree differs from components')
        self.coordinates=coordinates;self.degree=inferred
        self._components=tuple((index,sympy().simplify(value)) for index,value in sorted(parsed.items())
                               if sympy().simplify(value)!=0)

    @property
    def components(self):
        return {','.join(map(str,index)):str(value) for index,value in self._components}

    def to_data(self):
        return {'coordinates':list(self.coordinates),'degree':self.degree,'components':self.components}

    def add(self, other):
        if not isinstance(other,DifferentialForm) or self.coordinates!=other.coordinates or self.degree!=other.degree:
            raise ValueError('Only equal-degree forms on the same chart can be added')
        values=dict(self._components)
        for index,value in other._components:values[index]=values.get(index,0)+value
        return DifferentialForm(self.coordinates,{','.join(map(str,k)):str(v) for k,v in values.items()},degree=self.degree)

    def scale(self, value):
        scalar=expression(value,self.coordinates)[0]
        return DifferentialForm(self.coordinates,{','.join(map(str,k)):str(v*scalar) for k,v in self._components},degree=self.degree)

    def wedge(self, other):
        if not isinstance(other,DifferentialForm) or self.coordinates!=other.coordinates:
            raise ValueError('Wedge factors must share a chart')
        if self.degree+other.degree>len(self.coordinates):
            return {'zero':True,'degree':self.degree+other.degree,'reason':'Degree exceeds chart dimension'}
        return DifferentialForm(self.coordinates,wedge(self.coordinates,self.components,other.components),degree=self.degree+other.degree)

    def exterior_derivative(self):
        if self.degree==len(self.coordinates):
            return {'zero':True,'degree':self.degree+1,'reason':'Top-degree form has zero exterior derivative'}
        return DifferentialForm(self.coordinates,exterior_derivative(self.coordinates,self.components),degree=self.degree+1)

    def nilpotence_check(self):
        """Verify the finite coordinate d² residual; this is not a Lean proof."""
        first=exterior_derivative(self.coordinates,self.components)
        second=exterior_derivative(self.coordinates,first)
        return {'identity':'d(d(omega))=0','residual':second,'verified':not second,
                'verification':'Exact symbolic coordinate cancellation under smoothness hypotheses',
                'formal_kernel_verified':False}

    def contract(self, vector):
        if self.degree==0:return {'zero':True,'degree':-1,'reason':'Contraction of a scalar vanishes'}
        return DifferentialForm(self.coordinates,interior_product(self.coordinates,vector,self.components),degree=self.degree-1)

    def lie_derivative(self, vector):
        return DifferentialForm(self.coordinates,lie_derivative(self.coordinates,vector,self.components),degree=self.degree)

    def hodge(self, metric, orientation=1):
        result=hodge_star(self.coordinates,metric,self.components,orientation)
        return DifferentialForm(self.coordinates,result['components'],degree=len(self.coordinates)-self.degree)

    def codifferential(self, metric, *, negative_eigenvalues=0):
        """δ=(-1)^{n(k+1)+s+1} * d * on a signature-s chart."""
        n=len(self.coordinates)
        if type(negative_eigenvalues) is not int or not 0<=negative_eigenvalues<=n:
            raise ValueError('Signature index must be between zero and dimension')
        if self.degree==0:return {'zero':True,'degree':-1}
        dual=self.hodge(metric)
        derivative=exterior_derivative(self.coordinates,dual.components)
        out=hodge_star(self.coordinates,metric,derivative)['components']
        sign=(-1)**(n*(self.degree+1)+negative_eigenvalues+1)
        return DifferentialForm(self.coordinates,out,degree=self.degree-1).scale(sign)

    def hodge_laplacian(self, metric, *, negative_eigenvalues=0):
        """Compute dδ+δd, returning a degree-preserving form."""
        n=len(self.coordinates)
        result=DifferentialForm(self.coordinates,{},degree=self.degree)
        if self.degree>0:
            lower=self.codifferential(metric,negative_eigenvalues=negative_eigenvalues)
            result=result.add(DifferentialForm(self.coordinates,exterior_derivative(self.coordinates,lower.components),degree=self.degree))
        if self.degree<n:
            derivative=DifferentialForm(self.coordinates,exterior_derivative(self.coordinates,self.components),degree=self.degree+1)
            result=result.add(derivative.codifferential(metric,negative_eigenvalues=negative_eigenvalues))
        return result


class ChristoffelSymbols:
    """First/second-kind Levi–Civita symbols and numerical evaluation."""
    def __init__(self, metric):
        if not isinstance(metric,MetricGeometry):raise ValueError('MetricGeometry instance required')
        self.metric=metric

    def second_kind(self):
        return [[[str(v) for v in row] for row in layer] for layer in self.metric.christoffel]

    def first_kind(self):
        n=self.metric.dimension;g=self.metric.metric;gamma=self.metric.christoffel
        return [[[str(sympy().simplify(sum(g[a,b]*gamma[b][i][j] for b in range(n))))
                  for j in range(n)] for i in range(n)] for a in range(n)]

    def at(self, point):
        import numpy as np
        if not isinstance(point,(list,tuple)) or len(point)!=self.metric.dimension:
            raise ValueError('One point coordinate per chart dimension required')
        _,gamma=_numerical_metric(self.metric)(point)
        return gamma.tolist()

    def torsion(self):
        n=self.metric.dimension
        values=[[[str(sympy().simplify(self.metric.christoffel[a][i][j]-self.metric.christoffel[a][j][i]))
                  for j in range(n)] for i in range(n)] for a in range(n)]
        return {'components':values,'zero':all(v=='0' for layer in values for row in layer for v in row)}


class RiemannCurvature:
    """Riemann curvature and invariant contractions from a metric connection."""
    def __init__(self, metric):
        if not isinstance(metric,MetricGeometry):raise ValueError('MetricGeometry instance required')
        self.metric=metric

    def components(self, *, covariant=False):
        return self.metric.lower_curvature() if covariant else self.metric.to_data()['riemann']

    def kretschmann(self):
        """R_abcd R^abcd, using successive mode products rather than n^8 loops."""
        sp=sympy();n=self.metric.dimension
        lowered={index:sp.simplify(sum(self.metric.metric[index[0],e]*self.metric.riemann[e][index[1]][index[2]][index[3]]
                                      for e in range(n))) for index in _indices(n,4)}
        tensor=TensorField(self.metric.coordinates,(-1,)*4,tuple(lowered[i] for i in _indices(n,4)))
        raised=tensor
        for slot in range(4):raised=self.metric.change_index(raised,slot)
        return str(sp.simplify(sum(a*b for a,b in zip(tensor.entries,raised.entries))))

    def symmetries(self):
        sp=sympy();n=self.metric.dimension;lower=self.metric.lower_curvature()
        entries={i:expression(lower[i[0]][i[1]][i[2]][i[3]],self.metric.coordinates)[0] for i in _indices(n,4)}
        violations=[]
        for a,b,c,d in _indices(n,4):
            tests={'first_pair':entries[a,b,c,d]+entries[b,a,c,d],
                   'last_pair':entries[a,b,c,d]+entries[a,b,d,c],
                   'pair_exchange':entries[a,b,c,d]-entries[c,d,a,b]}
            for identity,value in tests.items():
                residual=sp.simplify(value)
                if residual!=0:violations.append({'identity':identity,'indices':[a,b,c,d],'residual':str(residual)})
        return {'verified':not violations,'violations':violations}


class RicciTensor:
    def __init__(self, metric):
        if not isinstance(metric,MetricGeometry):raise ValueError('MetricGeometry instance required')
        self.metric=metric

    def components(self):
        return [[str(v) for v in row] for row in self.metric.ricci.tolist()]

    def tensor(self):
        return TensorField(self.metric.coordinates,(-1,-1),tuple(self.metric.ricci))


class RicciScalar:
    def __init__(self, metric):
        if not isinstance(metric,MetricGeometry):raise ValueError('MetricGeometry instance required')
        self.metric=metric

    def expression(self):
        return str(self.metric.scalar_curvature)


class EinsteinTensor:
    def __init__(self, metric, cosmological_constant=0):
        if not isinstance(metric,MetricGeometry):raise ValueError('MetricGeometry instance required')
        self.metric=metric;self.cosmological_constant=cosmological_constant

    def components(self):
        return self.metric.einstein_tensor(self.cosmological_constant)

    def divergence(self):
        tensor=TensorField.from_components(self.metric.coordinates,(-1,-1),self.components())
        raised=self.metric.change_index(tensor,0)
        result=self.metric.divergence(raised)
        return {'components':result.to_data()['components'],
                'zero':all(sympy().simplify(v)==0 for v in result.entries)}


class GeodesicIntegrator:
    """Adaptive geodesic integration with explicit normalization diagnostics.

    Conservation is monitored rather than enforced by rescaling the tangent:
    rescaling at every step would change the integration problem. The caller
    may reject a trajectory when its observed metric norm drift is too large.
    """
    def __init__(self, metric, *, method='DOP853', rtol=1e-9, atol=1e-11):
        if not isinstance(metric,MetricGeometry):raise ValueError('MetricGeometry instance required')
        self.metric=metric;self.method=method;self.rtol=rtol;self.atol=atol

    def solve(self, position, velocity, duration=1., samples=101, *, max_norm_drift=None):
        result=geodesic_flow(self.metric.coordinates,[[str(v) for v in row] for row in self.metric.metric.tolist()],
                             position,velocity,duration,samples,self.rtol,self.atol,self.method)
        if max_norm_drift is not None:
            if type(max_norm_drift) not in (int,float) or max_norm_drift<0:
                raise ValueError('Nonnegative permitted norm drift required')
            if result['maximum_energy_drift']>max_norm_drift:
                raise ArithmeticError('Observed geodesic norm drift exceeds the requested tolerance')
        return result


class EulerLagrangeSolver:
    """Derive and integrate regular first-order mechanical Lagrangians.

    Field names q identify positions, q_v velocities and q_a accelerations.
    Densities with spatial derivatives belong to the field-equation API rather
    than this finite-dimensional initial-value solver.
    """
    def __init__(self, lagrangian, fields, time='t'):
        self.fields=names(fields,4);self.time=time
        variables=[time]+list(self.fields)+[f'{f}_v' for f in self.fields]+[f'{f}_a' for f in self.fields]
        self.lagrangian,self.symbols=expression(lagrangian,variables)
        self.variables=variables;self.symbols_by_name=dict(zip(variables,self.symbols))
        self.positions=[self.symbols_by_name[f] for f in self.fields]
        self.velocities=[self.symbols_by_name[f'{f}_v'] for f in self.fields]
        self.accelerations=[self.symbols_by_name[f'{f}_a'] for f in self.fields]
        if any(self.lagrangian.has(v) for v in self.accelerations):
            raise ValueError('Mechanical Lagrangian must have first-order derivatives only')
        sp=sympy();t=self.symbols_by_name[time]
        self.momenta=[sp.diff(self.lagrangian,v) for v in self.velocities]
        equations=[]
        for position,momentum in zip(self.positions,self.momenta):
            total=sp.diff(momentum,t)
            total+=sum(v*sp.diff(momentum,q)+a*sp.diff(momentum,w)
                       for q,v,w,a in zip(self.positions,self.velocities,self.velocities,self.accelerations))
            equations.append(sp.expand(total-sp.diff(self.lagrangian,position)))
        self.equations=tuple(equations)
        self.mass_matrix=sp.Matrix(equations).jacobian(self.accelerations)
        self.regularity=sp.simplify(self.mass_matrix.det())
        if self.regularity==0:raise ValueError('Singular mechanical Lagrangian requires constrained dynamics')
        force=-sp.Matrix(equations).subs(dict.fromkeys(self.accelerations,0),simultaneous=True)
        self.acceleration=(self.mass_matrix.inv()*force).applyfunc(sp.simplify)
        self.energy=sp.simplify(sum(v*p for v,p in zip(self.velocities,self.momenta))-self.lagrangian)

    def derive(self):
        return {'equations':list(map(str,self.equations)),
                'accelerations':list(map(str,self.acceleration)),
                'momenta':list(map(str,self.momenta)),'energy':str(self.energy),
                'regular_where':str(self.regularity)+' != 0',
                'autonomous':not self.lagrangian.has(self.symbols_by_name[self.time])}

    def solve(self, position, velocity, duration=1., samples=101, method='DOP853',
              rtol=1e-9, atol=1e-11):
        import numpy as np
        from scipy.integrate import solve_ivp
        n=len(self.fields)
        initial=np.asarray(list(position)+list(velocity),dtype=float)
        if initial.shape!=(2*n,) or not np.isfinite(initial).all():raise ValueError('Finite position/velocity vectors required')
        if not 0<duration<=10000 or type(samples) is not int or not 2<=samples<=10001:
            raise ValueError('Mechanical integration budget exceeded')
        if method not in ('RK45','DOP853','Radau','BDF') or not 0<rtol<=.1 or not 0<atol<=.1:
            raise ValueError('Invalid method/tolerances')
        arguments=[self.symbols_by_name[self.time]]+self.positions+self.velocities
        acceleration=sympy().lambdify(arguments,self.acceleration,modules='numpy',cse=True)
        energy=sympy().lambdify(arguments,self.energy,modules='numpy',cse=True)
        determinant=sympy().lambdify(arguments,self.regularity,modules='numpy',cse=True)
        def rhs(time,state):
            args=[time]+state.tolist()
            det=float(determinant(*args))
            if not np.isfinite(det) or abs(det)<1e-14:raise ArithmeticError('Mechanical mass matrix became singular')
            force=np.asarray(acceleration(*args),dtype=float).reshape(n)
            if not np.isfinite(force).all():raise ArithmeticError('Nonfinite mechanical acceleration')
            return np.concatenate((state[n:],force))
        solution=solve_ivp(rhs,(0,duration),initial,method=method,t_eval=np.linspace(0,duration,samples),rtol=rtol,atol=atol)
        if not solution.success or not np.isfinite(solution.y).all():raise ArithmeticError('Mechanical integration failed: '+solution.message)
        energies=[float(energy(time,*state)) for time,state in zip(solution.t,solution.y.T)]
        return {'times':solution.t.tolist(),'states':solution.y.T.tolist(),'energy':energies,
                'maximum_energy_drift':max(abs(v-energies[0]) for v in energies),
                'equations':self.derive(),'method':method,'rtol':rtol,'atol':atol}


def manifold_christoffel(coordinates, metric, kind='second', point=None):
    geometry=MetricTensor(coordinates,metric);connection=ChristoffelSymbols(geometry)
    if kind not in ('first','second'):raise ValueError('Christoffel kind is first or second')
    result={'components':connection.first_kind() if kind=='first' else connection.second_kind(),'kind':kind}
    if point is not None:
        if kind!='second':raise ValueError('Numerical point adapter currently uses second-kind symbols')
        result['at_point']=connection.at(point)
    return result


def manifold_riemann(coordinates, metric, covariant=False):
    geometry=MetricTensor(coordinates,metric)
    return {'components':RiemannCurvature(geometry).components(covariant=covariant),
            'covariant':covariant,'nondegenerate_where':str(geometry.determinant)+' != 0'}


def manifold_ricci(coordinates, metric, cosmological_constant=0):
    geometry=MetricTensor(coordinates,metric)
    return {'ricci':RicciTensor(geometry).components(),'scalar':RicciScalar(geometry).expression(),
            'einstein':EinsteinTensor(geometry,cosmological_constant).components()}


def geodesic_solve(coordinates, metric, position, velocity, duration=1., samples=101,
                   method='DOP853', rtol=1e-9, atol=1e-11):
    return GeodesicIntegrator(MetricTensor(coordinates,metric),method=method,rtol=rtol,atol=atol).solve(position,velocity,duration,samples)


def euler_lagrange_solve(lagrangian, fields, position, velocity, duration=1., samples=101,
                        time='t', method='DOP853', rtol=1e-9, atol=1e-11):
    return EulerLagrangeSolver(lagrangian,fields,time).solve(position,velocity,duration,samples,method,rtol,atol)


__all__ += ['MetricTensor','DifferentialForm','ChristoffelSymbols','RiemannCurvature',
            'RicciTensor','RicciScalar','EinsteinTensor','GeodesicIntegrator',
            'EulerLagrangeSolver','manifold_christoffel','manifold_riemann',
            'manifold_ricci','geodesic_solve','euler_lagrange_solve']


def poincare_homotopy(coordinates, components):
    """Radial chain homotopy on a star-shaped chart containing the origin.

    For a k-form, Kω = integral_0^1 t^(k-1) i_x ω(tx) dt. Smoothness on
    radial segments is essential: a punctured-domain closed form is not
    promoted to exact merely because its exterior derivative vanishes.
    """
    coordinates,form=_form(coordinates,components);sp=sympy()
    if not form:return {'components':{},'evaluated':True,'hypotheses':'Smooth on a star-shaped chart containing zero'}
    degree=len(next(iter(form)))
    if degree==0:return {'components':{},'evaluated':True,'degree':-1}
    parameter=sp.Dummy('radial',positive=True)
    symbols=tuple(map(sp.Symbol,coordinates));substitution={x:parameter*x for x in symbols};result={}
    for indices,coefficient in form.items():
        radial=coefficient.subs(substitution,simultaneous=True)
        for position,index in enumerate(indices):
            reduced=indices[:position]+indices[position+1:]
            integrand=(-1)**position*symbols[index]*parameter**(degree-1)*radial
            value=sp.integrate(integrand,(parameter,0,1))
            result[reduced]=sp.simplify(result.get(reduced,0)+value)
    if any(v.has(sp.zoo,sp.nan,sp.oo,-sp.oo) for v in result.values()):
        raise ValueError('Radial homotopy integral is singular; star-shaped smoothness fails')
    return {'components':{','.join(map(str,k)):str(v) for k,v in result.items() if v!=0},
            'evaluated':all(not v.has(sp.Integral) for v in result.values()),'degree':degree-1,
            'hypotheses':'Smooth coefficients along all radial segments in a star-shaped chart containing zero'}


def conservative_potential(coordinates, components):
    """Construct a potential for a closed one-form under Poincare hypotheses."""
    coordinates,form=_form(coordinates,components)
    if any(len(index)!=1 for index in form):raise ValueError('A one-form is required')
    closed=exterior_derivative(coordinates,components)
    if closed:return {'exact_under_hypotheses':False,'closed':False,'exterior_derivative':closed}
    homotopy=poincare_homotopy(coordinates,components)
    if not homotopy['evaluated']:return {'closed':True,'potential_status':'unevaluated_radial_integral','homotopy':homotopy}
    potential=homotopy['components'].get('','0')
    value=expression(potential,coordinates)[0];sp=sympy()
    residual={str(i):str(sp.simplify(sp.diff(value,sp.Symbol(x))-form.get((i,),0))) for i,x in enumerate(coordinates)}
    return {'closed':True,'potential':potential,'residual':residual,
            'exact_under_hypotheses':all(v=='0' for v in residual.values()),
            'hypotheses':homotopy['hypotheses']}


def metric_differential_operators(coordinates, metric, *, scalar=None, vector=None,
                                  covector=None):
    """Gradient, divergence, Hessian, wave/Laplace operator and covector curl."""
    geometry=MetricTensor(coordinates,metric);result={}
    if scalar is not None:
        result['gradient']=geometry.gradient(scalar).to_data()
        result['hessian']=geometry.hessian(scalar).to_data()
        result['laplace_beltrami']=geometry.laplace_beltrami(scalar)
    if vector is not None:
        value=TensorField.from_components(coordinates,[1],vector)
        result['divergence']=geometry.divergence(value).to_data()['components']
        derivative=geometry.covariant(value)
        result['covariant_derivative']=derivative.to_data()
    if covector is not None:
        if len(covector)!=geometry.dimension:raise ValueError('One covector component per coordinate required')
        components={str(i):v for i,v in enumerate(covector)}
        exterior=exterior_derivative(coordinates,components)
        result['exterior_derivative']=exterior
        if geometry.dimension==3:
            dual=hodge_star(coordinates,metric,exterior)['components']
            one_form=TensorField.from_components(coordinates,[-1],[dual.get(str(i),'0') for i in range(3)])
            result['curl']=geometry.change_index(one_form,0).to_data()
    if not result:raise ValueError('Supply at least one scalar, vector or covector')
    result['domain_hypothesis']=str(geometry.determinant)+' != 0; constant signature chart'
    return result


def canonical_stress_energy(lagrangian, coordinates, fields):
    """Canonical first-order field stress tensor and off-shell divergence identity.

    T^i_j = Σ_A ∂L/∂φ_A,i * φ_A,j − δ^i_j L. Translation conservation
    requires no explicit coordinate dependence and the field Euler–Lagrange
    equations. This tensor need not be symmetric or coincide with the Hilbert
    metric stress tensor; gauge-improved tensors require a separate choice.
    """
    coordinates=names(coordinates,3);fields=names(fields,2);sp=sympy();n=len(coordinates)
    first=[f'{f}_d{i}' for f in fields for i in range(n)]
    second=[f'{f}_d{i}d{j}' for f in fields for i in range(n) for j in range(i,n)]
    variables=list(coordinates)+list(fields)+first+second
    value,symbols=expression(lagrangian,variables);s=dict(zip(variables,symbols))
    if any(value.has(s[v]) for v in second):raise ValueError('Only first-order field Lagrangians supported')
    momenta={(f,i):sp.diff(value,s[f'{f}_d{i}']) for f in fields for i in range(n)}
    tensor=[[sp.simplify(sum(momenta[f,i]*s[f'{f}_d{j}'] for f in fields)-(value if i==j else 0))
             for j in range(n)] for i in range(n)]
    def total(source,i):
        out=sp.diff(source,s[coordinates[i]])
        for f in fields:
            out+=s[f'{f}_d{i}']*sp.diff(source,s[f])
            for j in range(n):
                a,b=sorted((i,j));out+=s[f'{f}_d{a}d{b}']*sp.diff(source,s[f'{f}_d{j}'])
        return sp.expand(out)
    equations={f:sp.simplify(sum(total(momenta[f,i],i) for i in range(n))-sp.diff(value,s[f])) for f in fields}
    divergence=[sp.simplify(sum(total(tensor[i][j],i) for i in range(n))) for j in range(n)]
    residual=[sp.simplify(divergence[j]-sum(equations[f]*s[f'{f}_d{j}'] for f in fields)
                          +sp.diff(value,s[coordinates[j]])) for j in range(n)]
    return {'tensor':[[str(v) for v in row] for row in tensor],
            'divergence':list(map(str,divergence)),'equations':{f:str(v) for f,v in equations.items()},
            'off_shell_identity_residual':list(map(str,residual)),
            'identity_verified':all(v==0 for v in residual),
            'translation_invariant':all(sp.diff(value,s[x])==0 for x in coordinates)}


def scalar_field_stress(coordinates, metric, field, potential='0', field_symbol='phi'):
    """Hilbert stress for a minimally coupled real scalar, signature (-,+,+,+)."""
    geometry=MetricTensor(coordinates,metric);sp=sympy();n=geometry.dimension
    if field_symbol in coordinates:raise ValueError('Potential field variable must differ from chart coordinates')
    phi=expression(field,coordinates)[0]
    potential_value,symbols=expression(potential,[field_symbol]);u=symbols[0]
    v=potential_value.subs(u,phi)
    gradient=[sp.diff(phi,x) for x in geometry.symbols]
    kinetic=sp.simplify(sum(geometry.inverse[i,j]*gradient[i]*gradient[j] for i in range(n) for j in range(n)))
    tensor=[[sp.simplify(gradient[i]*gradient[j]-geometry.metric[i,j]*(kinetic/2+v)) for j in range(n)] for i in range(n)]
    equation=sp.simplify(expression(geometry.laplace_beltrami(field),coordinates)[0]-sp.diff(potential_value,u).subs(u,phi))
    return {'stress_tensor':[[str(v) for v in row] for row in tensor],
            'kinetic_contraction':str(kinetic),'field_equation':str(equation),
            'lagrangian':str(-kinetic/2-v),
            'convention':'Real minimally coupled scalar; signature (-,+,+,+); c=1'}


def maxwell_field_stress(coordinates, metric, potential):
    """F=dA, source-free Maxwell divergence and Hilbert electromagnetic stress."""
    geometry=MetricTensor(coordinates,metric);sp=sympy();n=geometry.dimension
    if n!=4 or len(potential)!=4:raise ValueError('Maxwell stress API requires a four-dimensional chart and covector potential')
    values=[expression(v,coordinates)[0] for v in potential]
    field=sp.Matrix(4,4,lambda i,j:sp.diff(values[j],geometry.symbols[i])-sp.diff(values[i],geometry.symbols[j]))
    raised=geometry.inverse*field*geometry.inverse.T
    invariant=sp.simplify(sum(field[i,j]*raised[i,j] for i in range(4) for j in range(4)))
    stress=sp.Matrix(4,4,lambda i,j:sp.simplify(sum(field[i,a]*geometry.inverse[a,b]*field[j,b]
                          for a in range(4) for b in range(4))-geometry.metric[i,j]*invariant/4))
    tensor=TensorField(coordinates,(1,1),tuple(raised))
    divergence=geometry.divergence(tensor,0)
    return {'field':[[str(sp.simplify(v)) for v in row] for row in field.tolist()],
            'stress_tensor':[[str(v) for v in row] for row in stress.tolist()],
            'field_invariant':str(invariant),'source_free_residual':divergence.to_data()['components'],
            'bianchi_verified':not exterior_derivative(coordinates,{f'{i},{j}':str(field[i,j]) for i in range(4) for j in range(i+1,4)}),
            'convention':'F=dA; T_ij=F_ia F_j^a - g_ij F_ab F^ab/4; c=epsilon0=1'}


def perfect_fluid_stress(coordinates, metric, density, pressure, four_velocity):
    """T_ij=(rho+p)u_i u_j+p g_ij with checked symbolic u·u=-1."""
    geometry=MetricTensor(coordinates,metric);sp=sympy()
    if geometry.dimension!=4:raise ValueError('Perfect-fluid relativistic stress requires four dimensions')
    _,velocity=_vector(coordinates,four_velocity)
    norm=expression(geometry.inner_product(four_velocity,four_velocity),coordinates)[0]
    if sp.simplify(norm+1)!=0:raise ValueError('Four-velocity must satisfy the symbolic timelike unit constraint u.u=-1')
    rho=expression(density,coordinates)[0];p=expression(pressure,coordinates)[0]
    lower=geometry.metric*sp.Matrix(velocity)
    stress=(rho+p)*(lower*lower.T)+p*geometry.metric
    return {'stress_tensor':[[str(sp.simplify(v)) for v in row] for row in stress.tolist()],
            'four_velocity_norm':str(norm),'hypotheses':'rho and p are real; equation of state and conservation dynamics are separate'}


def adm_decomposition(coordinates, metric):
    """3+1 split with time coordinate first and K_ij=-1/2 L_n gamma_ij.

    α²>0 and positive-definite spatial γ must hold on the requested chart.
    Expressions alone do not certify those inequalities globally.
    """
    geometry=MetricTensor(coordinates,metric);sp=sympy()
    if geometry.dimension!=4:raise ValueError('ADM decomposition requires a four-dimensional metric')
    if geometry.inverse[0,0]==0:raise ValueError('Time foliation is null; ADM lapse is undefined')
    lapse_squared=sp.simplify(-1/geometry.inverse[0,0]);lapse=sp.sqrt(lapse_squared)
    spatial=geometry.metric[1:,1:]
    if sp.simplify(spatial.det())==0:raise ValueError('Spatial metric is degenerate')
    inverse=spatial.inv();shift=sp.Matrix([sp.simplify(-geometry.inverse[0,i]/geometry.inverse[0,0]) for i in range(1,4)])
    lower=spatial*shift;x=geometry.symbols[1:];gamma=[[[sp.simplify(sum(inverse[k,l]*(sp.diff(spatial[l,j],x[i])
                      +sp.diff(spatial[l,i],x[j])-sp.diff(spatial[i,j],x[l])) for l in range(3))/2)
                      for j in range(3)] for i in range(3)] for k in range(3)]
    covariant=lambda i,j:sp.diff(lower[j],x[i])-sum(gamma[k][i][j]*lower[k] for k in range(3))
    extrinsic=sp.Matrix(3,3,lambda i,j:sp.simplify((covariant(i,j)+covariant(j,i)-sp.diff(spatial[i,j],geometry.symbols[0]))/(2*lapse)))
    reconstruction=sp.zeros(4);reconstruction[0,0]=-lapse_squared+(shift.T*spatial*shift)[0]
    for i in range(3):
        reconstruction[0,i+1]=reconstruction[i+1,0]=lower[i]
        for j in range(3):reconstruction[i+1,j+1]=spatial[i,j]
    residual=(reconstruction-geometry.metric).applyfunc(sp.simplify)
    return {'lapse':str(lapse),'lapse_squared':str(lapse_squared),'shift':list(map(str,shift)),
            'spatial_metric':[[str(v) for v in row] for row in spatial.tolist()],
            'extrinsic_curvature':[[str(v) for v in row] for row in extrinsic.tolist()],
            'reconstruction_verified':all(v==0 for v in residual),
            'hypotheses':str(lapse_squared)+' > 0 and spatial metric positive definite'}


def hypersurface_geometry(coordinates, metric, parameters, embedding, normal_sign=1):
    """Induced metric and second fundamental form of a codimension-one immersion."""
    geometry=MetricTensor(coordinates,metric);sp=sympy();n=geometry.dimension
    parameters=names(parameters,3)
    if len(parameters)!=n-1 or len(embedding)!=n or set(parameters)&set(coordinates):
        raise ValueError('Codimension-one embedding needs distinct parameter names')
    if type(normal_sign) is not int or normal_sign not in (-1,1):raise ValueError('Unit normal squared sign must be +/-1')
    functions=[expression(v,parameters)[0] for v in embedding]
    u=tuple(map(sp.Symbol,parameters));sub=dict(zip(geometry.symbols,functions))
    jacobian=sp.Matrix(functions).jacobian(u);ambient=geometry.metric.subs(sub,simultaneous=True)
    induced=(jacobian.T*ambient*jacobian).applyfunc(sp.simplify)
    if sp.simplify(induced.det())==0:raise ValueError('Induced hypersurface metric is degenerate')
    kernel=(jacobian.T*ambient).nullspace()
    if len(kernel)!=1:raise ValueError('Immersion does not determine a one-dimensional normal space')
    normal=kernel[0];squared=sp.simplify((normal.T*ambient*normal)[0])
    if squared==0:raise ValueError('Hypersurface has a null normal')
    normal=normal/sp.sqrt(normal_sign*squared)
    gamma=[[[v.subs(sub,simultaneous=True) for v in row] for row in layer] for layer in geometry.christoffel]
    second=sp.zeros(n-1)
    for a in range(n-1):
        for b in range(n-1):
            acceleration=sp.Matrix([sp.diff(functions[j],u[a],u[b])+sum(gamma[j][k][l]*jacobian[k,a]*jacobian[l,b]
                                      for k in range(n) for l in range(n)) for j in range(n)])
            second[a,b]=sp.simplify((normal.T*ambient*acceleration)[0])
    shape=(induced.inv()*second).applyfunc(sp.simplify)
    return {'induced_metric':[[str(v) for v in row] for row in induced.tolist()],
            'normal':list(map(lambda v:str(sp.simplify(v)),normal)),
            'second_fundamental_form':[[str(v) for v in row] for row in second.tolist()],
            'shape_operator':[[str(v) for v in row] for row in shape.tolist()],
            'mean_curvature':str(sp.simplify(sp.trace(shape)/(n-1))),
            'gauss_kronecker_curvature':str(sp.simplify(shape.det())),
            'normal_valid_where':str(normal_sign*squared)+' > 0',
            'orientation':'Normal chosen from symbolic nullspace; reversing it reverses second fundamental form'}


__all__ += ['poincare_homotopy','conservative_potential','metric_differential_operators',
            'canonical_stress_energy','scalar_field_stress','maxwell_field_stress',
            'perfect_fluid_stress','adm_decomposition','hypersurface_geometry']


class SurfaceFiniteElements:
    """Piecewise-linear FEM on a finite embedded triangular two-manifold.

    Cotangent stiffness and lumped mass are assembled in vectorized NumPy and
    SciPy sparse kernels. The geometry is the supplied piecewise-flat surface;
    convergence to an unknown smooth surface is not inferred from mesh size.
    Scalar fields are represented at vertices, and isolated vertices are refused.
    """
    def __init__(self, vertices, triangles):
        import numpy as np
        from scipy.sparse import coo_matrix,diags
        points=np.asarray(vertices,dtype=float);faces=np.asarray(triangles)
        if points.ndim!=2 or points.shape[1]!=3 or not 3<=len(points)<=100000 or not np.isfinite(points).all():
            raise ValueError('Finite triangular surface needs 3–100000 XYZ vertices')
        if faces.ndim!=2 or faces.shape[1]!=3 or not 1<=len(faces)<=200000 or faces.dtype.kind not in 'iu':
            raise ValueError('Bounded integer triangle array required')
        if faces.min()<0 or faces.max()>=len(points) or np.any(np.diff(np.sort(faces,axis=1),axis=1)==0):
            raise ValueError('Triangle indices repeat or exceed the vertex array')
        a,b,c=points[faces[:,0]],points[faces[:,1]],points[faces[:,2]]
        double_area=np.linalg.norm(np.cross(b-a,c-a),axis=1)
        if np.any(double_area<=1e-14):raise ValueError('Degenerate surface triangles')
        self.vertices=points;self.triangles=faces;self.areas=double_area/2
        self.mass=np.zeros(len(points))
        for slot in range(3):np.add.at(self.mass,faces[:,slot],self.areas/3)
        if np.any(self.mass<=0):raise ValueError('Surface contains isolated vertices')
        cotangents=np.column_stack((np.einsum('ij,ij->i',b-a,c-a),
                                    np.einsum('ij,ij->i',a-b,c-b),
                                    np.einsum('ij,ij->i',a-c,b-c)))/double_area[:,None]
        rows=[];columns=[];entries=[];edges={}
        for opposite,(left,right) in enumerate(((1,2),(2,0),(0,1))):
            i,j=faces[:,left],faces[:,right];weight=cotangents[:,opposite]/2
            for r,col,value in ((i,i,weight),(j,j,weight),(i,j,-weight),(j,i,-weight)):
                rows.extend(r.tolist());columns.extend(col.tolist());entries.extend(value.tolist())
            for u,v in zip(i,j):
                edge=tuple(sorted((int(u),int(v))));edges[edge]=edges.get(edge,0)+1
        if any(count>2 for count in edges.values()):raise ValueError('Nonmanifold surface edge detected')
        self.edges=edges;self.boundary=sorted({v for edge,count in edges.items() if count==1 for v in edge})
        self.stiffness=coo_matrix((entries,(rows,columns)),shape=(len(points),len(points))).tocsr()
        self.mass_matrix=diags(self.mass,format='csr')
        self.laplacian=-diags(1/self.mass)@self.stiffness

    def _field(self, values):
        import numpy as np
        field=np.asarray(values,dtype=float)
        if field.shape!=(len(self.vertices),) or not np.isfinite(field).all():
            raise ValueError('One finite scalar field value per surface vertex required')
        return field

    def integrate(self, values):
        return float(self.mass@self._field(values))

    def gradient(self, values):
        """Constant tangential gradient in each triangle, in ambient XYZ."""
        import numpy as np
        value=self._field(values);faces=self.triangles
        a,b,c=(self.vertices[faces[:,i]] for i in range(3))
        normals=np.cross(b-a,c-a);squared=np.einsum('ij,ij->i',normals,normals)
        gradients=[np.cross(normals,c-b)/squared[:,None],
                   np.cross(normals,a-c)/squared[:,None],
                   np.cross(normals,b-a)/squared[:,None]]
        result=sum(value[faces[:,i],None]*gradients[i] for i in range(3))
        return result.tolist()

    def dirichlet_energy(self, values):
        field=self._field(values)
        return float(field@(self.stiffness@field)/2)

    def apply_laplacian(self, values):
        return (self.laplacian@self._field(values)).tolist()

    def poisson(self, forcing, *, dirichlet=None, zero_mean=False):
        """Solve -Δu=f; use explicit Dirichlet data or a compatible mean-zero gauge."""
        import numpy as np
        from scipy.sparse import bmat,csr_matrix
        from scipy.sparse.linalg import spsolve
        field=self._field(forcing);rhs=self.mass*field;n=len(field)
        constraints={} if dirichlet is None else dict(dirichlet)
        if any(type(i) is not int or not 0<=i<n or type(v) not in (int,float) or not np.isfinite(v) for i,v in constraints.items()):
            raise ValueError('Finite Dirichlet values keyed by integer vertex required')
        if constraints and zero_mean:raise ValueError('Choose Dirichlet conditions or zero-mean gauge')
        if constraints:
            fixed=np.asarray(sorted(constraints),dtype=int);free=np.asarray([i for i in range(n) if i not in constraints],dtype=int)
            values=np.zeros(n);values[fixed]=[constraints[i] for i in fixed]
            if len(free):
                adjusted=rhs[free]-self.stiffness[free][:,fixed]@values[fixed]
                values[free]=spsolve(self.stiffness[free][:,free],adjusted)
            residual=(self.stiffness@values-rhs)[free]
        elif zero_mean:
            from scipy.sparse.csgraph import connected_components
            adjacency=self.stiffness.copy();adjacency.data=np.ones_like(adjacency.data)
            components,_=connected_components(adjacency,directed=False)
            if components!=1:raise ValueError('Mean-zero gauge currently requires a connected surface')
            if abs(rhs.sum())>1e-10*max(1,float(np.linalg.norm(rhs,1))):raise ValueError('Neumann/closed Poisson forcing has nonzero total mass')
            column=csr_matrix(self.mass[:,None]);system=bmat([[self.stiffness,column],[column.T,None]],format='csr')
            solution=spsolve(system,np.concatenate((rhs,[0.])))
            values=solution[:-1];residual=self.stiffness@values-rhs
        else:raise ValueError('Poisson needs Dirichlet data or an explicit mean-zero gauge')
        if not np.isfinite(values).all():raise ArithmeticError('Surface Poisson system is singular or nonfinite')
        return {'values':values.tolist(),'residual_norm':float(np.linalg.norm(residual)),
                'weighted_mean':float(self.mass@values/self.mass.sum()),
                'scope':'Discrete linear FEM solution; no continuum error certificate'}

    def heat(self, initial, duration=1., steps=100, *, method='implicit'):
        """Mass-conserving heat flow with implicit Euler or matrix-exponential time."""
        import numpy as np
        from scipy.sparse.linalg import factorized,expm_multiply
        value=self._field(initial)
        if not 0<duration<=10000 or type(steps) is not int or not 1<=steps<=10000 or len(value)*steps>2000000:
            raise ValueError('Surface heat history budget exceeded')
        if method not in ('implicit','exponential'):raise ValueError('Heat method is implicit or exponential')
        dt=duration/steps
        if method=='exponential':history=expm_multiply(self.laplacian,value,start=0,stop=duration,num=steps+1,endpoint=True)
        else:
            solve=factorized((self.mass_matrix+dt*self.stiffness).tocsc())
            history=np.empty((steps+1,len(value)));history[0]=value
            for i in range(steps):history[i+1]=solve(self.mass*history[i])
        if not np.isfinite(history).all():raise ArithmeticError('Surface heat flow became nonfinite')
        masses=history@self.mass;energy=[self.dirichlet_energy(row) for row in history]
        return {'times':np.linspace(0,duration,steps+1).tolist(),'values':history.tolist(),
                'mass':masses.tolist(),'maximum_mass_drift':float(np.max(abs(masses-masses[0]))),
                'dirichlet_energy':energy,'method':method,
                'positivity_scope':'Obtuse triangulations need not define an M-matrix; no unconditional pointwise positivity claim'}

    def spectrum(self, count=6):
        """Smallest generalized eigenpairs Kφ=λMφ with residuals and M-Gram matrix."""
        import numpy as np
        from scipy.sparse.linalg import eigsh
        n=len(self.vertices)
        if type(count) is not int or not 1<=count<min(n,65):raise ValueError('Eigenpair count must be 1–64 and below vertex count')
        values,vectors=eigsh(self.stiffness,k=count,M=self.mass_matrix,sigma=-1e-8,which='LM')
        order=np.argsort(values);values=values[order];vectors=vectors[:,order]
        residual=self.stiffness@vectors-(self.mass[:,None]*vectors)*values
        return {'eigenvalues':values.tolist(),'eigenvectors':vectors.T.tolist(),
                'residual_norms':np.linalg.norm(residual,axis=0).tolist(),
                'mass_gram':(vectors.T@(self.mass[:,None]*vectors)).tolist(),
                'scope':'Discrete surface spectrum, floating-point residuals only'}

    def graph_distance(self, source):
        """Edge-path distance, an upper bound on the piecewise-flat geodesic distance."""
        import numpy as np
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import dijkstra
        if type(source) is not int or not 0<=source<len(self.vertices):raise ValueError('Valid source vertex required')
        rows=[];columns=[];weights=[]
        for a,b in self.edges:
            length=float(np.linalg.norm(self.vertices[a]-self.vertices[b]))
            rows.extend((a,b));columns.extend((b,a));weights.extend((length,length))
        graph=coo_matrix((weights,(rows,columns)),shape=(len(self.vertices),)*2).tocsr()
        distances=dijkstra(graph,directed=False,indices=source)
        return {'distances':[float(v) if np.isfinite(v) else None for v in distances],
                'source':source,'scope':'Shortest edge paths; not an exact smooth-manifold geodesic solver'}

    def de_rham_incidence(self):
        """Exact integer incidence matrices and the discrete d²=0 check."""
        import numpy as np
        from scipy.sparse import coo_matrix
        edges=sorted(self.edges);positions={edge:i for i,edge in enumerate(edges)}
        rows=[];columns=[];values=[]
        for i,(a,b) in enumerate(edges):
            rows.extend((i,i));columns.extend((a,b));values.extend((-1,1))
        d0=coo_matrix((values,(rows,columns)),shape=(len(edges),len(self.vertices)),dtype=np.int64).tocsr()
        rows=[];columns=[];values=[]
        for i,face in enumerate(self.triangles):
            for a,b in ((face[0],face[1]),(face[1],face[2]),(face[2],face[0])):
                edge=tuple(sorted((int(a),int(b))))
                rows.append(i);columns.append(positions[edge]);values.append(1 if a<b else -1)
        d1=coo_matrix((values,(rows,columns)),shape=(len(self.triangles),len(edges)),dtype=np.int64).tocsr()
        residual=d1@d0;residual.eliminate_zeros()
        def triplets(matrix):
            coordinates=matrix.tocoo()
            return [[int(i),int(j),int(v)] for i,j,v in zip(coordinates.row,coordinates.col,coordinates.data)]
        return {'d0':triplets(d0),'d1':triplets(d1),'shapes':[list(d0.shape),list(d1.shape)],
                'nilpotent':residual.nnz==0,'verification':'Exact integer matrix product on this finite triangulation'}


def surface_fem(vertices, triangles, operation, values=None, duration=1., steps=100,
                source=0, count=6, dirichlet=None, zero_mean=False):
    model=SurfaceFiniteElements(vertices,triangles)
    if dirichlet is not None:
        dirichlet={int(key):value for key,value in dirichlet.items()}
    if operation=='heat':return model.heat(values,duration,steps)
    if operation=='poisson':return model.poisson(values,dirichlet=dirichlet,zero_mean=zero_mean)
    if operation=='gradient':return {'gradient':model.gradient(values)}
    if operation=='spectrum':return model.spectrum(count)
    if operation=='distance':return model.graph_distance(source)
    if operation=='incidence':return model.de_rham_incidence()
    if operation=='integral':return {'integral':model.integrate(values),'energy':model.dirichlet_energy(values)}
    raise ValueError('Unsupported surface FEM operation')


__all__ += ['SurfaceFiniteElements','surface_fem']


def manifold_tensor(coordinates, variance, components, kind, metric=None, slots=None,
                    scalar=1, other=None, other_variance=None):
    return tensor_calculus(coordinates,variance,components,kind,metric=metric,slots=slots,
                           scalar=scalar,other=other,other_variance=other_variance)


def manifold_surface_fem(vertices, triangles, kind, values=None, duration=1., steps=100,
                         source=0, count=6, dirichlet=None, zero_mean=False):
    return surface_fem(vertices,triangles,kind,values,duration,steps,source,count,dirichlet,zero_mean)


__all__ += ['manifold_tensor','manifold_surface_fem']


class OrthonormalFrame:
    """Moving orthonormal frame, Cartan connection and structure equations.

    Columns of frame are vector components E_a^i; the inverse matrix contains
    coframe coefficients theta^a_i. The declared signature is checked as an
    exact symbolic identity E^T g E=diag(signature) on the chart domain.
    """
    def __init__(self, coordinates, metric, frame, signature):
        self.geometry=MetricTensor(coordinates,metric);n=self.geometry.dimension;sp=sympy()
        if _tensor_shape(frame)!=(n,n) or not isinstance(signature,(list,tuple)) or len(signature)!=n or any(type(v) is not int or v not in (-1,1) for v in signature):
            raise ValueError('Square frame and one signature sign per dimension required')
        matrix=sp.Matrix([[expression(v,coordinates)[0] for v in row] for row in frame])
        if sp.simplify(matrix.det())==0:raise ValueError('Frame is identically singular')
        eta=sp.diag(*signature);residual=(matrix.T*self.geometry.metric*matrix-eta).applyfunc(sp.simplify)
        if any(v!=0 for v in residual):raise ValueError('Frame is not orthonormal with the declared signature')
        self.frame=sp.ImmutableMatrix(matrix);self.coframe=sp.ImmutableMatrix(matrix.inv());self.signature=tuple(signature)

    @cached_property
    def connection(self):
        sp=sympy();n=self.geometry.dimension;coordinates=self.geometry.symbols;gamma=self.geometry.christoffel
        result=[]
        for i in range(n):
            derivative=sp.zeros(n)
            for j in range(n):
                for b in range(n):derivative[j,b]=sp.diff(self.frame[j,b],coordinates[i])+sum(gamma[j][i][k]*self.frame[k,b] for k in range(n))
            result.append(sp.ImmutableMatrix((self.coframe*derivative).applyfunc(sp.simplify)))
        return tuple(result)

    def structure_constants(self):
        sp=sympy();n=self.geometry.dimension;x=self.geometry.symbols;values=[]
        for a in range(n):
            layer=[]
            for b in range(n):
                row=[]
                for c in range(n):
                    bracket=[sum(self.frame[k,b]*sp.diff(self.frame[j,c],x[k])-self.frame[k,c]*sp.diff(self.frame[j,b],x[k]) for k in range(n)) for j in range(n)]
                    row.append(str(sp.simplify(sum(self.coframe[a,j]*bracket[j] for j in range(n)))))
                layer.append(row)
            values.append(layer)
        return {'components':values,'convention':'[E_b,E_c] = C^a_bc E_a'}

    def metric_skew_symmetry(self):
        sp=sympy();eta=sp.diag(*self.signature);residual=[]
        for matrix in self.connection:residual.append((eta*matrix+matrix.T*eta).applyfunc(sp.simplify))
        return {'verified':all(v==0 for matrix in residual for v in matrix),
                'residual':[[[str(v) for v in row] for row in matrix.tolist()] for matrix in residual]}

    def cartan_torsion(self):
        sp=sympy();n=self.geometry.dimension;x=self.geometry.symbols;result={}
        for a in range(n):
            components={}
            for i in range(n):
                for j in range(i+1,n):
                    value=sp.diff(self.coframe[a,j],x[i])-sp.diff(self.coframe[a,i],x[j])
                    value+=sum(self.connection[i][a,b]*self.coframe[b,j]-self.connection[j][a,b]*self.coframe[b,i] for b in range(n))
                    value=sp.simplify(value)
                    if value!=0:components[f'{i},{j}']=str(value)
            result[str(a)]=components
        return {'components':result,'torsion_free':not any(result.values()),'identity':'d theta + omega wedge theta = 0'}

    def curvature_forms(self):
        sp=sympy();n=self.geometry.dimension;x=self.geometry.symbols;result={}
        for i in range(n):
            for j in range(i+1,n):
                value=self.connection[j].diff(x[i])-self.connection[i].diff(x[j])
                value+=self.connection[i]*self.connection[j]-self.connection[j]*self.connection[i]
                result[f'{i},{j}']=[[str(sp.simplify(v)) for v in row] for row in value.tolist()]
        return {'components':result,'identity':'Omega=d omega+omega wedge omega'}

    def change_frame(self, transformation):
        sp=sympy();n=self.geometry.dimension
        if _tensor_shape(transformation)!=(n,n):raise ValueError('Frame transformation dimension mismatch')
        matrix=sp.Matrix([[expression(v,self.geometry.coordinates)[0] for v in row] for row in transformation])
        eta=sp.diag(*self.signature)
        if any(v!=0 for v in (matrix.T*eta*matrix-eta).applyfunc(sp.simplify)):
            raise ValueError('Transformation does not preserve the declared frame signature')
        frame=self.frame*matrix
        return OrthonormalFrame(self.geometry.coordinates,
                                [[str(v) for v in row] for row in self.geometry.metric.tolist()],
                                [[str(sp.simplify(v)) for v in row] for row in frame.tolist()],self.signature)

    def to_data(self):
        return {'frame':[[str(v) for v in row] for row in self.frame.tolist()],
                'coframe':[[str(v) for v in row] for row in self.coframe.tolist()],
                'signature':list(self.signature),
                'connection':[[[str(v) for v in row] for row in matrix.tolist()] for matrix in self.connection],
                'domain_hypothesis':str(sympy().simplify(self.frame.det()))+' != 0'}


class SpinConnection:
    """Four-dimensional (-,+,+,+) Clifford representation and spin connection.

    This is a local spin-frame calculation. Existence/choice of a global spin
    structure, quantum boundary conditions and field normalization are separate
    geometric and physical inputs, never inferred from a tetrad in one chart.
    """
    def __init__(self, frame):
        if not isinstance(frame,OrthonormalFrame) or frame.signature!=(-1,1,1,1):
            raise ValueError('Spin connection currently requires a (-,+,+,+) orthonormal tetrad')
        self.frame=frame;sp=sympy();i=sp.I
        sigma=[sp.Matrix([[0,1],[1,0]]),sp.Matrix([[0,-i],[i,0]]),sp.Matrix([[1,0],[0,-1]])]
        zero=sp.zeros(2);gamma0=sp.diag(1,1,-1,-1)
        gammas=[i*gamma0]
        for matrix in sigma:
            gammas.append(i*sp.Matrix.vstack(sp.Matrix.hstack(zero,matrix),sp.Matrix.hstack(-matrix,zero)))
        self.gamma=tuple(sp.ImmutableMatrix(value) for value in gammas)
        self._verify_clifford()

    def _verify_clifford(self):
        sp=sympy();identity=sp.eye(4)
        for a in range(4):
            for b in range(4):
                expected=2*self.frame.signature[a]*identity if a==b else sp.zeros(4)
                if self.gamma[a]*self.gamma[b]+self.gamma[b]*self.gamma[a]!=expected:
                    raise ArithmeticError('Clifford anticommutation verification failed')
        return True

    @cached_property
    def connection(self):
        sp=sympy();result=[]
        for omega in self.frame.connection:
            matrix=sp.zeros(4)
            for a in range(4):
                for b in range(4):matrix+=self.frame.signature[a]*omega[a,b]*self.gamma[a]*self.gamma[b]/4
            result.append(sp.ImmutableMatrix(matrix.applyfunc(sp.simplify)))
        return tuple(result)

    def curved_gamma(self):
        sp=sympy();result=[]
        for coordinate in range(4):
            matrix=sp.zeros(4)
            for a in range(4):matrix+=self.frame.frame[coordinate,a]*self.gamma[a]
            result.append(sp.ImmutableMatrix(matrix.applyfunc(sp.simplify)))
        return tuple(result)

    def compatibility(self):
        sp=sympy();gamma=self.curved_gamma();geometry=self.frame.geometry;failures=[]
        for derivative in range(4):
            for coordinate in range(4):
                value=gamma[coordinate].diff(geometry.symbols[derivative])
                value+=sum((geometry.christoffel[coordinate][derivative][j]*gamma[j] for j in range(4)),sp.zeros(4))
                value+=self.connection[derivative]*gamma[coordinate]-gamma[coordinate]*self.connection[derivative]
                simplified=value.applyfunc(sp.simplify)
                if any(v!=0 for v in simplified):failures.append({'derivative':derivative,'coordinate':coordinate,
                    'residual':[[str(v) for v in row] for row in simplified.tolist()]})
        return {'verified':not failures,'failures':failures,'identity':'Covariant constancy of curved Clifford matrices'}

    def dirac_operator(self, components, *, mass=0, imaginary_prefactor=False):
        sp=sympy();coordinates=self.frame.geometry.coordinates
        if not isinstance(components,(list,tuple)) or len(components)!=4:raise ValueError('Four closed-expression spinor components required')
        if type(imaginary_prefactor) is not bool:raise ValueError('imaginary_prefactor must be boolean')
        spinor=sp.Matrix([expression(v,coordinates)[0] for v in components])
        scalar=expression(mass,coordinates)[0];gamma=self.curved_gamma();result=sp.zeros(4,1)
        for i,x in enumerate(self.frame.geometry.symbols):result+=gamma[i]*(spinor.diff(x)+self.connection[i]*spinor)
        if imaginary_prefactor:result=sp.I*result
        result+=scalar*spinor
        return {'components':[str(sp.simplify(v)) for v in result],
                'convention':('i*gamma^mu*nabla_mu + mass' if imaginary_prefactor else 'gamma^mu*nabla_mu + mass'),
                'clifford_signature':[-1,1,1,1],
                'scope':'Formal local spinor differential operator; physical sign/action convention is explicit'}


def second_bianchi_identity(coordinates, metric):
    """Finite exact symbolic verification of ∇_[e R^a_|b|cd]=0."""
    geometry=MetricTensor(coordinates,metric);n=geometry.dimension;sp=sympy()
    tensor=TensorField(geometry.coordinates,(1,-1,-1,-1),
                       tuple(geometry.riemann[a][b][c][d] for a,b,c,d in _indices(n,4)))
    derivative=geometry.covariant(tensor);failures=[]
    for a,b,c,d,e in _indices(n,5):
        value=sp.simplify(derivative.at((a,b,c,d,e))+derivative.at((a,b,d,e,c))+derivative.at((a,b,e,c,d)))
        if value!=0:failures.append({'indices':[a,b,c,d,e],'residual':str(value)})
    return {'verified':not failures,'residuals':failures,'formal_kernel_verified':False,
            'hypotheses':'Metric C3 and nonsingular on the coordinate chart'}


__all__ += ['OrthonormalFrame','SpinConnection','second_bianchi_identity']


class HamiltonianSystem:
    """Canonical Hamiltonian calculus and fixed-step symplectic midpoint flow."""
    def __init__(self, hamiltonian, positions, momenta, *, time='t'):
        self.positions=names(positions,4);self.momenta=names(momenta,4)
        if len(self.positions)!=len(self.momenta):raise ValueError('Equal numbers of position/momentum variables required')
        self.variables=names(list(self.positions)+list(self.momenta)+[time],9);self.time=time
        self.hamiltonian,self.symbols=expression(hamiltonian,self.variables)
        self.dimension=len(self.positions);self.phase_symbols=self.symbols[:-1]
        sp=sympy();n=self.dimension
        self.symplectic=sp.zeros(2*n)
        for i in range(n):self.symplectic[i,n+i]=1;self.symplectic[n+i,i]=-1
        self.gradient=sp.Matrix([sp.diff(self.hamiltonian,x) for x in self.phase_symbols])
        self.vector_field=(self.symplectic*self.gradient).applyfunc(sp.simplify)
        self.jacobian=self.vector_field.jacobian(self.phase_symbols)

    def poisson_bracket(self, left, right):
        sp=sympy();a=expression(left,self.variables)[0];b=expression(right,self.variables)[0];n=self.dimension
        return sp.simplify(sum(sp.diff(a,self.phase_symbols[i])*sp.diff(b,self.phase_symbols[n+i])
                              -sp.diff(a,self.phase_symbols[n+i])*sp.diff(b,self.phase_symbols[i]) for i in range(n)))

    def first_integral(self, source):
        sp=sympy();value=expression(source,self.variables)[0]
        derivative=sp.simplify(sp.diff(value,self.symbols[-1])+self.poisson_bracket(source,str(self.hamiltonian)))
        return {'flow_derivative':str(derivative),'conserved_under_hypotheses':derivative==0,
                'scope':'Symbolic local first integral under the Hamilton equations and smoothness hypotheses'}

    def liouville_identity(self):
        residual=sympy().simplify(sum(sympy().diff(self.vector_field[i],x) for i,x in enumerate(self.phase_symbols)))
        return {'phase_space_divergence':str(residual),'zero':residual==0,
                'hypotheses':'Canonical chart; Hamiltonian twice continuously differentiable'}

    def dirac_bracket(self, left, right, constraints):
        sp=sympy()
        if not isinstance(constraints,(list,tuple)) or not 1<=len(constraints)<=8:
            raise ValueError('1–8 second-class constraint expressions required')
        parsed=[expression(v,self.variables)[0] for v in constraints]
        matrix=sp.Matrix(len(parsed),len(parsed),lambda i,j:self.poisson_bracket(str(parsed[i]),str(parsed[j])))
        determinant=sp.simplify(matrix.det())
        if determinant==0:raise ValueError('Constraint Poisson matrix is singular; constraints are not second class on this chart')
        first=sp.Matrix([[self.poisson_bracket(left,str(v)) for v in parsed]])
        second=sp.Matrix([self.poisson_bracket(str(v),right) for v in parsed])
        bracket=sp.simplify(self.poisson_bracket(left,right)-(first*matrix.inv()*second)[0])
        return {'bracket':str(bracket),'constraint_matrix':[[str(v) for v in row] for row in matrix.tolist()],
                'valid_where':str(determinant)+' != 0','scope':'Local Dirac bracket for second-class constraints, no global reduction or gauge fixing'}

    def canonical_map(self, mapping):
        sp=sympy();n=2*self.dimension
        if not isinstance(mapping,(list,tuple)) or len(mapping)!=n:raise ValueError('One transformed phase coordinate per dimension required')
        transformed=sp.Matrix([expression(v,self.variables)[0] for v in mapping])
        jacobian=transformed.jacobian(self.phase_symbols)
        residual=(jacobian*self.symplectic*jacobian.T-self.symplectic).applyfunc(sp.simplify)
        return {'canonical':all(v==0 for v in residual),
                'jacobian':[[str(v) for v in row] for row in jacobian.tolist()],
                'residual':[[str(v) for v in row] for row in residual.tolist()],
                'scope':'Local time-slice symplectic condition; global invertibility/time-dependent generating terms are separate'}

    def midpoint(self, initial, duration=1., steps=1000, *, tolerance=1e-10,
                 max_newton_iterations=30):
        import numpy as np
        from scipy.optimize import root
        n=2*self.dimension
        state=np.asarray(initial,dtype=float)
        if state.shape!=(n,) or not np.isfinite(state).all():raise ValueError('Finite canonical phase-space initial state required')
        if not 0<duration<=10000 or type(steps) is not int or not 1<=steps<=100000 or steps*n>1000000:
            raise ValueError('Hamiltonian integration budget exceeded')
        if not 0<tolerance<.1 or type(max_newton_iterations) is not int or not 1<=max_newton_iterations<=100:
            raise ValueError('Invalid implicit-solver tolerance/budget')
        field=sympy().lambdify(self.symbols,self.vector_field,modules='numpy',cse=True)
        jacobian=sympy().lambdify(self.symbols,self.jacobian,modules='numpy',cse=True)
        energy=sympy().lambdify(self.symbols,self.hamiltonian,modules='numpy',cse=True)
        dt=duration/steps;history=[state.copy()];energies=[float(energy(*state,0.))];residuals=[];symplectic_errors=[]
        canonical=np.asarray(self.symplectic,dtype=float);identity=np.eye(n)
        for step in range(steps):
            time=(step+.5)*dt
            def residual(candidate):
                midpoint=(state+candidate)/2
                value=np.asarray(field(*midpoint,time),dtype=float).reshape(n)
                if not np.isfinite(value).all():raise ArithmeticError('Hamiltonian vector field is nonfinite')
                return candidate-state-dt*value
            def derivative(candidate):
                midpoint=(state+candidate)/2
                matrix=np.asarray(jacobian(*midpoint,time),dtype=float)
                return identity-dt*matrix/2
            predictor=state+dt*np.asarray(field(*state,step*dt),dtype=float).reshape(n)
            solved=root(residual,predictor,jac=derivative,method='hybr',options={'xtol':tolerance,'maxfev':max_newton_iterations*(n+1)})
            error=float(np.linalg.norm(residual(solved.x),ord=np.inf))
            if not np.isfinite(solved.x).all() or error>tolerance*max(1,float(np.linalg.norm(solved.x,ord=np.inf))):
                raise ArithmeticError('Implicit Hamiltonian midpoint step did not converge at index '+str(step))
            middle=(state+solved.x)/2;linear=np.asarray(jacobian(*middle,time),dtype=float)
            tangent=np.linalg.solve(identity-dt*linear/2,identity+dt*linear/2)
            symplectic_errors.append(float(np.linalg.norm(tangent.T@canonical@tangent-canonical,ord=np.inf)))
            state=solved.x;history.append(state.copy());residuals.append(error);energies.append(float(energy(*state,(step+1)*dt)))
        if not np.isfinite(energies).all():raise ArithmeticError('Hamiltonian energy became nonfinite')
        return {'times':np.linspace(0,duration,steps+1).tolist(),'states':[row.tolist() for row in history],
                'energy':energies,'maximum_energy_drift':max(abs(v-energies[0]) for v in energies),
                'maximum_step_residual':max(residuals),'maximum_symplectic_residual':max(symplectic_errors),
                'method':'Fixed-step implicit midpoint','tolerance':tolerance,
                'scope':'Observed floating residuals; symplectic structure does not imply exact energy conservation for a general Hamiltonian'}


def holonomy_loop(coordinates, metric, path, *, duration=1., parameter='s',
                  closure_tolerance=1e-9):
    """Parallel-transport every basis vector around a closed coordinate loop."""
    import numpy as np
    geometry=MetricTensor(coordinates,metric);n=geometry.dimension
    if not 0<closure_tolerance<.1:raise ValueError('Positive closure tolerance required')
    columns=[];start=end=None;drifts=[]
    for i in range(n):
        basis=[int(i==j) for j in range(n)]
        result=parallel_transport_curve(coordinates,metric,path,basis,duration,samples=3,parameter=parameter)
        start=np.asarray(result['positions'][0]);end=np.asarray(result['positions'][-1])
        columns.append(result['vectors'][-1]);drifts.append(result['maximum_norm_drift'])
    gap=float(np.linalg.norm(end-start))
    if gap>closure_tolerance:raise ValueError('Path is not a closed loop within the declared coordinate tolerance')
    transport=np.asarray(columns).T
    g=np.asarray(geometry.at(dict(zip(coordinates,start.tolist()))),dtype=float)
    defect=transport.T@g@transport-g
    return {'holonomy':transport.tolist(),'closure_gap':gap,
            'metric_preservation_residual':float(np.linalg.norm(defect)),
            'column_norm_drifts':drifts,'scope':'Numerical local-chart holonomy; no homotopy classification or global atlas transport'}


__all__ += ['HamiltonianSystem','holonomy_loop']


class SymplecticGeometry:
    """Closed nondegenerate two-forms in one finite-dimensional coordinate chart.

    The inverse convention is X_H^i=(omega^-1)^ij partial_j H. A canonical
    matrix with upper-right identity therefore gives X_H=(-H_p,H_q).
    Choose its negative when using the HamiltonianSystem convention.
    """

    def __init__(self, coordinates, coefficients):
        self.coordinates = names(coordinates, 4)
        dimension = len(self.coordinates)
        if dimension % 2:
            raise ValueError('A symplectic chart has even dimension')
        if not isinstance(coefficients, (list, tuple)) or len(coefficients) != dimension:
            raise ValueError('Square two-form coefficient matrix required')
        if any(len(row) != dimension for row in coefficients):
            raise ValueError('Two-form matrix shape mismatch')
        sp = sympy()
        self.symbols = tuple(map(sp.Symbol, self.coordinates))
        matrix = sp.Matrix([[expression(value, self.coordinates)[0] for value in row]
                            for row in coefficients])
        if any(sp.simplify(value) != 0 for value in matrix + matrix.T):
            raise ValueError('Two-form coefficient matrix must be skew-symmetric')
        self.matrix = sp.ImmutableMatrix(matrix)
        self.determinant = sp.simplify(matrix.det())
        if self.determinant == 0:
            raise ValueError('Symplectic form is degenerate')
        self.inverse = sp.ImmutableMatrix(matrix.inv().applyfunc(sp.simplify))
        self.form = {','.join(map(str, (i, j))): str(matrix[i, j])
                     for i in range(dimension) for j in range(i+1, dimension)
                     if matrix[i, j] != 0}
        if exterior_derivative(self.coordinates, self.form):
            raise ValueError('Symplectic two-form must be closed on the chart')

    def hamiltonian_vector(self, hamiltonian):
        sp = sympy()
        scalar = expression(hamiltonian, self.coordinates)[0]
        gradient = sp.Matrix([sp.diff(scalar, variable) for variable in self.symbols])
        vector = (self.inverse * gradient).applyfunc(sp.simplify)
        return {'components': list(map(str, vector)),
                'chart_hypothesis': str(self.determinant) + ' != 0'}

    def bracket(self, left, right):
        sp = sympy()
        a = expression(left, self.coordinates)[0]
        b = expression(right, self.coordinates)[0]
        da = sp.Matrix([sp.diff(a, variable) for variable in self.symbols])
        db = sp.Matrix([sp.diff(b, variable) for variable in self.symbols])
        return sp.simplify((da.T * self.inverse * db)[0])

    def preserves(self, vector):
        values = _vector(self.coordinates, vector)[1]
        components = lie_derivative(self.coordinates, list(map(str, values)), self.form)
        return {'lie_derivative': components, 'preserves_two_form': not components,
                'scope': 'Symbolic local identity under smoothness hypotheses'}

    def pullback(self, new_coordinates, mapping):
        new_coordinates = names(new_coordinates, 4)
        if len(mapping) != len(self.coordinates):
            raise ValueError('One chart map component per original coordinate required')
        sp = sympy()
        parsed = sp.Matrix([expression(value, new_coordinates)[0] for value in mapping])
        jacobian = parsed.jacobian(list(map(sp.Symbol, new_coordinates)))
        substitution = dict(zip(self.symbols, parsed))
        evaluated = self.matrix.subs(substitution, simultaneous=True)
        result = (jacobian.T * evaluated * jacobian).applyfunc(sp.simplify)
        return SymplecticGeometry(new_coordinates, [list(map(str, row)) for row in result.tolist()])

    def to_data(self):
        return {'coordinates': list(self.coordinates), 'matrix': self.matrix.applyfunc(str).tolist(),
                'determinant': str(self.determinant), 'closed': True,
                'nondegeneracy_hypothesis': str(self.determinant) + ' != 0'}


__all__ += ['SymplecticGeometry']
