"""Trace trusted PyTorch calls without detaching returned tensors or changing gradients."""
from functools import wraps
import platform
from ..calc.receipt import receipt


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
