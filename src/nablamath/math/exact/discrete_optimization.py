"""Exact finite graph theory, optimization and combinatorial certificates.

Algorithms return replayable witnesses such as a minimum cut, matching cover,
spanning-tree edges or assignment permutation. Complexity bounds and graph
models are explicit; negative cycles are rejected instead of hidden.
"""
from __future__ import annotations

from collections import deque
from fractions import Fraction
from functools import lru_cache

from .laboratory import rational


def _vertices(vertices: object, limit: int = 128) -> tuple[str, ...]:
    if not isinstance(vertices, (tuple, list)) or not 1 <= len(vertices) <= limit:
        raise ValueError("Graph vertex count outside configured budget")
    if any(not isinstance(v, str) or not v or len(v) > 80 for v in vertices):
        raise ValueError("Vertex labels must be bounded nonempty strings")
    if len(set(vertices)) != len(vertices):
        raise ValueError("Vertex labels must be distinct")
    return tuple(vertices)


def _directed_edges(
    vertices: tuple[str, ...], edges: object, *, nonnegative: bool = False
) -> tuple[tuple[str, str, Fraction], ...]:
    if not isinstance(edges, (list, tuple)) or len(edges) > 4096:
        raise ValueError("Edge list outside budget")
    universe = set(vertices)
    result, seen = [], set()
    for row in edges:
        if not isinstance(row, (list, tuple)) or len(row) != 3:
            raise ValueError("Weighted edge must have exactly three fields")
        u, v, raw = row
        if not isinstance(u, str) or not isinstance(v, str) or u not in universe or v not in universe:
            raise ValueError("Unknown graph endpoint")
        if (u, v) in seen:
            raise ValueError("Duplicate directed edges are not supported")
        seen.add((u, v))
        weight = rational(raw)
        if nonnegative and weight < 0:
            raise ValueError("This graph operation requires nonnegative weights")
        result.append((u, v, weight))
    return tuple(result)


def bellman_ford(
    vertices: tuple[str, ...], edges: tuple[tuple[object, ...], ...], source: str,
) -> dict:
    """Exact shortest distances under arbitrary edge weights, no reachable -cycle."""
    vertices = _vertices(vertices)
    parsed = _directed_edges(vertices, edges)
    if source not in vertices:
        raise ValueError("Source vertex absent")
    distance: dict[str, Fraction | None] = {v: None for v in vertices}
    predecessor = {v: None for v in vertices}
    distance[source] = Fraction(0)
    for _ in range(len(vertices)-1):
        changed = False
        for u, v, cost in parsed:
            if distance[u] is None:
                continue
            candidate = distance[u] + cost
            if distance[v] is None or candidate < distance[v]:
                distance[v] = candidate
                predecessor[v] = u
                changed = True
        if not changed:
            break
    for u, v, cost in parsed:
        if distance[u] is not None and (distance[v] is None
                                      or distance[u] + cost < distance[v]):
            raise ValueError("Reachable negative-weight cycle")
    return {
        "source": source,
        "distances": {v: str(distance[v]) if distance[v] is not None else None for v in vertices},
        "predecessors": predecessor,
        "certificate": "Bellman-Ford relaxation with no reachable negative cycle",
    }


def floyd_warshall(
    vertices: tuple[str, ...], edges: tuple[tuple[object, ...], ...],
) -> dict:
    """Exact all-pairs shortest distances, rejecting every negative cycle."""
    vertices = _vertices(vertices, 48)
    parsed = _directed_edges(vertices, edges)
    n = len(vertices)
    index = {v: i for i, v in enumerate(vertices)}
    d = [[None] * n for _ in range(n)]
    for i in range(n):
        d[i][i] = Fraction(0)
    for u, v, value in parsed:
        i, j = index[u], index[v]
        if d[i][j] is None or value < d[i][j]:
            d[i][j] = value
    for k in range(n):
        for i in range(n):
            if d[i][k] is None:
                continue
            for j in range(n):
                if d[k][j] is None:
                    continue
                value = d[i][k] + d[k][j]
                if d[i][j] is None or value < d[i][j]:
                    d[i][j] = value
    if any(d[i][i] < 0 for i in range(n)):
        raise ValueError("Negative-weight cycle detected")
    return {
        "vertices": list(vertices),
        "distances": [[str(x) if x is not None else None for x in row] for row in d],
        "certificate": "Floyd-Warshall over exact rational path weights",
    }


