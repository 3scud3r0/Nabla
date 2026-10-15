"""Finite calibration evidence, with an explicit refusal to infer global readiness.

The random protocol is fixed before measurements. No failing case is discarded
or used to fit a replacement predictor. This measures exact rational arithmetic
and a bounded integration fragment; it is not a held-out learning benchmark.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from pathlib import Path
import random
import shutil

from ..core.semantic_ir import fingerprint
from ..core.semantic_contracts import canonical_payload, load_json, require_fields
from ..expression import evaluate, parse_expr
from ..math.polynomials.univariate import Polynomial
from ..math.calculus.risch import LinearFactor, integrate_rational

MAX_CASES = 100000
SCHEMA_VERSION = 1
SCOPE = 'finite exact arithmetic and integration checks; not scientific, causal, autonomy or full-roadmap certification'


def _count(value, maximum=MAX_CASES):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError('Positive bounded integer case count required')
    return value


def _seed(value):
    if type(value) is not int or not 0 <= value < 2**32:
        raise ValueError('Unsigned 32-bit seed required')
    return value


def _rational(rng):
    return Fraction(rng.randint(-20, 20), rng.randint(1, 12))


def _expression(rng, depth):
    """Construct syntactically safe trees; divisors are nonzero constants."""
    if depth == 0:
        return rng.choice(('x', 'y', str(rng.randint(-20, 20))))
    op = rng.choice(('+', '-', '*', '/'))
    left = _expression(rng, depth - 1)
    if op == '/':
        right = str(rng.choice((-9, -5, -1, 1, 3, 7)))
    else:
        right = _expression(rng, depth - 1)
    return f'({left}{op}{right})'


def differential_arithmetic(*, cases=10000, seed=951017):
    """Compare independently parsed exact results with SymPy, retaining failures.

    SymPy parses only strings manufactured by the closed generator here, never
    caller-supplied expressions. Its agreement is evidence for this fragment,
    not evidence of general equivalence between the two engines.
    """
    _count(cases)
    _seed(seed)
    protocol = {'cases': cases, 'seed': seed, 'depth': 3,
                'generator': 'rational-binary-nonzero-constant-divisors-v1'}
    try:
        import sympy
    except ImportError:
        return {'status': 'unavailable', 'protocol': protocol, 'executed': 0,
                'reason': 'Optional SymPy oracle unavailable', 'passed': False}
    rng = random.Random(seed)
    x, y = sympy.symbols('x y')
    disagreements, corpus_chain = [], '0' * 64
    for index in range(cases):
        source = _expression(rng, 3)
        values = {'x': _rational(rng), 'y': _rational(rng)}
        case = {'index': index, 'source': source,
                'values': {k: str(v) for k, v in values.items()}}
        corpus_chain = fingerprint({'parent': corpus_chain, 'case': case})
        ours = evaluate(parse_expr(source), values)
        theirs = sympy.sympify(source, locals={'x': x, 'y': y}, rational=True).subs(
            {x: sympy.Rational(str(values['x'])), y: sympy.Rational(str(values['y']))})
        exact = Fraction(int(theirs.p), int(theirs.q))
        if ours != exact:
            disagreements.append({**case, 'nabla': str(ours), 'oracle': str(exact)})
    return {'status': 'passed' if not disagreements else 'failed', 'protocol': protocol,
            'oracle': 'SymPy', 'oracle_version': sympy.__version__, 'executed': cases,
            'corpus_chain': corpus_chain, 'disagreements': disagreements,
            'passed': not disagreements, 'fit_on_cases': False}


def integration_metamorphisms(*, cases=512, seed=951017):
    """Manufacture pole families; independently check F' = f and exclusions.

    Besides the certificate's own verifier, reconstruct its derivative at exact
    rational points and compare with the original input, and exercise a scaled
    representation of the same integrand. These are finite identities, not an
    exhaustive test of all denominators or transcendental functions.
    """
    _count(cases, maximum=10000)
    _seed(seed)
    rng, failures = random.Random(seed), []
    chain = '0' * 64
    for index in range(cases):
        root = _rational(rng)
        factor = LinearFactor(root, rng.randint(1, 4))
        denominator = factor.polynomial
        numerator = Polynomial(tuple(_rational(rng) for _ in range(rng.randint(1, 6))))
        result = integrate_rational(numerator, denominator, (factor,))
        scale = Fraction(rng.randint(1, 9), rng.randint(1, 9))
        scaled = integrate_rational(
            Polynomial(tuple(c * scale for c in numerator.coefficients)),
            Polynomial(tuple(c * scale for c in denominator.coefficients)), (factor,))
        samples = []
        for offset in (Fraction(-3, 2), Fraction(1, 3), Fraction(7, 4)):
            point = root + offset
            derivative = result.polynomial_part.derivative()(point)
            scaled_derivative = scaled.polynomial_part.derivative()(point)
            for term in result.terms:
                n, d = term.derivative_pair()
                derivative += n(point) / d(point)
            for term in scaled.terms:
                n, d = term.derivative_pair()
                scaled_derivative += n(point) / d(point)
            expected = numerator(point) / denominator(point)
            samples.append(derivative == expected == scaled_derivative)
        ok = (result.verify() and scaled.verify() and all(samples)
              and result.excluded_roots == scaled.excluded_roots == (root,))
        case = {'index': index, 'root': str(root), 'multiplicity': factor.multiplicity,
                'numerator': [str(c) for c in numerator.coefficients], 'scale': str(scale)}
        chain = fingerprint({'parent': chain, 'case': case})
        if not ok:
            failures.append(case)
    return {'status': 'passed' if not failures else 'failed', 'cases': cases,
            'seed': seed, 'executed': cases, 'corpus_chain': chain,
            'failures': failures, 'passed': not failures,
            'scope': 'exact rational linear-factor fragment and three off-pole samples per case'}


def roadmap_readiness(matrix_path):
    """Conservative readout: never promote a requirement from its test outcome."""
    path = Path(matrix_path)
    if path.stat().st_size > 2_000_000:
        raise ValueError('Oversized matrix')
    raw = path.read_bytes()
    data = json.loads(raw)
    rows = data.get('requirements')
    if not isinstance(rows, list) or len(rows) != 213:
        raise ValueError('Expected exactly 213 requirements')
    if any(not isinstance(r, dict) or type(r.get('id')) is not int for r in rows):
        raise ValueError('Invalid requirement identity')
    if {r['id'] for r in rows} != set(range(1, 214)):
        raise ValueError('Missing or duplicate requirement IDs')
    counts = {status: 0 for status in ('planned', 'partial', 'validated')}
    unresolved = []
    for row in rows:
        status = row.get('status')
        if status not in counts:
            raise ValueError('Unknown requirement status')
        counts[status] += 1
        if status != 'validated':
            unresolved.append(row['id'])
        elif not all(row.get(key) for key in ('implementation', 'tests', 'evidence', 'reviewer', 'release')):
            raise ValueError('Validated row lacks declared acceptance evidence')
    return {'matrix_sha256': hashlib.sha256(raw).hexdigest(), 'counts': counts,
            'unresolved_ids': unresolved,
            'all_requirements_declared_validated': not unresolved,
            'independent_evidence_authenticated': False,
            'full_readiness_established': False}


def laboratory_readout(directory):
    """Read a prior fixed run without hiding failed jobs or learned baselines."""
    root = Path(directory)
    result = {'available': False, 'all_jobs_passed': False, 'learned_results': {},
              'scientific_generalization_established': False}
    summary = root / 'summary.json'
    if not summary.is_file():
        return result
    if summary.stat().st_size > 1_000_000:
        raise ValueError('Oversized laboratory summary')
    data = load_json(summary.read_text())
    result.update(available=True, all_jobs_passed=data.get('all_jobs_passed') is True,
                  selected_phase_profiles_passed=data.get('selected_phase_profiles_passed'),
                  jobs=data.get('jobs', []), summary_sha256=hashlib.sha256(summary.read_bytes()).hexdigest())
    workload = root / 'workload/summary.json'
    if workload.is_file():
        if workload.stat().st_size > 1_000_000:
            raise ValueError('Oversized workload summary')
        work = load_json(workload.read_text())
        result['learned_results'] = work.get('evaluations', {})
    return result


def calibrate(*, matrix_path, laboratory_directory, cases=10000, integration_cases=512, seed=951017):
    """Execute fixed finite checks and record prerequisite gaps as gaps."""
    protocol = {'schema_version': SCHEMA_VERSION, 'cases': _count(cases),
                'integration_cases': _count(integration_cases, 10000), 'seed': _seed(seed),
                'stopping_rule': 'one fixed run; retain every failure; no score-selected retries'}
    checks = {'differential': differential_arithmetic(cases=cases, seed=seed),
              'integration': integration_metamorphisms(cases=integration_cases, seed=seed)}
    report = {'schema_version': SCHEMA_VERSION, 'protocol': protocol,
              'protocol_id': fingerprint(protocol), 'checks': checks,
              'roadmap': roadmap_readiness(matrix_path),
              'laboratory': laboratory_readout(laboratory_directory),
              'tools_present': {name: shutil.which(name) is not None for name in ('lean', 'lake', 'nvidia-smi')},
              'finite_checks_passed': all(item['passed'] for item in checks.values()),
              'fully_calibrated_and_ready': False, 'scope': SCOPE}
    return {**report, 'report_id': fingerprint(report)}


def verify_report_structure(report):
    """Check local record integrity, not truth of claimed external measurements."""
    try:
        require_fields(report, {'schema_version', 'protocol', 'protocol_id', 'checks', 'roadmap',
            'laboratory', 'tools_present', 'finite_checks_passed', 'fully_calibrated_and_ready', 'scope', 'report_id'})
        if (type(report['schema_version']) is not int or report['schema_version'] != SCHEMA_VERSION
                or report['scope'] != SCOPE or report['fully_calibrated_and_ready'] is not False):
            return False
        protocol = report['protocol']
        require_fields(protocol, {'schema_version', 'cases', 'integration_cases', 'seed', 'stopping_rule'})
        _count(protocol['cases'])
        _count(protocol['integration_cases'], 10000)
        _seed(protocol['seed'])
        if protocol['schema_version'] != SCHEMA_VERSION or report['protocol_id'] != fingerprint(protocol):
            return False
        if set(report['checks']) != {'differential', 'integration'}:
            return False
        for name, check in report['checks'].items():
            if type(check.get('passed')) is not bool or check.get('status') not in {'passed', 'failed', 'unavailable'}:
                return False
            if check['passed'] != (check['status'] == 'passed'):
                return False
            expected = protocol['cases'] if name == 'differential' else protocol['integration_cases']
            if type(check.get('executed')) is not int:
                return False
            if check['executed'] != (0 if check['status'] == 'unavailable' else expected):
                return False
        if report['finite_checks_passed'] is not all(c['passed'] is True for c in report['checks'].values()):
            return False
        return report['report_id'] == fingerprint({k: v for k, v in report.items() if k != 'report_id'})
    except (ValueError, TypeError, KeyError, AttributeError):
        return False
