"""CuPy/PyTorch CUDA dispatch, native outputs and explicit CPU OOM recovery.

The exact CalculationSession catalog stays exact. Accelerated least squares and
ODE results use observation receipts and explicitly identify floating arithmetic.
Native dispatch records metadata by default; readback is an explicit choice.
"""
from dataclasses import dataclass
from concurrent.futures import Future
import math

from ..compiler.backends import BackendUnavailable
from ..calc.receipt import receipt


@dataclass
class DeviceCalculation:
    result: object
    backend: str
    device: str
    audit_receipt: dict | Future
    fallback_reason: str | None = None

    def to_data(self):
        from copy import deepcopy
        data = self.audit_receipt.result() if hasattr(self.audit_receipt,'result') else self.audit_receipt
        return deepcopy(data)


def available_backends():
    result = {'cupy_cuda':False,'torch_cuda':False,'torch_cpu':False,'numpy_cpu':False}
    try:
        import cupy as cp
        result['cupy_cuda'] = cp.cuda.runtime.getDeviceCount() > 0
    except (ImportError,RuntimeError,OSError):
        pass
    try:
        import torch
        result['torch_cuda'] = bool(torch.cuda.is_available())
        result['torch_cpu'] = True
    except (ImportError,RuntimeError,OSError):
        pass
    try:
        import numpy
        result['numpy_cpu'] = True
    except ImportError:
        pass
    return result


