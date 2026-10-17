"""Fundamental-group presentations of finite connected simplicial 2-skeleta."""
from collections import deque
from .._structured import sympy
from .homology import SimplicialComplex


def fundamental_group(facets):
    if not isinstance(facets,list) or not 1<=len(facets)<=128 or any(not 1<=len(f)<=4 or len(set(f))!=len(f) or any(type(v) is not int or v<0 for v in f) for f in facets):raise ValueError('Bounded integer-labelled complex required')
    complex_=SimplicialComplex(facets);vertices=[v[0] for v in complex_.cells(0)];edges=complex_.cells(1)
    if len(vertices)>64:raise ValueError('Vertex budget exceeded')
    adjacency={v:[] for v in vertices}
    for a,b in edges:adjacency[a].append(b);adjacency[b].append(a)
    seen={vertices[0]};queue=deque(seen);tree=set()
    while queue:
        a=queue.popleft()
        for b in adjacency[a]:
            if b not in seen:seen.add(b);queue.append(b);tree.add(frozenset((a,b)))
    if len(seen)!=len(vertices):raise ValueError('Choose a connected component/base point first')
    generators={edge:i+1 for i,edge in enumerate(edge for edge in edges if frozenset(edge) not in tree)}
    def edge_word(a,b):
        edge=next((e for e in edges if frozenset(e)==frozenset((a,b))),None)
        value=generators.get(edge,0)
        return value if edge==(a,b) else -value
    relations=[]
    for a,b,c in complex_.cells(2):
        word=[v for v in (edge_word(a,b),edge_word(b,c),edge_word(c,a)) if v]
        relations.append(word)
    return {'generators':[list(edge) for edge in generators],'relators':relations,
            'free_group_rank_if_graph':len(generators) if complex_.dimension<=1 else None,
            'scope':'Presentation from a maximal tree; no general word-problem or trivial-group decision.'}


def simplicial_map(source,target,vertex_map):
    a,b=SimplicialComplex(source),SimplicialComplex(target)
    mapping={int(k):v for k,v in vertex_map.items()}
    if any(v[0] not in mapping for v in a.cells(0)):raise ValueError('Total vertex map required')
    for simplex in a.simplices:
        image=tuple(sorted(set(mapping[v] for v in simplex),key=repr))
        if image not in b.simplices:return {'simplicial':False,'counterexample':list(simplex)}
    return {'simplicial':True}
