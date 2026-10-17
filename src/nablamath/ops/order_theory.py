"""Finite partial orders, Hasse covers and exact lattice joins/meets (MSC 06)."""
from ._area_utils import calculate as _calculate


def order_theory(relation):
    if not isinstance(relation,list) or not 1<=len(relation)<=64 or any(not isinstance(row,list) or len(row)!=len(relation) or any(type(v) is not bool for v in row) for row in relation):
        raise ValueError('Require a square boolean relation on 1–64 elements')
    n = len(relation)
    for i in range(n):
        if not relation[i][i]:raise ValueError('Order must be reflexive')
        for j in range(n):
            if i!=j and relation[i][j] and relation[j][i]:raise ValueError('Order must be antisymmetric')
            for k in range(n):
                if relation[i][j] and relation[j][k] and not relation[i][k]:raise ValueError('Order must be transitive')
    covers = [[i,j] for i in range(n) for j in range(n) if i!=j and relation[i][j] and
              not any(k not in (i,j) and relation[i][k] and relation[k][j] for k in range(n))]
    joins,meets = [],[]
    for i in range(n):
        jr,mr = [],[]
        for j in range(n):
            upper = [k for k in range(n) if relation[i][k] and relation[j][k]]
            lower = [k for k in range(n) if relation[k][i] and relation[k][j]]
            least = [k for k in upper if all(relation[k][v] for v in upper)]
            greatest = [k for k in lower if all(relation[v][k] for v in lower)]
            jr.append(least[0] if least else None);mr.append(greatest[0] if greatest else None)
        joins.append(jr);meets.append(mr)
    return {'size':n,'covers':covers,'joins':joins,'meets':meets,
            'is_lattice':all(v is not None for table in (joins,meets) for row in table for v in row),
            'minimal':[i for i in range(n) if not any(j!=i and relation[j][i] for j in range(n))],
            'maximal':[i for i in range(n) if not any(j!=i and relation[i][j] for j in range(n))]}


def calculate(**arguments):return _calculate('order_theory',**arguments)


def heyting_algebra(relation):
    """Finite distributive lattices are Heyting algebras; compute implication."""
    result=order_theory(relation);n=len(relation)
    if n>32 or not result['is_lattice']:raise ValueError('Require a lattice of at most 32 elements')
    join,meet=result['joins'],result['meets']
    distributive=all(meet[a][join[b][c]]==join[meet[a][b]][meet[a][c]] for a in range(n) for b in range(n) for c in range(n))
    if not distributive:raise ValueError('Lattice is not distributive')
    bottom,top=result['minimal'][0],result['maximal'][0];implication=[]
    for a in range(n):
        row=[]
        for b in range(n):
            candidates=[x for x in range(n) if relation[meet[a][x]][b]]
            row.append(next(x for x in candidates if all(relation[y][x] for y in candidates)))
        implication.append(row)
    negation=[implication[a][bottom] for a in range(n)]
    return {**result,'implication':implication,'negation':negation,'bottom':bottom,'top':top,
            'boolean':all(join[a][negation[a]]==top for a in range(n))}


def boolean_bitset(universe_size,left,right):
    if type(universe_size) is not int or not 0<=universe_size<=4096:raise ValueError('Universe bit budget exceeded')
    mask=(1<<universe_size)-1
    if any(type(v) is not int or v<0 or v>mask for v in (left,right)):raise ValueError('Invalid subset bitset')
    return {'union':left|right,'intersection':left&right,'difference':left&~right,
            'complement_left':mask^left,'implies':((mask^left)|right),'subset':left&right==left}


def symbolic_order(elements,predicate):
    from ..math._structured import expression,sympy
    from ._area_utils import vector
    elements=vector(elements,maximum=64);f,(a,b)=expression(predicate,['a','b'],functions=False)
    # The polynomial/rational sign predicate defines a <= b iff f(a,b)>=0.
    relation=[]
    for x in elements:
        row=[]
        for y in elements:
            v=f.subs({a:sympy().Rational(str(x)),b:sympy().Rational(str(y))})
            if v.is_real is not True:raise ValueError('Predicate undefined on the supplied domain')
            row.append(bool(v>=0))
        relation.append(row)
    return {**order_theory(relation),'relation':relation,'scope':'Symbolic predicate restricted to the supplied finite domain.'}
