"""NablaMath public API.

v0.3 uses lazy imports for heavy visualization/tensor/ML backends so the symbolic
and PDF-report core can import quickly even in restricted environments.
"""
from .core import (
    Expr, Number, Symbol, Equation, symbol, symbols,
    sin, cos, exp, log, sqrt, latex,
)
from .algebra import expand, factor, polynomial_coefficients, polynomial_to_expr, degree, analyze_quadratic
from .parser import parse_expr
from .autodiff import Var
from .reports import (
    CalculationStep, ReportAsset, ReportSection, LatexEquationRenderer,
    StepByStepDeriver, ExtremePDFReport, build_function_report,
)


def _lazy(module: str, name: str):
    mod = __import__(f"nablamath.{module}", fromlist=[name])
    return getattr(mod, name)


def plot2d(*args, **kwargs): return _lazy("plotting", "plot2d")(*args, **kwargs)
def plot3d(*args, **kwargs): return _lazy("plotting", "plot3d")(*args, **kwargs)
def plot_contour_with_path(*args, **kwargs): return _lazy("plotting", "plot_contour_with_path")(*args, **kwargs)
def plot_vector_field2d(*args, **kwargs): return _lazy("plotting", "plot_vector_field2d")(*args, **kwargs)
def plot_gradient_field2d(*args, **kwargs): return _lazy("plotting", "plot_gradient_field2d")(*args, **kwargs)
def plot_loss_dashboard(*args, **kwargs): return _lazy("plotting", "plot_loss_dashboard")(*args, **kwargs)

def gradient_descent(*args, **kwargs): return _lazy("optimize", "gradient_descent")(*args, **kwargs)
def newton_optimize(*args, **kwargs): return _lazy("optimize", "newton_optimize")(*args, **kwargs)
def random_search(*args, **kwargs): return _lazy("optimize", "random_search")(*args, **kwargs)
def simulated_annealing(*args, **kwargs): return _lazy("optimize", "simulated_annealing")(*args, **kwargs)
def adam_optimize(*args, **kwargs): return _lazy("optimize", "adam_optimize")(*args, **kwargs)
def rmsprop_optimize(*args, **kwargs): return _lazy("optimize", "rmsprop_optimize")(*args, **kwargs)
def auto_optimize(*args, **kwargs): return _lazy("optimize", "auto_optimize")(*args, **kwargs)
def SelfImprovingOptimizer(*args, **kwargs): return _lazy("optimize", "SelfImprovingOptimizer")(*args, **kwargs)

def NamedTensor(*args, **kwargs): return _lazy("tensor", "NamedTensor")(*args, **kwargs)
def TensorVar(*args, **kwargs): return _lazy("autodiff_tensor", "TensorVar")(*args, **kwargs)
def MLP(*args, **kwargs): return _lazy("ml", "MLP")(*args, **kwargs)
def research(*args, **kwargs): return _lazy("analysis", "research")(*args, **kwargs)
def ResearchReport(*args, **kwargs): return _lazy("analysis", "ResearchReport")(*args, **kwargs)
def SelfImprovingLoop(*args, **kwargs): return _lazy("recursive", "SelfImprovingLoop")(*args, **kwargs)
def ExperimentMemory(*args, **kwargs): return _lazy("recursive", "ExperimentMemory")(*args, **kwargs)
def RecursiveCandidate(*args, **kwargs): return _lazy("recursive", "RecursiveCandidate")(*args, **kwargs)
def pareto_front(*args, **kwargs): return _lazy("recursive", "pareto_front")(*args, **kwargs)

# v0.3 lazy wrappers
def FigureMetadata(*args, **kwargs): return _lazy("viz_enterprise", "FigureMetadata")(*args, **kwargs)
def VisualTheme(*args, **kwargs): return _lazy("viz_enterprise", "VisualTheme")(*args, **kwargs)
def VisualLayer(*args, **kwargs): return _lazy("viz_enterprise", "VisualLayer")(*args, **kwargs)
def ScientificFigure(*args, **kwargs): return _lazy("viz_enterprise", "ScientificFigure")(*args, **kwargs)
def PlotlyRenderer(*args, **kwargs): return _lazy("viz_enterprise", "PlotlyRenderer")(*args, **kwargs)
def plot2d_extreme(*args, **kwargs): return _lazy("viz_enterprise", "plot2d_extreme")(*args, **kwargs)
def plot3d_extreme(*args, **kwargs): return _lazy("viz_enterprise", "plot3d_extreme")(*args, **kwargs)
def plot_gradient_field_extreme(*args, **kwargs): return _lazy("viz_enterprise", "plot_gradient_field_extreme")(*args, **kwargs)
def optimization_dashboard_extreme(*args, **kwargs): return _lazy("viz_enterprise", "optimization_dashboard_extreme")(*args, **kwargs)
def function_visual_report_extreme(*args, **kwargs): return _lazy("viz_enterprise", "function_visual_report_extreme")(*args, **kwargs)

__all__ = [
    "Expr", "Number", "Symbol", "Equation", "symbol", "symbols", "sin", "cos", "exp", "log", "sqrt", "latex",
    "expand", "factor", "polynomial_coefficients", "polynomial_to_expr", "degree", "analyze_quadratic", "parse_expr", "Var",
    "CalculationStep", "ReportAsset", "ReportSection", "LatexEquationRenderer", "StepByStepDeriver", "ExtremePDFReport", "build_function_report",
    "plot2d", "plot3d", "plot_contour_with_path", "plot_vector_field2d", "plot_gradient_field2d", "plot_loss_dashboard",
    "gradient_descent", "newton_optimize", "random_search", "simulated_annealing", "adam_optimize", "rmsprop_optimize", "auto_optimize", "SelfImprovingOptimizer",
    "NamedTensor", "TensorVar", "MLP", "research", "ResearchReport", "SelfImprovingLoop", "ExperimentMemory", "RecursiveCandidate", "pareto_front",
    "FigureMetadata", "VisualTheme", "VisualLayer", "ScientificFigure", "PlotlyRenderer", "plot2d_extreme", "plot3d_extreme", "plot_gradient_field_extreme", "optimization_dashboard_extreme", "function_visual_report_extreme",
]
from .latex_report import ExtremeLatexPDFReport, LatexReportResult, build_extreme_latex_function_report
__all__ += ["ExtremeLatexPDFReport", "LatexReportResult", "build_extreme_latex_function_report"]
