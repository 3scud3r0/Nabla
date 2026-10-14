"""Known violations of deliberately false polynomial equalities in a declared grid."""
from fractions import Fraction
from ...expression import Binary,Number,Symbol,to_data
from ..sampling import rng_for
from ..task_spec import TaskSpec


def construct(seed,size=3):
    rng=rng_for(seed,size)
    root=rng.randint(-3,3)
    left=Binary('+',Binary('**',Symbol('x'),Number(Fraction(size))),Number(Fraction(rng.randint(-5,5))))
    offset=Binary('-',Symbol('x'),Number(Fraction(root)))
    right=Binary('+',left,Binary('**',offset,Number(Fraction(2))))
    return TaskSpec('counterexample',{'left':to_data(left),'right':to_data(right),'variables':['x'],'radius':4},size),{'assignment':{'x':str(root+1)}}
