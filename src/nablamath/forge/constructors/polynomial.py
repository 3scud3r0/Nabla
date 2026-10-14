"""Choose integer roots, convolve linear factors; repeated roots are retained."""
from fractions import Fraction
from ..sampling import rng_for
from ..task_spec import TaskSpec


def construct(seed,size=3):
    rng=rng_for(seed,size)
    roots=sorted(rng.randint(-5,5) for _ in range(size))
    coefficients=[Fraction(1)]
    for root in roots:
        product=[Fraction()]*(len(coefficients)+1)
        for i,value in enumerate(coefficients):
            product[i]-=root*value
            product[i+1]+=value
        coefficients=product
    return TaskSpec('factored_polynomial',{'coefficients':[str(v) for v in coefficients]},size),{'roots':[str(v) for v in roots]}
