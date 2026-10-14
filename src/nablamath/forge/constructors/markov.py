"""Choose a stationary law and reconstruct a strictly positive rational transition."""
from fractions import Fraction
from ..sampling import rng_for
from ..task_spec import TaskSpec


def construct(seed,size=3):
    rng=rng_for(seed,size)
    weights=[rng.randint(1,9) for _ in range(size)]
    stationary=[Fraction(w,sum(weights)) for w in weights]
    alpha=rng.choice((Fraction(1,2),Fraction(2,3),Fraction(3,4)))
    transition=[[(1-alpha)*int(i==j)+alpha*stationary[j] for j in range(size)] for i in range(size)]
    return TaskSpec('stationary_markov',{'transition':[[str(v) for v in row] for row in transition]},size),{'stationary':[str(v) for v in stationary]}
