from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import math

import numpy as np

from .core import Expr, Symbol


@dataclass
class PlotResult:
    figure: object
    axis: object
    path: Optional[str] = None


def plot2d(
    expr: Expr,
    var: Symbol,
    x_range: Tuple[float, float] = (-10.0, 10.0),
    samples: int = 1000,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    latex: bool = True,
    grid: bool = True,
    derivative: bool = False,
    save: str | None = None,
) -> PlotResult:
    import matplotlib.pyplot as plt
    xs = np.linspace(x_range[0], x_range[1], samples)
    ys = []
    for x in xs:
        try:
            y = expr.eval({var.name: float(x)})
            if math.isfinite(y):
                ys.append(y)
            else:
                ys.append(np.nan)
        except Exception:
            ys.append(np.nan)

    fig, ax = plt.subplots(figsize=(9, 5))
    label = f"${expr.to_latex()}$" if latex else str(expr)
    ax.plot(xs, ys, label=label)

    if derivative:
        dexpr = expr.diff(var).simplify()
        dys = []
        for x in xs:
            try:
                y = dexpr.eval({var.name: float(x)})
                dys.append(y if math.isfinite(y) else np.nan)
            except Exception:
                dys.append(np.nan)
        dlabel = f"$\\frac{{d}}{{d{var.to_latex()}}}({expr.to_latex()})$" if latex else "derivative"
        ax.plot(xs, dys, linestyle="--", label=dlabel)

    ax.set_title(title or (f"${expr.to_latex()}$" if latex else str(expr)))
    ax.set_xlabel(xlabel or (f"${var.to_latex()}$" if latex else var.name))
    ax.set_ylabel(ylabel or "$y$" if latex else "y")
    if grid:
        ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    if save:
        fig.savefig(save, dpi=180, bbox_inches="tight")
    return PlotResult(fig, ax, save)


def plot3d(
    expr: Expr,
    variables: Sequence[Symbol],
    x_range: Tuple[float, float] = (-5.0, 5.0),
    y_range: Tuple[float, float] = (-5.0, 5.0),
    samples: int = 120,
    title: str | None = None,
    latex: bool = True,
    contours: bool = True,
    save: str | None = None,
) -> PlotResult:
    import matplotlib.pyplot as plt
    if len(variables) != 2:
        raise ValueError("plot3d exige exatamente duas variáveis.")
    xvar, yvar = variables
    xs = np.linspace(x_range[0], x_range[1], samples)
    ys = np.linspace(y_range[0], y_range[1], samples)
    X, Y = np.meshgrid(xs, ys)
    Z = np.empty_like(X, dtype=float)
    for i in range(samples):
        for j in range(samples):
            try:
                val = expr.eval({xvar.name: float(X[i, j]), yvar.name: float(Y[i, j])})
                Z[i, j] = val if math.isfinite(val) else np.nan
            except Exception:
                Z[i, j] = np.nan

    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(X, Y, Z, linewidth=0, antialiased=True, alpha=0.88)
    if contours:
        finite = Z[np.isfinite(Z)]
        if finite.size:
            zmin = float(np.nanmin(finite))
            ax.contour(X, Y, Z, zdir="z", offset=zmin, levels=20, alpha=0.65)
            ax.set_zlim(zmin, float(np.nanmax(finite)))
    ax.set_title(title or (f"${expr.to_latex()}$" if latex else str(expr)))
    ax.set_xlabel(f"${xvar.to_latex()}$" if latex else xvar.name)
    ax.set_ylabel(f"${yvar.to_latex()}$" if latex else yvar.name)
    ax.set_zlabel("$z$" if latex else "z")
    fig.tight_layout()
    if save:
        fig.savefig(save, dpi=180, bbox_inches="tight")
    return PlotResult(fig, ax, save)


