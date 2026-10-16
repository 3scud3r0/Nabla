"""Exact sided limits of bounded univariate rational expressions.

The witness is algebraic evidence over Q, not a proof checked by Lean.  Original
domain guards remain separate from the reduced function, including removable
holes.  No numerical probing or symbolic backend is used to choose a sign.
"""

from fractions import Fraction

from ...core.obligations import domain_obligations
from ...core.semantic_ir import canonical_json, fingerprint, rational
from ...expression import parse_expr, render
from ..polynomials.univariate import Polynomial
from .rational_functions import rational_form


PROFILE = "rational-sided-limit-v1"
_INFINITIES = ("+infinity", "-infinity")


def _local_factor(polynomial, point):
    """Return the exact valuation and first nonzero Taylor coefficient."""
    if polynomial.is_zero:
        return None, Fraction(0)
    current = polynomial
    divisor = Polynomial((-point, 1))
    order = 0
    while current(point) == 0:
        current, remainder = current.divmod(divisor)
        if not remainder.is_zero:
            raise ArithmeticError("Exact root division failed")
        order += 1
    return order, current(point)


def _finite(value):
    return {"status": "finite", "value": str(value)}


def _infinite(sign):
    return {"status": "positive_infinity" if sign > 0 else "negative_infinity",
            "value": None}


def _domain(source, point):
    guards = []
    defined = point is not None
    for obligation in domain_obligations(parse_expr(source)):
        guard = rational_form(render(obligation.expression))
        # This also excludes expressions such as (x-x)**0: reducing the whole
        # expression to 1 must not turn an everywhere-undefined input into 1.
        if guard.numerator.is_zero:
            raise ValueError("Expressão com domínio vazio")
        if point is not None:
            defined = defined and obligation.check({"x": point}) == "satisfied"
        guards.append(obligation.to_data())
    return guards, defined if point is not None else None


def rational_sided_limit(source, point, *, direction="both"):
    """Compute a finite-point or signed-infinity limit with a replayable witness.

    ``point`` is an exact rational or ``+infinity``/``-infinity``.  Finite
    points support ``left``, ``right`` and ``both``.  At infinity only ``both``
    is accepted, since the sign of the infinity already selects the end.
    Distinct left/right infinities produce ``does_not_exist``.  A common
    signed infinity is explicitly distinguished from a finite real limit.
    """
    if not isinstance(source, str) or not source or len(source) > 4096:
        raise ValueError("Expressão racional requer 1–4096 caracteres")
    if direction not in ("both", "left", "right"):
        raise ValueError("Direção deve ser both, left ou right")
    at_infinity = isinstance(point, str) and point in _INFINITIES
    if at_infinity and direction != "both":
        raise ValueError("Ponto infinito já especifica a direção")
    center = None if at_infinity else rational(point)
    if center is not None:
        # Receipts store a canonical string.  Fraction inputs can otherwise
        # pass the bit budget but exceed the string budget during replay.
        rational(str(center))
    function = rational_form(source)
    guards, defined = _domain(source, center)
    top, bottom = function.numerator, function.denominator
    witness = {"normal_form": function.to_data(), "domain_guards": guards}

    if at_infinity:
        degree_difference = top.degree - bottom.degree
        ratio = top.leading / bottom.leading
        witness.update(degree_difference=degree_difference,
                       leading_coefficient_ratio=str(ratio))
        if top.is_zero or degree_difference < 0:
            result = _finite(0)
        elif degree_difference == 0:
            result = _finite(ratio)
        else:
            sign = 1 if ratio > 0 else -1
            if point == "-infinity" and degree_difference % 2:
                sign = -sign
            result = _infinite(sign)
        left = right = None
    else:
        top_order, top_coefficient = _local_factor(top, center)
        bottom_order, bottom_coefficient = _local_factor(bottom, center)
        witness.update(numerator_order=top_order, denominator_order=bottom_order,
                       numerator_coefficient=str(top_coefficient),
                       denominator_coefficient=str(bottom_coefficient))
        if top.is_zero or top_order > bottom_order:
            left = right = _finite(0)
        elif top_order == bottom_order:
            left = right = _finite(top_coefficient / bottom_coefficient)
        else:
            pole_order = bottom_order - top_order
            sign = 1 if top_coefficient / bottom_coefficient > 0 else -1
            right = _infinite(sign)
            left = _infinite(-sign if pole_order % 2 else sign)
        if direction == "left":
            result = left
        elif direction == "right":
            result = right
        elif left == right:
            result = left
        else:
            result = {"status": "does_not_exist", "value": None}

    payload = {
        "schema_version": 1,
        "profile": PROFILE,
        "request": {"source": source, "point": point if at_infinity else str(center),
                    "direction": direction},
        "result": dict(result),
        "left": None if left is None else dict(left),
        "right": None if right is None else dict(right),
        "defined_at_point": defined,
        "witness": witness,
        "formal_proof": False,
        "scope": "Exact rational functions in x; finite rational points and signed infinity; no empirical validation",
    }
    return {**payload, "limit_id": fingerprint(payload)}


def verify_rational_limit(receipt):
    """Recompute mathematics and domain guards, rather than trusting a hash.

    Invalid receipts raise ValueError, consistently with notebook replay.
    A rehashed change to an answer, guard, request, or witness is still rejected.
    """
    if not isinstance(receipt, dict):
        raise ValueError("Recibo de limite deve ser objeto")
    try:
        if len(canonical_json(receipt)) > 100_000:
            raise ValueError("Recibo de limite excede o limite")
        request = receipt["request"]
        if not isinstance(request, dict) or set(request) != {"source", "point", "direction"}:
            raise ValueError("Contrato de pedido de limite inválido")
        expected = rational_sided_limit(request["source"], request["point"],
                                       direction=request["direction"])
        # Canonical bytes distinguish booleans from integers, unlike dict ==.
        if canonical_json(receipt) != canonical_json(expected):
            raise ValueError("Recibo de limite diverge da reexecução")
    except (KeyError, TypeError, ArithmeticError, RecursionError) as error:
        raise ValueError("Recibo de limite inválido") from error
    return True