def exact_max_flow(
    vertices: tuple[str, ...], edges: tuple[tuple[object, ...], ...],
    source: str, sink: str,
) -> dict:
    """Edmonds–Karp max flow with exact min-cut equality certificate."""
    vertices = _vertices(vertices, 64)
    parsed = _directed_edges(vertices, edges, nonnegative=True)
    if source not in vertices or sink not in vertices or source == sink:
        raise ValueError("Flow requires distinct source and sink")
    if len(parsed) > 1024:
        raise ValueError("Flow edges exceed 1024")
    residual = {u: {} for u in vertices}
    for u, v, capacity in parsed:
        if u == v:
            continue
        residual[u][v] = residual[u].get(v, Fraction(0)) + capacity
        residual[v].setdefault(u, Fraction(0))
    value = Fraction(0)
    augmentations = 0
    while True:
        parent: dict[str, str | None] = {source: None}
        queue = deque([source])
        while queue and sink not in parent:
            u = queue.popleft()
            for v in sorted(residual[u]):
                if v not in parent and residual[u][v] > 0:
                    parent[v] = u
                    queue.append(v)
        if sink not in parent:
            break
        bottleneck = None
        v = sink
        while v != source:
            u = parent[v]
            amount = residual[u][v]
            bottleneck = amount if bottleneck is None else min(bottleneck, amount)
            v = u
        if bottleneck is None or bottleneck <= 0:
            raise ArithmeticError("Residual network invariant violated")
        v = sink
        while v != source:
            u = parent[v]
            residual[u][v] -= bottleneck
            residual[v][u] = residual[v].get(u, Fraction(0)) + bottleneck
            v = u
        value += bottleneck
        augmentations += 1
        if augmentations > len(vertices) * (len(parsed) + 1):
            raise ArithmeticError("Max-flow augmentation budget exceeded")
    reachable = {source}
    queue = deque([source])
    while queue:
        u = queue.popleft()
        for v, remaining in residual[u].items():
            if remaining > 0 and v not in reachable:
                reachable.add(v)
                queue.append(v)
    cut = sum((c for u, v, c in parsed if u in reachable and v not in reachable),
              Fraction(0))
    if sink in reachable or cut != value:
        raise ArithmeticError("Max flow does not equal its candidate min cut")
    return {
        "value": str(value),
        "cut_capacity": str(cut),
        "source_side": sorted(reachable),
        "sink_side": sorted(set(vertices) - reachable),
        "augmentations": augmentations,
        "certificate": "Exact max-flow/min-cut equality",
    }


def bipartite_matching(
    left: tuple[str, ...], right: tuple[str, ...],
    edges: tuple[tuple[str, str], ...],
) -> dict:
    """Maximum cardinality matching with a König minimum vertex cover."""
    left = _vertices(left, 128)
    right = _vertices(right, 128)
    if set(left) & set(right):
        raise ValueError("Bipartite vertex labels must be disjoint")
    if not isinstance(edges, (tuple, list)) or len(edges) > 8192:
        raise ValueError("Matching edge count exceeds budget")
    adj = {u: set() for u in left}
    for pair in edges:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("Matching edge must have two labels")
        u, v = pair
        if u not in adj or v not in right:
            raise ValueError("Matching edge belongs to wrong partition")
        adj[u].add(v)
    ordered = {u: sorted(v) for u, v in adj.items()}
    match_r: dict[str, str] = {}
    def augment(u: str, visited: set[str]) -> bool:
        for v in ordered[u]:
            if v in visited:
                continue
            visited.add(v)
            if v not in match_r or augment(match_r[v], visited):
                match_r[v] = u
                return True
        return False
    for u in left:
        augment(u, set())
    match_l = {u: v for v, u in match_r.items()}
    # König cover via alternating reachability from unmatched left vertices.
    visited_l = {u for u in left if u not in match_l}
    visited_r = set()
    queue = deque(sorted(visited_l))
    while queue:
        u = queue.popleft()
        for v in ordered[u]:
            if match_l.get(u) == v or v in visited_r:
                continue
            visited_r.add(v)
            matched = match_r.get(v)
            if matched is not None and matched not in visited_l:
                visited_l.add(matched)
                queue.append(matched)
    cover_l = set(left) - visited_l
    cover_r = visited_r
    if len(cover_l) + len(cover_r) != len(match_r):
        raise ArithmeticError("König minimum-cover certificate invalid")
    if any(u not in cover_l and v not in cover_r for u in left for v in ordered[u]):
        raise ArithmeticError("König cover does not cover an edge")
    return {
        "cardinality": len(match_r),
        "pairs": [[u, match_l[u]] for u in left if u in match_l],
        "minimum_vertex_cover": {"left": sorted(cover_l), "right": sorted(cover_r)},
        "certificate": "Matching cardinality equals bipartite cover cardinality",
    }


