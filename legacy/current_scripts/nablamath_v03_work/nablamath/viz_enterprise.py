from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import json
import math

import numpy as np

from .core import Expr, Symbol


@dataclass
class FigureMetadata:
    """Reproducibility metadata for scientific visualization."""

    library: str = "NablaMath"
    version: str = "0.3.0"
    expression: Optional[str] = None
    latex: Optional[str] = None
    variables: List[str] = field(default_factory=list)
    domain: Dict[str, Any] = field(default_factory=dict)
    resolution: Any = None
    backend: str = "plotly"
    seed: Optional[int] = None
    warnings: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VisualTheme:
    """Portable styling contract shared by plotting backends."""

    name: str = "enterprise_dark"
    plotly_template: str = "plotly_dark"
    font_family: str = "Computer Modern, Latin Modern Roman, Times New Roman, serif"
    title_size: int = 22
    axis_title_size: int = 16
    tick_size: int = 12
    line_width: float = 2.0
    marker_size: float = 6.0
    show_grid: bool = True

    @staticmethod
    def enterprise_dark() -> "VisualTheme":
        return VisualTheme(name="enterprise_dark", plotly_template="plotly_dark")

    @staticmethod
    def scientific_light() -> "VisualTheme":
        return VisualTheme(name="scientific_light", plotly_template="plotly_white")

    @staticmethod
    def paper() -> "VisualTheme":
        return VisualTheme(name="paper", plotly_template="simple_white", title_size=18, axis_title_size=14)


@dataclass
class VisualLayer:
    name: str
    kind: str
    data: Dict[str, Any]
    style: Dict[str, Any] = field(default_factory=dict)
    visible: bool = True


