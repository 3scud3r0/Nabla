from nablamath import *

x, y = symbols("x y")

f = (x**2 + y - 11)**2 + (x + y**2 - 7)**2

print("f =", f)
print("LaTeX =", f.to_latex())
print("Gradiente =", f.grad([x, y]))
print("Hessiana =", f.hessian([x, y]))

report = research(
    f,
    variables=[x, y],
    start={"x": 0.0, "y": 0.0},
    bounds={"x": (-6, 6), "y": (-6, 6)},
    self_improve=True,
)

print(report.to_markdown())

plot3d(f, [x, y], x_range=(-6, 6), y_range=(-6, 6), save="nablamath_plot3d.png")
plot_contour_with_path(f, [x, y], report.traces[0].path[:200], x_range=(-6, 6), y_range=(-6, 6), save="nablamath_contour_path.png")
