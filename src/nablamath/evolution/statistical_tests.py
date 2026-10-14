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
