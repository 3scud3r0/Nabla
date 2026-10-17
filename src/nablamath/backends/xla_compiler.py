"""JAX/XLA JIT for trusted Python callables and existing Nabla compiler IR."""
from ..compiler.backends import compile_jax, jax_devices, BackendUnavailable
from ..calc.receipt import receipt


def compile_ir(program):
    return compile_jax(program, jit=True)


class XLACompiler:
    def __init__(self, *, platform=None):
        try:
            import jax
        except ImportError as exc:
            raise BackendUnavailable('Install nablamath[accelerate] for XLA') from exc
        self.jax = jax
        try:
            self.devices = jax.devices(platform) if platform else jax.devices()
        except RuntimeError as exc:
            raise BackendUnavailable('Requested JAX platform is unavailable') from exc
        if not self.devices:
            raise BackendUnavailable('No XLA devices available')

    def compile(self, function):
        if not callable(function):
            raise TypeError('A trusted callable is required')
        return self.jax.jit(function)

    def execute(self, function, *args):
        import numpy as np
        def snapshot(x):
            array = np.asarray(x)
            if array.size > 1000000 or array.dtype.kind not in 'iuf' or not np.isfinite(array).all():
                raise ValueError('Expected bounded finite real arrays')
            return {'values':array.tolist(),'dtype':str(array.dtype),'shape':list(array.shape)}
        inputs = [snapshot(x) for x in args]
        placed = [self.jax.device_put(x,self.devices[0]) for x in args]
        result = self.compile(function)(*placed)
        result.block_until_ready()
        return receipt('xla.execute',inputs,snapshot(result),backend='xla',metadata={
            'jax_version':self.jax.__version__,'platform':self.devices[0].platform,
            'device':str(self.devices[0]),'x64_enabled':bool(self.jax.config.x64_enabled)})


__all__ = ['XLACompiler','compile_ir','jax_devices']
