"""Regression coverage for recovered merge damage and public scientific contracts."""
from fractions import Fraction
import importlib
import unittest

from nablamath.expression import evaluate, parse_expr, render
from nablamath.symbolic import differentiate, symbolic_gradient, symbolic_hessian, saturate


class PublicAPIRegressionTests(unittest.TestCase):
    def test_every_symbolic_export_exists(self):
        from nablamath import symbolic
        for name in symbolic.__all__:
            with self.subTest(name=name):
                self.assertTrue(hasattr(symbolic, name))

    def test_algebra_exports_survive_recovery(self):
        from nablamath.math import algebra
        for name in algebra.__all__:
            with self.subTest(name=name):
                self.assertTrue(hasattr(algebra, name))

    def test_zero_power_derivative_preserves_original_domain(self):
        result = differentiate(parse_expr('x**0'), 'x')
        self.assertEqual(evaluate(result.derivative, {'x': Fraction(0)}), 0)
        self.assertEqual(tuple(render(v) for v in result.required_nonzero), ('x',))
        self.assertTrue(result.steps)

    def test_hessian_retains_original_quotient_domain(self):
        result = symbolic_hessian(parse_expr('x/x + y*y'), ('x', 'y'))
        self.assertIn(parse_expr('x'), result[1][0].required_nonzero)

    def test_egraph_certificate_and_counts(self):
        result = saturate(parse_expr('2+3'))
        self.assertEqual(evaluate(result.expression, {}), 5)
        self.assertIsInstance(result.class_count, int)
        self.assertTrue(result.certificate_verified)

    def test_subtract_self_cannot_hide_a_singular_expression(self):
        from nablamath.expression import DomainError
        from nablamath.symbolic import AssumptionSet
        expression = parse_expr('(1/x) - (1/x)')
        result = saturate(expression)
        with self.assertRaises(DomainError):
            evaluate(result.expression, {'x': Fraction(0)})
        conditional = saturate(expression, assumptions=AssumptionSet.from_nonzero('x'))
        self.assertEqual(evaluate(conditional.expression, {'x': Fraction(2)}), 0)
        self.assertTrue(conditional.certificate_verified)
