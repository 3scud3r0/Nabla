"""Finite simplicial complexes, rational homology and 1D fundamental groups."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from typing import Hashable, Iterable

Vertex = Hashable
Simplex = tuple[Vertex, ...]


def _rank(matrix: list[list[Fraction]], columns: int) -> int:
    rows = [row[:] for row in matrix]
    pivot_row = 0
    for column in range(columns):
        candidate = next((index for index in range(pivot_row, len(rows)) if rows[index][column]), None)
        if candidate is None:
            continue
        rows[pivot_row], rows[candidate] = rows[candidate], rows[pivot_row]
        scale = rows[pivot_row][column]
        rows[pivot_row] = [value / scale for value in rows[pivot_row]]
        for index, row in enumerate(rows):
            if index != pivot_row and row[column]:
                factor = row[column]
                rows[index] = [value - factor * pivot for value, pivot in zip(row, rows[pivot_row])]
        pivot_row += 1
        if pivot_row == len(rows):
            break
    return pivot_row


@dataclass(frozen=True)
class SimplicialComplex:
    simplices: frozenset[Simplex]

    def __init__(self, maximal_simplices: Iterable[Iterable[Vertex]]) -> None:
        closure: set[Simplex] = set()
        for raw in maximal_simplices:
            simplex = tuple(sorted(set(raw), key=repr))
            if not simplex:
                raise ValueError("Simplexo vazio não é uma célula deste modelo")
            for size in range(1, len(simplex) + 1):
                closure.update(combinations(simplex, size))
        object.__setattr__(self, "simplices", frozenset(closure))

    @property
    def dimension(self) -> int:
        return max((len(simplex) - 1 for simplex in self.simplices), default=-1)

    def cells(self, dimension: int) -> tuple[Simplex, ...]:
        return tuple(sorted((simplex for simplex in self.simplices
                            if len(simplex) == dimension + 1), key=repr))

    def boundary_matrix(self, dimension: int) -> tuple[tuple[Fraction, ...], ...]:
        if dimension < 1:
            return ()
        sources, targets = self.cells(dimension), self.cells(dimension - 1)
        target_index = {simplex: index for index, simplex in enumerate(targets)}
        matrix = [[Fraction(0) for _ in sources] for _ in targets]
        for column, simplex in enumerate(sources):
            for removed in range(len(simplex)):
                face = simplex[:removed] + simplex[removed + 1:]
                matrix[target_index[face]][column] = Fraction((-1) ** removed)
        return tuple(tuple(row) for row in matrix)

    def boundary_rank(self, dimension: int) -> int:
        return _rank([list(row) for row in self.boundary_matrix(dimension)],
                     len(self.cells(dimension)))

    def betti_number(self, dimension: int) -> int:
        if dimension < 0:
            raise ValueError("Dimensão deve ser não negativa")
        return len(self.cells(dimension)) - self.boundary_rank(dimension) - self.boundary_rank(dimension + 1)

    def betti_numbers(self) -> tuple[int, ...]:
        return tuple(self.betti_number(index) for index in range(self.dimension + 1))

    def verify_boundary_squared_zero(self) -> bool:
        for dimension in range(2, self.dimension + 1):
            lower, upper = self.boundary_matrix(dimension - 1), self.boundary_matrix(dimension)
            if not lower or not upper:
                continue
            for row in range(len(lower)):
                for column in range(len(upper[0])):
                    if sum(lower[row][middle] * upper[middle][column]
                           for middle in range(len(upper))):
                        return False
        return True

    def fundamental_group_rank_1d(self) -> int:
        if self.dimension > 1:
            raise ValueError("π1 geral de complexos 2D+ não é implementado")
        vertices = self.cells(0)
        adjacency = {vertex: set() for vertex in vertices}
        for edge in self.cells(1):
            left, right = (edge[0],), (edge[1],)
            adjacency[left].add(right)
            adjacency[right].add(left)
        components, unseen = 0, set(vertices)
        while unseen:
            components += 1
            stack = [unseen.pop()]
            while stack:
                neighbors = adjacency[stack.pop()] & unseen
                unseen.difference_update(neighbors)
                stack.extend(neighbors)
        return len(self.cells(1)) - len(vertices) + components


__all__ = ["Simplex", "SimplicialComplex", "Vertex"]


def integral_homology(facets,degree):
    from .._structured import sympy
    sp=sympy();complex_=SimplicialComplex(facets)
    if len(complex_.simplices)>512 or type(degree) is not int or not 0<=degree<=8:raise ValueError('Integral homology budget exceeded')
    n=len(complex_.cells(degree));upper=sp.Matrix(complex_.boundary_matrix(degree+1)) if n and complex_.cells(degree+1) else sp.zeros(n,0)
    if n==0:return {'free_rank':0,'torsion':[]}
    lower=sp.Matrix(complex_.boundary_matrix(degree)) if degree>0 else sp.zeros(0,n)
    if lower.rows:
        from sympy.polys.matrices import DomainMatrix
        from sympy.polys.matrices.normalforms import smith_normal_decomp
        dm=DomainMatrix.from_Matrix(lower).convert_to(sp.ZZ)
        diagonal,s,t=smith_normal_decomp(dm);transform=t.to_Matrix();rank=lower.rank()
        coordinates=transform.inv()*upper
        if any(coordinates[i,j] for i in range(rank) for j in range(coordinates.cols)):raise ValueError('Boundary squared failed')
        image=coordinates[rank:,:];kernel_dimension=n-rank
    else:image=upper;kernel_dimension=n
    if not image.cols:return {'free_rank':kernel_dimension,'torsion':[]}
    from ..algebra.modules import presentation
    result=presentation([[int(v) for v in row] for row in image.tolist()],generators=kernel_dimension)
    return {'free_rank':result['free_rank'],'torsion':result['torsion']}


def cup_product(facets,left_degree,left,right_degree,right):
    c=SimplicialComplex(facets)
    if len(c.simplices)>512 or any(type(k) is not int or k<0 for k in (left_degree,right_degree)):raise ValueError('Cochain budget exceeded')
    a,b=c.cells(left_degree),c.cells(right_degree)
    if len(left)!=len(a) or len(right)!=len(b):raise ValueError('Cochain dimension mismatch')
    lhs={cell:Fraction(v) for cell,v in zip(a,left)};rhs={cell:Fraction(v) for cell,v in zip(b,right)}
    degree=left_degree+right_degree;cells=c.cells(degree)
    values=[lhs[simplex[:left_degree+1]]*rhs[simplex[left_degree:]] for simplex in cells]
    return {'degree':degree,'cells':[list(s) for s in cells],'cochain':list(map(str,values)),
            'scope':'Alexander–Whitney cochain product using the complex vertex order; a cohomology class requires cocycle inputs.'}


def cohomology_basis(facets,degree):
    from .._structured import sympy,data
    sp=sympy();c=SimplicialComplex(facets);n=len(c.cells(degree))
    if type(degree) is not int or not 0<=degree<=8 or len(c.simplices)>512:raise ValueError('Cohomology budget exceeded')
    upper=sp.Matrix(c.boundary_matrix(degree+1)).T if c.cells(degree+1) else sp.zeros(0,n)
    lower=sp.Matrix(c.boundary_matrix(degree)).T if degree else sp.zeros(n,0)
    image=lower.columnspace();basis=list(image);representatives=[]
    for vector in upper.nullspace():
        rank=sp.Matrix.hstack(*(basis+[vector])).rank()
        if rank>len(basis):basis.append(vector);representatives.append(vector)
    return {'degree':degree,'cells':[list(v) for v in c.cells(degree)],'representatives':data(representatives),
            'coboundary_basis':data(image),'dimension':len(representatives),'coefficient_field':'Q'}


def integral_cohomology(facets,degree):
    if type(degree) is not int or degree<0:raise ValueError('Nonnegative cohomology degree required')
    current=integral_homology(facets,degree);previous=integral_homology(facets,degree-1) if degree else {'torsion':[]}
    return {'free_rank':current['free_rank'],'torsion':previous['torsion'],'scope':'Integral cohomology group invariants by the universal coefficient theorem; no chosen splitting.'}


def cup_class(facets,left_degree,left,right_degree,right):
    from .._structured import sympy,data
    sp=sympy();c=SimplicialComplex(facets)
    for degree,values in ((left_degree,left),(right_degree,right)):
        if len(values)!=len(c.cells(degree)):raise ValueError('Cochain dimension mismatch')
        if c.cells(degree+1):
            derivative=sp.Matrix(c.boundary_matrix(degree+1)).T*sp.Matrix([sp.Rational(str(Fraction(v))) for v in values])
            if any(derivative):raise ValueError('Cup-class inputs must be cocycles')
    product=cup_product(facets,left_degree,left,right_degree,right);degree=left_degree+right_degree;basis=cohomology_basis(facets,degree)
    columns=[sp.Matrix([sp.Rational(v[0]) for v in vector]) for vector in basis['coboundary_basis']+basis['representatives']]
    value=sp.Matrix([sp.Rational(v) for v in product['cochain']])
    if columns:
        coordinates=sp.Matrix.hstack(*columns).gauss_jordan_solve(value)[0];coordinates=coordinates[len(basis['coboundary_basis']):,:]
    else:
        if any(value):raise ArithmeticError('Nonzero cocycle with empty cohomology basis')
        coordinates=sp.zeros(0,1)
    return {**product,'class_coordinates':data(coordinates),'coefficient_field':'Q'}
