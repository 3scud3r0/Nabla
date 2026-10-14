"""Choose the optimum, construct a positive-definite quadratic and its stationarity equations."""
from fractions import Fraction
from ..sampling import rng_for
from ..task_spec import TaskSpec


def construct(seed,size=3):
    rng=rng_for(seed,size)
    optimum=[Fraction(rng.randint(-5,5)) for _ in range(size)]
    b=[[Fraction(rng.randint(-3,3)) for _ in range(size)] for _ in range(size)]
    matrix=[[sum(b[k][i]*b[k][j] for k in range(size))+int(i==j) for j in range(size)] for i in range(size)]
    linear=[-sum(v*x for v,x in zip(row,optimum)) for row in matrix]
    return TaskSpec('convex_quadratic',{'matrix':[[str(v) for v in row] for row in matrix],
        'linear':[str(v) for v in linear],'constant':'0'},size),{'solution':[str(v) for v in optimum]}
