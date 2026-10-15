"""Exact paired sign tests; independence and multiplicity remain explicit assumptions."""
import math


def paired_sign_test(candidate_errors, baseline_errors, *, alpha=.05):
    a,b=tuple(candidate_errors),tuple(baseline_errors)
    if not a or len(a)!=len(b) or len(a)>128 or not 0<alpha<1:
        raise ValueError('Pares e alpha inválidos')
    if any(v is None or not math.isfinite(v) or v<0 for v in a+b):
        return {'valid':False,'p_value':None,'significant':False,'reason':'nonfinite_or_negative_errors'}
    wins=sum(x<y for x,y in zip(a,b)); regressions=sum(x>y for x,y in zip(a,b)); n=wins+regressions
    p=sum(math.comb(n,k) for k in range(wins,n+1))/2**n if n else 1.
    return {'valid':True,'wins':wins,'regressions':regressions,'ties':len(a)-n,'p_value':p,
            'alpha':alpha,'significant':p<=alpha,
            'assumptions':'paired iid sign null; synthetic parameter variants do not ensure independence'}


def practical_effect(candidate_errors, baseline_errors, *, minimum_relative_reduction=0.01):
    """Median paired relative error reduction; distinct from significance and cost.

    A zero baseline tied at zero contributes no gain. A regression from an exact
    baseline contributes -1 and is separately rejected by the regression gate.
    This is descriptive effect size, not a confidence interval or iid guarantee.
    """
    from statistics import median
    if (isinstance(minimum_relative_reduction, bool) or not math.isfinite(minimum_relative_reduction)
            or not 0 <= minimum_relative_reduction <= 1):
        raise ValueError('Efeito mínimo deve estar entre zero e um')
    a, b = tuple(candidate_errors), tuple(baseline_errors)
    if not a or len(a) != len(b) or len(a) > 128:
        raise ValueError('Pares inválidos')
    if any(v is None or isinstance(v, bool) or not math.isfinite(v) or v < 0 for v in a+b):
        return {'valid': False, 'passed': False, 'reason': 'invalid_errors'}
    reductions = [(y-x)/y if y else (0. if x == 0 else -1.) for x,y in zip(a,b)]
    if not all(math.isfinite(v) for v in reductions):
        return {'valid': False, 'passed': False, 'reason': 'nonfinite_effect'}
    effect = median(reductions)
    return {'valid': True, 'passed': effect >= minimum_relative_reduction,
            'median_relative_error_reduction': effect, 'paired_relative_reductions': reductions,
            'minimum_relative_reduction': minimum_relative_reduction,
            'scope': 'descriptive paired effect, not evidence of general recursive improvement'}
