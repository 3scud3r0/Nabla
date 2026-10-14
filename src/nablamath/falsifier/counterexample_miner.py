"""Keep every bounded refutation attempt, including time/budget-limited failures."""
from .search import investigate
from ..core.semantic_ir import fingerprint


def mine(pairs, *, radius=3, budget=1000):
    pairs=tuple(pairs)
    if not 1<=len(pairs)<=32:
        raise ValueError('Mineração requer de 1 a 32 pares')
    attempts=[investigate(left,right,radius=radius,budget=budget) for left,right in pairs]
    payload={'attempts':attempts,'counterexamples':sum(a['search']['status'] in {'counterexample','domain_counterexample'} for a in attempts),
             'scope':'finite integer domains, not universal theorem search','formal_proof':False}
    return {**payload,'mining_id':fingerprint(payload)}
