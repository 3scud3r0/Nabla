"""Version 1: rational pivoted LU with independently checkable identities."""
from dataclasses import dataclass
from .matrices import Matrix, identity
CONTRACT_VERSION = 1


@dataclass(frozen=True)
class LUDecomposition:
    permutation: Matrix
    lower: Matrix
    upper: Matrix

    def verify(self, original: Matrix) -> bool:
        """Check PA=LU and triangular/unit-diagonal structure exactly."""
        n, m = original.shape
        if n != m or any(a.shape != (n, n) for a in
                         (self.permutation, self.lower, self.upper)):
            return False
        p, l, u = self.permutation.rows, self.lower.rows, self.upper.rows
        return (all(sum(row) == 1 and all(v in (0, 1) for v in row) for row in p)
                and all(sum(p[i][j] for i in range(n)) == 1 for j in range(n))
                and all(l[i][i] == 1 for i in range(n))
                and all(l[i][j] == 0 for i in range(n) for j in range(i + 1, n))
                and all(u[i][j] == 0 for i in range(n) for j in range(i))
                and self.permutation @ original == self.lower @ self.upper)


def pivoted_lu(matrix: Matrix) -> LUDecomposition:
    """Return PA=LU over rationals, including singular square matrices (n<=128)."""
    n, m = matrix.shape
    if n != m or n > 128:
        raise ValueError("requires a square matrix of order at most 128")
    u = [list(row) for row in matrix.rows]
    l = [list(row) for row in identity(n).rows]
    p = [list(row) for row in identity(n).rows]
    for k in range(n):
        pivot = next((i for i in range(k, n) if u[i][k]), None)
        if pivot is None:
            continue
        if pivot != k:
            u[k], u[pivot] = u[pivot], u[k]
            p[k], p[pivot] = p[pivot], p[k]
            for j in range(k):
                l[k][j], l[pivot][j] = l[pivot][j], l[k][j]
        for i in range(k + 1, n):
            l[i][k] = u[i][k] / u[k][k]
            for j in range(k, n):
                u[i][j] -= l[i][k] * u[k][j]
    return LUDecomposition(*(Matrix(tuple(tuple(row) for row in a)) for a in (p, l, u)))
