"""Interface pública do primeiro núcleo auditável de NablaMath."""

from .expression import Expr, Number, Symbol, Binary, parse_expr
from .research import ResearchResult, calculate
from .entity import ExpressionEntity
from .solution import SolutionBundle, VerificationRecord, solve_expression

__version__ = "1.0.0"
__all__ = ["Expr", "Number", "Symbol", "Binary", "parse_expr", "ResearchResult", "calculate", "ExpressionEntity", "SolutionBundle", "VerificationRecord", "solve_expression"]
