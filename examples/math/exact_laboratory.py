"""Run from the repository root after installing NablaMath."""
from nablamath.math.exact import (
    Polynomial, RationalMatrix, isolate_real_roots, square_free_factors,
    bounded_linear_program, chinese_remainder,
)

polynomial = Polynomial((-2, 0, 1))  # x^2 - 2
print("Distinct real root brackets:", isolate_real_roots(polynomial))
print("Square-free factors:", square_free_factors(polynomial))

matrix = RationalMatrix(((1, 2), (3, 5)))
print("Inverse:", matrix.inverse().rows)
print("Generalized CRT:", chinese_remainder(((2, 6), (5, 9))))
print("Linear program:", bounded_linear_program(
    (3, 2), (((1, 1), 4),), ((0, 3), (0, 4)),
))
