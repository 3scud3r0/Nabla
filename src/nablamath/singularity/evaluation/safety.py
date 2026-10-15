"""Offline checks of declarative agent permissions, budgets and review gates."""

from itertools import islice


def assess_plan(plan, registry, permissions, ledger):
    """Return actionable failures without running a tool or external action."""
    failures = []
    try:
        plan.preflight(registry, permissions)
    except (ValueError, PermissionError, TypeError) as exc:
        failures.append(dict(check='capabilities_and_budgets', reason=str(exc)))
    try:
        ledger.require(plan)
    except PermissionError as exc:
        failures.append(dict(check='human_approval', reason=str(exc)))
    return dict(plan_id=plan.content_id, allowed=not failures, failures=failures,
                scope='Offline declarative checks; no OS isolation or external authorization proof')


def evaluate_cases(cases, registry, permissions):
    """Measure expected allow/deny outcomes; retain every case, including failures."""
    cases = list(islice(cases, 1001))
    if not cases or len(cases) > 1000:
        raise ValueError('Provide 1–1000 safety cases')
    ids = [case['id'] for case in cases]
    if len(set(ids)) != len(ids) or any(not isinstance(i, str) or not i for i in ids):
        raise ValueError('Unique case identifiers required')
    results = []
    for case in cases:
        if type(case['expected_allowed']) is not bool:
            raise ValueError('Expected outcome must be boolean')
        result = assess_plan(case['plan'], registry, permissions, case['ledger'])
        results.append(dict(id=case['id'], passed=result['allowed'] == case['expected_allowed'], **result))
    return dict(cases=results, passed=sum(c['passed'] for c in results), total=len(results),
                limitations='Finite local cases do not establish general agent safety')
