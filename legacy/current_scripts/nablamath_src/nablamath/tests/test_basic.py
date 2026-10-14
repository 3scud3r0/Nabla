from nablamath import *


def test_derivative_polynomial():
    x, = symbols("x")
    f = x**2 + 3*x + 2
    df = f.diff(x)
    assert abs(df.eval({"x": 5}) - 13) < 1e-9


def test_autodiff_scalar():
    x = Var(2.0)
    y = x*x + 3*x + 1
    y.backward()
    assert abs(x.grad - 7.0) < 1e-9


def test_optimization():
    x, y = symbols("x y")
    f = (x - 3)**2 + (y + 2)**2
    trace = gradient_descent(f, [x, y], start={"x": 10.0, "y": 10.0}, lr=0.05, steps=500)
    assert trace.best_value < 1e-5
