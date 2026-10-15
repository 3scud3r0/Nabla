"""Exact modular elimination on CUDA via an optional CuPy RawKernel.

Pivot selection synchronizes with the host; row arithmetic executes on the device.
This favors auditability over speed. No acceleration claim follows from selection.
"""
from __future__ import annotations

_KERNEL = r'''
extern "C" __global__ void eliminate(long long* a, const long long* pivot,
    int rows, int cols, int prow, int pcol, long long prime) {
    int row = blockIdx.x * blockDim.x + threadIdx.x;
    if (row >= rows || row == prow) return;
    long long factor = a[row * cols + pcol];
    for (int col = 0; col < cols; ++col) {
        long long value = (a[row * cols + col] - factor * pivot[col]) % prime;
        a[row * cols + col] = value < 0 ? value + prime : value;
    }
}
'''


class CudaUnavailable(RuntimeError):
    """Requested device execution cannot be provided; no silent fallback."""


class CudaF4Backend:
    name = "cupy-rawkernel-cuda-f4-v1"
    accelerated = True

    def __init__(self):
        try:
            import cupy as cp
            if cp.cuda.runtime.getDeviceCount() < 1:
                raise CudaUnavailable("No CUDA device")
            self.cp = cp
            self.kernel = cp.RawKernel(_KERNEL, "eliminate")
        except (ImportError, RuntimeError) as exc:
            raise CudaUnavailable("CuPy and a working CUDA device are required") from exc

    def modular_rref(self, matrix, prime):
        # Restrict the arithmetic contract before allocating a device buffer.
        from ..cuda_f4_reduction import _is_prime
        if type(prime) is not int or not 2 <= prime <= 32749 or not _is_prime(prime):
            raise ValueError("CUDA F4 requires a prime in [2,32749]")
        if not matrix:
            return [], []
        columns = len(matrix[0])
        if any(len(row) != columns for row in matrix):
            raise ValueError("Rectangular matrix required")
        if len(matrix) * columns > 10_000_000:
            raise MemoryError("CUDA F4 cell budget exceeded")
        if any(type(value) is not int for row in matrix for value in row):
            raise ValueError("Integer entries required")
        if not columns:
            return [[] for _ in matrix], []
        cp = self.cp
        data = cp.asarray([[v % prime for v in row] for row in matrix], dtype=cp.int64)
        pivots, prow = [], 0
        for column in range(columns):
            candidates = cp.asnumpy(cp.flatnonzero(data[prow:, column]))
            if not len(candidates):
                continue
            chosen = prow + int(candidates[0])
            if chosen != prow:
                temporary = data[prow].copy()
                data[prow] = data[chosen]
                data[chosen] = temporary
            inverse = pow(int(data[prow, column].item()), -1, prime)
            data[prow] = (data[prow] * inverse) % prime
            pivot = data[prow].copy()
            self.kernel(((len(matrix) + 127) // 128,), (128,),
                        (data, pivot, cp.int32(len(matrix)), cp.int32(columns),
                         cp.int32(prow), cp.int32(column), cp.int64(prime)))
            pivots.append(column)
            prow += 1
            if prow == len(matrix):
                break
        cp.cuda.get_current_stream().synchronize()
        return cp.asnumpy(data).tolist(), pivots
