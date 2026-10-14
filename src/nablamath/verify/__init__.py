"""Independent exact solvers and checks. Exact evidence is not a Lean proof."""
from .certificate import Verification, solve, verify

__all__ = ["Verification", "solve", "verify"]
