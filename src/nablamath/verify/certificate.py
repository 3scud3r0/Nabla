"""Separate construction, solving and residual/certificate checking."""
from dataclasses import dataclass
from fractions import Fraction

from ..core.semantic_ir import PolynomialSpec, ScientificTask, rational
from ..math.linear_algebra.matrices import Matrix
from ..symbolic.differentiate import differentiate
from ..symbolic.integrate import integrate_polynomial
from ..math.algebra.groebner import polynomial_from_expr

VERIFIER_VERSION = "exact-independent-v1"


@dataclass(frozen=True)
class Verification:
    valid: bool
    method: str
    checks: int
    errors: tuple[str, ...] = ()
    formal_proof: bool = False
    verifier_version: str = VERIFIER_VERSION

    def to_data(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


def solve(task: ScientificTask) -> tuple[Fraction, ...]:
    """Solve from the problem alone; no constructor or witness is consulted."""
    if task.family == "polynomial_integral":
        certificate = integrate_polynomial(PolynomialSpec(task.coefficients).to_expr(), "x")
        terms = dict(certificate.antiderivative_terms)
        return tuple(terms.get(i, Fraction()) for i in range(len(task.coefficients) + 1))
    inverse = Matrix(task.matrix).inverse()
    column = Matrix(tuple((value,) for value in task.rhs))
    return tuple(row[0] for row in (inverse @ column).rows)


def verify(task: ScientificTask, candidate: tuple[Fraction, ...]) -> Verification:
    try:
        if not 1 <= len(candidate) <= 33:
            return Verification(False, "invalid_candidate", 0, ("dimensao fora do limite",))
        values = tuple(rational(v) for v in candidate)
        if task.family == "linear_system":
            if len(values) != len(task.rhs):
                return Verification(False, "exact_residual_and_determinant", 0, ("dimensão divergente",))
            residuals = tuple(sum((a * b for a, b in zip(row, values)), Fraction()) - target
                              for row, target in zip(task.matrix, task.rhs))
            nonsingular = Matrix(task.matrix).determinant() != 0
            valid = nonsingular and not any(residuals)
            return Verification(valid, "exact_residual_and_determinant", len(residuals) + 1,
                                () if valid else ("resíduo não nulo ou sistema não único",))
        primitive = PolynomialSpec(values)
        derivative = differentiate(primitive.to_expr(), "x")
        # Canonical coefficient comparison checks every term, not selected samples.
        actual = polynomial_from_expr(derivative.derivative, ("x",))
        expected = polynomial_from_expr(PolynomialSpec(task.coefficients).to_expr(), ("x",))
        valid = actual.terms == expected.terms
        return Verification(valid, "symbolic_derivative_coefficient_identity", len(task.coefficients),
                            () if valid else ("derivada não corresponde ao integrando",))
    except (ValueError, TypeError, ArithmeticError) as exc:
        return Verification(False, "invalid_candidate", 0, (str(exc),))


def make_formal_certificate(statement,receipt):
    from ..core.semantic_ir import fingerprint
    from ..formal.lean_bridge import translate_statement
    translation=translate_statement(statement,receipt.get('strategy','auto')).to_data() if receipt.get('backend')=='lean4' else None
    if receipt.get('backend')=='lean4-std':
        from ..formal.lean_std import std_translation
        translation=std_translation(statement)
    payload={'schema_version':1,'statement':statement.to_data(),'translation':translation,'backend_receipt':receipt}
    return {**payload,'certificate_id':fingerprint(payload)}


def verify_formal_receipt(statement,receipt,*,project=None):
    """Regenerate and rerun the checker; a saved success flag/hash is not sufficient."""
    from pathlib import Path
    from ..core.semantic_ir import fingerprint
    from ..formal.lean_bridge import translate_statement
    from ..formal.lean_checker import check_lean
    from ..formal.smt_bridge import solve_statement
    try:
        if receipt.get('statement_id')!=statement.content_id:
            return False
        payload=dict(receipt);digest=payload.pop('receipt_id',None)
        if digest!=fingerprint(payload):return False
        if receipt.get('backend')=='lean4-std':
            from ..formal.lean_std import verify_std_receipt
            return verify_std_receipt(statement,receipt,project=Path(project or 'lean'))
        if receipt.get('backend')=='lean4':
            translation=translate_statement(statement,receipt.get('strategy','auto'))
            if receipt.get('source_hash')!=translation.source_hash or receipt.get('status')!='proved':
                return False
            result=check_lean(translation,Path(project or 'lean'))
            return (result.verified and receipt.get('formal_proof') is True and result.axioms==tuple(receipt.get('axioms',()))
                    and receipt.get('tool_version')==result.tool_version and receipt.get('returncode')==0)
        if receipt.get('backend')=='z3':
            result=solve_statement(statement,timeout_ms=receipt.get('timeout_ms',5000))
            if result.get('status')!=receipt.get('status') or result.get('query_hash')!=receipt.get('query_hash') or receipt.get('formal_proof') is not False:
                return False
            if result.get('status')=='counterexample':
                exact={name:rational(value) for name,value in receipt.get('witness',{}).items()}
                return set(exact)==set(statement.variables) and all(p.evaluate(exact) for p in statement.hypotheses) and not statement.goal.evaluate(exact)
            return (result.get('status')=='unsat' and result.get('proof')==receipt.get('proof')
                    and result.get('proof_truncated')==receipt.get('proof_truncated')
                    and result.get('solver_version')==receipt.get('solver_version'))
        return False
    except (ValueError,KeyError,TypeError,ArithmeticError):
        return False


def verify_formal_certificate(certificate,*,project=None):
    from ..core.semantic_ir import fingerprint
    from ..formal.statement import FormalStatement
    try:
        payload=dict(certificate);digest=payload.pop('certificate_id')
        if payload['schema_version']!=1 or digest!=fingerprint(payload):return False
        statement=FormalStatement.from_data(payload['statement'])
        if 'translation' in payload:
            from ..formal.lean_bridge import translate_statement
            from ..core.semantic_ir import canonical_json
            receipt=payload['backend_receipt']
            expected=translate_statement(statement,receipt.get('strategy','auto')).to_data() if receipt.get('backend')=='lean4' else None
            if receipt.get('backend')=='lean4-std':
                from ..formal.lean_std import std_translation
                expected=std_translation(statement)
            if canonical_json(payload['translation'])!=canonical_json(expected):return False
        return verify_formal_receipt(statement,payload['backend_receipt'],project=project)
    except (ValueError,KeyError,TypeError,ArithmeticError):
        return False
