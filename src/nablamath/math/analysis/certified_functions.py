"""Rational enclosures of exp, log, sin and cos with explicit series bounds.

Inputs and output endpoints are exact rationals. The series remainders, not a
binary64 comparison or a difference of iterates, determine acceptance. Budget
exhaustion returns no certificate. These APIs do not accept arbitrary code.
"""

from fractions import Fraction

from ...core.semantic_ir import canonical_json, fingerprint
from .intervals import RationalInterval, exact


def _exp_series(value, terms):
    term, total = Fraction(1), Fraction(1)
    for index in range(1, terms+1):
        term = exact(term*value/index)
        total = exact(total+term)
    first_omitted = exact(abs(term*value/(terms+1)))
    ratio = exact(abs(value)/(terms+2))
    if ratio >= 1:
        raise ArithmeticError('Exponential tail ratio must be below one')
    remainder = exact(first_omitted/(1-ratio))
    return RationalInterval(total-remainder, total+remainder), {
        'partial_sum': str(total), 'remainder': str(remainder), 'tail_ratio': str(ratio),
    }


def _log_series(value, terms):
    # log(x) = 2 atanh(z), z=(x-1)/(x+1), |z|<1 for x>0.
    z = exact((value-1)/(value+1))
    square = exact(z*z)
    power = z
    total = Fraction(0)
    for index in range(terms):
        total = exact(total+2*power/(2*index+1))
        power = exact(power*square)
    remainder = exact(2*abs(power)/((2*terms+1)*(1-square)))
    return RationalInterval(total-remainder, total+remainder), {
        'partial_sum': str(total), 'remainder': str(remainder), 'atanh_argument': str(z),
    }


def _trig_series(kind, value, terms):
    # Taylor's theorem at zero: every derivative of sin/cos has magnitude <=1.
    # Include all powers through degree d and bound by |x|^(d+1)/(d+1)!.
    # Building the factorial recurrence explicitly avoids trusting sin/cos.
    degree = 2*terms if kind == 'cos' else 2*terms+1
    coefficient = Fraction(1)
    total = Fraction(0)
    for power in range(degree+1):
        if power:
            coefficient = exact(coefficient*value/power)
        if kind == 'cos' and power % 2 == 0:
            total = exact(total+(-1)**(power//2)*coefficient)
        elif kind == 'sin' and power % 2:
            total = exact(total+(-1)**((power-1)//2)*coefficient)
    remainder = exact(abs(coefficient*value/(degree+1)))
    raw = RationalInterval(total-remainder, total+remainder)
    enclosure = raw.intersection(RationalInterval(-1, 1))
    return enclosure, {'partial_sum': str(total), 'remainder': str(remainder),
                       'taylor_degree': degree}


def certified_function(kind, value, *, tolerance='1/1000000', max_terms=128):
    """Enclose a single exact argument, with width no greater than tolerance.

    The argument is bounded to [-8,8]; log accepts [1/8,8]. A finite precision
    budget is part of the contract and is not automatically enlarged on failure.
    """
    if kind not in ('exp', 'log', 'sin', 'cos'):
        raise ValueError('Supported functions are exp, log, sin and cos')
    value, tolerance = exact(value), exact(tolerance)
    if abs(value) > 8 or (kind == 'log' and not Fraction(1, 8) <= value <= 8):
        raise ValueError('Argument outside the certified function profile')
    if tolerance <= 0:
        raise ValueError('Positive enclosure-width tolerance required')
    if type(max_terms) is not int or not 1 <= max_terms <= 512:
        raise ValueError('Series budget must be in [1,512]')
    argument = value
    squarings = 0
    if kind == 'exp':
        while abs(argument) > Fraction(1, 2):
            argument = exact(argument/2)
            squarings += 1
    for terms in range(1, max_terms+1):
        if kind == 'exp':
            enclosure, witness = _exp_series(argument, terms)
            # exp is positive. This intersection is a mathematical range fact,
            # not a way to discard a failed or inconsistent computed interval.
            if enclosure.upper <= 0:
                raise ArithmeticError('Exponential enclosure is inconsistent')
            enclosure = RationalInterval(max(Fraction(0), enclosure.lower), enclosure.upper)
            for _ in range(squarings):
                enclosure = enclosure**2
            witness.update(reduced_argument=str(argument), squarings=squarings)
        elif kind == 'log':
            enclosure, witness = _log_series(value, terms)
        else:
            enclosure, witness = _trig_series(kind, value, terms)
        if enclosure.width <= tolerance:
            break
    else:
        raise ArithmeticError('Certified function exhausted the series budget')
    payload = {
        'profile': 'rational-transcendental-enclosure-v1',
        'request': {'kind': kind, 'value': str(value), 'tolerance': str(tolerance),
                    'max_terms': max_terms},
        'enclosure': enclosure.to_data(), 'terms': terms, 'witness': witness,
        'formal_proof': False,
        'scope': 'Exact rational Taylor enclosure on a bounded real argument; analytic remainder theorem is not Lean-checked',
    }
    return {**payload, 'certificate_id': fingerprint(payload)}


def verify_certified_function(certificate):
    try:
        if not isinstance(certificate, dict) or len(canonical_json(certificate)) > 100_000:
            return False
        expected = certified_function(**certificate['request'])
        return canonical_json(certificate) == canonical_json(expected)
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return False
