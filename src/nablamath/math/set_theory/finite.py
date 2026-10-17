"""Construções e relações em conjuntos finitos explícitos."""

from itertools import combinations
from typing import Callable, TypeVar

T = TypeVar("T")
U = TypeVar("U")


def power_set(values: frozenset[T], *, max_elements: int = 20) -> frozenset[frozenset[T]]:
    if len(values) > max_elements: raise ValueError("conjunto excede o limite de enumeração")
    ordered = tuple(sorted(values, key=repr))
    return frozenset(frozenset(selection) for size in range(len(ordered) + 1)
                     for selection in combinations(ordered, size))


def cartesian_product(left: frozenset[T], right: frozenset[U]) -> frozenset[tuple[T, U]]:
    return frozenset((a, b) for a in left for b in right)


def equivalence_classes(values: frozenset[T], relation: Callable[[T, T], bool]) -> tuple[frozenset[T], ...]:
    ordered = tuple(sorted(values, key=repr))
    for a in ordered:
        if relation(a, a) is not True: raise ValueError("relação não reflexiva")
        for b in ordered:
            if relation(a, b) != relation(b, a): raise ValueError("relação não simétrica")
            for c in ordered:
                if relation(a, b) and relation(b, c) and not relation(a, c): raise ValueError("relação não transitiva")
    remaining = set(values); classes = []
    while remaining:
        representative = min(remaining, key=repr)
        block = frozenset(value for value in values if relation(representative, value))
        classes.append(block); remaining -= block
    return tuple(classes)


def is_injective(domain: frozenset[T], function: Callable[[T], U]) -> bool:
    images = [function(value) for value in domain]
    return len(set(images)) == len(images)


def is_surjective(domain: frozenset[T], codomain: frozenset[U], function: Callable[[T], U]) -> bool:
    images = {function(value) for value in domain}
    if not images <= codomain: raise ValueError("função produz valor fora do contradomínio")
    return images == codomain


__all__ = ["cartesian_product", "equivalence_classes", "is_injective", "is_surjective", "power_set"]
class IntegerProgression:
    """Decidable infinite arithmetic progression, represented without enumeration."""
    def __init__(self,modulus=1,residue=0,lower=None):
        if type(modulus) is not int or not 1<=modulus<=10**12 or type(residue) is not int or (lower is not None and type(lower) is not int):raise ValueError('Invalid integer progression')
        self.modulus,self.residue,self.lower=modulus,residue%modulus,lower

    def contains(self,value):
        return type(value) is int and (self.lower is None or value>=self.lower) and value%self.modulus==self.residue

    def prefix(self,count,start=0):
        if type(count) is not int or not 0<=count<=10000:raise ValueError('Finite prefix budget exceeded')
        start=max(start,self.lower) if self.lower is not None else start
        first=start+(self.residue-start)%self.modulus
        return [first+i*self.modulus for i in range(count)]


def progression(modulus,residue,values,*,lower=None,count=10,start=0):
    if len(values)>10000 or type(start) is not int:raise ValueError('Progression query budget exceeded')
    represented=IntegerProgression(modulus,residue,lower)
    return {'membership':[represented.contains(v) for v in values],'prefix':represented.prefix(count,start),
            'scope':'Exact symbolic integer progression; finite membership and prefix queries.'}
