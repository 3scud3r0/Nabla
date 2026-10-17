"""Grupos finitos por tabela explícita, adequados a exemplos e verificação exaustiva."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Generic, Mapping, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class FiniteGroup(Generic[T]):
    elements: tuple[T, ...]
    identity: T
    table: Mapping[tuple[T, T], T]

    def __post_init__(self) -> None:
        values = set(self.elements)
        if not self.elements or len(values) != len(self.elements) or self.identity not in values:
            raise ValueError("elementos/identidade inválidos")
        expected = set(product(self.elements, repeat=2))
        if set(self.table) != expected or any(value not in values for value in self.table.values()):
            raise ValueError("tabela não é uma operação fechada e total")
        for element in self.elements:
            if self.multiply(self.identity, element) != element or self.multiply(element, self.identity) != element:
                raise ValueError("identidade inválida")
            if not any(self.multiply(element, candidate) == self.identity and self.multiply(candidate, element) == self.identity
                       for candidate in self.elements):
                raise ValueError("elemento sem inverso bilateral")
        for a, b, c in product(self.elements, repeat=3):
            if self.multiply(self.multiply(a, b), c) != self.multiply(a, self.multiply(b, c)):
                raise ValueError("operação não associativa")

    def multiply(self, left: T, right: T) -> T:
        try: return self.table[left, right]
        except KeyError as exc: raise ValueError("elemento fora do grupo") from exc

    def inverse(self, element: T) -> T:
        for candidate in self.elements:
            if self.multiply(element, candidate) == self.identity and self.multiply(candidate, element) == self.identity:
                return candidate
        raise ValueError("elemento fora do grupo")

    def order(self, element: T) -> int:
        if element not in self.elements: raise ValueError("elemento fora do grupo")
        value = self.identity
        for exponent in range(1, len(self.elements) + 1):
            value = self.multiply(value, element)
            if value == self.identity: return exponent
        raise AssertionError("grupo validado sem ordem finita")


def cyclic_group(order: int) -> FiniteGroup[int]:
    if not 1 <= order <= 4096: raise ValueError("ordem fora do limite")
    elements = tuple(range(order))
    return FiniteGroup(elements, 0, {(a, b): (a + b) % order for a in elements for b in elements})


__all__ = ["FiniteGroup", "cyclic_group"]


def permutation_group(generators,*,subgroup_generators=None):
    from .._structured import sympy
    sympy()
    from sympy.combinatorics import Permutation,PermutationGroup
    if not isinstance(generators,list) or not 1<=len(generators)<=32:raise ValueError('Permutation generator budget exceeded')
    n=len(generators[0])
    if not 1<=n<=128 or any(sorted(g)!=list(range(n)) for g in generators):raise ValueError('Total equal-degree permutations required')
    group=PermutationGroup([Permutation(g) for g in generators]);group.schreier_sims()
    result={'order':int(group.order()),'base':list(group.base),'strong_generators':[list(g.array_form) for g in group.strong_gens],
            'abelian':bool(group.is_abelian),'solvable':bool(group.is_solvable),'orbits':[sorted(orbit) for orbit in group.orbits()]}
    if subgroup_generators is not None:
        if not subgroup_generators or len(subgroup_generators)>32 or any(sorted(g)!=list(range(n)) for g in subgroup_generators):raise ValueError('Invalid subgroup generators')
        h=PermutationGroup([Permutation(g) for g in subgroup_generators])
        if not h.is_subgroup(group):raise ValueError('Proposed subgroup lies outside the group')
        result['subgroup_order']=int(h.order());result['normal']=bool(h.is_normal(group));result['index']=int(group.order()//h.order())
        result['quotient_table_available']=bool(result['normal'] and group.order()<=10000 and result['index']<=64)
        if result['quotient_table_available']:
            cosets=group.coset_transversal(h);result['coset_representatives']=[list(g.array_form) for g in cosets]
            result['quotient_table']=[[next(k for k,c in enumerate(cosets) if h.contains(a*b*c**-1)) for b in cosets] for a in cosets]
    return result
