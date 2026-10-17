"""Unweighted combinatorial Hodge Laplacians and exact harmonic projection (58)."""
from fractions import Fraction
from ..math.topology.homology import SimplicialComplex
from ._area_utils import vector,nullspace,calculate as _calculate
from .functional_analysis import functional_analysis


def global_analysis(facets, *, degree=0, form=None):
    if not isinstance(facets,list) or not 1<=len(facets)<=64 or any(not isinstance(face,list) or not 1<=len(face)<=4 or any(type(v) is not int or v<0 for v in face) or len(set(face))!=len(face) for face in facets):
        raise ValueError('Require a finite simplicial complex of dimension at most three')
    if type(degree) is not int or not 0<=degree<=3:raise ValueError('Invalid cochain degree')
    complex_ = SimplicialComplex(facets);cells = complex_.cells(degree);n = len(cells)
    if len(complex_.simplices)>128 or n>32:raise ValueError('Hodge profile exceeds its exact elimination budget')
    lower,upper = complex_.boundary_matrix(degree),complex_.boundary_matrix(degree+1)
    laplacian = [[sum((row[i]*row[j] for row in lower),Fraction(0))+
                  sum((upper[i][k]*upper[j][k] for k in range(len(upper[0]))),Fraction(0))
                  if upper else sum((row[i]*row[j] for row in lower),Fraction(0))
                  for j in range(n)] for i in range(n)]
    basis = nullspace(laplacian,n)
    values = [Fraction(0)]*n if form is None else vector(form,maximum=32,minimum=0)
    if len(values)!=n:raise ValueError('Cochain and cell dimensions differ')
    harmonic = functional_analysis(basis,values)['projection'] if basis else [Fraction(0)]*n
    return {'cells':[list(cell) for cell in cells],'laplacian':laplacian,'harmonic_basis':basis,
            'harmonic_projection':harmonic,'harmonic_dimension':len(basis),
            'betti_number':complex_.betti_number(degree),'boundary_squared_zero':complex_.verify_boundary_squared_zero(),
            'scope':'Finite unweighted simplicial Hodge theory, not a smooth manifold elliptic solver.'}


def calculate(**arguments):return _calculate('global_analysis',**arguments)


def de_rham_derivative(coordinates,components):
    from ..math.geometry.differential_forms import exterior_derivative
    derivative=exterior_derivative(coordinates,components)
    return {'derivative':derivative,'d_squared':exterior_derivative(coordinates,derivative),
            'scope':'Coordinate de Rham differential on the supplied smooth expression chart.'}


def weighted_hodge(facets,degree,weights):
    from ..math._structured import rational_matrix,sympy,data
    sp=sympy();c=SimplicialComplex(facets)
    if len(c.simplices)>128 or not 0<=degree<=3:raise ValueError('Weighted Hodge budget exceeded')
    ns=[len(c.cells(k)) for k in range(c.dimension+1)]
    if degree>=len(ns) or len(weights)!=len(ns):raise ValueError('A positive diagonal inner product is required in each degree')
    ws=[]
    for n,values in zip(ns,weights):
        if len(values)!=n:raise ValueError('Hodge star dimension mismatch')
        v=vector(values,maximum=128,minimum=0)
        if any(x<=0 for x in v):raise ValueError('Hodge weights must be positive')
        ws.append(sp.diag(*(sp.Rational(str(x)) for x in v)))
    n=ns[degree];lap=sp.zeros(n)
    if degree>0:
        d=sp.Matrix(c.boundary_matrix(degree)).T;lap+=d*ws[degree-1].inv()*d.T*ws[degree]
    if degree<c.dimension:
        d=sp.Matrix(c.boundary_matrix(degree+1)).T;lap+=ws[degree].inv()*d.T*ws[degree+1]*d
    return {'laplacian':data(lap),'harmonic_basis':data(lap.nullspace()),'betti_number':c.betti_number(degree),
            'scope':'Finite-element/discrete positive inner-product Hodge profile; not arbitrary smooth elliptic theory.'}
