"""Version-one exact comparison contract; correctness, not speed ranking.

Owner: Nabla numerical/reference backend maintainers. Seed and trial budget are
fixed; SymPy is an optional independent oracle. No external solver is called on
untrusted code and no broad performance or kernel-proof claim is inferred.
"""
from fractions import Fraction
from random import Random

import pytest
from nablamath.autodiff import Tensor, tensor_hessian
from nablamath.compiler import lower_expr, compile_program
from nablamath.expression import parse_expr


def test_exact_compiled_rationals_against_sympy_128_cases():
    sympy = pytest.importorskip("sympy")
    rng = Random(951017)
    x, y = sympy.symbols("x y")
    expression = parse_expr("((x+y)**3-(x-y)**2)/(y**2+1)")
    executable = compile_program(lower_expr(expression))
    independent = ((x+y)**3-(x-y)**2)/(y**2+1)
    for _ in range(128):
        a = Fraction(rng.randrange(-20, 21), rng.randrange(1, 20))
        b = Fraction(rng.randrange(-20, 21), rng.randrange(1, 20))
        expected = independent.subs({x: sympy.Rational(a.numerator, a.denominator),
                                     y: sympy.Rational(b.numerator, b.denominator)})
        assert executable({"x": a, "y": b}) == Fraction(int(expected.p), int(expected.q))


def test_tensor_second_derivatives_against_sympy_32_cases():
    sympy = pytest.importorskip("sympy")
    x, y = sympy.symbols("x y")
    expression = (x*x+y*y) ** 2 + x*y
    gradient = [sympy.diff(expression, symbol) for symbol in (x, y)]
    hessian = sympy.hessian(expression, (x, y))
    rng = Random(314159)
    for _ in range(32):
        a, b = [rng.uniform(-2, 2) for _ in range(2)]
        # x.sum()**2 - sum(x**2) supplies 2*x*y without slicing.
        value, actual_gradient, actual_hessian = tensor_hessian(
            lambda t: (t*t).sum()**2 + (t.sum()**2-(t*t).sum())/2,
            Tensor([a,b]))
        binding = {x:a, y:b}
        assert value == pytest.approx(float(expression.subs(binding)))
        assert actual_gradient == pytest.approx([float(g.subs(binding)) for g in gradient])
        for i in range(2):
            assert actual_hessian[i] == pytest.approx([float(hessian[i,j].subs(binding)) for j in range(2)])
