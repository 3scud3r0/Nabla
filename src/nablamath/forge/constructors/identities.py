"""Construct polynomial identities by distributivity without erasing partial domains."""
from fractions import Fraction
from ...expression import Binary,Number,Symbol,to_data
from ..sampling import rng_for
from ..task_spec import TaskSpec


def construct(seed,size=3):
    rng=rng_for(seed,size)
    def term():
        return Binary('*',Number(Fraction(rng.choice((-5,-3,-1,1,3,5)))),Binary('**',Symbol('x'),Number(Fraction(rng.randint(1,size)))))
    a,b,c=term(),term(),term()
    left=Binary('+',Binary('*',a,b),Binary('*',a,c))
    right=Binary('*',a,Binary('+',b,c))
    return TaskSpec('polynomial_identity',{'left':to_data(left),'right':to_data(right),'variables':['x']},size),{'expression':to_data(right)}
