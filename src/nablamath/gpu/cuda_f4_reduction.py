"""F4 building block: exact modular row reduction of Macaulay matrices.

The public API accepts an optional backend implementing the same contract.  The
reference path is deterministic CPU code; an accelerator must identify itself in
the returned receipt, preventing silent CPU/GPU attribution errors.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Protocol, Sequence


class ModularRrefBackend(Protocol):
    name: str
    accelerated: bool

    def modular_rref(self, matrix: list[list[int]], prime: int) -> tuple[list[list[int]], list[int]]: ...


@dataclass(frozen=True)
class F4ReductionResult:
    matrix: tuple[tuple[int, ...], ...]
    pivots: tuple[int, ...]
    prime: int
    rank: int
    backend: str
    accelerated: bool
    content_id: str


def _is_prime(value: int) -> bool:
    if value < 2:
        return False
    if value % 2 == 0:
        return value == 2
    divisor = 3
    while divisor * divisor <= value:
        if value % divisor == 0:
            return False
        divisor += 2
    return True


def _cpu_rref(matrix: list[list[int]], prime: int) -> tuple[list[list[int]], list[int]]:
    if not matrix:
        return [], []
    rows, columns = len(matrix), len(matrix[0])
    pivot_row = 0
    pivots: list[int] = []
    for column in range(columns):
        candidate = next((row for row in range(pivot_row, rows)
                          if matrix[row][column] % prime), None)
        if candidate is None:
            continue
        matrix[pivot_row], matrix[candidate] = matrix[candidate], matrix[pivot_row]
        inverse = pow(matrix[pivot_row][column] % prime, -1, prime)
        matrix[pivot_row] = [(value * inverse) % prime for value in matrix[pivot_row]]
        for row in range(rows):
            if row == pivot_row:
                continue
            factor = matrix[row][column] % prime
            if factor:
                matrix[row] = [(value - factor * pivot) % prime
                               for value, pivot in zip(matrix[row], matrix[pivot_row])]
        pivots.append(column)
        pivot_row += 1
        if pivot_row == rows:
            break
    return matrix, pivots


def modular_rref(
    rows: Sequence[Sequence[int]],
    prime: int,
    *,
    backend: ModularRrefBackend | str | None = None,
    cell_limit: int = 10_000_000,
) -> F4ReductionResult:
    """Reduce exactly over ``GF(prime)`` with independently checked device output.

    ``backend=None`` or ``"cpu"`` selects the reference. ``"cuda"`` explicitly
    requests the optional CuPy backend and fails if it is unavailable. A backend
    object remains supported for integrations; selection never implies speedup.
    """
    if type(prime) is not int or not _is_prime(prime):
        raise ValueError("O módulo deve ser primo")
    if type(cell_limit) is not int or cell_limit < 1:
        raise ValueError("cell_limit deve ser positivo")
    matrix = [list(row) for row in rows]
    columns = len(matrix[0]) if matrix else 0
    if any(len(row) != columns for row in matrix):
        raise ValueError("Matriz precisa ser retangular")
    if len(matrix) * columns > cell_limit:
        raise MemoryError("Matriz F4 excede o orçamento de células")
    if any(type(value) is not int for row in matrix for value in row):
        raise ValueError("Exact modular reduction requires integer entries")
    matrix = [[value % prime for value in row] for row in matrix]
    if isinstance(backend, str):
        if backend == "cpu":
            backend = None
        elif backend == "cuda":
            from .kernels.f4_cuda import CudaF4Backend
            backend = CudaF4Backend()
        else:
            raise ValueError("Backend must be cpu, cuda, or a ModularRrefBackend")
    if backend is None:
        reduced, pivots = _cpu_rref(matrix, prime)
        backend_name, accelerated = "cpu-reference", False
    else:
        # A third-party backend may mutate its working input. Preserve the
        # original separately so verification cannot certify a substituted matrix.
        original = [row[:] for row in matrix]
        reduced, pivots = backend.modular_rref([row[:] for row in matrix], prime)
        backend_name, accelerated = backend.name, bool(backend.accelerated)
        if len(reduced) != len(matrix) or any(len(row) != columns for row in reduced):
            raise RuntimeError("Backend devolveu matriz com shape incompatível")
        reduced = [[int(value) % prime for value in row] for row in reduced]
        # Independently verify the claimed RREF instead of trusting a device kernel.
        verified, verified_pivots = _cpu_rref(original, prime)
        if reduced != verified or list(pivots) != verified_pivots:
            raise ArithmeticError("Backend acelerado divergiu da redução modular exata")
    payload = {"matrix": reduced, "pivots": pivots, "prime": prime,
               "backend": backend_name, "accelerated": accelerated}
    content_id = hashlib.sha256(json.dumps(payload, sort_keys=True,
                                           separators=(",", ":")).encode()).hexdigest()
    return F4ReductionResult(tuple(tuple(row) for row in reduced), tuple(pivots), prime,
                             len(pivots), backend_name, accelerated, content_id)


__all__ = ["F4ReductionResult", "ModularRrefBackend", "modular_rref"]