@dataclass
class ScientificFigure:
    """Structured scientific figure.

    It stores layers, metadata, diagnostics and can export a JSON spec.
    Rendering is delegated to backend renderers so NablaMath can grow from
    Matplotlib to Plotly, PyVista, Manim and WebGL without changing user code.
    """

    title: str
    subtitle: Optional[str] = None
    latex: Optional[str] = None
    description: Optional[str] = None
    theme: VisualTheme = field(default_factory=VisualTheme.enterprise_dark)
    metadata: FigureMetadata = field(default_factory=FigureMetadata)
    layers: List[VisualLayer] = field(default_factory=list)
    annotations: List[Dict[str, Any]] = field(default_factory=list)

    def add_layer(self, layer: VisualLayer) -> "ScientificFigure":
        self.layers.append(layer)
        return self

    def add_annotation(self, annotation: Dict[str, Any]) -> "ScientificFigure":
        self.annotations.append(annotation)
        return self

    def to_spec(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "latex": self.latex,
            "description": self.description,
            "theme": asdict(self.theme),
            "metadata": asdict(self.metadata),
            "layers": [
                {"name": l.name, "kind": l.kind, "style": l.style, "visible": l.visible}
                for l in self.layers
            ],
            "annotations": self.annotations,
        }

    def export_metadata(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_spec(), indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def render(self, backend: str = "plotly") -> Any:
        if backend == "plotly":
            return PlotlyRenderer().render(self)
        raise ValueError(f"Unsupported backend: {backend}")

    def export_html(self, path: str | Path, include_plotlyjs: str = "cdn") -> Path:
        rendered = self.render("plotly")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(rendered, "write_html"):
            rendered.write_html(str(path), include_plotlyjs=include_plotlyjs)
        else:
            path.write_text(str(rendered), encoding="utf-8")
        return path


class PlotlyRenderer:
    """Plotly renderer for interactive enterprise-grade HTML outputs."""

    def render(self, figure: ScientificFigure) -> Any:
        try:
            import plotly.graph_objects as go
        except Exception as exc:  # pragma: no cover - environment fallback
            return _fallback_html(figure, f"Plotly unavailable: {exc}")

        fig = go.Figure()

        for layer in figure.layers:
            if not layer.visible:
                continue
            kind = layer.kind
            data = layer.data
            style = layer.style

            if kind == "surface":
                fig.add_trace(go.Surface(
                    x=data["X"], y=data["Y"], z=data["Z"], name=layer.name,
                    opacity=style.get("opacity", 0.95), showscale=style.get("showscale", True),
                    colorscale=style.get("colorscale", "Viridis"),
                ))
            elif kind == "contour":
                fig.add_trace(go.Contour(
                    x=data["x"], y=data["y"], z=data["Z"], name=layer.name,
                    contours_coloring=style.get("coloring", "heatmap"),
                    line_width=style.get("line_width", 1.0),
                    colorscale=style.get("colorscale", "Viridis"),
                    opacity=style.get("opacity", 1.0),
                ))
            elif kind == "line2d":
                fig.add_trace(go.Scatter(
                    x=data["x"], y=data["y"], mode=style.get("mode", "lines"),
                    name=layer.name, line=dict(width=style.get("width", figure.theme.line_width)),
                ))
            elif kind == "scatter2d":
                fig.add_trace(go.Scatter(
                    x=data["x"], y=data["y"], mode=style.get("mode", "markers"),
                    name=layer.name, marker=dict(size=style.get("size", figure.theme.marker_size)),
                ))
            elif kind == "path2d":
                points = data["points"]
                fig.add_trace(go.Scatter(
                    x=[p[0] for p in points], y=[p[1] for p in points],
                    mode="lines+markers", name=layer.name,
                    line=dict(width=style.get("width", figure.theme.line_width)),
                    marker=dict(size=style.get("marker_size", figure.theme.marker_size)),
                ))
            elif kind == "path3d":
                points = data["points"]
                fig.add_trace(go.Scatter3d(
                    x=[p[0] for p in points], y=[p[1] for p in points], z=[p[2] for p in points],
                    mode="lines+markers", name=layer.name,
                    line=dict(width=style.get("width", figure.theme.line_width)),
                    marker=dict(size=style.get("marker_size", figure.theme.marker_size)),
                ))
            elif kind == "vector_field2d":
                x = np.asarray(data["X"]).ravel(); y = np.asarray(data["Y"]).ravel()
                u = np.asarray(data["U"]).ravel(); v = np.asarray(data["V"]).ravel()
                scale = float(style.get("scale", 0.2))
                xs: List[float] = []
                ys: List[float] = []
                for xi, yi, ui, vi in zip(x, y, u, v):
                    mag = math.sqrt(float(ui * ui + vi * vi)) + 1e-12
                    xs.extend([float(xi), float(xi + scale * ui / mag), None])
                    ys.extend([float(yi), float(yi + scale * vi / mag), None])
                fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=layer.name, line=dict(width=1)))
            elif kind == "table":
                fig.add_trace(go.Table(header=dict(values=data["headers"]), cells=dict(values=data["cells"]), name=layer.name))

        title = figure.title
        if figure.subtitle:
            title += f"<br><sup>{figure.subtitle}</sup>"
        if figure.latex:
            title += f"<br><sup>{figure.latex}</sup>"

        fig.update_layout(
            title=title,
            template=figure.theme.plotly_template,
            font=dict(family=figure.theme.font_family),
            xaxis=dict(showgrid=figure.theme.show_grid, title="x"),
            yaxis=dict(showgrid=figure.theme.show_grid, title="y"),
            scene=dict(xaxis_title="x", yaxis_title="y", zaxis_title="z"),
            legend=dict(orientation="h"),
            margin=dict(l=20, r=20, t=90, b=20),
        )
        return fig


def _fallback_html(figure: ScientificFigure, message: str) -> str:
    return "<html><body><h1>{}</h1><pre>{}</pre><pre>{}</pre></body></html>".format(
        figure.title, message, json.dumps(figure.to_spec(), indent=2, ensure_ascii=False)
    )


def _domain_key(domain: Mapping[Any, Tuple[float, float]], var: Symbol) -> Tuple[float, float]:
    if var in domain:
        return domain[var]  # type: ignore[index]
    if var.name in domain:
        return domain[var.name]  # type: ignore[index]
    raise KeyError(f"Domain missing variable {var.name}")


