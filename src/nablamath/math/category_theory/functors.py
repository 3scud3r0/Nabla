"""Funtores e transformações naturais entre categorias finitas."""

from dataclasses import dataclass
from typing import Mapping

from .categories import FiniteCategory


@dataclass(frozen=True)
class Functor:
    source: FiniteCategory
    target: FiniteCategory
    object_map: Mapping[str, str]
    morphism_map: Mapping[str, str]

    def __post_init__(self) -> None:
        if set(self.object_map) != set(self.source.objects) or set(self.morphism_map) != {a.name for a in self.source.morphisms}:
            raise ValueError("funtor deve mapear todos os objetos e morfismos")
        if any(value not in self.target.objects for value in self.object_map.values()): raise ValueError("objeto alvo inválido")
        for arrow in self.source.morphisms:
            image = self.target.arrow(self.morphism_map[arrow.name])
            if image.source != self.object_map[arrow.source] or image.target != self.object_map[arrow.target]:
                raise ValueError("funtor não preserva tipos")
        for obj, identity in self.source.identities.items():
            if self.morphism_map[identity] != self.target.identities[self.object_map[obj]]:
                raise ValueError("funtor não preserva identidades")
        for (g, f), composite in self.source.composition.items():
            if self.morphism_map[composite] != self.target.compose(self.morphism_map[g], self.morphism_map[f]):
                raise ValueError("funtor não preserva composição")


@dataclass(frozen=True)
class NaturalTransformation:
    source: Functor
    target: Functor
    components: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.source.source != self.target.source or self.source.target != self.target.target:
            raise ValueError("funtores devem ter mesma origem e destino")
        category = self.source.source
        codomain = self.source.target
        if set(self.components) != set(category.objects): raise ValueError("componente ausente")
        for obj, name in self.components.items():
            arrow = codomain.arrow(name)
            if arrow.source != self.source.object_map[obj] or arrow.target != self.target.object_map[obj]:
                raise ValueError("componente com tipo incorreto")
        for arrow in category.morphisms:
            left = codomain.compose(self.components[arrow.target], self.source.morphism_map[arrow.name])
            right = codomain.compose(self.target.morphism_map[arrow.name], self.components[arrow.source])
            if left != right: raise ValueError("quadrado de naturalidade não comuta")


__all__ = ["Functor", "NaturalTransformation"]


def compose_functors(left,right):
    if right.target!=left.source:raise ValueError('Functor endpoints do not compose')
    return Functor(right.source,left.target,{k:left.object_map[v] for k,v in right.object_map.items()},
                   {k:left.morphism_map[v] for k,v in right.morphism_map.items()})


def identity_functor(category):
    return Functor(category,category,{o:o for o in category.objects},{a.name:a.name for a in category.morphisms})


def adjunction(left,right,unit,counit):
    if left.source!=right.target or left.target!=right.source:raise ValueError('Adjunction functors have incompatible endpoints')
    eta=NaturalTransformation(identity_functor(left.source),compose_functors(right,left),unit)
    epsilon=NaturalTransformation(compose_functors(left,right),identity_functor(left.target),counit)
    for obj in left.source.objects:
        image=left.object_map[obj]
        if left.target.compose(counit[image],left.morphism_map[unit[obj]])!=left.target.identities[image]:raise ValueError('Left triangle identity fails')
    for obj in right.source.objects:
        image=right.object_map[obj]
        if right.target.compose(right.morphism_map[counit[obj]],unit[image])!=right.target.identities[image]:raise ValueError('Right triangle identity fails')
    def is_iso(category,name):
        arrow=category.arrow(name)
        return any(a.source==arrow.target and a.target==arrow.source and category.compose(a.name,name)==category.identities[arrow.source] and category.compose(name,a.name)==category.identities[arrow.target] for a in category.morphisms)
    equivalence=all(is_iso(left.source,v) for v in unit.values()) and all(is_iso(left.target,v) for v in counit.values())
    return {'adjunction':True,'equivalence':equivalence,'triangle_identities_verified':True}


def finite_adjunction(source,target,left,right,unit,counit):
    from .categories import Morphism
    def category(raw):
        if set(raw)!={'objects','morphisms','identities','composition'} or len(raw['objects'])>16 or len(raw['morphisms'])>64:raise ValueError('Bounded closed category data required')
        composition={}
        for entry in raw['composition']:
            if set(entry)!={'after','before','result'} or (entry['after'],entry['before']) in composition:raise ValueError('Unique composition records required')
            composition[entry['after'],entry['before']]=entry['result']
        return FiniteCategory(tuple(raw['objects']),tuple(Morphism(**v) for v in raw['morphisms']),raw['identities'],composition)
    a,b=category(source),category(target)
    if set(left)!={'objects','morphisms'} or set(right)!={'objects','morphisms'}:raise ValueError('Explicit closed functor maps required')
    f=Functor(a,b,left['objects'],left['morphisms']);g=Functor(b,a,right['objects'],right['morphisms'])
    return adjunction(f,g,unit,counit)
