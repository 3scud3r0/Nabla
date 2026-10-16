"""Exact advanced mathematics: auditable finite algorithms with bounded inputs.

This module deliberately uses Fraction instead of floating point.  Its claims
are *mathematical exactness within stated domains*, not physical validation,
universal symbolic integration, or formal Lean proofs.

All algorithms are implemented in the Python standard library; no mandatory
third-party dependency is introduced.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from math import comb, gcd
from typing import Sequence


MAX_BITS = 4096
MAX_POLY_COEFFICIENTS = 129
MAX_MATRIX_DIMENSION = 32


def rational(value: int | str | Fraction) -> Fraction:
    """Parse an exact rational; reject binary floats and unbounded numerators."""
    if type(value) is bool or not isinstance(value, (int, str, Fraction)):
        raise TypeError("Expected int, Fraction or rational string, never float")
    if isinstance(value, str) and len(value) > 128:
        raise ValueError("Rational text exceeds 128 characters")
    result = Fraction(value)
    if max(abs(result.numerator).bit_length(), result.denominator.bit_length()) > MAX_BITS:
        raise ValueError("Rational exceeds configured bit budget")
    return result


@dataclass(frozen=True)
class Polynomial:
    """Univariate polynomial over Q, with coefficients in ASCENDING order.

    Polynomial((3, 2, 1)) represents 3 + 2*x + x*x.
    Zero is stored canonically as (0,), and its degree is -1.
    """
    coefficients: tuple[Fraction, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.coefficients, (tuple, list)):
            raise TypeError("Polynomial coefficients must be a finite sequence")
        if not 1 <= len(self.coefficients) <= MAX_POLY_COEFFICIENTS:
            raise ValueError("Polynomial length outside exact computation budget")
        coeffs = tuple(rational(item) for item in self.coefficients)
        while len(coeffs) > 1 and coeffs[-1] == 0:
            coeffs = coeffs[:-1]
        object.__setattr__(self, "coefficients", coeffs)

    @classmethod
    def constant(cls, value: int | Fraction) -> Polynomial:
        return cls((rational(value),))

    @property
    def is_zero(self) -> bool:
        return len(self.coefficients) == 1 and self.coefficients[0] == 0

    @property
    def degree(self) -> int:
        return -1 if self.is_zero else len(self.coefficients) - 1

    @property
    def leading(self) -> Fraction:
        return self.coefficients[-1]

    def _coerce(self, value: object) -> Polynomial:
        return value if isinstance(value, Polynomial) else Polynomial.constant(value)

    def __add__(self, other: object) -> Polynomial:
        other = self._coerce(other)
        n = max(len(self.coefficients), len(other.coefficients))
        return Polynomial(tuple(
            (self.coefficients[i] if i < len(self.coefficients) else 0)
            + (other.coefficients[i] if i < len(other.coefficients) else 0)
            for i in range(n)
        ))

    def __radd__(self, other: object) -> Polynomial:
        return self + other

    def __neg__(self) -> Polynomial:
        return Polynomial(tuple(-c for c in self.coefficients))

    def __sub__(self, other: object) -> Polynomial:
        return self + (-self._coerce(other))

    def __rsub__(self, other: object) -> Polynomial:
        return self._coerce(other) - self

    def __mul__(self, other: object) -> Polynomial:
        other = self._coerce(other)
        if self.is_zero or other.is_zero:
            return Polynomial((0,))
        if self.degree + other.degree + 1 > MAX_POLY_COEFFICIENTS:
            raise ValueError("Polynomial product exceeds degree budget")
        coefficients = [Fraction(0)] * (self.degree + other.degree + 1)
        for i, a in enumerate(self.coefficients):
            for j, b in enumerate(other.coefficients):
                coefficients[i + j] += a * b
        return Polynomial(tuple(coefficients))

    def __rmul__(self, other: object) -> Polynomial:
        return self * other

    def __truediv__(self, constant: int | Fraction) -> Polynomial:
        divisor = rational(constant)
        if divisor == 0:
            raise ZeroDivisionError("Polynomial scalar division by zero")
        return Polynomial(tuple(c / divisor for c in self.coefficients))

    def __pow__(self, exponent: int) -> Polynomial:
        if type(exponent) is not int or not 0 <= exponent <= 128:
            raise ValueError("Polynomial exponent must be an integer in [0, 128]")
        result = Polynomial((1,))
        base = self
        while exponent:
            if exponent & 1:
                result = result * base
            exponent >>= 1
            if exponent:
                base = base * base
        return result

    def __call__(self, x: int | str | Fraction) -> Fraction:
        x = rational(x)
        result = Fraction(0)
        for coefficient in reversed(self.coefficients):
            result = result * x + coefficient
        return rational(result)

    def derivative(self, order: int = 1) -> Polynomial:
        if type(order) is not int or not 0 <= order <= 128:
            raise ValueError("Derivative order out of range")
        result = self
        for _ in range(order):
            result = Polynomial(tuple(
                i * c for i, c in enumerate(result.coefficients) if i
            ) or (0,))
        return result

    def integral(self, constant: int | Fraction = 0) -> Polynomial:
        return Polynomial((rational(constant),) + tuple(
            c / (i + 1) for i, c in enumerate(self.coefficients)
        ))

    def compose(self, inner: Polynomial) -> Polynomial:
        if not isinstance(inner, Polynomial):
            raise TypeError("Composition requires a polynomial")
        result = Polynomial((0,))
        for coefficient in reversed(self.coefficients):
            result = result * inner + coefficient
        return result

    def divide(self, divisor: Polynomial) -> tuple[Polynomial, Polynomial]:
        """Euclidean division: self = quotient*divisor + remainder."""
        if not isinstance(divisor, Polynomial) or divisor.is_zero:
            raise ZeroDivisionError("Polynomial divisor is zero or invalid")
        remainder = self
        quotient = Polynomial((0,))
        x = Polynomial((0, 1))
        while not remainder.is_zero and remainder.degree >= divisor.degree:
            term = Polynomial((0,) * (remainder.degree - divisor.degree)
                              + (remainder.leading / divisor.leading,))
            quotient = quotient + term
            remainder = remainder - term * divisor
        return quotient, remainder

    def exact_quotient(self, divisor: Polynomial) -> Polynomial:
        quotient, remainder = self.divide(divisor)
        if not remainder.is_zero:
            raise ValueError("Polynomial does not divide exactly")
        return quotient

    def monic(self) -> Polynomial:
        if self.is_zero:
            raise ZeroDivisionError("Zero polynomial has no monic normalization")
        return self / self.leading

    def to_data(self) -> list[str]:
        return [str(c) for c in self.coefficients]


ZERO = Polynomial((0,))
ONE = Polynomial((1,))
X = Polynomial((0, 1))


def polynomial_gcd(a: Polynomial, b: Polynomial) -> Polynomial:
    """Monic Euclidean gcd over the field of rational numbers."""
    while not b.is_zero:
        _, r = a.divide(b)
        a, b = b, r
    return ZERO if a.is_zero else a.monic()


def polynomial_extended_gcd(
    a: Polynomial, b: Polynomial
) -> tuple[Polynomial, Polynomial, Polynomial]:
    """Return monic gcd g and Bézout coefficients s,t: s*a+t*b=g."""
    if a.is_zero and b.is_zero:
        return ZERO, ZERO, ZERO
    old_r, r = a, b
    old_s, s = ONE, ZERO
    old_t, t = ZERO, ONE
    while not r.is_zero:
        q, rem = old_r.divide(r)
        old_r, r = r, rem
        old_s, s = s, old_s - q * s
        old_t, t = t, old_t - q * t
    scale = old_r.leading
    return old_r / scale, old_s / scale, old_t / scale


def square_free_factors(poly: Polynomial) -> tuple[tuple[Polynomial, int], ...]:
    """Square-free decomposition over Q; factors returned monic with multiplicity.

    Nonzero constant scaling is intentionally omitted; this is a structural
    decomposition, not an integer irreducible factorization.
    """
    if poly.is_zero:
        raise ValueError("Zero polynomial has no finite square-free factorization")
    if poly.degree <= 0:
        return ()
    f = poly.monic()
    c = polynomial_gcd(f, f.derivative())
    w = f.exact_quotient(c)
    i = 1
    factors = []
    while w != ONE:
        y = polynomial_gcd(w, c)
        z = w.exact_quotient(y)
        if z != ONE:
            factors.append((z, i))
        w, c = y, c.exact_quotient(y)
        i += 1
    return tuple(factors)


def resultant(a: Polynomial, b: Polynomial) -> Fraction:
    """Sylvester determinant; zero iff nonconstant polynomials share a root."""
    if a.is_zero or b.is_zero:
        raise ValueError("Resultant is undefined here for the zero polynomial")
    m, n = a.degree, b.degree
    size = m + n
    if size == 0:
        return Fraction(1)
    if size > MAX_MATRIX_DIMENSION:
        raise ValueError("Sylvester matrix exceeds linear algebra budget")
    a_desc, b_desc = list(reversed(a.coefficients)), list(reversed(b.coefficients))
    rows = []
    for shift in range(n):
        rows.append(tuple([0] * shift + a_desc + [0] * (n - shift - 1)))
    for shift in range(m):
        rows.append(tuple([0] * shift + b_desc + [0] * (m - shift - 1)))
    return RationalMatrix(tuple(rows)).determinant()


def discriminant(poly: Polynomial) -> Fraction:
    """Exact discriminant with standard sign convention for degree >= 1."""
    if poly.degree < 1:
        raise ValueError("Discriminant requires a nonconstant polynomial")
    n = poly.degree
    sign = -1 if (n * (n - 1) // 2) % 2 else 1
    return sign * resultant(poly, poly.derivative()) / poly.leading


def sturm_sequence(poly: Polynomial) -> tuple[Polynomial, ...]:
    """Sturm chain for distinct REAL roots; exact rational coefficients."""
    if poly.degree < 1:
        return (poly,)
    seq = [poly, poly.derivative()]
    while True:
        _, remainder = seq[-2].divide(seq[-1])
        if remainder.is_zero:
            break
        seq.append(-remainder)
    return tuple(seq)


def _sign_variations(chain: tuple[Polynomial, ...], value: Fraction) -> int:
    signs = [(1 if p(value) > 0 else -1) for p in chain if p(value) != 0]
    return sum(a != b for a, b in zip(signs, signs[1:]))


def real_root_count(poly: Polynomial, left: int | Fraction,
                    right: int | Fraction) -> int:
    """Sturm count on (left,right); both endpoints MUST be non-roots."""
    left, right = rational(left), rational(right)
    if left >= right or poly.degree < 1:
        if left >= right:
            raise ValueError("Interval bounds must be increasing")
        return 0
    if poly(left) == 0 or poly(right) == 0:
        raise ValueError("Sturm interval endpoints must not be roots")
    chain = sturm_sequence(poly)
    return _sign_variations(chain, left) - _sign_variations(chain, right)


def isolate_real_roots(poly: Polynomial, *, max_depth: int = 128
                       ) -> tuple[tuple[Fraction, Fraction], ...]:
    """Return disjoint rational brackets containing one distinct real root each.

    Cauchy's root bound provides a strict finite starting interval.  This
    function refuses to claim completion if its subdivision budget is exceeded.
    """
    if type(max_depth) is not int or not 1 <= max_depth <= 1024:
        raise ValueError("max_depth out of range")
    if poly.degree < 1:
        return ()
    bound = Fraction(1) + max(
        (abs(c / poly.leading) for c in poly.coefficients[:-1]),
        default=Fraction(0)
    )
    pending = [(-bound, bound, 0)]
    answer = []
    while pending:
        a, b, depth = pending.pop()
        count = real_root_count(poly, a, b)
        if count == 0:
            continue
        if count == 1:
            answer.append((a, b))
            continue
        if depth >= max_depth:
            raise ArithmeticError("Root isolation depth exhausted")
        middle = (a + b) / 2
        for _ in range(256):
            if poly(middle) != 0:
                break
            middle = (a + middle) / 2
        else:
            raise ArithmeticError("Cannot find a non-root splitting point")
        pending.extend(((a, middle, depth + 1), (middle, b, depth + 1)))
    return tuple(sorted(answer))


def interpolate(points: Sequence[tuple[object, object]]) -> Polynomial:
    """Unique minimal-degree Lagrange polynomial through distinct x values."""
    if not 1 <= len(points) <= 32:
        raise ValueError("Interpolation requires 1..32 nodes")
    data = [(rational(x), rational(y)) for x, y in points]
    if len({x for x, _ in data}) != len(data):
        raise ValueError("Interpolation nodes must be distinct")
    result = ZERO
    for i, (x_i, y_i) in enumerate(data):
        basis, scale = ONE, Fraction(1)
        for j, (x_j, _) in enumerate(data):
            if i != j:
                basis *= X - x_j
                scale *= x_i - x_j
        result += basis * (y_i / scale)
    return result


def hermite_interpolate(nodes: Sequence[tuple[object, object, object]]) -> Polynomial:
    """Interpolate values and first derivatives at distinct rational abscissae."""
    if not 1 <= len(nodes) <= 32:
        raise ValueError("Hermite interpolation requires 1..32 nodes")
    data = [(rational(x), rational(y), rational(d)) for x, y, d in nodes]
    if len({x for x, _, _ in data}) != len(data):
        raise ValueError("Hermite nodes must be distinct")
    result = ZERO
    for i, (x_i, y_i, d_i) in enumerate(data):
        basis, scale = ONE, Fraction(1)
        for j, (x_j, _, _) in enumerate(data):
            if i != j:
                basis *= X - x_j
                scale *= x_i - x_j
        basis = basis / scale
        slope = basis.derivative()(x_i)
        result += y_i * (ONE - 2 * slope * (X - x_i)) * basis**2
        result += d_i * (X - x_i) * basis**2
    return result


def bernstein_range(poly: Polynomial, left: object, right: object
                    ) -> tuple[Fraction, Fraction]:
    """Rigorous (potentially loose) range enclosure via Bernstein coefficients.

    This is an exact bound on polynomial values over [left,right], not an
    assertion that either reported bound is achieved by the function.
    """
    left, right = rational(left), rational(right)
    if left >= right:
        raise ValueError("Range interval must be increasing")
    transformed = poly.compose(Polynomial((left, right - left)))
    n = transformed.degree
    if n < 0:
        return Fraction(0), Fraction(0)
    bernstein = [
        sum((transformed.coefficients[j] * Fraction(comb(k, j), comb(n, j))
             for j in range(k + 1)), Fraction(0))
        for k in range(n + 1)
    ]
    return min(bernstein), max(bernstein)


@dataclass(frozen=True)
class RationalMatrix:
    """Exact rational matrix; elimination never uses floating-point tolerance."""
    rows: tuple[tuple[Fraction, ...], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.rows, (tuple, list)) or not 1 <= len(self.rows) <= MAX_MATRIX_DIMENSION:
            raise ValueError("Matrix row count outside configured budget")
        rows = tuple(tuple(rational(x) for x in row) for row in self.rows)
        if not rows[0] or len(rows[0]) > MAX_MATRIX_DIMENSION or any(len(row) != len(rows[0]) for row in rows):
            raise ValueError("Matrix must be nonempty, rectangular and bounded")
        object.__setattr__(self, "rows", rows)

    @property
    def shape(self) -> tuple[int, int]:
        return len(self.rows), len(self.rows[0])

    @classmethod
    def identity(cls, n: int) -> RationalMatrix:
        if type(n) is not int or not 1 <= n <= MAX_MATRIX_DIMENSION:
            raise ValueError("Identity dimension outside budget")
        return cls(tuple(tuple(int(i == j) for j in range(n)) for i in range(n)))

    def transpose(self) -> RationalMatrix:
        return RationalMatrix(tuple(tuple(col) for col in zip(*self.rows)))

    def __matmul__(self, other: RationalMatrix) -> RationalMatrix:
        if not isinstance(other, RationalMatrix) or self.shape[1] != other.shape[0]:
            raise ValueError("Matrix multiplication dimensions mismatch")
        other_t = other.transpose()
        return RationalMatrix(tuple(tuple(
            sum((a*b for a, b in zip(row, col)), Fraction(0))
            for col in other_t.rows) for row in self.rows))

    def rref(self) -> tuple[RationalMatrix, tuple[int, ...]]:
        """Gauss-Jordan row reduction, returning pivot column indices."""
        data = [list(row) for row in self.rows]
        m, n = self.shape
        pivots, row = [], 0
        for col in range(n):
            pivot = next((i for i in range(row, m) if data[i][col]), None)
            if pivot is None:
                continue
            data[row], data[pivot] = data[pivot], data[row]
            scale = data[row][col]
            data[row] = [x / scale for x in data[row]]
            for i in range(m):
                if i != row:
                    factor = data[i][col]
                    if factor:
                        data[i] = [a - factor*b for a, b in zip(data[i], data[row])]
            pivots.append(col)
            row += 1
            if row == m:
                break
        return RationalMatrix(tuple(tuple(line) for line in data)), tuple(pivots)

    @property
    def rank(self) -> int:
        return len(self.rref()[1])

    def determinant(self) -> Fraction:
        m, n = self.shape
        if m != n:
            raise ValueError("Determinant requires square matrix")
        data = [list(row) for row in self.rows]
        det = Fraction(1)
        for k in range(n):
            pivot = next((i for i in range(k, n) if data[i][k]), None)
            if pivot is None:
                return Fraction(0)
            if pivot != k:
                data[k], data[pivot] = data[pivot], data[k]
                det = -det
            p = data[k][k]
            det *= p
            for i in range(k + 1, n):
                factor = data[i][k] / p
                for j in range(k + 1, n):
                    data[i][j] -= factor * data[k][j]
                data[i][k] = 0
        return rational(det)

    def inverse(self) -> RationalMatrix:
        m, n = self.shape
        if m != n or 2*n > MAX_MATRIX_DIMENSION:
            raise ValueError("Inverse requires square matrix within augmented budget")
        eye = RationalMatrix.identity(n)
        augmented = RationalMatrix(tuple(a+b for a,b in zip(self.rows, eye.rows)))
        reduced, pivots = augmented.rref()
        if pivots[:n] != tuple(range(n)):
            raise ValueError("Matrix is singular")
        return RationalMatrix(tuple(row[n:] for row in reduced.rows))

    def solve(self, rhs: Sequence[object]) -> AffineSolution:
        """Solve A*x=b exactly; include a basis of the full homogeneous kernel."""
        m, n = self.shape
        if len(rhs) != m or n + 1 > MAX_MATRIX_DIMENSION:
            raise ValueError("RHS dimension or augmented matrix exceeds budget")
        augmented = RationalMatrix(tuple(row+(rational(rhs[i]),)
                                         for i, row in enumerate(self.rows)))
        reduced, pivots = augmented.rref()
        if n in pivots:
            raise ValueError("Inconsistent linear system")
        free = [j for j in range(n) if j not in pivots]
        particular = [Fraction(0)] * n
        for i, j in enumerate(pivots):
            particular[j] = reduced.rows[i][n]
        kernel = []
        for f in free:
            vector = [Fraction(0)] * n
            vector[f] = Fraction(1)
            for i, j in enumerate(pivots):
                vector[j] = -reduced.rows[i][f]
            kernel.append(tuple(vector))
        return AffineSolution(tuple(particular), tuple(kernel), tuple(pivots))

    def characteristic_polynomial(self) -> Polynomial:
        """Faddeev-LeVerrier recurrence, exact for square rational matrices."""
        m, n = self.shape
        if m != n:
            raise ValueError("Characteristic polynomial requires square matrix")
        identity = RationalMatrix.identity(n)
        b = identity
        coefficients = [Fraction(1)]
        for k in range(1, n+1):
            a_b = self @ b
            trace = sum(a_b.rows[i][i] for i in range(n))
            c = -trace / k
            coefficients.append(c)
            b = RationalMatrix(tuple(tuple(
                a_b.rows[i][j] + (c if i == j else 0)
                for j in range(n)) for i in range(n)))
        return Polynomial(tuple(reversed(coefficients)))


@dataclass(frozen=True)
class AffineSolution:
    """All exact solutions: particular + sum(t_i * nullspace[i])."""
    particular: tuple[Fraction, ...]
    nullspace: tuple[tuple[Fraction, ...], ...]
    pivot_columns: tuple[int, ...]


def chinese_remainder(congruences: Sequence[tuple[int, int]]) -> tuple[int, int]:
    """Generalized CRT; supports non-coprime moduli and detects contradictions."""
    if not 1 <= len(congruences) <= 128:
        raise ValueError("CRT requires 1..128 congruences")
    x, modulus = 0, 1
    for residue, next_modulus in congruences:
        if type(residue) is not int or type(next_modulus) is not int or next_modulus <= 0:
            raise ValueError("CRT moduli must be positive integers")
        common = gcd(modulus, next_modulus)
        if (residue - x) % common:
            raise ValueError("Incompatible modular congruences")
        reduced = next_modulus // common
        step = 0 if reduced == 1 else (
            ((residue - x) // common) * pow(modulus // common, -1, reduced)
        ) % reduced
        x = (x + modulus * step) % (modulus * reduced)
        modulus *= reduced
        if modulus.bit_length() > MAX_BITS:
            raise ValueError("CRT modulus exceeds bit budget")
    return x, modulus


def berlekamp_massey(sequence: Sequence[object]) -> tuple[Fraction, ...]:
    """Minimal linear recurrence compatible with a finite rational prefix.

    Returns (a1,..,aL) where s[n]=a1*s[n-1]+...+aL*s[n-L].
    A finite prefix alone does not prove the recurrence continues indefinitely.
    """
    if not 1 <= len(sequence) <= 512:
        raise ValueError("Recurrence inference requires 1..512 values")
    samples = tuple(rational(x) for x in sequence)
    c, b = [Fraction(1)], [Fraction(1)]
    length, shift, previous = 0, 1, Fraction(1)
    for n in range(len(samples)):
        discrepancy = sum(
            (c[i]*samples[n-i] for i in range(length+1)), Fraction(0)
        )
        if discrepancy == 0:
            shift += 1
            continue
        old = c[:]
        if len(c) < len(b) + shift:
            c.extend(Fraction(0) for _ in range(len(b) + shift - len(c)))
        factor = discrepancy / previous
        for i, coefficient in enumerate(b):
            c[i + shift] -= factor * coefficient
        if 2*length <= n:
            length = n + 1 - length
            b, previous, shift = old, discrepancy, 1
        else:
            shift += 1
    return tuple(rational(-x) for x in c[1:length+1])


def rational_generating_function(
    sequence: Sequence[object]
) -> tuple[Polynomial, Polynomial]:
    """Formal P(z)/Q(z) implied by the inferred rational recurrence."""
    samples = tuple(rational(x) for x in sequence)
    coefficients = berlekamp_massey(samples)
    if not coefficients:
        if any(samples):
            raise ArithmeticError("Nonzero sequence has empty recurrence")
        return ZERO, ONE
    denominator = Polynomial((1,) + tuple(-a for a in coefficients))
    numerator = Polynomial(tuple(
        sum((denominator.coefficients[j] * samples[k-j]
             for j in range(min(k, denominator.degree)+1)), Fraction(0))
        for k in range(len(coefficients))
    ))
    return numerator, denominator


def spanning_tree_count(adjacency: Sequence[Sequence[int]]) -> int:
    """Weighted Matrix-Tree theorem for a finite undirected integer multigraph."""
    n = len(adjacency)
    if not 1 <= n <= MAX_MATRIX_DIMENSION:
        raise ValueError("Graph size outside configured budget")
    if any(len(row) != n for row in adjacency):
        raise ValueError("Adjacency matrix must be square")
    if any(type(adjacency[i][j]) is not int or adjacency[i][j] < 0
           or adjacency[i][j] != adjacency[j][i] for i in range(n) for j in range(n)):
        raise ValueError("Adjacency requires nonnegative symmetric integer multiplicities")
    if any(adjacency[i][i] for i in range(n)):
        raise ValueError("Self loops are not part of this graph contract")
    if n == 1:
        return 1
    laplacian = [
        [sum(adjacency[i]) if i == j else -adjacency[i][j] for j in range(n)]
        for i in range(n)
    ]
    value = RationalMatrix(tuple(tuple(row[:-1]) for row in laplacian[:-1])).determinant()
    if value.denominator != 1 or value < 0:
        raise ArithmeticError("Matrix-Tree invariant violated")
    return int(value)


def absorbing_chain(transient_matrix: Sequence[Sequence[object]]) -> dict:
    """Fundamental matrix (I-Q)^-1 and exact expected times to absorption.

    Input Q describes only the transient states of a finite substochastic
    Markov chain.  A singular I-Q is refused (no finite mean guarantee).
    """
    q = RationalMatrix(tuple(tuple(row) for row in transient_matrix))
    m, n = q.shape
    if m != n:
        raise ValueError("Transient Markov matrix must be square")
    if any(any(x < 0 or x > 1 for x in row) or sum(row) > 1 for row in q.rows):
        raise ValueError("Transient transition rows must be substochastic")
    eye = RationalMatrix.identity(n)
    fundamental = RationalMatrix(tuple(tuple(
        eye.rows[i][j] - q.rows[i][j] for j in range(n)
    ) for i in range(n))).inverse()
    times = tuple(sum(row) for row in fundamental.rows)
    if any(time < 0 for time in times):
        raise ArithmeticError("Absorption fundamental matrix invalid")
    return {
        "fundamental": [[str(x) for x in row] for row in fundamental.rows],
        "expected_steps": [str(x) for x in times],
        "limitations": "Finite rational transient states; no external model validation",
    }


def bounded_linear_program(
    objective: Sequence[object],
    inequalities: Sequence[tuple[Sequence[object], object]],
    bounds: Sequence[tuple[object, object]], *,
    maximize: bool = True,
) -> dict:
    """Exact vertex enumeration for box-bounded linear programs A*x <= b.

    The finite box guarantees that any nonempty feasible set has an optimum.
    The returned vertex is a feasible witness, not a formal dual certificate.
    """
    n = len(objective)
    if not 1 <= n <= 5 or len(bounds) != n or len(inequalities) > 24:
        raise ValueError("LP supports 1..5 variables and at most 24 inequalities")
    if type(maximize) is not bool:
        raise TypeError("maximize must be bool")
    c = tuple(rational(x) for x in objective)
    parsed = []
    for a, b in inequalities:
        if len(a) != n:
            raise ValueError("LP constraint has incorrect dimension")
        parsed.append((tuple(rational(x) for x in a), rational(b)))
    for j, (lower, upper) in enumerate(bounds):
        lower, upper = rational(lower), rational(upper)
        if lower > upper:
            raise ValueError("LP bound is reversed")
        positive = [Fraction(0)] * n
        positive[j] = Fraction(1)
        parsed.append((tuple(positive), upper))
        parsed.append((tuple(-x for x in positive), -lower))
    if comb(len(parsed), n) > 200000:
        raise ValueError("LP vertex enumeration budget exceeded")
    best = None
    for active in combinations(range(len(parsed)), n):
        system = RationalMatrix(tuple(parsed[i][0] for i in active))
        try:
            candidate = system.solve(tuple(parsed[i][1] for i in active))
        except ValueError:
            continue
        if candidate.nullspace:
            continue
        point = candidate.particular
        if any(sum((a*x for a, x in zip(row, point)), Fraction(0)) > b
               for row, b in parsed):
            continue
        value = sum((a*x for a, x in zip(c, point)), Fraction(0))
        if best is None or (value > best[0] if maximize else value < best[0]):
            best = (value, point, active)
    if best is None:
        raise ValueError("Infeasible bounded LP")
    value, point, active = best
    return {
        "optimum": str(value),
        "point": [str(x) for x in point],
        "active_constraints": list(active),
        "sense": "max" if maximize else "min",
        "arithmetic": "exact-rational",
        "limitations": "Finite box-bounded LP; exponential vertex enumeration",
    }


__all__ = [
    "Polynomial", "RationalMatrix", "AffineSolution", "rational",
    "polynomial_gcd", "polynomial_extended_gcd", "square_free_factors",
    "resultant", "discriminant", "sturm_sequence", "real_root_count",
    "isolate_real_roots", "interpolate", "hermite_interpolate",
    "bernstein_range", "chinese_remainder", "berlekamp_massey",
    "rational_generating_function", "spanning_tree_count",
    "absorbing_chain", "bounded_linear_program",
]
