"""K0 of finite graph Leavitt path algebras via exact presentation divisors (19).

Regular vertices contribute e_v - sum_w A[v,w] e_w; sinks impose no relation.
No higher or general algebraic/topological K-theory is claimed.
"""
from itertools import combinations
from math import gcd
from ._area_utils import calculate as _calculate


def _determinant(rows):
    a = [list(row) for row in rows];n = len(a);previous,sign = 1,1
    if n==1:return a[0][0]
    for k in range(n-1):
        pivot = next((i for i in range(k,n) if a[i][k]),None)
        if pivot is None:return 0
        if pivot!=k:a[k],a[pivot] = a[pivot],a[k];sign = -sign
        value = a[k][k]
        for i in range(k+1,n):
            for j in range(k+1,n):a[i][j] = (a[i][j]*value-a[i][k]*a[k][j])//previous
            a[i][k] = 0
        previous = value
    return sign*a[-1][-1]


def k_theory(adjacency):
    if not isinstance(adjacency,list) or not 1<=len(adjacency)<=6 or any(not isinstance(row,list) or len(row)!=len(adjacency) or any(type(v) is not int or not 0<=v<=1000000 for v in row) for row in adjacency):
        raise ValueError('Require a 1–6 vertex finite directed multigraph')
    n = len(adjacency);regular = [i for i,row in enumerate(adjacency) if any(row)]
    presentation = [[int(i==j)-adjacency[j][i] for j in regular] for i in range(n)]
    divisors,invariants,previous = [],[],1
    for size in range(1,min(n,len(regular))+1):
        divisor = 0
        for rows in combinations(range(n),size):
            for cols in combinations(range(len(regular)),size):
                minor = _determinant([[presentation[i][j] for j in cols] for i in rows])
                divisor = gcd(divisor,abs(minor))
                if divisor==1:break
            if divisor==1:break
        if not divisor:break
        divisors.append(divisor);invariants.append(divisor//previous);previous = divisor
    return {'presentation':presentation,'determinantal_divisors':divisors,'invariant_factors':invariants,
            'K0_free_rank':n-len(invariants),'K0_torsion':[v for v in invariants if v>1],
            'scope':'K0 of the finite graph Leavitt path algebra over a field; no higher K groups.'}


def calculate(**arguments):return _calculate('k_theory',**arguments)
