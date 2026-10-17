"""Finite measures and exact conditional expectations on atomic sigma-algebras (28)."""
from fractions import Fraction
from ._area_utils import vector,calculate as _calculate


def measure_theory(weights, values, *, partition=None):
    weights,values = vector(weights),vector(values)
    if len(weights)!=len(values) or any(w<0 for w in weights) or not sum(weights):
        raise ValueError('Require equal dimensions and a nonzero nonnegative measure')
    n = len(weights);partition = list(range(n)) if partition is None else partition
    if not isinstance(partition,list) or len(partition)!=n or any(type(v) is not int or not 0<=v<n for v in partition):
        raise ValueError('Invalid sigma-algebra atom labels')
    atoms = []
    expected = [Fraction(0)]*n
    for label in sorted(set(partition)):
        members = [i for i in range(n) if partition[i]==label]
        mass = sum(weights[i] for i in members)
        average = sum(weights[i]*values[i] for i in members)/mass if mass else Fraction(0)
        for i in members:expected[i] = average
        atoms.append({'members':members,'measure':mass,'conditional_value':average})
    integral = sum(w*v for w,v in zip(weights,values))
    return {'total_measure':sum(weights),'integral':integral,'normalized_mean':integral/sum(weights),
            'conditional_expectation':expected,'atoms':atoms,'sigma_algebra_size':2**len(atoms),
            'tower_integral_verified':sum(w*v for w,v in zip(weights,expected))==integral,
            'scope':'Finite atomic measure; conditional value chosen as zero on null atoms.'}


def calculate(**arguments):return _calculate('measure_theory',**arguments)
