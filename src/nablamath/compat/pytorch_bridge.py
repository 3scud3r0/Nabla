"""Trace trusted PyTorch calls without detaching returned tensors or changing gradients."""
from functools import wraps
import platform
import weakref
from ..calc.receipt import receipt


class TorchTrace:
    """Dispatch-mode interceptor: native tensors and autograd stay untouched.

    Only shapes, strides, dtypes, devices and operation names leave PyTorch.
    No cpu(), numpy(), tolist(), item() or tensor wrapper is used on this path.
    Metadata batches are packaged by the session's bounded background worker.
    """
    def __init__(self, session=None, *, sink=None, batch_size=128, collect=False):
        if type(batch_size) is not int or not 1 <= batch_size <= 4096:
            raise ValueError('batch_size must be between 1 and 4096')
        if type(collect) is not bool or (session is not None and sink is not None):
            raise ValueError('Use a session or a sink, and a boolean collect flag')
        from ..calc.session import CalculationSession
        self._owned = session is None
        self.session = session or CalculationSession(background_receipts=True, receipt_sink=sink)
        self.batch_size, self.collect = batch_size, collect
        self._events, self._receipts, self._identities = [], [], {}
        self._next_id, self.operation_count, self.batch_count = 0, 0, 0
        self.last_receipt = None
        self._active = False

    def _metadata(self, value):
        import torch
        if isinstance(value, torch.Tensor):
            identity = id(value)
            existing = self._identities.get(identity)
            if existing is None or existing[0]() is not value:
                self._next_id += 1
                number = self._next_id
                def release(ref, identity=identity):
                    if self._identities.get(identity, (None,))[0] is ref:
                        self._identities.pop(identity, None)
                self._identities[identity] = (weakref.ref(value, release), number)
            number = self._identities[identity][1]
            return {'tensor_id':number, 'shape':[int(x) for x in value.shape],
                    'dtype':str(value.dtype), 'device':str(value.device),
                    'layout':str(value.layout), 'requires_grad':bool(value.requires_grad),
                    'strides':list(value.stride()) if value.layout == torch.strided else None}
        if isinstance(value, (tuple, list)):
            return [self._metadata(v) for v in value]
        if isinstance(value, dict):
            return {str(k):self._metadata(v) for k,v in value.items()}
        if value is None or type(value) in (bool,int,float,str):
            return value
        # torch.device, dtype, memory_format and symbolic configuration objects.
        return {'configuration_type':type(value).__name__, 'value':str(value)[:256]}

    def _flush_batch(self, *, failed=False):
        if not self._events:
            return
        events = self._events
        import torch
        future = self.session.record_observation('torch.dispatch.batch',{},events,backend='pytorch',
                    metadata={'batch':self.batch_count, 'torch_version':str(torch.__version__),
                              'tensor_contents_hashed':False,'capture':'metadata_only',
                              'execution_failed':failed})
        self._events = []
        self.batch_count += 1
        self.last_receipt = future
        if self.collect:
            self._receipts.append(future)

    def __enter__(self):
        if self._active:
            raise RuntimeError('A TorchTrace cannot be entered twice concurrently')
        import torch
        from torch.utils._python_dispatch import TorchDispatchMode
        trace = self
        class Interceptor(TorchDispatchMode):
            def __torch_dispatch__(self, func, types, args=(), kwargs=None):
                kwargs = kwargs or {}
                inputs = trace._metadata({'args':args,'kwargs':kwargs})
                # Delegation returns the very same native output, including aliasing/views.
                output = func(*args, **kwargs)
                trace._events.append({'operation':str(func),'inputs':inputs,'outputs':trace._metadata(output)})
                trace.operation_count += 1
                if len(trace._events) >= trace.batch_size:
                    trace._flush_batch()
                return output
        self._mode = Interceptor()
        self._mode.__enter__()
        self._active = True
        return self

    def __exit__(self, *exception):
        try:
            self._mode.__exit__(*exception)
            self._flush_batch(failed=exception[0] is not None)
        finally:
            self._active = False
            self._identities.clear()
            if self._owned:
                self.session.close()

    @property
    def receipts(self):
        if not self.collect:
            raise RuntimeError('Use collect=True for an in-memory receipt history, or provide a streaming sink')
        return [future.result() for future in self._receipts]


def from_dlpack(value):
    """Share a DLPack producer's device memory; ownership follows the DLPack protocol."""
    import torch
    return torch.utils.dlpack.from_dlpack(value)


def to_dlpack(tensor):
    import torch
    if not isinstance(tensor, torch.Tensor):
        raise TypeError('Expected a native PyTorch tensor')
    return torch.utils.dlpack.to_dlpack(tensor)


def trace_execution(*, sink):
    """Emit an immutable observation to sink after success, retaining the original result."""
    if not callable(sink):
        raise TypeError('A receipt sink callback is required')

    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            try:
                import torch
            except ImportError as exc:
                raise ImportError('Install nablamath[torch] for PyTorch tracing') from exc

            def snapshot(value):
                if isinstance(value,torch.Tensor):
                    if value.numel() > 100000 or value.is_complex() or value.layout != torch.strided:
                        raise ValueError('Tracing requires bounded dense real tensors')
                    return {'values':value.detach().cpu().tolist(), 'shape':list(value.shape),
                            'dtype':str(value.dtype), 'device':str(value.device),
                            'requires_grad':value.requires_grad}
                if isinstance(value,(tuple,list)):
                    return [snapshot(v) for v in value]
                if isinstance(value,dict) and all(isinstance(k,str) for k in value):
                    return {k:snapshot(v) for k,v in value.items()}
                if value is None or type(value) in (str,int,float,bool):
                    return value
                raise TypeError('Unsupported trace value; pass tensor/JSON inputs explicitly')

            inputs = {'args':snapshot(args),'kwargs':snapshot(kwargs)}
            # Profiling captures executed operators, including dynamic control-flow branches.
            with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU]) as profile:
                result = function(*args, **kwargs)
            record = receipt(function.__module__+'.'+function.__qualname__,inputs,snapshot(result),
                             backend='pytorch',metadata={'torch_version':torch.__version__,
                             'python_version':platform.python_version(),
                             'deterministic_algorithms':torch.are_deterministic_algorithms_enabled(),
                             'operators':[event.name for event in profile.events()][:10000]})
            sink(record)
            return result
        return wrapped
    return decorate
