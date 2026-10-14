"""Select a primitive, differentiate coefficients, retain the primitive as witness."""
from fractions import Fraction
from ..sampling import rng_for
from ..task_spec import TaskSpec


def construct(seed,size=3):
    rng=rng_for(seed,size)
    primitive=(Fraction(),)+tuple(Fraction(rng.choice((-5,-3,-1,1,3,5))) for _ in range(size))
    coefficients=tuple(i*c for i,c in enumerate(primitive) if i)
    task=TaskSpec('polynomial_integral',{'coefficients':[str(v) for v in coefficients]},size)
    return task,{'coefficients':[str(v) for v in primitive]}
