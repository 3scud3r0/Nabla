"""Select a solution and strictly diagonally dominant matrix; compute rhs independently."""
from fractions import Fraction
from ..sampling import rng_for
from ..task_spec import TaskSpec


def construct(seed,size=3):
    rng=rng_for(seed,size)
    solution=tuple(Fraction(rng.randint(-9,9)) for _ in range(size))
    rows=[]
    for i in range(size):
        row=[Fraction(rng.randint(-4,4)) for _ in range(size)]
        row[i]=1+sum(abs(v) for j,v in enumerate(row) if i!=j)
        rows.append(row)
    rhs=[sum(a*b for a,b in zip(row,solution)) for row in rows]
    return TaskSpec('linear_system',{'matrix':[[str(v) for v in row] for row in rows],'rhs':[str(v) for v in rhs]},size),{'solution':[str(v) for v in solution]}