def _safe_eval_grid(expr: Expr, x_var: Symbol, y_var: Symbol, X: np.ndarray, Y: np.ndarray) -> Tuple[np.ndarray, List[str], Dict[str, Any]]:
    Z = np.empty_like(X, dtype=float)
    warnings: List[str] = []
    for i in range(X.shape[0]):
        for j in range(X.shape[1]):
            try:
                val = expr.eval({x_var.name: float(X[i, j]), y_var.name: float(Y[i, j])})
                if not np.isfinite(val):
                    Z[i, j] = np.nan
                else:
                    Z[i, j] = val
            except Exception:
                Z[i, j] = np.nan
    nan_ratio = float(np.isnan(Z).mean())
    finite = Z[np.isfinite(Z)]
    diagnostics: Dict[str, Any] = {"nan_ratio": nan_ratio, "finite_count": int(finite.size)}
    if finite.size:
        diagnostics.update({
            "z_min": float(np.min(finite)), "z_max": float(np.max(finite)),
            "z_mean": float(np.mean(finite)), "z_std": float(np.std(finite)),
        })
    if nan_ratio > 0:
        warnings.append(f"NaN/invalid grid ratio: {nan_ratio:.4f}")
    return Z, warnings, diagnostics


def plot2d_extreme(expr: Expr, variable: Symbol, domain: Tuple[float, float], resolution: int = 2000,
                   title: str = "NablaMath 2D scientific plot", theme: Optional[VisualTheme] = None) -> ScientificFigure:
    xs = np.linspace(domain[0], domain[1], resolution)
    ys = np.empty_like(xs, dtype=float)
    warnings: List[str] = []
    for i, xv in enumerate(xs):
        try:
            yv = expr.eval({variable.name: float(xv)})
            ys[i] = yv if np.isfinite(yv) else np.nan
        except Exception:
            ys[i] = np.nan
    nan_ratio = float(np.isnan(ys).mean())
    if nan_ratio:
        warnings.append(f"NaN/invalid sample ratio: {nan_ratio:.4f}")
    metadata = FigureMetadata(
        expression=str(expr), latex=expr.to_latex(), variables=[variable.name],
        domain={variable.name: list(domain)}, resolution=resolution, warnings=warnings,
        diagnostics={"nan_ratio": nan_ratio},
    )
    fig = ScientificFigure(title=title, latex=f"${expr.to_latex()}$", theme=theme or VisualTheme.enterprise_dark(), metadata=metadata)
    fig.add_layer(VisualLayer("f(x)", "line2d", {"x": xs, "y": ys}, {"width": 2.5}))
    return fig


def plot3d_extreme(expr: Expr, variables: Sequence[Symbol], domain: Mapping[Any, Tuple[float, float]],
                   resolution: int | Tuple[int, int] = 180, title: str = "NablaMath 3D scientific surface",
                   contours: bool = True, theme: Optional[VisualTheme] = None) -> ScientificFigure:
    x_var, y_var = variables
    rx = _domain_key(domain, x_var); ry = _domain_key(domain, y_var)
    if isinstance(resolution, int):
        nx = ny = resolution
    else:
        nx, ny = resolution
    xs = np.linspace(rx[0], rx[1], nx)
    ys = np.linspace(ry[0], ry[1], ny)
    X, Y = np.meshgrid(xs, ys)
    Z, warnings, diagnostics = _safe_eval_grid(expr, x_var, y_var, X, Y)
    metadata = FigureMetadata(
        expression=str(expr), latex=expr.to_latex(), variables=[x_var.name, y_var.name],
        domain={x_var.name: list(rx), y_var.name: list(ry)}, resolution=[nx, ny],
        warnings=warnings, diagnostics=diagnostics,
    )
    fig = ScientificFigure(title=title, latex=f"${expr.to_latex()}$", theme=theme or VisualTheme.enterprise_dark(), metadata=metadata)
    fig.add_layer(VisualLayer("surface", "surface", {"X": X, "Y": Y, "Z": Z}, {"opacity": 0.96, "showscale": True}))
    if contours:
        fig.add_layer(VisualLayer("contours", "contour", {"x": xs, "y": ys, "Z": Z}, {"opacity": 0.72, "line_width": 1.0}))
    return fig


