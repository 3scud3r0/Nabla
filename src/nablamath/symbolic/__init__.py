"""Public symbolic API: exact calculus and bounded certified rewriting."""
from .parser import parse
from .derive import derive
from .differentiate import DerivativeResult, DerivativeStep, differentiate, symbolic_gradient, symbolic_hessian
from .integrate import IntegrationCertificate, integrate_polynomial
from .series import RationalLimit, TaylorSeries, rational_limit, taylor_series
from .assumptions import AssumptionSet
from .patterns import PNode, PVar, RewriteRule, RuleCondition, parse_pattern
from .proof import CertificateVerification, verify_saturation_certificate
from .egraph import EGraph, EGraphLimitError, RewriteEvent, SaturationResult, saturate

__all__ = [
    "parse", "derive", "DerivativeResult", "DerivativeStep", "differentiate",
    "symbolic_gradient", "symbolic_hessian", "IntegrationCertificate", "integrate_polynomial",
    "RationalLimit", "TaylorSeries", "rational_limit", "taylor_series", "AssumptionSet",
    "PNode", "PVar", "RewriteRule", "RuleCondition", "parse_pattern", "CertificateVerification",
    "verify_saturation_certificate", "EGraph", "EGraphLimitError", "RewriteEvent", "SaturationResult", "saturate",
]
