"""Real CUDA execution through CuPy; no CPU emulation when CUDA is missing."""
import math
from ..compiler.backends import BackendUnavailable
from ..calc.receipt import receipt


def _cupy():
    try:
        import cupy as cp
    except (ImportError, OSError) as exc:
        raise BackendUnavailable('Install nablamath[cuda12] and a working NVIDIA driver') from exc
    try:
        if cp.cuda.runtime.getDeviceCount() < 1:
            raise BackendUnavailable('No CUDA device available')
        return cp
    except (RuntimeError, OSError) as exc:
        raise BackendUnavailable('CUDA runtime or device unavailable') from exc


class CudaDispatcher:
    def __init__(self, device=0):
        cp = _cupy()
        if type(device) is not int or not 0 <= device < cp.cuda.runtime.getDeviceCount():
            raise ValueError('Invalid CUDA device')
        self.cp, self.device = cp, device

    def _array(self, values):
        array = self.cp.asarray(values,dtype=self.cp.float64)
        if not 1 <= array.size <= 1000000 or not bool(self.cp.isfinite(array).all()):
            raise ValueError('Expected bounded finite numeric input')
        return array

    def matmul(self, left, right):
        cp = self.cp
        with cp.cuda.Device(self.device):
            a,b = self._array(left),self._array(right)
            if a.ndim != 2 or b.ndim != 2 or a.shape[1] != b.shape[0] or a.shape[0]*b.shape[1] > 1000000:
                raise ValueError('Incompatible or excessive matrix dimensions')
            result = cp.asnumpy(a@b).tolist()
            return receipt('cuda.matmul',{'left':cp.asnumpy(a).tolist(),'right':cp.asnumpy(b).tolist()},result,
                           backend='cuda',metadata={'device':self.device,'cupy_version':cp.__version__,'dtype':'float64'})

    def diffuse(self, initial, *, ratio, steps):
        """1D FTCS diffusion with fixed zero Dirichlet boundaries, ratio=alpha*dt/dx²."""
        if not math.isfinite(ratio) or not 0 <= ratio <= 0.5 or type(steps) is not int or not 1 <= steps <= 100000:
            raise ValueError('Unstable diffusion ratio or invalid step count')
        cp = self.cp
        with cp.cuda.Device(self.device):
            state = self._array(initial).copy()
            if state.ndim != 1 or not 3 <= len(state) <= 10000 or len(state)*steps > 10000000:
                raise ValueError('Invalid diffusion grid/budget')
            if float(state[0]) != 0 or float(state[-1]) != 0:
                raise ValueError('Zero Dirichlet boundaries required')
            original = cp.asnumpy(state).tolist()
            for _ in range(steps):
                state[1:-1] = state[1:-1]+ratio*(state[:-2]-2*state[1:-1]+state[2:])
            return receipt('cuda.diffusion',{'initial':original,'ratio':ratio,'steps':steps},
                           cp.asnumpy(state).tolist(),backend='cuda',metadata={'device':self.device,'dtype':'float64'})
