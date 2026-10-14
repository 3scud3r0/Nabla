"""Exact rectangular systems, pivoted LU, orthogonal bases and conditioning."""
from dataclasses import dataclass
from fractions import Fraction
from .matrices import Matrix,identity


def bounded(matrix):
    if max(matrix.shape)>32:
        raise ValueError('Algebra linear limitada a 32 por 32')
    return matrix


@dataclass(frozen=True)
class LinearSolution:
    status: str
    particular: tuple[Fraction,...] | None
    nullspace: tuple[tuple[Fraction,...],...]
    rank: int
    pivots: tuple[int,...]


def solve_linear(matrix: Matrix, rhs) -> LinearSolution:
    bounded(matrix)
    if len(rhs)!=matrix.shape[0]:
        raise ValueError('Vetor incompativel')
    n=matrix.shape[1]
    augmented=Matrix(tuple(row+(Fraction(value),) for row,value in zip(matrix.rows,rhs)))
    reduced,_=augmented.echelon()
    pivots=[]
    for row in reduced.rows:
        pivot=next((j for j,value in enumerate(row[:n]) if value),None)
        if pivot is None and row[-1]:
            rank=matrix.echelon()[1]
            return LinearSolution('inconsistent',None,(),rank,())
        if pivot is not None:
            pivots.append(pivot)
    particular=[Fraction()]*n
    for row,pivot in zip(reduced.rows,pivots):
        particular[pivot]=row[-1]
    nullspace=[]
    for free in range(n):
        if free in pivots:
            continue
        vector=[Fraction()]*n
        vector[free]=Fraction(1)
        for row,pivot in zip(reduced.rows,pivots):
            vector[pivot]=-row[free]
        nullspace.append(tuple(vector))
    return LinearSolution('unique' if len(pivots)==n else 'underdetermined',tuple(particular),tuple(nullspace),len(pivots),tuple(pivots))


@dataclass(frozen=True)
class LUDecomposition:
    permutation: Matrix
    lower: Matrix
    upper: Matrix

    def verify(self,matrix):
        return self.permutation@matrix==self.lower@self.upper


def lu_decomposition(matrix: Matrix) -> LUDecomposition:
    bounded(matrix)
    n,m=matrix.shape
    if n!=m:
        raise ValueError('LU exige matriz quadrada')
    upper=[list(row) for row in matrix.rows]
    lower=[list(row) for row in identity(n).rows]
    permutation=[list(row) for row in identity(n).rows]
    for k in range(n):
        pivot=next((i for i in range(k,n) if upper[i][k]),None)
        if pivot is None:
            raise ValueError('LU nao singular requer pivo nao nulo')
        upper[k],upper[pivot]=upper[pivot],upper[k]
        permutation[k],permutation[pivot]=permutation[pivot],permutation[k]
        for j in range(k):
            lower[k][j],lower[pivot][j]=lower[pivot][j],lower[k][j]
        for i in range(k+1,n):
            factor=upper[i][k]/upper[k][k]
            lower[i][k]=factor
            for j in range(k,n):
                upper[i][j]-=factor*upper[k][j]
    result=LUDecomposition(*(Matrix(tuple(tuple(r) for r in data)) for data in (permutation,lower,upper)))
    if not result.verify(matrix):
        raise ArithmeticError('Decomposicao LU divergente')
    return result


def orthogonal_basis(vectors) -> tuple[tuple[Fraction,...],...]:
    if not vectors or len(vectors)>32 or not 1<=len(vectors[0])<=32 or any(len(v)!=len(vectors[0]) for v in vectors):
        raise ValueError('Vetores incompatíveis')
    basis=[]
    for vector in vectors:
        current=tuple(Fraction(v) for v in vector)
        for base in basis:
            scale=sum(a*b for a,b in zip(current,base))/sum(v*v for v in base)
            current=tuple(a-scale*b for a,b in zip(current,base))
        if any(current):
            basis.append(current)
    return tuple(basis)


def condition_number_inf(matrix: Matrix) -> Fraction:
    bounded(matrix)
    def norm(a):
        return max(sum(abs(v) for v in row) for row in a.rows)
    return norm(matrix)*norm(matrix.inverse())


def characteristic_polynomial(matrix: Matrix):
    """Faddeev-LeVerrier recurrence; ascending rational coefficients."""
    bounded(matrix)
    n,m=matrix.shape
    if n!=m:
        raise ValueError('Polinomio caracteristico exige matriz quadrada')
    current=identity(n)
    descending=[Fraction(1)]
    for k in range(1,n+1):
        product=matrix@current
        coefficient=-sum(product.rows[i][i] for i in range(n))/k
        descending.append(coefficient)
        current=Matrix(tuple(tuple(product.rows[i][j]+(coefficient if i==j else 0) for j in range(n)) for i in range(n)))
    return tuple(reversed(descending))
