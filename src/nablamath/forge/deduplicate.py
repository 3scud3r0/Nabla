"""Semantic keys ignore construction seeds, syntax order and equivalent linear row operations."""
from collections import Counter
from ..core.semantic_ir import fingerprint,rational
from ..schema.expression import from_data


def semantic_fingerprint(task):
    p=task.problem
    if task.family=='linear_system':
        from ..math.linear_algebra import Matrix
        reduced,_=Matrix(tuple(tuple(rational(v) for v in row)+(rational(b),) for row,b in zip(p['matrix'],p['rhs']))).echelon()
        p={'reduced_augmented':[[str(v) for v in row] for row in reduced.rows]}
    elif task.family=='polynomial_identity':
        from ..math.algebra.groebner import polynomial_from_expr
        sides=[]
        for key in ('left','right'):
            polynomial=polynomial_from_expr(from_data(p[key]),tuple(p['variables']))
            sides.append([[list(m),str(c)] for m,c in polynomial.terms])
        from ..core.semantic_ir import canonical_json
        p={'variables':p['variables'],'sides':sorted(sides,key=canonical_json)}
    return fingerprint({'family':task.family,'problem':p})


class SemanticIndex:
    def __init__(self):
        self._seen={}
        self.attempted=0
        self.duplicates=0
        self.families=Counter()
        self.sizes=Counter()

    def add(self,task):
        self.attempted+=1
        key=semantic_fingerprint(task)
        if key in self._seen:
            self.duplicates+=1
            return False
        self._seen[key]=task.content_id
        self.families[task.family]+=1
        self.sizes[task.size]+=1
        return True

    def report(self):
        return {'attempted':self.attempted,'unique_semantics':len(self._seen),'duplicates':self.duplicates,
                'semantic_unique_ratio':len(self._seen)/self.attempted if self.attempted else 0,
                'families':dict(sorted(self.families.items())),
                'sizes':{str(k):v for k,v in sorted(self.sizes.items())},
                'scope':'local_generated_tasks; not external diversity or training utility'}