def minimum_spanning_tree(
    vertices: tuple[str, ...], edges: tuple[tuple[object, ...], ...]
) -> dict:
    """Exact Kruskal minimum spanning tree for a connected undirected graph."""
    vertices = _vertices(vertices, 128)
    if not isinstance(edges, (tuple, list)) or len(edges) > 4096:
        raise ValueError("MST edges outside budget")
    universe = set(vertices)
    parsed, seen = [], set()
    for row in edges:
        if not isinstance(row, (tuple, list)) or len(row) != 3:
            raise ValueError("MST edges must be triples")
        u, v, cost = row
        if u not in universe or v not in universe or u == v:
            raise ValueError("Invalid undirected edge")
        pair = tuple(sorted((u, v)))
        if pair in seen:
            raise ValueError("Duplicate undirected edge")
        seen.add(pair)
        parsed.append((rational(cost), pair[0], pair[1]))
    parent = {v: v for v in vertices}
    rank = {v: 0 for v in vertices}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        a, b = find(a), find(b)
        if a == b:
            return False
        if rank[a] < rank[b]:
            a, b = b, a
        parent[b] = a
        if rank[a] == rank[b]:
            rank[a] += 1
        return True
    selected, cost = [], Fraction(0)
    for weight, u, v in sorted(parsed):
        if union(u, v):
            selected.append([u, v, str(weight)])
            cost += weight
            if len(selected) == len(vertices) - 1:
                break
    if len(selected) != len(vertices) - 1:
        raise ValueError("Undirected graph is disconnected")
    return {
        "weight": str(cost), "edges": selected,
        "certificate": "Kruskal cut property for rational edge weights",
    }


def optimal_assignment(costs: tuple[tuple[object, ...], ...]) -> dict:
    """Exact minimum-cost assignment by bitmask dynamic programming (n<=12)."""
    if not isinstance(costs, (tuple, list)) or not 1 <= len(costs) <= 12:
        raise ValueError("Assignment dimension must be 1..12")
    n = len(costs)
    if any(not isinstance(row, (tuple, list)) or len(row) != n for row in costs):
        raise ValueError("Assignment matrix must be square")
    matrix = tuple(tuple(rational(x) for x in row) for row in costs)

    @lru_cache(None)
    def search(mask: int) -> tuple[Fraction, tuple[int, ...]]:
        i = mask.bit_count()
        if i == n:
            return Fraction(0), ()
        best = None
        for j in range(n):
            if not mask & (1 << j):
                next_cost, next_assignment = search(mask | (1 << j))
                candidate = (matrix[i][j] + next_cost, (j,) + next_assignment)
                if best is None or candidate < best:
                    best = candidate
        return best

    cost, assignment = search(0)
    if len(set(assignment)) != n or sum(matrix[i][j] for i, j in enumerate(assignment)) != cost:
        raise ArithmeticError("Assignment permutation certificate invalid")
    return {
        "minimum_cost": str(cost),
        "assignment": list(assignment),
        "certificate": "Exhaustive subset dynamic programming over permutations",
    }


def strongly_connected_components(
    vertices: tuple[str, ...], edges: tuple[tuple[str, str], ...]
) -> tuple[tuple[str, ...], ...]:
    """Tarjan's algorithm with a deterministic ordering of SCCs."""
    vertices = _vertices(vertices)
    if not isinstance(edges, (tuple, list)) or len(edges) > 4096:
        raise ValueError("SCC edge budget exceeded")
    adj = {v: set() for v in vertices}
    for row in edges:
        if not isinstance(row, (tuple, list)) or len(row) != 2:
            raise ValueError("SCC edges must be pairs")
        u, v = row
        if u not in adj or v not in adj:
            raise ValueError("Unknown SCC vertex")
        adj[u].add(v)
    index, stack, on_stack, ids, low, components = 0, [], set(), {}, {}, []
    def visit(v):
        nonlocal index
        ids[v] = low[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)
        for w in sorted(adj[v]):
            if w not in ids:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], ids[w])
        if low[v] == ids[v]:
            group = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                group.append(w)
                if w == v:
                    break
            components.append(tuple(sorted(group)))
    for v in vertices:
        if v not in ids:
            visit(v)
    return tuple(sorted(components))


__all__ = [
    "bellman_ford", "floyd_warshall", "exact_max_flow",
    "bipartite_matching", "minimum_spanning_tree", "optimal_assignment",
    "strongly_connected_components",
]
