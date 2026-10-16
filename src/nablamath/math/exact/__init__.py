"""Exact rational mathematics with bounded algorithms and explicit guarantees.

Public imports deliberately live here instead of at the global package root.
The large implementation lives in laboratory.py to keep all contracts together.
"""
from .laboratory import (
    Polynomial, RationalMatrix, AffineSolution, rational,
    polynomial_gcd, polynomial_extended_gcd, square_free_factors,
    resultant, discriminant, sturm_sequence, real_root_count,
    isolate_real_roots, interpolate, hermite_interpolate,
    bernstein_range, chinese_remainder, berlekamp_massey,
    rational_generating_function, spanning_tree_count,
    absorbing_chain, bounded_linear_program,
)

__all__ = [
    "Polynomial", "RationalMatrix", "AffineSolution", "rational",
    "polynomial_gcd", "polynomial_extended_gcd", "square_free_factors",
    "resultant", "discriminant", "sturm_sequence", "real_root_count",
    "isolate_real_roots", "interpolate", "hermite_interpolate",
    "bernstein_range", "chinese_remainder", "berlekamp_massey",
    "rational_generating_function", "spanning_tree_count",
    "absorbing_chain", "bounded_linear_program",
]