class CudaDispatcher:
    def __init__(self, device=0, *, backend='auto', require_cuda=True, allow_cpu_fallback=True, session=None):
        if type(device) is not int or device < 0 or backend not in {'auto','torch','cupy'}:
            raise ValueError('Invalid device/backend')
        if type(require_cuda) is not bool or type(allow_cpu_fallback) is not bool:
            raise ValueError('CUDA/fallback flags must be boolean')
        self.device, self.allow_cpu_fallback = device,allow_cpu_fallback
        self.session = session
        availability = available_backends()
        self.cp = None
        if backend in {'auto','cupy'} and availability['cupy_cuda']:
            import cupy as cp
            if device >= cp.cuda.runtime.getDeviceCount():
                raise ValueError('CUDA device index is out of range')
            self.cp, self.backend, self.platform = cp,'cupy','cuda'
        elif backend in {'auto','torch'} and availability['torch_cuda']:
            import torch
            if device >= torch.cuda.device_count():
                raise ValueError('CUDA device index is out of range')
            self.backend,self.platform = 'torch','cuda'
        elif require_cuda:
            raise BackendUnavailable('No requested CUDA backend/device available; use require_cuda=False for explicit CPU execution')
        elif availability['torch_cpu'] and backend != 'cupy':
            self.backend,self.platform = 'torch','cpu'
        elif availability['numpy_cpu']:
            self.backend,self.platform = 'numpy','cpu'
        else:
            raise BackendUnavailable('CPU fallback requires NumPy or PyTorch')

    @staticmethod
    def _metadata(value):
        if isinstance(value,dict):
            return {k:CudaDispatcher._metadata(v) for k,v in value.items()}
        if isinstance(value,(tuple,list)):
            return [CudaDispatcher._metadata(v) for v in value]
        if hasattr(value,'shape') and hasattr(value,'dtype'):
            return {'shape':list(value.shape),'dtype':str(value.dtype),'device':str(getattr(value,'device','cpu'))}
        return value

    @staticmethod
    def _values(value):
        if isinstance(value,dict):
            return {k:CudaDispatcher._values(v) for k,v in value.items()}
        if isinstance(value,(tuple,list)):
            return [CudaDispatcher._values(v) for v in value]
        module = type(value).__module__.split('.')[0]
        if module == 'torch':
            return value.detach().cpu().tolist()
        if module == 'cupy':
            import cupy as cp
            return cp.asnumpy(value).tolist()
        return value.tolist() if hasattr(value,'tolist') else value

    def _run(self, backend, platform, operation, arguments):
        if backend == 'torch':
            import torch
            xp = torch
            target = f'cuda:{self.device}' if platform == 'cuda' else 'cpu'
            def array(value):
                if isinstance(value,torch.Tensor):
                    if not value.is_floating_point() or value.is_complex():
                        raise ValueError('Native numerical dispatch requires real floating tensors')
                    return value.to(device=target)
                return torch.as_tensor(value,dtype=torch.float64,device=target)
            stack = lambda rows: torch.stack(rows,dim=0)
            context = torch.cuda.device(self.device) if platform == 'cuda' else None
        else:
            if backend == 'cupy':
                import cupy as xp
                context = xp.cuda.Device(self.device)
            else:
                import numpy as xp
                context = None
            array = lambda value: xp.asarray(value,dtype=xp.float64)
            stack = lambda rows: xp.stack(rows,axis=0)
        from contextlib import nullcontext
        with context or nullcontext():
            if operation == 'matmul':
                a,b = array(arguments['left']),array(arguments['right'])
                if a.ndim != 2 or b.ndim != 2 or a.shape[1] != b.shape[0] or a.shape[0]*b.shape[1] > 1000000:
                    raise ValueError('Incompatible or excessive matrix dimensions')
                return a@b
            if operation == 'least_squares':
                a,y = array(arguments['predictors']),array(arguments['response'])
                if a.ndim != 2 or y.ndim != 1 or a.shape[0] != y.shape[0] or a.shape[0]*a.shape[1] > 1000000:
                    raise ValueError('Incompatible least-squares design/response')
                intercept = arguments.get('intercept',True)
                if type(intercept) is not bool:
                    raise ValueError('intercept must be boolean')
                if intercept:
                    ones = array([[1.0]]*a.shape[0])
                    a = xp.cat((ones,a),dim=1) if backend == 'torch' else xp.concatenate((ones,a),axis=1)
                if a.shape[0] <= a.shape[1]:
                    raise ValueError('Positive residual degrees of freedom required')
                if not bool(xp.linalg.matrix_rank(a) == a.shape[1]):
                    raise ValueError('Least-squares design must have full column rank')
                original_a,original_y = a,y
                if arguments.get('weights') is not None:
                    weights = array(arguments['weights'])
                    if weights.shape != y.shape or not bool((weights > 0).all()):
                        raise ValueError('Positive weights matching the response are required')
                    scale = xp.sqrt(weights)
                    a,y = a*scale[:,None],y*scale
                if backend == 'torch':
                    fitted = xp.linalg.lstsq(a,y,driver='gels' if platform == 'cuda' else 'gelsd')
                    coefficients = fitted.solution
                else:
                    coefficients = xp.linalg.lstsq(a,y,rcond=None)[0]
                residuals = original_y-original_a@coefficients
                squares = residuals*residuals
                if arguments.get('weights') is not None:
                    squares = squares*weights
                return {'coefficients':coefficients,'residuals':residuals,
                        'residual_sum_squares':squares.sum()}
            if operation in {'ode','ode_solve'}:
                model = arguments['model']; steps = arguments.get('steps',100)
                rate,duration = arguments.get('rate',1.),arguments.get('duration',1.)
                if type(steps) is not int or not 1 <= steps <= 10000 or model not in {'exponential_decay','harmonic_oscillator'}:
                    raise ValueError('Unsupported ODE model or step budget')
                if any(type(v) not in (int,float) or not math.isfinite(v) or v <= 0 for v in (rate,duration)):
                    raise ValueError('ODE rate and duration must be finite and positive')
                state = array(arguments['initial'])
                dimension = 1 if model == 'exponential_decay' else 2
                size = state.numel() if backend == 'torch' else state.size
                if state.ndim not in (1,2) or state.shape[-1] != dimension or size*(steps+1) > 2000000:
                    raise ValueError('Invalid ODE state shape or trajectory budget')
                dt = duration/steps
                def derivative(value):
                    if model == 'exponential_decay':
                        return -rate*value
                    a,b = value[...,1],-rate*rate*value[...,0]
                    return xp.stack((a,b),dim=-1) if backend == 'torch' else xp.stack((a,b),axis=-1)
                trajectory = [state]
                for _ in range(steps):
                    k1 = derivative(state); k2 = derivative(state+dt*k1/2)
                    k3 = derivative(state+dt*k2/2); k4 = derivative(state+dt*k3)
                    state = state+dt*(k1+2*k2+2*k3+k4)/6
                    trajectory.append(state)
                return {'times':[i*dt for i in range(steps+1)],'states':stack(trajectory),'final':state,'method':'rk4'}
            if operation == 'diffusion':
                ratio,steps = arguments['ratio'],arguments['steps']
                if type(ratio) not in (int,float) or not math.isfinite(ratio) or not 0 <= ratio <= .5 or type(steps) is not int or not 1 <= steps <= 100000:
                    raise ValueError('Unstable diffusion ratio or step budget')
                state = array(arguments['initial'])
                if state.ndim != 1 or not 3 <= len(state) <= 10000 or len(state)*steps > 10000000:
                    raise ValueError('Invalid diffusion grid/budget')
                if bool(state[0] != 0) or bool(state[-1] != 0):
                    raise ValueError('Zero Dirichlet boundaries required')
                for _ in range(steps):
                    middle = state[1:-1]+ratio*(state[:-2]-2*state[1:-1]+state[2:])
                    state = xp.cat((state[:1],middle,state[-1:])) if backend == 'torch' else xp.concatenate((state[:1],middle,state[-1:]))
                return state
            raise ValueError('Unsupported accelerated operation')

    def execute(self, operation, *, capture_values=False, audit_session=None, **arguments):
        contracts = {'matmul':({'left','right'},set()),
                     'least_squares':({'predictors','response'},{'intercept','weights'}),
                     'ode':({'model','initial'},{'steps','rate','duration'}),
                     'ode_solve':({'model','initial'},{'steps','rate','duration'}),
                     'diffusion':({'initial','ratio','steps'},set())}
        if operation not in contracts or type(capture_values) is not bool:
            raise ValueError('Invalid dispatch operation/options')
        required,optional = contracts[operation]
        if not required <= set(arguments) <= required|optional:
            raise ValueError('Dispatch arguments do not match the operation')
        backend,platform = self.backend,self.platform
        # Keep autograd when the caller supplies native torch tensors.
        if any(type(v).__module__.split('.')[0] == 'torch' for v in arguments.values()):
            backend = 'torch'
        oom_types = []
        try:
            import torch
            oom_types.append(torch.OutOfMemoryError)
        except ImportError:
            pass
        try:
            import cupy as cp
            oom_types.append(cp.cuda.memory.OutOfMemoryError)
        except ImportError:
            pass
        fallback = None
        inputs = self._metadata(arguments)
        try:
            result = self._run(backend,platform,operation,arguments)
        except tuple(oom_types) as error:
            if platform != 'cuda' or not self.allow_cpu_fallback:
                raise
            fallback = type(error).__name__+': CUDA allocation failed; retried on CPU'
            if backend == 'torch':
                cpu_arguments = {k:(v.to('cpu') if isinstance(v,torch.Tensor) else v) for k,v in arguments.items()}
                result = self._run('torch','cpu',operation,cpu_arguments)
            else:
                cpu_arguments = {k:self._values(v) for k,v in arguments.items()}
                result = self._run('numpy','cpu',operation,cpu_arguments)
                backend = 'numpy'
            platform = 'cpu'
        output = self._values(result) if capture_values else self._metadata(result)
        audited_inputs = self._values(arguments) if capture_values else inputs
        metadata = {'platform':platform,'device':self.device if platform == 'cuda' else 'cpu',
                                   'fallback_reason':fallback,'tensor_contents_hashed':capture_values,
                                   'capture':'values' if capture_values else 'metadata_only',
                                   'limitations':'Numerical backend observation; not an exact catalog result or formal proof.'}
        session = audit_session if audit_session is not None else self.session
        if session is not None:
            record = session.record_observation('device.'+operation,audited_inputs,output,backend=backend,metadata=metadata)
        else:
            record = receipt('device.'+operation,audited_inputs,output,backend=backend,metadata=metadata)
        return DeviceCalculation(result,backend,f'cuda:{self.device}' if platform == 'cuda' else 'cpu',record,fallback)

    def matmul(self, left, right):
        """Compatibility API returning a full receipt, with explicit host readback."""
        return self.execute('matmul',left=left,right=right,capture_values=True).to_data()

    def diffuse(self, initial, *, ratio, steps):
        return self.execute('diffusion',initial=initial,ratio=ratio,steps=steps,capture_values=True).to_data()
