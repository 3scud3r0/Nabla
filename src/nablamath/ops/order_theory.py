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
