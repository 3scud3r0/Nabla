from .core import (
    Expr,
    Number,
    Symbol,
    Equation,
    symbol,
    symbols,
    sin,
    cos,
    exp,
    log,
    sqrt,
    latex,
)
from .algebra import expand, factor, polynomial_coefficients, polynomial_to_expr, degree, analyze_quadratic
from .parser import parse_expr
from .tensor import NamedTensor
from .autodiff_tensor import TensorVar
from .plotting import (
    plot2d,
    plot3d,
    plot_contour_with_path,
    plot_vector_field2d,
    plot_gradient_field2d,
    plot_loss_dashboard,
)
from .optimize import (
    gradient_descent,
    newton_optimize,
    random_search,
    simulated_annealing,
    adam_optimize,
    rmsprop_optimize,
    auto_optimize,
    SelfImprovingOptimizer,
)
from .autodiff import Var
from .ml import MLP
from .analysis import research, ResearchReport
from .recursive import SelfImprovingLoop, ExperimentMemory, RecursiveCandidate, pareto_front

__all__ = [
    "Expr", "Number", "Symbol", "Equation", "symbol", "symbols",
    "sin", "cos", "exp", "log", "sqrt", "latex",
    "expand", "factor", "polynomial_coefficients", "polynomial_to_expr", "degree", "analyze_quadratic",
    "parse_expr", "NamedTensor", "TensorVar",
    "plot2d", "plot3d", "plot_contour_with_path", "plot_vector_field2d", "plot_gradient_field2d", "plot_loss_dashboard",
    "gradient_descent", "newton_optimize", "random_search", "simulated_annealing", "adam_optimize", "rmsprop_optimize", "auto_optimize", "SelfImprovingOptimizer",
    "Var", "TensorVar", "MLP", "research", "ResearchReport",
    "SelfImprovingLoop", "ExperimentMemory", "RecursiveCandidate", "pareto_front",
]