def plot_gradient_field_extreme(expr: Expr, variables: Sequence[Symbol], domain: Mapping[Any, Tuple[float, float]],
                                resolution: int = 21, title: str = "NablaMath gradient field") -> ScientificFigure:
    x_var, y_var = variables
    gx, gy = expr.grad([x_var, y_var])
    rx = _domain_key(domain, x_var); ry = _domain_key(domain, y_var)
    xs = np.linspace(rx[0], rx[1], resolution); ys = np.linspace(ry[0], ry[1], resolution)
    X, Y = np.meshgrid(xs, ys)
    U = np.empty_like(X, dtype=float); V = np.empty_like(Y, dtype=float)
    for i in range(X.shape[0]):
        for j in range(X.shape[1]):
            vals = {x_var.name: float(X[i, j]), y_var.name: float(Y[i, j])}
            try:
                U[i, j] = -gx.eval(vals)
                V[i, j] = -gy.eval(vals)
            except Exception:
                U[i, j] = np.nan; V[i, j] = np.nan
    fig = ScientificFigure(title=title, latex=f"$-\\nabla f,\\quad f={expr.to_latex()}$", metadata=FigureMetadata(
        expression=str(expr), latex=expr.to_latex(), variables=[x_var.name, y_var.name],
        domain={x_var.name: list(rx), y_var.name: list(ry)}, resolution=[resolution, resolution],
    ))
    fig.add_layer(VisualLayer("negative gradient", "vector_field2d", {"X": X, "Y": Y, "U": U, "V": V}, {"scale": 0.28}))
    return fig


def optimization_dashboard_extreme(expr: Expr, variables: Sequence[Symbol], traces: Mapping[str, Any],
                                   domain: Mapping[Any, Tuple[float, float]], output_dir: str | Path,
                                   resolution: int = 160) -> Dict[str, Path]:
    """Export a compact set of interactive HTML visualizations for optimization traces."""
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    x_var, y_var = variables
    surface = plot3d_extreme(expr, variables, domain, resolution=resolution, title="Optimization surface with trajectories")
    for name, trace in traces.items():
        points = []
        raw_points = getattr(trace, "points", None) or getattr(trace, "history", None) or []
        for p in raw_points:
            if isinstance(p, Mapping):
                xv, yv = float(p[x_var.name]), float(p[y_var.name])
            else:
                xv, yv = float(p[0]), float(p[1])
            try:
                zv = expr.eval({x_var.name: xv, y_var.name: yv})
            except Exception:
                zv = float("nan")
            points.append((xv, yv, zv))
        if points:
            surface.add_layer(VisualLayer(f"path: {name}", "path3d", {"points": points}, {"marker_size": 4}))
    surface_path = surface.export_html(output_dir / "optimization_surface.html")
    metadata_path = surface.export_metadata(output_dir / "optimization_surface.metadata.json")

    # Loss curves dashboard.
    import plotly.graph_objects as go
    loss_fig = go.Figure()
    for name, trace in traces.items():
        values = getattr(trace, "values", None) or getattr(trace, "losses", None) or []
        if values:
            loss_fig.add_trace(go.Scatter(y=list(values), mode="lines", name=name))
    loss_fig.update_layout(title="Optimization loss curves", template="plotly_dark", xaxis_title="iteration", yaxis_title="objective")
    loss_path = output_dir / "optimization_loss_curves.html"
    loss_fig.write_html(str(loss_path), include_plotlyjs="cdn")
    return {"surface_html": surface_path, "metadata_json": metadata_path, "loss_curves_html": loss_path}


def function_visual_report_extreme(expr: Expr, variables: Sequence[Symbol], domain: Mapping[Any, Tuple[float, float]],
                                   output_dir: str | Path, resolution: int = 180) -> Dict[str, Path]:
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    outputs: Dict[str, Path] = {}
    surface = plot3d_extreme(expr, variables, domain, resolution=resolution)
    outputs["surface_html"] = surface.export_html(output_dir / "surface3d.html")
    outputs["surface_metadata"] = surface.export_metadata(output_dir / "surface3d.metadata.json")
    field = plot_gradient_field_extreme(expr, variables, domain, resolution=25)
    outputs["gradient_field_html"] = field.export_html(output_dir / "gradient_field.html")
    outputs["gradient_field_metadata"] = field.export_metadata(output_dir / "gradient_field.metadata.json")
    return outputs
