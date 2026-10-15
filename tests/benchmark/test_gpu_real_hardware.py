"""Device evidence is skipped rather than simulated when hardware is unavailable."""
import pytest
from nablamath.gpu.cuda_f4_reduction import modular_rref
from nablamath.gpu.profiler import profile_operation


def test_cuda_exact_f4_hardware():
    cp = pytest.importorskip('cupy')
    try:
        if cp.cuda.runtime.getDeviceCount() < 1:
            pytest.skip('No CUDA device')
    except cp.cuda.runtime.CUDARuntimeError:
        pytest.skip('CUDA driver unavailable')
    from nablamath.gpu.kernels.f4_cuda import CudaF4Backend
    backend = CudaF4Backend()
    matrix = [[(i*7+j*3+i*j) % 101 for j in range(12)] for i in range(8)]
    expected = modular_rref(matrix, 101)
    result = modular_rref(matrix, 101, backend=backend)
    assert result.matrix == expected.matrix
    assert result.accelerated
    receipt = profile_operation(lambda: modular_rref(matrix, 101, backend=backend),
                                backend=backend.name, repetitions=3,
                                synchronize=cp.cuda.get_current_stream().synchronize)
    assert receipt.hardware['cuda_devices']


def test_triton_parent_lookup_hardware():
    torch = pytest.importorskip('torch')
    pytest.importorskip('triton')
    if not torch.cuda.is_available():
        pytest.skip('No CUDA device')
    from nablamath.gpu.kernels.egraph_triton import canonical_children_triton
    assert canonical_children_triton([0, 0, 1, 2], [3, 2, 0]) == [0, 0, 0]
