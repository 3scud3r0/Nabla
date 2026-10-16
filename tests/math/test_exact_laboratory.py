"""Independent invariant and edge-case tests for the exact rational laboratory."""
import random
import unittest
from fractions import Fraction

from nablamath.math.exact import (
    Polynomial, RationalMatrix, rational, polynomial_gcd,
    polynomial_extended_gcd, square_free_factors, resultant,
    discriminant, real_root_count, isolate_real_roots, interpolate,
    hermite_interpolate, bernstein_range, chinese_remainder,
    berlekamp_massey, rational_generating_function,
    spanning_tree_count, absorbing_chain, bounded_linear_program,
)

P = Polynomial
M = RationalMatrix


class TestExactRationals(unittest.TestCase):
    def test_reject_floats_and_booleans(self):
        for value in (True, 0.5, float("nan")):
            with self.subTest(value=str(value)):
                with self.assertRaises(TypeError):
                    rational(value)

    def test_exact_decimal_string(self):
        self.assertEqual(rational("0.125"), Fraction(1, 8))

    def test_large_value_rejected(self):
        with self.assertRaises(ValueError):
            rational(1 << 4097)

    def test_canonical_zero(self):
        self.assertEqual(P((0, 0, 0)), P((0,)))
        self.assertEqual(P((0,)).degree, -1)

    def test_horner_and_derivative(self):
        p = P((3, 2, 1))
        self.assertEqual(p(Fraction(1, 2)), Fraction(17, 4))
        self.assertEqual(p.derivative(), P((2, 2)))
        self.assertEqual(p.derivative(2), P((2,)))
        self.assertEqual(p.integral().derivative(), p)

    def test_arithmetic_composition_and_power(self):
        self.assertEqual((P((1, 1)) ** 3), P((1, 3, 3, 1)))
        self.assertEqual(P((0, 0, 1)).compose(P((1, 1))), P((1, 2, 1)))
        self.assertEqual(3 - P((1, 1)), P((2, -1)))
        self.assertEqual(P((2,)) / 4, P((Fraction(1, 2),)))

    def test_division_identity_random(self):
        random.seed(9127)
        for _ in range(60):
            p = P(tuple(random.randint(-7, 7) for _ in range(6)))
            d = P((random.randint(-3, 3), random.choice((1, 2, 3))))
            quotient, remainder = p.divide(d)
            self.assertEqual(p, quotient * d + remainder)
            self.assertLess(remainder.degree, d.degree)

    def test_bezout_random(self):
        random.seed(19)
        for _ in range(25):
            a = P(tuple(random.randint(-3, 3) for _ in range(5)))
            b = P(tuple(random.randint(-3, 3) for _ in range(4)))
            if a.is_zero and b.is_zero:
                continue
            g, s, t = polynomial_extended_gcd(a, b)
            self.assertEqual(s*a + t*b, g)
            self.assertEqual(g, polynomial_gcd(a, b))

    def test_square_free_multiplicity(self):
        p = (P((-1, 1))**3) * (P((2, 1))**2)
        factors = square_free_factors(p)
        reconstructed = P((1,))
        for f, degree in factors:
            reconstructed *= f ** degree
        self.assertEqual(reconstructed, p.monic())
        self.assertEqual(sorted(power for _, power in factors), [2, 3])

    def test_resultant_and_discriminant(self):
        f = P((-2, 0, 1))
        self.assertEqual(resultant(f, P((-1, 1))), -1)
        self.assertEqual(discriminant(f), 8)
        self.assertEqual(discriminant(P((3, 1))), 1)
        self.assertEqual(discriminant(P((-1, 2, -1))), 0)

    def test_sturm_repeated_roots(self):
        p = P((-1, 1))**2 * P((2, 1))
        self.assertEqual(real_root_count(p, -4, 4), 2)
        intervals = isolate_real_roots(p)
        self.assertEqual(len(intervals), 2)
        self.assertTrue(any(a < -2 < b for a,b in intervals))
        self.assertTrue(any(a < 1 < b for a,b in intervals))

    def test_root_count_requires_nonroot_endpoints(self):
        with self.assertRaises(ValueError):
            real_root_count(P((-1, 1)), 1, 3)

    def test_isolation_has_no_false_positive(self):
        self.assertEqual(isolate_real_roots(P((1, 0, 1))), ())
        self.assertEqual(len(isolate_real_roots(P((0, 1)))), 1)

    def test_lagrange_unique_interpolant(self):
        p = interpolate(((0, 1), (1, 2), (2, 5)))
        self.assertEqual(p, P((1, 0, 1)))
        with self.assertRaises(ValueError):
            interpolate(((1, 2), (1, 3)))

    def test_hermite_first_derivatives(self):
        p = hermite_interpolate(((0, 1, 0), (1, 2, 3)))
        self.assertEqual(p, P((1, 0, 0, 1)))
        for x, y, dy in ((0, 1, 0), (1, 2, 3)):
            self.assertEqual(p(x), y)
            self.assertEqual(p.derivative()(x), dy)

    def test_bernstein_bounds(self):
        self.assertEqual(bernstein_range(P((0, 1)), 2, 5), (2, 5))
        lo, hi = bernstein_range(P((0, 0, 1)), -1, 1)
        self.assertLessEqual(lo, 0)
        self.assertGreaterEqual(hi, 1)
        for numerator in range(-16, 17):
            x = Fraction(numerator, 16)
            self.assertLessEqual(lo, x*x)
            self.assertLessEqual(x*x, hi)

    def test_resource_budget(self):
        with self.assertRaises(ValueError):
            P(tuple(range(131)))
        with self.assertRaises(ValueError):
            P((1, 1)) ** 129


