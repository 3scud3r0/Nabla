"""Categorias pequenas finitas por tabelas explícitas."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Mapping


@dataclass(frozen=True)
class Morphism:
    name: str
    source: str
    target: str
    def __post_init__(self) -> None:
        if not self.name or not self.source or not self.target: raise ValueError("morfismo inválido")


@dataclass(frozen=True)
class FiniteCategory:
    objects: tuple[str, ...]
    morphisms: tuple[Morphism, ...]
    identities: Mapping[str, str]
    composition: Mapping[tuple[str, str], str]  # (g,f) = g ∘ f

    def __post_init__(self) -> None:
        objects = set(self.objects)
        arrows = {arrow.name: arrow for arrow in self.morphisms}
        if not objects or len(objects) != len(self.objects) or len(arrows) != len(self.morphisms):
            raise ValueError("objetos ou morfismos duplicados/vazios")
        if any(arrow.source not in objects or arrow.target not in objects for arrow in self.morphisms):
            raise ValueError("morfismo referencia objeto ausente")
        if set(self.identities) != objects:
            raise ValueError("cada objeto requer identidade")
        for obj, name in self.identities.items():
            arrow = arrows.get(name)
            if arrow is None or arrow.source != obj or arrow.target != obj:
                raise ValueError("identidade inválida")
        expected = {(g.name, f.name) for f, g in product(self.morphisms, repeat=2) if f.target == g.source}
        if set(self.composition) != expected or any(name not in arrows for name in self.composition.values()):
            raise ValueError("composição deve cobrir exatamente os pares componíveis")
        for (g, f), result in self.composition.items():
            if arrows[result].source != arrows[f].source or arrows[result].target != arrows[g].target:
                raise ValueError("tipo da composição inválido")
        for arrow in self.morphisms:
            if self.compose(self.identities[arrow.target], arrow.name) != arrow.name or self.compose(arrow.name, self.identities[arrow.source]) != arrow.name:
                raise ValueError("lei da identidade violada")
        for f, g, h in product(self.morphisms, repeat=3):
            if f.target == g.source and g.target == h.source:
                if self.compose(h.name, self.compose(g.name, f.name)) != self.compose(self.compose(h.name, g.name), f.name):
                    raise ValueError("associatividade violada")

    def arrow(self, name: str) -> Morphism:
        for arrow in self.morphisms:
            if arrow.name == name: return arrow
        raise KeyError(name)

    def compose(self, g: str, f: str) -> str:
        try: return self.composition[g, f]
        except KeyError as exc: raise ValueError("morfismos não componíveis") from exc


def discrete_category(objects: tuple[str, ...]) -> FiniteCategory:
    morphisms = tuple(Morphism(f"id:{obj}", obj, obj) for obj in objects)
    identities = {obj: f"id:{obj}" for obj in objects}
    composition = {(name, name): name for name in identities.values()}
    return FiniteCategory(objects, morphisms, identities, composition)


__all__ = ["FiniteCategory", "Morphism", "discrete_category"]


@dataclass(frozen=True)
class PresentedCategory:
    """Typed free paths modulo supplied strictly length-reducing relations.

    Reduction terminates by length; without a confluence certificate, equality
    of distinct normal forms remains undecided, rather than declared false.
    """
    objects: tuple[str,...]
    generators: tuple[Morphism,...]
    relations: tuple[tuple[tuple[str,...],tuple[str,...]],...]=()

    def __post_init__(self):
        if not 1<=len(self.objects)<=64 or len(set(self.objects))!=len(self.objects) or len(self.generators)>64 or len({g.name for g in self.generators})!=len(self.generators):raise ValueError('Invalid category presentation')
        if any(g.source not in self.objects or g.target not in self.objects for g in self.generators):raise ValueError('Generator endpoint outside category')
        if len(self.relations)>128:raise ValueError('Relation count budget exceeded')
        for left,right in self.relations:
            _,a=self._path(left);_,b=self._path(right)
            if len(a)<=len(b) or self.path_type(left)!=self.path_type(right):raise ValueError('Relations must be parallel and strictly length reducing')

    def _path(self,path):
        arrows={g.name:g for g in self.generators}
        if isinstance(path,dict):
            if set(path)!={'source','arrows'} or path['source'] not in self.objects or not isinstance(path['arrows'],(list,tuple)):raise ValueError('Typed path needs source and arrows')
            source,word=path['source'],tuple(path['arrows'])
        else:
            word=tuple(path)
            if not word or word[0] not in arrows:raise ValueError('Identity paths require an explicit source object')
            source=arrows[word[0]].source
        if len(word)>4096 or any(name not in arrows for name in word):raise ValueError('Bounded generator path required')
        if word and arrows[word[0]].source!=source:raise ValueError('Explicit path source differs from its first arrow')
        if any(arrows[a].target!=arrows[b].source for a,b in zip(word,word[1:])):raise ValueError('Path generators do not compose')
        return source,word

    def path_type(self,path):
        arrows={g.name:g for g in self.generators}
        source,word=self._path(path)
        return source,arrows[word[-1]].target if word else source

    def identity(self,obj):
        if obj not in self.objects:raise ValueError('Unknown identity object')
        return {'source':obj,'arrows':[]}

    def normal_form(self,path):
        source,path=self._path(path)
        while True:
            changed=False
            for left,right in self.relations:
                _,left=self._path(left);_,right=self._path(right)
                for i in range(len(path)-len(left)+1):
                    if path[i:i+len(left)]==tuple(left):path=path[:i]+tuple(right)+path[i+len(left):];changed=True;break
                if changed:break
            if not changed:return {'source':source,'arrows':list(path)}

    def compose(self,left,right):
        if self.path_type(right)[1]!=self.path_type(left)[0]:raise ValueError('Presented paths do not compose')
        source,a=self._path(right);_,b=self._path(left)
        return self.normal_form({'source':source,'arrows':list(a+b)})

    def equal(self,left,right):
        if self.path_type(left)!=self.path_type(right):return {'equal':False,'reason':'different arrow types'}
        same=self.normal_form(left)==self.normal_form(right)
        return {'equal':True if same else None,'reason':'common reduction witness' if same else 'distinct normal forms; confluence not established'}


def presented_equality(objects,generators,relations,left,right):
    if len(generators)>64:raise ValueError('Presented generator budget exceeded')
    arrows=tuple(Morphism(**record) for record in generators)
    category=PresentedCategory(tuple(objects),arrows,tuple((pair[0],pair[1]) for pair in relations))
    return {**category.equal(left,right),'left_normal_form':category.normal_form(left),'right_normal_form':category.normal_form(right)}