def plot_contour_with_path(
    expr: Expr,
    variables: Sequence[Symbol],
    path: Sequence[Dict[str, float]],
    x_range: Tuple[float, float] = (-5, 5),
    y_range: Tuple[float, float] = (-5, 5),
    samples: int = 160,
    save: str | None = None,
) -> PlotResult:
    import matplotlib.pyplot as plt
    if len(variables) != 2:
        raise ValueError("plot_contour_with_path exige duas variáveis.")
    xvar, yvar = variables
    xs = np.linspace(x_range[0], x_range[1], samples)
    ys = np.linspace(y_range[0], y_range[1], samples)
    X, Y = np.meshgrid(xs, ys)
    Z = np.empty_like(X, dtype=float)
    for i in range(samples):
        for j in range(samples):
            try:
                Z[i, j] = expr.eval({xvar.name: float(X[i, j]), yvar.name: float(Y[i, j])})
            except Exception:
                Z[i, j] = np.nan
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.contour(X, Y, Z, levels=30)
    if path:
        px = [p[xvar.name] for p in path]
        py = [p[yvar.name] for p in path]
        ax.plot(px, py, marker="o", markersize=2, linewidth=1.5)
        ax.scatter([px[0]], [py[0]], marker="x", s=80, label="início")
        ax.scatter([px[-1]], [py[-1]], marker="*", s=120, label="fim")
    ax.set_title(f"Trajetória de otimização em ${expr.to_latex()}$")
    ax.set_xlabel(f"${xvar.to_latex()}$")
    ax.set_ylabel(f"${yvar.to_latex()}$")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    if save:
        fig.savefig(save, dpi=180, bbox_inches="tight")
    return PlotResult(fig, ax, save)


def plot_vector_field2d(
    fx: Expr,
    fy: Expr,
    variables: Sequence[Symbol],
    x_range: Tuple[float, float] = (-5, 5),
    y_range: Tuple[float, float] = (-5, 5),
    samples: int = 25,
    normalize: bool = True,
    title: str | None = None,
    save: str | None = None,
) -> PlotResult:
    """Plot a 2D vector field (fx(x,y), fy(x,y))."""
    import matplotlib.pyplot as plt
    if len(variables) != 2:
        raise ValueError("plot_vector_field2d exige duas variáveis.")
    xvar, yvar = variables
    xs = np.linspace(*x_range, samples)
    ys = np.linspace(*y_range, samples)
    X, Y = np.meshgrid(xs, ys)
    U = np.empty_like(X, dtype=float)
    V = np.empty_like(Y, dtype=float)
    for i in range(samples):
        for j in range(samples):
            point = {xvar.name: float(X[i, j]), yvar.name: float(Y[i, j])}
            try:
                U[i, j] = fx.eval(point)
                V[i, j] = fy.eval(point)
            except Exception:
                U[i, j], V[i, j] = np.nan, np.nan
    if normalize:
        mag = np.sqrt(U * U + V * V)
        U = U / (mag + 1e-12)
        V = V / (mag + 1e-12)
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.quiver(X, Y, U, V, angles="xy")
    ax.set_title(title or f"Campo vetorial: $({fx.to_latex()}, {fy.to_latex()})$")
    ax.set_xlabel(f"${xvar.to_latex()}$")
    ax.set_ylabel(f"${yvar.to_latex()}$")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    if save:
        fig.savefig(save, dpi=180, bbox_inches="tight")
    return PlotResult(fig, ax, save)


def plot_gradient_field2d(
    expr: Expr,
    variables: Sequence[Symbol],
    x_range: Tuple[float, float] = (-5, 5),
    y_range: Tuple[float, float] = (-5, 5),
    samples: int = 25,
    descent: bool = True,
    save: str | None = None,
) -> PlotResult:
    grads = expr.grad(variables)
    fx = -grads[0] if descent else grads[0]
    fy = -grads[1] if descent else grads[1]
    title = f"Campo de {'-gradiente' if descent else 'gradiente'} de ${expr.to_latex()}$"
    return plot_vector_field2d(fx, fy, variables, x_range, y_range, samples, True, title, save)


def plot_loss_dashboard(
    expr: Expr,
    variables: Sequence[Symbol],
    trace,
    x_range: Tuple[float, float] = (-5, 5),
    y_range: Tuple[float, float] = (-5, 5),
    save_prefix: str = "nablamath_dashboard",
) -> Dict[str, str]:
    """Create multiple static diagnostics for a 2D optimization problem."""
    paths = {
        "surface": f"{save_prefix}_surface.png",
        "contour": f"{save_prefix}_contour.png",
        "gradient": f"{save_prefix}_gradient.png",
    }
    plot3d(expr, variables, x_range=x_range, y_range=y_range, save=paths["surface"])
    plot_contour_with_path(expr, variables, trace.path, x_range=x_range, y_range=y_range, save=paths["contour"])
    plot_gradient_field2d(expr, variables, x_range=x_range, y_range=y_range, save=paths["gradient"])
    return paths
