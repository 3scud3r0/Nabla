"""Certified adaptive quadrature for exact rational polynomials.

Remainders use exact Bernstein bounds on the required derivative. Unlike a
successive-grid error heuristic, the returned interval contains the true
integral under the displayed polynomial contract. It is an algebraic
certificate, not a Lean proof or validation of a physical integrand.
"""

from fractions import Fraction

from ...core.semantic_ir import canonical_json, fingerprint
from .intervals import (
    RationalInterval, bernstein_coefficients, checked_polynomial, exact,
)


_ORDERS = {'midpoint': 2, 'trapezoid': 2, 'simpson': 4}
_DENOMINATORS = {'midpoint': 24, 'trapezoid': 12, 'simpson': 2880}


def _piece(polynomial, derivative, interval, method):
    left, right, middle = interval.lower, interval.upper, interval.midpoint
    width = interval.width
    if method == 'midpoint':
        estimate = exact(width*exact(polynomial(middle)))
    elif method == 'trapezoid':
        estimate = exact(width*(exact(polynomial(left))+exact(polynomial(right)))/2)
    else:
        estimate = exact(width*(exact(polynomial(left))+4*exact(polynomial(middle))
                                +exact(polynomial(right)))/6)
    coefficients = bernstein_coefficients(derivative, interval)
    bound = max(abs(value) for value in coefficients)
    error = exact(bound*width**(_ORDERS[method]+1)/_DENOMINATORS[method])
    return {'interval': interval.to_data(), 'estimate': str(estimate),
            'derivative_bernstein': [str(v) for v in coefficients],
            'derivative_bound': str(bound), 'error_bound': str(error)}


def certified_polynomial_integral(coefficients, lower, upper, *, method='simpson',
                                  tolerance='1/1000000', max_pieces=256):
    """Integrate a bounded rational polynomial, subdividing the largest error.

    Exhausting the piece budget raises ArithmeticError and returns no accepted
    certificate. Reversed endpoints are supported and preserve the sign.
    """
    polynomial = checked_polynomial(coefficients)
    lower, upper, tolerance = exact(lower), exact(upper), exact(tolerance)
    if not isinstance(method, str) or method not in _ORDERS:
        raise ValueError('Quadrature method must be midpoint, trapezoid or simpson')
    if tolerance < 0:
        raise ValueError('Nonnegative error tolerance required')
    if type(max_pieces) is not int or not 1 <= max_pieces <= 1024:
        raise ValueError('Piece budget must be in [1,1024]')
    derivative = polynomial
    for _ in range(_ORDERS[method]):
        derivative = derivative.derivative()
    orientation = 1 if upper >= lower else -1
    domain = RationalInterval(min(lower, upper), max(lower, upper))
    pieces = [_piece(polynomial, derivative, domain, method)]
    total_error = exact(pieces[0]['error_bound'])
    while total_error > tolerance:
        if len(pieces) >= max_pieces:
            raise ArithmeticError('Certified quadrature exhausted the piece budget')
        index = max(range(len(pieces)), key=lambda i: (exact(pieces[i]['error_bound']), -i))
        old = pieces.pop(index)
        interval = RationalInterval.from_data(old['interval'])
        left, right = interval.bisect()
        children = [_piece(polynomial, derivative, part, method) for part in (left, right)]
        pieces[index:index] = children
        total_error = exact(total_error-exact(old['error_bound'])
                            +sum((exact(row['error_bound']) for row in children), Fraction(0)))
    estimate = exact(orientation*sum((exact(row['estimate']) for row in pieces), Fraction(0)))
    enclosure = RationalInterval(estimate-total_error, estimate+total_error)
    payload = {
        'profile': 'exact-polynomial-quadrature-v1',
        'request': {'coefficients': [str(v) for v in polynomial.coefficients],
                    'lower': str(lower), 'upper': str(upper), 'method': method,
                    'tolerance': str(tolerance), 'max_pieces': max_pieces},
        'estimate': str(estimate), 'error_bound': str(total_error),
        'enclosure': enclosure.to_data(), 'pieces': pieces,
        'derivative_order': _ORDERS[method], 'orientation': orientation,
        'formal_proof': False,
        'scope': 'Exact polynomial model with derivative remainder bound; no empirical validation',
    }
    return {**payload, 'certificate_id': fingerprint(payload)}


def verify_polynomial_integral(certificate):
    try:
        if not isinstance(certificate, dict) or len(canonical_json(certificate)) > 4_000_000:
            return False
        expected = certified_polynomial_integral(**certificate['request'])
        return canonical_json(certificate) == canonical_json(expected)
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return False
