import math
import numpy as np
from nablamath import *


def test_expand_and_quadratic():
    x, = symbols("x")
    expr = expand((x + 1) ** 3)
    assert abs(expr.eval({"x": 2}) - 27) < 1e-9
    q = analyze_quadratic(x**2 + 3*x + 2, x)
    r1, r2 = q.roots
    roots = sorted([r1.eval({"x": 0}), r2.eval({"x": 0})])
    assert all(abs(a-b) < 1e-9 for a, b in zip(roots, [-2.0, -1.0]))


def test_parser_and_adam():
    x, y = symbols("x y")
    expr = parse_expr("(x-3)^2 + (y+2)^2", {"x": x, "y": y})
    trace = adam_optimize(expr, [x, y], {"x": 0.0, "y": 0.0}, lr=0.1, steps=300)
    assert trace.best_value < 1e-4


def test_named_tensor_and_tensorvar():
    A = NamedTensor(np.ones((2, 3)), ["batch", "features"])
    W = NamedTensor(np.ones((3, 4)), ["features", "hidden"])
    Z = A.matmul(W, "features", "features")
    assert Z.data.shape == (2, 4)
    assert Z.axes == ("batch", "hidden")
    X = TensorVar([[1.0, 2.0]])
    WW = TensorVar([[0.5], [-1.0]])
    y = X.matmul(WW).mean()
    y.backward()
    assert WW.grad.shape == WW.data.shape
