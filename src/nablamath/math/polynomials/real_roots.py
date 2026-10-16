"""Exact rational Sturm isolation with multiplicity and replayable certificates.

The algorithm isolates every distinct real root of a rational polynomial in
pairwise-disjoint rational brackets. It does not approximate complex roots or
claim a Lean proof: an independent replay reconstructs Euclidean remainders and
uses Sturm's theorem. Resource limits are part of the public contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import ceil
from itertools import islice

from ...core.semantic_contracts import canonical_payload
from ...core.semantic_ir import fingerprint
from .univariate import Polynomial

_ONE = Polynomial((1,))


def _checked(polynomial, *, allow_zero=True):
    if not isinstance(polynomial, Polynomial) or polynomial.degree > 32:
        raise ValueError('Rational polynomial degree must be at most 32')
    if not allow_zero and polynomial.is_zero:
        raise ValueError('Zero polynomial has no finite root isolation')
    if any(max(abs(v.numerator).bit_length(), v.denominator.bit_length()) > 8192
           for v in polynomial.coefficients):
        raise ValueError('Polynomial arithmetic exceeded 8192-bit budget')
    return polynomial


def _input(polynomial):
    _checked(polynomial, allow_zero=False)
    if any(max(abs(v.numerator).bit_length(), v.denominator.bit_length()) > 512
           for v in polynomial.coefficients):
        raise ValueError('Input coefficients exceed 512-bit budget')
    return polynomial


def _scale(polynomial, value):
    return _checked(Polynomial(tuple(value * c for c in polynomial.coefficients)))


def _divide(left, right):
    _checked(left)
    _checked(right, allow_zero=False)
    coefficients = list(left.coefficients)
    quotient = [Fraction()] * max(1, left.degree - right.degree + 1)
    while len(coefficients) - 1 >= right.degree and any(coefficients):
        degree = len(coefficients) - 1 - right.degree
        factor = coefficients[-1] / right.leading
        quotient[degree] += factor
        for index, coefficient in enumerate(right.coefficients):
            coefficients[index + degree] -= factor * coefficient
        while len(coefficients) > 1 and not coefficients[-1]:
            coefficients.pop()
        _checked(Polynomial(tuple(coefficients)))
    return _checked(Polynomial(tuple(quotient))), _checked(Polynomial(tuple(coefficients)))


def _exact_divide(left, right):
    quotient, remainder = _divide(left, right)
    if not remainder.is_zero:
        raise ArithmeticError('Expected exact polynomial division')
    return quotient


def _gcd(left, right):
    while not right.is_zero:
        _, remainder = _divide(left, right)
        left, right = right, remainder
    return _scale(left, 1 / left.leading) if not left.is_zero else left


def square_free_decomposition(polynomial):
    """Return leading coefficient and monic pairwise-coprime multiplicity factors.

    Each pair is (factor, multiplicity). The product of factor**multiplicity
    times the returned coefficient reconstructs the input exactly over Q.
    """
    _input(polynomial)
    if polynomial.degree == 0:
        return polynomial.leading, ()
    monic = _scale(polynomial, 1 / polynomial.leading)
    repeated = _gcd(monic, monic.derivative())
    current = _exact_divide(monic, repeated)
    result = []
    multiplicity = 1
    while current.degree > 0:
        common = _gcd(current, repeated)
        factor = _exact_divide(current, common)
        if factor.degree > 0:
            result.append((factor, multiplicity))
        current = common
        repeated = _exact_divide(repeated, common)
        multiplicity += 1
        if multiplicity > polynomial.degree + 1:
            raise ArithmeticError('Square-free decomposition did not terminate')
    return polynomial.leading, tuple(result)


def _square_free_part(polynomial):
    monic = _scale(polynomial, 1 / polynomial.leading)
    return _exact_divide(monic, _gcd(monic, monic.derivative()))


def sturm_sequence(polynomial):
    """Canonical Sturm sequence for the square-free monic part of the input."""
    _input(polynomial)
    first = _square_free_part(polynomial)
    if first.degree == 0:
        return (first,)
    result = [first, first.derivative()]
    while not result[-1].is_zero:
        _, remainder = _divide(result[-2], result[-1])
        if remainder.is_zero:
            break
        # Positive scaling controls coefficient growth without changing signs.
        next_term = _scale(remainder, -1 / abs(remainder.leading))
        result.append(next_term)
    return tuple(result)


def _rational(value):
    if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
        raise ValueError('Endpoints must be exact rationals')
    value = Fraction(value)
    if max(abs(value.numerator).bit_length(), value.denominator.bit_length()) > 2048:
        raise ValueError('Rational endpoint exceeded 2048-bit budget')
    return value


def _evaluate(polynomial, value):
    result = Fraction()
    for coefficient in reversed(polynomial.coefficients):
        result = result * value + coefficient
        if max(abs(result.numerator).bit_length(), result.denominator.bit_length()) > 65536:
            raise ValueError('Sturm evaluation exceeded bit budget')
    return result


def sign_variations(sequence, value):
    """Count sign changes after deleting exact zeros at a rational point."""
    value = _rational(value)
    sequence=tuple(islice(iter(sequence),34))
    if not 1<=len(sequence)<=33:
        raise ValueError("Sturm sequence length budget exceeded")
    signs = []
    for polynomial in sequence:
        _checked(polynomial)
        result = _evaluate(polynomial, value)
        if result:
            signs.append(1 if result > 0 else -1)
    return sum(left != right for left, right in zip(signs, signs[1:]))


def count_real_roots(polynomial, lower, upper):
    """Count distinct real roots strictly inside nonroot rational endpoints.

    Endpoints that are roots are rejected instead of silently choosing a
    half-open interval convention. Repeated roots count once.
    """
    _input(polynomial)
    lower, upper = _rational(lower), _rational(upper)
    if lower >= upper:
        raise ValueError('Root-count interval must have increasing endpoints')
    if not _evaluate(polynomial, lower) or not _evaluate(polynomial, upper):
        raise ValueError('Root-count endpoints must not be roots')
    sequence = sturm_sequence(polynomial)
    return sign_variations(sequence, lower) - sign_variations(sequence, upper)


def cauchy_bound(polynomial):
    """Strict integer bound B such that every complex root has absolute value < B."""
    _input(polynomial)
    if polynomial.degree == 0:
        return 1
    maximum = max(abs(value / polynomial.leading) for value in polynomial.coefficients[:-1])
    return 2 + ceil(maximum)


@dataclass(frozen=True)
class RootInterval:
    lower: Fraction
    upper: Fraction
    multiplicity: int
    lower_variations: int
    upper_variations: int

    @property
    def width(self):
        return self.upper - self.lower

    @property
    def midpoint(self):
        return (self.lower + self.upper) / 2

    def to_data(self):
        return {'lower': str(self.lower), 'upper': str(self.upper),
                'multiplicity': self.multiplicity,
                'lower_variations': self.lower_variations,
                'upper_variations': self.upper_variations}


def _poly_data(polynomial):
    return [str(c) for c in polynomial.coefficients]


def _decode_fraction(text, *, bits=8192):
    if not isinstance(text, str) or len(text) > 6000:
        raise ValueError('Invalid certificate rational')
    value = Fraction(text)
    if str(value) != text or max(abs(value.numerator).bit_length(), value.denominator.bit_length()) > bits:
        raise ValueError('Noncanonical or oversized certificate rational')
    return value


def _decode_poly(data, *, input_polynomial=False):
    if not isinstance(data, list) or not 1 <= len(data) <= 33:
        raise ValueError('Invalid certificate polynomial')
    values = tuple(_decode_fraction(c, bits=512 if input_polynomial else 8192) for c in data)
    result = Polynomial(values)
    if result.coefficients != values:
        raise ValueError('Noncanonical trailing zero coefficients')
    return _input(result) if input_polynomial else _checked(result)


@dataclass(frozen=True)
class RootIsolation:
    polynomial: Polynomial
    intervals: tuple[RootInterval, ...]
    precision_bits: int
    visited_nodes: int

    def to_data(self):
        body = {'schema_version': 1, 'polynomial': _poly_data(self.polynomial),
                'precision_bits': self.precision_bits, 'visited_nodes': self.visited_nodes,
                'bound': cauchy_bound(self.polynomial),
                'sturm_sequence': [_poly_data(p) for p in sturm_sequence(self.polynomial)],
                'intervals': [interval.to_data() for interval in self.intervals],
                'distinct_real_roots': len(self.intervals),
                'real_roots_with_multiplicity': sum(i.multiplicity for i in self.intervals),
                'formal_proof': False,
                'scope': 'Exact rational Sturm isolation with algorithmic replay; not a Lean kernel certificate'}
        return {**body, 'certificate_id': fingerprint(body)}

    @classmethod
    def from_data(cls, data):
        """Decode only after full independent certificate checking."""
        if not verify_root_isolation(data):
            raise ValueError('Invalid root isolation certificate')
        return cls(_decode_poly(data['polynomial'], input_polynomial=True),
                   tuple(RootInterval(_decode_fraction(row['lower'], bits=2048),
                                      _decode_fraction(row['upper'], bits=2048), row['multiplicity'],
                                      row['lower_variations'], row['upper_variations']) for row in data['intervals']),
                   data['precision_bits'], data['visited_nodes'])


def isolate_real_roots(polynomial, *, precision_bits=32, max_nodes=10000):
    """Isolate all distinct real roots to brackets of width <= 2**(-bits).

    A deterministic nonroot split avoids special cases at rational roots.
    Exhausting the explicit work budget raises and returns no partial certificate.
    """
    _input(polynomial)
    if type(precision_bits) is not int or not 0 <= precision_bits <= 128:
        raise ValueError('Root precision must be in [0,128] bits')
    if type(max_nodes) is not int or not 1 <= max_nodes <= 100000:
        raise ValueError('Root isolation node budget must be in [1,100000]')
    sequence = sturm_sequence(polynomial)
    bound = cauchy_bound(polynomial)
    left, right = Fraction(-bound), Fraction(bound)
    pending = [(left, right, sign_variations(sequence, left), sign_variations(sequence, right))]
    factors = square_free_decomposition(polynomial)[1]
    target_width = Fraction(1, 2 ** precision_bits)
    intervals = []
    visited = 0
    while pending:
        if visited >= max_nodes:
            raise ValueError('Root isolation node budget exhausted')
        lower, upper, vl, vu = pending.pop()
        visited += 1
        count = vl - vu
        if count == 0:
            continue
        if count == 1 and upper - lower <= target_width:
            multiplicities = [multiplicity for factor, multiplicity in factors
                              if count_real_roots(factor, lower, upper) == 1]
            if len(multiplicities) != 1:
                raise ArithmeticError('Isolated root multiplicity could not be assigned')
            intervals.append(RootInterval(lower, upper, multiplicities[0], vl, vu))
            continue
        # A nonzero degree-d polynomial cannot vanish at d+1 distinct candidates.
        for denominator in range(2, polynomial.degree + 3):
            middle = _rational(lower + (upper - lower) / denominator)
            if _evaluate(sequence[0], middle):
                break
        else:
            raise ArithmeticError('No nonroot split found')
        vm = sign_variations(sequence, middle)
        pending.append((middle, upper, vm, vu))
        pending.append((lower, middle, vl, vm))
    intervals.sort(key=lambda interval: interval.lower)
    result = RootIsolation(polynomial, tuple(intervals), precision_bits, visited)
    if not verify_root_isolation(result.to_data()):
        raise ArithmeticError('Generated root certificate failed independent replay')
    return result


def verify_root_isolation(data):
    """Check hashes, Sturm remainders, root counts, coverage, widths and multiplicity.

    This verifier accepts any valid disjoint brackets, rather than merely rerunning
    the isolator and demanding the same bisection history. visited_nodes is bounded
    telemetry, not a proof of the original machine's computational work.
    """
    try:
        canonical_payload(data)
        fields = {'schema_version','polynomial','precision_bits','visited_nodes','bound',
                  'sturm_sequence','intervals','distinct_real_roots','real_roots_with_multiplicity',
                  'formal_proof','scope','certificate_id'}
        if type(data) is not dict or set(data) != fields:
            return False
        if type(data['schema_version']) is not int or data['schema_version'] != 1 or data['formal_proof'] is not False:
            return False
        if data['scope'] != 'Exact rational Sturm isolation with algorithmic replay; not a Lean kernel certificate':
            return False
        if data['certificate_id'] != fingerprint({k:v for k,v in data.items() if k != 'certificate_id'}):
            return False
        polynomial = _decode_poly(data['polynomial'], input_polynomial=True)
        bits = data['precision_bits']
        if type(bits) is not int or not 0 <= bits <= 128:
            return False
        if type(data['visited_nodes']) is not int or not 1 <= data['visited_nodes'] <= 100000:
            return False
        sequence = sturm_sequence(polynomial)
        if data['sturm_sequence'] != [_poly_data(p) for p in sequence]:
            return False
        bound = cauchy_bound(polynomial)
        if type(data['bound']) is not int or data['bound'] != bound:
            return False
        expected_count = sign_variations(sequence, -bound) - sign_variations(sequence, bound)
        if not isinstance(data['intervals'], list) or len(data['intervals']) > polynomial.degree + 1:
            return False
        factors = square_free_decomposition(polynomial)[1]
        previous = Fraction(-bound)
        multiplicities = []
        for row in data['intervals']:
            if type(row) is not dict or set(row) != {'lower','upper','multiplicity','lower_variations','upper_variations'}:
                return False
            lower = _decode_fraction(row['lower'], bits=2048)
            upper = _decode_fraction(row['upper'], bits=2048)
            if not -bound <= previous <= lower < upper <= bound or upper-lower > Fraction(1,2**bits):
                return False
            if not _evaluate(polynomial, lower) or not _evaluate(polynomial, upper):
                return False
            vl, vu = sign_variations(sequence, lower), sign_variations(sequence, upper)
            if any(type(row[k]) is not int for k in ('multiplicity','lower_variations','upper_variations')):
                return False
            if (row['lower_variations'], row['upper_variations']) != (vl,vu) or vl-vu != 1:
                return False
            matches = [m for factor,m in factors if count_real_roots(factor,lower,upper) == 1]
            if matches != [row['multiplicity']]:
                return False
            multiplicities.append(row['multiplicity'])
            previous = upper
        return (type(data['distinct_real_roots']) is int and data['distinct_real_roots'] == expected_count == len(multiplicities)
                and type(data['real_roots_with_multiplicity']) is int
                and data['real_roots_with_multiplicity'] == sum(multiplicities))
    except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError, RecursionError):
        return False


__all__ = ['RootInterval','RootIsolation','square_free_decomposition','sturm_sequence',
           'sign_variations','count_real_roots','cauchy_bound','isolate_real_roots','verify_root_isolation']