class TestExactLinearAlgebra(unittest.TestCase):
    def test_rref_rank(self):
        matrix = M(((1, 2, 3), (2, 4, 6)))
        reduced, pivots = matrix.rref()
        self.assertEqual(pivots, (0,))
        self.assertEqual(reduced.rows[1], (0, 0, 0))
        self.assertEqual(matrix.rank, 1)

    def test_determinants(self):
        self.assertEqual(M(((1, 2), (3, 4))).determinant(), -2)
        self.assertEqual(M(((1, 2), (2, 4))).determinant(), 0)
        self.assertEqual(M(((7,),)).determinant(), 7)

    def test_inverse(self):
        matrix = M(((1, 2), (3, 5)))
        self.assertEqual(matrix @ matrix.inverse(), M.identity(2))
        with self.assertRaises(ValueError):
            M(((1, 2), (2, 4))).inverse()

    def test_affine_solution_and_nullspace(self):
        a = M(((1, 1, 1), (0, 1, 1)))
        solution = a.solve((3, 2))
        self.assertEqual(solution.particular, (1, 2, 0))
        self.assertEqual(len(solution.nullspace), 1)
        kernel = solution.nullspace[0]
        for row in a.rows:
            self.assertEqual(sum(x*y for x,y in zip(row, kernel)), 0)
        for row, b in zip(a.rows, (3, 2)):
            self.assertEqual(sum(x*y for x,y in zip(row, solution.particular)), b)

    def test_inconsistent_system(self):
        with self.assertRaises(ValueError):
            M(((1, 1), (1, 1))).solve((1, 2))

    def test_characteristic_polynomial(self):
        matrix = M(((1, 2), (3, 4)))
        characteristic = matrix.characteristic_polynomial()
        self.assertEqual(characteristic, P((-2, -5, 1)))
        self.assertEqual(characteristic(0), matrix.determinant())

    def test_matrix_dimensions(self):
        with self.assertRaises(ValueError):
            M(((1, 2), (1,)))


class TestDiscreteAndApplications(unittest.TestCase):
    def test_crt_coprime(self):
        self.assertEqual(chinese_remainder(((2, 3), (3, 5))), (8, 15))

    def test_crt_non_coprime(self):
        self.assertEqual(chinese_remainder(((2, 6), (5, 9))), (14, 18))
        with self.assertRaises(ValueError):
            chinese_remainder(((0, 2), (1, 2)))

    def test_berlekamp_massey_fibonacci(self):
        recurrence = berlekamp_massey((0, 1, 1, 2, 3, 5, 8, 13, 21))
        self.assertEqual(recurrence, (1, 1))
        numerator, denominator = rational_generating_function(
            (0, 1, 1, 2, 3, 5, 8, 13, 21)
        )
        self.assertEqual(numerator, P((0, 1)))
        self.assertEqual(denominator, P((1, -1, -1)))

    def test_berlekamp_massey_geometric(self):
        self.assertEqual(berlekamp_massey((1, 2, 4, 8, 16)), (2,))
        self.assertEqual(berlekamp_massey((0, 0, 0)), ())

    def test_spanning_trees(self):
        self.assertEqual(spanning_tree_count(((0, 1, 1), (1, 0, 1), (1, 1, 0))), 3)
        self.assertEqual(spanning_tree_count(((0, 1, 0), (1, 0, 1), (0, 1, 0))), 1)
        self.assertEqual(spanning_tree_count(((0, 0), (0, 0))), 0)

    def test_reject_asymmetric_graph(self):
        with self.assertRaises(ValueError):
            spanning_tree_count(((0, 1), (0, 0)))

    def test_absorbing_chain_exact(self):
        result = absorbing_chain((("1/2", "1/2"), (0, "1/4")))
        self.assertEqual(result["expected_steps"], ["10/3", "4/3"])
        with self.assertRaises(ValueError):
            absorbing_chain(((1,),))

    def test_bounded_lp_feasible(self):
        result = bounded_linear_program(
            (3, 2), (((1, 1), 4),), ((0, 3), (0, 4))
        )
        self.assertEqual(result["optimum"], "11")
        self.assertEqual(result["point"], ["3", "1"])
        self.assertEqual(result["arithmetic"], "exact-rational")

    def test_bounded_lp_infeasible(self):
        with self.assertRaises(ValueError):
            bounded_linear_program((1,), (((1,), -1),), ((0, 2),))

    def test_lp_minimization(self):
        result = bounded_linear_program((1, 2), (), ((1, 3), (2, 4)),
                                        maximize=False)
        self.assertEqual(result["point"], ["1", "2"])
        self.assertEqual(result["optimum"], "5")


if __name__ == "__main__":
    unittest.main()
