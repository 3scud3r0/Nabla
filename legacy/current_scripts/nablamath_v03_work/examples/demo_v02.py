from pathlib import Path
from nablamath import *

ROOT = Path(__file__).resolve().parent

x, y = symbols("x y")
expr = parse_expr("(x^2 + y - 11)^2 + (x + y^2 - 7)^2", {"x": x, "y": y})

print("=== EXPRESSÃO ===")
print(expr)
print(expr.to_latex())

print("\n=== GRADIENTE ===")
for g in expr.grad([x, y]):
    print(g, "|", g.to_latex())

print("\n=== HESSIANA ===")
for row in expr.hessian([x, y]):
    print(row)

print("\n=== EXPAND / POLY ===")
poly = expand((x + 1) ** 3)
print("expand((x+1)^3)=", poly)
print("coeffs:", polynomial_coefficients(poly, x))
print("quadratic:", analyze_quadratic(x**2 + 3*x + 2, x).to_markdown())

print("\n=== OTIMIZAÇÃO AUTO ===")
traces = auto_optimize(
    expr,
    [x, y],
    start={"x": 0.0, "y": 0.0},
    bounds={"x": (-6, 6), "y": (-6, 6)},
)
for t in traces[:4]:
    print(t.method, t.best_value, t.best_point)

print("\n=== PLOTS ===")
print("Por padrão, este demo não abre Matplotlib para evitar travamentos em ambientes headless.")
print("Para gerar plots, chame plot_loss_dashboard(...) em uma máquina local com Matplotlib configurado.")

print("\n=== NAMED TENSOR ===")
import numpy as np
A = NamedTensor(np.ones((2, 3)), axes=["batch", "features"])
W = NamedTensor(np.ones((3, 4)), axes=["features", "hidden"])
Z = A.matmul(W, left_axis="features", right_axis="features")
print(Z.explain_shape())

print("\n=== TENSOR AUTODIFF ===")
X = TensorVar([[1.0, 2.0]], label="X")
W = TensorVar([[0.5], [-1.0]], label="W")
b = TensorVar([[0.1]], label="b")
pred = X.matmul(W) + b
loss = ((pred - TensorVar([[1.0]], requires_grad=False)) ** 2).mean()
loss.backward()
print("loss:", loss.data)
print("grad W:", W.grad)
