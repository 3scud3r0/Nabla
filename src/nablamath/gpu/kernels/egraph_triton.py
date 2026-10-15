"""Optional bounded Triton child lookup, not a complete GPU e-graph.

Inputs are snapshotted once. Linear-time forest validation precedes allocation;
GPU pointer jumping is limited to an explicit supported maximum chain depth.
"""
from itertools import islice

MAX_PARENTS = 100_000
MAX_CHILDREN = 1_000_000
MAX_DEPTH = 1024
MAX_DEVICE_LOOKUPS = 10_000_000


def _snapshot(values, limit, label):
    try:
        result = tuple(islice(iter(values), limit + 1))
    except TypeError as exc:
        raise ValueError(f'{label} must be an integer iterable') from exc
    if len(result) > limit:
        raise ValueError(f'{label} budget exceeded')
    return result


def _prepare(parents, children, *, max_depth):
    if type(max_depth) is not int or not 1 <= max_depth <= MAX_DEPTH:
        raise ValueError('Supported forest depth must be in [1,1024]')
    parents = _snapshot(parents, MAX_PARENTS, 'Parent')
    children = _snapshot(children, MAX_CHILDREN, 'Child')
    count = len(parents)
    if any(type(p) is not int or not 0 <= p < count for p in parents):
        raise ValueError('Parents must index the parent array')
    if any(type(c) is not int or not 0 <= c < count for c in children):
        raise ValueError('Child index outside forest')
    roots, depths = [-1] * count, [0] * count
    # Every unresolved node enters one path once; roots memoize prior traversals.
    for start in range(count):
        if roots[start] != -1:
            continue
        cursor, path, active = start, [], set()
        while roots[cursor] == -1 and parents[cursor] != cursor:
            if cursor in active:
                raise ValueError('Cyclic parent forest')
            active.add(cursor)
            path.append(cursor)
            if len(path) > max_depth:
                raise ValueError('Forest exceeds supported chain depth')
            cursor = parents[cursor]
        if roots[cursor] == -1:
            roots[cursor] = cursor
        root, depth = roots[cursor], depths[cursor]
        for node in reversed(path):
            depth += 1
            if depth > max_depth:
                raise ValueError('Forest exceeds supported chain depth')
            roots[node], depths[node] = root, depth
    return parents, children, roots, max(depths, default=0)


def canonical_children_cpu(parents, children, *, max_depth=MAX_DEPTH):
    """Resolve an integer forest in O(parents+children), under fixed budgets."""
    _, children, roots, _ = _prepare(parents, children, max_depth=max_depth)
    return [roots[child] for child in children]


def canonical_children_triton(parents, children, *, max_depth=MAX_DEPTH):
    """Resolve one immutable validated snapshot on CUDA; no implicit fallback."""
    parents, children, roots, depth = _prepare(parents, children, max_depth=max_depth)
    if len(children) * max(1, depth) > MAX_DEVICE_LOOKUPS:
        raise ValueError('Device pointer lookup work budget exceeded')
    expected = [roots[child] for child in children]
    try:
        import torch
        import triton
        import triton.language as tl
    except ImportError as exc:
        raise RuntimeError('Triton and CUDA-enabled PyTorch are required') from exc
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA device unavailable')
    if not children:
        return []

    @triton.jit
    def lookup(P, C, O, N: tl.constexpr, DEPTH: tl.constexpr, BLOCK: tl.constexpr):
        index = tl.program_id(0) * BLOCK + tl.arange(0, BLOCK)
        mask = index < N
        child = tl.load(C + index, mask=mask, other=0)
        for _ in range(DEPTH):
            child = tl.load(P + child, mask=mask, other=0)
        tl.store(O + index, child, mask=mask)

    parent_tensor = torch.tensor(parents, dtype=torch.int64, device='cuda')
    child_tensor = torch.tensor(children, dtype=torch.int64, device='cuda')
    result = torch.empty_like(child_tensor)
    lookup[(triton.cdiv(len(children), 256),)](
        parent_tensor, child_tensor, result, len(children), depth, 256)
    torch.cuda.synchronize()
    actual = result.cpu().tolist()
    if actual != expected:
        raise ArithmeticError('Device canonicalization differs from CPU oracle')
    return actual
