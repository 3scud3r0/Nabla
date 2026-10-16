"""Formal bridge for the typed rational subset supported by NablaMath."""

from .translate import free_symbols, lean_source, lean_term, rule_lean_source, universal_lean_source
from .check import FormalCheck, verify_rule_with_lean, verify_with_lean
from .search import (
    ProofAttempt, ProofSearchResult, candidate_strategies, search_rule_proof,
    search_universal_proof, verify_ruleset_with_lean,
)

__all__ = [
    "lean_source", "lean_term", "free_symbols", "universal_lean_source", "rule_lean_source",
    "FormalCheck", "verify_with_lean", "verify_rule_with_lean", "ProofAttempt",
    "ProofSearchResult", "candidate_strategies", "search_rule_proof",
    "search_universal_proof", "verify_ruleset_with_lean",
]

from .statement import FormalStatement,Predicate
from .lean_bridge import LeanTranslation,translate_statement
from .lean_checker import LeanCheck,check_lean,prove_statement
from .smt_bridge import solve_statement
__all__ += ['FormalStatement','Predicate','LeanTranslation','translate_statement','LeanCheck','check_lean','prove_statement','solve_statement']
from .lean_std import prove_with_std, std_source, verify_std_receipt
__all__ += ['prove_with_std', 'std_source', 'verify_std_receipt']
