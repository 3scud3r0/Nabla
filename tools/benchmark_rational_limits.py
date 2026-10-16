"""Compare sided rational limits with SymPy on a fixed, public analytic corpus.

This measures conformance within a narrow fragment, not general mathematical
capability, learned generalization, or difficulty. Never tunes on the results.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

from nablamath.core.semantic_ir import fingerprint
from nablamath.math.calculus.limits import rational_sided_limit, verify_rational_limit


def corpus():
    """Freeze all requests before evaluating either implementation."""
    cases = []
    for center in (-2, Fraction(1, 3), 3):
        for coefficient in (-3, 2):
            for top_power in range(4):
                for bottom_power in range(4):
                    source = f'{coefficient}*(x-({center}))**{top_power}/(x-({center}))**{bottom_power}'
                    for direction in ('left', 'right'):
                        cases.append({'source': source, 'point': str(center), 'direction': direction})
    for source in ('0/x', '1/x', '-1/x**2', '(3*x**2+1)/(2*x**2-5)',
                   '(x+1)/(x**2+1)', '1/(1/x)', 'x**3', '-x**4'):
        for point in ('+infinity', '-infinity'):
            cases.append({'source': source, 'point': point, 'direction': 'both'})
    return tuple(cases)


def oracle(request, sympy):
    # Inputs are fixed expressions constructed above, never user-supplied text.
    x = sympy.Symbol('x')
    expression = sympy.sympify(request['source'], locals={'x': x})
    point = request['point']
    target = {'+infinity': sympy.oo, '-infinity': -sympy.oo}.get(point)
    if target is None:
        target = sympy.Rational(point)
    direction = '-' if request['direction'] == 'left' else '+'
    value = sympy.limit(expression, x, target, dir=direction)
    if value == sympy.oo:
        return {'status': 'positive_infinity', 'value': None}
    if value == -sympy.oo:
        return {'status': 'negative_infinity', 'value': None}
    if not value.is_Rational:
        raise ValueError('Oracle returned an outcome outside this corpus contract')
    return {'status': 'finite', 'value': str(value)}


def benchmark():
    import sympy

    cases = corpus()
    protocol = {
        'version': 'rational-limits-conformance-v1',
        'cases': list(cases),
        'oracle': 'SymPy exact limits',
        'selection': 'Fixed public Cartesian corpus, no training or tuning',
        'acceptance': 'All exact outcomes must agree; all receipts must replay',
        'scope': 'Rational functions in x, rational finite points and signed infinity',
    }
    protocol_id = fingerprint(protocol)
    outcomes = []
    started = time.perf_counter()
    for request in cases:
        row = {'request': request, 'case_id': fingerprint(request)}
        try:
            receipt = rational_sided_limit(**request)
            row['actual'] = receipt['result']
            row['receipt_verified'] = verify_rational_limit(receipt)
            row['expected'] = oracle(request, sympy)
            row['status'] = 'passed' if row['actual'] == row['expected'] else 'failed'
        except Exception as error:
            # Continue independent cases, preserving the error instead of
            # treating an unsupported result as a passing or difficult case.
            row.update(status='error', error_type=type(error).__name__, error=str(error))
        outcomes.append(row)
    root = Path(__file__).resolve().parents[1]
    paths = [Path(__file__).resolve(),
             root/'src/nablamath/math/calculus/limits.py',
             root/'src/nablamath/math/calculus/rational_functions.py',
             root/'src/nablamath/math/polynomials/univariate.py']
    report = {
        'protocol': protocol, 'protocol_id': protocol_id,
        'runtime': {'python': platform.python_version(), 'sympy': sympy.__version__},
        'sources': {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in paths},
        'outcomes': outcomes,
        'counts': {status: sum(row['status'] == status for row in outcomes)
                   for status in ('passed', 'failed', 'error')},
        'seconds': time.perf_counter()-started,
        'external_review_performed': False,
        'private_holdout': False,
        'formal_proof': False,
    }
    return {**report, 'report_id': fingerprint(report)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New JSON file; never overwritten')
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('Use a new output destination to preserve previous evidence')
    report = benchmark()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'counts': report['counts'], 'protocol_id': report['protocol_id'],
                      'report_id': report['report_id']}, sort_keys=True))
    return 0 if report['counts']['passed'] == len(report['outcomes']) else 1


if __name__ == '__main__':
    sys.exit(main())
