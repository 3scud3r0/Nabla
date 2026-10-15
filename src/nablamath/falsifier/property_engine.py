"""Bounded deterministic property suites retaining every refutation and null result."""
from ..core.semantic_ir import fingerprint
from .search import search_equivalence


def check_properties(properties, *, radius=3, budget=1000):
    properties = tuple(properties)
    if not 1 <= len(properties) <= 64:
        raise ValueError('One to 64 properties required')
    names = set()
    attempts = []
    for item in properties:
        if not isinstance(item, dict) or set(item) != {'name', 'left', 'right'}:
            raise ValueError('Named expression pair required')
        name = item['name']
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError('Unique nonempty names required')
        names.add(name)
        result = search_equivalence(item['left'], item['right'], radius=radius, budget=budget)
        attempts.append({**item, 'result': result.to_data()})
    payload = {'schema_version': 1, 'radius': radius, 'budget_per_property': budget,
               'attempts': attempts, 'formal_proof': False,
               'refuted': [r['name'] for r in attempts if r['result']['status'] in {'counterexample', 'domain_counterexample'}]}
    return {**payload, 'suite_id': fingerprint(payload)}


def replay_properties(report):
    try:
        return check_properties([{k: row[k] for k in ('name', 'left', 'right')} for row in report['attempts']],
                                radius=report['radius'], budget=report['budget_per_property']) == report
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return False
