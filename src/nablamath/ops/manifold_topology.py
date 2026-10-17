"""Finite triangulated surfaces: links, boundaries, orientation and genus (57)."""
from collections import defaultdict
from itertools import combinations
from ._area_utils import calculate as _calculate


def manifold_topology(facets):
    if not isinstance(facets,list) or not 1<=len(facets)<=128 or any(not isinstance(face,list) or len(face)!=3 or any(type(v) is not int or v<0 for v in face) or len(set(face))!=3 for face in facets):
        raise ValueError('Require 1–128 nondegenerate finite triangles')
    faces = sorted(set(tuple(sorted(face)) for face in facets));vertices = sorted(set(v for face in faces for v in face))
    if len(vertices)>64:raise ValueError('Surface exceeds its 64-vertex budget')
    edges = defaultdict(list);adjacency = {v:set() for v in vertices}
    for index,face in enumerate(faces):
        cyclic = [(face[0],face[1]),(face[1],face[2]),(face[2],face[0])]
        for a,b in cyclic:
            edge = tuple(sorted((a,b)));edges[edge].append((index,1 if (a,b)==edge else -1))
            adjacency[a].add(b);adjacency[b].add(a)
    manifold = all(len(incident)<=2 for incident in edges.values());links = {}
    for vertex in vertices:
        graph = defaultdict(set)
        for face in faces:
            if vertex in face:
                a,b = [v for v in face if v!=vertex];graph[a].add(b);graph[b].add(a)
        seen = set();stack = [next(iter(graph))]
        while stack:
            v = stack.pop()
            if v not in seen:seen.add(v);stack.extend(graph[v]-seen)
        degrees = [len(row) for row in graph.values()]
        cycle = all(d==2 for d in degrees)
        path = degrees.count(1)==2 and all(d in (1,2) for d in degrees)
        valid = len(seen)==len(graph) and (cycle or path)
        manifold &= valid;links[str(vertex)] = 'circle' if valid and cycle else 'interval' if valid else 'singular'
    orientations = {};orientable = True;conflicts = set()
    neighbors = defaultdict(list)
    for incident in edges.values():
        if len(incident)==2:
            (a,sa),(b,sb) = incident;neighbors[a].append((b,-sa*sb));neighbors[b].append((a,-sa*sb))
    for index in range(len(faces)):
        if index in orientations:continue
        orientations[index] = 1;stack = [index]
        while stack:
            a = stack.pop()
            for b,relative in neighbors[a]:
                expected = orientations[a]*relative
                if b in orientations:
                    if orientations[b]!=expected:orientable = False;conflicts.update((a,b))
                else:orientations[b] = expected;stack.append(b)
    unseen = set(vertices);components = []
    while unseen:
        component = {unseen.pop()};stack = list(component)
        while stack:
            v = stack.pop();new = adjacency[v]&unseen;unseen-=new;component|=new;stack.extend(new)
        component_faces = [face for face in faces if face[0] in component]
        component_edges = [edge for edge in edges if edge[0] in component]
        chi = len(component)-len(component_edges)+len(component_faces)
        closed = all(len(edges[edge])==2 for edge in component_edges)
        locally_orientable = not any(i in conflicts for i,face in enumerate(faces) if face[0] in component)
        components.append({'vertices':sorted(component),'euler_characteristic':chi,'closed':closed,
            'orientable':locally_orientable if manifold else None,
            'orientable_genus':(2-chi)//2 if manifold and closed and locally_orientable else None,
            'nonorientable_crosscaps':2-chi if manifold and closed and not locally_orientable else None})
    return {'vertices':len(vertices),'edges':len(edges),'faces':len(faces),'euler_characteristic':len(vertices)-len(edges)+len(faces),
            'is_surface_with_boundary':bool(manifold),'closed':bool(manifold and all(len(v)==2 for v in edges.values())),
            'orientable':bool(orientable) if manifold else None,'vertex_links':links,'components':components,
            'boundary_edges':[list(edge) for edge,incident in edges.items() if len(incident)==1],
            'face_orientations':[orientations[i] for i in range(len(faces))] if manifold and orientable else None,
            'scope':'Finite triangulated two-manifolds; no arbitrary manifold recognition or high-dimensional classification.'}


def calculate(**arguments):return _calculate('manifold_topology',**arguments)
