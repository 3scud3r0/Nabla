"""Amalgamated, bounded frontier-science algorithms for Nabla.

Numerical estimates, SMT decisions and content integrity are separate contracts.
No estimator, hash, finite search or synthetic trace constitutes a universal proof.
All accelerators are optional; importing this file needs only Nabla and Python.
"""
from __future__ import annotations

# SECTION 0: interoperability and optional backends
import asyncio
import hashlib
import importlib
import itertools
import json
import math
import random
import re
import struct
import shutil
import time
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence

from nablamath.calc.session import CalculationSession
from nablamath.calc.receipt import verify_receipt, canonical, fingerprint, receipt
from nablamath.artifacts.bundle import create_bundle
from nablamath.ai.sandbox_verifier import AIVerifier


def _optional(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except (ImportError, OSError, RuntimeError):
        return None


np = _optional('numpy')
torch = _optional('torch')
nn = _optional('torch.nn') if torch is not None else None
z3 = _optional('z3')
pyarrow = _optional('pyarrow')
zarr = _optional('zarr')
scipy = _optional('scipy')
AVAILABLE = {name: module is not None for name, module in
             [('numpy', np), ('torch', torch), ('z3', z3), ('pyarrow', pyarrow),
              ('zarr', zarr), ('scipy', scipy)]}


def _require(module: Any, name: str) -> Any:
    if module is None:
        raise RuntimeError(f'{name}: is_available=False; install nablamath[superintelligence]')
    return module


def _finite(value: Any, name: str = 'value') -> float:
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a finite number')
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f'{name} must be finite')
    return result


def _positive(value: Any, name: str = 'value', *, zero: bool = False) -> float:
    result = _finite(value, name)
    if result < 0 or (result == 0 and not zero):
        raise ValueError(f'{name} must be {"nonnegative" if zero else "positive"}')
    return result


def _budget(value: int, maximum: int, name: str = 'budget') -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f'{name} must be an integer in [1,{maximum}]')
    return value


def _array(value: Any, ndim: int | None = None) -> Any:
    _require(np, 'numpy')
    result = np.asarray(value, dtype=float)
    if result.size == 0 or not np.isfinite(result).all() or (ndim is not None and result.ndim != ndim):
        raise ValueError('Nonempty finite array with declared dimensions required')
    return result


def _unit(value: Any) -> Any:
    value = _array(value, 1)
    if value.shape != (3,):
        raise ValueError('A three-vector is required')
    norm = float(np.linalg.norm(value))
    return value / _positive(norm, 'vector norm')


def _json(value: Any) -> Any:
    if np is not None and isinstance(value, (np.ndarray, np.generic)):
        return _json(value.tolist())
    if torch is not None and isinstance(value, torch.Tensor):
        return _json(value.detach().cpu().tolist())
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, Mapping):
        if not all(isinstance(k, str) for k in value):
            raise ValueError('JSON keys must be strings')
        return {k: _json(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(v) for v in value]
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float:
        return _finite(value)
    raise TypeError(f'Unsupported audit value: {type(value).__name__}')


_Module = nn.Module if nn is not None else object

class DeviceRuntime:
    """Explicit Torch CPU/CUDA placement, reproducible generators and device timing.

    CUDA is an execution requirement when requested: no CPU fallback is allowed.
    Tensor inputs remain on their device. CUDA events measure stream elapsed time;
    synchronizing the terminal event makes an observation receipt complete.
    """
    def __init__(self, device: str = 'auto', seed: int = 0, dtype: str = 'float32') -> None:
        _require(torch, 'torch')
        if type(seed) is not int or not 0 <= seed < 2**63:
            raise ValueError('Seed must lie in [0,2^63)')
        if dtype not in {'float32', 'float64'}:
            raise ValueError('Scientific kernels support float32 or float64')
        if device == 'auto':
            device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
        if device != 'cpu' and not re.fullmatch(r'cuda(?::[0-9]+)?', str(device)):
            raise ValueError('Device must be cpu, auto, cuda or cuda:N')
        self.device = torch.device(device)
        if self.device.type == 'cuda':
            if not torch.cuda.is_available():
                raise RuntimeError('CUDA requested: is_available=False; install a CUDA-enabled Torch build and expose an NVIDIA GPU')
            index = self.device.index or 0
            if index >= torch.cuda.device_count():
                raise RuntimeError('Requested CUDA device does not exist')
            self.device = torch.device('cuda', index)
        self.dtype = getattr(torch, dtype)
        self.seed = seed
        self.generator = torch.Generator(device=self.device).manual_seed(seed)
        self.gpu_seconds: float | None = None
        self._start_event: Any = None
        self._end_event: Any = None

    def tensor(self, value: Any, *, requires_grad: bool = False) -> Any:
        """Place a finite tensor without a host round trip for existing tensors."""
        if isinstance(value, torch.Tensor):
            tensor = value.to(device=self.device, dtype=self.dtype)
        else:
            tensor = torch.as_tensor(value, device=self.device, dtype=self.dtype)
        if tensor.numel() == 0 or not bool(torch.isfinite(tensor).all()):
            raise ValueError('Nonempty finite device tensor required')
        if requires_grad and not tensor.requires_grad:
            tensor = tensor.detach().requires_grad_(True)
        return tensor

    def begin(self) -> None:
        """Start event timing on this CUDA device's current stream."""
        if self.device.type == 'cuda':
            with torch.cuda.device(self.device):
                self._start_event = torch.cuda.Event(enable_timing=True)
                self._end_event = torch.cuda.Event(enable_timing=True)
                self._start_event.record()

    def finish(self) -> float | None:
        """Return measured CUDA seconds, or None when no GPU was used."""
        if self._start_event is not None:
            with torch.cuda.device(self.device):
                self._end_event.record()
                self._end_event.synchronize()
                self.gpu_seconds = _positive(self._start_event.elapsed_time(self._end_event)/1000, zero=True)
        return self.gpu_seconds

    def information(self) -> dict[str, Any]:
        """Report observed hardware, not an inferred acceleration claim."""
        result = {'device': str(self.device), 'dtype': str(self.dtype), 'seed': self.seed,
                  'torch_version': torch.__version__, 'cuda_build': torch.version.cuda,
                  'gpu_seconds': self.gpu_seconds}
        if self.device.type == 'cuda':
            props = torch.cuda.get_device_properties(self.device)
            result.update(gpu_name=props.name, compute_capability=[props.major, props.minor],
                          total_memory_bytes=props.total_memory,
                          peak_allocated_bytes=torch.cuda.max_memory_allocated(self.device))
        return result


def _tensor_finite(value: Any, name: str = 'tensor') -> Any:
    _require(torch, 'torch')
    if not isinstance(value, torch.Tensor) or value.numel() == 0 or not bool(torch.isfinite(value).all()):
        raise ValueError(f'{name} must be a nonempty finite Torch tensor')
    return value


def _native_audit_snapshot(value: Any, *, clone: bool = False) -> tuple[Any, Any]:
    """Freeze native inputs and hash tensor bytes in bounded host transfer chunks.

    A metadata-only observation records shape, dtype and SHA-256 while returning
    the actual result tensor to the caller. Only explicit byte hashing crosses
    the device boundary; numerical execution preserves native tensors/autograd.
    """
    if torch is not None and isinstance(value, torch.Tensor):
        _tensor_finite(value)
        snapshot = value.clone() if clone else value
        raw = snapshot.detach().contiguous().reshape(-1).view(torch.uint8)
        hasher = hashlib.sha256()
        for start in range(0, raw.numel(), 16*1024*1024):
            hasher.update(raw[start:start+16*1024*1024].cpu().numpy().tobytes())
        return snapshot, {'kind': 'native_tensor', 'shape': list(snapshot.shape),
                          'dtype': str(snapshot.dtype), 'device': str(snapshot.device),
                          'sha256': hasher.hexdigest(), 'byte_order': 'native Torch contiguous'}
    if np is not None and isinstance(value, np.ndarray):
        snapshot = value.copy() if clone else value
        _array(snapshot)
        raw = memoryview(np.ascontiguousarray(snapshot)).cast('B'); hasher = hashlib.sha256()
        for start in range(0, len(raw), 16*1024*1024):
            hasher.update(raw[start:start+16*1024*1024])
        return snapshot, {'kind': 'native_array', 'shape': list(snapshot.shape),
                          'dtype': str(snapshot.dtype), 'sha256': hasher.hexdigest()}
    if isinstance(value, Mapping):
        if any(not isinstance(k, str) for k in value):
            raise ValueError('Audit mapping keys must be strings')
        snapshots, ledgers = {}, {}
        for key, child in value.items():
            snapshots[key], ledgers[key] = _native_audit_snapshot(child, clone=clone)
        return snapshots, ledgers
    if isinstance(value, (list, tuple)):
        pairs = [_native_audit_snapshot(child, clone=clone) for child in value]
        return [p[0] for p in pairs], [p[1] for p in pairs]
    canonical_value = _json(value)
    return canonical_value, canonical_value


# SECTION 1: Fourier operators, DeepONet and conservation auditing
def _stencil_prepare(values: Any, spacing: float, axis: int, radius: int,
                     boundary: str, derivative: int) -> tuple[Any, float]:
    """Construct one halo for an unrolled stencil; preserve Torch autograd.

    Periodic halos wrap, zero halos impose a zero exterior, and reflect halos
    implement an even extension about the endpoint samples (zero normal slope).
    """
    spacing = _positive(spacing, 'grid spacing')
    denominator = _positive(spacing**derivative, 'spacing power')
    is_tensor = torch is not None and isinstance(values, torch.Tensor)
    values = _tensor_finite(values) if is_tensor else _array(values)
    if not -values.ndim <= axis < values.ndim or values.shape[axis] <= radius:
        raise ValueError('Stencil axis is missing or grid is smaller than its radius')
    if boundary == 'periodic':
        return values, 1/denominator
    size = values.shape[axis]
    if is_tensor:
        indices = torch.arange(-radius, size+radius, device=values.device)
        if boundary == 'reflect':
            period = 2*(size-1)
            folded = indices.remainder(period)
            indices = torch.minimum(folded, period-folded)
            halo = values.index_select(axis, indices)
        elif boundary == 'zero':
            valid = (indices >= 0) & (indices < size)
            halo = values.index_select(axis, indices.clamp(0, size-1))
            shape = [1]*values.ndim; shape[axis] = len(indices)
            halo = halo*valid.reshape(shape)
        else:
            raise ValueError('Unknown stencil boundary')
    else:
        pads = [(0, 0)]*values.ndim; pads[axis] = (radius, radius)
        halo = np.pad(values, pads, mode='reflect' if boundary == 'reflect' else 'constant')
    return halo, 1/denominator


def _stencil_shift(halo: Any, offset: int, axis: int, radius: int, boundary: str) -> Any:
    if boundary == 'periodic':
        return torch.roll(halo, -offset, axis) if torch is not None and isinstance(halo, torch.Tensor) else np.roll(halo, -offset, axis)
    slices = [slice(None)]*halo.ndim
    size = halo.shape[axis]-2*radius
    slices[axis] = slice(radius+offset, radius+offset+size)
    return halo[tuple(slices)]



class GPUStencilBank:
    """Exact-coefficient unrolled finite differences on CPU, NumPy and CUDA.

    Central derivative orders 1..4 and accuracy orders 2..20 are specialized
    over the last four axes and periodic/zero/reflect boundaries. Every kernel
    uses rational moment-matched coefficients, with no host tensor conversion.
    The generated source is embedded below; kernel metadata is inspectable.
    """
    @staticmethod
    def derivative(values: Any, spacing: float = 1, *, derivative: int = 1,
                   accuracy: int = 4, axis: int = -1, boundary: str = 'periodic') -> Any:
        key = (derivative, accuracy, axis, boundary)
        function = STENCIL_KERNELS.get(key)
        if function is None:
            raise ValueError('Unsupported derivative/accuracy/axis/boundary specialization')
        return function(values, spacing)

    @classmethod
    def laplacian(cls, values: Any, spacing: Sequence[float], accuracy: int = 4,
                  boundary: str = 'periodic') -> Any:
        if not 1 <= len(spacing) <= 4:
            raise ValueError('Laplacian requires one to four spacings')
        result = sum(cls.derivative(values, h, derivative=2, accuracy=accuracy,
                                    axis=-len(spacing)+i, boundary=boundary) for i, h in enumerate(spacing))
        return _tensor_finite(result) if torch is not None and isinstance(result, torch.Tensor) else _array(result)

    @classmethod
    def divergence(cls, components: Sequence[Any], spacing: Sequence[float],
                   accuracy: int = 4, boundary: str = 'periodic') -> Any:
        if len(components) != len(spacing) or not components:
            raise ValueError('Divergence components must match spacings')
        return sum(cls.derivative(v, h, accuracy=accuracy, axis=-len(spacing)+i,
                                  boundary=boundary) for i, (v, h) in enumerate(zip(components, spacing)))

    @classmethod
    def curl(cls, velocity: Sequence[Any], spacing: Sequence[float], accuracy: int = 4) -> Any:
        if len(velocity) != 3 or len(spacing) != 3:
            raise ValueError('Curl requires three velocity components and spacings')
        derivative = lambda i, j: cls.derivative(velocity[i], spacing[j], accuracy=accuracy, axis=j-3)
        return (derivative(2, 1)-derivative(1, 2), derivative(0, 2)-derivative(2, 0), derivative(1, 0)-derivative(0, 1))

# BEGIN EXACT GENERATED STENCIL SPECIALIZATIONS
# Rational Vandermonde moments are matched through degree 2*radius.
# Functions below are executable numerical kernels, not samples or filler.
STENCIL_KERNELS: dict[tuple[int, int, int, str], Callable[..., Any]] = {}
STENCIL_MOMENTS: dict[tuple[int, int], tuple[tuple[int, int, int], ...]] = {}

STENCIL_MOMENTS[1, 2] = (
    (-1, -1, 2),
    (0, 0, 1),
    (1, 1, 2),
)

def _fd_d1_a2_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 2, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 1, 'periodic', 1)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -1, -4, 1, 'periodic') +
        (1 / 2)
        * _stencil_shift(halo, 1, -4, 1, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 2, -4, 'periodic'] = _fd_d1_a2_axis4_periodic


def _fd_d1_a2_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 2, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 1, 'zero', 1)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -1, -4, 1, 'zero') +
        (1 / 2)
        * _stencil_shift(halo, 1, -4, 1, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 2, -4, 'zero'] = _fd_d1_a2_axis4_zero


def _fd_d1_a2_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 2, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 1, 'reflect', 1)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -1, -4, 1, 'reflect') +
        (1 / 2)
        * _stencil_shift(halo, 1, -4, 1, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 2, -4, 'reflect'] = _fd_d1_a2_axis4_reflect


def _fd_d1_a2_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 2, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 1, 'periodic', 1)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -1, -3, 1, 'periodic') +
        (1 / 2)
        * _stencil_shift(halo, 1, -3, 1, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 2, -3, 'periodic'] = _fd_d1_a2_axis3_periodic


def _fd_d1_a2_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 2, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 1, 'zero', 1)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -1, -3, 1, 'zero') +
        (1 / 2)
        * _stencil_shift(halo, 1, -3, 1, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 2, -3, 'zero'] = _fd_d1_a2_axis3_zero


def _fd_d1_a2_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 2, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 1, 'reflect', 1)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -1, -3, 1, 'reflect') +
        (1 / 2)
        * _stencil_shift(halo, 1, -3, 1, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 2, -3, 'reflect'] = _fd_d1_a2_axis3_reflect


def _fd_d1_a2_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 2, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 1, 'periodic', 1)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -1, -2, 1, 'periodic') +
        (1 / 2)
        * _stencil_shift(halo, 1, -2, 1, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 2, -2, 'periodic'] = _fd_d1_a2_axis2_periodic


def _fd_d1_a2_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 2, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 1, 'zero', 1)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -1, -2, 1, 'zero') +
        (1 / 2)
        * _stencil_shift(halo, 1, -2, 1, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 2, -2, 'zero'] = _fd_d1_a2_axis2_zero


def _fd_d1_a2_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 2, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 1, 'reflect', 1)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -1, -2, 1, 'reflect') +
        (1 / 2)
        * _stencil_shift(halo, 1, -2, 1, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 2, -2, 'reflect'] = _fd_d1_a2_axis2_reflect


def _fd_d1_a2_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 2, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 1, 'periodic', 1)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -1, -1, 1, 'periodic') +
        (1 / 2)
        * _stencil_shift(halo, 1, -1, 1, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 2, -1, 'periodic'] = _fd_d1_a2_axis1_periodic


def _fd_d1_a2_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 2, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 1, 'zero', 1)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -1, -1, 1, 'zero') +
        (1 / 2)
        * _stencil_shift(halo, 1, -1, 1, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 2, -1, 'zero'] = _fd_d1_a2_axis1_zero


def _fd_d1_a2_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 2, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 1, 'reflect', 1)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -1, -1, 1, 'reflect') +
        (1 / 2)
        * _stencil_shift(halo, 1, -1, 1, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 2, -1, 'reflect'] = _fd_d1_a2_axis1_reflect


STENCIL_MOMENTS[1, 4] = (
    (-2, 1, 12),
    (-1, -2, 3),
    (0, 0, 1),
    (1, 2, 3),
    (2, -1, 12),
)

def _fd_d1_a4_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 4, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 2, 'periodic', 1)
    result = (
        (1 / 12)
        * _stencil_shift(halo, -2, -4, 2, 'periodic') +
        (-2 / 3)
        * _stencil_shift(halo, -1, -4, 2, 'periodic') +
        (2 / 3)
        * _stencil_shift(halo, 1, -4, 2, 'periodic') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -4, 2, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 4, -4, 'periodic'] = _fd_d1_a4_axis4_periodic


def _fd_d1_a4_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 4, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 2, 'zero', 1)
    result = (
        (1 / 12)
        * _stencil_shift(halo, -2, -4, 2, 'zero') +
        (-2 / 3)
        * _stencil_shift(halo, -1, -4, 2, 'zero') +
        (2 / 3)
        * _stencil_shift(halo, 1, -4, 2, 'zero') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -4, 2, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 4, -4, 'zero'] = _fd_d1_a4_axis4_zero


def _fd_d1_a4_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 4, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 2, 'reflect', 1)
    result = (
        (1 / 12)
        * _stencil_shift(halo, -2, -4, 2, 'reflect') +
        (-2 / 3)
        * _stencil_shift(halo, -1, -4, 2, 'reflect') +
        (2 / 3)
        * _stencil_shift(halo, 1, -4, 2, 'reflect') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -4, 2, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 4, -4, 'reflect'] = _fd_d1_a4_axis4_reflect


def _fd_d1_a4_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 4, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 2, 'periodic', 1)
    result = (
        (1 / 12)
        * _stencil_shift(halo, -2, -3, 2, 'periodic') +
        (-2 / 3)
        * _stencil_shift(halo, -1, -3, 2, 'periodic') +
        (2 / 3)
        * _stencil_shift(halo, 1, -3, 2, 'periodic') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -3, 2, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 4, -3, 'periodic'] = _fd_d1_a4_axis3_periodic


def _fd_d1_a4_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 4, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 2, 'zero', 1)
    result = (
        (1 / 12)
        * _stencil_shift(halo, -2, -3, 2, 'zero') +
        (-2 / 3)
        * _stencil_shift(halo, -1, -3, 2, 'zero') +
        (2 / 3)
        * _stencil_shift(halo, 1, -3, 2, 'zero') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -3, 2, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 4, -3, 'zero'] = _fd_d1_a4_axis3_zero


def _fd_d1_a4_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 4, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 2, 'reflect', 1)
    result = (
        (1 / 12)
        * _stencil_shift(halo, -2, -3, 2, 'reflect') +
        (-2 / 3)
        * _stencil_shift(halo, -1, -3, 2, 'reflect') +
        (2 / 3)
        * _stencil_shift(halo, 1, -3, 2, 'reflect') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -3, 2, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 4, -3, 'reflect'] = _fd_d1_a4_axis3_reflect


def _fd_d1_a4_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 4, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 2, 'periodic', 1)
    result = (
        (1 / 12)
        * _stencil_shift(halo, -2, -2, 2, 'periodic') +
        (-2 / 3)
        * _stencil_shift(halo, -1, -2, 2, 'periodic') +
        (2 / 3)
        * _stencil_shift(halo, 1, -2, 2, 'periodic') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -2, 2, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 4, -2, 'periodic'] = _fd_d1_a4_axis2_periodic


def _fd_d1_a4_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 4, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 2, 'zero', 1)
    result = (
        (1 / 12)
        * _stencil_shift(halo, -2, -2, 2, 'zero') +
        (-2 / 3)
        * _stencil_shift(halo, -1, -2, 2, 'zero') +
        (2 / 3)
        * _stencil_shift(halo, 1, -2, 2, 'zero') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -2, 2, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 4, -2, 'zero'] = _fd_d1_a4_axis2_zero


def _fd_d1_a4_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 4, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 2, 'reflect', 1)
    result = (
        (1 / 12)
        * _stencil_shift(halo, -2, -2, 2, 'reflect') +
        (-2 / 3)
        * _stencil_shift(halo, -1, -2, 2, 'reflect') +
        (2 / 3)
        * _stencil_shift(halo, 1, -2, 2, 'reflect') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -2, 2, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 4, -2, 'reflect'] = _fd_d1_a4_axis2_reflect


def _fd_d1_a4_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 4, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 2, 'periodic', 1)
    result = (
        (1 / 12)
        * _stencil_shift(halo, -2, -1, 2, 'periodic') +
        (-2 / 3)
        * _stencil_shift(halo, -1, -1, 2, 'periodic') +
        (2 / 3)
        * _stencil_shift(halo, 1, -1, 2, 'periodic') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -1, 2, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 4, -1, 'periodic'] = _fd_d1_a4_axis1_periodic


def _fd_d1_a4_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 4, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 2, 'zero', 1)
    result = (
        (1 / 12)
        * _stencil_shift(halo, -2, -1, 2, 'zero') +
        (-2 / 3)
        * _stencil_shift(halo, -1, -1, 2, 'zero') +
        (2 / 3)
        * _stencil_shift(halo, 1, -1, 2, 'zero') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -1, 2, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 4, -1, 'zero'] = _fd_d1_a4_axis1_zero


def _fd_d1_a4_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 4, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 2, 'reflect', 1)
    result = (
        (1 / 12)
        * _stencil_shift(halo, -2, -1, 2, 'reflect') +
        (-2 / 3)
        * _stencil_shift(halo, -1, -1, 2, 'reflect') +
        (2 / 3)
        * _stencil_shift(halo, 1, -1, 2, 'reflect') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -1, 2, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 4, -1, 'reflect'] = _fd_d1_a4_axis1_reflect


STENCIL_MOMENTS[1, 6] = (
    (-3, -1, 60),
    (-2, 3, 20),
    (-1, -3, 4),
    (0, 0, 1),
    (1, 3, 4),
    (2, -3, 20),
    (3, 1, 60),
)

def _fd_d1_a6_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 6, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 3, 'periodic', 1)
    result = (
        (-1 / 60)
        * _stencil_shift(halo, -3, -4, 3, 'periodic') +
        (3 / 20)
        * _stencil_shift(halo, -2, -4, 3, 'periodic') +
        (-3 / 4)
        * _stencil_shift(halo, -1, -4, 3, 'periodic') +
        (3 / 4)
        * _stencil_shift(halo, 1, -4, 3, 'periodic') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -4, 3, 'periodic') +
        (1 / 60)
        * _stencil_shift(halo, 3, -4, 3, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 6, -4, 'periodic'] = _fd_d1_a6_axis4_periodic


def _fd_d1_a6_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 6, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 3, 'zero', 1)
    result = (
        (-1 / 60)
        * _stencil_shift(halo, -3, -4, 3, 'zero') +
        (3 / 20)
        * _stencil_shift(halo, -2, -4, 3, 'zero') +
        (-3 / 4)
        * _stencil_shift(halo, -1, -4, 3, 'zero') +
        (3 / 4)
        * _stencil_shift(halo, 1, -4, 3, 'zero') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -4, 3, 'zero') +
        (1 / 60)
        * _stencil_shift(halo, 3, -4, 3, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 6, -4, 'zero'] = _fd_d1_a6_axis4_zero


def _fd_d1_a6_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 6, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 3, 'reflect', 1)
    result = (
        (-1 / 60)
        * _stencil_shift(halo, -3, -4, 3, 'reflect') +
        (3 / 20)
        * _stencil_shift(halo, -2, -4, 3, 'reflect') +
        (-3 / 4)
        * _stencil_shift(halo, -1, -4, 3, 'reflect') +
        (3 / 4)
        * _stencil_shift(halo, 1, -4, 3, 'reflect') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -4, 3, 'reflect') +
        (1 / 60)
        * _stencil_shift(halo, 3, -4, 3, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 6, -4, 'reflect'] = _fd_d1_a6_axis4_reflect


def _fd_d1_a6_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 6, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 3, 'periodic', 1)
    result = (
        (-1 / 60)
        * _stencil_shift(halo, -3, -3, 3, 'periodic') +
        (3 / 20)
        * _stencil_shift(halo, -2, -3, 3, 'periodic') +
        (-3 / 4)
        * _stencil_shift(halo, -1, -3, 3, 'periodic') +
        (3 / 4)
        * _stencil_shift(halo, 1, -3, 3, 'periodic') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -3, 3, 'periodic') +
        (1 / 60)
        * _stencil_shift(halo, 3, -3, 3, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 6, -3, 'periodic'] = _fd_d1_a6_axis3_periodic


def _fd_d1_a6_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 6, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 3, 'zero', 1)
    result = (
        (-1 / 60)
        * _stencil_shift(halo, -3, -3, 3, 'zero') +
        (3 / 20)
        * _stencil_shift(halo, -2, -3, 3, 'zero') +
        (-3 / 4)
        * _stencil_shift(halo, -1, -3, 3, 'zero') +
        (3 / 4)
        * _stencil_shift(halo, 1, -3, 3, 'zero') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -3, 3, 'zero') +
        (1 / 60)
        * _stencil_shift(halo, 3, -3, 3, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 6, -3, 'zero'] = _fd_d1_a6_axis3_zero


def _fd_d1_a6_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 6, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 3, 'reflect', 1)
    result = (
        (-1 / 60)
        * _stencil_shift(halo, -3, -3, 3, 'reflect') +
        (3 / 20)
        * _stencil_shift(halo, -2, -3, 3, 'reflect') +
        (-3 / 4)
        * _stencil_shift(halo, -1, -3, 3, 'reflect') +
        (3 / 4)
        * _stencil_shift(halo, 1, -3, 3, 'reflect') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -3, 3, 'reflect') +
        (1 / 60)
        * _stencil_shift(halo, 3, -3, 3, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 6, -3, 'reflect'] = _fd_d1_a6_axis3_reflect


def _fd_d1_a6_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 6, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 3, 'periodic', 1)
    result = (
        (-1 / 60)
        * _stencil_shift(halo, -3, -2, 3, 'periodic') +
        (3 / 20)
        * _stencil_shift(halo, -2, -2, 3, 'periodic') +
        (-3 / 4)
        * _stencil_shift(halo, -1, -2, 3, 'periodic') +
        (3 / 4)
        * _stencil_shift(halo, 1, -2, 3, 'periodic') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -2, 3, 'periodic') +
        (1 / 60)
        * _stencil_shift(halo, 3, -2, 3, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 6, -2, 'periodic'] = _fd_d1_a6_axis2_periodic


def _fd_d1_a6_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 6, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 3, 'zero', 1)
    result = (
        (-1 / 60)
        * _stencil_shift(halo, -3, -2, 3, 'zero') +
        (3 / 20)
        * _stencil_shift(halo, -2, -2, 3, 'zero') +
        (-3 / 4)
        * _stencil_shift(halo, -1, -2, 3, 'zero') +
        (3 / 4)
        * _stencil_shift(halo, 1, -2, 3, 'zero') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -2, 3, 'zero') +
        (1 / 60)
        * _stencil_shift(halo, 3, -2, 3, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 6, -2, 'zero'] = _fd_d1_a6_axis2_zero


def _fd_d1_a6_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 6, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 3, 'reflect', 1)
    result = (
        (-1 / 60)
        * _stencil_shift(halo, -3, -2, 3, 'reflect') +
        (3 / 20)
        * _stencil_shift(halo, -2, -2, 3, 'reflect') +
        (-3 / 4)
        * _stencil_shift(halo, -1, -2, 3, 'reflect') +
        (3 / 4)
        * _stencil_shift(halo, 1, -2, 3, 'reflect') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -2, 3, 'reflect') +
        (1 / 60)
        * _stencil_shift(halo, 3, -2, 3, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 6, -2, 'reflect'] = _fd_d1_a6_axis2_reflect


def _fd_d1_a6_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 6, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 3, 'periodic', 1)
    result = (
        (-1 / 60)
        * _stencil_shift(halo, -3, -1, 3, 'periodic') +
        (3 / 20)
        * _stencil_shift(halo, -2, -1, 3, 'periodic') +
        (-3 / 4)
        * _stencil_shift(halo, -1, -1, 3, 'periodic') +
        (3 / 4)
        * _stencil_shift(halo, 1, -1, 3, 'periodic') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -1, 3, 'periodic') +
        (1 / 60)
        * _stencil_shift(halo, 3, -1, 3, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 6, -1, 'periodic'] = _fd_d1_a6_axis1_periodic


def _fd_d1_a6_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 6, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 3, 'zero', 1)
    result = (
        (-1 / 60)
        * _stencil_shift(halo, -3, -1, 3, 'zero') +
        (3 / 20)
        * _stencil_shift(halo, -2, -1, 3, 'zero') +
        (-3 / 4)
        * _stencil_shift(halo, -1, -1, 3, 'zero') +
        (3 / 4)
        * _stencil_shift(halo, 1, -1, 3, 'zero') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -1, 3, 'zero') +
        (1 / 60)
        * _stencil_shift(halo, 3, -1, 3, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 6, -1, 'zero'] = _fd_d1_a6_axis1_zero


def _fd_d1_a6_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 6, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 3, 'reflect', 1)
    result = (
        (-1 / 60)
        * _stencil_shift(halo, -3, -1, 3, 'reflect') +
        (3 / 20)
        * _stencil_shift(halo, -2, -1, 3, 'reflect') +
        (-3 / 4)
        * _stencil_shift(halo, -1, -1, 3, 'reflect') +
        (3 / 4)
        * _stencil_shift(halo, 1, -1, 3, 'reflect') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -1, 3, 'reflect') +
        (1 / 60)
        * _stencil_shift(halo, 3, -1, 3, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 6, -1, 'reflect'] = _fd_d1_a6_axis1_reflect


STENCIL_MOMENTS[1, 8] = (
    (-4, 1, 280),
    (-3, -4, 105),
    (-2, 1, 5),
    (-1, -4, 5),
    (0, 0, 1),
    (1, 4, 5),
    (2, -1, 5),
    (3, 4, 105),
    (4, -1, 280),
)

def _fd_d1_a8_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 8, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 4, 'periodic', 1)
    result = (
        (1 / 280)
        * _stencil_shift(halo, -4, -4, 4, 'periodic') +
        (-4 / 105)
        * _stencil_shift(halo, -3, -4, 4, 'periodic') +
        (1 / 5)
        * _stencil_shift(halo, -2, -4, 4, 'periodic') +
        (-4 / 5)
        * _stencil_shift(halo, -1, -4, 4, 'periodic') +
        (4 / 5)
        * _stencil_shift(halo, 1, -4, 4, 'periodic') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -4, 4, 'periodic') +
        (4 / 105)
        * _stencil_shift(halo, 3, -4, 4, 'periodic') +
        (-1 / 280)
        * _stencil_shift(halo, 4, -4, 4, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 8, -4, 'periodic'] = _fd_d1_a8_axis4_periodic


def _fd_d1_a8_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 8, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 4, 'zero', 1)
    result = (
        (1 / 280)
        * _stencil_shift(halo, -4, -4, 4, 'zero') +
        (-4 / 105)
        * _stencil_shift(halo, -3, -4, 4, 'zero') +
        (1 / 5)
        * _stencil_shift(halo, -2, -4, 4, 'zero') +
        (-4 / 5)
        * _stencil_shift(halo, -1, -4, 4, 'zero') +
        (4 / 5)
        * _stencil_shift(halo, 1, -4, 4, 'zero') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -4, 4, 'zero') +
        (4 / 105)
        * _stencil_shift(halo, 3, -4, 4, 'zero') +
        (-1 / 280)
        * _stencil_shift(halo, 4, -4, 4, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 8, -4, 'zero'] = _fd_d1_a8_axis4_zero


def _fd_d1_a8_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 8, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 4, 'reflect', 1)
    result = (
        (1 / 280)
        * _stencil_shift(halo, -4, -4, 4, 'reflect') +
        (-4 / 105)
        * _stencil_shift(halo, -3, -4, 4, 'reflect') +
        (1 / 5)
        * _stencil_shift(halo, -2, -4, 4, 'reflect') +
        (-4 / 5)
        * _stencil_shift(halo, -1, -4, 4, 'reflect') +
        (4 / 5)
        * _stencil_shift(halo, 1, -4, 4, 'reflect') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -4, 4, 'reflect') +
        (4 / 105)
        * _stencil_shift(halo, 3, -4, 4, 'reflect') +
        (-1 / 280)
        * _stencil_shift(halo, 4, -4, 4, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 8, -4, 'reflect'] = _fd_d1_a8_axis4_reflect


def _fd_d1_a8_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 8, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 4, 'periodic', 1)
    result = (
        (1 / 280)
        * _stencil_shift(halo, -4, -3, 4, 'periodic') +
        (-4 / 105)
        * _stencil_shift(halo, -3, -3, 4, 'periodic') +
        (1 / 5)
        * _stencil_shift(halo, -2, -3, 4, 'periodic') +
        (-4 / 5)
        * _stencil_shift(halo, -1, -3, 4, 'periodic') +
        (4 / 5)
        * _stencil_shift(halo, 1, -3, 4, 'periodic') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -3, 4, 'periodic') +
        (4 / 105)
        * _stencil_shift(halo, 3, -3, 4, 'periodic') +
        (-1 / 280)
        * _stencil_shift(halo, 4, -3, 4, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 8, -3, 'periodic'] = _fd_d1_a8_axis3_periodic


def _fd_d1_a8_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 8, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 4, 'zero', 1)
    result = (
        (1 / 280)
        * _stencil_shift(halo, -4, -3, 4, 'zero') +
        (-4 / 105)
        * _stencil_shift(halo, -3, -3, 4, 'zero') +
        (1 / 5)
        * _stencil_shift(halo, -2, -3, 4, 'zero') +
        (-4 / 5)
        * _stencil_shift(halo, -1, -3, 4, 'zero') +
        (4 / 5)
        * _stencil_shift(halo, 1, -3, 4, 'zero') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -3, 4, 'zero') +
        (4 / 105)
        * _stencil_shift(halo, 3, -3, 4, 'zero') +
        (-1 / 280)
        * _stencil_shift(halo, 4, -3, 4, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 8, -3, 'zero'] = _fd_d1_a8_axis3_zero


def _fd_d1_a8_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 8, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 4, 'reflect', 1)
    result = (
        (1 / 280)
        * _stencil_shift(halo, -4, -3, 4, 'reflect') +
        (-4 / 105)
        * _stencil_shift(halo, -3, -3, 4, 'reflect') +
        (1 / 5)
        * _stencil_shift(halo, -2, -3, 4, 'reflect') +
        (-4 / 5)
        * _stencil_shift(halo, -1, -3, 4, 'reflect') +
        (4 / 5)
        * _stencil_shift(halo, 1, -3, 4, 'reflect') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -3, 4, 'reflect') +
        (4 / 105)
        * _stencil_shift(halo, 3, -3, 4, 'reflect') +
        (-1 / 280)
        * _stencil_shift(halo, 4, -3, 4, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 8, -3, 'reflect'] = _fd_d1_a8_axis3_reflect


def _fd_d1_a8_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 8, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 4, 'periodic', 1)
    result = (
        (1 / 280)
        * _stencil_shift(halo, -4, -2, 4, 'periodic') +
        (-4 / 105)
        * _stencil_shift(halo, -3, -2, 4, 'periodic') +
        (1 / 5)
        * _stencil_shift(halo, -2, -2, 4, 'periodic') +
        (-4 / 5)
        * _stencil_shift(halo, -1, -2, 4, 'periodic') +
        (4 / 5)
        * _stencil_shift(halo, 1, -2, 4, 'periodic') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -2, 4, 'periodic') +
        (4 / 105)
        * _stencil_shift(halo, 3, -2, 4, 'periodic') +
        (-1 / 280)
        * _stencil_shift(halo, 4, -2, 4, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 8, -2, 'periodic'] = _fd_d1_a8_axis2_periodic


def _fd_d1_a8_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 8, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 4, 'zero', 1)
    result = (
        (1 / 280)
        * _stencil_shift(halo, -4, -2, 4, 'zero') +
        (-4 / 105)
        * _stencil_shift(halo, -3, -2, 4, 'zero') +
        (1 / 5)
        * _stencil_shift(halo, -2, -2, 4, 'zero') +
        (-4 / 5)
        * _stencil_shift(halo, -1, -2, 4, 'zero') +
        (4 / 5)
        * _stencil_shift(halo, 1, -2, 4, 'zero') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -2, 4, 'zero') +
        (4 / 105)
        * _stencil_shift(halo, 3, -2, 4, 'zero') +
        (-1 / 280)
        * _stencil_shift(halo, 4, -2, 4, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 8, -2, 'zero'] = _fd_d1_a8_axis2_zero


def _fd_d1_a8_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 8, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 4, 'reflect', 1)
    result = (
        (1 / 280)
        * _stencil_shift(halo, -4, -2, 4, 'reflect') +
        (-4 / 105)
        * _stencil_shift(halo, -3, -2, 4, 'reflect') +
        (1 / 5)
        * _stencil_shift(halo, -2, -2, 4, 'reflect') +
        (-4 / 5)
        * _stencil_shift(halo, -1, -2, 4, 'reflect') +
        (4 / 5)
        * _stencil_shift(halo, 1, -2, 4, 'reflect') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -2, 4, 'reflect') +
        (4 / 105)
        * _stencil_shift(halo, 3, -2, 4, 'reflect') +
        (-1 / 280)
        * _stencil_shift(halo, 4, -2, 4, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 8, -2, 'reflect'] = _fd_d1_a8_axis2_reflect


def _fd_d1_a8_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 8, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 4, 'periodic', 1)
    result = (
        (1 / 280)
        * _stencil_shift(halo, -4, -1, 4, 'periodic') +
        (-4 / 105)
        * _stencil_shift(halo, -3, -1, 4, 'periodic') +
        (1 / 5)
        * _stencil_shift(halo, -2, -1, 4, 'periodic') +
        (-4 / 5)
        * _stencil_shift(halo, -1, -1, 4, 'periodic') +
        (4 / 5)
        * _stencil_shift(halo, 1, -1, 4, 'periodic') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -1, 4, 'periodic') +
        (4 / 105)
        * _stencil_shift(halo, 3, -1, 4, 'periodic') +
        (-1 / 280)
        * _stencil_shift(halo, 4, -1, 4, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 8, -1, 'periodic'] = _fd_d1_a8_axis1_periodic


def _fd_d1_a8_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 8, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 4, 'zero', 1)
    result = (
        (1 / 280)
        * _stencil_shift(halo, -4, -1, 4, 'zero') +
        (-4 / 105)
        * _stencil_shift(halo, -3, -1, 4, 'zero') +
        (1 / 5)
        * _stencil_shift(halo, -2, -1, 4, 'zero') +
        (-4 / 5)
        * _stencil_shift(halo, -1, -1, 4, 'zero') +
        (4 / 5)
        * _stencil_shift(halo, 1, -1, 4, 'zero') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -1, 4, 'zero') +
        (4 / 105)
        * _stencil_shift(halo, 3, -1, 4, 'zero') +
        (-1 / 280)
        * _stencil_shift(halo, 4, -1, 4, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 8, -1, 'zero'] = _fd_d1_a8_axis1_zero


def _fd_d1_a8_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 8, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 4, 'reflect', 1)
    result = (
        (1 / 280)
        * _stencil_shift(halo, -4, -1, 4, 'reflect') +
        (-4 / 105)
        * _stencil_shift(halo, -3, -1, 4, 'reflect') +
        (1 / 5)
        * _stencil_shift(halo, -2, -1, 4, 'reflect') +
        (-4 / 5)
        * _stencil_shift(halo, -1, -1, 4, 'reflect') +
        (4 / 5)
        * _stencil_shift(halo, 1, -1, 4, 'reflect') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -1, 4, 'reflect') +
        (4 / 105)
        * _stencil_shift(halo, 3, -1, 4, 'reflect') +
        (-1 / 280)
        * _stencil_shift(halo, 4, -1, 4, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 8, -1, 'reflect'] = _fd_d1_a8_axis1_reflect


STENCIL_MOMENTS[1, 10] = (
    (-5, -1, 1260),
    (-4, 5, 504),
    (-3, -5, 84),
    (-2, 5, 21),
    (-1, -5, 6),
    (0, 0, 1),
    (1, 5, 6),
    (2, -5, 21),
    (3, 5, 84),
    (4, -5, 504),
    (5, 1, 1260),
)

def _fd_d1_a10_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 10, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 5, 'periodic', 1)
    result = (
        (-1 / 1260)
        * _stencil_shift(halo, -5, -4, 5, 'periodic') +
        (5 / 504)
        * _stencil_shift(halo, -4, -4, 5, 'periodic') +
        (-5 / 84)
        * _stencil_shift(halo, -3, -4, 5, 'periodic') +
        (5 / 21)
        * _stencil_shift(halo, -2, -4, 5, 'periodic') +
        (-5 / 6)
        * _stencil_shift(halo, -1, -4, 5, 'periodic') +
        (5 / 6)
        * _stencil_shift(halo, 1, -4, 5, 'periodic') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -4, 5, 'periodic') +
        (5 / 84)
        * _stencil_shift(halo, 3, -4, 5, 'periodic') +
        (-5 / 504)
        * _stencil_shift(halo, 4, -4, 5, 'periodic') +
        (1 / 1260)
        * _stencil_shift(halo, 5, -4, 5, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 10, -4, 'periodic'] = _fd_d1_a10_axis4_periodic


def _fd_d1_a10_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 10, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 5, 'zero', 1)
    result = (
        (-1 / 1260)
        * _stencil_shift(halo, -5, -4, 5, 'zero') +
        (5 / 504)
        * _stencil_shift(halo, -4, -4, 5, 'zero') +
        (-5 / 84)
        * _stencil_shift(halo, -3, -4, 5, 'zero') +
        (5 / 21)
        * _stencil_shift(halo, -2, -4, 5, 'zero') +
        (-5 / 6)
        * _stencil_shift(halo, -1, -4, 5, 'zero') +
        (5 / 6)
        * _stencil_shift(halo, 1, -4, 5, 'zero') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -4, 5, 'zero') +
        (5 / 84)
        * _stencil_shift(halo, 3, -4, 5, 'zero') +
        (-5 / 504)
        * _stencil_shift(halo, 4, -4, 5, 'zero') +
        (1 / 1260)
        * _stencil_shift(halo, 5, -4, 5, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 10, -4, 'zero'] = _fd_d1_a10_axis4_zero


def _fd_d1_a10_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 10, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 5, 'reflect', 1)
    result = (
        (-1 / 1260)
        * _stencil_shift(halo, -5, -4, 5, 'reflect') +
        (5 / 504)
        * _stencil_shift(halo, -4, -4, 5, 'reflect') +
        (-5 / 84)
        * _stencil_shift(halo, -3, -4, 5, 'reflect') +
        (5 / 21)
        * _stencil_shift(halo, -2, -4, 5, 'reflect') +
        (-5 / 6)
        * _stencil_shift(halo, -1, -4, 5, 'reflect') +
        (5 / 6)
        * _stencil_shift(halo, 1, -4, 5, 'reflect') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -4, 5, 'reflect') +
        (5 / 84)
        * _stencil_shift(halo, 3, -4, 5, 'reflect') +
        (-5 / 504)
        * _stencil_shift(halo, 4, -4, 5, 'reflect') +
        (1 / 1260)
        * _stencil_shift(halo, 5, -4, 5, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 10, -4, 'reflect'] = _fd_d1_a10_axis4_reflect


def _fd_d1_a10_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 10, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 5, 'periodic', 1)
    result = (
        (-1 / 1260)
        * _stencil_shift(halo, -5, -3, 5, 'periodic') +
        (5 / 504)
        * _stencil_shift(halo, -4, -3, 5, 'periodic') +
        (-5 / 84)
        * _stencil_shift(halo, -3, -3, 5, 'periodic') +
        (5 / 21)
        * _stencil_shift(halo, -2, -3, 5, 'periodic') +
        (-5 / 6)
        * _stencil_shift(halo, -1, -3, 5, 'periodic') +
        (5 / 6)
        * _stencil_shift(halo, 1, -3, 5, 'periodic') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -3, 5, 'periodic') +
        (5 / 84)
        * _stencil_shift(halo, 3, -3, 5, 'periodic') +
        (-5 / 504)
        * _stencil_shift(halo, 4, -3, 5, 'periodic') +
        (1 / 1260)
        * _stencil_shift(halo, 5, -3, 5, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 10, -3, 'periodic'] = _fd_d1_a10_axis3_periodic


def _fd_d1_a10_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 10, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 5, 'zero', 1)
    result = (
        (-1 / 1260)
        * _stencil_shift(halo, -5, -3, 5, 'zero') +
        (5 / 504)
        * _stencil_shift(halo, -4, -3, 5, 'zero') +
        (-5 / 84)
        * _stencil_shift(halo, -3, -3, 5, 'zero') +
        (5 / 21)
        * _stencil_shift(halo, -2, -3, 5, 'zero') +
        (-5 / 6)
        * _stencil_shift(halo, -1, -3, 5, 'zero') +
        (5 / 6)
        * _stencil_shift(halo, 1, -3, 5, 'zero') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -3, 5, 'zero') +
        (5 / 84)
        * _stencil_shift(halo, 3, -3, 5, 'zero') +
        (-5 / 504)
        * _stencil_shift(halo, 4, -3, 5, 'zero') +
        (1 / 1260)
        * _stencil_shift(halo, 5, -3, 5, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 10, -3, 'zero'] = _fd_d1_a10_axis3_zero


def _fd_d1_a10_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 10, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 5, 'reflect', 1)
    result = (
        (-1 / 1260)
        * _stencil_shift(halo, -5, -3, 5, 'reflect') +
        (5 / 504)
        * _stencil_shift(halo, -4, -3, 5, 'reflect') +
        (-5 / 84)
        * _stencil_shift(halo, -3, -3, 5, 'reflect') +
        (5 / 21)
        * _stencil_shift(halo, -2, -3, 5, 'reflect') +
        (-5 / 6)
        * _stencil_shift(halo, -1, -3, 5, 'reflect') +
        (5 / 6)
        * _stencil_shift(halo, 1, -3, 5, 'reflect') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -3, 5, 'reflect') +
        (5 / 84)
        * _stencil_shift(halo, 3, -3, 5, 'reflect') +
        (-5 / 504)
        * _stencil_shift(halo, 4, -3, 5, 'reflect') +
        (1 / 1260)
        * _stencil_shift(halo, 5, -3, 5, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 10, -3, 'reflect'] = _fd_d1_a10_axis3_reflect


def _fd_d1_a10_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 10, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 5, 'periodic', 1)
    result = (
        (-1 / 1260)
        * _stencil_shift(halo, -5, -2, 5, 'periodic') +
        (5 / 504)
        * _stencil_shift(halo, -4, -2, 5, 'periodic') +
        (-5 / 84)
        * _stencil_shift(halo, -3, -2, 5, 'periodic') +
        (5 / 21)
        * _stencil_shift(halo, -2, -2, 5, 'periodic') +
        (-5 / 6)
        * _stencil_shift(halo, -1, -2, 5, 'periodic') +
        (5 / 6)
        * _stencil_shift(halo, 1, -2, 5, 'periodic') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -2, 5, 'periodic') +
        (5 / 84)
        * _stencil_shift(halo, 3, -2, 5, 'periodic') +
        (-5 / 504)
        * _stencil_shift(halo, 4, -2, 5, 'periodic') +
        (1 / 1260)
        * _stencil_shift(halo, 5, -2, 5, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 10, -2, 'periodic'] = _fd_d1_a10_axis2_periodic


def _fd_d1_a10_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 10, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 5, 'zero', 1)
    result = (
        (-1 / 1260)
        * _stencil_shift(halo, -5, -2, 5, 'zero') +
        (5 / 504)
        * _stencil_shift(halo, -4, -2, 5, 'zero') +
        (-5 / 84)
        * _stencil_shift(halo, -3, -2, 5, 'zero') +
        (5 / 21)
        * _stencil_shift(halo, -2, -2, 5, 'zero') +
        (-5 / 6)
        * _stencil_shift(halo, -1, -2, 5, 'zero') +
        (5 / 6)
        * _stencil_shift(halo, 1, -2, 5, 'zero') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -2, 5, 'zero') +
        (5 / 84)
        * _stencil_shift(halo, 3, -2, 5, 'zero') +
        (-5 / 504)
        * _stencil_shift(halo, 4, -2, 5, 'zero') +
        (1 / 1260)
        * _stencil_shift(halo, 5, -2, 5, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 10, -2, 'zero'] = _fd_d1_a10_axis2_zero


def _fd_d1_a10_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 10, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 5, 'reflect', 1)
    result = (
        (-1 / 1260)
        * _stencil_shift(halo, -5, -2, 5, 'reflect') +
        (5 / 504)
        * _stencil_shift(halo, -4, -2, 5, 'reflect') +
        (-5 / 84)
        * _stencil_shift(halo, -3, -2, 5, 'reflect') +
        (5 / 21)
        * _stencil_shift(halo, -2, -2, 5, 'reflect') +
        (-5 / 6)
        * _stencil_shift(halo, -1, -2, 5, 'reflect') +
        (5 / 6)
        * _stencil_shift(halo, 1, -2, 5, 'reflect') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -2, 5, 'reflect') +
        (5 / 84)
        * _stencil_shift(halo, 3, -2, 5, 'reflect') +
        (-5 / 504)
        * _stencil_shift(halo, 4, -2, 5, 'reflect') +
        (1 / 1260)
        * _stencil_shift(halo, 5, -2, 5, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 10, -2, 'reflect'] = _fd_d1_a10_axis2_reflect


def _fd_d1_a10_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 10, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 5, 'periodic', 1)
    result = (
        (-1 / 1260)
        * _stencil_shift(halo, -5, -1, 5, 'periodic') +
        (5 / 504)
        * _stencil_shift(halo, -4, -1, 5, 'periodic') +
        (-5 / 84)
        * _stencil_shift(halo, -3, -1, 5, 'periodic') +
        (5 / 21)
        * _stencil_shift(halo, -2, -1, 5, 'periodic') +
        (-5 / 6)
        * _stencil_shift(halo, -1, -1, 5, 'periodic') +
        (5 / 6)
        * _stencil_shift(halo, 1, -1, 5, 'periodic') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -1, 5, 'periodic') +
        (5 / 84)
        * _stencil_shift(halo, 3, -1, 5, 'periodic') +
        (-5 / 504)
        * _stencil_shift(halo, 4, -1, 5, 'periodic') +
        (1 / 1260)
        * _stencil_shift(halo, 5, -1, 5, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 10, -1, 'periodic'] = _fd_d1_a10_axis1_periodic


def _fd_d1_a10_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 10, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 5, 'zero', 1)
    result = (
        (-1 / 1260)
        * _stencil_shift(halo, -5, -1, 5, 'zero') +
        (5 / 504)
        * _stencil_shift(halo, -4, -1, 5, 'zero') +
        (-5 / 84)
        * _stencil_shift(halo, -3, -1, 5, 'zero') +
        (5 / 21)
        * _stencil_shift(halo, -2, -1, 5, 'zero') +
        (-5 / 6)
        * _stencil_shift(halo, -1, -1, 5, 'zero') +
        (5 / 6)
        * _stencil_shift(halo, 1, -1, 5, 'zero') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -1, 5, 'zero') +
        (5 / 84)
        * _stencil_shift(halo, 3, -1, 5, 'zero') +
        (-5 / 504)
        * _stencil_shift(halo, 4, -1, 5, 'zero') +
        (1 / 1260)
        * _stencil_shift(halo, 5, -1, 5, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 10, -1, 'zero'] = _fd_d1_a10_axis1_zero


def _fd_d1_a10_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 10, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 5, 'reflect', 1)
    result = (
        (-1 / 1260)
        * _stencil_shift(halo, -5, -1, 5, 'reflect') +
        (5 / 504)
        * _stencil_shift(halo, -4, -1, 5, 'reflect') +
        (-5 / 84)
        * _stencil_shift(halo, -3, -1, 5, 'reflect') +
        (5 / 21)
        * _stencil_shift(halo, -2, -1, 5, 'reflect') +
        (-5 / 6)
        * _stencil_shift(halo, -1, -1, 5, 'reflect') +
        (5 / 6)
        * _stencil_shift(halo, 1, -1, 5, 'reflect') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -1, 5, 'reflect') +
        (5 / 84)
        * _stencil_shift(halo, 3, -1, 5, 'reflect') +
        (-5 / 504)
        * _stencil_shift(halo, 4, -1, 5, 'reflect') +
        (1 / 1260)
        * _stencil_shift(halo, 5, -1, 5, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 10, -1, 'reflect'] = _fd_d1_a10_axis1_reflect


STENCIL_MOMENTS[1, 12] = (
    (-6, 1, 5544),
    (-5, -1, 385),
    (-4, 1, 56),
    (-3, -5, 63),
    (-2, 15, 56),
    (-1, -6, 7),
    (0, 0, 1),
    (1, 6, 7),
    (2, -15, 56),
    (3, 5, 63),
    (4, -1, 56),
    (5, 1, 385),
    (6, -1, 5544),
)

def _fd_d1_a12_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 12, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 6, 'periodic', 1)
    result = (
        (1 / 5544)
        * _stencil_shift(halo, -6, -4, 6, 'periodic') +
        (-1 / 385)
        * _stencil_shift(halo, -5, -4, 6, 'periodic') +
        (1 / 56)
        * _stencil_shift(halo, -4, -4, 6, 'periodic') +
        (-5 / 63)
        * _stencil_shift(halo, -3, -4, 6, 'periodic') +
        (15 / 56)
        * _stencil_shift(halo, -2, -4, 6, 'periodic') +
        (-6 / 7)
        * _stencil_shift(halo, -1, -4, 6, 'periodic') +
        (6 / 7)
        * _stencil_shift(halo, 1, -4, 6, 'periodic') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -4, 6, 'periodic') +
        (5 / 63)
        * _stencil_shift(halo, 3, -4, 6, 'periodic') +
        (-1 / 56)
        * _stencil_shift(halo, 4, -4, 6, 'periodic') +
        (1 / 385)
        * _stencil_shift(halo, 5, -4, 6, 'periodic') +
        (-1 / 5544)
        * _stencil_shift(halo, 6, -4, 6, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 12, -4, 'periodic'] = _fd_d1_a12_axis4_periodic


def _fd_d1_a12_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 12, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 6, 'zero', 1)
    result = (
        (1 / 5544)
        * _stencil_shift(halo, -6, -4, 6, 'zero') +
        (-1 / 385)
        * _stencil_shift(halo, -5, -4, 6, 'zero') +
        (1 / 56)
        * _stencil_shift(halo, -4, -4, 6, 'zero') +
        (-5 / 63)
        * _stencil_shift(halo, -3, -4, 6, 'zero') +
        (15 / 56)
        * _stencil_shift(halo, -2, -4, 6, 'zero') +
        (-6 / 7)
        * _stencil_shift(halo, -1, -4, 6, 'zero') +
        (6 / 7)
        * _stencil_shift(halo, 1, -4, 6, 'zero') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -4, 6, 'zero') +
        (5 / 63)
        * _stencil_shift(halo, 3, -4, 6, 'zero') +
        (-1 / 56)
        * _stencil_shift(halo, 4, -4, 6, 'zero') +
        (1 / 385)
        * _stencil_shift(halo, 5, -4, 6, 'zero') +
        (-1 / 5544)
        * _stencil_shift(halo, 6, -4, 6, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 12, -4, 'zero'] = _fd_d1_a12_axis4_zero


def _fd_d1_a12_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 12, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 6, 'reflect', 1)
    result = (
        (1 / 5544)
        * _stencil_shift(halo, -6, -4, 6, 'reflect') +
        (-1 / 385)
        * _stencil_shift(halo, -5, -4, 6, 'reflect') +
        (1 / 56)
        * _stencil_shift(halo, -4, -4, 6, 'reflect') +
        (-5 / 63)
        * _stencil_shift(halo, -3, -4, 6, 'reflect') +
        (15 / 56)
        * _stencil_shift(halo, -2, -4, 6, 'reflect') +
        (-6 / 7)
        * _stencil_shift(halo, -1, -4, 6, 'reflect') +
        (6 / 7)
        * _stencil_shift(halo, 1, -4, 6, 'reflect') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -4, 6, 'reflect') +
        (5 / 63)
        * _stencil_shift(halo, 3, -4, 6, 'reflect') +
        (-1 / 56)
        * _stencil_shift(halo, 4, -4, 6, 'reflect') +
        (1 / 385)
        * _stencil_shift(halo, 5, -4, 6, 'reflect') +
        (-1 / 5544)
        * _stencil_shift(halo, 6, -4, 6, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 12, -4, 'reflect'] = _fd_d1_a12_axis4_reflect


def _fd_d1_a12_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 12, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 6, 'periodic', 1)
    result = (
        (1 / 5544)
        * _stencil_shift(halo, -6, -3, 6, 'periodic') +
        (-1 / 385)
        * _stencil_shift(halo, -5, -3, 6, 'periodic') +
        (1 / 56)
        * _stencil_shift(halo, -4, -3, 6, 'periodic') +
        (-5 / 63)
        * _stencil_shift(halo, -3, -3, 6, 'periodic') +
        (15 / 56)
        * _stencil_shift(halo, -2, -3, 6, 'periodic') +
        (-6 / 7)
        * _stencil_shift(halo, -1, -3, 6, 'periodic') +
        (6 / 7)
        * _stencil_shift(halo, 1, -3, 6, 'periodic') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -3, 6, 'periodic') +
        (5 / 63)
        * _stencil_shift(halo, 3, -3, 6, 'periodic') +
        (-1 / 56)
        * _stencil_shift(halo, 4, -3, 6, 'periodic') +
        (1 / 385)
        * _stencil_shift(halo, 5, -3, 6, 'periodic') +
        (-1 / 5544)
        * _stencil_shift(halo, 6, -3, 6, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 12, -3, 'periodic'] = _fd_d1_a12_axis3_periodic


def _fd_d1_a12_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 12, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 6, 'zero', 1)
    result = (
        (1 / 5544)
        * _stencil_shift(halo, -6, -3, 6, 'zero') +
        (-1 / 385)
        * _stencil_shift(halo, -5, -3, 6, 'zero') +
        (1 / 56)
        * _stencil_shift(halo, -4, -3, 6, 'zero') +
        (-5 / 63)
        * _stencil_shift(halo, -3, -3, 6, 'zero') +
        (15 / 56)
        * _stencil_shift(halo, -2, -3, 6, 'zero') +
        (-6 / 7)
        * _stencil_shift(halo, -1, -3, 6, 'zero') +
        (6 / 7)
        * _stencil_shift(halo, 1, -3, 6, 'zero') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -3, 6, 'zero') +
        (5 / 63)
        * _stencil_shift(halo, 3, -3, 6, 'zero') +
        (-1 / 56)
        * _stencil_shift(halo, 4, -3, 6, 'zero') +
        (1 / 385)
        * _stencil_shift(halo, 5, -3, 6, 'zero') +
        (-1 / 5544)
        * _stencil_shift(halo, 6, -3, 6, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 12, -3, 'zero'] = _fd_d1_a12_axis3_zero


def _fd_d1_a12_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 12, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 6, 'reflect', 1)
    result = (
        (1 / 5544)
        * _stencil_shift(halo, -6, -3, 6, 'reflect') +
        (-1 / 385)
        * _stencil_shift(halo, -5, -3, 6, 'reflect') +
        (1 / 56)
        * _stencil_shift(halo, -4, -3, 6, 'reflect') +
        (-5 / 63)
        * _stencil_shift(halo, -3, -3, 6, 'reflect') +
        (15 / 56)
        * _stencil_shift(halo, -2, -3, 6, 'reflect') +
        (-6 / 7)
        * _stencil_shift(halo, -1, -3, 6, 'reflect') +
        (6 / 7)
        * _stencil_shift(halo, 1, -3, 6, 'reflect') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -3, 6, 'reflect') +
        (5 / 63)
        * _stencil_shift(halo, 3, -3, 6, 'reflect') +
        (-1 / 56)
        * _stencil_shift(halo, 4, -3, 6, 'reflect') +
        (1 / 385)
        * _stencil_shift(halo, 5, -3, 6, 'reflect') +
        (-1 / 5544)
        * _stencil_shift(halo, 6, -3, 6, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 12, -3, 'reflect'] = _fd_d1_a12_axis3_reflect


def _fd_d1_a12_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 12, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 6, 'periodic', 1)
    result = (
        (1 / 5544)
        * _stencil_shift(halo, -6, -2, 6, 'periodic') +
        (-1 / 385)
        * _stencil_shift(halo, -5, -2, 6, 'periodic') +
        (1 / 56)
        * _stencil_shift(halo, -4, -2, 6, 'periodic') +
        (-5 / 63)
        * _stencil_shift(halo, -3, -2, 6, 'periodic') +
        (15 / 56)
        * _stencil_shift(halo, -2, -2, 6, 'periodic') +
        (-6 / 7)
        * _stencil_shift(halo, -1, -2, 6, 'periodic') +
        (6 / 7)
        * _stencil_shift(halo, 1, -2, 6, 'periodic') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -2, 6, 'periodic') +
        (5 / 63)
        * _stencil_shift(halo, 3, -2, 6, 'periodic') +
        (-1 / 56)
        * _stencil_shift(halo, 4, -2, 6, 'periodic') +
        (1 / 385)
        * _stencil_shift(halo, 5, -2, 6, 'periodic') +
        (-1 / 5544)
        * _stencil_shift(halo, 6, -2, 6, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 12, -2, 'periodic'] = _fd_d1_a12_axis2_periodic


def _fd_d1_a12_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 12, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 6, 'zero', 1)
    result = (
        (1 / 5544)
        * _stencil_shift(halo, -6, -2, 6, 'zero') +
        (-1 / 385)
        * _stencil_shift(halo, -5, -2, 6, 'zero') +
        (1 / 56)
        * _stencil_shift(halo, -4, -2, 6, 'zero') +
        (-5 / 63)
        * _stencil_shift(halo, -3, -2, 6, 'zero') +
        (15 / 56)
        * _stencil_shift(halo, -2, -2, 6, 'zero') +
        (-6 / 7)
        * _stencil_shift(halo, -1, -2, 6, 'zero') +
        (6 / 7)
        * _stencil_shift(halo, 1, -2, 6, 'zero') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -2, 6, 'zero') +
        (5 / 63)
        * _stencil_shift(halo, 3, -2, 6, 'zero') +
        (-1 / 56)
        * _stencil_shift(halo, 4, -2, 6, 'zero') +
        (1 / 385)
        * _stencil_shift(halo, 5, -2, 6, 'zero') +
        (-1 / 5544)
        * _stencil_shift(halo, 6, -2, 6, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 12, -2, 'zero'] = _fd_d1_a12_axis2_zero


def _fd_d1_a12_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 12, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 6, 'reflect', 1)
    result = (
        (1 / 5544)
        * _stencil_shift(halo, -6, -2, 6, 'reflect') +
        (-1 / 385)
        * _stencil_shift(halo, -5, -2, 6, 'reflect') +
        (1 / 56)
        * _stencil_shift(halo, -4, -2, 6, 'reflect') +
        (-5 / 63)
        * _stencil_shift(halo, -3, -2, 6, 'reflect') +
        (15 / 56)
        * _stencil_shift(halo, -2, -2, 6, 'reflect') +
        (-6 / 7)
        * _stencil_shift(halo, -1, -2, 6, 'reflect') +
        (6 / 7)
        * _stencil_shift(halo, 1, -2, 6, 'reflect') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -2, 6, 'reflect') +
        (5 / 63)
        * _stencil_shift(halo, 3, -2, 6, 'reflect') +
        (-1 / 56)
        * _stencil_shift(halo, 4, -2, 6, 'reflect') +
        (1 / 385)
        * _stencil_shift(halo, 5, -2, 6, 'reflect') +
        (-1 / 5544)
        * _stencil_shift(halo, 6, -2, 6, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 12, -2, 'reflect'] = _fd_d1_a12_axis2_reflect


def _fd_d1_a12_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 12, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 6, 'periodic', 1)
    result = (
        (1 / 5544)
        * _stencil_shift(halo, -6, -1, 6, 'periodic') +
        (-1 / 385)
        * _stencil_shift(halo, -5, -1, 6, 'periodic') +
        (1 / 56)
        * _stencil_shift(halo, -4, -1, 6, 'periodic') +
        (-5 / 63)
        * _stencil_shift(halo, -3, -1, 6, 'periodic') +
        (15 / 56)
        * _stencil_shift(halo, -2, -1, 6, 'periodic') +
        (-6 / 7)
        * _stencil_shift(halo, -1, -1, 6, 'periodic') +
        (6 / 7)
        * _stencil_shift(halo, 1, -1, 6, 'periodic') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -1, 6, 'periodic') +
        (5 / 63)
        * _stencil_shift(halo, 3, -1, 6, 'periodic') +
        (-1 / 56)
        * _stencil_shift(halo, 4, -1, 6, 'periodic') +
        (1 / 385)
        * _stencil_shift(halo, 5, -1, 6, 'periodic') +
        (-1 / 5544)
        * _stencil_shift(halo, 6, -1, 6, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 12, -1, 'periodic'] = _fd_d1_a12_axis1_periodic


def _fd_d1_a12_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 12, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 6, 'zero', 1)
    result = (
        (1 / 5544)
        * _stencil_shift(halo, -6, -1, 6, 'zero') +
        (-1 / 385)
        * _stencil_shift(halo, -5, -1, 6, 'zero') +
        (1 / 56)
        * _stencil_shift(halo, -4, -1, 6, 'zero') +
        (-5 / 63)
        * _stencil_shift(halo, -3, -1, 6, 'zero') +
        (15 / 56)
        * _stencil_shift(halo, -2, -1, 6, 'zero') +
        (-6 / 7)
        * _stencil_shift(halo, -1, -1, 6, 'zero') +
        (6 / 7)
        * _stencil_shift(halo, 1, -1, 6, 'zero') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -1, 6, 'zero') +
        (5 / 63)
        * _stencil_shift(halo, 3, -1, 6, 'zero') +
        (-1 / 56)
        * _stencil_shift(halo, 4, -1, 6, 'zero') +
        (1 / 385)
        * _stencil_shift(halo, 5, -1, 6, 'zero') +
        (-1 / 5544)
        * _stencil_shift(halo, 6, -1, 6, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 12, -1, 'zero'] = _fd_d1_a12_axis1_zero


def _fd_d1_a12_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 12, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 6, 'reflect', 1)
    result = (
        (1 / 5544)
        * _stencil_shift(halo, -6, -1, 6, 'reflect') +
        (-1 / 385)
        * _stencil_shift(halo, -5, -1, 6, 'reflect') +
        (1 / 56)
        * _stencil_shift(halo, -4, -1, 6, 'reflect') +
        (-5 / 63)
        * _stencil_shift(halo, -3, -1, 6, 'reflect') +
        (15 / 56)
        * _stencil_shift(halo, -2, -1, 6, 'reflect') +
        (-6 / 7)
        * _stencil_shift(halo, -1, -1, 6, 'reflect') +
        (6 / 7)
        * _stencil_shift(halo, 1, -1, 6, 'reflect') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -1, 6, 'reflect') +
        (5 / 63)
        * _stencil_shift(halo, 3, -1, 6, 'reflect') +
        (-1 / 56)
        * _stencil_shift(halo, 4, -1, 6, 'reflect') +
        (1 / 385)
        * _stencil_shift(halo, 5, -1, 6, 'reflect') +
        (-1 / 5544)
        * _stencil_shift(halo, 6, -1, 6, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 12, -1, 'reflect'] = _fd_d1_a12_axis1_reflect


STENCIL_MOMENTS[1, 14] = (
    (-7, -1, 24024),
    (-6, 7, 10296),
    (-5, -7, 1320),
    (-4, 7, 264),
    (-3, -7, 72),
    (-2, 7, 24),
    (-1, -7, 8),
    (0, 0, 1),
    (1, 7, 8),
    (2, -7, 24),
    (3, 7, 72),
    (4, -7, 264),
    (5, 7, 1320),
    (6, -7, 10296),
    (7, 1, 24024),
)

def _fd_d1_a14_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 14, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 7, 'periodic', 1)
    result = (
        (-1 / 24024)
        * _stencil_shift(halo, -7, -4, 7, 'periodic') +
        (7 / 10296)
        * _stencil_shift(halo, -6, -4, 7, 'periodic') +
        (-7 / 1320)
        * _stencil_shift(halo, -5, -4, 7, 'periodic') +
        (7 / 264)
        * _stencil_shift(halo, -4, -4, 7, 'periodic') +
        (-7 / 72)
        * _stencil_shift(halo, -3, -4, 7, 'periodic') +
        (7 / 24)
        * _stencil_shift(halo, -2, -4, 7, 'periodic') +
        (-7 / 8)
        * _stencil_shift(halo, -1, -4, 7, 'periodic') +
        (7 / 8)
        * _stencil_shift(halo, 1, -4, 7, 'periodic') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -4, 7, 'periodic') +
        (7 / 72)
        * _stencil_shift(halo, 3, -4, 7, 'periodic') +
        (-7 / 264)
        * _stencil_shift(halo, 4, -4, 7, 'periodic') +
        (7 / 1320)
        * _stencil_shift(halo, 5, -4, 7, 'periodic') +
        (-7 / 10296)
        * _stencil_shift(halo, 6, -4, 7, 'periodic') +
        (1 / 24024)
        * _stencil_shift(halo, 7, -4, 7, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 14, -4, 'periodic'] = _fd_d1_a14_axis4_periodic


def _fd_d1_a14_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 14, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 7, 'zero', 1)
    result = (
        (-1 / 24024)
        * _stencil_shift(halo, -7, -4, 7, 'zero') +
        (7 / 10296)
        * _stencil_shift(halo, -6, -4, 7, 'zero') +
        (-7 / 1320)
        * _stencil_shift(halo, -5, -4, 7, 'zero') +
        (7 / 264)
        * _stencil_shift(halo, -4, -4, 7, 'zero') +
        (-7 / 72)
        * _stencil_shift(halo, -3, -4, 7, 'zero') +
        (7 / 24)
        * _stencil_shift(halo, -2, -4, 7, 'zero') +
        (-7 / 8)
        * _stencil_shift(halo, -1, -4, 7, 'zero') +
        (7 / 8)
        * _stencil_shift(halo, 1, -4, 7, 'zero') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -4, 7, 'zero') +
        (7 / 72)
        * _stencil_shift(halo, 3, -4, 7, 'zero') +
        (-7 / 264)
        * _stencil_shift(halo, 4, -4, 7, 'zero') +
        (7 / 1320)
        * _stencil_shift(halo, 5, -4, 7, 'zero') +
        (-7 / 10296)
        * _stencil_shift(halo, 6, -4, 7, 'zero') +
        (1 / 24024)
        * _stencil_shift(halo, 7, -4, 7, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 14, -4, 'zero'] = _fd_d1_a14_axis4_zero


def _fd_d1_a14_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 14, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 7, 'reflect', 1)
    result = (
        (-1 / 24024)
        * _stencil_shift(halo, -7, -4, 7, 'reflect') +
        (7 / 10296)
        * _stencil_shift(halo, -6, -4, 7, 'reflect') +
        (-7 / 1320)
        * _stencil_shift(halo, -5, -4, 7, 'reflect') +
        (7 / 264)
        * _stencil_shift(halo, -4, -4, 7, 'reflect') +
        (-7 / 72)
        * _stencil_shift(halo, -3, -4, 7, 'reflect') +
        (7 / 24)
        * _stencil_shift(halo, -2, -4, 7, 'reflect') +
        (-7 / 8)
        * _stencil_shift(halo, -1, -4, 7, 'reflect') +
        (7 / 8)
        * _stencil_shift(halo, 1, -4, 7, 'reflect') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -4, 7, 'reflect') +
        (7 / 72)
        * _stencil_shift(halo, 3, -4, 7, 'reflect') +
        (-7 / 264)
        * _stencil_shift(halo, 4, -4, 7, 'reflect') +
        (7 / 1320)
        * _stencil_shift(halo, 5, -4, 7, 'reflect') +
        (-7 / 10296)
        * _stencil_shift(halo, 6, -4, 7, 'reflect') +
        (1 / 24024)
        * _stencil_shift(halo, 7, -4, 7, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 14, -4, 'reflect'] = _fd_d1_a14_axis4_reflect


def _fd_d1_a14_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 14, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 7, 'periodic', 1)
    result = (
        (-1 / 24024)
        * _stencil_shift(halo, -7, -3, 7, 'periodic') +
        (7 / 10296)
        * _stencil_shift(halo, -6, -3, 7, 'periodic') +
        (-7 / 1320)
        * _stencil_shift(halo, -5, -3, 7, 'periodic') +
        (7 / 264)
        * _stencil_shift(halo, -4, -3, 7, 'periodic') +
        (-7 / 72)
        * _stencil_shift(halo, -3, -3, 7, 'periodic') +
        (7 / 24)
        * _stencil_shift(halo, -2, -3, 7, 'periodic') +
        (-7 / 8)
        * _stencil_shift(halo, -1, -3, 7, 'periodic') +
        (7 / 8)
        * _stencil_shift(halo, 1, -3, 7, 'periodic') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -3, 7, 'periodic') +
        (7 / 72)
        * _stencil_shift(halo, 3, -3, 7, 'periodic') +
        (-7 / 264)
        * _stencil_shift(halo, 4, -3, 7, 'periodic') +
        (7 / 1320)
        * _stencil_shift(halo, 5, -3, 7, 'periodic') +
        (-7 / 10296)
        * _stencil_shift(halo, 6, -3, 7, 'periodic') +
        (1 / 24024)
        * _stencil_shift(halo, 7, -3, 7, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 14, -3, 'periodic'] = _fd_d1_a14_axis3_periodic


def _fd_d1_a14_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 14, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 7, 'zero', 1)
    result = (
        (-1 / 24024)
        * _stencil_shift(halo, -7, -3, 7, 'zero') +
        (7 / 10296)
        * _stencil_shift(halo, -6, -3, 7, 'zero') +
        (-7 / 1320)
        * _stencil_shift(halo, -5, -3, 7, 'zero') +
        (7 / 264)
        * _stencil_shift(halo, -4, -3, 7, 'zero') +
        (-7 / 72)
        * _stencil_shift(halo, -3, -3, 7, 'zero') +
        (7 / 24)
        * _stencil_shift(halo, -2, -3, 7, 'zero') +
        (-7 / 8)
        * _stencil_shift(halo, -1, -3, 7, 'zero') +
        (7 / 8)
        * _stencil_shift(halo, 1, -3, 7, 'zero') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -3, 7, 'zero') +
        (7 / 72)
        * _stencil_shift(halo, 3, -3, 7, 'zero') +
        (-7 / 264)
        * _stencil_shift(halo, 4, -3, 7, 'zero') +
        (7 / 1320)
        * _stencil_shift(halo, 5, -3, 7, 'zero') +
        (-7 / 10296)
        * _stencil_shift(halo, 6, -3, 7, 'zero') +
        (1 / 24024)
        * _stencil_shift(halo, 7, -3, 7, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 14, -3, 'zero'] = _fd_d1_a14_axis3_zero


def _fd_d1_a14_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 14, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 7, 'reflect', 1)
    result = (
        (-1 / 24024)
        * _stencil_shift(halo, -7, -3, 7, 'reflect') +
        (7 / 10296)
        * _stencil_shift(halo, -6, -3, 7, 'reflect') +
        (-7 / 1320)
        * _stencil_shift(halo, -5, -3, 7, 'reflect') +
        (7 / 264)
        * _stencil_shift(halo, -4, -3, 7, 'reflect') +
        (-7 / 72)
        * _stencil_shift(halo, -3, -3, 7, 'reflect') +
        (7 / 24)
        * _stencil_shift(halo, -2, -3, 7, 'reflect') +
        (-7 / 8)
        * _stencil_shift(halo, -1, -3, 7, 'reflect') +
        (7 / 8)
        * _stencil_shift(halo, 1, -3, 7, 'reflect') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -3, 7, 'reflect') +
        (7 / 72)
        * _stencil_shift(halo, 3, -3, 7, 'reflect') +
        (-7 / 264)
        * _stencil_shift(halo, 4, -3, 7, 'reflect') +
        (7 / 1320)
        * _stencil_shift(halo, 5, -3, 7, 'reflect') +
        (-7 / 10296)
        * _stencil_shift(halo, 6, -3, 7, 'reflect') +
        (1 / 24024)
        * _stencil_shift(halo, 7, -3, 7, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 14, -3, 'reflect'] = _fd_d1_a14_axis3_reflect


def _fd_d1_a14_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 14, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 7, 'periodic', 1)
    result = (
        (-1 / 24024)
        * _stencil_shift(halo, -7, -2, 7, 'periodic') +
        (7 / 10296)
        * _stencil_shift(halo, -6, -2, 7, 'periodic') +
        (-7 / 1320)
        * _stencil_shift(halo, -5, -2, 7, 'periodic') +
        (7 / 264)
        * _stencil_shift(halo, -4, -2, 7, 'periodic') +
        (-7 / 72)
        * _stencil_shift(halo, -3, -2, 7, 'periodic') +
        (7 / 24)
        * _stencil_shift(halo, -2, -2, 7, 'periodic') +
        (-7 / 8)
        * _stencil_shift(halo, -1, -2, 7, 'periodic') +
        (7 / 8)
        * _stencil_shift(halo, 1, -2, 7, 'periodic') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -2, 7, 'periodic') +
        (7 / 72)
        * _stencil_shift(halo, 3, -2, 7, 'periodic') +
        (-7 / 264)
        * _stencil_shift(halo, 4, -2, 7, 'periodic') +
        (7 / 1320)
        * _stencil_shift(halo, 5, -2, 7, 'periodic') +
        (-7 / 10296)
        * _stencil_shift(halo, 6, -2, 7, 'periodic') +
        (1 / 24024)
        * _stencil_shift(halo, 7, -2, 7, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 14, -2, 'periodic'] = _fd_d1_a14_axis2_periodic


def _fd_d1_a14_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 14, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 7, 'zero', 1)
    result = (
        (-1 / 24024)
        * _stencil_shift(halo, -7, -2, 7, 'zero') +
        (7 / 10296)
        * _stencil_shift(halo, -6, -2, 7, 'zero') +
        (-7 / 1320)
        * _stencil_shift(halo, -5, -2, 7, 'zero') +
        (7 / 264)
        * _stencil_shift(halo, -4, -2, 7, 'zero') +
        (-7 / 72)
        * _stencil_shift(halo, -3, -2, 7, 'zero') +
        (7 / 24)
        * _stencil_shift(halo, -2, -2, 7, 'zero') +
        (-7 / 8)
        * _stencil_shift(halo, -1, -2, 7, 'zero') +
        (7 / 8)
        * _stencil_shift(halo, 1, -2, 7, 'zero') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -2, 7, 'zero') +
        (7 / 72)
        * _stencil_shift(halo, 3, -2, 7, 'zero') +
        (-7 / 264)
        * _stencil_shift(halo, 4, -2, 7, 'zero') +
        (7 / 1320)
        * _stencil_shift(halo, 5, -2, 7, 'zero') +
        (-7 / 10296)
        * _stencil_shift(halo, 6, -2, 7, 'zero') +
        (1 / 24024)
        * _stencil_shift(halo, 7, -2, 7, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 14, -2, 'zero'] = _fd_d1_a14_axis2_zero


def _fd_d1_a14_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 14, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 7, 'reflect', 1)
    result = (
        (-1 / 24024)
        * _stencil_shift(halo, -7, -2, 7, 'reflect') +
        (7 / 10296)
        * _stencil_shift(halo, -6, -2, 7, 'reflect') +
        (-7 / 1320)
        * _stencil_shift(halo, -5, -2, 7, 'reflect') +
        (7 / 264)
        * _stencil_shift(halo, -4, -2, 7, 'reflect') +
        (-7 / 72)
        * _stencil_shift(halo, -3, -2, 7, 'reflect') +
        (7 / 24)
        * _stencil_shift(halo, -2, -2, 7, 'reflect') +
        (-7 / 8)
        * _stencil_shift(halo, -1, -2, 7, 'reflect') +
        (7 / 8)
        * _stencil_shift(halo, 1, -2, 7, 'reflect') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -2, 7, 'reflect') +
        (7 / 72)
        * _stencil_shift(halo, 3, -2, 7, 'reflect') +
        (-7 / 264)
        * _stencil_shift(halo, 4, -2, 7, 'reflect') +
        (7 / 1320)
        * _stencil_shift(halo, 5, -2, 7, 'reflect') +
        (-7 / 10296)
        * _stencil_shift(halo, 6, -2, 7, 'reflect') +
        (1 / 24024)
        * _stencil_shift(halo, 7, -2, 7, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 14, -2, 'reflect'] = _fd_d1_a14_axis2_reflect


def _fd_d1_a14_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 14, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 7, 'periodic', 1)
    result = (
        (-1 / 24024)
        * _stencil_shift(halo, -7, -1, 7, 'periodic') +
        (7 / 10296)
        * _stencil_shift(halo, -6, -1, 7, 'periodic') +
        (-7 / 1320)
        * _stencil_shift(halo, -5, -1, 7, 'periodic') +
        (7 / 264)
        * _stencil_shift(halo, -4, -1, 7, 'periodic') +
        (-7 / 72)
        * _stencil_shift(halo, -3, -1, 7, 'periodic') +
        (7 / 24)
        * _stencil_shift(halo, -2, -1, 7, 'periodic') +
        (-7 / 8)
        * _stencil_shift(halo, -1, -1, 7, 'periodic') +
        (7 / 8)
        * _stencil_shift(halo, 1, -1, 7, 'periodic') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -1, 7, 'periodic') +
        (7 / 72)
        * _stencil_shift(halo, 3, -1, 7, 'periodic') +
        (-7 / 264)
        * _stencil_shift(halo, 4, -1, 7, 'periodic') +
        (7 / 1320)
        * _stencil_shift(halo, 5, -1, 7, 'periodic') +
        (-7 / 10296)
        * _stencil_shift(halo, 6, -1, 7, 'periodic') +
        (1 / 24024)
        * _stencil_shift(halo, 7, -1, 7, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 14, -1, 'periodic'] = _fd_d1_a14_axis1_periodic


def _fd_d1_a14_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 14, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 7, 'zero', 1)
    result = (
        (-1 / 24024)
        * _stencil_shift(halo, -7, -1, 7, 'zero') +
        (7 / 10296)
        * _stencil_shift(halo, -6, -1, 7, 'zero') +
        (-7 / 1320)
        * _stencil_shift(halo, -5, -1, 7, 'zero') +
        (7 / 264)
        * _stencil_shift(halo, -4, -1, 7, 'zero') +
        (-7 / 72)
        * _stencil_shift(halo, -3, -1, 7, 'zero') +
        (7 / 24)
        * _stencil_shift(halo, -2, -1, 7, 'zero') +
        (-7 / 8)
        * _stencil_shift(halo, -1, -1, 7, 'zero') +
        (7 / 8)
        * _stencil_shift(halo, 1, -1, 7, 'zero') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -1, 7, 'zero') +
        (7 / 72)
        * _stencil_shift(halo, 3, -1, 7, 'zero') +
        (-7 / 264)
        * _stencil_shift(halo, 4, -1, 7, 'zero') +
        (7 / 1320)
        * _stencil_shift(halo, 5, -1, 7, 'zero') +
        (-7 / 10296)
        * _stencil_shift(halo, 6, -1, 7, 'zero') +
        (1 / 24024)
        * _stencil_shift(halo, 7, -1, 7, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 14, -1, 'zero'] = _fd_d1_a14_axis1_zero


def _fd_d1_a14_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 14, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 7, 'reflect', 1)
    result = (
        (-1 / 24024)
        * _stencil_shift(halo, -7, -1, 7, 'reflect') +
        (7 / 10296)
        * _stencil_shift(halo, -6, -1, 7, 'reflect') +
        (-7 / 1320)
        * _stencil_shift(halo, -5, -1, 7, 'reflect') +
        (7 / 264)
        * _stencil_shift(halo, -4, -1, 7, 'reflect') +
        (-7 / 72)
        * _stencil_shift(halo, -3, -1, 7, 'reflect') +
        (7 / 24)
        * _stencil_shift(halo, -2, -1, 7, 'reflect') +
        (-7 / 8)
        * _stencil_shift(halo, -1, -1, 7, 'reflect') +
        (7 / 8)
        * _stencil_shift(halo, 1, -1, 7, 'reflect') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -1, 7, 'reflect') +
        (7 / 72)
        * _stencil_shift(halo, 3, -1, 7, 'reflect') +
        (-7 / 264)
        * _stencil_shift(halo, 4, -1, 7, 'reflect') +
        (7 / 1320)
        * _stencil_shift(halo, 5, -1, 7, 'reflect') +
        (-7 / 10296)
        * _stencil_shift(halo, 6, -1, 7, 'reflect') +
        (1 / 24024)
        * _stencil_shift(halo, 7, -1, 7, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 14, -1, 'reflect'] = _fd_d1_a14_axis1_reflect


STENCIL_MOMENTS[1, 16] = (
    (-8, 1, 102960),
    (-7, -8, 45045),
    (-6, 2, 1287),
    (-5, -56, 6435),
    (-4, 7, 198),
    (-3, -56, 495),
    (-2, 14, 45),
    (-1, -8, 9),
    (0, 0, 1),
    (1, 8, 9),
    (2, -14, 45),
    (3, 56, 495),
    (4, -7, 198),
    (5, 56, 6435),
    (6, -2, 1287),
    (7, 8, 45045),
    (8, -1, 102960),
)

def _fd_d1_a16_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 16, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 8, 'periodic', 1)
    result = (
        (1 / 102960)
        * _stencil_shift(halo, -8, -4, 8, 'periodic') +
        (-8 / 45045)
        * _stencil_shift(halo, -7, -4, 8, 'periodic') +
        (2 / 1287)
        * _stencil_shift(halo, -6, -4, 8, 'periodic') +
        (-56 / 6435)
        * _stencil_shift(halo, -5, -4, 8, 'periodic') +
        (7 / 198)
        * _stencil_shift(halo, -4, -4, 8, 'periodic') +
        (-56 / 495)
        * _stencil_shift(halo, -3, -4, 8, 'periodic') +
        (14 / 45)
        * _stencil_shift(halo, -2, -4, 8, 'periodic') +
        (-8 / 9)
        * _stencil_shift(halo, -1, -4, 8, 'periodic') +
        (8 / 9)
        * _stencil_shift(halo, 1, -4, 8, 'periodic') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -4, 8, 'periodic') +
        (56 / 495)
        * _stencil_shift(halo, 3, -4, 8, 'periodic') +
        (-7 / 198)
        * _stencil_shift(halo, 4, -4, 8, 'periodic') +
        (56 / 6435)
        * _stencil_shift(halo, 5, -4, 8, 'periodic') +
        (-2 / 1287)
        * _stencil_shift(halo, 6, -4, 8, 'periodic') +
        (8 / 45045)
        * _stencil_shift(halo, 7, -4, 8, 'periodic') +
        (-1 / 102960)
        * _stencil_shift(halo, 8, -4, 8, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 16, -4, 'periodic'] = _fd_d1_a16_axis4_periodic


def _fd_d1_a16_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 16, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 8, 'zero', 1)
    result = (
        (1 / 102960)
        * _stencil_shift(halo, -8, -4, 8, 'zero') +
        (-8 / 45045)
        * _stencil_shift(halo, -7, -4, 8, 'zero') +
        (2 / 1287)
        * _stencil_shift(halo, -6, -4, 8, 'zero') +
        (-56 / 6435)
        * _stencil_shift(halo, -5, -4, 8, 'zero') +
        (7 / 198)
        * _stencil_shift(halo, -4, -4, 8, 'zero') +
        (-56 / 495)
        * _stencil_shift(halo, -3, -4, 8, 'zero') +
        (14 / 45)
        * _stencil_shift(halo, -2, -4, 8, 'zero') +
        (-8 / 9)
        * _stencil_shift(halo, -1, -4, 8, 'zero') +
        (8 / 9)
        * _stencil_shift(halo, 1, -4, 8, 'zero') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -4, 8, 'zero') +
        (56 / 495)
        * _stencil_shift(halo, 3, -4, 8, 'zero') +
        (-7 / 198)
        * _stencil_shift(halo, 4, -4, 8, 'zero') +
        (56 / 6435)
        * _stencil_shift(halo, 5, -4, 8, 'zero') +
        (-2 / 1287)
        * _stencil_shift(halo, 6, -4, 8, 'zero') +
        (8 / 45045)
        * _stencil_shift(halo, 7, -4, 8, 'zero') +
        (-1 / 102960)
        * _stencil_shift(halo, 8, -4, 8, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 16, -4, 'zero'] = _fd_d1_a16_axis4_zero


def _fd_d1_a16_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 16, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 8, 'reflect', 1)
    result = (
        (1 / 102960)
        * _stencil_shift(halo, -8, -4, 8, 'reflect') +
        (-8 / 45045)
        * _stencil_shift(halo, -7, -4, 8, 'reflect') +
        (2 / 1287)
        * _stencil_shift(halo, -6, -4, 8, 'reflect') +
        (-56 / 6435)
        * _stencil_shift(halo, -5, -4, 8, 'reflect') +
        (7 / 198)
        * _stencil_shift(halo, -4, -4, 8, 'reflect') +
        (-56 / 495)
        * _stencil_shift(halo, -3, -4, 8, 'reflect') +
        (14 / 45)
        * _stencil_shift(halo, -2, -4, 8, 'reflect') +
        (-8 / 9)
        * _stencil_shift(halo, -1, -4, 8, 'reflect') +
        (8 / 9)
        * _stencil_shift(halo, 1, -4, 8, 'reflect') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -4, 8, 'reflect') +
        (56 / 495)
        * _stencil_shift(halo, 3, -4, 8, 'reflect') +
        (-7 / 198)
        * _stencil_shift(halo, 4, -4, 8, 'reflect') +
        (56 / 6435)
        * _stencil_shift(halo, 5, -4, 8, 'reflect') +
        (-2 / 1287)
        * _stencil_shift(halo, 6, -4, 8, 'reflect') +
        (8 / 45045)
        * _stencil_shift(halo, 7, -4, 8, 'reflect') +
        (-1 / 102960)
        * _stencil_shift(halo, 8, -4, 8, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 16, -4, 'reflect'] = _fd_d1_a16_axis4_reflect


def _fd_d1_a16_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 16, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 8, 'periodic', 1)
    result = (
        (1 / 102960)
        * _stencil_shift(halo, -8, -3, 8, 'periodic') +
        (-8 / 45045)
        * _stencil_shift(halo, -7, -3, 8, 'periodic') +
        (2 / 1287)
        * _stencil_shift(halo, -6, -3, 8, 'periodic') +
        (-56 / 6435)
        * _stencil_shift(halo, -5, -3, 8, 'periodic') +
        (7 / 198)
        * _stencil_shift(halo, -4, -3, 8, 'periodic') +
        (-56 / 495)
        * _stencil_shift(halo, -3, -3, 8, 'periodic') +
        (14 / 45)
        * _stencil_shift(halo, -2, -3, 8, 'periodic') +
        (-8 / 9)
        * _stencil_shift(halo, -1, -3, 8, 'periodic') +
        (8 / 9)
        * _stencil_shift(halo, 1, -3, 8, 'periodic') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -3, 8, 'periodic') +
        (56 / 495)
        * _stencil_shift(halo, 3, -3, 8, 'periodic') +
        (-7 / 198)
        * _stencil_shift(halo, 4, -3, 8, 'periodic') +
        (56 / 6435)
        * _stencil_shift(halo, 5, -3, 8, 'periodic') +
        (-2 / 1287)
        * _stencil_shift(halo, 6, -3, 8, 'periodic') +
        (8 / 45045)
        * _stencil_shift(halo, 7, -3, 8, 'periodic') +
        (-1 / 102960)
        * _stencil_shift(halo, 8, -3, 8, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 16, -3, 'periodic'] = _fd_d1_a16_axis3_periodic


def _fd_d1_a16_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 16, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 8, 'zero', 1)
    result = (
        (1 / 102960)
        * _stencil_shift(halo, -8, -3, 8, 'zero') +
        (-8 / 45045)
        * _stencil_shift(halo, -7, -3, 8, 'zero') +
        (2 / 1287)
        * _stencil_shift(halo, -6, -3, 8, 'zero') +
        (-56 / 6435)
        * _stencil_shift(halo, -5, -3, 8, 'zero') +
        (7 / 198)
        * _stencil_shift(halo, -4, -3, 8, 'zero') +
        (-56 / 495)
        * _stencil_shift(halo, -3, -3, 8, 'zero') +
        (14 / 45)
        * _stencil_shift(halo, -2, -3, 8, 'zero') +
        (-8 / 9)
        * _stencil_shift(halo, -1, -3, 8, 'zero') +
        (8 / 9)
        * _stencil_shift(halo, 1, -3, 8, 'zero') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -3, 8, 'zero') +
        (56 / 495)
        * _stencil_shift(halo, 3, -3, 8, 'zero') +
        (-7 / 198)
        * _stencil_shift(halo, 4, -3, 8, 'zero') +
        (56 / 6435)
        * _stencil_shift(halo, 5, -3, 8, 'zero') +
        (-2 / 1287)
        * _stencil_shift(halo, 6, -3, 8, 'zero') +
        (8 / 45045)
        * _stencil_shift(halo, 7, -3, 8, 'zero') +
        (-1 / 102960)
        * _stencil_shift(halo, 8, -3, 8, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 16, -3, 'zero'] = _fd_d1_a16_axis3_zero


def _fd_d1_a16_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 16, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 8, 'reflect', 1)
    result = (
        (1 / 102960)
        * _stencil_shift(halo, -8, -3, 8, 'reflect') +
        (-8 / 45045)
        * _stencil_shift(halo, -7, -3, 8, 'reflect') +
        (2 / 1287)
        * _stencil_shift(halo, -6, -3, 8, 'reflect') +
        (-56 / 6435)
        * _stencil_shift(halo, -5, -3, 8, 'reflect') +
        (7 / 198)
        * _stencil_shift(halo, -4, -3, 8, 'reflect') +
        (-56 / 495)
        * _stencil_shift(halo, -3, -3, 8, 'reflect') +
        (14 / 45)
        * _stencil_shift(halo, -2, -3, 8, 'reflect') +
        (-8 / 9)
        * _stencil_shift(halo, -1, -3, 8, 'reflect') +
        (8 / 9)
        * _stencil_shift(halo, 1, -3, 8, 'reflect') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -3, 8, 'reflect') +
        (56 / 495)
        * _stencil_shift(halo, 3, -3, 8, 'reflect') +
        (-7 / 198)
        * _stencil_shift(halo, 4, -3, 8, 'reflect') +
        (56 / 6435)
        * _stencil_shift(halo, 5, -3, 8, 'reflect') +
        (-2 / 1287)
        * _stencil_shift(halo, 6, -3, 8, 'reflect') +
        (8 / 45045)
        * _stencil_shift(halo, 7, -3, 8, 'reflect') +
        (-1 / 102960)
        * _stencil_shift(halo, 8, -3, 8, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 16, -3, 'reflect'] = _fd_d1_a16_axis3_reflect


def _fd_d1_a16_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 16, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 8, 'periodic', 1)
    result = (
        (1 / 102960)
        * _stencil_shift(halo, -8, -2, 8, 'periodic') +
        (-8 / 45045)
        * _stencil_shift(halo, -7, -2, 8, 'periodic') +
        (2 / 1287)
        * _stencil_shift(halo, -6, -2, 8, 'periodic') +
        (-56 / 6435)
        * _stencil_shift(halo, -5, -2, 8, 'periodic') +
        (7 / 198)
        * _stencil_shift(halo, -4, -2, 8, 'periodic') +
        (-56 / 495)
        * _stencil_shift(halo, -3, -2, 8, 'periodic') +
        (14 / 45)
        * _stencil_shift(halo, -2, -2, 8, 'periodic') +
        (-8 / 9)
        * _stencil_shift(halo, -1, -2, 8, 'periodic') +
        (8 / 9)
        * _stencil_shift(halo, 1, -2, 8, 'periodic') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -2, 8, 'periodic') +
        (56 / 495)
        * _stencil_shift(halo, 3, -2, 8, 'periodic') +
        (-7 / 198)
        * _stencil_shift(halo, 4, -2, 8, 'periodic') +
        (56 / 6435)
        * _stencil_shift(halo, 5, -2, 8, 'periodic') +
        (-2 / 1287)
        * _stencil_shift(halo, 6, -2, 8, 'periodic') +
        (8 / 45045)
        * _stencil_shift(halo, 7, -2, 8, 'periodic') +
        (-1 / 102960)
        * _stencil_shift(halo, 8, -2, 8, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 16, -2, 'periodic'] = _fd_d1_a16_axis2_periodic


def _fd_d1_a16_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 16, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 8, 'zero', 1)
    result = (
        (1 / 102960)
        * _stencil_shift(halo, -8, -2, 8, 'zero') +
        (-8 / 45045)
        * _stencil_shift(halo, -7, -2, 8, 'zero') +
        (2 / 1287)
        * _stencil_shift(halo, -6, -2, 8, 'zero') +
        (-56 / 6435)
        * _stencil_shift(halo, -5, -2, 8, 'zero') +
        (7 / 198)
        * _stencil_shift(halo, -4, -2, 8, 'zero') +
        (-56 / 495)
        * _stencil_shift(halo, -3, -2, 8, 'zero') +
        (14 / 45)
        * _stencil_shift(halo, -2, -2, 8, 'zero') +
        (-8 / 9)
        * _stencil_shift(halo, -1, -2, 8, 'zero') +
        (8 / 9)
        * _stencil_shift(halo, 1, -2, 8, 'zero') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -2, 8, 'zero') +
        (56 / 495)
        * _stencil_shift(halo, 3, -2, 8, 'zero') +
        (-7 / 198)
        * _stencil_shift(halo, 4, -2, 8, 'zero') +
        (56 / 6435)
        * _stencil_shift(halo, 5, -2, 8, 'zero') +
        (-2 / 1287)
        * _stencil_shift(halo, 6, -2, 8, 'zero') +
        (8 / 45045)
        * _stencil_shift(halo, 7, -2, 8, 'zero') +
        (-1 / 102960)
        * _stencil_shift(halo, 8, -2, 8, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 16, -2, 'zero'] = _fd_d1_a16_axis2_zero


def _fd_d1_a16_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 16, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 8, 'reflect', 1)
    result = (
        (1 / 102960)
        * _stencil_shift(halo, -8, -2, 8, 'reflect') +
        (-8 / 45045)
        * _stencil_shift(halo, -7, -2, 8, 'reflect') +
        (2 / 1287)
        * _stencil_shift(halo, -6, -2, 8, 'reflect') +
        (-56 / 6435)
        * _stencil_shift(halo, -5, -2, 8, 'reflect') +
        (7 / 198)
        * _stencil_shift(halo, -4, -2, 8, 'reflect') +
        (-56 / 495)
        * _stencil_shift(halo, -3, -2, 8, 'reflect') +
        (14 / 45)
        * _stencil_shift(halo, -2, -2, 8, 'reflect') +
        (-8 / 9)
        * _stencil_shift(halo, -1, -2, 8, 'reflect') +
        (8 / 9)
        * _stencil_shift(halo, 1, -2, 8, 'reflect') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -2, 8, 'reflect') +
        (56 / 495)
        * _stencil_shift(halo, 3, -2, 8, 'reflect') +
        (-7 / 198)
        * _stencil_shift(halo, 4, -2, 8, 'reflect') +
        (56 / 6435)
        * _stencil_shift(halo, 5, -2, 8, 'reflect') +
        (-2 / 1287)
        * _stencil_shift(halo, 6, -2, 8, 'reflect') +
        (8 / 45045)
        * _stencil_shift(halo, 7, -2, 8, 'reflect') +
        (-1 / 102960)
        * _stencil_shift(halo, 8, -2, 8, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 16, -2, 'reflect'] = _fd_d1_a16_axis2_reflect


def _fd_d1_a16_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 16, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 8, 'periodic', 1)
    result = (
        (1 / 102960)
        * _stencil_shift(halo, -8, -1, 8, 'periodic') +
        (-8 / 45045)
        * _stencil_shift(halo, -7, -1, 8, 'periodic') +
        (2 / 1287)
        * _stencil_shift(halo, -6, -1, 8, 'periodic') +
        (-56 / 6435)
        * _stencil_shift(halo, -5, -1, 8, 'periodic') +
        (7 / 198)
        * _stencil_shift(halo, -4, -1, 8, 'periodic') +
        (-56 / 495)
        * _stencil_shift(halo, -3, -1, 8, 'periodic') +
        (14 / 45)
        * _stencil_shift(halo, -2, -1, 8, 'periodic') +
        (-8 / 9)
        * _stencil_shift(halo, -1, -1, 8, 'periodic') +
        (8 / 9)
        * _stencil_shift(halo, 1, -1, 8, 'periodic') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -1, 8, 'periodic') +
        (56 / 495)
        * _stencil_shift(halo, 3, -1, 8, 'periodic') +
        (-7 / 198)
        * _stencil_shift(halo, 4, -1, 8, 'periodic') +
        (56 / 6435)
        * _stencil_shift(halo, 5, -1, 8, 'periodic') +
        (-2 / 1287)
        * _stencil_shift(halo, 6, -1, 8, 'periodic') +
        (8 / 45045)
        * _stencil_shift(halo, 7, -1, 8, 'periodic') +
        (-1 / 102960)
        * _stencil_shift(halo, 8, -1, 8, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 16, -1, 'periodic'] = _fd_d1_a16_axis1_periodic


def _fd_d1_a16_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 16, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 8, 'zero', 1)
    result = (
        (1 / 102960)
        * _stencil_shift(halo, -8, -1, 8, 'zero') +
        (-8 / 45045)
        * _stencil_shift(halo, -7, -1, 8, 'zero') +
        (2 / 1287)
        * _stencil_shift(halo, -6, -1, 8, 'zero') +
        (-56 / 6435)
        * _stencil_shift(halo, -5, -1, 8, 'zero') +
        (7 / 198)
        * _stencil_shift(halo, -4, -1, 8, 'zero') +
        (-56 / 495)
        * _stencil_shift(halo, -3, -1, 8, 'zero') +
        (14 / 45)
        * _stencil_shift(halo, -2, -1, 8, 'zero') +
        (-8 / 9)
        * _stencil_shift(halo, -1, -1, 8, 'zero') +
        (8 / 9)
        * _stencil_shift(halo, 1, -1, 8, 'zero') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -1, 8, 'zero') +
        (56 / 495)
        * _stencil_shift(halo, 3, -1, 8, 'zero') +
        (-7 / 198)
        * _stencil_shift(halo, 4, -1, 8, 'zero') +
        (56 / 6435)
        * _stencil_shift(halo, 5, -1, 8, 'zero') +
        (-2 / 1287)
        * _stencil_shift(halo, 6, -1, 8, 'zero') +
        (8 / 45045)
        * _stencil_shift(halo, 7, -1, 8, 'zero') +
        (-1 / 102960)
        * _stencil_shift(halo, 8, -1, 8, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 16, -1, 'zero'] = _fd_d1_a16_axis1_zero


def _fd_d1_a16_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 16, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 8, 'reflect', 1)
    result = (
        (1 / 102960)
        * _stencil_shift(halo, -8, -1, 8, 'reflect') +
        (-8 / 45045)
        * _stencil_shift(halo, -7, -1, 8, 'reflect') +
        (2 / 1287)
        * _stencil_shift(halo, -6, -1, 8, 'reflect') +
        (-56 / 6435)
        * _stencil_shift(halo, -5, -1, 8, 'reflect') +
        (7 / 198)
        * _stencil_shift(halo, -4, -1, 8, 'reflect') +
        (-56 / 495)
        * _stencil_shift(halo, -3, -1, 8, 'reflect') +
        (14 / 45)
        * _stencil_shift(halo, -2, -1, 8, 'reflect') +
        (-8 / 9)
        * _stencil_shift(halo, -1, -1, 8, 'reflect') +
        (8 / 9)
        * _stencil_shift(halo, 1, -1, 8, 'reflect') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -1, 8, 'reflect') +
        (56 / 495)
        * _stencil_shift(halo, 3, -1, 8, 'reflect') +
        (-7 / 198)
        * _stencil_shift(halo, 4, -1, 8, 'reflect') +
        (56 / 6435)
        * _stencil_shift(halo, 5, -1, 8, 'reflect') +
        (-2 / 1287)
        * _stencil_shift(halo, 6, -1, 8, 'reflect') +
        (8 / 45045)
        * _stencil_shift(halo, 7, -1, 8, 'reflect') +
        (-1 / 102960)
        * _stencil_shift(halo, 8, -1, 8, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 16, -1, 'reflect'] = _fd_d1_a16_axis1_reflect


STENCIL_MOMENTS[1, 18] = (
    (-9, -1, 437580),
    (-8, 9, 194480),
    (-7, -9, 20020),
    (-6, 2, 715),
    (-5, -9, 715),
    (-4, 63, 1430),
    (-3, -7, 55),
    (-2, 18, 55),
    (-1, -9, 10),
    (0, 0, 1),
    (1, 9, 10),
    (2, -18, 55),
    (3, 7, 55),
    (4, -63, 1430),
    (5, 9, 715),
    (6, -2, 715),
    (7, 9, 20020),
    (8, -9, 194480),
    (9, 1, 437580),
)

def _fd_d1_a18_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 18, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 9, 'periodic', 1)
    result = (
        (-1 / 437580)
        * _stencil_shift(halo, -9, -4, 9, 'periodic') +
        (9 / 194480)
        * _stencil_shift(halo, -8, -4, 9, 'periodic') +
        (-9 / 20020)
        * _stencil_shift(halo, -7, -4, 9, 'periodic') +
        (2 / 715)
        * _stencil_shift(halo, -6, -4, 9, 'periodic') +
        (-9 / 715)
        * _stencil_shift(halo, -5, -4, 9, 'periodic') +
        (63 / 1430)
        * _stencil_shift(halo, -4, -4, 9, 'periodic') +
        (-7 / 55)
        * _stencil_shift(halo, -3, -4, 9, 'periodic') +
        (18 / 55)
        * _stencil_shift(halo, -2, -4, 9, 'periodic') +
        (-9 / 10)
        * _stencil_shift(halo, -1, -4, 9, 'periodic') +
        (9 / 10)
        * _stencil_shift(halo, 1, -4, 9, 'periodic') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -4, 9, 'periodic') +
        (7 / 55)
        * _stencil_shift(halo, 3, -4, 9, 'periodic') +
        (-63 / 1430)
        * _stencil_shift(halo, 4, -4, 9, 'periodic') +
        (9 / 715)
        * _stencil_shift(halo, 5, -4, 9, 'periodic') +
        (-2 / 715)
        * _stencil_shift(halo, 6, -4, 9, 'periodic') +
        (9 / 20020)
        * _stencil_shift(halo, 7, -4, 9, 'periodic') +
        (-9 / 194480)
        * _stencil_shift(halo, 8, -4, 9, 'periodic') +
        (1 / 437580)
        * _stencil_shift(halo, 9, -4, 9, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 18, -4, 'periodic'] = _fd_d1_a18_axis4_periodic


def _fd_d1_a18_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 18, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 9, 'zero', 1)
    result = (
        (-1 / 437580)
        * _stencil_shift(halo, -9, -4, 9, 'zero') +
        (9 / 194480)
        * _stencil_shift(halo, -8, -4, 9, 'zero') +
        (-9 / 20020)
        * _stencil_shift(halo, -7, -4, 9, 'zero') +
        (2 / 715)
        * _stencil_shift(halo, -6, -4, 9, 'zero') +
        (-9 / 715)
        * _stencil_shift(halo, -5, -4, 9, 'zero') +
        (63 / 1430)
        * _stencil_shift(halo, -4, -4, 9, 'zero') +
        (-7 / 55)
        * _stencil_shift(halo, -3, -4, 9, 'zero') +
        (18 / 55)
        * _stencil_shift(halo, -2, -4, 9, 'zero') +
        (-9 / 10)
        * _stencil_shift(halo, -1, -4, 9, 'zero') +
        (9 / 10)
        * _stencil_shift(halo, 1, -4, 9, 'zero') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -4, 9, 'zero') +
        (7 / 55)
        * _stencil_shift(halo, 3, -4, 9, 'zero') +
        (-63 / 1430)
        * _stencil_shift(halo, 4, -4, 9, 'zero') +
        (9 / 715)
        * _stencil_shift(halo, 5, -4, 9, 'zero') +
        (-2 / 715)
        * _stencil_shift(halo, 6, -4, 9, 'zero') +
        (9 / 20020)
        * _stencil_shift(halo, 7, -4, 9, 'zero') +
        (-9 / 194480)
        * _stencil_shift(halo, 8, -4, 9, 'zero') +
        (1 / 437580)
        * _stencil_shift(halo, 9, -4, 9, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 18, -4, 'zero'] = _fd_d1_a18_axis4_zero


def _fd_d1_a18_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 18, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 9, 'reflect', 1)
    result = (
        (-1 / 437580)
        * _stencil_shift(halo, -9, -4, 9, 'reflect') +
        (9 / 194480)
        * _stencil_shift(halo, -8, -4, 9, 'reflect') +
        (-9 / 20020)
        * _stencil_shift(halo, -7, -4, 9, 'reflect') +
        (2 / 715)
        * _stencil_shift(halo, -6, -4, 9, 'reflect') +
        (-9 / 715)
        * _stencil_shift(halo, -5, -4, 9, 'reflect') +
        (63 / 1430)
        * _stencil_shift(halo, -4, -4, 9, 'reflect') +
        (-7 / 55)
        * _stencil_shift(halo, -3, -4, 9, 'reflect') +
        (18 / 55)
        * _stencil_shift(halo, -2, -4, 9, 'reflect') +
        (-9 / 10)
        * _stencil_shift(halo, -1, -4, 9, 'reflect') +
        (9 / 10)
        * _stencil_shift(halo, 1, -4, 9, 'reflect') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -4, 9, 'reflect') +
        (7 / 55)
        * _stencil_shift(halo, 3, -4, 9, 'reflect') +
        (-63 / 1430)
        * _stencil_shift(halo, 4, -4, 9, 'reflect') +
        (9 / 715)
        * _stencil_shift(halo, 5, -4, 9, 'reflect') +
        (-2 / 715)
        * _stencil_shift(halo, 6, -4, 9, 'reflect') +
        (9 / 20020)
        * _stencil_shift(halo, 7, -4, 9, 'reflect') +
        (-9 / 194480)
        * _stencil_shift(halo, 8, -4, 9, 'reflect') +
        (1 / 437580)
        * _stencil_shift(halo, 9, -4, 9, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 18, -4, 'reflect'] = _fd_d1_a18_axis4_reflect


def _fd_d1_a18_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 18, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 9, 'periodic', 1)
    result = (
        (-1 / 437580)
        * _stencil_shift(halo, -9, -3, 9, 'periodic') +
        (9 / 194480)
        * _stencil_shift(halo, -8, -3, 9, 'periodic') +
        (-9 / 20020)
        * _stencil_shift(halo, -7, -3, 9, 'periodic') +
        (2 / 715)
        * _stencil_shift(halo, -6, -3, 9, 'periodic') +
        (-9 / 715)
        * _stencil_shift(halo, -5, -3, 9, 'periodic') +
        (63 / 1430)
        * _stencil_shift(halo, -4, -3, 9, 'periodic') +
        (-7 / 55)
        * _stencil_shift(halo, -3, -3, 9, 'periodic') +
        (18 / 55)
        * _stencil_shift(halo, -2, -3, 9, 'periodic') +
        (-9 / 10)
        * _stencil_shift(halo, -1, -3, 9, 'periodic') +
        (9 / 10)
        * _stencil_shift(halo, 1, -3, 9, 'periodic') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -3, 9, 'periodic') +
        (7 / 55)
        * _stencil_shift(halo, 3, -3, 9, 'periodic') +
        (-63 / 1430)
        * _stencil_shift(halo, 4, -3, 9, 'periodic') +
        (9 / 715)
        * _stencil_shift(halo, 5, -3, 9, 'periodic') +
        (-2 / 715)
        * _stencil_shift(halo, 6, -3, 9, 'periodic') +
        (9 / 20020)
        * _stencil_shift(halo, 7, -3, 9, 'periodic') +
        (-9 / 194480)
        * _stencil_shift(halo, 8, -3, 9, 'periodic') +
        (1 / 437580)
        * _stencil_shift(halo, 9, -3, 9, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 18, -3, 'periodic'] = _fd_d1_a18_axis3_periodic


def _fd_d1_a18_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 18, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 9, 'zero', 1)
    result = (
        (-1 / 437580)
        * _stencil_shift(halo, -9, -3, 9, 'zero') +
        (9 / 194480)
        * _stencil_shift(halo, -8, -3, 9, 'zero') +
        (-9 / 20020)
        * _stencil_shift(halo, -7, -3, 9, 'zero') +
        (2 / 715)
        * _stencil_shift(halo, -6, -3, 9, 'zero') +
        (-9 / 715)
        * _stencil_shift(halo, -5, -3, 9, 'zero') +
        (63 / 1430)
        * _stencil_shift(halo, -4, -3, 9, 'zero') +
        (-7 / 55)
        * _stencil_shift(halo, -3, -3, 9, 'zero') +
        (18 / 55)
        * _stencil_shift(halo, -2, -3, 9, 'zero') +
        (-9 / 10)
        * _stencil_shift(halo, -1, -3, 9, 'zero') +
        (9 / 10)
        * _stencil_shift(halo, 1, -3, 9, 'zero') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -3, 9, 'zero') +
        (7 / 55)
        * _stencil_shift(halo, 3, -3, 9, 'zero') +
        (-63 / 1430)
        * _stencil_shift(halo, 4, -3, 9, 'zero') +
        (9 / 715)
        * _stencil_shift(halo, 5, -3, 9, 'zero') +
        (-2 / 715)
        * _stencil_shift(halo, 6, -3, 9, 'zero') +
        (9 / 20020)
        * _stencil_shift(halo, 7, -3, 9, 'zero') +
        (-9 / 194480)
        * _stencil_shift(halo, 8, -3, 9, 'zero') +
        (1 / 437580)
        * _stencil_shift(halo, 9, -3, 9, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 18, -3, 'zero'] = _fd_d1_a18_axis3_zero


def _fd_d1_a18_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 18, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 9, 'reflect', 1)
    result = (
        (-1 / 437580)
        * _stencil_shift(halo, -9, -3, 9, 'reflect') +
        (9 / 194480)
        * _stencil_shift(halo, -8, -3, 9, 'reflect') +
        (-9 / 20020)
        * _stencil_shift(halo, -7, -3, 9, 'reflect') +
        (2 / 715)
        * _stencil_shift(halo, -6, -3, 9, 'reflect') +
        (-9 / 715)
        * _stencil_shift(halo, -5, -3, 9, 'reflect') +
        (63 / 1430)
        * _stencil_shift(halo, -4, -3, 9, 'reflect') +
        (-7 / 55)
        * _stencil_shift(halo, -3, -3, 9, 'reflect') +
        (18 / 55)
        * _stencil_shift(halo, -2, -3, 9, 'reflect') +
        (-9 / 10)
        * _stencil_shift(halo, -1, -3, 9, 'reflect') +
        (9 / 10)
        * _stencil_shift(halo, 1, -3, 9, 'reflect') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -3, 9, 'reflect') +
        (7 / 55)
        * _stencil_shift(halo, 3, -3, 9, 'reflect') +
        (-63 / 1430)
        * _stencil_shift(halo, 4, -3, 9, 'reflect') +
        (9 / 715)
        * _stencil_shift(halo, 5, -3, 9, 'reflect') +
        (-2 / 715)
        * _stencil_shift(halo, 6, -3, 9, 'reflect') +
        (9 / 20020)
        * _stencil_shift(halo, 7, -3, 9, 'reflect') +
        (-9 / 194480)
        * _stencil_shift(halo, 8, -3, 9, 'reflect') +
        (1 / 437580)
        * _stencil_shift(halo, 9, -3, 9, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 18, -3, 'reflect'] = _fd_d1_a18_axis3_reflect


def _fd_d1_a18_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 18, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 9, 'periodic', 1)
    result = (
        (-1 / 437580)
        * _stencil_shift(halo, -9, -2, 9, 'periodic') +
        (9 / 194480)
        * _stencil_shift(halo, -8, -2, 9, 'periodic') +
        (-9 / 20020)
        * _stencil_shift(halo, -7, -2, 9, 'periodic') +
        (2 / 715)
        * _stencil_shift(halo, -6, -2, 9, 'periodic') +
        (-9 / 715)
        * _stencil_shift(halo, -5, -2, 9, 'periodic') +
        (63 / 1430)
        * _stencil_shift(halo, -4, -2, 9, 'periodic') +
        (-7 / 55)
        * _stencil_shift(halo, -3, -2, 9, 'periodic') +
        (18 / 55)
        * _stencil_shift(halo, -2, -2, 9, 'periodic') +
        (-9 / 10)
        * _stencil_shift(halo, -1, -2, 9, 'periodic') +
        (9 / 10)
        * _stencil_shift(halo, 1, -2, 9, 'periodic') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -2, 9, 'periodic') +
        (7 / 55)
        * _stencil_shift(halo, 3, -2, 9, 'periodic') +
        (-63 / 1430)
        * _stencil_shift(halo, 4, -2, 9, 'periodic') +
        (9 / 715)
        * _stencil_shift(halo, 5, -2, 9, 'periodic') +
        (-2 / 715)
        * _stencil_shift(halo, 6, -2, 9, 'periodic') +
        (9 / 20020)
        * _stencil_shift(halo, 7, -2, 9, 'periodic') +
        (-9 / 194480)
        * _stencil_shift(halo, 8, -2, 9, 'periodic') +
        (1 / 437580)
        * _stencil_shift(halo, 9, -2, 9, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 18, -2, 'periodic'] = _fd_d1_a18_axis2_periodic


def _fd_d1_a18_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 18, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 9, 'zero', 1)
    result = (
        (-1 / 437580)
        * _stencil_shift(halo, -9, -2, 9, 'zero') +
        (9 / 194480)
        * _stencil_shift(halo, -8, -2, 9, 'zero') +
        (-9 / 20020)
        * _stencil_shift(halo, -7, -2, 9, 'zero') +
        (2 / 715)
        * _stencil_shift(halo, -6, -2, 9, 'zero') +
        (-9 / 715)
        * _stencil_shift(halo, -5, -2, 9, 'zero') +
        (63 / 1430)
        * _stencil_shift(halo, -4, -2, 9, 'zero') +
        (-7 / 55)
        * _stencil_shift(halo, -3, -2, 9, 'zero') +
        (18 / 55)
        * _stencil_shift(halo, -2, -2, 9, 'zero') +
        (-9 / 10)
        * _stencil_shift(halo, -1, -2, 9, 'zero') +
        (9 / 10)
        * _stencil_shift(halo, 1, -2, 9, 'zero') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -2, 9, 'zero') +
        (7 / 55)
        * _stencil_shift(halo, 3, -2, 9, 'zero') +
        (-63 / 1430)
        * _stencil_shift(halo, 4, -2, 9, 'zero') +
        (9 / 715)
        * _stencil_shift(halo, 5, -2, 9, 'zero') +
        (-2 / 715)
        * _stencil_shift(halo, 6, -2, 9, 'zero') +
        (9 / 20020)
        * _stencil_shift(halo, 7, -2, 9, 'zero') +
        (-9 / 194480)
        * _stencil_shift(halo, 8, -2, 9, 'zero') +
        (1 / 437580)
        * _stencil_shift(halo, 9, -2, 9, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 18, -2, 'zero'] = _fd_d1_a18_axis2_zero


def _fd_d1_a18_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 18, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 9, 'reflect', 1)
    result = (
        (-1 / 437580)
        * _stencil_shift(halo, -9, -2, 9, 'reflect') +
        (9 / 194480)
        * _stencil_shift(halo, -8, -2, 9, 'reflect') +
        (-9 / 20020)
        * _stencil_shift(halo, -7, -2, 9, 'reflect') +
        (2 / 715)
        * _stencil_shift(halo, -6, -2, 9, 'reflect') +
        (-9 / 715)
        * _stencil_shift(halo, -5, -2, 9, 'reflect') +
        (63 / 1430)
        * _stencil_shift(halo, -4, -2, 9, 'reflect') +
        (-7 / 55)
        * _stencil_shift(halo, -3, -2, 9, 'reflect') +
        (18 / 55)
        * _stencil_shift(halo, -2, -2, 9, 'reflect') +
        (-9 / 10)
        * _stencil_shift(halo, -1, -2, 9, 'reflect') +
        (9 / 10)
        * _stencil_shift(halo, 1, -2, 9, 'reflect') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -2, 9, 'reflect') +
        (7 / 55)
        * _stencil_shift(halo, 3, -2, 9, 'reflect') +
        (-63 / 1430)
        * _stencil_shift(halo, 4, -2, 9, 'reflect') +
        (9 / 715)
        * _stencil_shift(halo, 5, -2, 9, 'reflect') +
        (-2 / 715)
        * _stencil_shift(halo, 6, -2, 9, 'reflect') +
        (9 / 20020)
        * _stencil_shift(halo, 7, -2, 9, 'reflect') +
        (-9 / 194480)
        * _stencil_shift(halo, 8, -2, 9, 'reflect') +
        (1 / 437580)
        * _stencil_shift(halo, 9, -2, 9, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 18, -2, 'reflect'] = _fd_d1_a18_axis2_reflect


def _fd_d1_a18_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 18, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 9, 'periodic', 1)
    result = (
        (-1 / 437580)
        * _stencil_shift(halo, -9, -1, 9, 'periodic') +
        (9 / 194480)
        * _stencil_shift(halo, -8, -1, 9, 'periodic') +
        (-9 / 20020)
        * _stencil_shift(halo, -7, -1, 9, 'periodic') +
        (2 / 715)
        * _stencil_shift(halo, -6, -1, 9, 'periodic') +
        (-9 / 715)
        * _stencil_shift(halo, -5, -1, 9, 'periodic') +
        (63 / 1430)
        * _stencil_shift(halo, -4, -1, 9, 'periodic') +
        (-7 / 55)
        * _stencil_shift(halo, -3, -1, 9, 'periodic') +
        (18 / 55)
        * _stencil_shift(halo, -2, -1, 9, 'periodic') +
        (-9 / 10)
        * _stencil_shift(halo, -1, -1, 9, 'periodic') +
        (9 / 10)
        * _stencil_shift(halo, 1, -1, 9, 'periodic') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -1, 9, 'periodic') +
        (7 / 55)
        * _stencil_shift(halo, 3, -1, 9, 'periodic') +
        (-63 / 1430)
        * _stencil_shift(halo, 4, -1, 9, 'periodic') +
        (9 / 715)
        * _stencil_shift(halo, 5, -1, 9, 'periodic') +
        (-2 / 715)
        * _stencil_shift(halo, 6, -1, 9, 'periodic') +
        (9 / 20020)
        * _stencil_shift(halo, 7, -1, 9, 'periodic') +
        (-9 / 194480)
        * _stencil_shift(halo, 8, -1, 9, 'periodic') +
        (1 / 437580)
        * _stencil_shift(halo, 9, -1, 9, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 18, -1, 'periodic'] = _fd_d1_a18_axis1_periodic


def _fd_d1_a18_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 18, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 9, 'zero', 1)
    result = (
        (-1 / 437580)
        * _stencil_shift(halo, -9, -1, 9, 'zero') +
        (9 / 194480)
        * _stencil_shift(halo, -8, -1, 9, 'zero') +
        (-9 / 20020)
        * _stencil_shift(halo, -7, -1, 9, 'zero') +
        (2 / 715)
        * _stencil_shift(halo, -6, -1, 9, 'zero') +
        (-9 / 715)
        * _stencil_shift(halo, -5, -1, 9, 'zero') +
        (63 / 1430)
        * _stencil_shift(halo, -4, -1, 9, 'zero') +
        (-7 / 55)
        * _stencil_shift(halo, -3, -1, 9, 'zero') +
        (18 / 55)
        * _stencil_shift(halo, -2, -1, 9, 'zero') +
        (-9 / 10)
        * _stencil_shift(halo, -1, -1, 9, 'zero') +
        (9 / 10)
        * _stencil_shift(halo, 1, -1, 9, 'zero') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -1, 9, 'zero') +
        (7 / 55)
        * _stencil_shift(halo, 3, -1, 9, 'zero') +
        (-63 / 1430)
        * _stencil_shift(halo, 4, -1, 9, 'zero') +
        (9 / 715)
        * _stencil_shift(halo, 5, -1, 9, 'zero') +
        (-2 / 715)
        * _stencil_shift(halo, 6, -1, 9, 'zero') +
        (9 / 20020)
        * _stencil_shift(halo, 7, -1, 9, 'zero') +
        (-9 / 194480)
        * _stencil_shift(halo, 8, -1, 9, 'zero') +
        (1 / 437580)
        * _stencil_shift(halo, 9, -1, 9, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 18, -1, 'zero'] = _fd_d1_a18_axis1_zero


def _fd_d1_a18_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 18, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 9, 'reflect', 1)
    result = (
        (-1 / 437580)
        * _stencil_shift(halo, -9, -1, 9, 'reflect') +
        (9 / 194480)
        * _stencil_shift(halo, -8, -1, 9, 'reflect') +
        (-9 / 20020)
        * _stencil_shift(halo, -7, -1, 9, 'reflect') +
        (2 / 715)
        * _stencil_shift(halo, -6, -1, 9, 'reflect') +
        (-9 / 715)
        * _stencil_shift(halo, -5, -1, 9, 'reflect') +
        (63 / 1430)
        * _stencil_shift(halo, -4, -1, 9, 'reflect') +
        (-7 / 55)
        * _stencil_shift(halo, -3, -1, 9, 'reflect') +
        (18 / 55)
        * _stencil_shift(halo, -2, -1, 9, 'reflect') +
        (-9 / 10)
        * _stencil_shift(halo, -1, -1, 9, 'reflect') +
        (9 / 10)
        * _stencil_shift(halo, 1, -1, 9, 'reflect') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -1, 9, 'reflect') +
        (7 / 55)
        * _stencil_shift(halo, 3, -1, 9, 'reflect') +
        (-63 / 1430)
        * _stencil_shift(halo, 4, -1, 9, 'reflect') +
        (9 / 715)
        * _stencil_shift(halo, 5, -1, 9, 'reflect') +
        (-2 / 715)
        * _stencil_shift(halo, 6, -1, 9, 'reflect') +
        (9 / 20020)
        * _stencil_shift(halo, 7, -1, 9, 'reflect') +
        (-9 / 194480)
        * _stencil_shift(halo, 8, -1, 9, 'reflect') +
        (1 / 437580)
        * _stencil_shift(halo, 9, -1, 9, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 18, -1, 'reflect'] = _fd_d1_a18_axis1_reflect


STENCIL_MOMENTS[1, 20] = (
    (-10, 1, 1847560),
    (-9, -5, 415701),
    (-8, 5, 38896),
    (-7, -15, 17017),
    (-6, 5, 1144),
    (-5, -12, 715),
    (-4, 15, 286),
    (-3, -20, 143),
    (-2, 15, 44),
    (-1, -10, 11),
    (0, 0, 1),
    (1, 10, 11),
    (2, -15, 44),
    (3, 20, 143),
    (4, -15, 286),
    (5, 12, 715),
    (6, -5, 1144),
    (7, 15, 17017),
    (8, -5, 38896),
    (9, 5, 415701),
    (10, -1, 1847560),
)

def _fd_d1_a20_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 20, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 10, 'periodic', 1)
    result = (
        (1 / 1847560)
        * _stencil_shift(halo, -10, -4, 10, 'periodic') +
        (-5 / 415701)
        * _stencil_shift(halo, -9, -4, 10, 'periodic') +
        (5 / 38896)
        * _stencil_shift(halo, -8, -4, 10, 'periodic') +
        (-15 / 17017)
        * _stencil_shift(halo, -7, -4, 10, 'periodic') +
        (5 / 1144)
        * _stencil_shift(halo, -6, -4, 10, 'periodic') +
        (-12 / 715)
        * _stencil_shift(halo, -5, -4, 10, 'periodic') +
        (15 / 286)
        * _stencil_shift(halo, -4, -4, 10, 'periodic') +
        (-20 / 143)
        * _stencil_shift(halo, -3, -4, 10, 'periodic') +
        (15 / 44)
        * _stencil_shift(halo, -2, -4, 10, 'periodic') +
        (-10 / 11)
        * _stencil_shift(halo, -1, -4, 10, 'periodic') +
        (10 / 11)
        * _stencil_shift(halo, 1, -4, 10, 'periodic') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -4, 10, 'periodic') +
        (20 / 143)
        * _stencil_shift(halo, 3, -4, 10, 'periodic') +
        (-15 / 286)
        * _stencil_shift(halo, 4, -4, 10, 'periodic') +
        (12 / 715)
        * _stencil_shift(halo, 5, -4, 10, 'periodic') +
        (-5 / 1144)
        * _stencil_shift(halo, 6, -4, 10, 'periodic') +
        (15 / 17017)
        * _stencil_shift(halo, 7, -4, 10, 'periodic') +
        (-5 / 38896)
        * _stencil_shift(halo, 8, -4, 10, 'periodic') +
        (5 / 415701)
        * _stencil_shift(halo, 9, -4, 10, 'periodic') +
        (-1 / 1847560)
        * _stencil_shift(halo, 10, -4, 10, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 20, -4, 'periodic'] = _fd_d1_a20_axis4_periodic


def _fd_d1_a20_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 20, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 10, 'zero', 1)
    result = (
        (1 / 1847560)
        * _stencil_shift(halo, -10, -4, 10, 'zero') +
        (-5 / 415701)
        * _stencil_shift(halo, -9, -4, 10, 'zero') +
        (5 / 38896)
        * _stencil_shift(halo, -8, -4, 10, 'zero') +
        (-15 / 17017)
        * _stencil_shift(halo, -7, -4, 10, 'zero') +
        (5 / 1144)
        * _stencil_shift(halo, -6, -4, 10, 'zero') +
        (-12 / 715)
        * _stencil_shift(halo, -5, -4, 10, 'zero') +
        (15 / 286)
        * _stencil_shift(halo, -4, -4, 10, 'zero') +
        (-20 / 143)
        * _stencil_shift(halo, -3, -4, 10, 'zero') +
        (15 / 44)
        * _stencil_shift(halo, -2, -4, 10, 'zero') +
        (-10 / 11)
        * _stencil_shift(halo, -1, -4, 10, 'zero') +
        (10 / 11)
        * _stencil_shift(halo, 1, -4, 10, 'zero') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -4, 10, 'zero') +
        (20 / 143)
        * _stencil_shift(halo, 3, -4, 10, 'zero') +
        (-15 / 286)
        * _stencil_shift(halo, 4, -4, 10, 'zero') +
        (12 / 715)
        * _stencil_shift(halo, 5, -4, 10, 'zero') +
        (-5 / 1144)
        * _stencil_shift(halo, 6, -4, 10, 'zero') +
        (15 / 17017)
        * _stencil_shift(halo, 7, -4, 10, 'zero') +
        (-5 / 38896)
        * _stencil_shift(halo, 8, -4, 10, 'zero') +
        (5 / 415701)
        * _stencil_shift(halo, 9, -4, 10, 'zero') +
        (-1 / 1847560)
        * _stencil_shift(halo, 10, -4, 10, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 20, -4, 'zero'] = _fd_d1_a20_axis4_zero


def _fd_d1_a20_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 20, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 10, 'reflect', 1)
    result = (
        (1 / 1847560)
        * _stencil_shift(halo, -10, -4, 10, 'reflect') +
        (-5 / 415701)
        * _stencil_shift(halo, -9, -4, 10, 'reflect') +
        (5 / 38896)
        * _stencil_shift(halo, -8, -4, 10, 'reflect') +
        (-15 / 17017)
        * _stencil_shift(halo, -7, -4, 10, 'reflect') +
        (5 / 1144)
        * _stencil_shift(halo, -6, -4, 10, 'reflect') +
        (-12 / 715)
        * _stencil_shift(halo, -5, -4, 10, 'reflect') +
        (15 / 286)
        * _stencil_shift(halo, -4, -4, 10, 'reflect') +
        (-20 / 143)
        * _stencil_shift(halo, -3, -4, 10, 'reflect') +
        (15 / 44)
        * _stencil_shift(halo, -2, -4, 10, 'reflect') +
        (-10 / 11)
        * _stencil_shift(halo, -1, -4, 10, 'reflect') +
        (10 / 11)
        * _stencil_shift(halo, 1, -4, 10, 'reflect') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -4, 10, 'reflect') +
        (20 / 143)
        * _stencil_shift(halo, 3, -4, 10, 'reflect') +
        (-15 / 286)
        * _stencil_shift(halo, 4, -4, 10, 'reflect') +
        (12 / 715)
        * _stencil_shift(halo, 5, -4, 10, 'reflect') +
        (-5 / 1144)
        * _stencil_shift(halo, 6, -4, 10, 'reflect') +
        (15 / 17017)
        * _stencil_shift(halo, 7, -4, 10, 'reflect') +
        (-5 / 38896)
        * _stencil_shift(halo, 8, -4, 10, 'reflect') +
        (5 / 415701)
        * _stencil_shift(halo, 9, -4, 10, 'reflect') +
        (-1 / 1847560)
        * _stencil_shift(halo, 10, -4, 10, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 20, -4, 'reflect'] = _fd_d1_a20_axis4_reflect


def _fd_d1_a20_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 20, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 10, 'periodic', 1)
    result = (
        (1 / 1847560)
        * _stencil_shift(halo, -10, -3, 10, 'periodic') +
        (-5 / 415701)
        * _stencil_shift(halo, -9, -3, 10, 'periodic') +
        (5 / 38896)
        * _stencil_shift(halo, -8, -3, 10, 'periodic') +
        (-15 / 17017)
        * _stencil_shift(halo, -7, -3, 10, 'periodic') +
        (5 / 1144)
        * _stencil_shift(halo, -6, -3, 10, 'periodic') +
        (-12 / 715)
        * _stencil_shift(halo, -5, -3, 10, 'periodic') +
        (15 / 286)
        * _stencil_shift(halo, -4, -3, 10, 'periodic') +
        (-20 / 143)
        * _stencil_shift(halo, -3, -3, 10, 'periodic') +
        (15 / 44)
        * _stencil_shift(halo, -2, -3, 10, 'periodic') +
        (-10 / 11)
        * _stencil_shift(halo, -1, -3, 10, 'periodic') +
        (10 / 11)
        * _stencil_shift(halo, 1, -3, 10, 'periodic') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -3, 10, 'periodic') +
        (20 / 143)
        * _stencil_shift(halo, 3, -3, 10, 'periodic') +
        (-15 / 286)
        * _stencil_shift(halo, 4, -3, 10, 'periodic') +
        (12 / 715)
        * _stencil_shift(halo, 5, -3, 10, 'periodic') +
        (-5 / 1144)
        * _stencil_shift(halo, 6, -3, 10, 'periodic') +
        (15 / 17017)
        * _stencil_shift(halo, 7, -3, 10, 'periodic') +
        (-5 / 38896)
        * _stencil_shift(halo, 8, -3, 10, 'periodic') +
        (5 / 415701)
        * _stencil_shift(halo, 9, -3, 10, 'periodic') +
        (-1 / 1847560)
        * _stencil_shift(halo, 10, -3, 10, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 20, -3, 'periodic'] = _fd_d1_a20_axis3_periodic


def _fd_d1_a20_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 20, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 10, 'zero', 1)
    result = (
        (1 / 1847560)
        * _stencil_shift(halo, -10, -3, 10, 'zero') +
        (-5 / 415701)
        * _stencil_shift(halo, -9, -3, 10, 'zero') +
        (5 / 38896)
        * _stencil_shift(halo, -8, -3, 10, 'zero') +
        (-15 / 17017)
        * _stencil_shift(halo, -7, -3, 10, 'zero') +
        (5 / 1144)
        * _stencil_shift(halo, -6, -3, 10, 'zero') +
        (-12 / 715)
        * _stencil_shift(halo, -5, -3, 10, 'zero') +
        (15 / 286)
        * _stencil_shift(halo, -4, -3, 10, 'zero') +
        (-20 / 143)
        * _stencil_shift(halo, -3, -3, 10, 'zero') +
        (15 / 44)
        * _stencil_shift(halo, -2, -3, 10, 'zero') +
        (-10 / 11)
        * _stencil_shift(halo, -1, -3, 10, 'zero') +
        (10 / 11)
        * _stencil_shift(halo, 1, -3, 10, 'zero') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -3, 10, 'zero') +
        (20 / 143)
        * _stencil_shift(halo, 3, -3, 10, 'zero') +
        (-15 / 286)
        * _stencil_shift(halo, 4, -3, 10, 'zero') +
        (12 / 715)
        * _stencil_shift(halo, 5, -3, 10, 'zero') +
        (-5 / 1144)
        * _stencil_shift(halo, 6, -3, 10, 'zero') +
        (15 / 17017)
        * _stencil_shift(halo, 7, -3, 10, 'zero') +
        (-5 / 38896)
        * _stencil_shift(halo, 8, -3, 10, 'zero') +
        (5 / 415701)
        * _stencil_shift(halo, 9, -3, 10, 'zero') +
        (-1 / 1847560)
        * _stencil_shift(halo, 10, -3, 10, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 20, -3, 'zero'] = _fd_d1_a20_axis3_zero


def _fd_d1_a20_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 20, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 10, 'reflect', 1)
    result = (
        (1 / 1847560)
        * _stencil_shift(halo, -10, -3, 10, 'reflect') +
        (-5 / 415701)
        * _stencil_shift(halo, -9, -3, 10, 'reflect') +
        (5 / 38896)
        * _stencil_shift(halo, -8, -3, 10, 'reflect') +
        (-15 / 17017)
        * _stencil_shift(halo, -7, -3, 10, 'reflect') +
        (5 / 1144)
        * _stencil_shift(halo, -6, -3, 10, 'reflect') +
        (-12 / 715)
        * _stencil_shift(halo, -5, -3, 10, 'reflect') +
        (15 / 286)
        * _stencil_shift(halo, -4, -3, 10, 'reflect') +
        (-20 / 143)
        * _stencil_shift(halo, -3, -3, 10, 'reflect') +
        (15 / 44)
        * _stencil_shift(halo, -2, -3, 10, 'reflect') +
        (-10 / 11)
        * _stencil_shift(halo, -1, -3, 10, 'reflect') +
        (10 / 11)
        * _stencil_shift(halo, 1, -3, 10, 'reflect') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -3, 10, 'reflect') +
        (20 / 143)
        * _stencil_shift(halo, 3, -3, 10, 'reflect') +
        (-15 / 286)
        * _stencil_shift(halo, 4, -3, 10, 'reflect') +
        (12 / 715)
        * _stencil_shift(halo, 5, -3, 10, 'reflect') +
        (-5 / 1144)
        * _stencil_shift(halo, 6, -3, 10, 'reflect') +
        (15 / 17017)
        * _stencil_shift(halo, 7, -3, 10, 'reflect') +
        (-5 / 38896)
        * _stencil_shift(halo, 8, -3, 10, 'reflect') +
        (5 / 415701)
        * _stencil_shift(halo, 9, -3, 10, 'reflect') +
        (-1 / 1847560)
        * _stencil_shift(halo, 10, -3, 10, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 20, -3, 'reflect'] = _fd_d1_a20_axis3_reflect


def _fd_d1_a20_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 20, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 10, 'periodic', 1)
    result = (
        (1 / 1847560)
        * _stencil_shift(halo, -10, -2, 10, 'periodic') +
        (-5 / 415701)
        * _stencil_shift(halo, -9, -2, 10, 'periodic') +
        (5 / 38896)
        * _stencil_shift(halo, -8, -2, 10, 'periodic') +
        (-15 / 17017)
        * _stencil_shift(halo, -7, -2, 10, 'periodic') +
        (5 / 1144)
        * _stencil_shift(halo, -6, -2, 10, 'periodic') +
        (-12 / 715)
        * _stencil_shift(halo, -5, -2, 10, 'periodic') +
        (15 / 286)
        * _stencil_shift(halo, -4, -2, 10, 'periodic') +
        (-20 / 143)
        * _stencil_shift(halo, -3, -2, 10, 'periodic') +
        (15 / 44)
        * _stencil_shift(halo, -2, -2, 10, 'periodic') +
        (-10 / 11)
        * _stencil_shift(halo, -1, -2, 10, 'periodic') +
        (10 / 11)
        * _stencil_shift(halo, 1, -2, 10, 'periodic') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -2, 10, 'periodic') +
        (20 / 143)
        * _stencil_shift(halo, 3, -2, 10, 'periodic') +
        (-15 / 286)
        * _stencil_shift(halo, 4, -2, 10, 'periodic') +
        (12 / 715)
        * _stencil_shift(halo, 5, -2, 10, 'periodic') +
        (-5 / 1144)
        * _stencil_shift(halo, 6, -2, 10, 'periodic') +
        (15 / 17017)
        * _stencil_shift(halo, 7, -2, 10, 'periodic') +
        (-5 / 38896)
        * _stencil_shift(halo, 8, -2, 10, 'periodic') +
        (5 / 415701)
        * _stencil_shift(halo, 9, -2, 10, 'periodic') +
        (-1 / 1847560)
        * _stencil_shift(halo, 10, -2, 10, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 20, -2, 'periodic'] = _fd_d1_a20_axis2_periodic


def _fd_d1_a20_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 20, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 10, 'zero', 1)
    result = (
        (1 / 1847560)
        * _stencil_shift(halo, -10, -2, 10, 'zero') +
        (-5 / 415701)
        * _stencil_shift(halo, -9, -2, 10, 'zero') +
        (5 / 38896)
        * _stencil_shift(halo, -8, -2, 10, 'zero') +
        (-15 / 17017)
        * _stencil_shift(halo, -7, -2, 10, 'zero') +
        (5 / 1144)
        * _stencil_shift(halo, -6, -2, 10, 'zero') +
        (-12 / 715)
        * _stencil_shift(halo, -5, -2, 10, 'zero') +
        (15 / 286)
        * _stencil_shift(halo, -4, -2, 10, 'zero') +
        (-20 / 143)
        * _stencil_shift(halo, -3, -2, 10, 'zero') +
        (15 / 44)
        * _stencil_shift(halo, -2, -2, 10, 'zero') +
        (-10 / 11)
        * _stencil_shift(halo, -1, -2, 10, 'zero') +
        (10 / 11)
        * _stencil_shift(halo, 1, -2, 10, 'zero') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -2, 10, 'zero') +
        (20 / 143)
        * _stencil_shift(halo, 3, -2, 10, 'zero') +
        (-15 / 286)
        * _stencil_shift(halo, 4, -2, 10, 'zero') +
        (12 / 715)
        * _stencil_shift(halo, 5, -2, 10, 'zero') +
        (-5 / 1144)
        * _stencil_shift(halo, 6, -2, 10, 'zero') +
        (15 / 17017)
        * _stencil_shift(halo, 7, -2, 10, 'zero') +
        (-5 / 38896)
        * _stencil_shift(halo, 8, -2, 10, 'zero') +
        (5 / 415701)
        * _stencil_shift(halo, 9, -2, 10, 'zero') +
        (-1 / 1847560)
        * _stencil_shift(halo, 10, -2, 10, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 20, -2, 'zero'] = _fd_d1_a20_axis2_zero


def _fd_d1_a20_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 20, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 10, 'reflect', 1)
    result = (
        (1 / 1847560)
        * _stencil_shift(halo, -10, -2, 10, 'reflect') +
        (-5 / 415701)
        * _stencil_shift(halo, -9, -2, 10, 'reflect') +
        (5 / 38896)
        * _stencil_shift(halo, -8, -2, 10, 'reflect') +
        (-15 / 17017)
        * _stencil_shift(halo, -7, -2, 10, 'reflect') +
        (5 / 1144)
        * _stencil_shift(halo, -6, -2, 10, 'reflect') +
        (-12 / 715)
        * _stencil_shift(halo, -5, -2, 10, 'reflect') +
        (15 / 286)
        * _stencil_shift(halo, -4, -2, 10, 'reflect') +
        (-20 / 143)
        * _stencil_shift(halo, -3, -2, 10, 'reflect') +
        (15 / 44)
        * _stencil_shift(halo, -2, -2, 10, 'reflect') +
        (-10 / 11)
        * _stencil_shift(halo, -1, -2, 10, 'reflect') +
        (10 / 11)
        * _stencil_shift(halo, 1, -2, 10, 'reflect') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -2, 10, 'reflect') +
        (20 / 143)
        * _stencil_shift(halo, 3, -2, 10, 'reflect') +
        (-15 / 286)
        * _stencil_shift(halo, 4, -2, 10, 'reflect') +
        (12 / 715)
        * _stencil_shift(halo, 5, -2, 10, 'reflect') +
        (-5 / 1144)
        * _stencil_shift(halo, 6, -2, 10, 'reflect') +
        (15 / 17017)
        * _stencil_shift(halo, 7, -2, 10, 'reflect') +
        (-5 / 38896)
        * _stencil_shift(halo, 8, -2, 10, 'reflect') +
        (5 / 415701)
        * _stencil_shift(halo, 9, -2, 10, 'reflect') +
        (-1 / 1847560)
        * _stencil_shift(halo, 10, -2, 10, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 20, -2, 'reflect'] = _fd_d1_a20_axis2_reflect


def _fd_d1_a20_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 20, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 10, 'periodic', 1)
    result = (
        (1 / 1847560)
        * _stencil_shift(halo, -10, -1, 10, 'periodic') +
        (-5 / 415701)
        * _stencil_shift(halo, -9, -1, 10, 'periodic') +
        (5 / 38896)
        * _stencil_shift(halo, -8, -1, 10, 'periodic') +
        (-15 / 17017)
        * _stencil_shift(halo, -7, -1, 10, 'periodic') +
        (5 / 1144)
        * _stencil_shift(halo, -6, -1, 10, 'periodic') +
        (-12 / 715)
        * _stencil_shift(halo, -5, -1, 10, 'periodic') +
        (15 / 286)
        * _stencil_shift(halo, -4, -1, 10, 'periodic') +
        (-20 / 143)
        * _stencil_shift(halo, -3, -1, 10, 'periodic') +
        (15 / 44)
        * _stencil_shift(halo, -2, -1, 10, 'periodic') +
        (-10 / 11)
        * _stencil_shift(halo, -1, -1, 10, 'periodic') +
        (10 / 11)
        * _stencil_shift(halo, 1, -1, 10, 'periodic') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -1, 10, 'periodic') +
        (20 / 143)
        * _stencil_shift(halo, 3, -1, 10, 'periodic') +
        (-15 / 286)
        * _stencil_shift(halo, 4, -1, 10, 'periodic') +
        (12 / 715)
        * _stencil_shift(halo, 5, -1, 10, 'periodic') +
        (-5 / 1144)
        * _stencil_shift(halo, 6, -1, 10, 'periodic') +
        (15 / 17017)
        * _stencil_shift(halo, 7, -1, 10, 'periodic') +
        (-5 / 38896)
        * _stencil_shift(halo, 8, -1, 10, 'periodic') +
        (5 / 415701)
        * _stencil_shift(halo, 9, -1, 10, 'periodic') +
        (-1 / 1847560)
        * _stencil_shift(halo, 10, -1, 10, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 20, -1, 'periodic'] = _fd_d1_a20_axis1_periodic


def _fd_d1_a20_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 20, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 10, 'zero', 1)
    result = (
        (1 / 1847560)
        * _stencil_shift(halo, -10, -1, 10, 'zero') +
        (-5 / 415701)
        * _stencil_shift(halo, -9, -1, 10, 'zero') +
        (5 / 38896)
        * _stencil_shift(halo, -8, -1, 10, 'zero') +
        (-15 / 17017)
        * _stencil_shift(halo, -7, -1, 10, 'zero') +
        (5 / 1144)
        * _stencil_shift(halo, -6, -1, 10, 'zero') +
        (-12 / 715)
        * _stencil_shift(halo, -5, -1, 10, 'zero') +
        (15 / 286)
        * _stencil_shift(halo, -4, -1, 10, 'zero') +
        (-20 / 143)
        * _stencil_shift(halo, -3, -1, 10, 'zero') +
        (15 / 44)
        * _stencil_shift(halo, -2, -1, 10, 'zero') +
        (-10 / 11)
        * _stencil_shift(halo, -1, -1, 10, 'zero') +
        (10 / 11)
        * _stencil_shift(halo, 1, -1, 10, 'zero') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -1, 10, 'zero') +
        (20 / 143)
        * _stencil_shift(halo, 3, -1, 10, 'zero') +
        (-15 / 286)
        * _stencil_shift(halo, 4, -1, 10, 'zero') +
        (12 / 715)
        * _stencil_shift(halo, 5, -1, 10, 'zero') +
        (-5 / 1144)
        * _stencil_shift(halo, 6, -1, 10, 'zero') +
        (15 / 17017)
        * _stencil_shift(halo, 7, -1, 10, 'zero') +
        (-5 / 38896)
        * _stencil_shift(halo, 8, -1, 10, 'zero') +
        (5 / 415701)
        * _stencil_shift(halo, 9, -1, 10, 'zero') +
        (-1 / 1847560)
        * _stencil_shift(halo, 10, -1, 10, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 20, -1, 'zero'] = _fd_d1_a20_axis1_zero


def _fd_d1_a20_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 1, accuracy 20, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**1, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 10, 'reflect', 1)
    result = (
        (1 / 1847560)
        * _stencil_shift(halo, -10, -1, 10, 'reflect') +
        (-5 / 415701)
        * _stencil_shift(halo, -9, -1, 10, 'reflect') +
        (5 / 38896)
        * _stencil_shift(halo, -8, -1, 10, 'reflect') +
        (-15 / 17017)
        * _stencil_shift(halo, -7, -1, 10, 'reflect') +
        (5 / 1144)
        * _stencil_shift(halo, -6, -1, 10, 'reflect') +
        (-12 / 715)
        * _stencil_shift(halo, -5, -1, 10, 'reflect') +
        (15 / 286)
        * _stencil_shift(halo, -4, -1, 10, 'reflect') +
        (-20 / 143)
        * _stencil_shift(halo, -3, -1, 10, 'reflect') +
        (15 / 44)
        * _stencil_shift(halo, -2, -1, 10, 'reflect') +
        (-10 / 11)
        * _stencil_shift(halo, -1, -1, 10, 'reflect') +
        (10 / 11)
        * _stencil_shift(halo, 1, -1, 10, 'reflect') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -1, 10, 'reflect') +
        (20 / 143)
        * _stencil_shift(halo, 3, -1, 10, 'reflect') +
        (-15 / 286)
        * _stencil_shift(halo, 4, -1, 10, 'reflect') +
        (12 / 715)
        * _stencil_shift(halo, 5, -1, 10, 'reflect') +
        (-5 / 1144)
        * _stencil_shift(halo, 6, -1, 10, 'reflect') +
        (15 / 17017)
        * _stencil_shift(halo, 7, -1, 10, 'reflect') +
        (-5 / 38896)
        * _stencil_shift(halo, 8, -1, 10, 'reflect') +
        (5 / 415701)
        * _stencil_shift(halo, 9, -1, 10, 'reflect') +
        (-1 / 1847560)
        * _stencil_shift(halo, 10, -1, 10, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[1, 20, -1, 'reflect'] = _fd_d1_a20_axis1_reflect


STENCIL_MOMENTS[2, 2] = (
    (-1, 1, 1),
    (0, -2, 1),
    (1, 1, 1),
)

def _fd_d2_a2_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 2, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 1, 'periodic', 2)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -1, -4, 1, 'periodic') +
        (-2 / 1)
        * _stencil_shift(halo, 0, -4, 1, 'periodic') +
        (1 / 1)
        * _stencil_shift(halo, 1, -4, 1, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 2, -4, 'periodic'] = _fd_d2_a2_axis4_periodic


def _fd_d2_a2_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 2, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 1, 'zero', 2)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -1, -4, 1, 'zero') +
        (-2 / 1)
        * _stencil_shift(halo, 0, -4, 1, 'zero') +
        (1 / 1)
        * _stencil_shift(halo, 1, -4, 1, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 2, -4, 'zero'] = _fd_d2_a2_axis4_zero


def _fd_d2_a2_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 2, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 1, 'reflect', 2)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -1, -4, 1, 'reflect') +
        (-2 / 1)
        * _stencil_shift(halo, 0, -4, 1, 'reflect') +
        (1 / 1)
        * _stencil_shift(halo, 1, -4, 1, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 2, -4, 'reflect'] = _fd_d2_a2_axis4_reflect


def _fd_d2_a2_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 2, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 1, 'periodic', 2)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -1, -3, 1, 'periodic') +
        (-2 / 1)
        * _stencil_shift(halo, 0, -3, 1, 'periodic') +
        (1 / 1)
        * _stencil_shift(halo, 1, -3, 1, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 2, -3, 'periodic'] = _fd_d2_a2_axis3_periodic


def _fd_d2_a2_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 2, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 1, 'zero', 2)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -1, -3, 1, 'zero') +
        (-2 / 1)
        * _stencil_shift(halo, 0, -3, 1, 'zero') +
        (1 / 1)
        * _stencil_shift(halo, 1, -3, 1, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 2, -3, 'zero'] = _fd_d2_a2_axis3_zero


def _fd_d2_a2_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 2, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 1, 'reflect', 2)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -1, -3, 1, 'reflect') +
        (-2 / 1)
        * _stencil_shift(halo, 0, -3, 1, 'reflect') +
        (1 / 1)
        * _stencil_shift(halo, 1, -3, 1, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 2, -3, 'reflect'] = _fd_d2_a2_axis3_reflect


def _fd_d2_a2_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 2, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 1, 'periodic', 2)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -1, -2, 1, 'periodic') +
        (-2 / 1)
        * _stencil_shift(halo, 0, -2, 1, 'periodic') +
        (1 / 1)
        * _stencil_shift(halo, 1, -2, 1, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 2, -2, 'periodic'] = _fd_d2_a2_axis2_periodic


def _fd_d2_a2_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 2, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 1, 'zero', 2)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -1, -2, 1, 'zero') +
        (-2 / 1)
        * _stencil_shift(halo, 0, -2, 1, 'zero') +
        (1 / 1)
        * _stencil_shift(halo, 1, -2, 1, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 2, -2, 'zero'] = _fd_d2_a2_axis2_zero


def _fd_d2_a2_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 2, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 1, 'reflect', 2)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -1, -2, 1, 'reflect') +
        (-2 / 1)
        * _stencil_shift(halo, 0, -2, 1, 'reflect') +
        (1 / 1)
        * _stencil_shift(halo, 1, -2, 1, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 2, -2, 'reflect'] = _fd_d2_a2_axis2_reflect


def _fd_d2_a2_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 2, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 1, 'periodic', 2)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -1, -1, 1, 'periodic') +
        (-2 / 1)
        * _stencil_shift(halo, 0, -1, 1, 'periodic') +
        (1 / 1)
        * _stencil_shift(halo, 1, -1, 1, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 2, -1, 'periodic'] = _fd_d2_a2_axis1_periodic


def _fd_d2_a2_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 2, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 1, 'zero', 2)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -1, -1, 1, 'zero') +
        (-2 / 1)
        * _stencil_shift(halo, 0, -1, 1, 'zero') +
        (1 / 1)
        * _stencil_shift(halo, 1, -1, 1, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 2, -1, 'zero'] = _fd_d2_a2_axis1_zero


def _fd_d2_a2_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 2, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 2.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 1, 'reflect', 2)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -1, -1, 1, 'reflect') +
        (-2 / 1)
        * _stencil_shift(halo, 0, -1, 1, 'reflect') +
        (1 / 1)
        * _stencil_shift(halo, 1, -1, 1, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 2, -1, 'reflect'] = _fd_d2_a2_axis1_reflect


STENCIL_MOMENTS[2, 4] = (
    (-2, -1, 12),
    (-1, 4, 3),
    (0, -5, 2),
    (1, 4, 3),
    (2, -1, 12),
)

def _fd_d2_a4_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 4, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 2, 'periodic', 2)
    result = (
        (-1 / 12)
        * _stencil_shift(halo, -2, -4, 2, 'periodic') +
        (4 / 3)
        * _stencil_shift(halo, -1, -4, 2, 'periodic') +
        (-5 / 2)
        * _stencil_shift(halo, 0, -4, 2, 'periodic') +
        (4 / 3)
        * _stencil_shift(halo, 1, -4, 2, 'periodic') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -4, 2, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 4, -4, 'periodic'] = _fd_d2_a4_axis4_periodic


def _fd_d2_a4_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 4, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 2, 'zero', 2)
    result = (
        (-1 / 12)
        * _stencil_shift(halo, -2, -4, 2, 'zero') +
        (4 / 3)
        * _stencil_shift(halo, -1, -4, 2, 'zero') +
        (-5 / 2)
        * _stencil_shift(halo, 0, -4, 2, 'zero') +
        (4 / 3)
        * _stencil_shift(halo, 1, -4, 2, 'zero') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -4, 2, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 4, -4, 'zero'] = _fd_d2_a4_axis4_zero


def _fd_d2_a4_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 4, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 2, 'reflect', 2)
    result = (
        (-1 / 12)
        * _stencil_shift(halo, -2, -4, 2, 'reflect') +
        (4 / 3)
        * _stencil_shift(halo, -1, -4, 2, 'reflect') +
        (-5 / 2)
        * _stencil_shift(halo, 0, -4, 2, 'reflect') +
        (4 / 3)
        * _stencil_shift(halo, 1, -4, 2, 'reflect') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -4, 2, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 4, -4, 'reflect'] = _fd_d2_a4_axis4_reflect


def _fd_d2_a4_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 4, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 2, 'periodic', 2)
    result = (
        (-1 / 12)
        * _stencil_shift(halo, -2, -3, 2, 'periodic') +
        (4 / 3)
        * _stencil_shift(halo, -1, -3, 2, 'periodic') +
        (-5 / 2)
        * _stencil_shift(halo, 0, -3, 2, 'periodic') +
        (4 / 3)
        * _stencil_shift(halo, 1, -3, 2, 'periodic') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -3, 2, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 4, -3, 'periodic'] = _fd_d2_a4_axis3_periodic


def _fd_d2_a4_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 4, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 2, 'zero', 2)
    result = (
        (-1 / 12)
        * _stencil_shift(halo, -2, -3, 2, 'zero') +
        (4 / 3)
        * _stencil_shift(halo, -1, -3, 2, 'zero') +
        (-5 / 2)
        * _stencil_shift(halo, 0, -3, 2, 'zero') +
        (4 / 3)
        * _stencil_shift(halo, 1, -3, 2, 'zero') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -3, 2, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 4, -3, 'zero'] = _fd_d2_a4_axis3_zero


def _fd_d2_a4_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 4, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 2, 'reflect', 2)
    result = (
        (-1 / 12)
        * _stencil_shift(halo, -2, -3, 2, 'reflect') +
        (4 / 3)
        * _stencil_shift(halo, -1, -3, 2, 'reflect') +
        (-5 / 2)
        * _stencil_shift(halo, 0, -3, 2, 'reflect') +
        (4 / 3)
        * _stencil_shift(halo, 1, -3, 2, 'reflect') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -3, 2, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 4, -3, 'reflect'] = _fd_d2_a4_axis3_reflect


def _fd_d2_a4_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 4, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 2, 'periodic', 2)
    result = (
        (-1 / 12)
        * _stencil_shift(halo, -2, -2, 2, 'periodic') +
        (4 / 3)
        * _stencil_shift(halo, -1, -2, 2, 'periodic') +
        (-5 / 2)
        * _stencil_shift(halo, 0, -2, 2, 'periodic') +
        (4 / 3)
        * _stencil_shift(halo, 1, -2, 2, 'periodic') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -2, 2, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 4, -2, 'periodic'] = _fd_d2_a4_axis2_periodic


def _fd_d2_a4_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 4, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 2, 'zero', 2)
    result = (
        (-1 / 12)
        * _stencil_shift(halo, -2, -2, 2, 'zero') +
        (4 / 3)
        * _stencil_shift(halo, -1, -2, 2, 'zero') +
        (-5 / 2)
        * _stencil_shift(halo, 0, -2, 2, 'zero') +
        (4 / 3)
        * _stencil_shift(halo, 1, -2, 2, 'zero') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -2, 2, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 4, -2, 'zero'] = _fd_d2_a4_axis2_zero


def _fd_d2_a4_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 4, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 2, 'reflect', 2)
    result = (
        (-1 / 12)
        * _stencil_shift(halo, -2, -2, 2, 'reflect') +
        (4 / 3)
        * _stencil_shift(halo, -1, -2, 2, 'reflect') +
        (-5 / 2)
        * _stencil_shift(halo, 0, -2, 2, 'reflect') +
        (4 / 3)
        * _stencil_shift(halo, 1, -2, 2, 'reflect') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -2, 2, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 4, -2, 'reflect'] = _fd_d2_a4_axis2_reflect


def _fd_d2_a4_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 4, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 2, 'periodic', 2)
    result = (
        (-1 / 12)
        * _stencil_shift(halo, -2, -1, 2, 'periodic') +
        (4 / 3)
        * _stencil_shift(halo, -1, -1, 2, 'periodic') +
        (-5 / 2)
        * _stencil_shift(halo, 0, -1, 2, 'periodic') +
        (4 / 3)
        * _stencil_shift(halo, 1, -1, 2, 'periodic') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -1, 2, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 4, -1, 'periodic'] = _fd_d2_a4_axis1_periodic


def _fd_d2_a4_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 4, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 2, 'zero', 2)
    result = (
        (-1 / 12)
        * _stencil_shift(halo, -2, -1, 2, 'zero') +
        (4 / 3)
        * _stencil_shift(halo, -1, -1, 2, 'zero') +
        (-5 / 2)
        * _stencil_shift(halo, 0, -1, 2, 'zero') +
        (4 / 3)
        * _stencil_shift(halo, 1, -1, 2, 'zero') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -1, 2, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 4, -1, 'zero'] = _fd_d2_a4_axis1_zero


def _fd_d2_a4_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 4, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 2, 'reflect', 2)
    result = (
        (-1 / 12)
        * _stencil_shift(halo, -2, -1, 2, 'reflect') +
        (4 / 3)
        * _stencil_shift(halo, -1, -1, 2, 'reflect') +
        (-5 / 2)
        * _stencil_shift(halo, 0, -1, 2, 'reflect') +
        (4 / 3)
        * _stencil_shift(halo, 1, -1, 2, 'reflect') +
        (-1 / 12)
        * _stencil_shift(halo, 2, -1, 2, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 4, -1, 'reflect'] = _fd_d2_a4_axis1_reflect


STENCIL_MOMENTS[2, 6] = (
    (-3, 1, 90),
    (-2, -3, 20),
    (-1, 3, 2),
    (0, -49, 18),
    (1, 3, 2),
    (2, -3, 20),
    (3, 1, 90),
)

def _fd_d2_a6_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 6, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 3, 'periodic', 2)
    result = (
        (1 / 90)
        * _stencil_shift(halo, -3, -4, 3, 'periodic') +
        (-3 / 20)
        * _stencil_shift(halo, -2, -4, 3, 'periodic') +
        (3 / 2)
        * _stencil_shift(halo, -1, -4, 3, 'periodic') +
        (-49 / 18)
        * _stencil_shift(halo, 0, -4, 3, 'periodic') +
        (3 / 2)
        * _stencil_shift(halo, 1, -4, 3, 'periodic') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -4, 3, 'periodic') +
        (1 / 90)
        * _stencil_shift(halo, 3, -4, 3, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 6, -4, 'periodic'] = _fd_d2_a6_axis4_periodic


def _fd_d2_a6_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 6, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 3, 'zero', 2)
    result = (
        (1 / 90)
        * _stencil_shift(halo, -3, -4, 3, 'zero') +
        (-3 / 20)
        * _stencil_shift(halo, -2, -4, 3, 'zero') +
        (3 / 2)
        * _stencil_shift(halo, -1, -4, 3, 'zero') +
        (-49 / 18)
        * _stencil_shift(halo, 0, -4, 3, 'zero') +
        (3 / 2)
        * _stencil_shift(halo, 1, -4, 3, 'zero') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -4, 3, 'zero') +
        (1 / 90)
        * _stencil_shift(halo, 3, -4, 3, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 6, -4, 'zero'] = _fd_d2_a6_axis4_zero


def _fd_d2_a6_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 6, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 3, 'reflect', 2)
    result = (
        (1 / 90)
        * _stencil_shift(halo, -3, -4, 3, 'reflect') +
        (-3 / 20)
        * _stencil_shift(halo, -2, -4, 3, 'reflect') +
        (3 / 2)
        * _stencil_shift(halo, -1, -4, 3, 'reflect') +
        (-49 / 18)
        * _stencil_shift(halo, 0, -4, 3, 'reflect') +
        (3 / 2)
        * _stencil_shift(halo, 1, -4, 3, 'reflect') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -4, 3, 'reflect') +
        (1 / 90)
        * _stencil_shift(halo, 3, -4, 3, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 6, -4, 'reflect'] = _fd_d2_a6_axis4_reflect


def _fd_d2_a6_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 6, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 3, 'periodic', 2)
    result = (
        (1 / 90)
        * _stencil_shift(halo, -3, -3, 3, 'periodic') +
        (-3 / 20)
        * _stencil_shift(halo, -2, -3, 3, 'periodic') +
        (3 / 2)
        * _stencil_shift(halo, -1, -3, 3, 'periodic') +
        (-49 / 18)
        * _stencil_shift(halo, 0, -3, 3, 'periodic') +
        (3 / 2)
        * _stencil_shift(halo, 1, -3, 3, 'periodic') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -3, 3, 'periodic') +
        (1 / 90)
        * _stencil_shift(halo, 3, -3, 3, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 6, -3, 'periodic'] = _fd_d2_a6_axis3_periodic


def _fd_d2_a6_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 6, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 3, 'zero', 2)
    result = (
        (1 / 90)
        * _stencil_shift(halo, -3, -3, 3, 'zero') +
        (-3 / 20)
        * _stencil_shift(halo, -2, -3, 3, 'zero') +
        (3 / 2)
        * _stencil_shift(halo, -1, -3, 3, 'zero') +
        (-49 / 18)
        * _stencil_shift(halo, 0, -3, 3, 'zero') +
        (3 / 2)
        * _stencil_shift(halo, 1, -3, 3, 'zero') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -3, 3, 'zero') +
        (1 / 90)
        * _stencil_shift(halo, 3, -3, 3, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 6, -3, 'zero'] = _fd_d2_a6_axis3_zero


def _fd_d2_a6_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 6, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 3, 'reflect', 2)
    result = (
        (1 / 90)
        * _stencil_shift(halo, -3, -3, 3, 'reflect') +
        (-3 / 20)
        * _stencil_shift(halo, -2, -3, 3, 'reflect') +
        (3 / 2)
        * _stencil_shift(halo, -1, -3, 3, 'reflect') +
        (-49 / 18)
        * _stencil_shift(halo, 0, -3, 3, 'reflect') +
        (3 / 2)
        * _stencil_shift(halo, 1, -3, 3, 'reflect') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -3, 3, 'reflect') +
        (1 / 90)
        * _stencil_shift(halo, 3, -3, 3, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 6, -3, 'reflect'] = _fd_d2_a6_axis3_reflect


def _fd_d2_a6_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 6, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 3, 'periodic', 2)
    result = (
        (1 / 90)
        * _stencil_shift(halo, -3, -2, 3, 'periodic') +
        (-3 / 20)
        * _stencil_shift(halo, -2, -2, 3, 'periodic') +
        (3 / 2)
        * _stencil_shift(halo, -1, -2, 3, 'periodic') +
        (-49 / 18)
        * _stencil_shift(halo, 0, -2, 3, 'periodic') +
        (3 / 2)
        * _stencil_shift(halo, 1, -2, 3, 'periodic') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -2, 3, 'periodic') +
        (1 / 90)
        * _stencil_shift(halo, 3, -2, 3, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 6, -2, 'periodic'] = _fd_d2_a6_axis2_periodic


def _fd_d2_a6_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 6, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 3, 'zero', 2)
    result = (
        (1 / 90)
        * _stencil_shift(halo, -3, -2, 3, 'zero') +
        (-3 / 20)
        * _stencil_shift(halo, -2, -2, 3, 'zero') +
        (3 / 2)
        * _stencil_shift(halo, -1, -2, 3, 'zero') +
        (-49 / 18)
        * _stencil_shift(halo, 0, -2, 3, 'zero') +
        (3 / 2)
        * _stencil_shift(halo, 1, -2, 3, 'zero') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -2, 3, 'zero') +
        (1 / 90)
        * _stencil_shift(halo, 3, -2, 3, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 6, -2, 'zero'] = _fd_d2_a6_axis2_zero


def _fd_d2_a6_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 6, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 3, 'reflect', 2)
    result = (
        (1 / 90)
        * _stencil_shift(halo, -3, -2, 3, 'reflect') +
        (-3 / 20)
        * _stencil_shift(halo, -2, -2, 3, 'reflect') +
        (3 / 2)
        * _stencil_shift(halo, -1, -2, 3, 'reflect') +
        (-49 / 18)
        * _stencil_shift(halo, 0, -2, 3, 'reflect') +
        (3 / 2)
        * _stencil_shift(halo, 1, -2, 3, 'reflect') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -2, 3, 'reflect') +
        (1 / 90)
        * _stencil_shift(halo, 3, -2, 3, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 6, -2, 'reflect'] = _fd_d2_a6_axis2_reflect


def _fd_d2_a6_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 6, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 3, 'periodic', 2)
    result = (
        (1 / 90)
        * _stencil_shift(halo, -3, -1, 3, 'periodic') +
        (-3 / 20)
        * _stencil_shift(halo, -2, -1, 3, 'periodic') +
        (3 / 2)
        * _stencil_shift(halo, -1, -1, 3, 'periodic') +
        (-49 / 18)
        * _stencil_shift(halo, 0, -1, 3, 'periodic') +
        (3 / 2)
        * _stencil_shift(halo, 1, -1, 3, 'periodic') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -1, 3, 'periodic') +
        (1 / 90)
        * _stencil_shift(halo, 3, -1, 3, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 6, -1, 'periodic'] = _fd_d2_a6_axis1_periodic


def _fd_d2_a6_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 6, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 3, 'zero', 2)
    result = (
        (1 / 90)
        * _stencil_shift(halo, -3, -1, 3, 'zero') +
        (-3 / 20)
        * _stencil_shift(halo, -2, -1, 3, 'zero') +
        (3 / 2)
        * _stencil_shift(halo, -1, -1, 3, 'zero') +
        (-49 / 18)
        * _stencil_shift(halo, 0, -1, 3, 'zero') +
        (3 / 2)
        * _stencil_shift(halo, 1, -1, 3, 'zero') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -1, 3, 'zero') +
        (1 / 90)
        * _stencil_shift(halo, 3, -1, 3, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 6, -1, 'zero'] = _fd_d2_a6_axis1_zero


def _fd_d2_a6_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 6, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 3, 'reflect', 2)
    result = (
        (1 / 90)
        * _stencil_shift(halo, -3, -1, 3, 'reflect') +
        (-3 / 20)
        * _stencil_shift(halo, -2, -1, 3, 'reflect') +
        (3 / 2)
        * _stencil_shift(halo, -1, -1, 3, 'reflect') +
        (-49 / 18)
        * _stencil_shift(halo, 0, -1, 3, 'reflect') +
        (3 / 2)
        * _stencil_shift(halo, 1, -1, 3, 'reflect') +
        (-3 / 20)
        * _stencil_shift(halo, 2, -1, 3, 'reflect') +
        (1 / 90)
        * _stencil_shift(halo, 3, -1, 3, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 6, -1, 'reflect'] = _fd_d2_a6_axis1_reflect


STENCIL_MOMENTS[2, 8] = (
    (-4, -1, 560),
    (-3, 8, 315),
    (-2, -1, 5),
    (-1, 8, 5),
    (0, -205, 72),
    (1, 8, 5),
    (2, -1, 5),
    (3, 8, 315),
    (4, -1, 560),
)

def _fd_d2_a8_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 8, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 4, 'periodic', 2)
    result = (
        (-1 / 560)
        * _stencil_shift(halo, -4, -4, 4, 'periodic') +
        (8 / 315)
        * _stencil_shift(halo, -3, -4, 4, 'periodic') +
        (-1 / 5)
        * _stencil_shift(halo, -2, -4, 4, 'periodic') +
        (8 / 5)
        * _stencil_shift(halo, -1, -4, 4, 'periodic') +
        (-205 / 72)
        * _stencil_shift(halo, 0, -4, 4, 'periodic') +
        (8 / 5)
        * _stencil_shift(halo, 1, -4, 4, 'periodic') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -4, 4, 'periodic') +
        (8 / 315)
        * _stencil_shift(halo, 3, -4, 4, 'periodic') +
        (-1 / 560)
        * _stencil_shift(halo, 4, -4, 4, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 8, -4, 'periodic'] = _fd_d2_a8_axis4_periodic


def _fd_d2_a8_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 8, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 4, 'zero', 2)
    result = (
        (-1 / 560)
        * _stencil_shift(halo, -4, -4, 4, 'zero') +
        (8 / 315)
        * _stencil_shift(halo, -3, -4, 4, 'zero') +
        (-1 / 5)
        * _stencil_shift(halo, -2, -4, 4, 'zero') +
        (8 / 5)
        * _stencil_shift(halo, -1, -4, 4, 'zero') +
        (-205 / 72)
        * _stencil_shift(halo, 0, -4, 4, 'zero') +
        (8 / 5)
        * _stencil_shift(halo, 1, -4, 4, 'zero') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -4, 4, 'zero') +
        (8 / 315)
        * _stencil_shift(halo, 3, -4, 4, 'zero') +
        (-1 / 560)
        * _stencil_shift(halo, 4, -4, 4, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 8, -4, 'zero'] = _fd_d2_a8_axis4_zero


def _fd_d2_a8_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 8, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 4, 'reflect', 2)
    result = (
        (-1 / 560)
        * _stencil_shift(halo, -4, -4, 4, 'reflect') +
        (8 / 315)
        * _stencil_shift(halo, -3, -4, 4, 'reflect') +
        (-1 / 5)
        * _stencil_shift(halo, -2, -4, 4, 'reflect') +
        (8 / 5)
        * _stencil_shift(halo, -1, -4, 4, 'reflect') +
        (-205 / 72)
        * _stencil_shift(halo, 0, -4, 4, 'reflect') +
        (8 / 5)
        * _stencil_shift(halo, 1, -4, 4, 'reflect') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -4, 4, 'reflect') +
        (8 / 315)
        * _stencil_shift(halo, 3, -4, 4, 'reflect') +
        (-1 / 560)
        * _stencil_shift(halo, 4, -4, 4, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 8, -4, 'reflect'] = _fd_d2_a8_axis4_reflect


def _fd_d2_a8_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 8, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 4, 'periodic', 2)
    result = (
        (-1 / 560)
        * _stencil_shift(halo, -4, -3, 4, 'periodic') +
        (8 / 315)
        * _stencil_shift(halo, -3, -3, 4, 'periodic') +
        (-1 / 5)
        * _stencil_shift(halo, -2, -3, 4, 'periodic') +
        (8 / 5)
        * _stencil_shift(halo, -1, -3, 4, 'periodic') +
        (-205 / 72)
        * _stencil_shift(halo, 0, -3, 4, 'periodic') +
        (8 / 5)
        * _stencil_shift(halo, 1, -3, 4, 'periodic') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -3, 4, 'periodic') +
        (8 / 315)
        * _stencil_shift(halo, 3, -3, 4, 'periodic') +
        (-1 / 560)
        * _stencil_shift(halo, 4, -3, 4, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 8, -3, 'periodic'] = _fd_d2_a8_axis3_periodic


def _fd_d2_a8_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 8, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 4, 'zero', 2)
    result = (
        (-1 / 560)
        * _stencil_shift(halo, -4, -3, 4, 'zero') +
        (8 / 315)
        * _stencil_shift(halo, -3, -3, 4, 'zero') +
        (-1 / 5)
        * _stencil_shift(halo, -2, -3, 4, 'zero') +
        (8 / 5)
        * _stencil_shift(halo, -1, -3, 4, 'zero') +
        (-205 / 72)
        * _stencil_shift(halo, 0, -3, 4, 'zero') +
        (8 / 5)
        * _stencil_shift(halo, 1, -3, 4, 'zero') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -3, 4, 'zero') +
        (8 / 315)
        * _stencil_shift(halo, 3, -3, 4, 'zero') +
        (-1 / 560)
        * _stencil_shift(halo, 4, -3, 4, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 8, -3, 'zero'] = _fd_d2_a8_axis3_zero


def _fd_d2_a8_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 8, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 4, 'reflect', 2)
    result = (
        (-1 / 560)
        * _stencil_shift(halo, -4, -3, 4, 'reflect') +
        (8 / 315)
        * _stencil_shift(halo, -3, -3, 4, 'reflect') +
        (-1 / 5)
        * _stencil_shift(halo, -2, -3, 4, 'reflect') +
        (8 / 5)
        * _stencil_shift(halo, -1, -3, 4, 'reflect') +
        (-205 / 72)
        * _stencil_shift(halo, 0, -3, 4, 'reflect') +
        (8 / 5)
        * _stencil_shift(halo, 1, -3, 4, 'reflect') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -3, 4, 'reflect') +
        (8 / 315)
        * _stencil_shift(halo, 3, -3, 4, 'reflect') +
        (-1 / 560)
        * _stencil_shift(halo, 4, -3, 4, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 8, -3, 'reflect'] = _fd_d2_a8_axis3_reflect


def _fd_d2_a8_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 8, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 4, 'periodic', 2)
    result = (
        (-1 / 560)
        * _stencil_shift(halo, -4, -2, 4, 'periodic') +
        (8 / 315)
        * _stencil_shift(halo, -3, -2, 4, 'periodic') +
        (-1 / 5)
        * _stencil_shift(halo, -2, -2, 4, 'periodic') +
        (8 / 5)
        * _stencil_shift(halo, -1, -2, 4, 'periodic') +
        (-205 / 72)
        * _stencil_shift(halo, 0, -2, 4, 'periodic') +
        (8 / 5)
        * _stencil_shift(halo, 1, -2, 4, 'periodic') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -2, 4, 'periodic') +
        (8 / 315)
        * _stencil_shift(halo, 3, -2, 4, 'periodic') +
        (-1 / 560)
        * _stencil_shift(halo, 4, -2, 4, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 8, -2, 'periodic'] = _fd_d2_a8_axis2_periodic


def _fd_d2_a8_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 8, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 4, 'zero', 2)
    result = (
        (-1 / 560)
        * _stencil_shift(halo, -4, -2, 4, 'zero') +
        (8 / 315)
        * _stencil_shift(halo, -3, -2, 4, 'zero') +
        (-1 / 5)
        * _stencil_shift(halo, -2, -2, 4, 'zero') +
        (8 / 5)
        * _stencil_shift(halo, -1, -2, 4, 'zero') +
        (-205 / 72)
        * _stencil_shift(halo, 0, -2, 4, 'zero') +
        (8 / 5)
        * _stencil_shift(halo, 1, -2, 4, 'zero') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -2, 4, 'zero') +
        (8 / 315)
        * _stencil_shift(halo, 3, -2, 4, 'zero') +
        (-1 / 560)
        * _stencil_shift(halo, 4, -2, 4, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 8, -2, 'zero'] = _fd_d2_a8_axis2_zero


def _fd_d2_a8_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 8, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 4, 'reflect', 2)
    result = (
        (-1 / 560)
        * _stencil_shift(halo, -4, -2, 4, 'reflect') +
        (8 / 315)
        * _stencil_shift(halo, -3, -2, 4, 'reflect') +
        (-1 / 5)
        * _stencil_shift(halo, -2, -2, 4, 'reflect') +
        (8 / 5)
        * _stencil_shift(halo, -1, -2, 4, 'reflect') +
        (-205 / 72)
        * _stencil_shift(halo, 0, -2, 4, 'reflect') +
        (8 / 5)
        * _stencil_shift(halo, 1, -2, 4, 'reflect') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -2, 4, 'reflect') +
        (8 / 315)
        * _stencil_shift(halo, 3, -2, 4, 'reflect') +
        (-1 / 560)
        * _stencil_shift(halo, 4, -2, 4, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 8, -2, 'reflect'] = _fd_d2_a8_axis2_reflect


def _fd_d2_a8_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 8, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 4, 'periodic', 2)
    result = (
        (-1 / 560)
        * _stencil_shift(halo, -4, -1, 4, 'periodic') +
        (8 / 315)
        * _stencil_shift(halo, -3, -1, 4, 'periodic') +
        (-1 / 5)
        * _stencil_shift(halo, -2, -1, 4, 'periodic') +
        (8 / 5)
        * _stencil_shift(halo, -1, -1, 4, 'periodic') +
        (-205 / 72)
        * _stencil_shift(halo, 0, -1, 4, 'periodic') +
        (8 / 5)
        * _stencil_shift(halo, 1, -1, 4, 'periodic') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -1, 4, 'periodic') +
        (8 / 315)
        * _stencil_shift(halo, 3, -1, 4, 'periodic') +
        (-1 / 560)
        * _stencil_shift(halo, 4, -1, 4, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 8, -1, 'periodic'] = _fd_d2_a8_axis1_periodic


def _fd_d2_a8_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 8, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 4, 'zero', 2)
    result = (
        (-1 / 560)
        * _stencil_shift(halo, -4, -1, 4, 'zero') +
        (8 / 315)
        * _stencil_shift(halo, -3, -1, 4, 'zero') +
        (-1 / 5)
        * _stencil_shift(halo, -2, -1, 4, 'zero') +
        (8 / 5)
        * _stencil_shift(halo, -1, -1, 4, 'zero') +
        (-205 / 72)
        * _stencil_shift(halo, 0, -1, 4, 'zero') +
        (8 / 5)
        * _stencil_shift(halo, 1, -1, 4, 'zero') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -1, 4, 'zero') +
        (8 / 315)
        * _stencil_shift(halo, 3, -1, 4, 'zero') +
        (-1 / 560)
        * _stencil_shift(halo, 4, -1, 4, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 8, -1, 'zero'] = _fd_d2_a8_axis1_zero


def _fd_d2_a8_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 8, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 4, 'reflect', 2)
    result = (
        (-1 / 560)
        * _stencil_shift(halo, -4, -1, 4, 'reflect') +
        (8 / 315)
        * _stencil_shift(halo, -3, -1, 4, 'reflect') +
        (-1 / 5)
        * _stencil_shift(halo, -2, -1, 4, 'reflect') +
        (8 / 5)
        * _stencil_shift(halo, -1, -1, 4, 'reflect') +
        (-205 / 72)
        * _stencil_shift(halo, 0, -1, 4, 'reflect') +
        (8 / 5)
        * _stencil_shift(halo, 1, -1, 4, 'reflect') +
        (-1 / 5)
        * _stencil_shift(halo, 2, -1, 4, 'reflect') +
        (8 / 315)
        * _stencil_shift(halo, 3, -1, 4, 'reflect') +
        (-1 / 560)
        * _stencil_shift(halo, 4, -1, 4, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 8, -1, 'reflect'] = _fd_d2_a8_axis1_reflect


STENCIL_MOMENTS[2, 10] = (
    (-5, 1, 3150),
    (-4, -5, 1008),
    (-3, 5, 126),
    (-2, -5, 21),
    (-1, 5, 3),
    (0, -5269, 1800),
    (1, 5, 3),
    (2, -5, 21),
    (3, 5, 126),
    (4, -5, 1008),
    (5, 1, 3150),
)

def _fd_d2_a10_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 10, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 5, 'periodic', 2)
    result = (
        (1 / 3150)
        * _stencil_shift(halo, -5, -4, 5, 'periodic') +
        (-5 / 1008)
        * _stencil_shift(halo, -4, -4, 5, 'periodic') +
        (5 / 126)
        * _stencil_shift(halo, -3, -4, 5, 'periodic') +
        (-5 / 21)
        * _stencil_shift(halo, -2, -4, 5, 'periodic') +
        (5 / 3)
        * _stencil_shift(halo, -1, -4, 5, 'periodic') +
        (-5269 / 1800)
        * _stencil_shift(halo, 0, -4, 5, 'periodic') +
        (5 / 3)
        * _stencil_shift(halo, 1, -4, 5, 'periodic') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -4, 5, 'periodic') +
        (5 / 126)
        * _stencil_shift(halo, 3, -4, 5, 'periodic') +
        (-5 / 1008)
        * _stencil_shift(halo, 4, -4, 5, 'periodic') +
        (1 / 3150)
        * _stencil_shift(halo, 5, -4, 5, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 10, -4, 'periodic'] = _fd_d2_a10_axis4_periodic


def _fd_d2_a10_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 10, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 5, 'zero', 2)
    result = (
        (1 / 3150)
        * _stencil_shift(halo, -5, -4, 5, 'zero') +
        (-5 / 1008)
        * _stencil_shift(halo, -4, -4, 5, 'zero') +
        (5 / 126)
        * _stencil_shift(halo, -3, -4, 5, 'zero') +
        (-5 / 21)
        * _stencil_shift(halo, -2, -4, 5, 'zero') +
        (5 / 3)
        * _stencil_shift(halo, -1, -4, 5, 'zero') +
        (-5269 / 1800)
        * _stencil_shift(halo, 0, -4, 5, 'zero') +
        (5 / 3)
        * _stencil_shift(halo, 1, -4, 5, 'zero') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -4, 5, 'zero') +
        (5 / 126)
        * _stencil_shift(halo, 3, -4, 5, 'zero') +
        (-5 / 1008)
        * _stencil_shift(halo, 4, -4, 5, 'zero') +
        (1 / 3150)
        * _stencil_shift(halo, 5, -4, 5, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 10, -4, 'zero'] = _fd_d2_a10_axis4_zero


def _fd_d2_a10_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 10, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 5, 'reflect', 2)
    result = (
        (1 / 3150)
        * _stencil_shift(halo, -5, -4, 5, 'reflect') +
        (-5 / 1008)
        * _stencil_shift(halo, -4, -4, 5, 'reflect') +
        (5 / 126)
        * _stencil_shift(halo, -3, -4, 5, 'reflect') +
        (-5 / 21)
        * _stencil_shift(halo, -2, -4, 5, 'reflect') +
        (5 / 3)
        * _stencil_shift(halo, -1, -4, 5, 'reflect') +
        (-5269 / 1800)
        * _stencil_shift(halo, 0, -4, 5, 'reflect') +
        (5 / 3)
        * _stencil_shift(halo, 1, -4, 5, 'reflect') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -4, 5, 'reflect') +
        (5 / 126)
        * _stencil_shift(halo, 3, -4, 5, 'reflect') +
        (-5 / 1008)
        * _stencil_shift(halo, 4, -4, 5, 'reflect') +
        (1 / 3150)
        * _stencil_shift(halo, 5, -4, 5, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 10, -4, 'reflect'] = _fd_d2_a10_axis4_reflect


def _fd_d2_a10_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 10, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 5, 'periodic', 2)
    result = (
        (1 / 3150)
        * _stencil_shift(halo, -5, -3, 5, 'periodic') +
        (-5 / 1008)
        * _stencil_shift(halo, -4, -3, 5, 'periodic') +
        (5 / 126)
        * _stencil_shift(halo, -3, -3, 5, 'periodic') +
        (-5 / 21)
        * _stencil_shift(halo, -2, -3, 5, 'periodic') +
        (5 / 3)
        * _stencil_shift(halo, -1, -3, 5, 'periodic') +
        (-5269 / 1800)
        * _stencil_shift(halo, 0, -3, 5, 'periodic') +
        (5 / 3)
        * _stencil_shift(halo, 1, -3, 5, 'periodic') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -3, 5, 'periodic') +
        (5 / 126)
        * _stencil_shift(halo, 3, -3, 5, 'periodic') +
        (-5 / 1008)
        * _stencil_shift(halo, 4, -3, 5, 'periodic') +
        (1 / 3150)
        * _stencil_shift(halo, 5, -3, 5, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 10, -3, 'periodic'] = _fd_d2_a10_axis3_periodic


def _fd_d2_a10_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 10, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 5, 'zero', 2)
    result = (
        (1 / 3150)
        * _stencil_shift(halo, -5, -3, 5, 'zero') +
        (-5 / 1008)
        * _stencil_shift(halo, -4, -3, 5, 'zero') +
        (5 / 126)
        * _stencil_shift(halo, -3, -3, 5, 'zero') +
        (-5 / 21)
        * _stencil_shift(halo, -2, -3, 5, 'zero') +
        (5 / 3)
        * _stencil_shift(halo, -1, -3, 5, 'zero') +
        (-5269 / 1800)
        * _stencil_shift(halo, 0, -3, 5, 'zero') +
        (5 / 3)
        * _stencil_shift(halo, 1, -3, 5, 'zero') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -3, 5, 'zero') +
        (5 / 126)
        * _stencil_shift(halo, 3, -3, 5, 'zero') +
        (-5 / 1008)
        * _stencil_shift(halo, 4, -3, 5, 'zero') +
        (1 / 3150)
        * _stencil_shift(halo, 5, -3, 5, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 10, -3, 'zero'] = _fd_d2_a10_axis3_zero


def _fd_d2_a10_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 10, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 5, 'reflect', 2)
    result = (
        (1 / 3150)
        * _stencil_shift(halo, -5, -3, 5, 'reflect') +
        (-5 / 1008)
        * _stencil_shift(halo, -4, -3, 5, 'reflect') +
        (5 / 126)
        * _stencil_shift(halo, -3, -3, 5, 'reflect') +
        (-5 / 21)
        * _stencil_shift(halo, -2, -3, 5, 'reflect') +
        (5 / 3)
        * _stencil_shift(halo, -1, -3, 5, 'reflect') +
        (-5269 / 1800)
        * _stencil_shift(halo, 0, -3, 5, 'reflect') +
        (5 / 3)
        * _stencil_shift(halo, 1, -3, 5, 'reflect') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -3, 5, 'reflect') +
        (5 / 126)
        * _stencil_shift(halo, 3, -3, 5, 'reflect') +
        (-5 / 1008)
        * _stencil_shift(halo, 4, -3, 5, 'reflect') +
        (1 / 3150)
        * _stencil_shift(halo, 5, -3, 5, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 10, -3, 'reflect'] = _fd_d2_a10_axis3_reflect


def _fd_d2_a10_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 10, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 5, 'periodic', 2)
    result = (
        (1 / 3150)
        * _stencil_shift(halo, -5, -2, 5, 'periodic') +
        (-5 / 1008)
        * _stencil_shift(halo, -4, -2, 5, 'periodic') +
        (5 / 126)
        * _stencil_shift(halo, -3, -2, 5, 'periodic') +
        (-5 / 21)
        * _stencil_shift(halo, -2, -2, 5, 'periodic') +
        (5 / 3)
        * _stencil_shift(halo, -1, -2, 5, 'periodic') +
        (-5269 / 1800)
        * _stencil_shift(halo, 0, -2, 5, 'periodic') +
        (5 / 3)
        * _stencil_shift(halo, 1, -2, 5, 'periodic') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -2, 5, 'periodic') +
        (5 / 126)
        * _stencil_shift(halo, 3, -2, 5, 'periodic') +
        (-5 / 1008)
        * _stencil_shift(halo, 4, -2, 5, 'periodic') +
        (1 / 3150)
        * _stencil_shift(halo, 5, -2, 5, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 10, -2, 'periodic'] = _fd_d2_a10_axis2_periodic


def _fd_d2_a10_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 10, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 5, 'zero', 2)
    result = (
        (1 / 3150)
        * _stencil_shift(halo, -5, -2, 5, 'zero') +
        (-5 / 1008)
        * _stencil_shift(halo, -4, -2, 5, 'zero') +
        (5 / 126)
        * _stencil_shift(halo, -3, -2, 5, 'zero') +
        (-5 / 21)
        * _stencil_shift(halo, -2, -2, 5, 'zero') +
        (5 / 3)
        * _stencil_shift(halo, -1, -2, 5, 'zero') +
        (-5269 / 1800)
        * _stencil_shift(halo, 0, -2, 5, 'zero') +
        (5 / 3)
        * _stencil_shift(halo, 1, -2, 5, 'zero') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -2, 5, 'zero') +
        (5 / 126)
        * _stencil_shift(halo, 3, -2, 5, 'zero') +
        (-5 / 1008)
        * _stencil_shift(halo, 4, -2, 5, 'zero') +
        (1 / 3150)
        * _stencil_shift(halo, 5, -2, 5, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 10, -2, 'zero'] = _fd_d2_a10_axis2_zero


def _fd_d2_a10_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 10, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 5, 'reflect', 2)
    result = (
        (1 / 3150)
        * _stencil_shift(halo, -5, -2, 5, 'reflect') +
        (-5 / 1008)
        * _stencil_shift(halo, -4, -2, 5, 'reflect') +
        (5 / 126)
        * _stencil_shift(halo, -3, -2, 5, 'reflect') +
        (-5 / 21)
        * _stencil_shift(halo, -2, -2, 5, 'reflect') +
        (5 / 3)
        * _stencil_shift(halo, -1, -2, 5, 'reflect') +
        (-5269 / 1800)
        * _stencil_shift(halo, 0, -2, 5, 'reflect') +
        (5 / 3)
        * _stencil_shift(halo, 1, -2, 5, 'reflect') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -2, 5, 'reflect') +
        (5 / 126)
        * _stencil_shift(halo, 3, -2, 5, 'reflect') +
        (-5 / 1008)
        * _stencil_shift(halo, 4, -2, 5, 'reflect') +
        (1 / 3150)
        * _stencil_shift(halo, 5, -2, 5, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 10, -2, 'reflect'] = _fd_d2_a10_axis2_reflect


def _fd_d2_a10_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 10, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 5, 'periodic', 2)
    result = (
        (1 / 3150)
        * _stencil_shift(halo, -5, -1, 5, 'periodic') +
        (-5 / 1008)
        * _stencil_shift(halo, -4, -1, 5, 'periodic') +
        (5 / 126)
        * _stencil_shift(halo, -3, -1, 5, 'periodic') +
        (-5 / 21)
        * _stencil_shift(halo, -2, -1, 5, 'periodic') +
        (5 / 3)
        * _stencil_shift(halo, -1, -1, 5, 'periodic') +
        (-5269 / 1800)
        * _stencil_shift(halo, 0, -1, 5, 'periodic') +
        (5 / 3)
        * _stencil_shift(halo, 1, -1, 5, 'periodic') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -1, 5, 'periodic') +
        (5 / 126)
        * _stencil_shift(halo, 3, -1, 5, 'periodic') +
        (-5 / 1008)
        * _stencil_shift(halo, 4, -1, 5, 'periodic') +
        (1 / 3150)
        * _stencil_shift(halo, 5, -1, 5, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 10, -1, 'periodic'] = _fd_d2_a10_axis1_periodic


def _fd_d2_a10_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 10, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 5, 'zero', 2)
    result = (
        (1 / 3150)
        * _stencil_shift(halo, -5, -1, 5, 'zero') +
        (-5 / 1008)
        * _stencil_shift(halo, -4, -1, 5, 'zero') +
        (5 / 126)
        * _stencil_shift(halo, -3, -1, 5, 'zero') +
        (-5 / 21)
        * _stencil_shift(halo, -2, -1, 5, 'zero') +
        (5 / 3)
        * _stencil_shift(halo, -1, -1, 5, 'zero') +
        (-5269 / 1800)
        * _stencil_shift(halo, 0, -1, 5, 'zero') +
        (5 / 3)
        * _stencil_shift(halo, 1, -1, 5, 'zero') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -1, 5, 'zero') +
        (5 / 126)
        * _stencil_shift(halo, 3, -1, 5, 'zero') +
        (-5 / 1008)
        * _stencil_shift(halo, 4, -1, 5, 'zero') +
        (1 / 3150)
        * _stencil_shift(halo, 5, -1, 5, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 10, -1, 'zero'] = _fd_d2_a10_axis1_zero


def _fd_d2_a10_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 10, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 5, 'reflect', 2)
    result = (
        (1 / 3150)
        * _stencil_shift(halo, -5, -1, 5, 'reflect') +
        (-5 / 1008)
        * _stencil_shift(halo, -4, -1, 5, 'reflect') +
        (5 / 126)
        * _stencil_shift(halo, -3, -1, 5, 'reflect') +
        (-5 / 21)
        * _stencil_shift(halo, -2, -1, 5, 'reflect') +
        (5 / 3)
        * _stencil_shift(halo, -1, -1, 5, 'reflect') +
        (-5269 / 1800)
        * _stencil_shift(halo, 0, -1, 5, 'reflect') +
        (5 / 3)
        * _stencil_shift(halo, 1, -1, 5, 'reflect') +
        (-5 / 21)
        * _stencil_shift(halo, 2, -1, 5, 'reflect') +
        (5 / 126)
        * _stencil_shift(halo, 3, -1, 5, 'reflect') +
        (-5 / 1008)
        * _stencil_shift(halo, 4, -1, 5, 'reflect') +
        (1 / 3150)
        * _stencil_shift(halo, 5, -1, 5, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 10, -1, 'reflect'] = _fd_d2_a10_axis1_reflect


STENCIL_MOMENTS[2, 12] = (
    (-6, -1, 16632),
    (-5, 2, 1925),
    (-4, -1, 112),
    (-3, 10, 189),
    (-2, -15, 56),
    (-1, 12, 7),
    (0, -5369, 1800),
    (1, 12, 7),
    (2, -15, 56),
    (3, 10, 189),
    (4, -1, 112),
    (5, 2, 1925),
    (6, -1, 16632),
)

def _fd_d2_a12_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 12, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 6, 'periodic', 2)
    result = (
        (-1 / 16632)
        * _stencil_shift(halo, -6, -4, 6, 'periodic') +
        (2 / 1925)
        * _stencil_shift(halo, -5, -4, 6, 'periodic') +
        (-1 / 112)
        * _stencil_shift(halo, -4, -4, 6, 'periodic') +
        (10 / 189)
        * _stencil_shift(halo, -3, -4, 6, 'periodic') +
        (-15 / 56)
        * _stencil_shift(halo, -2, -4, 6, 'periodic') +
        (12 / 7)
        * _stencil_shift(halo, -1, -4, 6, 'periodic') +
        (-5369 / 1800)
        * _stencil_shift(halo, 0, -4, 6, 'periodic') +
        (12 / 7)
        * _stencil_shift(halo, 1, -4, 6, 'periodic') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -4, 6, 'periodic') +
        (10 / 189)
        * _stencil_shift(halo, 3, -4, 6, 'periodic') +
        (-1 / 112)
        * _stencil_shift(halo, 4, -4, 6, 'periodic') +
        (2 / 1925)
        * _stencil_shift(halo, 5, -4, 6, 'periodic') +
        (-1 / 16632)
        * _stencil_shift(halo, 6, -4, 6, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 12, -4, 'periodic'] = _fd_d2_a12_axis4_periodic


def _fd_d2_a12_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 12, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 6, 'zero', 2)
    result = (
        (-1 / 16632)
        * _stencil_shift(halo, -6, -4, 6, 'zero') +
        (2 / 1925)
        * _stencil_shift(halo, -5, -4, 6, 'zero') +
        (-1 / 112)
        * _stencil_shift(halo, -4, -4, 6, 'zero') +
        (10 / 189)
        * _stencil_shift(halo, -3, -4, 6, 'zero') +
        (-15 / 56)
        * _stencil_shift(halo, -2, -4, 6, 'zero') +
        (12 / 7)
        * _stencil_shift(halo, -1, -4, 6, 'zero') +
        (-5369 / 1800)
        * _stencil_shift(halo, 0, -4, 6, 'zero') +
        (12 / 7)
        * _stencil_shift(halo, 1, -4, 6, 'zero') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -4, 6, 'zero') +
        (10 / 189)
        * _stencil_shift(halo, 3, -4, 6, 'zero') +
        (-1 / 112)
        * _stencil_shift(halo, 4, -4, 6, 'zero') +
        (2 / 1925)
        * _stencil_shift(halo, 5, -4, 6, 'zero') +
        (-1 / 16632)
        * _stencil_shift(halo, 6, -4, 6, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 12, -4, 'zero'] = _fd_d2_a12_axis4_zero


def _fd_d2_a12_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 12, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 6, 'reflect', 2)
    result = (
        (-1 / 16632)
        * _stencil_shift(halo, -6, -4, 6, 'reflect') +
        (2 / 1925)
        * _stencil_shift(halo, -5, -4, 6, 'reflect') +
        (-1 / 112)
        * _stencil_shift(halo, -4, -4, 6, 'reflect') +
        (10 / 189)
        * _stencil_shift(halo, -3, -4, 6, 'reflect') +
        (-15 / 56)
        * _stencil_shift(halo, -2, -4, 6, 'reflect') +
        (12 / 7)
        * _stencil_shift(halo, -1, -4, 6, 'reflect') +
        (-5369 / 1800)
        * _stencil_shift(halo, 0, -4, 6, 'reflect') +
        (12 / 7)
        * _stencil_shift(halo, 1, -4, 6, 'reflect') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -4, 6, 'reflect') +
        (10 / 189)
        * _stencil_shift(halo, 3, -4, 6, 'reflect') +
        (-1 / 112)
        * _stencil_shift(halo, 4, -4, 6, 'reflect') +
        (2 / 1925)
        * _stencil_shift(halo, 5, -4, 6, 'reflect') +
        (-1 / 16632)
        * _stencil_shift(halo, 6, -4, 6, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 12, -4, 'reflect'] = _fd_d2_a12_axis4_reflect


def _fd_d2_a12_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 12, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 6, 'periodic', 2)
    result = (
        (-1 / 16632)
        * _stencil_shift(halo, -6, -3, 6, 'periodic') +
        (2 / 1925)
        * _stencil_shift(halo, -5, -3, 6, 'periodic') +
        (-1 / 112)
        * _stencil_shift(halo, -4, -3, 6, 'periodic') +
        (10 / 189)
        * _stencil_shift(halo, -3, -3, 6, 'periodic') +
        (-15 / 56)
        * _stencil_shift(halo, -2, -3, 6, 'periodic') +
        (12 / 7)
        * _stencil_shift(halo, -1, -3, 6, 'periodic') +
        (-5369 / 1800)
        * _stencil_shift(halo, 0, -3, 6, 'periodic') +
        (12 / 7)
        * _stencil_shift(halo, 1, -3, 6, 'periodic') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -3, 6, 'periodic') +
        (10 / 189)
        * _stencil_shift(halo, 3, -3, 6, 'periodic') +
        (-1 / 112)
        * _stencil_shift(halo, 4, -3, 6, 'periodic') +
        (2 / 1925)
        * _stencil_shift(halo, 5, -3, 6, 'periodic') +
        (-1 / 16632)
        * _stencil_shift(halo, 6, -3, 6, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 12, -3, 'periodic'] = _fd_d2_a12_axis3_periodic


def _fd_d2_a12_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 12, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 6, 'zero', 2)
    result = (
        (-1 / 16632)
        * _stencil_shift(halo, -6, -3, 6, 'zero') +
        (2 / 1925)
        * _stencil_shift(halo, -5, -3, 6, 'zero') +
        (-1 / 112)
        * _stencil_shift(halo, -4, -3, 6, 'zero') +
        (10 / 189)
        * _stencil_shift(halo, -3, -3, 6, 'zero') +
        (-15 / 56)
        * _stencil_shift(halo, -2, -3, 6, 'zero') +
        (12 / 7)
        * _stencil_shift(halo, -1, -3, 6, 'zero') +
        (-5369 / 1800)
        * _stencil_shift(halo, 0, -3, 6, 'zero') +
        (12 / 7)
        * _stencil_shift(halo, 1, -3, 6, 'zero') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -3, 6, 'zero') +
        (10 / 189)
        * _stencil_shift(halo, 3, -3, 6, 'zero') +
        (-1 / 112)
        * _stencil_shift(halo, 4, -3, 6, 'zero') +
        (2 / 1925)
        * _stencil_shift(halo, 5, -3, 6, 'zero') +
        (-1 / 16632)
        * _stencil_shift(halo, 6, -3, 6, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 12, -3, 'zero'] = _fd_d2_a12_axis3_zero


def _fd_d2_a12_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 12, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 6, 'reflect', 2)
    result = (
        (-1 / 16632)
        * _stencil_shift(halo, -6, -3, 6, 'reflect') +
        (2 / 1925)
        * _stencil_shift(halo, -5, -3, 6, 'reflect') +
        (-1 / 112)
        * _stencil_shift(halo, -4, -3, 6, 'reflect') +
        (10 / 189)
        * _stencil_shift(halo, -3, -3, 6, 'reflect') +
        (-15 / 56)
        * _stencil_shift(halo, -2, -3, 6, 'reflect') +
        (12 / 7)
        * _stencil_shift(halo, -1, -3, 6, 'reflect') +
        (-5369 / 1800)
        * _stencil_shift(halo, 0, -3, 6, 'reflect') +
        (12 / 7)
        * _stencil_shift(halo, 1, -3, 6, 'reflect') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -3, 6, 'reflect') +
        (10 / 189)
        * _stencil_shift(halo, 3, -3, 6, 'reflect') +
        (-1 / 112)
        * _stencil_shift(halo, 4, -3, 6, 'reflect') +
        (2 / 1925)
        * _stencil_shift(halo, 5, -3, 6, 'reflect') +
        (-1 / 16632)
        * _stencil_shift(halo, 6, -3, 6, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 12, -3, 'reflect'] = _fd_d2_a12_axis3_reflect


def _fd_d2_a12_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 12, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 6, 'periodic', 2)
    result = (
        (-1 / 16632)
        * _stencil_shift(halo, -6, -2, 6, 'periodic') +
        (2 / 1925)
        * _stencil_shift(halo, -5, -2, 6, 'periodic') +
        (-1 / 112)
        * _stencil_shift(halo, -4, -2, 6, 'periodic') +
        (10 / 189)
        * _stencil_shift(halo, -3, -2, 6, 'periodic') +
        (-15 / 56)
        * _stencil_shift(halo, -2, -2, 6, 'periodic') +
        (12 / 7)
        * _stencil_shift(halo, -1, -2, 6, 'periodic') +
        (-5369 / 1800)
        * _stencil_shift(halo, 0, -2, 6, 'periodic') +
        (12 / 7)
        * _stencil_shift(halo, 1, -2, 6, 'periodic') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -2, 6, 'periodic') +
        (10 / 189)
        * _stencil_shift(halo, 3, -2, 6, 'periodic') +
        (-1 / 112)
        * _stencil_shift(halo, 4, -2, 6, 'periodic') +
        (2 / 1925)
        * _stencil_shift(halo, 5, -2, 6, 'periodic') +
        (-1 / 16632)
        * _stencil_shift(halo, 6, -2, 6, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 12, -2, 'periodic'] = _fd_d2_a12_axis2_periodic


def _fd_d2_a12_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 12, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 6, 'zero', 2)
    result = (
        (-1 / 16632)
        * _stencil_shift(halo, -6, -2, 6, 'zero') +
        (2 / 1925)
        * _stencil_shift(halo, -5, -2, 6, 'zero') +
        (-1 / 112)
        * _stencil_shift(halo, -4, -2, 6, 'zero') +
        (10 / 189)
        * _stencil_shift(halo, -3, -2, 6, 'zero') +
        (-15 / 56)
        * _stencil_shift(halo, -2, -2, 6, 'zero') +
        (12 / 7)
        * _stencil_shift(halo, -1, -2, 6, 'zero') +
        (-5369 / 1800)
        * _stencil_shift(halo, 0, -2, 6, 'zero') +
        (12 / 7)
        * _stencil_shift(halo, 1, -2, 6, 'zero') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -2, 6, 'zero') +
        (10 / 189)
        * _stencil_shift(halo, 3, -2, 6, 'zero') +
        (-1 / 112)
        * _stencil_shift(halo, 4, -2, 6, 'zero') +
        (2 / 1925)
        * _stencil_shift(halo, 5, -2, 6, 'zero') +
        (-1 / 16632)
        * _stencil_shift(halo, 6, -2, 6, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 12, -2, 'zero'] = _fd_d2_a12_axis2_zero


def _fd_d2_a12_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 12, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 6, 'reflect', 2)
    result = (
        (-1 / 16632)
        * _stencil_shift(halo, -6, -2, 6, 'reflect') +
        (2 / 1925)
        * _stencil_shift(halo, -5, -2, 6, 'reflect') +
        (-1 / 112)
        * _stencil_shift(halo, -4, -2, 6, 'reflect') +
        (10 / 189)
        * _stencil_shift(halo, -3, -2, 6, 'reflect') +
        (-15 / 56)
        * _stencil_shift(halo, -2, -2, 6, 'reflect') +
        (12 / 7)
        * _stencil_shift(halo, -1, -2, 6, 'reflect') +
        (-5369 / 1800)
        * _stencil_shift(halo, 0, -2, 6, 'reflect') +
        (12 / 7)
        * _stencil_shift(halo, 1, -2, 6, 'reflect') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -2, 6, 'reflect') +
        (10 / 189)
        * _stencil_shift(halo, 3, -2, 6, 'reflect') +
        (-1 / 112)
        * _stencil_shift(halo, 4, -2, 6, 'reflect') +
        (2 / 1925)
        * _stencil_shift(halo, 5, -2, 6, 'reflect') +
        (-1 / 16632)
        * _stencil_shift(halo, 6, -2, 6, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 12, -2, 'reflect'] = _fd_d2_a12_axis2_reflect


def _fd_d2_a12_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 12, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 6, 'periodic', 2)
    result = (
        (-1 / 16632)
        * _stencil_shift(halo, -6, -1, 6, 'periodic') +
        (2 / 1925)
        * _stencil_shift(halo, -5, -1, 6, 'periodic') +
        (-1 / 112)
        * _stencil_shift(halo, -4, -1, 6, 'periodic') +
        (10 / 189)
        * _stencil_shift(halo, -3, -1, 6, 'periodic') +
        (-15 / 56)
        * _stencil_shift(halo, -2, -1, 6, 'periodic') +
        (12 / 7)
        * _stencil_shift(halo, -1, -1, 6, 'periodic') +
        (-5369 / 1800)
        * _stencil_shift(halo, 0, -1, 6, 'periodic') +
        (12 / 7)
        * _stencil_shift(halo, 1, -1, 6, 'periodic') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -1, 6, 'periodic') +
        (10 / 189)
        * _stencil_shift(halo, 3, -1, 6, 'periodic') +
        (-1 / 112)
        * _stencil_shift(halo, 4, -1, 6, 'periodic') +
        (2 / 1925)
        * _stencil_shift(halo, 5, -1, 6, 'periodic') +
        (-1 / 16632)
        * _stencil_shift(halo, 6, -1, 6, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 12, -1, 'periodic'] = _fd_d2_a12_axis1_periodic


def _fd_d2_a12_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 12, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 6, 'zero', 2)
    result = (
        (-1 / 16632)
        * _stencil_shift(halo, -6, -1, 6, 'zero') +
        (2 / 1925)
        * _stencil_shift(halo, -5, -1, 6, 'zero') +
        (-1 / 112)
        * _stencil_shift(halo, -4, -1, 6, 'zero') +
        (10 / 189)
        * _stencil_shift(halo, -3, -1, 6, 'zero') +
        (-15 / 56)
        * _stencil_shift(halo, -2, -1, 6, 'zero') +
        (12 / 7)
        * _stencil_shift(halo, -1, -1, 6, 'zero') +
        (-5369 / 1800)
        * _stencil_shift(halo, 0, -1, 6, 'zero') +
        (12 / 7)
        * _stencil_shift(halo, 1, -1, 6, 'zero') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -1, 6, 'zero') +
        (10 / 189)
        * _stencil_shift(halo, 3, -1, 6, 'zero') +
        (-1 / 112)
        * _stencil_shift(halo, 4, -1, 6, 'zero') +
        (2 / 1925)
        * _stencil_shift(halo, 5, -1, 6, 'zero') +
        (-1 / 16632)
        * _stencil_shift(halo, 6, -1, 6, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 12, -1, 'zero'] = _fd_d2_a12_axis1_zero


def _fd_d2_a12_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 12, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 6, 'reflect', 2)
    result = (
        (-1 / 16632)
        * _stencil_shift(halo, -6, -1, 6, 'reflect') +
        (2 / 1925)
        * _stencil_shift(halo, -5, -1, 6, 'reflect') +
        (-1 / 112)
        * _stencil_shift(halo, -4, -1, 6, 'reflect') +
        (10 / 189)
        * _stencil_shift(halo, -3, -1, 6, 'reflect') +
        (-15 / 56)
        * _stencil_shift(halo, -2, -1, 6, 'reflect') +
        (12 / 7)
        * _stencil_shift(halo, -1, -1, 6, 'reflect') +
        (-5369 / 1800)
        * _stencil_shift(halo, 0, -1, 6, 'reflect') +
        (12 / 7)
        * _stencil_shift(halo, 1, -1, 6, 'reflect') +
        (-15 / 56)
        * _stencil_shift(halo, 2, -1, 6, 'reflect') +
        (10 / 189)
        * _stencil_shift(halo, 3, -1, 6, 'reflect') +
        (-1 / 112)
        * _stencil_shift(halo, 4, -1, 6, 'reflect') +
        (2 / 1925)
        * _stencil_shift(halo, 5, -1, 6, 'reflect') +
        (-1 / 16632)
        * _stencil_shift(halo, 6, -1, 6, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 12, -1, 'reflect'] = _fd_d2_a12_axis1_reflect


STENCIL_MOMENTS[2, 14] = (
    (-7, 1, 84084),
    (-6, -7, 30888),
    (-5, 7, 3300),
    (-4, -7, 528),
    (-3, 7, 108),
    (-2, -7, 24),
    (-1, 7, 4),
    (0, -266681, 88200),
    (1, 7, 4),
    (2, -7, 24),
    (3, 7, 108),
    (4, -7, 528),
    (5, 7, 3300),
    (6, -7, 30888),
    (7, 1, 84084),
)

def _fd_d2_a14_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 14, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 7, 'periodic', 2)
    result = (
        (1 / 84084)
        * _stencil_shift(halo, -7, -4, 7, 'periodic') +
        (-7 / 30888)
        * _stencil_shift(halo, -6, -4, 7, 'periodic') +
        (7 / 3300)
        * _stencil_shift(halo, -5, -4, 7, 'periodic') +
        (-7 / 528)
        * _stencil_shift(halo, -4, -4, 7, 'periodic') +
        (7 / 108)
        * _stencil_shift(halo, -3, -4, 7, 'periodic') +
        (-7 / 24)
        * _stencil_shift(halo, -2, -4, 7, 'periodic') +
        (7 / 4)
        * _stencil_shift(halo, -1, -4, 7, 'periodic') +
        (-266681 / 88200)
        * _stencil_shift(halo, 0, -4, 7, 'periodic') +
        (7 / 4)
        * _stencil_shift(halo, 1, -4, 7, 'periodic') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -4, 7, 'periodic') +
        (7 / 108)
        * _stencil_shift(halo, 3, -4, 7, 'periodic') +
        (-7 / 528)
        * _stencil_shift(halo, 4, -4, 7, 'periodic') +
        (7 / 3300)
        * _stencil_shift(halo, 5, -4, 7, 'periodic') +
        (-7 / 30888)
        * _stencil_shift(halo, 6, -4, 7, 'periodic') +
        (1 / 84084)
        * _stencil_shift(halo, 7, -4, 7, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 14, -4, 'periodic'] = _fd_d2_a14_axis4_periodic


def _fd_d2_a14_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 14, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 7, 'zero', 2)
    result = (
        (1 / 84084)
        * _stencil_shift(halo, -7, -4, 7, 'zero') +
        (-7 / 30888)
        * _stencil_shift(halo, -6, -4, 7, 'zero') +
        (7 / 3300)
        * _stencil_shift(halo, -5, -4, 7, 'zero') +
        (-7 / 528)
        * _stencil_shift(halo, -4, -4, 7, 'zero') +
        (7 / 108)
        * _stencil_shift(halo, -3, -4, 7, 'zero') +
        (-7 / 24)
        * _stencil_shift(halo, -2, -4, 7, 'zero') +
        (7 / 4)
        * _stencil_shift(halo, -1, -4, 7, 'zero') +
        (-266681 / 88200)
        * _stencil_shift(halo, 0, -4, 7, 'zero') +
        (7 / 4)
        * _stencil_shift(halo, 1, -4, 7, 'zero') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -4, 7, 'zero') +
        (7 / 108)
        * _stencil_shift(halo, 3, -4, 7, 'zero') +
        (-7 / 528)
        * _stencil_shift(halo, 4, -4, 7, 'zero') +
        (7 / 3300)
        * _stencil_shift(halo, 5, -4, 7, 'zero') +
        (-7 / 30888)
        * _stencil_shift(halo, 6, -4, 7, 'zero') +
        (1 / 84084)
        * _stencil_shift(halo, 7, -4, 7, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 14, -4, 'zero'] = _fd_d2_a14_axis4_zero


def _fd_d2_a14_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 14, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 7, 'reflect', 2)
    result = (
        (1 / 84084)
        * _stencil_shift(halo, -7, -4, 7, 'reflect') +
        (-7 / 30888)
        * _stencil_shift(halo, -6, -4, 7, 'reflect') +
        (7 / 3300)
        * _stencil_shift(halo, -5, -4, 7, 'reflect') +
        (-7 / 528)
        * _stencil_shift(halo, -4, -4, 7, 'reflect') +
        (7 / 108)
        * _stencil_shift(halo, -3, -4, 7, 'reflect') +
        (-7 / 24)
        * _stencil_shift(halo, -2, -4, 7, 'reflect') +
        (7 / 4)
        * _stencil_shift(halo, -1, -4, 7, 'reflect') +
        (-266681 / 88200)
        * _stencil_shift(halo, 0, -4, 7, 'reflect') +
        (7 / 4)
        * _stencil_shift(halo, 1, -4, 7, 'reflect') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -4, 7, 'reflect') +
        (7 / 108)
        * _stencil_shift(halo, 3, -4, 7, 'reflect') +
        (-7 / 528)
        * _stencil_shift(halo, 4, -4, 7, 'reflect') +
        (7 / 3300)
        * _stencil_shift(halo, 5, -4, 7, 'reflect') +
        (-7 / 30888)
        * _stencil_shift(halo, 6, -4, 7, 'reflect') +
        (1 / 84084)
        * _stencil_shift(halo, 7, -4, 7, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 14, -4, 'reflect'] = _fd_d2_a14_axis4_reflect


def _fd_d2_a14_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 14, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 7, 'periodic', 2)
    result = (
        (1 / 84084)
        * _stencil_shift(halo, -7, -3, 7, 'periodic') +
        (-7 / 30888)
        * _stencil_shift(halo, -6, -3, 7, 'periodic') +
        (7 / 3300)
        * _stencil_shift(halo, -5, -3, 7, 'periodic') +
        (-7 / 528)
        * _stencil_shift(halo, -4, -3, 7, 'periodic') +
        (7 / 108)
        * _stencil_shift(halo, -3, -3, 7, 'periodic') +
        (-7 / 24)
        * _stencil_shift(halo, -2, -3, 7, 'periodic') +
        (7 / 4)
        * _stencil_shift(halo, -1, -3, 7, 'periodic') +
        (-266681 / 88200)
        * _stencil_shift(halo, 0, -3, 7, 'periodic') +
        (7 / 4)
        * _stencil_shift(halo, 1, -3, 7, 'periodic') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -3, 7, 'periodic') +
        (7 / 108)
        * _stencil_shift(halo, 3, -3, 7, 'periodic') +
        (-7 / 528)
        * _stencil_shift(halo, 4, -3, 7, 'periodic') +
        (7 / 3300)
        * _stencil_shift(halo, 5, -3, 7, 'periodic') +
        (-7 / 30888)
        * _stencil_shift(halo, 6, -3, 7, 'periodic') +
        (1 / 84084)
        * _stencil_shift(halo, 7, -3, 7, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 14, -3, 'periodic'] = _fd_d2_a14_axis3_periodic


def _fd_d2_a14_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 14, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 7, 'zero', 2)
    result = (
        (1 / 84084)
        * _stencil_shift(halo, -7, -3, 7, 'zero') +
        (-7 / 30888)
        * _stencil_shift(halo, -6, -3, 7, 'zero') +
        (7 / 3300)
        * _stencil_shift(halo, -5, -3, 7, 'zero') +
        (-7 / 528)
        * _stencil_shift(halo, -4, -3, 7, 'zero') +
        (7 / 108)
        * _stencil_shift(halo, -3, -3, 7, 'zero') +
        (-7 / 24)
        * _stencil_shift(halo, -2, -3, 7, 'zero') +
        (7 / 4)
        * _stencil_shift(halo, -1, -3, 7, 'zero') +
        (-266681 / 88200)
        * _stencil_shift(halo, 0, -3, 7, 'zero') +
        (7 / 4)
        * _stencil_shift(halo, 1, -3, 7, 'zero') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -3, 7, 'zero') +
        (7 / 108)
        * _stencil_shift(halo, 3, -3, 7, 'zero') +
        (-7 / 528)
        * _stencil_shift(halo, 4, -3, 7, 'zero') +
        (7 / 3300)
        * _stencil_shift(halo, 5, -3, 7, 'zero') +
        (-7 / 30888)
        * _stencil_shift(halo, 6, -3, 7, 'zero') +
        (1 / 84084)
        * _stencil_shift(halo, 7, -3, 7, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 14, -3, 'zero'] = _fd_d2_a14_axis3_zero


def _fd_d2_a14_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 14, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 7, 'reflect', 2)
    result = (
        (1 / 84084)
        * _stencil_shift(halo, -7, -3, 7, 'reflect') +
        (-7 / 30888)
        * _stencil_shift(halo, -6, -3, 7, 'reflect') +
        (7 / 3300)
        * _stencil_shift(halo, -5, -3, 7, 'reflect') +
        (-7 / 528)
        * _stencil_shift(halo, -4, -3, 7, 'reflect') +
        (7 / 108)
        * _stencil_shift(halo, -3, -3, 7, 'reflect') +
        (-7 / 24)
        * _stencil_shift(halo, -2, -3, 7, 'reflect') +
        (7 / 4)
        * _stencil_shift(halo, -1, -3, 7, 'reflect') +
        (-266681 / 88200)
        * _stencil_shift(halo, 0, -3, 7, 'reflect') +
        (7 / 4)
        * _stencil_shift(halo, 1, -3, 7, 'reflect') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -3, 7, 'reflect') +
        (7 / 108)
        * _stencil_shift(halo, 3, -3, 7, 'reflect') +
        (-7 / 528)
        * _stencil_shift(halo, 4, -3, 7, 'reflect') +
        (7 / 3300)
        * _stencil_shift(halo, 5, -3, 7, 'reflect') +
        (-7 / 30888)
        * _stencil_shift(halo, 6, -3, 7, 'reflect') +
        (1 / 84084)
        * _stencil_shift(halo, 7, -3, 7, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 14, -3, 'reflect'] = _fd_d2_a14_axis3_reflect


def _fd_d2_a14_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 14, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 7, 'periodic', 2)
    result = (
        (1 / 84084)
        * _stencil_shift(halo, -7, -2, 7, 'periodic') +
        (-7 / 30888)
        * _stencil_shift(halo, -6, -2, 7, 'periodic') +
        (7 / 3300)
        * _stencil_shift(halo, -5, -2, 7, 'periodic') +
        (-7 / 528)
        * _stencil_shift(halo, -4, -2, 7, 'periodic') +
        (7 / 108)
        * _stencil_shift(halo, -3, -2, 7, 'periodic') +
        (-7 / 24)
        * _stencil_shift(halo, -2, -2, 7, 'periodic') +
        (7 / 4)
        * _stencil_shift(halo, -1, -2, 7, 'periodic') +
        (-266681 / 88200)
        * _stencil_shift(halo, 0, -2, 7, 'periodic') +
        (7 / 4)
        * _stencil_shift(halo, 1, -2, 7, 'periodic') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -2, 7, 'periodic') +
        (7 / 108)
        * _stencil_shift(halo, 3, -2, 7, 'periodic') +
        (-7 / 528)
        * _stencil_shift(halo, 4, -2, 7, 'periodic') +
        (7 / 3300)
        * _stencil_shift(halo, 5, -2, 7, 'periodic') +
        (-7 / 30888)
        * _stencil_shift(halo, 6, -2, 7, 'periodic') +
        (1 / 84084)
        * _stencil_shift(halo, 7, -2, 7, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 14, -2, 'periodic'] = _fd_d2_a14_axis2_periodic


def _fd_d2_a14_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 14, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 7, 'zero', 2)
    result = (
        (1 / 84084)
        * _stencil_shift(halo, -7, -2, 7, 'zero') +
        (-7 / 30888)
        * _stencil_shift(halo, -6, -2, 7, 'zero') +
        (7 / 3300)
        * _stencil_shift(halo, -5, -2, 7, 'zero') +
        (-7 / 528)
        * _stencil_shift(halo, -4, -2, 7, 'zero') +
        (7 / 108)
        * _stencil_shift(halo, -3, -2, 7, 'zero') +
        (-7 / 24)
        * _stencil_shift(halo, -2, -2, 7, 'zero') +
        (7 / 4)
        * _stencil_shift(halo, -1, -2, 7, 'zero') +
        (-266681 / 88200)
        * _stencil_shift(halo, 0, -2, 7, 'zero') +
        (7 / 4)
        * _stencil_shift(halo, 1, -2, 7, 'zero') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -2, 7, 'zero') +
        (7 / 108)
        * _stencil_shift(halo, 3, -2, 7, 'zero') +
        (-7 / 528)
        * _stencil_shift(halo, 4, -2, 7, 'zero') +
        (7 / 3300)
        * _stencil_shift(halo, 5, -2, 7, 'zero') +
        (-7 / 30888)
        * _stencil_shift(halo, 6, -2, 7, 'zero') +
        (1 / 84084)
        * _stencil_shift(halo, 7, -2, 7, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 14, -2, 'zero'] = _fd_d2_a14_axis2_zero


def _fd_d2_a14_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 14, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 7, 'reflect', 2)
    result = (
        (1 / 84084)
        * _stencil_shift(halo, -7, -2, 7, 'reflect') +
        (-7 / 30888)
        * _stencil_shift(halo, -6, -2, 7, 'reflect') +
        (7 / 3300)
        * _stencil_shift(halo, -5, -2, 7, 'reflect') +
        (-7 / 528)
        * _stencil_shift(halo, -4, -2, 7, 'reflect') +
        (7 / 108)
        * _stencil_shift(halo, -3, -2, 7, 'reflect') +
        (-7 / 24)
        * _stencil_shift(halo, -2, -2, 7, 'reflect') +
        (7 / 4)
        * _stencil_shift(halo, -1, -2, 7, 'reflect') +
        (-266681 / 88200)
        * _stencil_shift(halo, 0, -2, 7, 'reflect') +
        (7 / 4)
        * _stencil_shift(halo, 1, -2, 7, 'reflect') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -2, 7, 'reflect') +
        (7 / 108)
        * _stencil_shift(halo, 3, -2, 7, 'reflect') +
        (-7 / 528)
        * _stencil_shift(halo, 4, -2, 7, 'reflect') +
        (7 / 3300)
        * _stencil_shift(halo, 5, -2, 7, 'reflect') +
        (-7 / 30888)
        * _stencil_shift(halo, 6, -2, 7, 'reflect') +
        (1 / 84084)
        * _stencil_shift(halo, 7, -2, 7, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 14, -2, 'reflect'] = _fd_d2_a14_axis2_reflect


def _fd_d2_a14_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 14, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 7, 'periodic', 2)
    result = (
        (1 / 84084)
        * _stencil_shift(halo, -7, -1, 7, 'periodic') +
        (-7 / 30888)
        * _stencil_shift(halo, -6, -1, 7, 'periodic') +
        (7 / 3300)
        * _stencil_shift(halo, -5, -1, 7, 'periodic') +
        (-7 / 528)
        * _stencil_shift(halo, -4, -1, 7, 'periodic') +
        (7 / 108)
        * _stencil_shift(halo, -3, -1, 7, 'periodic') +
        (-7 / 24)
        * _stencil_shift(halo, -2, -1, 7, 'periodic') +
        (7 / 4)
        * _stencil_shift(halo, -1, -1, 7, 'periodic') +
        (-266681 / 88200)
        * _stencil_shift(halo, 0, -1, 7, 'periodic') +
        (7 / 4)
        * _stencil_shift(halo, 1, -1, 7, 'periodic') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -1, 7, 'periodic') +
        (7 / 108)
        * _stencil_shift(halo, 3, -1, 7, 'periodic') +
        (-7 / 528)
        * _stencil_shift(halo, 4, -1, 7, 'periodic') +
        (7 / 3300)
        * _stencil_shift(halo, 5, -1, 7, 'periodic') +
        (-7 / 30888)
        * _stencil_shift(halo, 6, -1, 7, 'periodic') +
        (1 / 84084)
        * _stencil_shift(halo, 7, -1, 7, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 14, -1, 'periodic'] = _fd_d2_a14_axis1_periodic


def _fd_d2_a14_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 14, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 7, 'zero', 2)
    result = (
        (1 / 84084)
        * _stencil_shift(halo, -7, -1, 7, 'zero') +
        (-7 / 30888)
        * _stencil_shift(halo, -6, -1, 7, 'zero') +
        (7 / 3300)
        * _stencil_shift(halo, -5, -1, 7, 'zero') +
        (-7 / 528)
        * _stencil_shift(halo, -4, -1, 7, 'zero') +
        (7 / 108)
        * _stencil_shift(halo, -3, -1, 7, 'zero') +
        (-7 / 24)
        * _stencil_shift(halo, -2, -1, 7, 'zero') +
        (7 / 4)
        * _stencil_shift(halo, -1, -1, 7, 'zero') +
        (-266681 / 88200)
        * _stencil_shift(halo, 0, -1, 7, 'zero') +
        (7 / 4)
        * _stencil_shift(halo, 1, -1, 7, 'zero') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -1, 7, 'zero') +
        (7 / 108)
        * _stencil_shift(halo, 3, -1, 7, 'zero') +
        (-7 / 528)
        * _stencil_shift(halo, 4, -1, 7, 'zero') +
        (7 / 3300)
        * _stencil_shift(halo, 5, -1, 7, 'zero') +
        (-7 / 30888)
        * _stencil_shift(halo, 6, -1, 7, 'zero') +
        (1 / 84084)
        * _stencil_shift(halo, 7, -1, 7, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 14, -1, 'zero'] = _fd_d2_a14_axis1_zero


def _fd_d2_a14_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 14, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 7, 'reflect', 2)
    result = (
        (1 / 84084)
        * _stencil_shift(halo, -7, -1, 7, 'reflect') +
        (-7 / 30888)
        * _stencil_shift(halo, -6, -1, 7, 'reflect') +
        (7 / 3300)
        * _stencil_shift(halo, -5, -1, 7, 'reflect') +
        (-7 / 528)
        * _stencil_shift(halo, -4, -1, 7, 'reflect') +
        (7 / 108)
        * _stencil_shift(halo, -3, -1, 7, 'reflect') +
        (-7 / 24)
        * _stencil_shift(halo, -2, -1, 7, 'reflect') +
        (7 / 4)
        * _stencil_shift(halo, -1, -1, 7, 'reflect') +
        (-266681 / 88200)
        * _stencil_shift(halo, 0, -1, 7, 'reflect') +
        (7 / 4)
        * _stencil_shift(halo, 1, -1, 7, 'reflect') +
        (-7 / 24)
        * _stencil_shift(halo, 2, -1, 7, 'reflect') +
        (7 / 108)
        * _stencil_shift(halo, 3, -1, 7, 'reflect') +
        (-7 / 528)
        * _stencil_shift(halo, 4, -1, 7, 'reflect') +
        (7 / 3300)
        * _stencil_shift(halo, 5, -1, 7, 'reflect') +
        (-7 / 30888)
        * _stencil_shift(halo, 6, -1, 7, 'reflect') +
        (1 / 84084)
        * _stencil_shift(halo, 7, -1, 7, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 14, -1, 'reflect'] = _fd_d2_a14_axis1_reflect


STENCIL_MOMENTS[2, 16] = (
    (-8, -1, 411840),
    (-7, 16, 315315),
    (-6, -2, 3861),
    (-5, 112, 32175),
    (-4, -7, 396),
    (-3, 112, 1485),
    (-2, -14, 45),
    (-1, 16, 9),
    (0, -1077749, 352800),
    (1, 16, 9),
    (2, -14, 45),
    (3, 112, 1485),
    (4, -7, 396),
    (5, 112, 32175),
    (6, -2, 3861),
    (7, 16, 315315),
    (8, -1, 411840),
)

def _fd_d2_a16_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 16, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 8, 'periodic', 2)
    result = (
        (-1 / 411840)
        * _stencil_shift(halo, -8, -4, 8, 'periodic') +
        (16 / 315315)
        * _stencil_shift(halo, -7, -4, 8, 'periodic') +
        (-2 / 3861)
        * _stencil_shift(halo, -6, -4, 8, 'periodic') +
        (112 / 32175)
        * _stencil_shift(halo, -5, -4, 8, 'periodic') +
        (-7 / 396)
        * _stencil_shift(halo, -4, -4, 8, 'periodic') +
        (112 / 1485)
        * _stencil_shift(halo, -3, -4, 8, 'periodic') +
        (-14 / 45)
        * _stencil_shift(halo, -2, -4, 8, 'periodic') +
        (16 / 9)
        * _stencil_shift(halo, -1, -4, 8, 'periodic') +
        (-1077749 / 352800)
        * _stencil_shift(halo, 0, -4, 8, 'periodic') +
        (16 / 9)
        * _stencil_shift(halo, 1, -4, 8, 'periodic') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -4, 8, 'periodic') +
        (112 / 1485)
        * _stencil_shift(halo, 3, -4, 8, 'periodic') +
        (-7 / 396)
        * _stencil_shift(halo, 4, -4, 8, 'periodic') +
        (112 / 32175)
        * _stencil_shift(halo, 5, -4, 8, 'periodic') +
        (-2 / 3861)
        * _stencil_shift(halo, 6, -4, 8, 'periodic') +
        (16 / 315315)
        * _stencil_shift(halo, 7, -4, 8, 'periodic') +
        (-1 / 411840)
        * _stencil_shift(halo, 8, -4, 8, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 16, -4, 'periodic'] = _fd_d2_a16_axis4_periodic


def _fd_d2_a16_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 16, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 8, 'zero', 2)
    result = (
        (-1 / 411840)
        * _stencil_shift(halo, -8, -4, 8, 'zero') +
        (16 / 315315)
        * _stencil_shift(halo, -7, -4, 8, 'zero') +
        (-2 / 3861)
        * _stencil_shift(halo, -6, -4, 8, 'zero') +
        (112 / 32175)
        * _stencil_shift(halo, -5, -4, 8, 'zero') +
        (-7 / 396)
        * _stencil_shift(halo, -4, -4, 8, 'zero') +
        (112 / 1485)
        * _stencil_shift(halo, -3, -4, 8, 'zero') +
        (-14 / 45)
        * _stencil_shift(halo, -2, -4, 8, 'zero') +
        (16 / 9)
        * _stencil_shift(halo, -1, -4, 8, 'zero') +
        (-1077749 / 352800)
        * _stencil_shift(halo, 0, -4, 8, 'zero') +
        (16 / 9)
        * _stencil_shift(halo, 1, -4, 8, 'zero') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -4, 8, 'zero') +
        (112 / 1485)
        * _stencil_shift(halo, 3, -4, 8, 'zero') +
        (-7 / 396)
        * _stencil_shift(halo, 4, -4, 8, 'zero') +
        (112 / 32175)
        * _stencil_shift(halo, 5, -4, 8, 'zero') +
        (-2 / 3861)
        * _stencil_shift(halo, 6, -4, 8, 'zero') +
        (16 / 315315)
        * _stencil_shift(halo, 7, -4, 8, 'zero') +
        (-1 / 411840)
        * _stencil_shift(halo, 8, -4, 8, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 16, -4, 'zero'] = _fd_d2_a16_axis4_zero


def _fd_d2_a16_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 16, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 8, 'reflect', 2)
    result = (
        (-1 / 411840)
        * _stencil_shift(halo, -8, -4, 8, 'reflect') +
        (16 / 315315)
        * _stencil_shift(halo, -7, -4, 8, 'reflect') +
        (-2 / 3861)
        * _stencil_shift(halo, -6, -4, 8, 'reflect') +
        (112 / 32175)
        * _stencil_shift(halo, -5, -4, 8, 'reflect') +
        (-7 / 396)
        * _stencil_shift(halo, -4, -4, 8, 'reflect') +
        (112 / 1485)
        * _stencil_shift(halo, -3, -4, 8, 'reflect') +
        (-14 / 45)
        * _stencil_shift(halo, -2, -4, 8, 'reflect') +
        (16 / 9)
        * _stencil_shift(halo, -1, -4, 8, 'reflect') +
        (-1077749 / 352800)
        * _stencil_shift(halo, 0, -4, 8, 'reflect') +
        (16 / 9)
        * _stencil_shift(halo, 1, -4, 8, 'reflect') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -4, 8, 'reflect') +
        (112 / 1485)
        * _stencil_shift(halo, 3, -4, 8, 'reflect') +
        (-7 / 396)
        * _stencil_shift(halo, 4, -4, 8, 'reflect') +
        (112 / 32175)
        * _stencil_shift(halo, 5, -4, 8, 'reflect') +
        (-2 / 3861)
        * _stencil_shift(halo, 6, -4, 8, 'reflect') +
        (16 / 315315)
        * _stencil_shift(halo, 7, -4, 8, 'reflect') +
        (-1 / 411840)
        * _stencil_shift(halo, 8, -4, 8, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 16, -4, 'reflect'] = _fd_d2_a16_axis4_reflect


def _fd_d2_a16_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 16, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 8, 'periodic', 2)
    result = (
        (-1 / 411840)
        * _stencil_shift(halo, -8, -3, 8, 'periodic') +
        (16 / 315315)
        * _stencil_shift(halo, -7, -3, 8, 'periodic') +
        (-2 / 3861)
        * _stencil_shift(halo, -6, -3, 8, 'periodic') +
        (112 / 32175)
        * _stencil_shift(halo, -5, -3, 8, 'periodic') +
        (-7 / 396)
        * _stencil_shift(halo, -4, -3, 8, 'periodic') +
        (112 / 1485)
        * _stencil_shift(halo, -3, -3, 8, 'periodic') +
        (-14 / 45)
        * _stencil_shift(halo, -2, -3, 8, 'periodic') +
        (16 / 9)
        * _stencil_shift(halo, -1, -3, 8, 'periodic') +
        (-1077749 / 352800)
        * _stencil_shift(halo, 0, -3, 8, 'periodic') +
        (16 / 9)
        * _stencil_shift(halo, 1, -3, 8, 'periodic') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -3, 8, 'periodic') +
        (112 / 1485)
        * _stencil_shift(halo, 3, -3, 8, 'periodic') +
        (-7 / 396)
        * _stencil_shift(halo, 4, -3, 8, 'periodic') +
        (112 / 32175)
        * _stencil_shift(halo, 5, -3, 8, 'periodic') +
        (-2 / 3861)
        * _stencil_shift(halo, 6, -3, 8, 'periodic') +
        (16 / 315315)
        * _stencil_shift(halo, 7, -3, 8, 'periodic') +
        (-1 / 411840)
        * _stencil_shift(halo, 8, -3, 8, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 16, -3, 'periodic'] = _fd_d2_a16_axis3_periodic


def _fd_d2_a16_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 16, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 8, 'zero', 2)
    result = (
        (-1 / 411840)
        * _stencil_shift(halo, -8, -3, 8, 'zero') +
        (16 / 315315)
        * _stencil_shift(halo, -7, -3, 8, 'zero') +
        (-2 / 3861)
        * _stencil_shift(halo, -6, -3, 8, 'zero') +
        (112 / 32175)
        * _stencil_shift(halo, -5, -3, 8, 'zero') +
        (-7 / 396)
        * _stencil_shift(halo, -4, -3, 8, 'zero') +
        (112 / 1485)
        * _stencil_shift(halo, -3, -3, 8, 'zero') +
        (-14 / 45)
        * _stencil_shift(halo, -2, -3, 8, 'zero') +
        (16 / 9)
        * _stencil_shift(halo, -1, -3, 8, 'zero') +
        (-1077749 / 352800)
        * _stencil_shift(halo, 0, -3, 8, 'zero') +
        (16 / 9)
        * _stencil_shift(halo, 1, -3, 8, 'zero') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -3, 8, 'zero') +
        (112 / 1485)
        * _stencil_shift(halo, 3, -3, 8, 'zero') +
        (-7 / 396)
        * _stencil_shift(halo, 4, -3, 8, 'zero') +
        (112 / 32175)
        * _stencil_shift(halo, 5, -3, 8, 'zero') +
        (-2 / 3861)
        * _stencil_shift(halo, 6, -3, 8, 'zero') +
        (16 / 315315)
        * _stencil_shift(halo, 7, -3, 8, 'zero') +
        (-1 / 411840)
        * _stencil_shift(halo, 8, -3, 8, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 16, -3, 'zero'] = _fd_d2_a16_axis3_zero


def _fd_d2_a16_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 16, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 8, 'reflect', 2)
    result = (
        (-1 / 411840)
        * _stencil_shift(halo, -8, -3, 8, 'reflect') +
        (16 / 315315)
        * _stencil_shift(halo, -7, -3, 8, 'reflect') +
        (-2 / 3861)
        * _stencil_shift(halo, -6, -3, 8, 'reflect') +
        (112 / 32175)
        * _stencil_shift(halo, -5, -3, 8, 'reflect') +
        (-7 / 396)
        * _stencil_shift(halo, -4, -3, 8, 'reflect') +
        (112 / 1485)
        * _stencil_shift(halo, -3, -3, 8, 'reflect') +
        (-14 / 45)
        * _stencil_shift(halo, -2, -3, 8, 'reflect') +
        (16 / 9)
        * _stencil_shift(halo, -1, -3, 8, 'reflect') +
        (-1077749 / 352800)
        * _stencil_shift(halo, 0, -3, 8, 'reflect') +
        (16 / 9)
        * _stencil_shift(halo, 1, -3, 8, 'reflect') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -3, 8, 'reflect') +
        (112 / 1485)
        * _stencil_shift(halo, 3, -3, 8, 'reflect') +
        (-7 / 396)
        * _stencil_shift(halo, 4, -3, 8, 'reflect') +
        (112 / 32175)
        * _stencil_shift(halo, 5, -3, 8, 'reflect') +
        (-2 / 3861)
        * _stencil_shift(halo, 6, -3, 8, 'reflect') +
        (16 / 315315)
        * _stencil_shift(halo, 7, -3, 8, 'reflect') +
        (-1 / 411840)
        * _stencil_shift(halo, 8, -3, 8, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 16, -3, 'reflect'] = _fd_d2_a16_axis3_reflect


def _fd_d2_a16_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 16, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 8, 'periodic', 2)
    result = (
        (-1 / 411840)
        * _stencil_shift(halo, -8, -2, 8, 'periodic') +
        (16 / 315315)
        * _stencil_shift(halo, -7, -2, 8, 'periodic') +
        (-2 / 3861)
        * _stencil_shift(halo, -6, -2, 8, 'periodic') +
        (112 / 32175)
        * _stencil_shift(halo, -5, -2, 8, 'periodic') +
        (-7 / 396)
        * _stencil_shift(halo, -4, -2, 8, 'periodic') +
        (112 / 1485)
        * _stencil_shift(halo, -3, -2, 8, 'periodic') +
        (-14 / 45)
        * _stencil_shift(halo, -2, -2, 8, 'periodic') +
        (16 / 9)
        * _stencil_shift(halo, -1, -2, 8, 'periodic') +
        (-1077749 / 352800)
        * _stencil_shift(halo, 0, -2, 8, 'periodic') +
        (16 / 9)
        * _stencil_shift(halo, 1, -2, 8, 'periodic') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -2, 8, 'periodic') +
        (112 / 1485)
        * _stencil_shift(halo, 3, -2, 8, 'periodic') +
        (-7 / 396)
        * _stencil_shift(halo, 4, -2, 8, 'periodic') +
        (112 / 32175)
        * _stencil_shift(halo, 5, -2, 8, 'periodic') +
        (-2 / 3861)
        * _stencil_shift(halo, 6, -2, 8, 'periodic') +
        (16 / 315315)
        * _stencil_shift(halo, 7, -2, 8, 'periodic') +
        (-1 / 411840)
        * _stencil_shift(halo, 8, -2, 8, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 16, -2, 'periodic'] = _fd_d2_a16_axis2_periodic


def _fd_d2_a16_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 16, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 8, 'zero', 2)
    result = (
        (-1 / 411840)
        * _stencil_shift(halo, -8, -2, 8, 'zero') +
        (16 / 315315)
        * _stencil_shift(halo, -7, -2, 8, 'zero') +
        (-2 / 3861)
        * _stencil_shift(halo, -6, -2, 8, 'zero') +
        (112 / 32175)
        * _stencil_shift(halo, -5, -2, 8, 'zero') +
        (-7 / 396)
        * _stencil_shift(halo, -4, -2, 8, 'zero') +
        (112 / 1485)
        * _stencil_shift(halo, -3, -2, 8, 'zero') +
        (-14 / 45)
        * _stencil_shift(halo, -2, -2, 8, 'zero') +
        (16 / 9)
        * _stencil_shift(halo, -1, -2, 8, 'zero') +
        (-1077749 / 352800)
        * _stencil_shift(halo, 0, -2, 8, 'zero') +
        (16 / 9)
        * _stencil_shift(halo, 1, -2, 8, 'zero') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -2, 8, 'zero') +
        (112 / 1485)
        * _stencil_shift(halo, 3, -2, 8, 'zero') +
        (-7 / 396)
        * _stencil_shift(halo, 4, -2, 8, 'zero') +
        (112 / 32175)
        * _stencil_shift(halo, 5, -2, 8, 'zero') +
        (-2 / 3861)
        * _stencil_shift(halo, 6, -2, 8, 'zero') +
        (16 / 315315)
        * _stencil_shift(halo, 7, -2, 8, 'zero') +
        (-1 / 411840)
        * _stencil_shift(halo, 8, -2, 8, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 16, -2, 'zero'] = _fd_d2_a16_axis2_zero


def _fd_d2_a16_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 16, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 8, 'reflect', 2)
    result = (
        (-1 / 411840)
        * _stencil_shift(halo, -8, -2, 8, 'reflect') +
        (16 / 315315)
        * _stencil_shift(halo, -7, -2, 8, 'reflect') +
        (-2 / 3861)
        * _stencil_shift(halo, -6, -2, 8, 'reflect') +
        (112 / 32175)
        * _stencil_shift(halo, -5, -2, 8, 'reflect') +
        (-7 / 396)
        * _stencil_shift(halo, -4, -2, 8, 'reflect') +
        (112 / 1485)
        * _stencil_shift(halo, -3, -2, 8, 'reflect') +
        (-14 / 45)
        * _stencil_shift(halo, -2, -2, 8, 'reflect') +
        (16 / 9)
        * _stencil_shift(halo, -1, -2, 8, 'reflect') +
        (-1077749 / 352800)
        * _stencil_shift(halo, 0, -2, 8, 'reflect') +
        (16 / 9)
        * _stencil_shift(halo, 1, -2, 8, 'reflect') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -2, 8, 'reflect') +
        (112 / 1485)
        * _stencil_shift(halo, 3, -2, 8, 'reflect') +
        (-7 / 396)
        * _stencil_shift(halo, 4, -2, 8, 'reflect') +
        (112 / 32175)
        * _stencil_shift(halo, 5, -2, 8, 'reflect') +
        (-2 / 3861)
        * _stencil_shift(halo, 6, -2, 8, 'reflect') +
        (16 / 315315)
        * _stencil_shift(halo, 7, -2, 8, 'reflect') +
        (-1 / 411840)
        * _stencil_shift(halo, 8, -2, 8, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 16, -2, 'reflect'] = _fd_d2_a16_axis2_reflect


def _fd_d2_a16_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 16, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 8, 'periodic', 2)
    result = (
        (-1 / 411840)
        * _stencil_shift(halo, -8, -1, 8, 'periodic') +
        (16 / 315315)
        * _stencil_shift(halo, -7, -1, 8, 'periodic') +
        (-2 / 3861)
        * _stencil_shift(halo, -6, -1, 8, 'periodic') +
        (112 / 32175)
        * _stencil_shift(halo, -5, -1, 8, 'periodic') +
        (-7 / 396)
        * _stencil_shift(halo, -4, -1, 8, 'periodic') +
        (112 / 1485)
        * _stencil_shift(halo, -3, -1, 8, 'periodic') +
        (-14 / 45)
        * _stencil_shift(halo, -2, -1, 8, 'periodic') +
        (16 / 9)
        * _stencil_shift(halo, -1, -1, 8, 'periodic') +
        (-1077749 / 352800)
        * _stencil_shift(halo, 0, -1, 8, 'periodic') +
        (16 / 9)
        * _stencil_shift(halo, 1, -1, 8, 'periodic') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -1, 8, 'periodic') +
        (112 / 1485)
        * _stencil_shift(halo, 3, -1, 8, 'periodic') +
        (-7 / 396)
        * _stencil_shift(halo, 4, -1, 8, 'periodic') +
        (112 / 32175)
        * _stencil_shift(halo, 5, -1, 8, 'periodic') +
        (-2 / 3861)
        * _stencil_shift(halo, 6, -1, 8, 'periodic') +
        (16 / 315315)
        * _stencil_shift(halo, 7, -1, 8, 'periodic') +
        (-1 / 411840)
        * _stencil_shift(halo, 8, -1, 8, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 16, -1, 'periodic'] = _fd_d2_a16_axis1_periodic


def _fd_d2_a16_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 16, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 8, 'zero', 2)
    result = (
        (-1 / 411840)
        * _stencil_shift(halo, -8, -1, 8, 'zero') +
        (16 / 315315)
        * _stencil_shift(halo, -7, -1, 8, 'zero') +
        (-2 / 3861)
        * _stencil_shift(halo, -6, -1, 8, 'zero') +
        (112 / 32175)
        * _stencil_shift(halo, -5, -1, 8, 'zero') +
        (-7 / 396)
        * _stencil_shift(halo, -4, -1, 8, 'zero') +
        (112 / 1485)
        * _stencil_shift(halo, -3, -1, 8, 'zero') +
        (-14 / 45)
        * _stencil_shift(halo, -2, -1, 8, 'zero') +
        (16 / 9)
        * _stencil_shift(halo, -1, -1, 8, 'zero') +
        (-1077749 / 352800)
        * _stencil_shift(halo, 0, -1, 8, 'zero') +
        (16 / 9)
        * _stencil_shift(halo, 1, -1, 8, 'zero') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -1, 8, 'zero') +
        (112 / 1485)
        * _stencil_shift(halo, 3, -1, 8, 'zero') +
        (-7 / 396)
        * _stencil_shift(halo, 4, -1, 8, 'zero') +
        (112 / 32175)
        * _stencil_shift(halo, 5, -1, 8, 'zero') +
        (-2 / 3861)
        * _stencil_shift(halo, 6, -1, 8, 'zero') +
        (16 / 315315)
        * _stencil_shift(halo, 7, -1, 8, 'zero') +
        (-1 / 411840)
        * _stencil_shift(halo, 8, -1, 8, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 16, -1, 'zero'] = _fd_d2_a16_axis1_zero


def _fd_d2_a16_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 16, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 8, 'reflect', 2)
    result = (
        (-1 / 411840)
        * _stencil_shift(halo, -8, -1, 8, 'reflect') +
        (16 / 315315)
        * _stencil_shift(halo, -7, -1, 8, 'reflect') +
        (-2 / 3861)
        * _stencil_shift(halo, -6, -1, 8, 'reflect') +
        (112 / 32175)
        * _stencil_shift(halo, -5, -1, 8, 'reflect') +
        (-7 / 396)
        * _stencil_shift(halo, -4, -1, 8, 'reflect') +
        (112 / 1485)
        * _stencil_shift(halo, -3, -1, 8, 'reflect') +
        (-14 / 45)
        * _stencil_shift(halo, -2, -1, 8, 'reflect') +
        (16 / 9)
        * _stencil_shift(halo, -1, -1, 8, 'reflect') +
        (-1077749 / 352800)
        * _stencil_shift(halo, 0, -1, 8, 'reflect') +
        (16 / 9)
        * _stencil_shift(halo, 1, -1, 8, 'reflect') +
        (-14 / 45)
        * _stencil_shift(halo, 2, -1, 8, 'reflect') +
        (112 / 1485)
        * _stencil_shift(halo, 3, -1, 8, 'reflect') +
        (-7 / 396)
        * _stencil_shift(halo, 4, -1, 8, 'reflect') +
        (112 / 32175)
        * _stencil_shift(halo, 5, -1, 8, 'reflect') +
        (-2 / 3861)
        * _stencil_shift(halo, 6, -1, 8, 'reflect') +
        (16 / 315315)
        * _stencil_shift(halo, 7, -1, 8, 'reflect') +
        (-1 / 411840)
        * _stencil_shift(halo, 8, -1, 8, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 16, -1, 'reflect'] = _fd_d2_a16_axis1_reflect


STENCIL_MOMENTS[2, 18] = (
    (-9, 1, 1969110),
    (-8, -9, 777920),
    (-7, 9, 70070),
    (-6, -2, 2145),
    (-5, 18, 3575),
    (-4, -63, 2860),
    (-3, 14, 165),
    (-2, -18, 55),
    (-1, 9, 5),
    (0, -9778141, 3175200),
    (1, 9, 5),
    (2, -18, 55),
    (3, 14, 165),
    (4, -63, 2860),
    (5, 18, 3575),
    (6, -2, 2145),
    (7, 9, 70070),
    (8, -9, 777920),
    (9, 1, 1969110),
)

def _fd_d2_a18_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 18, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 9, 'periodic', 2)
    result = (
        (1 / 1969110)
        * _stencil_shift(halo, -9, -4, 9, 'periodic') +
        (-9 / 777920)
        * _stencil_shift(halo, -8, -4, 9, 'periodic') +
        (9 / 70070)
        * _stencil_shift(halo, -7, -4, 9, 'periodic') +
        (-2 / 2145)
        * _stencil_shift(halo, -6, -4, 9, 'periodic') +
        (18 / 3575)
        * _stencil_shift(halo, -5, -4, 9, 'periodic') +
        (-63 / 2860)
        * _stencil_shift(halo, -4, -4, 9, 'periodic') +
        (14 / 165)
        * _stencil_shift(halo, -3, -4, 9, 'periodic') +
        (-18 / 55)
        * _stencil_shift(halo, -2, -4, 9, 'periodic') +
        (9 / 5)
        * _stencil_shift(halo, -1, -4, 9, 'periodic') +
        (-9778141 / 3175200)
        * _stencil_shift(halo, 0, -4, 9, 'periodic') +
        (9 / 5)
        * _stencil_shift(halo, 1, -4, 9, 'periodic') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -4, 9, 'periodic') +
        (14 / 165)
        * _stencil_shift(halo, 3, -4, 9, 'periodic') +
        (-63 / 2860)
        * _stencil_shift(halo, 4, -4, 9, 'periodic') +
        (18 / 3575)
        * _stencil_shift(halo, 5, -4, 9, 'periodic') +
        (-2 / 2145)
        * _stencil_shift(halo, 6, -4, 9, 'periodic') +
        (9 / 70070)
        * _stencil_shift(halo, 7, -4, 9, 'periodic') +
        (-9 / 777920)
        * _stencil_shift(halo, 8, -4, 9, 'periodic') +
        (1 / 1969110)
        * _stencil_shift(halo, 9, -4, 9, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 18, -4, 'periodic'] = _fd_d2_a18_axis4_periodic


def _fd_d2_a18_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 18, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 9, 'zero', 2)
    result = (
        (1 / 1969110)
        * _stencil_shift(halo, -9, -4, 9, 'zero') +
        (-9 / 777920)
        * _stencil_shift(halo, -8, -4, 9, 'zero') +
        (9 / 70070)
        * _stencil_shift(halo, -7, -4, 9, 'zero') +
        (-2 / 2145)
        * _stencil_shift(halo, -6, -4, 9, 'zero') +
        (18 / 3575)
        * _stencil_shift(halo, -5, -4, 9, 'zero') +
        (-63 / 2860)
        * _stencil_shift(halo, -4, -4, 9, 'zero') +
        (14 / 165)
        * _stencil_shift(halo, -3, -4, 9, 'zero') +
        (-18 / 55)
        * _stencil_shift(halo, -2, -4, 9, 'zero') +
        (9 / 5)
        * _stencil_shift(halo, -1, -4, 9, 'zero') +
        (-9778141 / 3175200)
        * _stencil_shift(halo, 0, -4, 9, 'zero') +
        (9 / 5)
        * _stencil_shift(halo, 1, -4, 9, 'zero') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -4, 9, 'zero') +
        (14 / 165)
        * _stencil_shift(halo, 3, -4, 9, 'zero') +
        (-63 / 2860)
        * _stencil_shift(halo, 4, -4, 9, 'zero') +
        (18 / 3575)
        * _stencil_shift(halo, 5, -4, 9, 'zero') +
        (-2 / 2145)
        * _stencil_shift(halo, 6, -4, 9, 'zero') +
        (9 / 70070)
        * _stencil_shift(halo, 7, -4, 9, 'zero') +
        (-9 / 777920)
        * _stencil_shift(halo, 8, -4, 9, 'zero') +
        (1 / 1969110)
        * _stencil_shift(halo, 9, -4, 9, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 18, -4, 'zero'] = _fd_d2_a18_axis4_zero


def _fd_d2_a18_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 18, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 9, 'reflect', 2)
    result = (
        (1 / 1969110)
        * _stencil_shift(halo, -9, -4, 9, 'reflect') +
        (-9 / 777920)
        * _stencil_shift(halo, -8, -4, 9, 'reflect') +
        (9 / 70070)
        * _stencil_shift(halo, -7, -4, 9, 'reflect') +
        (-2 / 2145)
        * _stencil_shift(halo, -6, -4, 9, 'reflect') +
        (18 / 3575)
        * _stencil_shift(halo, -5, -4, 9, 'reflect') +
        (-63 / 2860)
        * _stencil_shift(halo, -4, -4, 9, 'reflect') +
        (14 / 165)
        * _stencil_shift(halo, -3, -4, 9, 'reflect') +
        (-18 / 55)
        * _stencil_shift(halo, -2, -4, 9, 'reflect') +
        (9 / 5)
        * _stencil_shift(halo, -1, -4, 9, 'reflect') +
        (-9778141 / 3175200)
        * _stencil_shift(halo, 0, -4, 9, 'reflect') +
        (9 / 5)
        * _stencil_shift(halo, 1, -4, 9, 'reflect') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -4, 9, 'reflect') +
        (14 / 165)
        * _stencil_shift(halo, 3, -4, 9, 'reflect') +
        (-63 / 2860)
        * _stencil_shift(halo, 4, -4, 9, 'reflect') +
        (18 / 3575)
        * _stencil_shift(halo, 5, -4, 9, 'reflect') +
        (-2 / 2145)
        * _stencil_shift(halo, 6, -4, 9, 'reflect') +
        (9 / 70070)
        * _stencil_shift(halo, 7, -4, 9, 'reflect') +
        (-9 / 777920)
        * _stencil_shift(halo, 8, -4, 9, 'reflect') +
        (1 / 1969110)
        * _stencil_shift(halo, 9, -4, 9, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 18, -4, 'reflect'] = _fd_d2_a18_axis4_reflect


def _fd_d2_a18_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 18, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 9, 'periodic', 2)
    result = (
        (1 / 1969110)
        * _stencil_shift(halo, -9, -3, 9, 'periodic') +
        (-9 / 777920)
        * _stencil_shift(halo, -8, -3, 9, 'periodic') +
        (9 / 70070)
        * _stencil_shift(halo, -7, -3, 9, 'periodic') +
        (-2 / 2145)
        * _stencil_shift(halo, -6, -3, 9, 'periodic') +
        (18 / 3575)
        * _stencil_shift(halo, -5, -3, 9, 'periodic') +
        (-63 / 2860)
        * _stencil_shift(halo, -4, -3, 9, 'periodic') +
        (14 / 165)
        * _stencil_shift(halo, -3, -3, 9, 'periodic') +
        (-18 / 55)
        * _stencil_shift(halo, -2, -3, 9, 'periodic') +
        (9 / 5)
        * _stencil_shift(halo, -1, -3, 9, 'periodic') +
        (-9778141 / 3175200)
        * _stencil_shift(halo, 0, -3, 9, 'periodic') +
        (9 / 5)
        * _stencil_shift(halo, 1, -3, 9, 'periodic') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -3, 9, 'periodic') +
        (14 / 165)
        * _stencil_shift(halo, 3, -3, 9, 'periodic') +
        (-63 / 2860)
        * _stencil_shift(halo, 4, -3, 9, 'periodic') +
        (18 / 3575)
        * _stencil_shift(halo, 5, -3, 9, 'periodic') +
        (-2 / 2145)
        * _stencil_shift(halo, 6, -3, 9, 'periodic') +
        (9 / 70070)
        * _stencil_shift(halo, 7, -3, 9, 'periodic') +
        (-9 / 777920)
        * _stencil_shift(halo, 8, -3, 9, 'periodic') +
        (1 / 1969110)
        * _stencil_shift(halo, 9, -3, 9, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 18, -3, 'periodic'] = _fd_d2_a18_axis3_periodic


def _fd_d2_a18_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 18, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 9, 'zero', 2)
    result = (
        (1 / 1969110)
        * _stencil_shift(halo, -9, -3, 9, 'zero') +
        (-9 / 777920)
        * _stencil_shift(halo, -8, -3, 9, 'zero') +
        (9 / 70070)
        * _stencil_shift(halo, -7, -3, 9, 'zero') +
        (-2 / 2145)
        * _stencil_shift(halo, -6, -3, 9, 'zero') +
        (18 / 3575)
        * _stencil_shift(halo, -5, -3, 9, 'zero') +
        (-63 / 2860)
        * _stencil_shift(halo, -4, -3, 9, 'zero') +
        (14 / 165)
        * _stencil_shift(halo, -3, -3, 9, 'zero') +
        (-18 / 55)
        * _stencil_shift(halo, -2, -3, 9, 'zero') +
        (9 / 5)
        * _stencil_shift(halo, -1, -3, 9, 'zero') +
        (-9778141 / 3175200)
        * _stencil_shift(halo, 0, -3, 9, 'zero') +
        (9 / 5)
        * _stencil_shift(halo, 1, -3, 9, 'zero') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -3, 9, 'zero') +
        (14 / 165)
        * _stencil_shift(halo, 3, -3, 9, 'zero') +
        (-63 / 2860)
        * _stencil_shift(halo, 4, -3, 9, 'zero') +
        (18 / 3575)
        * _stencil_shift(halo, 5, -3, 9, 'zero') +
        (-2 / 2145)
        * _stencil_shift(halo, 6, -3, 9, 'zero') +
        (9 / 70070)
        * _stencil_shift(halo, 7, -3, 9, 'zero') +
        (-9 / 777920)
        * _stencil_shift(halo, 8, -3, 9, 'zero') +
        (1 / 1969110)
        * _stencil_shift(halo, 9, -3, 9, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 18, -3, 'zero'] = _fd_d2_a18_axis3_zero


def _fd_d2_a18_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 18, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 9, 'reflect', 2)
    result = (
        (1 / 1969110)
        * _stencil_shift(halo, -9, -3, 9, 'reflect') +
        (-9 / 777920)
        * _stencil_shift(halo, -8, -3, 9, 'reflect') +
        (9 / 70070)
        * _stencil_shift(halo, -7, -3, 9, 'reflect') +
        (-2 / 2145)
        * _stencil_shift(halo, -6, -3, 9, 'reflect') +
        (18 / 3575)
        * _stencil_shift(halo, -5, -3, 9, 'reflect') +
        (-63 / 2860)
        * _stencil_shift(halo, -4, -3, 9, 'reflect') +
        (14 / 165)
        * _stencil_shift(halo, -3, -3, 9, 'reflect') +
        (-18 / 55)
        * _stencil_shift(halo, -2, -3, 9, 'reflect') +
        (9 / 5)
        * _stencil_shift(halo, -1, -3, 9, 'reflect') +
        (-9778141 / 3175200)
        * _stencil_shift(halo, 0, -3, 9, 'reflect') +
        (9 / 5)
        * _stencil_shift(halo, 1, -3, 9, 'reflect') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -3, 9, 'reflect') +
        (14 / 165)
        * _stencil_shift(halo, 3, -3, 9, 'reflect') +
        (-63 / 2860)
        * _stencil_shift(halo, 4, -3, 9, 'reflect') +
        (18 / 3575)
        * _stencil_shift(halo, 5, -3, 9, 'reflect') +
        (-2 / 2145)
        * _stencil_shift(halo, 6, -3, 9, 'reflect') +
        (9 / 70070)
        * _stencil_shift(halo, 7, -3, 9, 'reflect') +
        (-9 / 777920)
        * _stencil_shift(halo, 8, -3, 9, 'reflect') +
        (1 / 1969110)
        * _stencil_shift(halo, 9, -3, 9, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 18, -3, 'reflect'] = _fd_d2_a18_axis3_reflect


def _fd_d2_a18_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 18, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 9, 'periodic', 2)
    result = (
        (1 / 1969110)
        * _stencil_shift(halo, -9, -2, 9, 'periodic') +
        (-9 / 777920)
        * _stencil_shift(halo, -8, -2, 9, 'periodic') +
        (9 / 70070)
        * _stencil_shift(halo, -7, -2, 9, 'periodic') +
        (-2 / 2145)
        * _stencil_shift(halo, -6, -2, 9, 'periodic') +
        (18 / 3575)
        * _stencil_shift(halo, -5, -2, 9, 'periodic') +
        (-63 / 2860)
        * _stencil_shift(halo, -4, -2, 9, 'periodic') +
        (14 / 165)
        * _stencil_shift(halo, -3, -2, 9, 'periodic') +
        (-18 / 55)
        * _stencil_shift(halo, -2, -2, 9, 'periodic') +
        (9 / 5)
        * _stencil_shift(halo, -1, -2, 9, 'periodic') +
        (-9778141 / 3175200)
        * _stencil_shift(halo, 0, -2, 9, 'periodic') +
        (9 / 5)
        * _stencil_shift(halo, 1, -2, 9, 'periodic') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -2, 9, 'periodic') +
        (14 / 165)
        * _stencil_shift(halo, 3, -2, 9, 'periodic') +
        (-63 / 2860)
        * _stencil_shift(halo, 4, -2, 9, 'periodic') +
        (18 / 3575)
        * _stencil_shift(halo, 5, -2, 9, 'periodic') +
        (-2 / 2145)
        * _stencil_shift(halo, 6, -2, 9, 'periodic') +
        (9 / 70070)
        * _stencil_shift(halo, 7, -2, 9, 'periodic') +
        (-9 / 777920)
        * _stencil_shift(halo, 8, -2, 9, 'periodic') +
        (1 / 1969110)
        * _stencil_shift(halo, 9, -2, 9, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 18, -2, 'periodic'] = _fd_d2_a18_axis2_periodic


def _fd_d2_a18_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 18, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 9, 'zero', 2)
    result = (
        (1 / 1969110)
        * _stencil_shift(halo, -9, -2, 9, 'zero') +
        (-9 / 777920)
        * _stencil_shift(halo, -8, -2, 9, 'zero') +
        (9 / 70070)
        * _stencil_shift(halo, -7, -2, 9, 'zero') +
        (-2 / 2145)
        * _stencil_shift(halo, -6, -2, 9, 'zero') +
        (18 / 3575)
        * _stencil_shift(halo, -5, -2, 9, 'zero') +
        (-63 / 2860)
        * _stencil_shift(halo, -4, -2, 9, 'zero') +
        (14 / 165)
        * _stencil_shift(halo, -3, -2, 9, 'zero') +
        (-18 / 55)
        * _stencil_shift(halo, -2, -2, 9, 'zero') +
        (9 / 5)
        * _stencil_shift(halo, -1, -2, 9, 'zero') +
        (-9778141 / 3175200)
        * _stencil_shift(halo, 0, -2, 9, 'zero') +
        (9 / 5)
        * _stencil_shift(halo, 1, -2, 9, 'zero') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -2, 9, 'zero') +
        (14 / 165)
        * _stencil_shift(halo, 3, -2, 9, 'zero') +
        (-63 / 2860)
        * _stencil_shift(halo, 4, -2, 9, 'zero') +
        (18 / 3575)
        * _stencil_shift(halo, 5, -2, 9, 'zero') +
        (-2 / 2145)
        * _stencil_shift(halo, 6, -2, 9, 'zero') +
        (9 / 70070)
        * _stencil_shift(halo, 7, -2, 9, 'zero') +
        (-9 / 777920)
        * _stencil_shift(halo, 8, -2, 9, 'zero') +
        (1 / 1969110)
        * _stencil_shift(halo, 9, -2, 9, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 18, -2, 'zero'] = _fd_d2_a18_axis2_zero


def _fd_d2_a18_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 18, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 9, 'reflect', 2)
    result = (
        (1 / 1969110)
        * _stencil_shift(halo, -9, -2, 9, 'reflect') +
        (-9 / 777920)
        * _stencil_shift(halo, -8, -2, 9, 'reflect') +
        (9 / 70070)
        * _stencil_shift(halo, -7, -2, 9, 'reflect') +
        (-2 / 2145)
        * _stencil_shift(halo, -6, -2, 9, 'reflect') +
        (18 / 3575)
        * _stencil_shift(halo, -5, -2, 9, 'reflect') +
        (-63 / 2860)
        * _stencil_shift(halo, -4, -2, 9, 'reflect') +
        (14 / 165)
        * _stencil_shift(halo, -3, -2, 9, 'reflect') +
        (-18 / 55)
        * _stencil_shift(halo, -2, -2, 9, 'reflect') +
        (9 / 5)
        * _stencil_shift(halo, -1, -2, 9, 'reflect') +
        (-9778141 / 3175200)
        * _stencil_shift(halo, 0, -2, 9, 'reflect') +
        (9 / 5)
        * _stencil_shift(halo, 1, -2, 9, 'reflect') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -2, 9, 'reflect') +
        (14 / 165)
        * _stencil_shift(halo, 3, -2, 9, 'reflect') +
        (-63 / 2860)
        * _stencil_shift(halo, 4, -2, 9, 'reflect') +
        (18 / 3575)
        * _stencil_shift(halo, 5, -2, 9, 'reflect') +
        (-2 / 2145)
        * _stencil_shift(halo, 6, -2, 9, 'reflect') +
        (9 / 70070)
        * _stencil_shift(halo, 7, -2, 9, 'reflect') +
        (-9 / 777920)
        * _stencil_shift(halo, 8, -2, 9, 'reflect') +
        (1 / 1969110)
        * _stencil_shift(halo, 9, -2, 9, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 18, -2, 'reflect'] = _fd_d2_a18_axis2_reflect


def _fd_d2_a18_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 18, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 9, 'periodic', 2)
    result = (
        (1 / 1969110)
        * _stencil_shift(halo, -9, -1, 9, 'periodic') +
        (-9 / 777920)
        * _stencil_shift(halo, -8, -1, 9, 'periodic') +
        (9 / 70070)
        * _stencil_shift(halo, -7, -1, 9, 'periodic') +
        (-2 / 2145)
        * _stencil_shift(halo, -6, -1, 9, 'periodic') +
        (18 / 3575)
        * _stencil_shift(halo, -5, -1, 9, 'periodic') +
        (-63 / 2860)
        * _stencil_shift(halo, -4, -1, 9, 'periodic') +
        (14 / 165)
        * _stencil_shift(halo, -3, -1, 9, 'periodic') +
        (-18 / 55)
        * _stencil_shift(halo, -2, -1, 9, 'periodic') +
        (9 / 5)
        * _stencil_shift(halo, -1, -1, 9, 'periodic') +
        (-9778141 / 3175200)
        * _stencil_shift(halo, 0, -1, 9, 'periodic') +
        (9 / 5)
        * _stencil_shift(halo, 1, -1, 9, 'periodic') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -1, 9, 'periodic') +
        (14 / 165)
        * _stencil_shift(halo, 3, -1, 9, 'periodic') +
        (-63 / 2860)
        * _stencil_shift(halo, 4, -1, 9, 'periodic') +
        (18 / 3575)
        * _stencil_shift(halo, 5, -1, 9, 'periodic') +
        (-2 / 2145)
        * _stencil_shift(halo, 6, -1, 9, 'periodic') +
        (9 / 70070)
        * _stencil_shift(halo, 7, -1, 9, 'periodic') +
        (-9 / 777920)
        * _stencil_shift(halo, 8, -1, 9, 'periodic') +
        (1 / 1969110)
        * _stencil_shift(halo, 9, -1, 9, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 18, -1, 'periodic'] = _fd_d2_a18_axis1_periodic


def _fd_d2_a18_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 18, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 9, 'zero', 2)
    result = (
        (1 / 1969110)
        * _stencil_shift(halo, -9, -1, 9, 'zero') +
        (-9 / 777920)
        * _stencil_shift(halo, -8, -1, 9, 'zero') +
        (9 / 70070)
        * _stencil_shift(halo, -7, -1, 9, 'zero') +
        (-2 / 2145)
        * _stencil_shift(halo, -6, -1, 9, 'zero') +
        (18 / 3575)
        * _stencil_shift(halo, -5, -1, 9, 'zero') +
        (-63 / 2860)
        * _stencil_shift(halo, -4, -1, 9, 'zero') +
        (14 / 165)
        * _stencil_shift(halo, -3, -1, 9, 'zero') +
        (-18 / 55)
        * _stencil_shift(halo, -2, -1, 9, 'zero') +
        (9 / 5)
        * _stencil_shift(halo, -1, -1, 9, 'zero') +
        (-9778141 / 3175200)
        * _stencil_shift(halo, 0, -1, 9, 'zero') +
        (9 / 5)
        * _stencil_shift(halo, 1, -1, 9, 'zero') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -1, 9, 'zero') +
        (14 / 165)
        * _stencil_shift(halo, 3, -1, 9, 'zero') +
        (-63 / 2860)
        * _stencil_shift(halo, 4, -1, 9, 'zero') +
        (18 / 3575)
        * _stencil_shift(halo, 5, -1, 9, 'zero') +
        (-2 / 2145)
        * _stencil_shift(halo, 6, -1, 9, 'zero') +
        (9 / 70070)
        * _stencil_shift(halo, 7, -1, 9, 'zero') +
        (-9 / 777920)
        * _stencil_shift(halo, 8, -1, 9, 'zero') +
        (1 / 1969110)
        * _stencil_shift(halo, 9, -1, 9, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 18, -1, 'zero'] = _fd_d2_a18_axis1_zero


def _fd_d2_a18_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 18, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 9, 'reflect', 2)
    result = (
        (1 / 1969110)
        * _stencil_shift(halo, -9, -1, 9, 'reflect') +
        (-9 / 777920)
        * _stencil_shift(halo, -8, -1, 9, 'reflect') +
        (9 / 70070)
        * _stencil_shift(halo, -7, -1, 9, 'reflect') +
        (-2 / 2145)
        * _stencil_shift(halo, -6, -1, 9, 'reflect') +
        (18 / 3575)
        * _stencil_shift(halo, -5, -1, 9, 'reflect') +
        (-63 / 2860)
        * _stencil_shift(halo, -4, -1, 9, 'reflect') +
        (14 / 165)
        * _stencil_shift(halo, -3, -1, 9, 'reflect') +
        (-18 / 55)
        * _stencil_shift(halo, -2, -1, 9, 'reflect') +
        (9 / 5)
        * _stencil_shift(halo, -1, -1, 9, 'reflect') +
        (-9778141 / 3175200)
        * _stencil_shift(halo, 0, -1, 9, 'reflect') +
        (9 / 5)
        * _stencil_shift(halo, 1, -1, 9, 'reflect') +
        (-18 / 55)
        * _stencil_shift(halo, 2, -1, 9, 'reflect') +
        (14 / 165)
        * _stencil_shift(halo, 3, -1, 9, 'reflect') +
        (-63 / 2860)
        * _stencil_shift(halo, 4, -1, 9, 'reflect') +
        (18 / 3575)
        * _stencil_shift(halo, 5, -1, 9, 'reflect') +
        (-2 / 2145)
        * _stencil_shift(halo, 6, -1, 9, 'reflect') +
        (9 / 70070)
        * _stencil_shift(halo, 7, -1, 9, 'reflect') +
        (-9 / 777920)
        * _stencil_shift(halo, 8, -1, 9, 'reflect') +
        (1 / 1969110)
        * _stencil_shift(halo, 9, -1, 9, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 18, -1, 'reflect'] = _fd_d2_a18_axis1_reflect


STENCIL_MOMENTS[2, 20] = (
    (-10, -1, 9237800),
    (-9, 10, 3741309),
    (-8, -5, 155584),
    (-7, 30, 119119),
    (-6, -5, 3432),
    (-5, 24, 3575),
    (-4, -15, 572),
    (-3, 40, 429),
    (-2, -15, 44),
    (-1, 20, 11),
    (0, -1968329, 635040),
    (1, 20, 11),
    (2, -15, 44),
    (3, 40, 429),
    (4, -15, 572),
    (5, 24, 3575),
    (6, -5, 3432),
    (7, 30, 119119),
    (8, -5, 155584),
    (9, 10, 3741309),
    (10, -1, 9237800),
)

def _fd_d2_a20_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 20, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 10, 'periodic', 2)
    result = (
        (-1 / 9237800)
        * _stencil_shift(halo, -10, -4, 10, 'periodic') +
        (10 / 3741309)
        * _stencil_shift(halo, -9, -4, 10, 'periodic') +
        (-5 / 155584)
        * _stencil_shift(halo, -8, -4, 10, 'periodic') +
        (30 / 119119)
        * _stencil_shift(halo, -7, -4, 10, 'periodic') +
        (-5 / 3432)
        * _stencil_shift(halo, -6, -4, 10, 'periodic') +
        (24 / 3575)
        * _stencil_shift(halo, -5, -4, 10, 'periodic') +
        (-15 / 572)
        * _stencil_shift(halo, -4, -4, 10, 'periodic') +
        (40 / 429)
        * _stencil_shift(halo, -3, -4, 10, 'periodic') +
        (-15 / 44)
        * _stencil_shift(halo, -2, -4, 10, 'periodic') +
        (20 / 11)
        * _stencil_shift(halo, -1, -4, 10, 'periodic') +
        (-1968329 / 635040)
        * _stencil_shift(halo, 0, -4, 10, 'periodic') +
        (20 / 11)
        * _stencil_shift(halo, 1, -4, 10, 'periodic') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -4, 10, 'periodic') +
        (40 / 429)
        * _stencil_shift(halo, 3, -4, 10, 'periodic') +
        (-15 / 572)
        * _stencil_shift(halo, 4, -4, 10, 'periodic') +
        (24 / 3575)
        * _stencil_shift(halo, 5, -4, 10, 'periodic') +
        (-5 / 3432)
        * _stencil_shift(halo, 6, -4, 10, 'periodic') +
        (30 / 119119)
        * _stencil_shift(halo, 7, -4, 10, 'periodic') +
        (-5 / 155584)
        * _stencil_shift(halo, 8, -4, 10, 'periodic') +
        (10 / 3741309)
        * _stencil_shift(halo, 9, -4, 10, 'periodic') +
        (-1 / 9237800)
        * _stencil_shift(halo, 10, -4, 10, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 20, -4, 'periodic'] = _fd_d2_a20_axis4_periodic


def _fd_d2_a20_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 20, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 10, 'zero', 2)
    result = (
        (-1 / 9237800)
        * _stencil_shift(halo, -10, -4, 10, 'zero') +
        (10 / 3741309)
        * _stencil_shift(halo, -9, -4, 10, 'zero') +
        (-5 / 155584)
        * _stencil_shift(halo, -8, -4, 10, 'zero') +
        (30 / 119119)
        * _stencil_shift(halo, -7, -4, 10, 'zero') +
        (-5 / 3432)
        * _stencil_shift(halo, -6, -4, 10, 'zero') +
        (24 / 3575)
        * _stencil_shift(halo, -5, -4, 10, 'zero') +
        (-15 / 572)
        * _stencil_shift(halo, -4, -4, 10, 'zero') +
        (40 / 429)
        * _stencil_shift(halo, -3, -4, 10, 'zero') +
        (-15 / 44)
        * _stencil_shift(halo, -2, -4, 10, 'zero') +
        (20 / 11)
        * _stencil_shift(halo, -1, -4, 10, 'zero') +
        (-1968329 / 635040)
        * _stencil_shift(halo, 0, -4, 10, 'zero') +
        (20 / 11)
        * _stencil_shift(halo, 1, -4, 10, 'zero') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -4, 10, 'zero') +
        (40 / 429)
        * _stencil_shift(halo, 3, -4, 10, 'zero') +
        (-15 / 572)
        * _stencil_shift(halo, 4, -4, 10, 'zero') +
        (24 / 3575)
        * _stencil_shift(halo, 5, -4, 10, 'zero') +
        (-5 / 3432)
        * _stencil_shift(halo, 6, -4, 10, 'zero') +
        (30 / 119119)
        * _stencil_shift(halo, 7, -4, 10, 'zero') +
        (-5 / 155584)
        * _stencil_shift(halo, 8, -4, 10, 'zero') +
        (10 / 3741309)
        * _stencil_shift(halo, 9, -4, 10, 'zero') +
        (-1 / 9237800)
        * _stencil_shift(halo, 10, -4, 10, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 20, -4, 'zero'] = _fd_d2_a20_axis4_zero


def _fd_d2_a20_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 20, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 10, 'reflect', 2)
    result = (
        (-1 / 9237800)
        * _stencil_shift(halo, -10, -4, 10, 'reflect') +
        (10 / 3741309)
        * _stencil_shift(halo, -9, -4, 10, 'reflect') +
        (-5 / 155584)
        * _stencil_shift(halo, -8, -4, 10, 'reflect') +
        (30 / 119119)
        * _stencil_shift(halo, -7, -4, 10, 'reflect') +
        (-5 / 3432)
        * _stencil_shift(halo, -6, -4, 10, 'reflect') +
        (24 / 3575)
        * _stencil_shift(halo, -5, -4, 10, 'reflect') +
        (-15 / 572)
        * _stencil_shift(halo, -4, -4, 10, 'reflect') +
        (40 / 429)
        * _stencil_shift(halo, -3, -4, 10, 'reflect') +
        (-15 / 44)
        * _stencil_shift(halo, -2, -4, 10, 'reflect') +
        (20 / 11)
        * _stencil_shift(halo, -1, -4, 10, 'reflect') +
        (-1968329 / 635040)
        * _stencil_shift(halo, 0, -4, 10, 'reflect') +
        (20 / 11)
        * _stencil_shift(halo, 1, -4, 10, 'reflect') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -4, 10, 'reflect') +
        (40 / 429)
        * _stencil_shift(halo, 3, -4, 10, 'reflect') +
        (-15 / 572)
        * _stencil_shift(halo, 4, -4, 10, 'reflect') +
        (24 / 3575)
        * _stencil_shift(halo, 5, -4, 10, 'reflect') +
        (-5 / 3432)
        * _stencil_shift(halo, 6, -4, 10, 'reflect') +
        (30 / 119119)
        * _stencil_shift(halo, 7, -4, 10, 'reflect') +
        (-5 / 155584)
        * _stencil_shift(halo, 8, -4, 10, 'reflect') +
        (10 / 3741309)
        * _stencil_shift(halo, 9, -4, 10, 'reflect') +
        (-1 / 9237800)
        * _stencil_shift(halo, 10, -4, 10, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 20, -4, 'reflect'] = _fd_d2_a20_axis4_reflect


def _fd_d2_a20_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 20, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 10, 'periodic', 2)
    result = (
        (-1 / 9237800)
        * _stencil_shift(halo, -10, -3, 10, 'periodic') +
        (10 / 3741309)
        * _stencil_shift(halo, -9, -3, 10, 'periodic') +
        (-5 / 155584)
        * _stencil_shift(halo, -8, -3, 10, 'periodic') +
        (30 / 119119)
        * _stencil_shift(halo, -7, -3, 10, 'periodic') +
        (-5 / 3432)
        * _stencil_shift(halo, -6, -3, 10, 'periodic') +
        (24 / 3575)
        * _stencil_shift(halo, -5, -3, 10, 'periodic') +
        (-15 / 572)
        * _stencil_shift(halo, -4, -3, 10, 'periodic') +
        (40 / 429)
        * _stencil_shift(halo, -3, -3, 10, 'periodic') +
        (-15 / 44)
        * _stencil_shift(halo, -2, -3, 10, 'periodic') +
        (20 / 11)
        * _stencil_shift(halo, -1, -3, 10, 'periodic') +
        (-1968329 / 635040)
        * _stencil_shift(halo, 0, -3, 10, 'periodic') +
        (20 / 11)
        * _stencil_shift(halo, 1, -3, 10, 'periodic') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -3, 10, 'periodic') +
        (40 / 429)
        * _stencil_shift(halo, 3, -3, 10, 'periodic') +
        (-15 / 572)
        * _stencil_shift(halo, 4, -3, 10, 'periodic') +
        (24 / 3575)
        * _stencil_shift(halo, 5, -3, 10, 'periodic') +
        (-5 / 3432)
        * _stencil_shift(halo, 6, -3, 10, 'periodic') +
        (30 / 119119)
        * _stencil_shift(halo, 7, -3, 10, 'periodic') +
        (-5 / 155584)
        * _stencil_shift(halo, 8, -3, 10, 'periodic') +
        (10 / 3741309)
        * _stencil_shift(halo, 9, -3, 10, 'periodic') +
        (-1 / 9237800)
        * _stencil_shift(halo, 10, -3, 10, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 20, -3, 'periodic'] = _fd_d2_a20_axis3_periodic


def _fd_d2_a20_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 20, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 10, 'zero', 2)
    result = (
        (-1 / 9237800)
        * _stencil_shift(halo, -10, -3, 10, 'zero') +
        (10 / 3741309)
        * _stencil_shift(halo, -9, -3, 10, 'zero') +
        (-5 / 155584)
        * _stencil_shift(halo, -8, -3, 10, 'zero') +
        (30 / 119119)
        * _stencil_shift(halo, -7, -3, 10, 'zero') +
        (-5 / 3432)
        * _stencil_shift(halo, -6, -3, 10, 'zero') +
        (24 / 3575)
        * _stencil_shift(halo, -5, -3, 10, 'zero') +
        (-15 / 572)
        * _stencil_shift(halo, -4, -3, 10, 'zero') +
        (40 / 429)
        * _stencil_shift(halo, -3, -3, 10, 'zero') +
        (-15 / 44)
        * _stencil_shift(halo, -2, -3, 10, 'zero') +
        (20 / 11)
        * _stencil_shift(halo, -1, -3, 10, 'zero') +
        (-1968329 / 635040)
        * _stencil_shift(halo, 0, -3, 10, 'zero') +
        (20 / 11)
        * _stencil_shift(halo, 1, -3, 10, 'zero') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -3, 10, 'zero') +
        (40 / 429)
        * _stencil_shift(halo, 3, -3, 10, 'zero') +
        (-15 / 572)
        * _stencil_shift(halo, 4, -3, 10, 'zero') +
        (24 / 3575)
        * _stencil_shift(halo, 5, -3, 10, 'zero') +
        (-5 / 3432)
        * _stencil_shift(halo, 6, -3, 10, 'zero') +
        (30 / 119119)
        * _stencil_shift(halo, 7, -3, 10, 'zero') +
        (-5 / 155584)
        * _stencil_shift(halo, 8, -3, 10, 'zero') +
        (10 / 3741309)
        * _stencil_shift(halo, 9, -3, 10, 'zero') +
        (-1 / 9237800)
        * _stencil_shift(halo, 10, -3, 10, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 20, -3, 'zero'] = _fd_d2_a20_axis3_zero


def _fd_d2_a20_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 20, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 10, 'reflect', 2)
    result = (
        (-1 / 9237800)
        * _stencil_shift(halo, -10, -3, 10, 'reflect') +
        (10 / 3741309)
        * _stencil_shift(halo, -9, -3, 10, 'reflect') +
        (-5 / 155584)
        * _stencil_shift(halo, -8, -3, 10, 'reflect') +
        (30 / 119119)
        * _stencil_shift(halo, -7, -3, 10, 'reflect') +
        (-5 / 3432)
        * _stencil_shift(halo, -6, -3, 10, 'reflect') +
        (24 / 3575)
        * _stencil_shift(halo, -5, -3, 10, 'reflect') +
        (-15 / 572)
        * _stencil_shift(halo, -4, -3, 10, 'reflect') +
        (40 / 429)
        * _stencil_shift(halo, -3, -3, 10, 'reflect') +
        (-15 / 44)
        * _stencil_shift(halo, -2, -3, 10, 'reflect') +
        (20 / 11)
        * _stencil_shift(halo, -1, -3, 10, 'reflect') +
        (-1968329 / 635040)
        * _stencil_shift(halo, 0, -3, 10, 'reflect') +
        (20 / 11)
        * _stencil_shift(halo, 1, -3, 10, 'reflect') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -3, 10, 'reflect') +
        (40 / 429)
        * _stencil_shift(halo, 3, -3, 10, 'reflect') +
        (-15 / 572)
        * _stencil_shift(halo, 4, -3, 10, 'reflect') +
        (24 / 3575)
        * _stencil_shift(halo, 5, -3, 10, 'reflect') +
        (-5 / 3432)
        * _stencil_shift(halo, 6, -3, 10, 'reflect') +
        (30 / 119119)
        * _stencil_shift(halo, 7, -3, 10, 'reflect') +
        (-5 / 155584)
        * _stencil_shift(halo, 8, -3, 10, 'reflect') +
        (10 / 3741309)
        * _stencil_shift(halo, 9, -3, 10, 'reflect') +
        (-1 / 9237800)
        * _stencil_shift(halo, 10, -3, 10, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 20, -3, 'reflect'] = _fd_d2_a20_axis3_reflect


def _fd_d2_a20_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 20, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 10, 'periodic', 2)
    result = (
        (-1 / 9237800)
        * _stencil_shift(halo, -10, -2, 10, 'periodic') +
        (10 / 3741309)
        * _stencil_shift(halo, -9, -2, 10, 'periodic') +
        (-5 / 155584)
        * _stencil_shift(halo, -8, -2, 10, 'periodic') +
        (30 / 119119)
        * _stencil_shift(halo, -7, -2, 10, 'periodic') +
        (-5 / 3432)
        * _stencil_shift(halo, -6, -2, 10, 'periodic') +
        (24 / 3575)
        * _stencil_shift(halo, -5, -2, 10, 'periodic') +
        (-15 / 572)
        * _stencil_shift(halo, -4, -2, 10, 'periodic') +
        (40 / 429)
        * _stencil_shift(halo, -3, -2, 10, 'periodic') +
        (-15 / 44)
        * _stencil_shift(halo, -2, -2, 10, 'periodic') +
        (20 / 11)
        * _stencil_shift(halo, -1, -2, 10, 'periodic') +
        (-1968329 / 635040)
        * _stencil_shift(halo, 0, -2, 10, 'periodic') +
        (20 / 11)
        * _stencil_shift(halo, 1, -2, 10, 'periodic') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -2, 10, 'periodic') +
        (40 / 429)
        * _stencil_shift(halo, 3, -2, 10, 'periodic') +
        (-15 / 572)
        * _stencil_shift(halo, 4, -2, 10, 'periodic') +
        (24 / 3575)
        * _stencil_shift(halo, 5, -2, 10, 'periodic') +
        (-5 / 3432)
        * _stencil_shift(halo, 6, -2, 10, 'periodic') +
        (30 / 119119)
        * _stencil_shift(halo, 7, -2, 10, 'periodic') +
        (-5 / 155584)
        * _stencil_shift(halo, 8, -2, 10, 'periodic') +
        (10 / 3741309)
        * _stencil_shift(halo, 9, -2, 10, 'periodic') +
        (-1 / 9237800)
        * _stencil_shift(halo, 10, -2, 10, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 20, -2, 'periodic'] = _fd_d2_a20_axis2_periodic


def _fd_d2_a20_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 20, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 10, 'zero', 2)
    result = (
        (-1 / 9237800)
        * _stencil_shift(halo, -10, -2, 10, 'zero') +
        (10 / 3741309)
        * _stencil_shift(halo, -9, -2, 10, 'zero') +
        (-5 / 155584)
        * _stencil_shift(halo, -8, -2, 10, 'zero') +
        (30 / 119119)
        * _stencil_shift(halo, -7, -2, 10, 'zero') +
        (-5 / 3432)
        * _stencil_shift(halo, -6, -2, 10, 'zero') +
        (24 / 3575)
        * _stencil_shift(halo, -5, -2, 10, 'zero') +
        (-15 / 572)
        * _stencil_shift(halo, -4, -2, 10, 'zero') +
        (40 / 429)
        * _stencil_shift(halo, -3, -2, 10, 'zero') +
        (-15 / 44)
        * _stencil_shift(halo, -2, -2, 10, 'zero') +
        (20 / 11)
        * _stencil_shift(halo, -1, -2, 10, 'zero') +
        (-1968329 / 635040)
        * _stencil_shift(halo, 0, -2, 10, 'zero') +
        (20 / 11)
        * _stencil_shift(halo, 1, -2, 10, 'zero') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -2, 10, 'zero') +
        (40 / 429)
        * _stencil_shift(halo, 3, -2, 10, 'zero') +
        (-15 / 572)
        * _stencil_shift(halo, 4, -2, 10, 'zero') +
        (24 / 3575)
        * _stencil_shift(halo, 5, -2, 10, 'zero') +
        (-5 / 3432)
        * _stencil_shift(halo, 6, -2, 10, 'zero') +
        (30 / 119119)
        * _stencil_shift(halo, 7, -2, 10, 'zero') +
        (-5 / 155584)
        * _stencil_shift(halo, 8, -2, 10, 'zero') +
        (10 / 3741309)
        * _stencil_shift(halo, 9, -2, 10, 'zero') +
        (-1 / 9237800)
        * _stencil_shift(halo, 10, -2, 10, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 20, -2, 'zero'] = _fd_d2_a20_axis2_zero


def _fd_d2_a20_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 20, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 10, 'reflect', 2)
    result = (
        (-1 / 9237800)
        * _stencil_shift(halo, -10, -2, 10, 'reflect') +
        (10 / 3741309)
        * _stencil_shift(halo, -9, -2, 10, 'reflect') +
        (-5 / 155584)
        * _stencil_shift(halo, -8, -2, 10, 'reflect') +
        (30 / 119119)
        * _stencil_shift(halo, -7, -2, 10, 'reflect') +
        (-5 / 3432)
        * _stencil_shift(halo, -6, -2, 10, 'reflect') +
        (24 / 3575)
        * _stencil_shift(halo, -5, -2, 10, 'reflect') +
        (-15 / 572)
        * _stencil_shift(halo, -4, -2, 10, 'reflect') +
        (40 / 429)
        * _stencil_shift(halo, -3, -2, 10, 'reflect') +
        (-15 / 44)
        * _stencil_shift(halo, -2, -2, 10, 'reflect') +
        (20 / 11)
        * _stencil_shift(halo, -1, -2, 10, 'reflect') +
        (-1968329 / 635040)
        * _stencil_shift(halo, 0, -2, 10, 'reflect') +
        (20 / 11)
        * _stencil_shift(halo, 1, -2, 10, 'reflect') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -2, 10, 'reflect') +
        (40 / 429)
        * _stencil_shift(halo, 3, -2, 10, 'reflect') +
        (-15 / 572)
        * _stencil_shift(halo, 4, -2, 10, 'reflect') +
        (24 / 3575)
        * _stencil_shift(halo, 5, -2, 10, 'reflect') +
        (-5 / 3432)
        * _stencil_shift(halo, 6, -2, 10, 'reflect') +
        (30 / 119119)
        * _stencil_shift(halo, 7, -2, 10, 'reflect') +
        (-5 / 155584)
        * _stencil_shift(halo, 8, -2, 10, 'reflect') +
        (10 / 3741309)
        * _stencil_shift(halo, 9, -2, 10, 'reflect') +
        (-1 / 9237800)
        * _stencil_shift(halo, 10, -2, 10, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 20, -2, 'reflect'] = _fd_d2_a20_axis2_reflect


def _fd_d2_a20_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 20, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 10, 'periodic', 2)
    result = (
        (-1 / 9237800)
        * _stencil_shift(halo, -10, -1, 10, 'periodic') +
        (10 / 3741309)
        * _stencil_shift(halo, -9, -1, 10, 'periodic') +
        (-5 / 155584)
        * _stencil_shift(halo, -8, -1, 10, 'periodic') +
        (30 / 119119)
        * _stencil_shift(halo, -7, -1, 10, 'periodic') +
        (-5 / 3432)
        * _stencil_shift(halo, -6, -1, 10, 'periodic') +
        (24 / 3575)
        * _stencil_shift(halo, -5, -1, 10, 'periodic') +
        (-15 / 572)
        * _stencil_shift(halo, -4, -1, 10, 'periodic') +
        (40 / 429)
        * _stencil_shift(halo, -3, -1, 10, 'periodic') +
        (-15 / 44)
        * _stencil_shift(halo, -2, -1, 10, 'periodic') +
        (20 / 11)
        * _stencil_shift(halo, -1, -1, 10, 'periodic') +
        (-1968329 / 635040)
        * _stencil_shift(halo, 0, -1, 10, 'periodic') +
        (20 / 11)
        * _stencil_shift(halo, 1, -1, 10, 'periodic') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -1, 10, 'periodic') +
        (40 / 429)
        * _stencil_shift(halo, 3, -1, 10, 'periodic') +
        (-15 / 572)
        * _stencil_shift(halo, 4, -1, 10, 'periodic') +
        (24 / 3575)
        * _stencil_shift(halo, 5, -1, 10, 'periodic') +
        (-5 / 3432)
        * _stencil_shift(halo, 6, -1, 10, 'periodic') +
        (30 / 119119)
        * _stencil_shift(halo, 7, -1, 10, 'periodic') +
        (-5 / 155584)
        * _stencil_shift(halo, 8, -1, 10, 'periodic') +
        (10 / 3741309)
        * _stencil_shift(halo, 9, -1, 10, 'periodic') +
        (-1 / 9237800)
        * _stencil_shift(halo, 10, -1, 10, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 20, -1, 'periodic'] = _fd_d2_a20_axis1_periodic


def _fd_d2_a20_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 20, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 10, 'zero', 2)
    result = (
        (-1 / 9237800)
        * _stencil_shift(halo, -10, -1, 10, 'zero') +
        (10 / 3741309)
        * _stencil_shift(halo, -9, -1, 10, 'zero') +
        (-5 / 155584)
        * _stencil_shift(halo, -8, -1, 10, 'zero') +
        (30 / 119119)
        * _stencil_shift(halo, -7, -1, 10, 'zero') +
        (-5 / 3432)
        * _stencil_shift(halo, -6, -1, 10, 'zero') +
        (24 / 3575)
        * _stencil_shift(halo, -5, -1, 10, 'zero') +
        (-15 / 572)
        * _stencil_shift(halo, -4, -1, 10, 'zero') +
        (40 / 429)
        * _stencil_shift(halo, -3, -1, 10, 'zero') +
        (-15 / 44)
        * _stencil_shift(halo, -2, -1, 10, 'zero') +
        (20 / 11)
        * _stencil_shift(halo, -1, -1, 10, 'zero') +
        (-1968329 / 635040)
        * _stencil_shift(halo, 0, -1, 10, 'zero') +
        (20 / 11)
        * _stencil_shift(halo, 1, -1, 10, 'zero') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -1, 10, 'zero') +
        (40 / 429)
        * _stencil_shift(halo, 3, -1, 10, 'zero') +
        (-15 / 572)
        * _stencil_shift(halo, 4, -1, 10, 'zero') +
        (24 / 3575)
        * _stencil_shift(halo, 5, -1, 10, 'zero') +
        (-5 / 3432)
        * _stencil_shift(halo, 6, -1, 10, 'zero') +
        (30 / 119119)
        * _stencil_shift(halo, 7, -1, 10, 'zero') +
        (-5 / 155584)
        * _stencil_shift(halo, 8, -1, 10, 'zero') +
        (10 / 3741309)
        * _stencil_shift(halo, 9, -1, 10, 'zero') +
        (-1 / 9237800)
        * _stencil_shift(halo, 10, -1, 10, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 20, -1, 'zero'] = _fd_d2_a20_axis1_zero


def _fd_d2_a20_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 2, accuracy 20, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**2, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 10, 'reflect', 2)
    result = (
        (-1 / 9237800)
        * _stencil_shift(halo, -10, -1, 10, 'reflect') +
        (10 / 3741309)
        * _stencil_shift(halo, -9, -1, 10, 'reflect') +
        (-5 / 155584)
        * _stencil_shift(halo, -8, -1, 10, 'reflect') +
        (30 / 119119)
        * _stencil_shift(halo, -7, -1, 10, 'reflect') +
        (-5 / 3432)
        * _stencil_shift(halo, -6, -1, 10, 'reflect') +
        (24 / 3575)
        * _stencil_shift(halo, -5, -1, 10, 'reflect') +
        (-15 / 572)
        * _stencil_shift(halo, -4, -1, 10, 'reflect') +
        (40 / 429)
        * _stencil_shift(halo, -3, -1, 10, 'reflect') +
        (-15 / 44)
        * _stencil_shift(halo, -2, -1, 10, 'reflect') +
        (20 / 11)
        * _stencil_shift(halo, -1, -1, 10, 'reflect') +
        (-1968329 / 635040)
        * _stencil_shift(halo, 0, -1, 10, 'reflect') +
        (20 / 11)
        * _stencil_shift(halo, 1, -1, 10, 'reflect') +
        (-15 / 44)
        * _stencil_shift(halo, 2, -1, 10, 'reflect') +
        (40 / 429)
        * _stencil_shift(halo, 3, -1, 10, 'reflect') +
        (-15 / 572)
        * _stencil_shift(halo, 4, -1, 10, 'reflect') +
        (24 / 3575)
        * _stencil_shift(halo, 5, -1, 10, 'reflect') +
        (-5 / 3432)
        * _stencil_shift(halo, 6, -1, 10, 'reflect') +
        (30 / 119119)
        * _stencil_shift(halo, 7, -1, 10, 'reflect') +
        (-5 / 155584)
        * _stencil_shift(halo, 8, -1, 10, 'reflect') +
        (10 / 3741309)
        * _stencil_shift(halo, 9, -1, 10, 'reflect') +
        (-1 / 9237800)
        * _stencil_shift(halo, 10, -1, 10, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[2, 20, -1, 'reflect'] = _fd_d2_a20_axis1_reflect


STENCIL_MOMENTS[3, 2] = (
    (-2, -1, 2),
    (-1, 1, 1),
    (0, 0, 1),
    (1, -1, 1),
    (2, 1, 2),
)

def _fd_d3_a2_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 2, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 2, 'periodic', 3)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -2, -4, 2, 'periodic') +
        (1 / 1)
        * _stencil_shift(halo, -1, -4, 2, 'periodic') +
        (-1 / 1)
        * _stencil_shift(halo, 1, -4, 2, 'periodic') +
        (1 / 2)
        * _stencil_shift(halo, 2, -4, 2, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 2, -4, 'periodic'] = _fd_d3_a2_axis4_periodic


def _fd_d3_a2_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 2, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 2, 'zero', 3)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -2, -4, 2, 'zero') +
        (1 / 1)
        * _stencil_shift(halo, -1, -4, 2, 'zero') +
        (-1 / 1)
        * _stencil_shift(halo, 1, -4, 2, 'zero') +
        (1 / 2)
        * _stencil_shift(halo, 2, -4, 2, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 2, -4, 'zero'] = _fd_d3_a2_axis4_zero


def _fd_d3_a2_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 2, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 2, 'reflect', 3)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -2, -4, 2, 'reflect') +
        (1 / 1)
        * _stencil_shift(halo, -1, -4, 2, 'reflect') +
        (-1 / 1)
        * _stencil_shift(halo, 1, -4, 2, 'reflect') +
        (1 / 2)
        * _stencil_shift(halo, 2, -4, 2, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 2, -4, 'reflect'] = _fd_d3_a2_axis4_reflect


def _fd_d3_a2_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 2, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 2, 'periodic', 3)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -2, -3, 2, 'periodic') +
        (1 / 1)
        * _stencil_shift(halo, -1, -3, 2, 'periodic') +
        (-1 / 1)
        * _stencil_shift(halo, 1, -3, 2, 'periodic') +
        (1 / 2)
        * _stencil_shift(halo, 2, -3, 2, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 2, -3, 'periodic'] = _fd_d3_a2_axis3_periodic


def _fd_d3_a2_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 2, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 2, 'zero', 3)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -2, -3, 2, 'zero') +
        (1 / 1)
        * _stencil_shift(halo, -1, -3, 2, 'zero') +
        (-1 / 1)
        * _stencil_shift(halo, 1, -3, 2, 'zero') +
        (1 / 2)
        * _stencil_shift(halo, 2, -3, 2, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 2, -3, 'zero'] = _fd_d3_a2_axis3_zero


def _fd_d3_a2_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 2, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 2, 'reflect', 3)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -2, -3, 2, 'reflect') +
        (1 / 1)
        * _stencil_shift(halo, -1, -3, 2, 'reflect') +
        (-1 / 1)
        * _stencil_shift(halo, 1, -3, 2, 'reflect') +
        (1 / 2)
        * _stencil_shift(halo, 2, -3, 2, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 2, -3, 'reflect'] = _fd_d3_a2_axis3_reflect


def _fd_d3_a2_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 2, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 2, 'periodic', 3)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -2, -2, 2, 'periodic') +
        (1 / 1)
        * _stencil_shift(halo, -1, -2, 2, 'periodic') +
        (-1 / 1)
        * _stencil_shift(halo, 1, -2, 2, 'periodic') +
        (1 / 2)
        * _stencil_shift(halo, 2, -2, 2, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 2, -2, 'periodic'] = _fd_d3_a2_axis2_periodic


def _fd_d3_a2_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 2, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 2, 'zero', 3)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -2, -2, 2, 'zero') +
        (1 / 1)
        * _stencil_shift(halo, -1, -2, 2, 'zero') +
        (-1 / 1)
        * _stencil_shift(halo, 1, -2, 2, 'zero') +
        (1 / 2)
        * _stencil_shift(halo, 2, -2, 2, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 2, -2, 'zero'] = _fd_d3_a2_axis2_zero


def _fd_d3_a2_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 2, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 2, 'reflect', 3)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -2, -2, 2, 'reflect') +
        (1 / 1)
        * _stencil_shift(halo, -1, -2, 2, 'reflect') +
        (-1 / 1)
        * _stencil_shift(halo, 1, -2, 2, 'reflect') +
        (1 / 2)
        * _stencil_shift(halo, 2, -2, 2, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 2, -2, 'reflect'] = _fd_d3_a2_axis2_reflect


def _fd_d3_a2_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 2, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 2, 'periodic', 3)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -2, -1, 2, 'periodic') +
        (1 / 1)
        * _stencil_shift(halo, -1, -1, 2, 'periodic') +
        (-1 / 1)
        * _stencil_shift(halo, 1, -1, 2, 'periodic') +
        (1 / 2)
        * _stencil_shift(halo, 2, -1, 2, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 2, -1, 'periodic'] = _fd_d3_a2_axis1_periodic


def _fd_d3_a2_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 2, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 2, 'zero', 3)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -2, -1, 2, 'zero') +
        (1 / 1)
        * _stencil_shift(halo, -1, -1, 2, 'zero') +
        (-1 / 1)
        * _stencil_shift(halo, 1, -1, 2, 'zero') +
        (1 / 2)
        * _stencil_shift(halo, 2, -1, 2, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 2, -1, 'zero'] = _fd_d3_a2_axis1_zero


def _fd_d3_a2_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 2, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 2, 'reflect', 3)
    result = (
        (-1 / 2)
        * _stencil_shift(halo, -2, -1, 2, 'reflect') +
        (1 / 1)
        * _stencil_shift(halo, -1, -1, 2, 'reflect') +
        (-1 / 1)
        * _stencil_shift(halo, 1, -1, 2, 'reflect') +
        (1 / 2)
        * _stencil_shift(halo, 2, -1, 2, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 2, -1, 'reflect'] = _fd_d3_a2_axis1_reflect


STENCIL_MOMENTS[3, 4] = (
    (-3, 1, 8),
    (-2, -1, 1),
    (-1, 13, 8),
    (0, 0, 1),
    (1, -13, 8),
    (2, 1, 1),
    (3, -1, 8),
)

def _fd_d3_a4_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 4, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 3, 'periodic', 3)
    result = (
        (1 / 8)
        * _stencil_shift(halo, -3, -4, 3, 'periodic') +
        (-1 / 1)
        * _stencil_shift(halo, -2, -4, 3, 'periodic') +
        (13 / 8)
        * _stencil_shift(halo, -1, -4, 3, 'periodic') +
        (-13 / 8)
        * _stencil_shift(halo, 1, -4, 3, 'periodic') +
        (1 / 1)
        * _stencil_shift(halo, 2, -4, 3, 'periodic') +
        (-1 / 8)
        * _stencil_shift(halo, 3, -4, 3, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 4, -4, 'periodic'] = _fd_d3_a4_axis4_periodic


def _fd_d3_a4_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 4, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 3, 'zero', 3)
    result = (
        (1 / 8)
        * _stencil_shift(halo, -3, -4, 3, 'zero') +
        (-1 / 1)
        * _stencil_shift(halo, -2, -4, 3, 'zero') +
        (13 / 8)
        * _stencil_shift(halo, -1, -4, 3, 'zero') +
        (-13 / 8)
        * _stencil_shift(halo, 1, -4, 3, 'zero') +
        (1 / 1)
        * _stencil_shift(halo, 2, -4, 3, 'zero') +
        (-1 / 8)
        * _stencil_shift(halo, 3, -4, 3, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 4, -4, 'zero'] = _fd_d3_a4_axis4_zero


def _fd_d3_a4_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 4, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 3, 'reflect', 3)
    result = (
        (1 / 8)
        * _stencil_shift(halo, -3, -4, 3, 'reflect') +
        (-1 / 1)
        * _stencil_shift(halo, -2, -4, 3, 'reflect') +
        (13 / 8)
        * _stencil_shift(halo, -1, -4, 3, 'reflect') +
        (-13 / 8)
        * _stencil_shift(halo, 1, -4, 3, 'reflect') +
        (1 / 1)
        * _stencil_shift(halo, 2, -4, 3, 'reflect') +
        (-1 / 8)
        * _stencil_shift(halo, 3, -4, 3, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 4, -4, 'reflect'] = _fd_d3_a4_axis4_reflect


def _fd_d3_a4_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 4, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 3, 'periodic', 3)
    result = (
        (1 / 8)
        * _stencil_shift(halo, -3, -3, 3, 'periodic') +
        (-1 / 1)
        * _stencil_shift(halo, -2, -3, 3, 'periodic') +
        (13 / 8)
        * _stencil_shift(halo, -1, -3, 3, 'periodic') +
        (-13 / 8)
        * _stencil_shift(halo, 1, -3, 3, 'periodic') +
        (1 / 1)
        * _stencil_shift(halo, 2, -3, 3, 'periodic') +
        (-1 / 8)
        * _stencil_shift(halo, 3, -3, 3, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 4, -3, 'periodic'] = _fd_d3_a4_axis3_periodic


def _fd_d3_a4_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 4, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 3, 'zero', 3)
    result = (
        (1 / 8)
        * _stencil_shift(halo, -3, -3, 3, 'zero') +
        (-1 / 1)
        * _stencil_shift(halo, -2, -3, 3, 'zero') +
        (13 / 8)
        * _stencil_shift(halo, -1, -3, 3, 'zero') +
        (-13 / 8)
        * _stencil_shift(halo, 1, -3, 3, 'zero') +
        (1 / 1)
        * _stencil_shift(halo, 2, -3, 3, 'zero') +
        (-1 / 8)
        * _stencil_shift(halo, 3, -3, 3, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 4, -3, 'zero'] = _fd_d3_a4_axis3_zero


def _fd_d3_a4_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 4, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 3, 'reflect', 3)
    result = (
        (1 / 8)
        * _stencil_shift(halo, -3, -3, 3, 'reflect') +
        (-1 / 1)
        * _stencil_shift(halo, -2, -3, 3, 'reflect') +
        (13 / 8)
        * _stencil_shift(halo, -1, -3, 3, 'reflect') +
        (-13 / 8)
        * _stencil_shift(halo, 1, -3, 3, 'reflect') +
        (1 / 1)
        * _stencil_shift(halo, 2, -3, 3, 'reflect') +
        (-1 / 8)
        * _stencil_shift(halo, 3, -3, 3, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 4, -3, 'reflect'] = _fd_d3_a4_axis3_reflect


def _fd_d3_a4_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 4, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 3, 'periodic', 3)
    result = (
        (1 / 8)
        * _stencil_shift(halo, -3, -2, 3, 'periodic') +
        (-1 / 1)
        * _stencil_shift(halo, -2, -2, 3, 'periodic') +
        (13 / 8)
        * _stencil_shift(halo, -1, -2, 3, 'periodic') +
        (-13 / 8)
        * _stencil_shift(halo, 1, -2, 3, 'periodic') +
        (1 / 1)
        * _stencil_shift(halo, 2, -2, 3, 'periodic') +
        (-1 / 8)
        * _stencil_shift(halo, 3, -2, 3, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 4, -2, 'periodic'] = _fd_d3_a4_axis2_periodic


def _fd_d3_a4_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 4, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 3, 'zero', 3)
    result = (
        (1 / 8)
        * _stencil_shift(halo, -3, -2, 3, 'zero') +
        (-1 / 1)
        * _stencil_shift(halo, -2, -2, 3, 'zero') +
        (13 / 8)
        * _stencil_shift(halo, -1, -2, 3, 'zero') +
        (-13 / 8)
        * _stencil_shift(halo, 1, -2, 3, 'zero') +
        (1 / 1)
        * _stencil_shift(halo, 2, -2, 3, 'zero') +
        (-1 / 8)
        * _stencil_shift(halo, 3, -2, 3, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 4, -2, 'zero'] = _fd_d3_a4_axis2_zero


def _fd_d3_a4_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 4, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 3, 'reflect', 3)
    result = (
        (1 / 8)
        * _stencil_shift(halo, -3, -2, 3, 'reflect') +
        (-1 / 1)
        * _stencil_shift(halo, -2, -2, 3, 'reflect') +
        (13 / 8)
        * _stencil_shift(halo, -1, -2, 3, 'reflect') +
        (-13 / 8)
        * _stencil_shift(halo, 1, -2, 3, 'reflect') +
        (1 / 1)
        * _stencil_shift(halo, 2, -2, 3, 'reflect') +
        (-1 / 8)
        * _stencil_shift(halo, 3, -2, 3, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 4, -2, 'reflect'] = _fd_d3_a4_axis2_reflect


def _fd_d3_a4_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 4, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 3, 'periodic', 3)
    result = (
        (1 / 8)
        * _stencil_shift(halo, -3, -1, 3, 'periodic') +
        (-1 / 1)
        * _stencil_shift(halo, -2, -1, 3, 'periodic') +
        (13 / 8)
        * _stencil_shift(halo, -1, -1, 3, 'periodic') +
        (-13 / 8)
        * _stencil_shift(halo, 1, -1, 3, 'periodic') +
        (1 / 1)
        * _stencil_shift(halo, 2, -1, 3, 'periodic') +
        (-1 / 8)
        * _stencil_shift(halo, 3, -1, 3, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 4, -1, 'periodic'] = _fd_d3_a4_axis1_periodic


def _fd_d3_a4_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 4, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 3, 'zero', 3)
    result = (
        (1 / 8)
        * _stencil_shift(halo, -3, -1, 3, 'zero') +
        (-1 / 1)
        * _stencil_shift(halo, -2, -1, 3, 'zero') +
        (13 / 8)
        * _stencil_shift(halo, -1, -1, 3, 'zero') +
        (-13 / 8)
        * _stencil_shift(halo, 1, -1, 3, 'zero') +
        (1 / 1)
        * _stencil_shift(halo, 2, -1, 3, 'zero') +
        (-1 / 8)
        * _stencil_shift(halo, 3, -1, 3, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 4, -1, 'zero'] = _fd_d3_a4_axis1_zero


def _fd_d3_a4_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 4, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 3, 'reflect', 3)
    result = (
        (1 / 8)
        * _stencil_shift(halo, -3, -1, 3, 'reflect') +
        (-1 / 1)
        * _stencil_shift(halo, -2, -1, 3, 'reflect') +
        (13 / 8)
        * _stencil_shift(halo, -1, -1, 3, 'reflect') +
        (-13 / 8)
        * _stencil_shift(halo, 1, -1, 3, 'reflect') +
        (1 / 1)
        * _stencil_shift(halo, 2, -1, 3, 'reflect') +
        (-1 / 8)
        * _stencil_shift(halo, 3, -1, 3, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 4, -1, 'reflect'] = _fd_d3_a4_axis1_reflect


STENCIL_MOMENTS[3, 6] = (
    (-4, -7, 240),
    (-3, 3, 10),
    (-2, -169, 120),
    (-1, 61, 30),
    (0, 0, 1),
    (1, -61, 30),
    (2, 169, 120),
    (3, -3, 10),
    (4, 7, 240),
)

def _fd_d3_a6_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 6, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 4, 'periodic', 3)
    result = (
        (-7 / 240)
        * _stencil_shift(halo, -4, -4, 4, 'periodic') +
        (3 / 10)
        * _stencil_shift(halo, -3, -4, 4, 'periodic') +
        (-169 / 120)
        * _stencil_shift(halo, -2, -4, 4, 'periodic') +
        (61 / 30)
        * _stencil_shift(halo, -1, -4, 4, 'periodic') +
        (-61 / 30)
        * _stencil_shift(halo, 1, -4, 4, 'periodic') +
        (169 / 120)
        * _stencil_shift(halo, 2, -4, 4, 'periodic') +
        (-3 / 10)
        * _stencil_shift(halo, 3, -4, 4, 'periodic') +
        (7 / 240)
        * _stencil_shift(halo, 4, -4, 4, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 6, -4, 'periodic'] = _fd_d3_a6_axis4_periodic


def _fd_d3_a6_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 6, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 4, 'zero', 3)
    result = (
        (-7 / 240)
        * _stencil_shift(halo, -4, -4, 4, 'zero') +
        (3 / 10)
        * _stencil_shift(halo, -3, -4, 4, 'zero') +
        (-169 / 120)
        * _stencil_shift(halo, -2, -4, 4, 'zero') +
        (61 / 30)
        * _stencil_shift(halo, -1, -4, 4, 'zero') +
        (-61 / 30)
        * _stencil_shift(halo, 1, -4, 4, 'zero') +
        (169 / 120)
        * _stencil_shift(halo, 2, -4, 4, 'zero') +
        (-3 / 10)
        * _stencil_shift(halo, 3, -4, 4, 'zero') +
        (7 / 240)
        * _stencil_shift(halo, 4, -4, 4, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 6, -4, 'zero'] = _fd_d3_a6_axis4_zero


def _fd_d3_a6_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 6, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 4, 'reflect', 3)
    result = (
        (-7 / 240)
        * _stencil_shift(halo, -4, -4, 4, 'reflect') +
        (3 / 10)
        * _stencil_shift(halo, -3, -4, 4, 'reflect') +
        (-169 / 120)
        * _stencil_shift(halo, -2, -4, 4, 'reflect') +
        (61 / 30)
        * _stencil_shift(halo, -1, -4, 4, 'reflect') +
        (-61 / 30)
        * _stencil_shift(halo, 1, -4, 4, 'reflect') +
        (169 / 120)
        * _stencil_shift(halo, 2, -4, 4, 'reflect') +
        (-3 / 10)
        * _stencil_shift(halo, 3, -4, 4, 'reflect') +
        (7 / 240)
        * _stencil_shift(halo, 4, -4, 4, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 6, -4, 'reflect'] = _fd_d3_a6_axis4_reflect


def _fd_d3_a6_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 6, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 4, 'periodic', 3)
    result = (
        (-7 / 240)
        * _stencil_shift(halo, -4, -3, 4, 'periodic') +
        (3 / 10)
        * _stencil_shift(halo, -3, -3, 4, 'periodic') +
        (-169 / 120)
        * _stencil_shift(halo, -2, -3, 4, 'periodic') +
        (61 / 30)
        * _stencil_shift(halo, -1, -3, 4, 'periodic') +
        (-61 / 30)
        * _stencil_shift(halo, 1, -3, 4, 'periodic') +
        (169 / 120)
        * _stencil_shift(halo, 2, -3, 4, 'periodic') +
        (-3 / 10)
        * _stencil_shift(halo, 3, -3, 4, 'periodic') +
        (7 / 240)
        * _stencil_shift(halo, 4, -3, 4, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 6, -3, 'periodic'] = _fd_d3_a6_axis3_periodic


def _fd_d3_a6_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 6, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 4, 'zero', 3)
    result = (
        (-7 / 240)
        * _stencil_shift(halo, -4, -3, 4, 'zero') +
        (3 / 10)
        * _stencil_shift(halo, -3, -3, 4, 'zero') +
        (-169 / 120)
        * _stencil_shift(halo, -2, -3, 4, 'zero') +
        (61 / 30)
        * _stencil_shift(halo, -1, -3, 4, 'zero') +
        (-61 / 30)
        * _stencil_shift(halo, 1, -3, 4, 'zero') +
        (169 / 120)
        * _stencil_shift(halo, 2, -3, 4, 'zero') +
        (-3 / 10)
        * _stencil_shift(halo, 3, -3, 4, 'zero') +
        (7 / 240)
        * _stencil_shift(halo, 4, -3, 4, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 6, -3, 'zero'] = _fd_d3_a6_axis3_zero


def _fd_d3_a6_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 6, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 4, 'reflect', 3)
    result = (
        (-7 / 240)
        * _stencil_shift(halo, -4, -3, 4, 'reflect') +
        (3 / 10)
        * _stencil_shift(halo, -3, -3, 4, 'reflect') +
        (-169 / 120)
        * _stencil_shift(halo, -2, -3, 4, 'reflect') +
        (61 / 30)
        * _stencil_shift(halo, -1, -3, 4, 'reflect') +
        (-61 / 30)
        * _stencil_shift(halo, 1, -3, 4, 'reflect') +
        (169 / 120)
        * _stencil_shift(halo, 2, -3, 4, 'reflect') +
        (-3 / 10)
        * _stencil_shift(halo, 3, -3, 4, 'reflect') +
        (7 / 240)
        * _stencil_shift(halo, 4, -3, 4, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 6, -3, 'reflect'] = _fd_d3_a6_axis3_reflect


def _fd_d3_a6_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 6, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 4, 'periodic', 3)
    result = (
        (-7 / 240)
        * _stencil_shift(halo, -4, -2, 4, 'periodic') +
        (3 / 10)
        * _stencil_shift(halo, -3, -2, 4, 'periodic') +
        (-169 / 120)
        * _stencil_shift(halo, -2, -2, 4, 'periodic') +
        (61 / 30)
        * _stencil_shift(halo, -1, -2, 4, 'periodic') +
        (-61 / 30)
        * _stencil_shift(halo, 1, -2, 4, 'periodic') +
        (169 / 120)
        * _stencil_shift(halo, 2, -2, 4, 'periodic') +
        (-3 / 10)
        * _stencil_shift(halo, 3, -2, 4, 'periodic') +
        (7 / 240)
        * _stencil_shift(halo, 4, -2, 4, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 6, -2, 'periodic'] = _fd_d3_a6_axis2_periodic


def _fd_d3_a6_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 6, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 4, 'zero', 3)
    result = (
        (-7 / 240)
        * _stencil_shift(halo, -4, -2, 4, 'zero') +
        (3 / 10)
        * _stencil_shift(halo, -3, -2, 4, 'zero') +
        (-169 / 120)
        * _stencil_shift(halo, -2, -2, 4, 'zero') +
        (61 / 30)
        * _stencil_shift(halo, -1, -2, 4, 'zero') +
        (-61 / 30)
        * _stencil_shift(halo, 1, -2, 4, 'zero') +
        (169 / 120)
        * _stencil_shift(halo, 2, -2, 4, 'zero') +
        (-3 / 10)
        * _stencil_shift(halo, 3, -2, 4, 'zero') +
        (7 / 240)
        * _stencil_shift(halo, 4, -2, 4, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 6, -2, 'zero'] = _fd_d3_a6_axis2_zero


def _fd_d3_a6_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 6, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 4, 'reflect', 3)
    result = (
        (-7 / 240)
        * _stencil_shift(halo, -4, -2, 4, 'reflect') +
        (3 / 10)
        * _stencil_shift(halo, -3, -2, 4, 'reflect') +
        (-169 / 120)
        * _stencil_shift(halo, -2, -2, 4, 'reflect') +
        (61 / 30)
        * _stencil_shift(halo, -1, -2, 4, 'reflect') +
        (-61 / 30)
        * _stencil_shift(halo, 1, -2, 4, 'reflect') +
        (169 / 120)
        * _stencil_shift(halo, 2, -2, 4, 'reflect') +
        (-3 / 10)
        * _stencil_shift(halo, 3, -2, 4, 'reflect') +
        (7 / 240)
        * _stencil_shift(halo, 4, -2, 4, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 6, -2, 'reflect'] = _fd_d3_a6_axis2_reflect


def _fd_d3_a6_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 6, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 4, 'periodic', 3)
    result = (
        (-7 / 240)
        * _stencil_shift(halo, -4, -1, 4, 'periodic') +
        (3 / 10)
        * _stencil_shift(halo, -3, -1, 4, 'periodic') +
        (-169 / 120)
        * _stencil_shift(halo, -2, -1, 4, 'periodic') +
        (61 / 30)
        * _stencil_shift(halo, -1, -1, 4, 'periodic') +
        (-61 / 30)
        * _stencil_shift(halo, 1, -1, 4, 'periodic') +
        (169 / 120)
        * _stencil_shift(halo, 2, -1, 4, 'periodic') +
        (-3 / 10)
        * _stencil_shift(halo, 3, -1, 4, 'periodic') +
        (7 / 240)
        * _stencil_shift(halo, 4, -1, 4, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 6, -1, 'periodic'] = _fd_d3_a6_axis1_periodic


def _fd_d3_a6_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 6, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 4, 'zero', 3)
    result = (
        (-7 / 240)
        * _stencil_shift(halo, -4, -1, 4, 'zero') +
        (3 / 10)
        * _stencil_shift(halo, -3, -1, 4, 'zero') +
        (-169 / 120)
        * _stencil_shift(halo, -2, -1, 4, 'zero') +
        (61 / 30)
        * _stencil_shift(halo, -1, -1, 4, 'zero') +
        (-61 / 30)
        * _stencil_shift(halo, 1, -1, 4, 'zero') +
        (169 / 120)
        * _stencil_shift(halo, 2, -1, 4, 'zero') +
        (-3 / 10)
        * _stencil_shift(halo, 3, -1, 4, 'zero') +
        (7 / 240)
        * _stencil_shift(halo, 4, -1, 4, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 6, -1, 'zero'] = _fd_d3_a6_axis1_zero


def _fd_d3_a6_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 6, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 4, 'reflect', 3)
    result = (
        (-7 / 240)
        * _stencil_shift(halo, -4, -1, 4, 'reflect') +
        (3 / 10)
        * _stencil_shift(halo, -3, -1, 4, 'reflect') +
        (-169 / 120)
        * _stencil_shift(halo, -2, -1, 4, 'reflect') +
        (61 / 30)
        * _stencil_shift(halo, -1, -1, 4, 'reflect') +
        (-61 / 30)
        * _stencil_shift(halo, 1, -1, 4, 'reflect') +
        (169 / 120)
        * _stencil_shift(halo, 2, -1, 4, 'reflect') +
        (-3 / 10)
        * _stencil_shift(halo, 3, -1, 4, 'reflect') +
        (7 / 240)
        * _stencil_shift(halo, 4, -1, 4, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 6, -1, 'reflect'] = _fd_d3_a6_axis1_reflect


STENCIL_MOMENTS[3, 8] = (
    (-5, 41, 6048),
    (-4, -1261, 15120),
    (-3, 541, 1120),
    (-2, -4369, 2520),
    (-1, 1669, 720),
    (0, 0, 1),
    (1, -1669, 720),
    (2, 4369, 2520),
    (3, -541, 1120),
    (4, 1261, 15120),
    (5, -41, 6048),
)

def _fd_d3_a8_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 8, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 5, 'periodic', 3)
    result = (
        (41 / 6048)
        * _stencil_shift(halo, -5, -4, 5, 'periodic') +
        (-1261 / 15120)
        * _stencil_shift(halo, -4, -4, 5, 'periodic') +
        (541 / 1120)
        * _stencil_shift(halo, -3, -4, 5, 'periodic') +
        (-4369 / 2520)
        * _stencil_shift(halo, -2, -4, 5, 'periodic') +
        (1669 / 720)
        * _stencil_shift(halo, -1, -4, 5, 'periodic') +
        (-1669 / 720)
        * _stencil_shift(halo, 1, -4, 5, 'periodic') +
        (4369 / 2520)
        * _stencil_shift(halo, 2, -4, 5, 'periodic') +
        (-541 / 1120)
        * _stencil_shift(halo, 3, -4, 5, 'periodic') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -4, 5, 'periodic') +
        (-41 / 6048)
        * _stencil_shift(halo, 5, -4, 5, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 8, -4, 'periodic'] = _fd_d3_a8_axis4_periodic


def _fd_d3_a8_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 8, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 5, 'zero', 3)
    result = (
        (41 / 6048)
        * _stencil_shift(halo, -5, -4, 5, 'zero') +
        (-1261 / 15120)
        * _stencil_shift(halo, -4, -4, 5, 'zero') +
        (541 / 1120)
        * _stencil_shift(halo, -3, -4, 5, 'zero') +
        (-4369 / 2520)
        * _stencil_shift(halo, -2, -4, 5, 'zero') +
        (1669 / 720)
        * _stencil_shift(halo, -1, -4, 5, 'zero') +
        (-1669 / 720)
        * _stencil_shift(halo, 1, -4, 5, 'zero') +
        (4369 / 2520)
        * _stencil_shift(halo, 2, -4, 5, 'zero') +
        (-541 / 1120)
        * _stencil_shift(halo, 3, -4, 5, 'zero') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -4, 5, 'zero') +
        (-41 / 6048)
        * _stencil_shift(halo, 5, -4, 5, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 8, -4, 'zero'] = _fd_d3_a8_axis4_zero


def _fd_d3_a8_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 8, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 5, 'reflect', 3)
    result = (
        (41 / 6048)
        * _stencil_shift(halo, -5, -4, 5, 'reflect') +
        (-1261 / 15120)
        * _stencil_shift(halo, -4, -4, 5, 'reflect') +
        (541 / 1120)
        * _stencil_shift(halo, -3, -4, 5, 'reflect') +
        (-4369 / 2520)
        * _stencil_shift(halo, -2, -4, 5, 'reflect') +
        (1669 / 720)
        * _stencil_shift(halo, -1, -4, 5, 'reflect') +
        (-1669 / 720)
        * _stencil_shift(halo, 1, -4, 5, 'reflect') +
        (4369 / 2520)
        * _stencil_shift(halo, 2, -4, 5, 'reflect') +
        (-541 / 1120)
        * _stencil_shift(halo, 3, -4, 5, 'reflect') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -4, 5, 'reflect') +
        (-41 / 6048)
        * _stencil_shift(halo, 5, -4, 5, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 8, -4, 'reflect'] = _fd_d3_a8_axis4_reflect


def _fd_d3_a8_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 8, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 5, 'periodic', 3)
    result = (
        (41 / 6048)
        * _stencil_shift(halo, -5, -3, 5, 'periodic') +
        (-1261 / 15120)
        * _stencil_shift(halo, -4, -3, 5, 'periodic') +
        (541 / 1120)
        * _stencil_shift(halo, -3, -3, 5, 'periodic') +
        (-4369 / 2520)
        * _stencil_shift(halo, -2, -3, 5, 'periodic') +
        (1669 / 720)
        * _stencil_shift(halo, -1, -3, 5, 'periodic') +
        (-1669 / 720)
        * _stencil_shift(halo, 1, -3, 5, 'periodic') +
        (4369 / 2520)
        * _stencil_shift(halo, 2, -3, 5, 'periodic') +
        (-541 / 1120)
        * _stencil_shift(halo, 3, -3, 5, 'periodic') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -3, 5, 'periodic') +
        (-41 / 6048)
        * _stencil_shift(halo, 5, -3, 5, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 8, -3, 'periodic'] = _fd_d3_a8_axis3_periodic


def _fd_d3_a8_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 8, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 5, 'zero', 3)
    result = (
        (41 / 6048)
        * _stencil_shift(halo, -5, -3, 5, 'zero') +
        (-1261 / 15120)
        * _stencil_shift(halo, -4, -3, 5, 'zero') +
        (541 / 1120)
        * _stencil_shift(halo, -3, -3, 5, 'zero') +
        (-4369 / 2520)
        * _stencil_shift(halo, -2, -3, 5, 'zero') +
        (1669 / 720)
        * _stencil_shift(halo, -1, -3, 5, 'zero') +
        (-1669 / 720)
        * _stencil_shift(halo, 1, -3, 5, 'zero') +
        (4369 / 2520)
        * _stencil_shift(halo, 2, -3, 5, 'zero') +
        (-541 / 1120)
        * _stencil_shift(halo, 3, -3, 5, 'zero') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -3, 5, 'zero') +
        (-41 / 6048)
        * _stencil_shift(halo, 5, -3, 5, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 8, -3, 'zero'] = _fd_d3_a8_axis3_zero


def _fd_d3_a8_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 8, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 5, 'reflect', 3)
    result = (
        (41 / 6048)
        * _stencil_shift(halo, -5, -3, 5, 'reflect') +
        (-1261 / 15120)
        * _stencil_shift(halo, -4, -3, 5, 'reflect') +
        (541 / 1120)
        * _stencil_shift(halo, -3, -3, 5, 'reflect') +
        (-4369 / 2520)
        * _stencil_shift(halo, -2, -3, 5, 'reflect') +
        (1669 / 720)
        * _stencil_shift(halo, -1, -3, 5, 'reflect') +
        (-1669 / 720)
        * _stencil_shift(halo, 1, -3, 5, 'reflect') +
        (4369 / 2520)
        * _stencil_shift(halo, 2, -3, 5, 'reflect') +
        (-541 / 1120)
        * _stencil_shift(halo, 3, -3, 5, 'reflect') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -3, 5, 'reflect') +
        (-41 / 6048)
        * _stencil_shift(halo, 5, -3, 5, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 8, -3, 'reflect'] = _fd_d3_a8_axis3_reflect


def _fd_d3_a8_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 8, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 5, 'periodic', 3)
    result = (
        (41 / 6048)
        * _stencil_shift(halo, -5, -2, 5, 'periodic') +
        (-1261 / 15120)
        * _stencil_shift(halo, -4, -2, 5, 'periodic') +
        (541 / 1120)
        * _stencil_shift(halo, -3, -2, 5, 'periodic') +
        (-4369 / 2520)
        * _stencil_shift(halo, -2, -2, 5, 'periodic') +
        (1669 / 720)
        * _stencil_shift(halo, -1, -2, 5, 'periodic') +
        (-1669 / 720)
        * _stencil_shift(halo, 1, -2, 5, 'periodic') +
        (4369 / 2520)
        * _stencil_shift(halo, 2, -2, 5, 'periodic') +
        (-541 / 1120)
        * _stencil_shift(halo, 3, -2, 5, 'periodic') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -2, 5, 'periodic') +
        (-41 / 6048)
        * _stencil_shift(halo, 5, -2, 5, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 8, -2, 'periodic'] = _fd_d3_a8_axis2_periodic


def _fd_d3_a8_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 8, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 5, 'zero', 3)
    result = (
        (41 / 6048)
        * _stencil_shift(halo, -5, -2, 5, 'zero') +
        (-1261 / 15120)
        * _stencil_shift(halo, -4, -2, 5, 'zero') +
        (541 / 1120)
        * _stencil_shift(halo, -3, -2, 5, 'zero') +
        (-4369 / 2520)
        * _stencil_shift(halo, -2, -2, 5, 'zero') +
        (1669 / 720)
        * _stencil_shift(halo, -1, -2, 5, 'zero') +
        (-1669 / 720)
        * _stencil_shift(halo, 1, -2, 5, 'zero') +
        (4369 / 2520)
        * _stencil_shift(halo, 2, -2, 5, 'zero') +
        (-541 / 1120)
        * _stencil_shift(halo, 3, -2, 5, 'zero') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -2, 5, 'zero') +
        (-41 / 6048)
        * _stencil_shift(halo, 5, -2, 5, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 8, -2, 'zero'] = _fd_d3_a8_axis2_zero


def _fd_d3_a8_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 8, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 5, 'reflect', 3)
    result = (
        (41 / 6048)
        * _stencil_shift(halo, -5, -2, 5, 'reflect') +
        (-1261 / 15120)
        * _stencil_shift(halo, -4, -2, 5, 'reflect') +
        (541 / 1120)
        * _stencil_shift(halo, -3, -2, 5, 'reflect') +
        (-4369 / 2520)
        * _stencil_shift(halo, -2, -2, 5, 'reflect') +
        (1669 / 720)
        * _stencil_shift(halo, -1, -2, 5, 'reflect') +
        (-1669 / 720)
        * _stencil_shift(halo, 1, -2, 5, 'reflect') +
        (4369 / 2520)
        * _stencil_shift(halo, 2, -2, 5, 'reflect') +
        (-541 / 1120)
        * _stencil_shift(halo, 3, -2, 5, 'reflect') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -2, 5, 'reflect') +
        (-41 / 6048)
        * _stencil_shift(halo, 5, -2, 5, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 8, -2, 'reflect'] = _fd_d3_a8_axis2_reflect


def _fd_d3_a8_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 8, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 5, 'periodic', 3)
    result = (
        (41 / 6048)
        * _stencil_shift(halo, -5, -1, 5, 'periodic') +
        (-1261 / 15120)
        * _stencil_shift(halo, -4, -1, 5, 'periodic') +
        (541 / 1120)
        * _stencil_shift(halo, -3, -1, 5, 'periodic') +
        (-4369 / 2520)
        * _stencil_shift(halo, -2, -1, 5, 'periodic') +
        (1669 / 720)
        * _stencil_shift(halo, -1, -1, 5, 'periodic') +
        (-1669 / 720)
        * _stencil_shift(halo, 1, -1, 5, 'periodic') +
        (4369 / 2520)
        * _stencil_shift(halo, 2, -1, 5, 'periodic') +
        (-541 / 1120)
        * _stencil_shift(halo, 3, -1, 5, 'periodic') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -1, 5, 'periodic') +
        (-41 / 6048)
        * _stencil_shift(halo, 5, -1, 5, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 8, -1, 'periodic'] = _fd_d3_a8_axis1_periodic


def _fd_d3_a8_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 8, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 5, 'zero', 3)
    result = (
        (41 / 6048)
        * _stencil_shift(halo, -5, -1, 5, 'zero') +
        (-1261 / 15120)
        * _stencil_shift(halo, -4, -1, 5, 'zero') +
        (541 / 1120)
        * _stencil_shift(halo, -3, -1, 5, 'zero') +
        (-4369 / 2520)
        * _stencil_shift(halo, -2, -1, 5, 'zero') +
        (1669 / 720)
        * _stencil_shift(halo, -1, -1, 5, 'zero') +
        (-1669 / 720)
        * _stencil_shift(halo, 1, -1, 5, 'zero') +
        (4369 / 2520)
        * _stencil_shift(halo, 2, -1, 5, 'zero') +
        (-541 / 1120)
        * _stencil_shift(halo, 3, -1, 5, 'zero') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -1, 5, 'zero') +
        (-41 / 6048)
        * _stencil_shift(halo, 5, -1, 5, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 8, -1, 'zero'] = _fd_d3_a8_axis1_zero


def _fd_d3_a8_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 8, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 5, 'reflect', 3)
    result = (
        (41 / 6048)
        * _stencil_shift(halo, -5, -1, 5, 'reflect') +
        (-1261 / 15120)
        * _stencil_shift(halo, -4, -1, 5, 'reflect') +
        (541 / 1120)
        * _stencil_shift(halo, -3, -1, 5, 'reflect') +
        (-4369 / 2520)
        * _stencil_shift(halo, -2, -1, 5, 'reflect') +
        (1669 / 720)
        * _stencil_shift(halo, -1, -1, 5, 'reflect') +
        (-1669 / 720)
        * _stencil_shift(halo, 1, -1, 5, 'reflect') +
        (4369 / 2520)
        * _stencil_shift(halo, 2, -1, 5, 'reflect') +
        (-541 / 1120)
        * _stencil_shift(halo, 3, -1, 5, 'reflect') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -1, 5, 'reflect') +
        (-41 / 6048)
        * _stencil_shift(halo, 5, -1, 5, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 8, -1, 'reflect'] = _fd_d3_a8_axis1_reflect


STENCIL_MOMENTS[3, 10] = (
    (-6, -479, 302400),
    (-5, 19, 840),
    (-4, -643, 4200),
    (-3, 4969, 7560),
    (-2, -4469, 2240),
    (-1, 1769, 700),
    (0, 0, 1),
    (1, -1769, 700),
    (2, 4469, 2240),
    (3, -4969, 7560),
    (4, 643, 4200),
    (5, -19, 840),
    (6, 479, 302400),
)

def _fd_d3_a10_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 10, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 6, 'periodic', 3)
    result = (
        (-479 / 302400)
        * _stencil_shift(halo, -6, -4, 6, 'periodic') +
        (19 / 840)
        * _stencil_shift(halo, -5, -4, 6, 'periodic') +
        (-643 / 4200)
        * _stencil_shift(halo, -4, -4, 6, 'periodic') +
        (4969 / 7560)
        * _stencil_shift(halo, -3, -4, 6, 'periodic') +
        (-4469 / 2240)
        * _stencil_shift(halo, -2, -4, 6, 'periodic') +
        (1769 / 700)
        * _stencil_shift(halo, -1, -4, 6, 'periodic') +
        (-1769 / 700)
        * _stencil_shift(halo, 1, -4, 6, 'periodic') +
        (4469 / 2240)
        * _stencil_shift(halo, 2, -4, 6, 'periodic') +
        (-4969 / 7560)
        * _stencil_shift(halo, 3, -4, 6, 'periodic') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -4, 6, 'periodic') +
        (-19 / 840)
        * _stencil_shift(halo, 5, -4, 6, 'periodic') +
        (479 / 302400)
        * _stencil_shift(halo, 6, -4, 6, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 10, -4, 'periodic'] = _fd_d3_a10_axis4_periodic


def _fd_d3_a10_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 10, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 6, 'zero', 3)
    result = (
        (-479 / 302400)
        * _stencil_shift(halo, -6, -4, 6, 'zero') +
        (19 / 840)
        * _stencil_shift(halo, -5, -4, 6, 'zero') +
        (-643 / 4200)
        * _stencil_shift(halo, -4, -4, 6, 'zero') +
        (4969 / 7560)
        * _stencil_shift(halo, -3, -4, 6, 'zero') +
        (-4469 / 2240)
        * _stencil_shift(halo, -2, -4, 6, 'zero') +
        (1769 / 700)
        * _stencil_shift(halo, -1, -4, 6, 'zero') +
        (-1769 / 700)
        * _stencil_shift(halo, 1, -4, 6, 'zero') +
        (4469 / 2240)
        * _stencil_shift(halo, 2, -4, 6, 'zero') +
        (-4969 / 7560)
        * _stencil_shift(halo, 3, -4, 6, 'zero') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -4, 6, 'zero') +
        (-19 / 840)
        * _stencil_shift(halo, 5, -4, 6, 'zero') +
        (479 / 302400)
        * _stencil_shift(halo, 6, -4, 6, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 10, -4, 'zero'] = _fd_d3_a10_axis4_zero


def _fd_d3_a10_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 10, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 6, 'reflect', 3)
    result = (
        (-479 / 302400)
        * _stencil_shift(halo, -6, -4, 6, 'reflect') +
        (19 / 840)
        * _stencil_shift(halo, -5, -4, 6, 'reflect') +
        (-643 / 4200)
        * _stencil_shift(halo, -4, -4, 6, 'reflect') +
        (4969 / 7560)
        * _stencil_shift(halo, -3, -4, 6, 'reflect') +
        (-4469 / 2240)
        * _stencil_shift(halo, -2, -4, 6, 'reflect') +
        (1769 / 700)
        * _stencil_shift(halo, -1, -4, 6, 'reflect') +
        (-1769 / 700)
        * _stencil_shift(halo, 1, -4, 6, 'reflect') +
        (4469 / 2240)
        * _stencil_shift(halo, 2, -4, 6, 'reflect') +
        (-4969 / 7560)
        * _stencil_shift(halo, 3, -4, 6, 'reflect') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -4, 6, 'reflect') +
        (-19 / 840)
        * _stencil_shift(halo, 5, -4, 6, 'reflect') +
        (479 / 302400)
        * _stencil_shift(halo, 6, -4, 6, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 10, -4, 'reflect'] = _fd_d3_a10_axis4_reflect


def _fd_d3_a10_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 10, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 6, 'periodic', 3)
    result = (
        (-479 / 302400)
        * _stencil_shift(halo, -6, -3, 6, 'periodic') +
        (19 / 840)
        * _stencil_shift(halo, -5, -3, 6, 'periodic') +
        (-643 / 4200)
        * _stencil_shift(halo, -4, -3, 6, 'periodic') +
        (4969 / 7560)
        * _stencil_shift(halo, -3, -3, 6, 'periodic') +
        (-4469 / 2240)
        * _stencil_shift(halo, -2, -3, 6, 'periodic') +
        (1769 / 700)
        * _stencil_shift(halo, -1, -3, 6, 'periodic') +
        (-1769 / 700)
        * _stencil_shift(halo, 1, -3, 6, 'periodic') +
        (4469 / 2240)
        * _stencil_shift(halo, 2, -3, 6, 'periodic') +
        (-4969 / 7560)
        * _stencil_shift(halo, 3, -3, 6, 'periodic') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -3, 6, 'periodic') +
        (-19 / 840)
        * _stencil_shift(halo, 5, -3, 6, 'periodic') +
        (479 / 302400)
        * _stencil_shift(halo, 6, -3, 6, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 10, -3, 'periodic'] = _fd_d3_a10_axis3_periodic


def _fd_d3_a10_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 10, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 6, 'zero', 3)
    result = (
        (-479 / 302400)
        * _stencil_shift(halo, -6, -3, 6, 'zero') +
        (19 / 840)
        * _stencil_shift(halo, -5, -3, 6, 'zero') +
        (-643 / 4200)
        * _stencil_shift(halo, -4, -3, 6, 'zero') +
        (4969 / 7560)
        * _stencil_shift(halo, -3, -3, 6, 'zero') +
        (-4469 / 2240)
        * _stencil_shift(halo, -2, -3, 6, 'zero') +
        (1769 / 700)
        * _stencil_shift(halo, -1, -3, 6, 'zero') +
        (-1769 / 700)
        * _stencil_shift(halo, 1, -3, 6, 'zero') +
        (4469 / 2240)
        * _stencil_shift(halo, 2, -3, 6, 'zero') +
        (-4969 / 7560)
        * _stencil_shift(halo, 3, -3, 6, 'zero') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -3, 6, 'zero') +
        (-19 / 840)
        * _stencil_shift(halo, 5, -3, 6, 'zero') +
        (479 / 302400)
        * _stencil_shift(halo, 6, -3, 6, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 10, -3, 'zero'] = _fd_d3_a10_axis3_zero


def _fd_d3_a10_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 10, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 6, 'reflect', 3)
    result = (
        (-479 / 302400)
        * _stencil_shift(halo, -6, -3, 6, 'reflect') +
        (19 / 840)
        * _stencil_shift(halo, -5, -3, 6, 'reflect') +
        (-643 / 4200)
        * _stencil_shift(halo, -4, -3, 6, 'reflect') +
        (4969 / 7560)
        * _stencil_shift(halo, -3, -3, 6, 'reflect') +
        (-4469 / 2240)
        * _stencil_shift(halo, -2, -3, 6, 'reflect') +
        (1769 / 700)
        * _stencil_shift(halo, -1, -3, 6, 'reflect') +
        (-1769 / 700)
        * _stencil_shift(halo, 1, -3, 6, 'reflect') +
        (4469 / 2240)
        * _stencil_shift(halo, 2, -3, 6, 'reflect') +
        (-4969 / 7560)
        * _stencil_shift(halo, 3, -3, 6, 'reflect') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -3, 6, 'reflect') +
        (-19 / 840)
        * _stencil_shift(halo, 5, -3, 6, 'reflect') +
        (479 / 302400)
        * _stencil_shift(halo, 6, -3, 6, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 10, -3, 'reflect'] = _fd_d3_a10_axis3_reflect


def _fd_d3_a10_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 10, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 6, 'periodic', 3)
    result = (
        (-479 / 302400)
        * _stencil_shift(halo, -6, -2, 6, 'periodic') +
        (19 / 840)
        * _stencil_shift(halo, -5, -2, 6, 'periodic') +
        (-643 / 4200)
        * _stencil_shift(halo, -4, -2, 6, 'periodic') +
        (4969 / 7560)
        * _stencil_shift(halo, -3, -2, 6, 'periodic') +
        (-4469 / 2240)
        * _stencil_shift(halo, -2, -2, 6, 'periodic') +
        (1769 / 700)
        * _stencil_shift(halo, -1, -2, 6, 'periodic') +
        (-1769 / 700)
        * _stencil_shift(halo, 1, -2, 6, 'periodic') +
        (4469 / 2240)
        * _stencil_shift(halo, 2, -2, 6, 'periodic') +
        (-4969 / 7560)
        * _stencil_shift(halo, 3, -2, 6, 'periodic') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -2, 6, 'periodic') +
        (-19 / 840)
        * _stencil_shift(halo, 5, -2, 6, 'periodic') +
        (479 / 302400)
        * _stencil_shift(halo, 6, -2, 6, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 10, -2, 'periodic'] = _fd_d3_a10_axis2_periodic


def _fd_d3_a10_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 10, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 6, 'zero', 3)
    result = (
        (-479 / 302400)
        * _stencil_shift(halo, -6, -2, 6, 'zero') +
        (19 / 840)
        * _stencil_shift(halo, -5, -2, 6, 'zero') +
        (-643 / 4200)
        * _stencil_shift(halo, -4, -2, 6, 'zero') +
        (4969 / 7560)
        * _stencil_shift(halo, -3, -2, 6, 'zero') +
        (-4469 / 2240)
        * _stencil_shift(halo, -2, -2, 6, 'zero') +
        (1769 / 700)
        * _stencil_shift(halo, -1, -2, 6, 'zero') +
        (-1769 / 700)
        * _stencil_shift(halo, 1, -2, 6, 'zero') +
        (4469 / 2240)
        * _stencil_shift(halo, 2, -2, 6, 'zero') +
        (-4969 / 7560)
        * _stencil_shift(halo, 3, -2, 6, 'zero') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -2, 6, 'zero') +
        (-19 / 840)
        * _stencil_shift(halo, 5, -2, 6, 'zero') +
        (479 / 302400)
        * _stencil_shift(halo, 6, -2, 6, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 10, -2, 'zero'] = _fd_d3_a10_axis2_zero


def _fd_d3_a10_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 10, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 6, 'reflect', 3)
    result = (
        (-479 / 302400)
        * _stencil_shift(halo, -6, -2, 6, 'reflect') +
        (19 / 840)
        * _stencil_shift(halo, -5, -2, 6, 'reflect') +
        (-643 / 4200)
        * _stencil_shift(halo, -4, -2, 6, 'reflect') +
        (4969 / 7560)
        * _stencil_shift(halo, -3, -2, 6, 'reflect') +
        (-4469 / 2240)
        * _stencil_shift(halo, -2, -2, 6, 'reflect') +
        (1769 / 700)
        * _stencil_shift(halo, -1, -2, 6, 'reflect') +
        (-1769 / 700)
        * _stencil_shift(halo, 1, -2, 6, 'reflect') +
        (4469 / 2240)
        * _stencil_shift(halo, 2, -2, 6, 'reflect') +
        (-4969 / 7560)
        * _stencil_shift(halo, 3, -2, 6, 'reflect') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -2, 6, 'reflect') +
        (-19 / 840)
        * _stencil_shift(halo, 5, -2, 6, 'reflect') +
        (479 / 302400)
        * _stencil_shift(halo, 6, -2, 6, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 10, -2, 'reflect'] = _fd_d3_a10_axis2_reflect


def _fd_d3_a10_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 10, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 6, 'periodic', 3)
    result = (
        (-479 / 302400)
        * _stencil_shift(halo, -6, -1, 6, 'periodic') +
        (19 / 840)
        * _stencil_shift(halo, -5, -1, 6, 'periodic') +
        (-643 / 4200)
        * _stencil_shift(halo, -4, -1, 6, 'periodic') +
        (4969 / 7560)
        * _stencil_shift(halo, -3, -1, 6, 'periodic') +
        (-4469 / 2240)
        * _stencil_shift(halo, -2, -1, 6, 'periodic') +
        (1769 / 700)
        * _stencil_shift(halo, -1, -1, 6, 'periodic') +
        (-1769 / 700)
        * _stencil_shift(halo, 1, -1, 6, 'periodic') +
        (4469 / 2240)
        * _stencil_shift(halo, 2, -1, 6, 'periodic') +
        (-4969 / 7560)
        * _stencil_shift(halo, 3, -1, 6, 'periodic') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -1, 6, 'periodic') +
        (-19 / 840)
        * _stencil_shift(halo, 5, -1, 6, 'periodic') +
        (479 / 302400)
        * _stencil_shift(halo, 6, -1, 6, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 10, -1, 'periodic'] = _fd_d3_a10_axis1_periodic


def _fd_d3_a10_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 10, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 6, 'zero', 3)
    result = (
        (-479 / 302400)
        * _stencil_shift(halo, -6, -1, 6, 'zero') +
        (19 / 840)
        * _stencil_shift(halo, -5, -1, 6, 'zero') +
        (-643 / 4200)
        * _stencil_shift(halo, -4, -1, 6, 'zero') +
        (4969 / 7560)
        * _stencil_shift(halo, -3, -1, 6, 'zero') +
        (-4469 / 2240)
        * _stencil_shift(halo, -2, -1, 6, 'zero') +
        (1769 / 700)
        * _stencil_shift(halo, -1, -1, 6, 'zero') +
        (-1769 / 700)
        * _stencil_shift(halo, 1, -1, 6, 'zero') +
        (4469 / 2240)
        * _stencil_shift(halo, 2, -1, 6, 'zero') +
        (-4969 / 7560)
        * _stencil_shift(halo, 3, -1, 6, 'zero') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -1, 6, 'zero') +
        (-19 / 840)
        * _stencil_shift(halo, 5, -1, 6, 'zero') +
        (479 / 302400)
        * _stencil_shift(halo, 6, -1, 6, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 10, -1, 'zero'] = _fd_d3_a10_axis1_zero


def _fd_d3_a10_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 10, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 6, 'reflect', 3)
    result = (
        (-479 / 302400)
        * _stencil_shift(halo, -6, -1, 6, 'reflect') +
        (19 / 840)
        * _stencil_shift(halo, -5, -1, 6, 'reflect') +
        (-643 / 4200)
        * _stencil_shift(halo, -4, -1, 6, 'reflect') +
        (4969 / 7560)
        * _stencil_shift(halo, -3, -1, 6, 'reflect') +
        (-4469 / 2240)
        * _stencil_shift(halo, -2, -1, 6, 'reflect') +
        (1769 / 700)
        * _stencil_shift(halo, -1, -1, 6, 'reflect') +
        (-1769 / 700)
        * _stencil_shift(halo, 1, -1, 6, 'reflect') +
        (4469 / 2240)
        * _stencil_shift(halo, 2, -1, 6, 'reflect') +
        (-4969 / 7560)
        * _stencil_shift(halo, 3, -1, 6, 'reflect') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -1, 6, 'reflect') +
        (-19 / 840)
        * _stencil_shift(halo, 5, -1, 6, 'reflect') +
        (479 / 302400)
        * _stencil_shift(halo, 6, -1, 6, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 10, -1, 'reflect'] = _fd_d3_a10_axis1_reflect


STENCIL_MOMENTS[3, 12] = (
    (-7, 59, 158400),
    (-6, -20137, 3326400),
    (-5, 2077, 44352),
    (-4, -31957, 138600),
    (-3, 247081, 302400),
    (-2, -222581, 100800),
    (-1, 90281, 33600),
    (0, 0, 1),
    (1, -90281, 33600),
    (2, 222581, 100800),
    (3, -247081, 302400),
    (4, 31957, 138600),
    (5, -2077, 44352),
    (6, 20137, 3326400),
    (7, -59, 158400),
)

def _fd_d3_a12_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 12, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 7, 'periodic', 3)
    result = (
        (59 / 158400)
        * _stencil_shift(halo, -7, -4, 7, 'periodic') +
        (-20137 / 3326400)
        * _stencil_shift(halo, -6, -4, 7, 'periodic') +
        (2077 / 44352)
        * _stencil_shift(halo, -5, -4, 7, 'periodic') +
        (-31957 / 138600)
        * _stencil_shift(halo, -4, -4, 7, 'periodic') +
        (247081 / 302400)
        * _stencil_shift(halo, -3, -4, 7, 'periodic') +
        (-222581 / 100800)
        * _stencil_shift(halo, -2, -4, 7, 'periodic') +
        (90281 / 33600)
        * _stencil_shift(halo, -1, -4, 7, 'periodic') +
        (-90281 / 33600)
        * _stencil_shift(halo, 1, -4, 7, 'periodic') +
        (222581 / 100800)
        * _stencil_shift(halo, 2, -4, 7, 'periodic') +
        (-247081 / 302400)
        * _stencil_shift(halo, 3, -4, 7, 'periodic') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -4, 7, 'periodic') +
        (-2077 / 44352)
        * _stencil_shift(halo, 5, -4, 7, 'periodic') +
        (20137 / 3326400)
        * _stencil_shift(halo, 6, -4, 7, 'periodic') +
        (-59 / 158400)
        * _stencil_shift(halo, 7, -4, 7, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 12, -4, 'periodic'] = _fd_d3_a12_axis4_periodic


def _fd_d3_a12_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 12, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 7, 'zero', 3)
    result = (
        (59 / 158400)
        * _stencil_shift(halo, -7, -4, 7, 'zero') +
        (-20137 / 3326400)
        * _stencil_shift(halo, -6, -4, 7, 'zero') +
        (2077 / 44352)
        * _stencil_shift(halo, -5, -4, 7, 'zero') +
        (-31957 / 138600)
        * _stencil_shift(halo, -4, -4, 7, 'zero') +
        (247081 / 302400)
        * _stencil_shift(halo, -3, -4, 7, 'zero') +
        (-222581 / 100800)
        * _stencil_shift(halo, -2, -4, 7, 'zero') +
        (90281 / 33600)
        * _stencil_shift(halo, -1, -4, 7, 'zero') +
        (-90281 / 33600)
        * _stencil_shift(halo, 1, -4, 7, 'zero') +
        (222581 / 100800)
        * _stencil_shift(halo, 2, -4, 7, 'zero') +
        (-247081 / 302400)
        * _stencil_shift(halo, 3, -4, 7, 'zero') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -4, 7, 'zero') +
        (-2077 / 44352)
        * _stencil_shift(halo, 5, -4, 7, 'zero') +
        (20137 / 3326400)
        * _stencil_shift(halo, 6, -4, 7, 'zero') +
        (-59 / 158400)
        * _stencil_shift(halo, 7, -4, 7, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 12, -4, 'zero'] = _fd_d3_a12_axis4_zero


def _fd_d3_a12_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 12, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 7, 'reflect', 3)
    result = (
        (59 / 158400)
        * _stencil_shift(halo, -7, -4, 7, 'reflect') +
        (-20137 / 3326400)
        * _stencil_shift(halo, -6, -4, 7, 'reflect') +
        (2077 / 44352)
        * _stencil_shift(halo, -5, -4, 7, 'reflect') +
        (-31957 / 138600)
        * _stencil_shift(halo, -4, -4, 7, 'reflect') +
        (247081 / 302400)
        * _stencil_shift(halo, -3, -4, 7, 'reflect') +
        (-222581 / 100800)
        * _stencil_shift(halo, -2, -4, 7, 'reflect') +
        (90281 / 33600)
        * _stencil_shift(halo, -1, -4, 7, 'reflect') +
        (-90281 / 33600)
        * _stencil_shift(halo, 1, -4, 7, 'reflect') +
        (222581 / 100800)
        * _stencil_shift(halo, 2, -4, 7, 'reflect') +
        (-247081 / 302400)
        * _stencil_shift(halo, 3, -4, 7, 'reflect') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -4, 7, 'reflect') +
        (-2077 / 44352)
        * _stencil_shift(halo, 5, -4, 7, 'reflect') +
        (20137 / 3326400)
        * _stencil_shift(halo, 6, -4, 7, 'reflect') +
        (-59 / 158400)
        * _stencil_shift(halo, 7, -4, 7, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 12, -4, 'reflect'] = _fd_d3_a12_axis4_reflect


def _fd_d3_a12_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 12, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 7, 'periodic', 3)
    result = (
        (59 / 158400)
        * _stencil_shift(halo, -7, -3, 7, 'periodic') +
        (-20137 / 3326400)
        * _stencil_shift(halo, -6, -3, 7, 'periodic') +
        (2077 / 44352)
        * _stencil_shift(halo, -5, -3, 7, 'periodic') +
        (-31957 / 138600)
        * _stencil_shift(halo, -4, -3, 7, 'periodic') +
        (247081 / 302400)
        * _stencil_shift(halo, -3, -3, 7, 'periodic') +
        (-222581 / 100800)
        * _stencil_shift(halo, -2, -3, 7, 'periodic') +
        (90281 / 33600)
        * _stencil_shift(halo, -1, -3, 7, 'periodic') +
        (-90281 / 33600)
        * _stencil_shift(halo, 1, -3, 7, 'periodic') +
        (222581 / 100800)
        * _stencil_shift(halo, 2, -3, 7, 'periodic') +
        (-247081 / 302400)
        * _stencil_shift(halo, 3, -3, 7, 'periodic') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -3, 7, 'periodic') +
        (-2077 / 44352)
        * _stencil_shift(halo, 5, -3, 7, 'periodic') +
        (20137 / 3326400)
        * _stencil_shift(halo, 6, -3, 7, 'periodic') +
        (-59 / 158400)
        * _stencil_shift(halo, 7, -3, 7, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 12, -3, 'periodic'] = _fd_d3_a12_axis3_periodic


def _fd_d3_a12_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 12, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 7, 'zero', 3)
    result = (
        (59 / 158400)
        * _stencil_shift(halo, -7, -3, 7, 'zero') +
        (-20137 / 3326400)
        * _stencil_shift(halo, -6, -3, 7, 'zero') +
        (2077 / 44352)
        * _stencil_shift(halo, -5, -3, 7, 'zero') +
        (-31957 / 138600)
        * _stencil_shift(halo, -4, -3, 7, 'zero') +
        (247081 / 302400)
        * _stencil_shift(halo, -3, -3, 7, 'zero') +
        (-222581 / 100800)
        * _stencil_shift(halo, -2, -3, 7, 'zero') +
        (90281 / 33600)
        * _stencil_shift(halo, -1, -3, 7, 'zero') +
        (-90281 / 33600)
        * _stencil_shift(halo, 1, -3, 7, 'zero') +
        (222581 / 100800)
        * _stencil_shift(halo, 2, -3, 7, 'zero') +
        (-247081 / 302400)
        * _stencil_shift(halo, 3, -3, 7, 'zero') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -3, 7, 'zero') +
        (-2077 / 44352)
        * _stencil_shift(halo, 5, -3, 7, 'zero') +
        (20137 / 3326400)
        * _stencil_shift(halo, 6, -3, 7, 'zero') +
        (-59 / 158400)
        * _stencil_shift(halo, 7, -3, 7, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 12, -3, 'zero'] = _fd_d3_a12_axis3_zero


def _fd_d3_a12_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 12, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 7, 'reflect', 3)
    result = (
        (59 / 158400)
        * _stencil_shift(halo, -7, -3, 7, 'reflect') +
        (-20137 / 3326400)
        * _stencil_shift(halo, -6, -3, 7, 'reflect') +
        (2077 / 44352)
        * _stencil_shift(halo, -5, -3, 7, 'reflect') +
        (-31957 / 138600)
        * _stencil_shift(halo, -4, -3, 7, 'reflect') +
        (247081 / 302400)
        * _stencil_shift(halo, -3, -3, 7, 'reflect') +
        (-222581 / 100800)
        * _stencil_shift(halo, -2, -3, 7, 'reflect') +
        (90281 / 33600)
        * _stencil_shift(halo, -1, -3, 7, 'reflect') +
        (-90281 / 33600)
        * _stencil_shift(halo, 1, -3, 7, 'reflect') +
        (222581 / 100800)
        * _stencil_shift(halo, 2, -3, 7, 'reflect') +
        (-247081 / 302400)
        * _stencil_shift(halo, 3, -3, 7, 'reflect') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -3, 7, 'reflect') +
        (-2077 / 44352)
        * _stencil_shift(halo, 5, -3, 7, 'reflect') +
        (20137 / 3326400)
        * _stencil_shift(halo, 6, -3, 7, 'reflect') +
        (-59 / 158400)
        * _stencil_shift(halo, 7, -3, 7, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 12, -3, 'reflect'] = _fd_d3_a12_axis3_reflect


def _fd_d3_a12_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 12, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 7, 'periodic', 3)
    result = (
        (59 / 158400)
        * _stencil_shift(halo, -7, -2, 7, 'periodic') +
        (-20137 / 3326400)
        * _stencil_shift(halo, -6, -2, 7, 'periodic') +
        (2077 / 44352)
        * _stencil_shift(halo, -5, -2, 7, 'periodic') +
        (-31957 / 138600)
        * _stencil_shift(halo, -4, -2, 7, 'periodic') +
        (247081 / 302400)
        * _stencil_shift(halo, -3, -2, 7, 'periodic') +
        (-222581 / 100800)
        * _stencil_shift(halo, -2, -2, 7, 'periodic') +
        (90281 / 33600)
        * _stencil_shift(halo, -1, -2, 7, 'periodic') +
        (-90281 / 33600)
        * _stencil_shift(halo, 1, -2, 7, 'periodic') +
        (222581 / 100800)
        * _stencil_shift(halo, 2, -2, 7, 'periodic') +
        (-247081 / 302400)
        * _stencil_shift(halo, 3, -2, 7, 'periodic') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -2, 7, 'periodic') +
        (-2077 / 44352)
        * _stencil_shift(halo, 5, -2, 7, 'periodic') +
        (20137 / 3326400)
        * _stencil_shift(halo, 6, -2, 7, 'periodic') +
        (-59 / 158400)
        * _stencil_shift(halo, 7, -2, 7, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 12, -2, 'periodic'] = _fd_d3_a12_axis2_periodic


def _fd_d3_a12_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 12, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 7, 'zero', 3)
    result = (
        (59 / 158400)
        * _stencil_shift(halo, -7, -2, 7, 'zero') +
        (-20137 / 3326400)
        * _stencil_shift(halo, -6, -2, 7, 'zero') +
        (2077 / 44352)
        * _stencil_shift(halo, -5, -2, 7, 'zero') +
        (-31957 / 138600)
        * _stencil_shift(halo, -4, -2, 7, 'zero') +
        (247081 / 302400)
        * _stencil_shift(halo, -3, -2, 7, 'zero') +
        (-222581 / 100800)
        * _stencil_shift(halo, -2, -2, 7, 'zero') +
        (90281 / 33600)
        * _stencil_shift(halo, -1, -2, 7, 'zero') +
        (-90281 / 33600)
        * _stencil_shift(halo, 1, -2, 7, 'zero') +
        (222581 / 100800)
        * _stencil_shift(halo, 2, -2, 7, 'zero') +
        (-247081 / 302400)
        * _stencil_shift(halo, 3, -2, 7, 'zero') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -2, 7, 'zero') +
        (-2077 / 44352)
        * _stencil_shift(halo, 5, -2, 7, 'zero') +
        (20137 / 3326400)
        * _stencil_shift(halo, 6, -2, 7, 'zero') +
        (-59 / 158400)
        * _stencil_shift(halo, 7, -2, 7, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 12, -2, 'zero'] = _fd_d3_a12_axis2_zero


def _fd_d3_a12_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 12, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 7, 'reflect', 3)
    result = (
        (59 / 158400)
        * _stencil_shift(halo, -7, -2, 7, 'reflect') +
        (-20137 / 3326400)
        * _stencil_shift(halo, -6, -2, 7, 'reflect') +
        (2077 / 44352)
        * _stencil_shift(halo, -5, -2, 7, 'reflect') +
        (-31957 / 138600)
        * _stencil_shift(halo, -4, -2, 7, 'reflect') +
        (247081 / 302400)
        * _stencil_shift(halo, -3, -2, 7, 'reflect') +
        (-222581 / 100800)
        * _stencil_shift(halo, -2, -2, 7, 'reflect') +
        (90281 / 33600)
        * _stencil_shift(halo, -1, -2, 7, 'reflect') +
        (-90281 / 33600)
        * _stencil_shift(halo, 1, -2, 7, 'reflect') +
        (222581 / 100800)
        * _stencil_shift(halo, 2, -2, 7, 'reflect') +
        (-247081 / 302400)
        * _stencil_shift(halo, 3, -2, 7, 'reflect') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -2, 7, 'reflect') +
        (-2077 / 44352)
        * _stencil_shift(halo, 5, -2, 7, 'reflect') +
        (20137 / 3326400)
        * _stencil_shift(halo, 6, -2, 7, 'reflect') +
        (-59 / 158400)
        * _stencil_shift(halo, 7, -2, 7, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 12, -2, 'reflect'] = _fd_d3_a12_axis2_reflect


def _fd_d3_a12_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 12, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 7, 'periodic', 3)
    result = (
        (59 / 158400)
        * _stencil_shift(halo, -7, -1, 7, 'periodic') +
        (-20137 / 3326400)
        * _stencil_shift(halo, -6, -1, 7, 'periodic') +
        (2077 / 44352)
        * _stencil_shift(halo, -5, -1, 7, 'periodic') +
        (-31957 / 138600)
        * _stencil_shift(halo, -4, -1, 7, 'periodic') +
        (247081 / 302400)
        * _stencil_shift(halo, -3, -1, 7, 'periodic') +
        (-222581 / 100800)
        * _stencil_shift(halo, -2, -1, 7, 'periodic') +
        (90281 / 33600)
        * _stencil_shift(halo, -1, -1, 7, 'periodic') +
        (-90281 / 33600)
        * _stencil_shift(halo, 1, -1, 7, 'periodic') +
        (222581 / 100800)
        * _stencil_shift(halo, 2, -1, 7, 'periodic') +
        (-247081 / 302400)
        * _stencil_shift(halo, 3, -1, 7, 'periodic') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -1, 7, 'periodic') +
        (-2077 / 44352)
        * _stencil_shift(halo, 5, -1, 7, 'periodic') +
        (20137 / 3326400)
        * _stencil_shift(halo, 6, -1, 7, 'periodic') +
        (-59 / 158400)
        * _stencil_shift(halo, 7, -1, 7, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 12, -1, 'periodic'] = _fd_d3_a12_axis1_periodic


def _fd_d3_a12_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 12, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 7, 'zero', 3)
    result = (
        (59 / 158400)
        * _stencil_shift(halo, -7, -1, 7, 'zero') +
        (-20137 / 3326400)
        * _stencil_shift(halo, -6, -1, 7, 'zero') +
        (2077 / 44352)
        * _stencil_shift(halo, -5, -1, 7, 'zero') +
        (-31957 / 138600)
        * _stencil_shift(halo, -4, -1, 7, 'zero') +
        (247081 / 302400)
        * _stencil_shift(halo, -3, -1, 7, 'zero') +
        (-222581 / 100800)
        * _stencil_shift(halo, -2, -1, 7, 'zero') +
        (90281 / 33600)
        * _stencil_shift(halo, -1, -1, 7, 'zero') +
        (-90281 / 33600)
        * _stencil_shift(halo, 1, -1, 7, 'zero') +
        (222581 / 100800)
        * _stencil_shift(halo, 2, -1, 7, 'zero') +
        (-247081 / 302400)
        * _stencil_shift(halo, 3, -1, 7, 'zero') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -1, 7, 'zero') +
        (-2077 / 44352)
        * _stencil_shift(halo, 5, -1, 7, 'zero') +
        (20137 / 3326400)
        * _stencil_shift(halo, 6, -1, 7, 'zero') +
        (-59 / 158400)
        * _stencil_shift(halo, 7, -1, 7, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 12, -1, 'zero'] = _fd_d3_a12_axis1_zero


def _fd_d3_a12_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 12, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 7, 'reflect', 3)
    result = (
        (59 / 158400)
        * _stencil_shift(halo, -7, -1, 7, 'reflect') +
        (-20137 / 3326400)
        * _stencil_shift(halo, -6, -1, 7, 'reflect') +
        (2077 / 44352)
        * _stencil_shift(halo, -5, -1, 7, 'reflect') +
        (-31957 / 138600)
        * _stencil_shift(halo, -4, -1, 7, 'reflect') +
        (247081 / 302400)
        * _stencil_shift(halo, -3, -1, 7, 'reflect') +
        (-222581 / 100800)
        * _stencil_shift(halo, -2, -1, 7, 'reflect') +
        (90281 / 33600)
        * _stencil_shift(halo, -1, -1, 7, 'reflect') +
        (-90281 / 33600)
        * _stencil_shift(halo, 1, -1, 7, 'reflect') +
        (222581 / 100800)
        * _stencil_shift(halo, 2, -1, 7, 'reflect') +
        (-247081 / 302400)
        * _stencil_shift(halo, 3, -1, 7, 'reflect') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -1, 7, 'reflect') +
        (-2077 / 44352)
        * _stencil_shift(halo, 5, -1, 7, 'reflect') +
        (20137 / 3326400)
        * _stencil_shift(halo, 6, -1, 7, 'reflect') +
        (-59 / 158400)
        * _stencil_shift(halo, 7, -1, 7, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 12, -1, 'reflect'] = _fd_d3_a12_axis1_reflect


STENCIL_MOMENTS[3, 14] = (
    (-8, -266681, 3027024000),
    (-7, 21701, 13513500),
    (-6, -1058149, 75675600),
    (-5, 41981, 540540),
    (-4, -1033649, 3326400),
    (-3, 999349, 1039500),
    (-2, -901349, 378000),
    (-1, 372149, 132300),
    (0, 0, 1),
    (1, -372149, 132300),
    (2, 901349, 378000),
    (3, -999349, 1039500),
    (4, 1033649, 3326400),
    (5, -41981, 540540),
    (6, 1058149, 75675600),
    (7, -21701, 13513500),
    (8, 266681, 3027024000),
)

def _fd_d3_a14_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 14, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 8, 'periodic', 3)
    result = (
        (-266681 / 3027024000)
        * _stencil_shift(halo, -8, -4, 8, 'periodic') +
        (21701 / 13513500)
        * _stencil_shift(halo, -7, -4, 8, 'periodic') +
        (-1058149 / 75675600)
        * _stencil_shift(halo, -6, -4, 8, 'periodic') +
        (41981 / 540540)
        * _stencil_shift(halo, -5, -4, 8, 'periodic') +
        (-1033649 / 3326400)
        * _stencil_shift(halo, -4, -4, 8, 'periodic') +
        (999349 / 1039500)
        * _stencil_shift(halo, -3, -4, 8, 'periodic') +
        (-901349 / 378000)
        * _stencil_shift(halo, -2, -4, 8, 'periodic') +
        (372149 / 132300)
        * _stencil_shift(halo, -1, -4, 8, 'periodic') +
        (-372149 / 132300)
        * _stencil_shift(halo, 1, -4, 8, 'periodic') +
        (901349 / 378000)
        * _stencil_shift(halo, 2, -4, 8, 'periodic') +
        (-999349 / 1039500)
        * _stencil_shift(halo, 3, -4, 8, 'periodic') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -4, 8, 'periodic') +
        (-41981 / 540540)
        * _stencil_shift(halo, 5, -4, 8, 'periodic') +
        (1058149 / 75675600)
        * _stencil_shift(halo, 6, -4, 8, 'periodic') +
        (-21701 / 13513500)
        * _stencil_shift(halo, 7, -4, 8, 'periodic') +
        (266681 / 3027024000)
        * _stencil_shift(halo, 8, -4, 8, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 14, -4, 'periodic'] = _fd_d3_a14_axis4_periodic


def _fd_d3_a14_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 14, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 8, 'zero', 3)
    result = (
        (-266681 / 3027024000)
        * _stencil_shift(halo, -8, -4, 8, 'zero') +
        (21701 / 13513500)
        * _stencil_shift(halo, -7, -4, 8, 'zero') +
        (-1058149 / 75675600)
        * _stencil_shift(halo, -6, -4, 8, 'zero') +
        (41981 / 540540)
        * _stencil_shift(halo, -5, -4, 8, 'zero') +
        (-1033649 / 3326400)
        * _stencil_shift(halo, -4, -4, 8, 'zero') +
        (999349 / 1039500)
        * _stencil_shift(halo, -3, -4, 8, 'zero') +
        (-901349 / 378000)
        * _stencil_shift(halo, -2, -4, 8, 'zero') +
        (372149 / 132300)
        * _stencil_shift(halo, -1, -4, 8, 'zero') +
        (-372149 / 132300)
        * _stencil_shift(halo, 1, -4, 8, 'zero') +
        (901349 / 378000)
        * _stencil_shift(halo, 2, -4, 8, 'zero') +
        (-999349 / 1039500)
        * _stencil_shift(halo, 3, -4, 8, 'zero') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -4, 8, 'zero') +
        (-41981 / 540540)
        * _stencil_shift(halo, 5, -4, 8, 'zero') +
        (1058149 / 75675600)
        * _stencil_shift(halo, 6, -4, 8, 'zero') +
        (-21701 / 13513500)
        * _stencil_shift(halo, 7, -4, 8, 'zero') +
        (266681 / 3027024000)
        * _stencil_shift(halo, 8, -4, 8, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 14, -4, 'zero'] = _fd_d3_a14_axis4_zero


def _fd_d3_a14_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 14, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 8, 'reflect', 3)
    result = (
        (-266681 / 3027024000)
        * _stencil_shift(halo, -8, -4, 8, 'reflect') +
        (21701 / 13513500)
        * _stencil_shift(halo, -7, -4, 8, 'reflect') +
        (-1058149 / 75675600)
        * _stencil_shift(halo, -6, -4, 8, 'reflect') +
        (41981 / 540540)
        * _stencil_shift(halo, -5, -4, 8, 'reflect') +
        (-1033649 / 3326400)
        * _stencil_shift(halo, -4, -4, 8, 'reflect') +
        (999349 / 1039500)
        * _stencil_shift(halo, -3, -4, 8, 'reflect') +
        (-901349 / 378000)
        * _stencil_shift(halo, -2, -4, 8, 'reflect') +
        (372149 / 132300)
        * _stencil_shift(halo, -1, -4, 8, 'reflect') +
        (-372149 / 132300)
        * _stencil_shift(halo, 1, -4, 8, 'reflect') +
        (901349 / 378000)
        * _stencil_shift(halo, 2, -4, 8, 'reflect') +
        (-999349 / 1039500)
        * _stencil_shift(halo, 3, -4, 8, 'reflect') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -4, 8, 'reflect') +
        (-41981 / 540540)
        * _stencil_shift(halo, 5, -4, 8, 'reflect') +
        (1058149 / 75675600)
        * _stencil_shift(halo, 6, -4, 8, 'reflect') +
        (-21701 / 13513500)
        * _stencil_shift(halo, 7, -4, 8, 'reflect') +
        (266681 / 3027024000)
        * _stencil_shift(halo, 8, -4, 8, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 14, -4, 'reflect'] = _fd_d3_a14_axis4_reflect


def _fd_d3_a14_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 14, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 8, 'periodic', 3)
    result = (
        (-266681 / 3027024000)
        * _stencil_shift(halo, -8, -3, 8, 'periodic') +
        (21701 / 13513500)
        * _stencil_shift(halo, -7, -3, 8, 'periodic') +
        (-1058149 / 75675600)
        * _stencil_shift(halo, -6, -3, 8, 'periodic') +
        (41981 / 540540)
        * _stencil_shift(halo, -5, -3, 8, 'periodic') +
        (-1033649 / 3326400)
        * _stencil_shift(halo, -4, -3, 8, 'periodic') +
        (999349 / 1039500)
        * _stencil_shift(halo, -3, -3, 8, 'periodic') +
        (-901349 / 378000)
        * _stencil_shift(halo, -2, -3, 8, 'periodic') +
        (372149 / 132300)
        * _stencil_shift(halo, -1, -3, 8, 'periodic') +
        (-372149 / 132300)
        * _stencil_shift(halo, 1, -3, 8, 'periodic') +
        (901349 / 378000)
        * _stencil_shift(halo, 2, -3, 8, 'periodic') +
        (-999349 / 1039500)
        * _stencil_shift(halo, 3, -3, 8, 'periodic') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -3, 8, 'periodic') +
        (-41981 / 540540)
        * _stencil_shift(halo, 5, -3, 8, 'periodic') +
        (1058149 / 75675600)
        * _stencil_shift(halo, 6, -3, 8, 'periodic') +
        (-21701 / 13513500)
        * _stencil_shift(halo, 7, -3, 8, 'periodic') +
        (266681 / 3027024000)
        * _stencil_shift(halo, 8, -3, 8, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 14, -3, 'periodic'] = _fd_d3_a14_axis3_periodic


def _fd_d3_a14_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 14, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 8, 'zero', 3)
    result = (
        (-266681 / 3027024000)
        * _stencil_shift(halo, -8, -3, 8, 'zero') +
        (21701 / 13513500)
        * _stencil_shift(halo, -7, -3, 8, 'zero') +
        (-1058149 / 75675600)
        * _stencil_shift(halo, -6, -3, 8, 'zero') +
        (41981 / 540540)
        * _stencil_shift(halo, -5, -3, 8, 'zero') +
        (-1033649 / 3326400)
        * _stencil_shift(halo, -4, -3, 8, 'zero') +
        (999349 / 1039500)
        * _stencil_shift(halo, -3, -3, 8, 'zero') +
        (-901349 / 378000)
        * _stencil_shift(halo, -2, -3, 8, 'zero') +
        (372149 / 132300)
        * _stencil_shift(halo, -1, -3, 8, 'zero') +
        (-372149 / 132300)
        * _stencil_shift(halo, 1, -3, 8, 'zero') +
        (901349 / 378000)
        * _stencil_shift(halo, 2, -3, 8, 'zero') +
        (-999349 / 1039500)
        * _stencil_shift(halo, 3, -3, 8, 'zero') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -3, 8, 'zero') +
        (-41981 / 540540)
        * _stencil_shift(halo, 5, -3, 8, 'zero') +
        (1058149 / 75675600)
        * _stencil_shift(halo, 6, -3, 8, 'zero') +
        (-21701 / 13513500)
        * _stencil_shift(halo, 7, -3, 8, 'zero') +
        (266681 / 3027024000)
        * _stencil_shift(halo, 8, -3, 8, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 14, -3, 'zero'] = _fd_d3_a14_axis3_zero


def _fd_d3_a14_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 14, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 8, 'reflect', 3)
    result = (
        (-266681 / 3027024000)
        * _stencil_shift(halo, -8, -3, 8, 'reflect') +
        (21701 / 13513500)
        * _stencil_shift(halo, -7, -3, 8, 'reflect') +
        (-1058149 / 75675600)
        * _stencil_shift(halo, -6, -3, 8, 'reflect') +
        (41981 / 540540)
        * _stencil_shift(halo, -5, -3, 8, 'reflect') +
        (-1033649 / 3326400)
        * _stencil_shift(halo, -4, -3, 8, 'reflect') +
        (999349 / 1039500)
        * _stencil_shift(halo, -3, -3, 8, 'reflect') +
        (-901349 / 378000)
        * _stencil_shift(halo, -2, -3, 8, 'reflect') +
        (372149 / 132300)
        * _stencil_shift(halo, -1, -3, 8, 'reflect') +
        (-372149 / 132300)
        * _stencil_shift(halo, 1, -3, 8, 'reflect') +
        (901349 / 378000)
        * _stencil_shift(halo, 2, -3, 8, 'reflect') +
        (-999349 / 1039500)
        * _stencil_shift(halo, 3, -3, 8, 'reflect') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -3, 8, 'reflect') +
        (-41981 / 540540)
        * _stencil_shift(halo, 5, -3, 8, 'reflect') +
        (1058149 / 75675600)
        * _stencil_shift(halo, 6, -3, 8, 'reflect') +
        (-21701 / 13513500)
        * _stencil_shift(halo, 7, -3, 8, 'reflect') +
        (266681 / 3027024000)
        * _stencil_shift(halo, 8, -3, 8, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 14, -3, 'reflect'] = _fd_d3_a14_axis3_reflect


def _fd_d3_a14_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 14, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 8, 'periodic', 3)
    result = (
        (-266681 / 3027024000)
        * _stencil_shift(halo, -8, -2, 8, 'periodic') +
        (21701 / 13513500)
        * _stencil_shift(halo, -7, -2, 8, 'periodic') +
        (-1058149 / 75675600)
        * _stencil_shift(halo, -6, -2, 8, 'periodic') +
        (41981 / 540540)
        * _stencil_shift(halo, -5, -2, 8, 'periodic') +
        (-1033649 / 3326400)
        * _stencil_shift(halo, -4, -2, 8, 'periodic') +
        (999349 / 1039500)
        * _stencil_shift(halo, -3, -2, 8, 'periodic') +
        (-901349 / 378000)
        * _stencil_shift(halo, -2, -2, 8, 'periodic') +
        (372149 / 132300)
        * _stencil_shift(halo, -1, -2, 8, 'periodic') +
        (-372149 / 132300)
        * _stencil_shift(halo, 1, -2, 8, 'periodic') +
        (901349 / 378000)
        * _stencil_shift(halo, 2, -2, 8, 'periodic') +
        (-999349 / 1039500)
        * _stencil_shift(halo, 3, -2, 8, 'periodic') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -2, 8, 'periodic') +
        (-41981 / 540540)
        * _stencil_shift(halo, 5, -2, 8, 'periodic') +
        (1058149 / 75675600)
        * _stencil_shift(halo, 6, -2, 8, 'periodic') +
        (-21701 / 13513500)
        * _stencil_shift(halo, 7, -2, 8, 'periodic') +
        (266681 / 3027024000)
        * _stencil_shift(halo, 8, -2, 8, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 14, -2, 'periodic'] = _fd_d3_a14_axis2_periodic


def _fd_d3_a14_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 14, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 8, 'zero', 3)
    result = (
        (-266681 / 3027024000)
        * _stencil_shift(halo, -8, -2, 8, 'zero') +
        (21701 / 13513500)
        * _stencil_shift(halo, -7, -2, 8, 'zero') +
        (-1058149 / 75675600)
        * _stencil_shift(halo, -6, -2, 8, 'zero') +
        (41981 / 540540)
        * _stencil_shift(halo, -5, -2, 8, 'zero') +
        (-1033649 / 3326400)
        * _stencil_shift(halo, -4, -2, 8, 'zero') +
        (999349 / 1039500)
        * _stencil_shift(halo, -3, -2, 8, 'zero') +
        (-901349 / 378000)
        * _stencil_shift(halo, -2, -2, 8, 'zero') +
        (372149 / 132300)
        * _stencil_shift(halo, -1, -2, 8, 'zero') +
        (-372149 / 132300)
        * _stencil_shift(halo, 1, -2, 8, 'zero') +
        (901349 / 378000)
        * _stencil_shift(halo, 2, -2, 8, 'zero') +
        (-999349 / 1039500)
        * _stencil_shift(halo, 3, -2, 8, 'zero') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -2, 8, 'zero') +
        (-41981 / 540540)
        * _stencil_shift(halo, 5, -2, 8, 'zero') +
        (1058149 / 75675600)
        * _stencil_shift(halo, 6, -2, 8, 'zero') +
        (-21701 / 13513500)
        * _stencil_shift(halo, 7, -2, 8, 'zero') +
        (266681 / 3027024000)
        * _stencil_shift(halo, 8, -2, 8, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 14, -2, 'zero'] = _fd_d3_a14_axis2_zero


def _fd_d3_a14_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 14, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 8, 'reflect', 3)
    result = (
        (-266681 / 3027024000)
        * _stencil_shift(halo, -8, -2, 8, 'reflect') +
        (21701 / 13513500)
        * _stencil_shift(halo, -7, -2, 8, 'reflect') +
        (-1058149 / 75675600)
        * _stencil_shift(halo, -6, -2, 8, 'reflect') +
        (41981 / 540540)
        * _stencil_shift(halo, -5, -2, 8, 'reflect') +
        (-1033649 / 3326400)
        * _stencil_shift(halo, -4, -2, 8, 'reflect') +
        (999349 / 1039500)
        * _stencil_shift(halo, -3, -2, 8, 'reflect') +
        (-901349 / 378000)
        * _stencil_shift(halo, -2, -2, 8, 'reflect') +
        (372149 / 132300)
        * _stencil_shift(halo, -1, -2, 8, 'reflect') +
        (-372149 / 132300)
        * _stencil_shift(halo, 1, -2, 8, 'reflect') +
        (901349 / 378000)
        * _stencil_shift(halo, 2, -2, 8, 'reflect') +
        (-999349 / 1039500)
        * _stencil_shift(halo, 3, -2, 8, 'reflect') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -2, 8, 'reflect') +
        (-41981 / 540540)
        * _stencil_shift(halo, 5, -2, 8, 'reflect') +
        (1058149 / 75675600)
        * _stencil_shift(halo, 6, -2, 8, 'reflect') +
        (-21701 / 13513500)
        * _stencil_shift(halo, 7, -2, 8, 'reflect') +
        (266681 / 3027024000)
        * _stencil_shift(halo, 8, -2, 8, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 14, -2, 'reflect'] = _fd_d3_a14_axis2_reflect


def _fd_d3_a14_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 14, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 8, 'periodic', 3)
    result = (
        (-266681 / 3027024000)
        * _stencil_shift(halo, -8, -1, 8, 'periodic') +
        (21701 / 13513500)
        * _stencil_shift(halo, -7, -1, 8, 'periodic') +
        (-1058149 / 75675600)
        * _stencil_shift(halo, -6, -1, 8, 'periodic') +
        (41981 / 540540)
        * _stencil_shift(halo, -5, -1, 8, 'periodic') +
        (-1033649 / 3326400)
        * _stencil_shift(halo, -4, -1, 8, 'periodic') +
        (999349 / 1039500)
        * _stencil_shift(halo, -3, -1, 8, 'periodic') +
        (-901349 / 378000)
        * _stencil_shift(halo, -2, -1, 8, 'periodic') +
        (372149 / 132300)
        * _stencil_shift(halo, -1, -1, 8, 'periodic') +
        (-372149 / 132300)
        * _stencil_shift(halo, 1, -1, 8, 'periodic') +
        (901349 / 378000)
        * _stencil_shift(halo, 2, -1, 8, 'periodic') +
        (-999349 / 1039500)
        * _stencil_shift(halo, 3, -1, 8, 'periodic') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -1, 8, 'periodic') +
        (-41981 / 540540)
        * _stencil_shift(halo, 5, -1, 8, 'periodic') +
        (1058149 / 75675600)
        * _stencil_shift(halo, 6, -1, 8, 'periodic') +
        (-21701 / 13513500)
        * _stencil_shift(halo, 7, -1, 8, 'periodic') +
        (266681 / 3027024000)
        * _stencil_shift(halo, 8, -1, 8, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 14, -1, 'periodic'] = _fd_d3_a14_axis1_periodic


def _fd_d3_a14_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 14, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 8, 'zero', 3)
    result = (
        (-266681 / 3027024000)
        * _stencil_shift(halo, -8, -1, 8, 'zero') +
        (21701 / 13513500)
        * _stencil_shift(halo, -7, -1, 8, 'zero') +
        (-1058149 / 75675600)
        * _stencil_shift(halo, -6, -1, 8, 'zero') +
        (41981 / 540540)
        * _stencil_shift(halo, -5, -1, 8, 'zero') +
        (-1033649 / 3326400)
        * _stencil_shift(halo, -4, -1, 8, 'zero') +
        (999349 / 1039500)
        * _stencil_shift(halo, -3, -1, 8, 'zero') +
        (-901349 / 378000)
        * _stencil_shift(halo, -2, -1, 8, 'zero') +
        (372149 / 132300)
        * _stencil_shift(halo, -1, -1, 8, 'zero') +
        (-372149 / 132300)
        * _stencil_shift(halo, 1, -1, 8, 'zero') +
        (901349 / 378000)
        * _stencil_shift(halo, 2, -1, 8, 'zero') +
        (-999349 / 1039500)
        * _stencil_shift(halo, 3, -1, 8, 'zero') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -1, 8, 'zero') +
        (-41981 / 540540)
        * _stencil_shift(halo, 5, -1, 8, 'zero') +
        (1058149 / 75675600)
        * _stencil_shift(halo, 6, -1, 8, 'zero') +
        (-21701 / 13513500)
        * _stencil_shift(halo, 7, -1, 8, 'zero') +
        (266681 / 3027024000)
        * _stencil_shift(halo, 8, -1, 8, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 14, -1, 'zero'] = _fd_d3_a14_axis1_zero


def _fd_d3_a14_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 14, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 8, 'reflect', 3)
    result = (
        (-266681 / 3027024000)
        * _stencil_shift(halo, -8, -1, 8, 'reflect') +
        (21701 / 13513500)
        * _stencil_shift(halo, -7, -1, 8, 'reflect') +
        (-1058149 / 75675600)
        * _stencil_shift(halo, -6, -1, 8, 'reflect') +
        (41981 / 540540)
        * _stencil_shift(halo, -5, -1, 8, 'reflect') +
        (-1033649 / 3326400)
        * _stencil_shift(halo, -4, -1, 8, 'reflect') +
        (999349 / 1039500)
        * _stencil_shift(halo, -3, -1, 8, 'reflect') +
        (-901349 / 378000)
        * _stencil_shift(halo, -2, -1, 8, 'reflect') +
        (372149 / 132300)
        * _stencil_shift(halo, -1, -1, 8, 'reflect') +
        (-372149 / 132300)
        * _stencil_shift(halo, 1, -1, 8, 'reflect') +
        (901349 / 378000)
        * _stencil_shift(halo, 2, -1, 8, 'reflect') +
        (-999349 / 1039500)
        * _stencil_shift(halo, 3, -1, 8, 'reflect') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -1, 8, 'reflect') +
        (-41981 / 540540)
        * _stencil_shift(halo, 5, -1, 8, 'reflect') +
        (1058149 / 75675600)
        * _stencil_shift(halo, 6, -1, 8, 'reflect') +
        (-21701 / 13513500)
        * _stencil_shift(halo, 7, -1, 8, 'reflect') +
        (266681 / 3027024000)
        * _stencil_shift(halo, 8, -1, 8, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 14, -1, 'reflect'] = _fd_d3_a14_axis1_reflect


STENCIL_MOMENTS[3, 16] = (
    (-9, 63397, 3027024000),
    (-8, -10949, 25872000),
    (-7, 196909, 48048000),
    (-6, -9601741, 378378000),
    (-5, 5861, 51744),
    (-4, -9381241, 24024000),
    (-3, 9072541, 8316000),
    (-2, -8190541, 3234000),
    (-1, 3427741, 1176000),
    (0, 0, 1),
    (1, -3427741, 1176000),
    (2, 8190541, 3234000),
    (3, -9072541, 8316000),
    (4, 9381241, 24024000),
    (5, -5861, 51744),
    (6, 9601741, 378378000),
    (7, -196909, 48048000),
    (8, 10949, 25872000),
    (9, -63397, 3027024000),
)

def _fd_d3_a16_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 16, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 9, 'periodic', 3)
    result = (
        (63397 / 3027024000)
        * _stencil_shift(halo, -9, -4, 9, 'periodic') +
        (-10949 / 25872000)
        * _stencil_shift(halo, -8, -4, 9, 'periodic') +
        (196909 / 48048000)
        * _stencil_shift(halo, -7, -4, 9, 'periodic') +
        (-9601741 / 378378000)
        * _stencil_shift(halo, -6, -4, 9, 'periodic') +
        (5861 / 51744)
        * _stencil_shift(halo, -5, -4, 9, 'periodic') +
        (-9381241 / 24024000)
        * _stencil_shift(halo, -4, -4, 9, 'periodic') +
        (9072541 / 8316000)
        * _stencil_shift(halo, -3, -4, 9, 'periodic') +
        (-8190541 / 3234000)
        * _stencil_shift(halo, -2, -4, 9, 'periodic') +
        (3427741 / 1176000)
        * _stencil_shift(halo, -1, -4, 9, 'periodic') +
        (-3427741 / 1176000)
        * _stencil_shift(halo, 1, -4, 9, 'periodic') +
        (8190541 / 3234000)
        * _stencil_shift(halo, 2, -4, 9, 'periodic') +
        (-9072541 / 8316000)
        * _stencil_shift(halo, 3, -4, 9, 'periodic') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -4, 9, 'periodic') +
        (-5861 / 51744)
        * _stencil_shift(halo, 5, -4, 9, 'periodic') +
        (9601741 / 378378000)
        * _stencil_shift(halo, 6, -4, 9, 'periodic') +
        (-196909 / 48048000)
        * _stencil_shift(halo, 7, -4, 9, 'periodic') +
        (10949 / 25872000)
        * _stencil_shift(halo, 8, -4, 9, 'periodic') +
        (-63397 / 3027024000)
        * _stencil_shift(halo, 9, -4, 9, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 16, -4, 'periodic'] = _fd_d3_a16_axis4_periodic


def _fd_d3_a16_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 16, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 9, 'zero', 3)
    result = (
        (63397 / 3027024000)
        * _stencil_shift(halo, -9, -4, 9, 'zero') +
        (-10949 / 25872000)
        * _stencil_shift(halo, -8, -4, 9, 'zero') +
        (196909 / 48048000)
        * _stencil_shift(halo, -7, -4, 9, 'zero') +
        (-9601741 / 378378000)
        * _stencil_shift(halo, -6, -4, 9, 'zero') +
        (5861 / 51744)
        * _stencil_shift(halo, -5, -4, 9, 'zero') +
        (-9381241 / 24024000)
        * _stencil_shift(halo, -4, -4, 9, 'zero') +
        (9072541 / 8316000)
        * _stencil_shift(halo, -3, -4, 9, 'zero') +
        (-8190541 / 3234000)
        * _stencil_shift(halo, -2, -4, 9, 'zero') +
        (3427741 / 1176000)
        * _stencil_shift(halo, -1, -4, 9, 'zero') +
        (-3427741 / 1176000)
        * _stencil_shift(halo, 1, -4, 9, 'zero') +
        (8190541 / 3234000)
        * _stencil_shift(halo, 2, -4, 9, 'zero') +
        (-9072541 / 8316000)
        * _stencil_shift(halo, 3, -4, 9, 'zero') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -4, 9, 'zero') +
        (-5861 / 51744)
        * _stencil_shift(halo, 5, -4, 9, 'zero') +
        (9601741 / 378378000)
        * _stencil_shift(halo, 6, -4, 9, 'zero') +
        (-196909 / 48048000)
        * _stencil_shift(halo, 7, -4, 9, 'zero') +
        (10949 / 25872000)
        * _stencil_shift(halo, 8, -4, 9, 'zero') +
        (-63397 / 3027024000)
        * _stencil_shift(halo, 9, -4, 9, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 16, -4, 'zero'] = _fd_d3_a16_axis4_zero


def _fd_d3_a16_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 16, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 9, 'reflect', 3)
    result = (
        (63397 / 3027024000)
        * _stencil_shift(halo, -9, -4, 9, 'reflect') +
        (-10949 / 25872000)
        * _stencil_shift(halo, -8, -4, 9, 'reflect') +
        (196909 / 48048000)
        * _stencil_shift(halo, -7, -4, 9, 'reflect') +
        (-9601741 / 378378000)
        * _stencil_shift(halo, -6, -4, 9, 'reflect') +
        (5861 / 51744)
        * _stencil_shift(halo, -5, -4, 9, 'reflect') +
        (-9381241 / 24024000)
        * _stencil_shift(halo, -4, -4, 9, 'reflect') +
        (9072541 / 8316000)
        * _stencil_shift(halo, -3, -4, 9, 'reflect') +
        (-8190541 / 3234000)
        * _stencil_shift(halo, -2, -4, 9, 'reflect') +
        (3427741 / 1176000)
        * _stencil_shift(halo, -1, -4, 9, 'reflect') +
        (-3427741 / 1176000)
        * _stencil_shift(halo, 1, -4, 9, 'reflect') +
        (8190541 / 3234000)
        * _stencil_shift(halo, 2, -4, 9, 'reflect') +
        (-9072541 / 8316000)
        * _stencil_shift(halo, 3, -4, 9, 'reflect') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -4, 9, 'reflect') +
        (-5861 / 51744)
        * _stencil_shift(halo, 5, -4, 9, 'reflect') +
        (9601741 / 378378000)
        * _stencil_shift(halo, 6, -4, 9, 'reflect') +
        (-196909 / 48048000)
        * _stencil_shift(halo, 7, -4, 9, 'reflect') +
        (10949 / 25872000)
        * _stencil_shift(halo, 8, -4, 9, 'reflect') +
        (-63397 / 3027024000)
        * _stencil_shift(halo, 9, -4, 9, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 16, -4, 'reflect'] = _fd_d3_a16_axis4_reflect


def _fd_d3_a16_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 16, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 9, 'periodic', 3)
    result = (
        (63397 / 3027024000)
        * _stencil_shift(halo, -9, -3, 9, 'periodic') +
        (-10949 / 25872000)
        * _stencil_shift(halo, -8, -3, 9, 'periodic') +
        (196909 / 48048000)
        * _stencil_shift(halo, -7, -3, 9, 'periodic') +
        (-9601741 / 378378000)
        * _stencil_shift(halo, -6, -3, 9, 'periodic') +
        (5861 / 51744)
        * _stencil_shift(halo, -5, -3, 9, 'periodic') +
        (-9381241 / 24024000)
        * _stencil_shift(halo, -4, -3, 9, 'periodic') +
        (9072541 / 8316000)
        * _stencil_shift(halo, -3, -3, 9, 'periodic') +
        (-8190541 / 3234000)
        * _stencil_shift(halo, -2, -3, 9, 'periodic') +
        (3427741 / 1176000)
        * _stencil_shift(halo, -1, -3, 9, 'periodic') +
        (-3427741 / 1176000)
        * _stencil_shift(halo, 1, -3, 9, 'periodic') +
        (8190541 / 3234000)
        * _stencil_shift(halo, 2, -3, 9, 'periodic') +
        (-9072541 / 8316000)
        * _stencil_shift(halo, 3, -3, 9, 'periodic') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -3, 9, 'periodic') +
        (-5861 / 51744)
        * _stencil_shift(halo, 5, -3, 9, 'periodic') +
        (9601741 / 378378000)
        * _stencil_shift(halo, 6, -3, 9, 'periodic') +
        (-196909 / 48048000)
        * _stencil_shift(halo, 7, -3, 9, 'periodic') +
        (10949 / 25872000)
        * _stencil_shift(halo, 8, -3, 9, 'periodic') +
        (-63397 / 3027024000)
        * _stencil_shift(halo, 9, -3, 9, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 16, -3, 'periodic'] = _fd_d3_a16_axis3_periodic


def _fd_d3_a16_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 16, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 9, 'zero', 3)
    result = (
        (63397 / 3027024000)
        * _stencil_shift(halo, -9, -3, 9, 'zero') +
        (-10949 / 25872000)
        * _stencil_shift(halo, -8, -3, 9, 'zero') +
        (196909 / 48048000)
        * _stencil_shift(halo, -7, -3, 9, 'zero') +
        (-9601741 / 378378000)
        * _stencil_shift(halo, -6, -3, 9, 'zero') +
        (5861 / 51744)
        * _stencil_shift(halo, -5, -3, 9, 'zero') +
        (-9381241 / 24024000)
        * _stencil_shift(halo, -4, -3, 9, 'zero') +
        (9072541 / 8316000)
        * _stencil_shift(halo, -3, -3, 9, 'zero') +
        (-8190541 / 3234000)
        * _stencil_shift(halo, -2, -3, 9, 'zero') +
        (3427741 / 1176000)
        * _stencil_shift(halo, -1, -3, 9, 'zero') +
        (-3427741 / 1176000)
        * _stencil_shift(halo, 1, -3, 9, 'zero') +
        (8190541 / 3234000)
        * _stencil_shift(halo, 2, -3, 9, 'zero') +
        (-9072541 / 8316000)
        * _stencil_shift(halo, 3, -3, 9, 'zero') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -3, 9, 'zero') +
        (-5861 / 51744)
        * _stencil_shift(halo, 5, -3, 9, 'zero') +
        (9601741 / 378378000)
        * _stencil_shift(halo, 6, -3, 9, 'zero') +
        (-196909 / 48048000)
        * _stencil_shift(halo, 7, -3, 9, 'zero') +
        (10949 / 25872000)
        * _stencil_shift(halo, 8, -3, 9, 'zero') +
        (-63397 / 3027024000)
        * _stencil_shift(halo, 9, -3, 9, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 16, -3, 'zero'] = _fd_d3_a16_axis3_zero


def _fd_d3_a16_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 16, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 9, 'reflect', 3)
    result = (
        (63397 / 3027024000)
        * _stencil_shift(halo, -9, -3, 9, 'reflect') +
        (-10949 / 25872000)
        * _stencil_shift(halo, -8, -3, 9, 'reflect') +
        (196909 / 48048000)
        * _stencil_shift(halo, -7, -3, 9, 'reflect') +
        (-9601741 / 378378000)
        * _stencil_shift(halo, -6, -3, 9, 'reflect') +
        (5861 / 51744)
        * _stencil_shift(halo, -5, -3, 9, 'reflect') +
        (-9381241 / 24024000)
        * _stencil_shift(halo, -4, -3, 9, 'reflect') +
        (9072541 / 8316000)
        * _stencil_shift(halo, -3, -3, 9, 'reflect') +
        (-8190541 / 3234000)
        * _stencil_shift(halo, -2, -3, 9, 'reflect') +
        (3427741 / 1176000)
        * _stencil_shift(halo, -1, -3, 9, 'reflect') +
        (-3427741 / 1176000)
        * _stencil_shift(halo, 1, -3, 9, 'reflect') +
        (8190541 / 3234000)
        * _stencil_shift(halo, 2, -3, 9, 'reflect') +
        (-9072541 / 8316000)
        * _stencil_shift(halo, 3, -3, 9, 'reflect') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -3, 9, 'reflect') +
        (-5861 / 51744)
        * _stencil_shift(halo, 5, -3, 9, 'reflect') +
        (9601741 / 378378000)
        * _stencil_shift(halo, 6, -3, 9, 'reflect') +
        (-196909 / 48048000)
        * _stencil_shift(halo, 7, -3, 9, 'reflect') +
        (10949 / 25872000)
        * _stencil_shift(halo, 8, -3, 9, 'reflect') +
        (-63397 / 3027024000)
        * _stencil_shift(halo, 9, -3, 9, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 16, -3, 'reflect'] = _fd_d3_a16_axis3_reflect


def _fd_d3_a16_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 16, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 9, 'periodic', 3)
    result = (
        (63397 / 3027024000)
        * _stencil_shift(halo, -9, -2, 9, 'periodic') +
        (-10949 / 25872000)
        * _stencil_shift(halo, -8, -2, 9, 'periodic') +
        (196909 / 48048000)
        * _stencil_shift(halo, -7, -2, 9, 'periodic') +
        (-9601741 / 378378000)
        * _stencil_shift(halo, -6, -2, 9, 'periodic') +
        (5861 / 51744)
        * _stencil_shift(halo, -5, -2, 9, 'periodic') +
        (-9381241 / 24024000)
        * _stencil_shift(halo, -4, -2, 9, 'periodic') +
        (9072541 / 8316000)
        * _stencil_shift(halo, -3, -2, 9, 'periodic') +
        (-8190541 / 3234000)
        * _stencil_shift(halo, -2, -2, 9, 'periodic') +
        (3427741 / 1176000)
        * _stencil_shift(halo, -1, -2, 9, 'periodic') +
        (-3427741 / 1176000)
        * _stencil_shift(halo, 1, -2, 9, 'periodic') +
        (8190541 / 3234000)
        * _stencil_shift(halo, 2, -2, 9, 'periodic') +
        (-9072541 / 8316000)
        * _stencil_shift(halo, 3, -2, 9, 'periodic') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -2, 9, 'periodic') +
        (-5861 / 51744)
        * _stencil_shift(halo, 5, -2, 9, 'periodic') +
        (9601741 / 378378000)
        * _stencil_shift(halo, 6, -2, 9, 'periodic') +
        (-196909 / 48048000)
        * _stencil_shift(halo, 7, -2, 9, 'periodic') +
        (10949 / 25872000)
        * _stencil_shift(halo, 8, -2, 9, 'periodic') +
        (-63397 / 3027024000)
        * _stencil_shift(halo, 9, -2, 9, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 16, -2, 'periodic'] = _fd_d3_a16_axis2_periodic


def _fd_d3_a16_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 16, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 9, 'zero', 3)
    result = (
        (63397 / 3027024000)
        * _stencil_shift(halo, -9, -2, 9, 'zero') +
        (-10949 / 25872000)
        * _stencil_shift(halo, -8, -2, 9, 'zero') +
        (196909 / 48048000)
        * _stencil_shift(halo, -7, -2, 9, 'zero') +
        (-9601741 / 378378000)
        * _stencil_shift(halo, -6, -2, 9, 'zero') +
        (5861 / 51744)
        * _stencil_shift(halo, -5, -2, 9, 'zero') +
        (-9381241 / 24024000)
        * _stencil_shift(halo, -4, -2, 9, 'zero') +
        (9072541 / 8316000)
        * _stencil_shift(halo, -3, -2, 9, 'zero') +
        (-8190541 / 3234000)
        * _stencil_shift(halo, -2, -2, 9, 'zero') +
        (3427741 / 1176000)
        * _stencil_shift(halo, -1, -2, 9, 'zero') +
        (-3427741 / 1176000)
        * _stencil_shift(halo, 1, -2, 9, 'zero') +
        (8190541 / 3234000)
        * _stencil_shift(halo, 2, -2, 9, 'zero') +
        (-9072541 / 8316000)
        * _stencil_shift(halo, 3, -2, 9, 'zero') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -2, 9, 'zero') +
        (-5861 / 51744)
        * _stencil_shift(halo, 5, -2, 9, 'zero') +
        (9601741 / 378378000)
        * _stencil_shift(halo, 6, -2, 9, 'zero') +
        (-196909 / 48048000)
        * _stencil_shift(halo, 7, -2, 9, 'zero') +
        (10949 / 25872000)
        * _stencil_shift(halo, 8, -2, 9, 'zero') +
        (-63397 / 3027024000)
        * _stencil_shift(halo, 9, -2, 9, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 16, -2, 'zero'] = _fd_d3_a16_axis2_zero


def _fd_d3_a16_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 16, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 9, 'reflect', 3)
    result = (
        (63397 / 3027024000)
        * _stencil_shift(halo, -9, -2, 9, 'reflect') +
        (-10949 / 25872000)
        * _stencil_shift(halo, -8, -2, 9, 'reflect') +
        (196909 / 48048000)
        * _stencil_shift(halo, -7, -2, 9, 'reflect') +
        (-9601741 / 378378000)
        * _stencil_shift(halo, -6, -2, 9, 'reflect') +
        (5861 / 51744)
        * _stencil_shift(halo, -5, -2, 9, 'reflect') +
        (-9381241 / 24024000)
        * _stencil_shift(halo, -4, -2, 9, 'reflect') +
        (9072541 / 8316000)
        * _stencil_shift(halo, -3, -2, 9, 'reflect') +
        (-8190541 / 3234000)
        * _stencil_shift(halo, -2, -2, 9, 'reflect') +
        (3427741 / 1176000)
        * _stencil_shift(halo, -1, -2, 9, 'reflect') +
        (-3427741 / 1176000)
        * _stencil_shift(halo, 1, -2, 9, 'reflect') +
        (8190541 / 3234000)
        * _stencil_shift(halo, 2, -2, 9, 'reflect') +
        (-9072541 / 8316000)
        * _stencil_shift(halo, 3, -2, 9, 'reflect') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -2, 9, 'reflect') +
        (-5861 / 51744)
        * _stencil_shift(halo, 5, -2, 9, 'reflect') +
        (9601741 / 378378000)
        * _stencil_shift(halo, 6, -2, 9, 'reflect') +
        (-196909 / 48048000)
        * _stencil_shift(halo, 7, -2, 9, 'reflect') +
        (10949 / 25872000)
        * _stencil_shift(halo, 8, -2, 9, 'reflect') +
        (-63397 / 3027024000)
        * _stencil_shift(halo, 9, -2, 9, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 16, -2, 'reflect'] = _fd_d3_a16_axis2_reflect


def _fd_d3_a16_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 16, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 9, 'periodic', 3)
    result = (
        (63397 / 3027024000)
        * _stencil_shift(halo, -9, -1, 9, 'periodic') +
        (-10949 / 25872000)
        * _stencil_shift(halo, -8, -1, 9, 'periodic') +
        (196909 / 48048000)
        * _stencil_shift(halo, -7, -1, 9, 'periodic') +
        (-9601741 / 378378000)
        * _stencil_shift(halo, -6, -1, 9, 'periodic') +
        (5861 / 51744)
        * _stencil_shift(halo, -5, -1, 9, 'periodic') +
        (-9381241 / 24024000)
        * _stencil_shift(halo, -4, -1, 9, 'periodic') +
        (9072541 / 8316000)
        * _stencil_shift(halo, -3, -1, 9, 'periodic') +
        (-8190541 / 3234000)
        * _stencil_shift(halo, -2, -1, 9, 'periodic') +
        (3427741 / 1176000)
        * _stencil_shift(halo, -1, -1, 9, 'periodic') +
        (-3427741 / 1176000)
        * _stencil_shift(halo, 1, -1, 9, 'periodic') +
        (8190541 / 3234000)
        * _stencil_shift(halo, 2, -1, 9, 'periodic') +
        (-9072541 / 8316000)
        * _stencil_shift(halo, 3, -1, 9, 'periodic') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -1, 9, 'periodic') +
        (-5861 / 51744)
        * _stencil_shift(halo, 5, -1, 9, 'periodic') +
        (9601741 / 378378000)
        * _stencil_shift(halo, 6, -1, 9, 'periodic') +
        (-196909 / 48048000)
        * _stencil_shift(halo, 7, -1, 9, 'periodic') +
        (10949 / 25872000)
        * _stencil_shift(halo, 8, -1, 9, 'periodic') +
        (-63397 / 3027024000)
        * _stencil_shift(halo, 9, -1, 9, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 16, -1, 'periodic'] = _fd_d3_a16_axis1_periodic


def _fd_d3_a16_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 16, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 9, 'zero', 3)
    result = (
        (63397 / 3027024000)
        * _stencil_shift(halo, -9, -1, 9, 'zero') +
        (-10949 / 25872000)
        * _stencil_shift(halo, -8, -1, 9, 'zero') +
        (196909 / 48048000)
        * _stencil_shift(halo, -7, -1, 9, 'zero') +
        (-9601741 / 378378000)
        * _stencil_shift(halo, -6, -1, 9, 'zero') +
        (5861 / 51744)
        * _stencil_shift(halo, -5, -1, 9, 'zero') +
        (-9381241 / 24024000)
        * _stencil_shift(halo, -4, -1, 9, 'zero') +
        (9072541 / 8316000)
        * _stencil_shift(halo, -3, -1, 9, 'zero') +
        (-8190541 / 3234000)
        * _stencil_shift(halo, -2, -1, 9, 'zero') +
        (3427741 / 1176000)
        * _stencil_shift(halo, -1, -1, 9, 'zero') +
        (-3427741 / 1176000)
        * _stencil_shift(halo, 1, -1, 9, 'zero') +
        (8190541 / 3234000)
        * _stencil_shift(halo, 2, -1, 9, 'zero') +
        (-9072541 / 8316000)
        * _stencil_shift(halo, 3, -1, 9, 'zero') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -1, 9, 'zero') +
        (-5861 / 51744)
        * _stencil_shift(halo, 5, -1, 9, 'zero') +
        (9601741 / 378378000)
        * _stencil_shift(halo, 6, -1, 9, 'zero') +
        (-196909 / 48048000)
        * _stencil_shift(halo, 7, -1, 9, 'zero') +
        (10949 / 25872000)
        * _stencil_shift(halo, 8, -1, 9, 'zero') +
        (-63397 / 3027024000)
        * _stencil_shift(halo, 9, -1, 9, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 16, -1, 'zero'] = _fd_d3_a16_axis1_zero


def _fd_d3_a16_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 16, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 9, 'reflect', 3)
    result = (
        (63397 / 3027024000)
        * _stencil_shift(halo, -9, -1, 9, 'reflect') +
        (-10949 / 25872000)
        * _stencil_shift(halo, -8, -1, 9, 'reflect') +
        (196909 / 48048000)
        * _stencil_shift(halo, -7, -1, 9, 'reflect') +
        (-9601741 / 378378000)
        * _stencil_shift(halo, -6, -1, 9, 'reflect') +
        (5861 / 51744)
        * _stencil_shift(halo, -5, -1, 9, 'reflect') +
        (-9381241 / 24024000)
        * _stencil_shift(halo, -4, -1, 9, 'reflect') +
        (9072541 / 8316000)
        * _stencil_shift(halo, -3, -1, 9, 'reflect') +
        (-8190541 / 3234000)
        * _stencil_shift(halo, -2, -1, 9, 'reflect') +
        (3427741 / 1176000)
        * _stencil_shift(halo, -1, -1, 9, 'reflect') +
        (-3427741 / 1176000)
        * _stencil_shift(halo, 1, -1, 9, 'reflect') +
        (8190541 / 3234000)
        * _stencil_shift(halo, 2, -1, 9, 'reflect') +
        (-9072541 / 8316000)
        * _stencil_shift(halo, 3, -1, 9, 'reflect') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -1, 9, 'reflect') +
        (-5861 / 51744)
        * _stencil_shift(halo, 5, -1, 9, 'reflect') +
        (9601741 / 378378000)
        * _stencil_shift(halo, 6, -1, 9, 'reflect') +
        (-196909 / 48048000)
        * _stencil_shift(halo, 7, -1, 9, 'reflect') +
        (10949 / 25872000)
        * _stencil_shift(halo, 8, -1, 9, 'reflect') +
        (-63397 / 3027024000)
        * _stencil_shift(halo, 9, -1, 9, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 16, -1, 'reflect'] = _fd_d3_a16_axis1_reflect


STENCIL_MOMENTS[3, 18] = (
    (-10, -514639, 102918816000),
    (-9, 11419, 102918816),
    (-8, -487121, 411675264),
    (-7, 5663, 700128),
    (-6, -1933049, 48432384),
    (-5, 9587629, 63063000),
    (-4, -1888949, 4036032),
    (-3, 1827209, 1513512),
    (-2, -1650809, 620928),
    (-1, 698249, 232848),
    (0, 0, 1),
    (1, -698249, 232848),
    (2, 1650809, 620928),
    (3, -1827209, 1513512),
    (4, 1888949, 4036032),
    (5, -9587629, 63063000),
    (6, 1933049, 48432384),
    (7, -5663, 700128),
    (8, 487121, 411675264),
    (9, -11419, 102918816),
    (10, 514639, 102918816000),
)

def _fd_d3_a18_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 18, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 10, 'periodic', 3)
    result = (
        (-514639 / 102918816000)
        * _stencil_shift(halo, -10, -4, 10, 'periodic') +
        (11419 / 102918816)
        * _stencil_shift(halo, -9, -4, 10, 'periodic') +
        (-487121 / 411675264)
        * _stencil_shift(halo, -8, -4, 10, 'periodic') +
        (5663 / 700128)
        * _stencil_shift(halo, -7, -4, 10, 'periodic') +
        (-1933049 / 48432384)
        * _stencil_shift(halo, -6, -4, 10, 'periodic') +
        (9587629 / 63063000)
        * _stencil_shift(halo, -5, -4, 10, 'periodic') +
        (-1888949 / 4036032)
        * _stencil_shift(halo, -4, -4, 10, 'periodic') +
        (1827209 / 1513512)
        * _stencil_shift(halo, -3, -4, 10, 'periodic') +
        (-1650809 / 620928)
        * _stencil_shift(halo, -2, -4, 10, 'periodic') +
        (698249 / 232848)
        * _stencil_shift(halo, -1, -4, 10, 'periodic') +
        (-698249 / 232848)
        * _stencil_shift(halo, 1, -4, 10, 'periodic') +
        (1650809 / 620928)
        * _stencil_shift(halo, 2, -4, 10, 'periodic') +
        (-1827209 / 1513512)
        * _stencil_shift(halo, 3, -4, 10, 'periodic') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -4, 10, 'periodic') +
        (-9587629 / 63063000)
        * _stencil_shift(halo, 5, -4, 10, 'periodic') +
        (1933049 / 48432384)
        * _stencil_shift(halo, 6, -4, 10, 'periodic') +
        (-5663 / 700128)
        * _stencil_shift(halo, 7, -4, 10, 'periodic') +
        (487121 / 411675264)
        * _stencil_shift(halo, 8, -4, 10, 'periodic') +
        (-11419 / 102918816)
        * _stencil_shift(halo, 9, -4, 10, 'periodic') +
        (514639 / 102918816000)
        * _stencil_shift(halo, 10, -4, 10, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 18, -4, 'periodic'] = _fd_d3_a18_axis4_periodic


def _fd_d3_a18_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 18, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 10, 'zero', 3)
    result = (
        (-514639 / 102918816000)
        * _stencil_shift(halo, -10, -4, 10, 'zero') +
        (11419 / 102918816)
        * _stencil_shift(halo, -9, -4, 10, 'zero') +
        (-487121 / 411675264)
        * _stencil_shift(halo, -8, -4, 10, 'zero') +
        (5663 / 700128)
        * _stencil_shift(halo, -7, -4, 10, 'zero') +
        (-1933049 / 48432384)
        * _stencil_shift(halo, -6, -4, 10, 'zero') +
        (9587629 / 63063000)
        * _stencil_shift(halo, -5, -4, 10, 'zero') +
        (-1888949 / 4036032)
        * _stencil_shift(halo, -4, -4, 10, 'zero') +
        (1827209 / 1513512)
        * _stencil_shift(halo, -3, -4, 10, 'zero') +
        (-1650809 / 620928)
        * _stencil_shift(halo, -2, -4, 10, 'zero') +
        (698249 / 232848)
        * _stencil_shift(halo, -1, -4, 10, 'zero') +
        (-698249 / 232848)
        * _stencil_shift(halo, 1, -4, 10, 'zero') +
        (1650809 / 620928)
        * _stencil_shift(halo, 2, -4, 10, 'zero') +
        (-1827209 / 1513512)
        * _stencil_shift(halo, 3, -4, 10, 'zero') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -4, 10, 'zero') +
        (-9587629 / 63063000)
        * _stencil_shift(halo, 5, -4, 10, 'zero') +
        (1933049 / 48432384)
        * _stencil_shift(halo, 6, -4, 10, 'zero') +
        (-5663 / 700128)
        * _stencil_shift(halo, 7, -4, 10, 'zero') +
        (487121 / 411675264)
        * _stencil_shift(halo, 8, -4, 10, 'zero') +
        (-11419 / 102918816)
        * _stencil_shift(halo, 9, -4, 10, 'zero') +
        (514639 / 102918816000)
        * _stencil_shift(halo, 10, -4, 10, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 18, -4, 'zero'] = _fd_d3_a18_axis4_zero


def _fd_d3_a18_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 18, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 10, 'reflect', 3)
    result = (
        (-514639 / 102918816000)
        * _stencil_shift(halo, -10, -4, 10, 'reflect') +
        (11419 / 102918816)
        * _stencil_shift(halo, -9, -4, 10, 'reflect') +
        (-487121 / 411675264)
        * _stencil_shift(halo, -8, -4, 10, 'reflect') +
        (5663 / 700128)
        * _stencil_shift(halo, -7, -4, 10, 'reflect') +
        (-1933049 / 48432384)
        * _stencil_shift(halo, -6, -4, 10, 'reflect') +
        (9587629 / 63063000)
        * _stencil_shift(halo, -5, -4, 10, 'reflect') +
        (-1888949 / 4036032)
        * _stencil_shift(halo, -4, -4, 10, 'reflect') +
        (1827209 / 1513512)
        * _stencil_shift(halo, -3, -4, 10, 'reflect') +
        (-1650809 / 620928)
        * _stencil_shift(halo, -2, -4, 10, 'reflect') +
        (698249 / 232848)
        * _stencil_shift(halo, -1, -4, 10, 'reflect') +
        (-698249 / 232848)
        * _stencil_shift(halo, 1, -4, 10, 'reflect') +
        (1650809 / 620928)
        * _stencil_shift(halo, 2, -4, 10, 'reflect') +
        (-1827209 / 1513512)
        * _stencil_shift(halo, 3, -4, 10, 'reflect') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -4, 10, 'reflect') +
        (-9587629 / 63063000)
        * _stencil_shift(halo, 5, -4, 10, 'reflect') +
        (1933049 / 48432384)
        * _stencil_shift(halo, 6, -4, 10, 'reflect') +
        (-5663 / 700128)
        * _stencil_shift(halo, 7, -4, 10, 'reflect') +
        (487121 / 411675264)
        * _stencil_shift(halo, 8, -4, 10, 'reflect') +
        (-11419 / 102918816)
        * _stencil_shift(halo, 9, -4, 10, 'reflect') +
        (514639 / 102918816000)
        * _stencil_shift(halo, 10, -4, 10, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 18, -4, 'reflect'] = _fd_d3_a18_axis4_reflect


def _fd_d3_a18_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 18, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 10, 'periodic', 3)
    result = (
        (-514639 / 102918816000)
        * _stencil_shift(halo, -10, -3, 10, 'periodic') +
        (11419 / 102918816)
        * _stencil_shift(halo, -9, -3, 10, 'periodic') +
        (-487121 / 411675264)
        * _stencil_shift(halo, -8, -3, 10, 'periodic') +
        (5663 / 700128)
        * _stencil_shift(halo, -7, -3, 10, 'periodic') +
        (-1933049 / 48432384)
        * _stencil_shift(halo, -6, -3, 10, 'periodic') +
        (9587629 / 63063000)
        * _stencil_shift(halo, -5, -3, 10, 'periodic') +
        (-1888949 / 4036032)
        * _stencil_shift(halo, -4, -3, 10, 'periodic') +
        (1827209 / 1513512)
        * _stencil_shift(halo, -3, -3, 10, 'periodic') +
        (-1650809 / 620928)
        * _stencil_shift(halo, -2, -3, 10, 'periodic') +
        (698249 / 232848)
        * _stencil_shift(halo, -1, -3, 10, 'periodic') +
        (-698249 / 232848)
        * _stencil_shift(halo, 1, -3, 10, 'periodic') +
        (1650809 / 620928)
        * _stencil_shift(halo, 2, -3, 10, 'periodic') +
        (-1827209 / 1513512)
        * _stencil_shift(halo, 3, -3, 10, 'periodic') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -3, 10, 'periodic') +
        (-9587629 / 63063000)
        * _stencil_shift(halo, 5, -3, 10, 'periodic') +
        (1933049 / 48432384)
        * _stencil_shift(halo, 6, -3, 10, 'periodic') +
        (-5663 / 700128)
        * _stencil_shift(halo, 7, -3, 10, 'periodic') +
        (487121 / 411675264)
        * _stencil_shift(halo, 8, -3, 10, 'periodic') +
        (-11419 / 102918816)
        * _stencil_shift(halo, 9, -3, 10, 'periodic') +
        (514639 / 102918816000)
        * _stencil_shift(halo, 10, -3, 10, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 18, -3, 'periodic'] = _fd_d3_a18_axis3_periodic


def _fd_d3_a18_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 18, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 10, 'zero', 3)
    result = (
        (-514639 / 102918816000)
        * _stencil_shift(halo, -10, -3, 10, 'zero') +
        (11419 / 102918816)
        * _stencil_shift(halo, -9, -3, 10, 'zero') +
        (-487121 / 411675264)
        * _stencil_shift(halo, -8, -3, 10, 'zero') +
        (5663 / 700128)
        * _stencil_shift(halo, -7, -3, 10, 'zero') +
        (-1933049 / 48432384)
        * _stencil_shift(halo, -6, -3, 10, 'zero') +
        (9587629 / 63063000)
        * _stencil_shift(halo, -5, -3, 10, 'zero') +
        (-1888949 / 4036032)
        * _stencil_shift(halo, -4, -3, 10, 'zero') +
        (1827209 / 1513512)
        * _stencil_shift(halo, -3, -3, 10, 'zero') +
        (-1650809 / 620928)
        * _stencil_shift(halo, -2, -3, 10, 'zero') +
        (698249 / 232848)
        * _stencil_shift(halo, -1, -3, 10, 'zero') +
        (-698249 / 232848)
        * _stencil_shift(halo, 1, -3, 10, 'zero') +
        (1650809 / 620928)
        * _stencil_shift(halo, 2, -3, 10, 'zero') +
        (-1827209 / 1513512)
        * _stencil_shift(halo, 3, -3, 10, 'zero') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -3, 10, 'zero') +
        (-9587629 / 63063000)
        * _stencil_shift(halo, 5, -3, 10, 'zero') +
        (1933049 / 48432384)
        * _stencil_shift(halo, 6, -3, 10, 'zero') +
        (-5663 / 700128)
        * _stencil_shift(halo, 7, -3, 10, 'zero') +
        (487121 / 411675264)
        * _stencil_shift(halo, 8, -3, 10, 'zero') +
        (-11419 / 102918816)
        * _stencil_shift(halo, 9, -3, 10, 'zero') +
        (514639 / 102918816000)
        * _stencil_shift(halo, 10, -3, 10, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 18, -3, 'zero'] = _fd_d3_a18_axis3_zero


def _fd_d3_a18_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 18, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 10, 'reflect', 3)
    result = (
        (-514639 / 102918816000)
        * _stencil_shift(halo, -10, -3, 10, 'reflect') +
        (11419 / 102918816)
        * _stencil_shift(halo, -9, -3, 10, 'reflect') +
        (-487121 / 411675264)
        * _stencil_shift(halo, -8, -3, 10, 'reflect') +
        (5663 / 700128)
        * _stencil_shift(halo, -7, -3, 10, 'reflect') +
        (-1933049 / 48432384)
        * _stencil_shift(halo, -6, -3, 10, 'reflect') +
        (9587629 / 63063000)
        * _stencil_shift(halo, -5, -3, 10, 'reflect') +
        (-1888949 / 4036032)
        * _stencil_shift(halo, -4, -3, 10, 'reflect') +
        (1827209 / 1513512)
        * _stencil_shift(halo, -3, -3, 10, 'reflect') +
        (-1650809 / 620928)
        * _stencil_shift(halo, -2, -3, 10, 'reflect') +
        (698249 / 232848)
        * _stencil_shift(halo, -1, -3, 10, 'reflect') +
        (-698249 / 232848)
        * _stencil_shift(halo, 1, -3, 10, 'reflect') +
        (1650809 / 620928)
        * _stencil_shift(halo, 2, -3, 10, 'reflect') +
        (-1827209 / 1513512)
        * _stencil_shift(halo, 3, -3, 10, 'reflect') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -3, 10, 'reflect') +
        (-9587629 / 63063000)
        * _stencil_shift(halo, 5, -3, 10, 'reflect') +
        (1933049 / 48432384)
        * _stencil_shift(halo, 6, -3, 10, 'reflect') +
        (-5663 / 700128)
        * _stencil_shift(halo, 7, -3, 10, 'reflect') +
        (487121 / 411675264)
        * _stencil_shift(halo, 8, -3, 10, 'reflect') +
        (-11419 / 102918816)
        * _stencil_shift(halo, 9, -3, 10, 'reflect') +
        (514639 / 102918816000)
        * _stencil_shift(halo, 10, -3, 10, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 18, -3, 'reflect'] = _fd_d3_a18_axis3_reflect


def _fd_d3_a18_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 18, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 10, 'periodic', 3)
    result = (
        (-514639 / 102918816000)
        * _stencil_shift(halo, -10, -2, 10, 'periodic') +
        (11419 / 102918816)
        * _stencil_shift(halo, -9, -2, 10, 'periodic') +
        (-487121 / 411675264)
        * _stencil_shift(halo, -8, -2, 10, 'periodic') +
        (5663 / 700128)
        * _stencil_shift(halo, -7, -2, 10, 'periodic') +
        (-1933049 / 48432384)
        * _stencil_shift(halo, -6, -2, 10, 'periodic') +
        (9587629 / 63063000)
        * _stencil_shift(halo, -5, -2, 10, 'periodic') +
        (-1888949 / 4036032)
        * _stencil_shift(halo, -4, -2, 10, 'periodic') +
        (1827209 / 1513512)
        * _stencil_shift(halo, -3, -2, 10, 'periodic') +
        (-1650809 / 620928)
        * _stencil_shift(halo, -2, -2, 10, 'periodic') +
        (698249 / 232848)
        * _stencil_shift(halo, -1, -2, 10, 'periodic') +
        (-698249 / 232848)
        * _stencil_shift(halo, 1, -2, 10, 'periodic') +
        (1650809 / 620928)
        * _stencil_shift(halo, 2, -2, 10, 'periodic') +
        (-1827209 / 1513512)
        * _stencil_shift(halo, 3, -2, 10, 'periodic') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -2, 10, 'periodic') +
        (-9587629 / 63063000)
        * _stencil_shift(halo, 5, -2, 10, 'periodic') +
        (1933049 / 48432384)
        * _stencil_shift(halo, 6, -2, 10, 'periodic') +
        (-5663 / 700128)
        * _stencil_shift(halo, 7, -2, 10, 'periodic') +
        (487121 / 411675264)
        * _stencil_shift(halo, 8, -2, 10, 'periodic') +
        (-11419 / 102918816)
        * _stencil_shift(halo, 9, -2, 10, 'periodic') +
        (514639 / 102918816000)
        * _stencil_shift(halo, 10, -2, 10, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 18, -2, 'periodic'] = _fd_d3_a18_axis2_periodic


def _fd_d3_a18_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 18, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 10, 'zero', 3)
    result = (
        (-514639 / 102918816000)
        * _stencil_shift(halo, -10, -2, 10, 'zero') +
        (11419 / 102918816)
        * _stencil_shift(halo, -9, -2, 10, 'zero') +
        (-487121 / 411675264)
        * _stencil_shift(halo, -8, -2, 10, 'zero') +
        (5663 / 700128)
        * _stencil_shift(halo, -7, -2, 10, 'zero') +
        (-1933049 / 48432384)
        * _stencil_shift(halo, -6, -2, 10, 'zero') +
        (9587629 / 63063000)
        * _stencil_shift(halo, -5, -2, 10, 'zero') +
        (-1888949 / 4036032)
        * _stencil_shift(halo, -4, -2, 10, 'zero') +
        (1827209 / 1513512)
        * _stencil_shift(halo, -3, -2, 10, 'zero') +
        (-1650809 / 620928)
        * _stencil_shift(halo, -2, -2, 10, 'zero') +
        (698249 / 232848)
        * _stencil_shift(halo, -1, -2, 10, 'zero') +
        (-698249 / 232848)
        * _stencil_shift(halo, 1, -2, 10, 'zero') +
        (1650809 / 620928)
        * _stencil_shift(halo, 2, -2, 10, 'zero') +
        (-1827209 / 1513512)
        * _stencil_shift(halo, 3, -2, 10, 'zero') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -2, 10, 'zero') +
        (-9587629 / 63063000)
        * _stencil_shift(halo, 5, -2, 10, 'zero') +
        (1933049 / 48432384)
        * _stencil_shift(halo, 6, -2, 10, 'zero') +
        (-5663 / 700128)
        * _stencil_shift(halo, 7, -2, 10, 'zero') +
        (487121 / 411675264)
        * _stencil_shift(halo, 8, -2, 10, 'zero') +
        (-11419 / 102918816)
        * _stencil_shift(halo, 9, -2, 10, 'zero') +
        (514639 / 102918816000)
        * _stencil_shift(halo, 10, -2, 10, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 18, -2, 'zero'] = _fd_d3_a18_axis2_zero


def _fd_d3_a18_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 18, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 10, 'reflect', 3)
    result = (
        (-514639 / 102918816000)
        * _stencil_shift(halo, -10, -2, 10, 'reflect') +
        (11419 / 102918816)
        * _stencil_shift(halo, -9, -2, 10, 'reflect') +
        (-487121 / 411675264)
        * _stencil_shift(halo, -8, -2, 10, 'reflect') +
        (5663 / 700128)
        * _stencil_shift(halo, -7, -2, 10, 'reflect') +
        (-1933049 / 48432384)
        * _stencil_shift(halo, -6, -2, 10, 'reflect') +
        (9587629 / 63063000)
        * _stencil_shift(halo, -5, -2, 10, 'reflect') +
        (-1888949 / 4036032)
        * _stencil_shift(halo, -4, -2, 10, 'reflect') +
        (1827209 / 1513512)
        * _stencil_shift(halo, -3, -2, 10, 'reflect') +
        (-1650809 / 620928)
        * _stencil_shift(halo, -2, -2, 10, 'reflect') +
        (698249 / 232848)
        * _stencil_shift(halo, -1, -2, 10, 'reflect') +
        (-698249 / 232848)
        * _stencil_shift(halo, 1, -2, 10, 'reflect') +
        (1650809 / 620928)
        * _stencil_shift(halo, 2, -2, 10, 'reflect') +
        (-1827209 / 1513512)
        * _stencil_shift(halo, 3, -2, 10, 'reflect') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -2, 10, 'reflect') +
        (-9587629 / 63063000)
        * _stencil_shift(halo, 5, -2, 10, 'reflect') +
        (1933049 / 48432384)
        * _stencil_shift(halo, 6, -2, 10, 'reflect') +
        (-5663 / 700128)
        * _stencil_shift(halo, 7, -2, 10, 'reflect') +
        (487121 / 411675264)
        * _stencil_shift(halo, 8, -2, 10, 'reflect') +
        (-11419 / 102918816)
        * _stencil_shift(halo, 9, -2, 10, 'reflect') +
        (514639 / 102918816000)
        * _stencil_shift(halo, 10, -2, 10, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 18, -2, 'reflect'] = _fd_d3_a18_axis2_reflect


def _fd_d3_a18_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 18, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 10, 'periodic', 3)
    result = (
        (-514639 / 102918816000)
        * _stencil_shift(halo, -10, -1, 10, 'periodic') +
        (11419 / 102918816)
        * _stencil_shift(halo, -9, -1, 10, 'periodic') +
        (-487121 / 411675264)
        * _stencil_shift(halo, -8, -1, 10, 'periodic') +
        (5663 / 700128)
        * _stencil_shift(halo, -7, -1, 10, 'periodic') +
        (-1933049 / 48432384)
        * _stencil_shift(halo, -6, -1, 10, 'periodic') +
        (9587629 / 63063000)
        * _stencil_shift(halo, -5, -1, 10, 'periodic') +
        (-1888949 / 4036032)
        * _stencil_shift(halo, -4, -1, 10, 'periodic') +
        (1827209 / 1513512)
        * _stencil_shift(halo, -3, -1, 10, 'periodic') +
        (-1650809 / 620928)
        * _stencil_shift(halo, -2, -1, 10, 'periodic') +
        (698249 / 232848)
        * _stencil_shift(halo, -1, -1, 10, 'periodic') +
        (-698249 / 232848)
        * _stencil_shift(halo, 1, -1, 10, 'periodic') +
        (1650809 / 620928)
        * _stencil_shift(halo, 2, -1, 10, 'periodic') +
        (-1827209 / 1513512)
        * _stencil_shift(halo, 3, -1, 10, 'periodic') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -1, 10, 'periodic') +
        (-9587629 / 63063000)
        * _stencil_shift(halo, 5, -1, 10, 'periodic') +
        (1933049 / 48432384)
        * _stencil_shift(halo, 6, -1, 10, 'periodic') +
        (-5663 / 700128)
        * _stencil_shift(halo, 7, -1, 10, 'periodic') +
        (487121 / 411675264)
        * _stencil_shift(halo, 8, -1, 10, 'periodic') +
        (-11419 / 102918816)
        * _stencil_shift(halo, 9, -1, 10, 'periodic') +
        (514639 / 102918816000)
        * _stencil_shift(halo, 10, -1, 10, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 18, -1, 'periodic'] = _fd_d3_a18_axis1_periodic


def _fd_d3_a18_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 18, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 10, 'zero', 3)
    result = (
        (-514639 / 102918816000)
        * _stencil_shift(halo, -10, -1, 10, 'zero') +
        (11419 / 102918816)
        * _stencil_shift(halo, -9, -1, 10, 'zero') +
        (-487121 / 411675264)
        * _stencil_shift(halo, -8, -1, 10, 'zero') +
        (5663 / 700128)
        * _stencil_shift(halo, -7, -1, 10, 'zero') +
        (-1933049 / 48432384)
        * _stencil_shift(halo, -6, -1, 10, 'zero') +
        (9587629 / 63063000)
        * _stencil_shift(halo, -5, -1, 10, 'zero') +
        (-1888949 / 4036032)
        * _stencil_shift(halo, -4, -1, 10, 'zero') +
        (1827209 / 1513512)
        * _stencil_shift(halo, -3, -1, 10, 'zero') +
        (-1650809 / 620928)
        * _stencil_shift(halo, -2, -1, 10, 'zero') +
        (698249 / 232848)
        * _stencil_shift(halo, -1, -1, 10, 'zero') +
        (-698249 / 232848)
        * _stencil_shift(halo, 1, -1, 10, 'zero') +
        (1650809 / 620928)
        * _stencil_shift(halo, 2, -1, 10, 'zero') +
        (-1827209 / 1513512)
        * _stencil_shift(halo, 3, -1, 10, 'zero') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -1, 10, 'zero') +
        (-9587629 / 63063000)
        * _stencil_shift(halo, 5, -1, 10, 'zero') +
        (1933049 / 48432384)
        * _stencil_shift(halo, 6, -1, 10, 'zero') +
        (-5663 / 700128)
        * _stencil_shift(halo, 7, -1, 10, 'zero') +
        (487121 / 411675264)
        * _stencil_shift(halo, 8, -1, 10, 'zero') +
        (-11419 / 102918816)
        * _stencil_shift(halo, 9, -1, 10, 'zero') +
        (514639 / 102918816000)
        * _stencil_shift(halo, 10, -1, 10, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 18, -1, 'zero'] = _fd_d3_a18_axis1_zero


def _fd_d3_a18_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 18, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 10, 'reflect', 3)
    result = (
        (-514639 / 102918816000)
        * _stencil_shift(halo, -10, -1, 10, 'reflect') +
        (11419 / 102918816)
        * _stencil_shift(halo, -9, -1, 10, 'reflect') +
        (-487121 / 411675264)
        * _stencil_shift(halo, -8, -1, 10, 'reflect') +
        (5663 / 700128)
        * _stencil_shift(halo, -7, -1, 10, 'reflect') +
        (-1933049 / 48432384)
        * _stencil_shift(halo, -6, -1, 10, 'reflect') +
        (9587629 / 63063000)
        * _stencil_shift(halo, -5, -1, 10, 'reflect') +
        (-1888949 / 4036032)
        * _stencil_shift(halo, -4, -1, 10, 'reflect') +
        (1827209 / 1513512)
        * _stencil_shift(halo, -3, -1, 10, 'reflect') +
        (-1650809 / 620928)
        * _stencil_shift(halo, -2, -1, 10, 'reflect') +
        (698249 / 232848)
        * _stencil_shift(halo, -1, -1, 10, 'reflect') +
        (-698249 / 232848)
        * _stencil_shift(halo, 1, -1, 10, 'reflect') +
        (1650809 / 620928)
        * _stencil_shift(halo, 2, -1, 10, 'reflect') +
        (-1827209 / 1513512)
        * _stencil_shift(halo, 3, -1, 10, 'reflect') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -1, 10, 'reflect') +
        (-9587629 / 63063000)
        * _stencil_shift(halo, 5, -1, 10, 'reflect') +
        (1933049 / 48432384)
        * _stencil_shift(halo, 6, -1, 10, 'reflect') +
        (-5663 / 700128)
        * _stencil_shift(halo, 7, -1, 10, 'reflect') +
        (487121 / 411675264)
        * _stencil_shift(halo, 8, -1, 10, 'reflect') +
        (-11419 / 102918816)
        * _stencil_shift(halo, 9, -1, 10, 'reflect') +
        (514639 / 102918816000)
        * _stencil_shift(halo, 10, -1, 10, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 18, -1, 'reflect'] = _fd_d3_a18_axis1_reflect


STENCIL_MOMENTS[3, 20] = (
    (-11, 178939, 149325845760),
    (-10, -1189505461, 41064607584000),
    (-9, 1552553, 4601076480),
    (-8, -268141, 106178688),
    (-7, 4822481, 352864512),
    (-6, -235169009, 4116752640),
    (-5, 89727193, 465696000),
    (-4, -229832909, 423783360),
    (-3, 222362369, 169513344),
    (-2, -201017969, 72648576),
    (-1, 85758209, 27941760),
    (0, 0, 1),
    (1, -85758209, 27941760),
    (2, 201017969, 72648576),
    (3, -222362369, 169513344),
    (4, 229832909, 423783360),
    (5, -89727193, 465696000),
    (6, 235169009, 4116752640),
    (7, -4822481, 352864512),
    (8, 268141, 106178688),
    (9, -1552553, 4601076480),
    (10, 1189505461, 41064607584000),
    (11, -178939, 149325845760),
)

def _fd_d3_a20_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 20, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 11, 'periodic', 3)
    result = (
        (178939 / 149325845760)
        * _stencil_shift(halo, -11, -4, 11, 'periodic') +
        (-1189505461 / 41064607584000)
        * _stencil_shift(halo, -10, -4, 11, 'periodic') +
        (1552553 / 4601076480)
        * _stencil_shift(halo, -9, -4, 11, 'periodic') +
        (-268141 / 106178688)
        * _stencil_shift(halo, -8, -4, 11, 'periodic') +
        (4822481 / 352864512)
        * _stencil_shift(halo, -7, -4, 11, 'periodic') +
        (-235169009 / 4116752640)
        * _stencil_shift(halo, -6, -4, 11, 'periodic') +
        (89727193 / 465696000)
        * _stencil_shift(halo, -5, -4, 11, 'periodic') +
        (-229832909 / 423783360)
        * _stencil_shift(halo, -4, -4, 11, 'periodic') +
        (222362369 / 169513344)
        * _stencil_shift(halo, -3, -4, 11, 'periodic') +
        (-201017969 / 72648576)
        * _stencil_shift(halo, -2, -4, 11, 'periodic') +
        (85758209 / 27941760)
        * _stencil_shift(halo, -1, -4, 11, 'periodic') +
        (-85758209 / 27941760)
        * _stencil_shift(halo, 1, -4, 11, 'periodic') +
        (201017969 / 72648576)
        * _stencil_shift(halo, 2, -4, 11, 'periodic') +
        (-222362369 / 169513344)
        * _stencil_shift(halo, 3, -4, 11, 'periodic') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -4, 11, 'periodic') +
        (-89727193 / 465696000)
        * _stencil_shift(halo, 5, -4, 11, 'periodic') +
        (235169009 / 4116752640)
        * _stencil_shift(halo, 6, -4, 11, 'periodic') +
        (-4822481 / 352864512)
        * _stencil_shift(halo, 7, -4, 11, 'periodic') +
        (268141 / 106178688)
        * _stencil_shift(halo, 8, -4, 11, 'periodic') +
        (-1552553 / 4601076480)
        * _stencil_shift(halo, 9, -4, 11, 'periodic') +
        (1189505461 / 41064607584000)
        * _stencil_shift(halo, 10, -4, 11, 'periodic') +
        (-178939 / 149325845760)
        * _stencil_shift(halo, 11, -4, 11, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 20, -4, 'periodic'] = _fd_d3_a20_axis4_periodic


def _fd_d3_a20_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 20, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 11, 'zero', 3)
    result = (
        (178939 / 149325845760)
        * _stencil_shift(halo, -11, -4, 11, 'zero') +
        (-1189505461 / 41064607584000)
        * _stencil_shift(halo, -10, -4, 11, 'zero') +
        (1552553 / 4601076480)
        * _stencil_shift(halo, -9, -4, 11, 'zero') +
        (-268141 / 106178688)
        * _stencil_shift(halo, -8, -4, 11, 'zero') +
        (4822481 / 352864512)
        * _stencil_shift(halo, -7, -4, 11, 'zero') +
        (-235169009 / 4116752640)
        * _stencil_shift(halo, -6, -4, 11, 'zero') +
        (89727193 / 465696000)
        * _stencil_shift(halo, -5, -4, 11, 'zero') +
        (-229832909 / 423783360)
        * _stencil_shift(halo, -4, -4, 11, 'zero') +
        (222362369 / 169513344)
        * _stencil_shift(halo, -3, -4, 11, 'zero') +
        (-201017969 / 72648576)
        * _stencil_shift(halo, -2, -4, 11, 'zero') +
        (85758209 / 27941760)
        * _stencil_shift(halo, -1, -4, 11, 'zero') +
        (-85758209 / 27941760)
        * _stencil_shift(halo, 1, -4, 11, 'zero') +
        (201017969 / 72648576)
        * _stencil_shift(halo, 2, -4, 11, 'zero') +
        (-222362369 / 169513344)
        * _stencil_shift(halo, 3, -4, 11, 'zero') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -4, 11, 'zero') +
        (-89727193 / 465696000)
        * _stencil_shift(halo, 5, -4, 11, 'zero') +
        (235169009 / 4116752640)
        * _stencil_shift(halo, 6, -4, 11, 'zero') +
        (-4822481 / 352864512)
        * _stencil_shift(halo, 7, -4, 11, 'zero') +
        (268141 / 106178688)
        * _stencil_shift(halo, 8, -4, 11, 'zero') +
        (-1552553 / 4601076480)
        * _stencil_shift(halo, 9, -4, 11, 'zero') +
        (1189505461 / 41064607584000)
        * _stencil_shift(halo, 10, -4, 11, 'zero') +
        (-178939 / 149325845760)
        * _stencil_shift(halo, 11, -4, 11, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 20, -4, 'zero'] = _fd_d3_a20_axis4_zero


def _fd_d3_a20_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 20, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 11, 'reflect', 3)
    result = (
        (178939 / 149325845760)
        * _stencil_shift(halo, -11, -4, 11, 'reflect') +
        (-1189505461 / 41064607584000)
        * _stencil_shift(halo, -10, -4, 11, 'reflect') +
        (1552553 / 4601076480)
        * _stencil_shift(halo, -9, -4, 11, 'reflect') +
        (-268141 / 106178688)
        * _stencil_shift(halo, -8, -4, 11, 'reflect') +
        (4822481 / 352864512)
        * _stencil_shift(halo, -7, -4, 11, 'reflect') +
        (-235169009 / 4116752640)
        * _stencil_shift(halo, -6, -4, 11, 'reflect') +
        (89727193 / 465696000)
        * _stencil_shift(halo, -5, -4, 11, 'reflect') +
        (-229832909 / 423783360)
        * _stencil_shift(halo, -4, -4, 11, 'reflect') +
        (222362369 / 169513344)
        * _stencil_shift(halo, -3, -4, 11, 'reflect') +
        (-201017969 / 72648576)
        * _stencil_shift(halo, -2, -4, 11, 'reflect') +
        (85758209 / 27941760)
        * _stencil_shift(halo, -1, -4, 11, 'reflect') +
        (-85758209 / 27941760)
        * _stencil_shift(halo, 1, -4, 11, 'reflect') +
        (201017969 / 72648576)
        * _stencil_shift(halo, 2, -4, 11, 'reflect') +
        (-222362369 / 169513344)
        * _stencil_shift(halo, 3, -4, 11, 'reflect') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -4, 11, 'reflect') +
        (-89727193 / 465696000)
        * _stencil_shift(halo, 5, -4, 11, 'reflect') +
        (235169009 / 4116752640)
        * _stencil_shift(halo, 6, -4, 11, 'reflect') +
        (-4822481 / 352864512)
        * _stencil_shift(halo, 7, -4, 11, 'reflect') +
        (268141 / 106178688)
        * _stencil_shift(halo, 8, -4, 11, 'reflect') +
        (-1552553 / 4601076480)
        * _stencil_shift(halo, 9, -4, 11, 'reflect') +
        (1189505461 / 41064607584000)
        * _stencil_shift(halo, 10, -4, 11, 'reflect') +
        (-178939 / 149325845760)
        * _stencil_shift(halo, 11, -4, 11, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 20, -4, 'reflect'] = _fd_d3_a20_axis4_reflect


def _fd_d3_a20_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 20, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 11, 'periodic', 3)
    result = (
        (178939 / 149325845760)
        * _stencil_shift(halo, -11, -3, 11, 'periodic') +
        (-1189505461 / 41064607584000)
        * _stencil_shift(halo, -10, -3, 11, 'periodic') +
        (1552553 / 4601076480)
        * _stencil_shift(halo, -9, -3, 11, 'periodic') +
        (-268141 / 106178688)
        * _stencil_shift(halo, -8, -3, 11, 'periodic') +
        (4822481 / 352864512)
        * _stencil_shift(halo, -7, -3, 11, 'periodic') +
        (-235169009 / 4116752640)
        * _stencil_shift(halo, -6, -3, 11, 'periodic') +
        (89727193 / 465696000)
        * _stencil_shift(halo, -5, -3, 11, 'periodic') +
        (-229832909 / 423783360)
        * _stencil_shift(halo, -4, -3, 11, 'periodic') +
        (222362369 / 169513344)
        * _stencil_shift(halo, -3, -3, 11, 'periodic') +
        (-201017969 / 72648576)
        * _stencil_shift(halo, -2, -3, 11, 'periodic') +
        (85758209 / 27941760)
        * _stencil_shift(halo, -1, -3, 11, 'periodic') +
        (-85758209 / 27941760)
        * _stencil_shift(halo, 1, -3, 11, 'periodic') +
        (201017969 / 72648576)
        * _stencil_shift(halo, 2, -3, 11, 'periodic') +
        (-222362369 / 169513344)
        * _stencil_shift(halo, 3, -3, 11, 'periodic') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -3, 11, 'periodic') +
        (-89727193 / 465696000)
        * _stencil_shift(halo, 5, -3, 11, 'periodic') +
        (235169009 / 4116752640)
        * _stencil_shift(halo, 6, -3, 11, 'periodic') +
        (-4822481 / 352864512)
        * _stencil_shift(halo, 7, -3, 11, 'periodic') +
        (268141 / 106178688)
        * _stencil_shift(halo, 8, -3, 11, 'periodic') +
        (-1552553 / 4601076480)
        * _stencil_shift(halo, 9, -3, 11, 'periodic') +
        (1189505461 / 41064607584000)
        * _stencil_shift(halo, 10, -3, 11, 'periodic') +
        (-178939 / 149325845760)
        * _stencil_shift(halo, 11, -3, 11, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 20, -3, 'periodic'] = _fd_d3_a20_axis3_periodic


def _fd_d3_a20_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 20, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 11, 'zero', 3)
    result = (
        (178939 / 149325845760)
        * _stencil_shift(halo, -11, -3, 11, 'zero') +
        (-1189505461 / 41064607584000)
        * _stencil_shift(halo, -10, -3, 11, 'zero') +
        (1552553 / 4601076480)
        * _stencil_shift(halo, -9, -3, 11, 'zero') +
        (-268141 / 106178688)
        * _stencil_shift(halo, -8, -3, 11, 'zero') +
        (4822481 / 352864512)
        * _stencil_shift(halo, -7, -3, 11, 'zero') +
        (-235169009 / 4116752640)
        * _stencil_shift(halo, -6, -3, 11, 'zero') +
        (89727193 / 465696000)
        * _stencil_shift(halo, -5, -3, 11, 'zero') +
        (-229832909 / 423783360)
        * _stencil_shift(halo, -4, -3, 11, 'zero') +
        (222362369 / 169513344)
        * _stencil_shift(halo, -3, -3, 11, 'zero') +
        (-201017969 / 72648576)
        * _stencil_shift(halo, -2, -3, 11, 'zero') +
        (85758209 / 27941760)
        * _stencil_shift(halo, -1, -3, 11, 'zero') +
        (-85758209 / 27941760)
        * _stencil_shift(halo, 1, -3, 11, 'zero') +
        (201017969 / 72648576)
        * _stencil_shift(halo, 2, -3, 11, 'zero') +
        (-222362369 / 169513344)
        * _stencil_shift(halo, 3, -3, 11, 'zero') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -3, 11, 'zero') +
        (-89727193 / 465696000)
        * _stencil_shift(halo, 5, -3, 11, 'zero') +
        (235169009 / 4116752640)
        * _stencil_shift(halo, 6, -3, 11, 'zero') +
        (-4822481 / 352864512)
        * _stencil_shift(halo, 7, -3, 11, 'zero') +
        (268141 / 106178688)
        * _stencil_shift(halo, 8, -3, 11, 'zero') +
        (-1552553 / 4601076480)
        * _stencil_shift(halo, 9, -3, 11, 'zero') +
        (1189505461 / 41064607584000)
        * _stencil_shift(halo, 10, -3, 11, 'zero') +
        (-178939 / 149325845760)
        * _stencil_shift(halo, 11, -3, 11, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 20, -3, 'zero'] = _fd_d3_a20_axis3_zero


def _fd_d3_a20_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 20, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 11, 'reflect', 3)
    result = (
        (178939 / 149325845760)
        * _stencil_shift(halo, -11, -3, 11, 'reflect') +
        (-1189505461 / 41064607584000)
        * _stencil_shift(halo, -10, -3, 11, 'reflect') +
        (1552553 / 4601076480)
        * _stencil_shift(halo, -9, -3, 11, 'reflect') +
        (-268141 / 106178688)
        * _stencil_shift(halo, -8, -3, 11, 'reflect') +
        (4822481 / 352864512)
        * _stencil_shift(halo, -7, -3, 11, 'reflect') +
        (-235169009 / 4116752640)
        * _stencil_shift(halo, -6, -3, 11, 'reflect') +
        (89727193 / 465696000)
        * _stencil_shift(halo, -5, -3, 11, 'reflect') +
        (-229832909 / 423783360)
        * _stencil_shift(halo, -4, -3, 11, 'reflect') +
        (222362369 / 169513344)
        * _stencil_shift(halo, -3, -3, 11, 'reflect') +
        (-201017969 / 72648576)
        * _stencil_shift(halo, -2, -3, 11, 'reflect') +
        (85758209 / 27941760)
        * _stencil_shift(halo, -1, -3, 11, 'reflect') +
        (-85758209 / 27941760)
        * _stencil_shift(halo, 1, -3, 11, 'reflect') +
        (201017969 / 72648576)
        * _stencil_shift(halo, 2, -3, 11, 'reflect') +
        (-222362369 / 169513344)
        * _stencil_shift(halo, 3, -3, 11, 'reflect') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -3, 11, 'reflect') +
        (-89727193 / 465696000)
        * _stencil_shift(halo, 5, -3, 11, 'reflect') +
        (235169009 / 4116752640)
        * _stencil_shift(halo, 6, -3, 11, 'reflect') +
        (-4822481 / 352864512)
        * _stencil_shift(halo, 7, -3, 11, 'reflect') +
        (268141 / 106178688)
        * _stencil_shift(halo, 8, -3, 11, 'reflect') +
        (-1552553 / 4601076480)
        * _stencil_shift(halo, 9, -3, 11, 'reflect') +
        (1189505461 / 41064607584000)
        * _stencil_shift(halo, 10, -3, 11, 'reflect') +
        (-178939 / 149325845760)
        * _stencil_shift(halo, 11, -3, 11, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 20, -3, 'reflect'] = _fd_d3_a20_axis3_reflect


def _fd_d3_a20_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 20, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 11, 'periodic', 3)
    result = (
        (178939 / 149325845760)
        * _stencil_shift(halo, -11, -2, 11, 'periodic') +
        (-1189505461 / 41064607584000)
        * _stencil_shift(halo, -10, -2, 11, 'periodic') +
        (1552553 / 4601076480)
        * _stencil_shift(halo, -9, -2, 11, 'periodic') +
        (-268141 / 106178688)
        * _stencil_shift(halo, -8, -2, 11, 'periodic') +
        (4822481 / 352864512)
        * _stencil_shift(halo, -7, -2, 11, 'periodic') +
        (-235169009 / 4116752640)
        * _stencil_shift(halo, -6, -2, 11, 'periodic') +
        (89727193 / 465696000)
        * _stencil_shift(halo, -5, -2, 11, 'periodic') +
        (-229832909 / 423783360)
        * _stencil_shift(halo, -4, -2, 11, 'periodic') +
        (222362369 / 169513344)
        * _stencil_shift(halo, -3, -2, 11, 'periodic') +
        (-201017969 / 72648576)
        * _stencil_shift(halo, -2, -2, 11, 'periodic') +
        (85758209 / 27941760)
        * _stencil_shift(halo, -1, -2, 11, 'periodic') +
        (-85758209 / 27941760)
        * _stencil_shift(halo, 1, -2, 11, 'periodic') +
        (201017969 / 72648576)
        * _stencil_shift(halo, 2, -2, 11, 'periodic') +
        (-222362369 / 169513344)
        * _stencil_shift(halo, 3, -2, 11, 'periodic') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -2, 11, 'periodic') +
        (-89727193 / 465696000)
        * _stencil_shift(halo, 5, -2, 11, 'periodic') +
        (235169009 / 4116752640)
        * _stencil_shift(halo, 6, -2, 11, 'periodic') +
        (-4822481 / 352864512)
        * _stencil_shift(halo, 7, -2, 11, 'periodic') +
        (268141 / 106178688)
        * _stencil_shift(halo, 8, -2, 11, 'periodic') +
        (-1552553 / 4601076480)
        * _stencil_shift(halo, 9, -2, 11, 'periodic') +
        (1189505461 / 41064607584000)
        * _stencil_shift(halo, 10, -2, 11, 'periodic') +
        (-178939 / 149325845760)
        * _stencil_shift(halo, 11, -2, 11, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 20, -2, 'periodic'] = _fd_d3_a20_axis2_periodic


def _fd_d3_a20_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 20, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 11, 'zero', 3)
    result = (
        (178939 / 149325845760)
        * _stencil_shift(halo, -11, -2, 11, 'zero') +
        (-1189505461 / 41064607584000)
        * _stencil_shift(halo, -10, -2, 11, 'zero') +
        (1552553 / 4601076480)
        * _stencil_shift(halo, -9, -2, 11, 'zero') +
        (-268141 / 106178688)
        * _stencil_shift(halo, -8, -2, 11, 'zero') +
        (4822481 / 352864512)
        * _stencil_shift(halo, -7, -2, 11, 'zero') +
        (-235169009 / 4116752640)
        * _stencil_shift(halo, -6, -2, 11, 'zero') +
        (89727193 / 465696000)
        * _stencil_shift(halo, -5, -2, 11, 'zero') +
        (-229832909 / 423783360)
        * _stencil_shift(halo, -4, -2, 11, 'zero') +
        (222362369 / 169513344)
        * _stencil_shift(halo, -3, -2, 11, 'zero') +
        (-201017969 / 72648576)
        * _stencil_shift(halo, -2, -2, 11, 'zero') +
        (85758209 / 27941760)
        * _stencil_shift(halo, -1, -2, 11, 'zero') +
        (-85758209 / 27941760)
        * _stencil_shift(halo, 1, -2, 11, 'zero') +
        (201017969 / 72648576)
        * _stencil_shift(halo, 2, -2, 11, 'zero') +
        (-222362369 / 169513344)
        * _stencil_shift(halo, 3, -2, 11, 'zero') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -2, 11, 'zero') +
        (-89727193 / 465696000)
        * _stencil_shift(halo, 5, -2, 11, 'zero') +
        (235169009 / 4116752640)
        * _stencil_shift(halo, 6, -2, 11, 'zero') +
        (-4822481 / 352864512)
        * _stencil_shift(halo, 7, -2, 11, 'zero') +
        (268141 / 106178688)
        * _stencil_shift(halo, 8, -2, 11, 'zero') +
        (-1552553 / 4601076480)
        * _stencil_shift(halo, 9, -2, 11, 'zero') +
        (1189505461 / 41064607584000)
        * _stencil_shift(halo, 10, -2, 11, 'zero') +
        (-178939 / 149325845760)
        * _stencil_shift(halo, 11, -2, 11, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 20, -2, 'zero'] = _fd_d3_a20_axis2_zero


def _fd_d3_a20_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 20, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 11, 'reflect', 3)
    result = (
        (178939 / 149325845760)
        * _stencil_shift(halo, -11, -2, 11, 'reflect') +
        (-1189505461 / 41064607584000)
        * _stencil_shift(halo, -10, -2, 11, 'reflect') +
        (1552553 / 4601076480)
        * _stencil_shift(halo, -9, -2, 11, 'reflect') +
        (-268141 / 106178688)
        * _stencil_shift(halo, -8, -2, 11, 'reflect') +
        (4822481 / 352864512)
        * _stencil_shift(halo, -7, -2, 11, 'reflect') +
        (-235169009 / 4116752640)
        * _stencil_shift(halo, -6, -2, 11, 'reflect') +
        (89727193 / 465696000)
        * _stencil_shift(halo, -5, -2, 11, 'reflect') +
        (-229832909 / 423783360)
        * _stencil_shift(halo, -4, -2, 11, 'reflect') +
        (222362369 / 169513344)
        * _stencil_shift(halo, -3, -2, 11, 'reflect') +
        (-201017969 / 72648576)
        * _stencil_shift(halo, -2, -2, 11, 'reflect') +
        (85758209 / 27941760)
        * _stencil_shift(halo, -1, -2, 11, 'reflect') +
        (-85758209 / 27941760)
        * _stencil_shift(halo, 1, -2, 11, 'reflect') +
        (201017969 / 72648576)
        * _stencil_shift(halo, 2, -2, 11, 'reflect') +
        (-222362369 / 169513344)
        * _stencil_shift(halo, 3, -2, 11, 'reflect') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -2, 11, 'reflect') +
        (-89727193 / 465696000)
        * _stencil_shift(halo, 5, -2, 11, 'reflect') +
        (235169009 / 4116752640)
        * _stencil_shift(halo, 6, -2, 11, 'reflect') +
        (-4822481 / 352864512)
        * _stencil_shift(halo, 7, -2, 11, 'reflect') +
        (268141 / 106178688)
        * _stencil_shift(halo, 8, -2, 11, 'reflect') +
        (-1552553 / 4601076480)
        * _stencil_shift(halo, 9, -2, 11, 'reflect') +
        (1189505461 / 41064607584000)
        * _stencil_shift(halo, 10, -2, 11, 'reflect') +
        (-178939 / 149325845760)
        * _stencil_shift(halo, 11, -2, 11, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 20, -2, 'reflect'] = _fd_d3_a20_axis2_reflect


def _fd_d3_a20_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 20, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 11, 'periodic', 3)
    result = (
        (178939 / 149325845760)
        * _stencil_shift(halo, -11, -1, 11, 'periodic') +
        (-1189505461 / 41064607584000)
        * _stencil_shift(halo, -10, -1, 11, 'periodic') +
        (1552553 / 4601076480)
        * _stencil_shift(halo, -9, -1, 11, 'periodic') +
        (-268141 / 106178688)
        * _stencil_shift(halo, -8, -1, 11, 'periodic') +
        (4822481 / 352864512)
        * _stencil_shift(halo, -7, -1, 11, 'periodic') +
        (-235169009 / 4116752640)
        * _stencil_shift(halo, -6, -1, 11, 'periodic') +
        (89727193 / 465696000)
        * _stencil_shift(halo, -5, -1, 11, 'periodic') +
        (-229832909 / 423783360)
        * _stencil_shift(halo, -4, -1, 11, 'periodic') +
        (222362369 / 169513344)
        * _stencil_shift(halo, -3, -1, 11, 'periodic') +
        (-201017969 / 72648576)
        * _stencil_shift(halo, -2, -1, 11, 'periodic') +
        (85758209 / 27941760)
        * _stencil_shift(halo, -1, -1, 11, 'periodic') +
        (-85758209 / 27941760)
        * _stencil_shift(halo, 1, -1, 11, 'periodic') +
        (201017969 / 72648576)
        * _stencil_shift(halo, 2, -1, 11, 'periodic') +
        (-222362369 / 169513344)
        * _stencil_shift(halo, 3, -1, 11, 'periodic') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -1, 11, 'periodic') +
        (-89727193 / 465696000)
        * _stencil_shift(halo, 5, -1, 11, 'periodic') +
        (235169009 / 4116752640)
        * _stencil_shift(halo, 6, -1, 11, 'periodic') +
        (-4822481 / 352864512)
        * _stencil_shift(halo, 7, -1, 11, 'periodic') +
        (268141 / 106178688)
        * _stencil_shift(halo, 8, -1, 11, 'periodic') +
        (-1552553 / 4601076480)
        * _stencil_shift(halo, 9, -1, 11, 'periodic') +
        (1189505461 / 41064607584000)
        * _stencil_shift(halo, 10, -1, 11, 'periodic') +
        (-178939 / 149325845760)
        * _stencil_shift(halo, 11, -1, 11, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 20, -1, 'periodic'] = _fd_d3_a20_axis1_periodic


def _fd_d3_a20_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 20, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 11, 'zero', 3)
    result = (
        (178939 / 149325845760)
        * _stencil_shift(halo, -11, -1, 11, 'zero') +
        (-1189505461 / 41064607584000)
        * _stencil_shift(halo, -10, -1, 11, 'zero') +
        (1552553 / 4601076480)
        * _stencil_shift(halo, -9, -1, 11, 'zero') +
        (-268141 / 106178688)
        * _stencil_shift(halo, -8, -1, 11, 'zero') +
        (4822481 / 352864512)
        * _stencil_shift(halo, -7, -1, 11, 'zero') +
        (-235169009 / 4116752640)
        * _stencil_shift(halo, -6, -1, 11, 'zero') +
        (89727193 / 465696000)
        * _stencil_shift(halo, -5, -1, 11, 'zero') +
        (-229832909 / 423783360)
        * _stencil_shift(halo, -4, -1, 11, 'zero') +
        (222362369 / 169513344)
        * _stencil_shift(halo, -3, -1, 11, 'zero') +
        (-201017969 / 72648576)
        * _stencil_shift(halo, -2, -1, 11, 'zero') +
        (85758209 / 27941760)
        * _stencil_shift(halo, -1, -1, 11, 'zero') +
        (-85758209 / 27941760)
        * _stencil_shift(halo, 1, -1, 11, 'zero') +
        (201017969 / 72648576)
        * _stencil_shift(halo, 2, -1, 11, 'zero') +
        (-222362369 / 169513344)
        * _stencil_shift(halo, 3, -1, 11, 'zero') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -1, 11, 'zero') +
        (-89727193 / 465696000)
        * _stencil_shift(halo, 5, -1, 11, 'zero') +
        (235169009 / 4116752640)
        * _stencil_shift(halo, 6, -1, 11, 'zero') +
        (-4822481 / 352864512)
        * _stencil_shift(halo, 7, -1, 11, 'zero') +
        (268141 / 106178688)
        * _stencil_shift(halo, 8, -1, 11, 'zero') +
        (-1552553 / 4601076480)
        * _stencil_shift(halo, 9, -1, 11, 'zero') +
        (1189505461 / 41064607584000)
        * _stencil_shift(halo, 10, -1, 11, 'zero') +
        (-178939 / 149325845760)
        * _stencil_shift(halo, 11, -1, 11, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 20, -1, 'zero'] = _fd_d3_a20_axis1_zero


def _fd_d3_a20_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 3, accuracy 20, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**3, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 11, 'reflect', 3)
    result = (
        (178939 / 149325845760)
        * _stencil_shift(halo, -11, -1, 11, 'reflect') +
        (-1189505461 / 41064607584000)
        * _stencil_shift(halo, -10, -1, 11, 'reflect') +
        (1552553 / 4601076480)
        * _stencil_shift(halo, -9, -1, 11, 'reflect') +
        (-268141 / 106178688)
        * _stencil_shift(halo, -8, -1, 11, 'reflect') +
        (4822481 / 352864512)
        * _stencil_shift(halo, -7, -1, 11, 'reflect') +
        (-235169009 / 4116752640)
        * _stencil_shift(halo, -6, -1, 11, 'reflect') +
        (89727193 / 465696000)
        * _stencil_shift(halo, -5, -1, 11, 'reflect') +
        (-229832909 / 423783360)
        * _stencil_shift(halo, -4, -1, 11, 'reflect') +
        (222362369 / 169513344)
        * _stencil_shift(halo, -3, -1, 11, 'reflect') +
        (-201017969 / 72648576)
        * _stencil_shift(halo, -2, -1, 11, 'reflect') +
        (85758209 / 27941760)
        * _stencil_shift(halo, -1, -1, 11, 'reflect') +
        (-85758209 / 27941760)
        * _stencil_shift(halo, 1, -1, 11, 'reflect') +
        (201017969 / 72648576)
        * _stencil_shift(halo, 2, -1, 11, 'reflect') +
        (-222362369 / 169513344)
        * _stencil_shift(halo, 3, -1, 11, 'reflect') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -1, 11, 'reflect') +
        (-89727193 / 465696000)
        * _stencil_shift(halo, 5, -1, 11, 'reflect') +
        (235169009 / 4116752640)
        * _stencil_shift(halo, 6, -1, 11, 'reflect') +
        (-4822481 / 352864512)
        * _stencil_shift(halo, 7, -1, 11, 'reflect') +
        (268141 / 106178688)
        * _stencil_shift(halo, 8, -1, 11, 'reflect') +
        (-1552553 / 4601076480)
        * _stencil_shift(halo, 9, -1, 11, 'reflect') +
        (1189505461 / 41064607584000)
        * _stencil_shift(halo, 10, -1, 11, 'reflect') +
        (-178939 / 149325845760)
        * _stencil_shift(halo, 11, -1, 11, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[3, 20, -1, 'reflect'] = _fd_d3_a20_axis1_reflect


STENCIL_MOMENTS[4, 2] = (
    (-2, 1, 1),
    (-1, -4, 1),
    (0, 6, 1),
    (1, -4, 1),
    (2, 1, 1),
)

def _fd_d4_a2_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 2, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 2, 'periodic', 4)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -2, -4, 2, 'periodic') +
        (-4 / 1)
        * _stencil_shift(halo, -1, -4, 2, 'periodic') +
        (6 / 1)
        * _stencil_shift(halo, 0, -4, 2, 'periodic') +
        (-4 / 1)
        * _stencil_shift(halo, 1, -4, 2, 'periodic') +
        (1 / 1)
        * _stencil_shift(halo, 2, -4, 2, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 2, -4, 'periodic'] = _fd_d4_a2_axis4_periodic


def _fd_d4_a2_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 2, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 2, 'zero', 4)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -2, -4, 2, 'zero') +
        (-4 / 1)
        * _stencil_shift(halo, -1, -4, 2, 'zero') +
        (6 / 1)
        * _stencil_shift(halo, 0, -4, 2, 'zero') +
        (-4 / 1)
        * _stencil_shift(halo, 1, -4, 2, 'zero') +
        (1 / 1)
        * _stencil_shift(halo, 2, -4, 2, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 2, -4, 'zero'] = _fd_d4_a2_axis4_zero


def _fd_d4_a2_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 2, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 2, 'reflect', 4)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -2, -4, 2, 'reflect') +
        (-4 / 1)
        * _stencil_shift(halo, -1, -4, 2, 'reflect') +
        (6 / 1)
        * _stencil_shift(halo, 0, -4, 2, 'reflect') +
        (-4 / 1)
        * _stencil_shift(halo, 1, -4, 2, 'reflect') +
        (1 / 1)
        * _stencil_shift(halo, 2, -4, 2, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 2, -4, 'reflect'] = _fd_d4_a2_axis4_reflect


def _fd_d4_a2_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 2, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 2, 'periodic', 4)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -2, -3, 2, 'periodic') +
        (-4 / 1)
        * _stencil_shift(halo, -1, -3, 2, 'periodic') +
        (6 / 1)
        * _stencil_shift(halo, 0, -3, 2, 'periodic') +
        (-4 / 1)
        * _stencil_shift(halo, 1, -3, 2, 'periodic') +
        (1 / 1)
        * _stencil_shift(halo, 2, -3, 2, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 2, -3, 'periodic'] = _fd_d4_a2_axis3_periodic


def _fd_d4_a2_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 2, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 2, 'zero', 4)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -2, -3, 2, 'zero') +
        (-4 / 1)
        * _stencil_shift(halo, -1, -3, 2, 'zero') +
        (6 / 1)
        * _stencil_shift(halo, 0, -3, 2, 'zero') +
        (-4 / 1)
        * _stencil_shift(halo, 1, -3, 2, 'zero') +
        (1 / 1)
        * _stencil_shift(halo, 2, -3, 2, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 2, -3, 'zero'] = _fd_d4_a2_axis3_zero


def _fd_d4_a2_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 2, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 2, 'reflect', 4)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -2, -3, 2, 'reflect') +
        (-4 / 1)
        * _stencil_shift(halo, -1, -3, 2, 'reflect') +
        (6 / 1)
        * _stencil_shift(halo, 0, -3, 2, 'reflect') +
        (-4 / 1)
        * _stencil_shift(halo, 1, -3, 2, 'reflect') +
        (1 / 1)
        * _stencil_shift(halo, 2, -3, 2, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 2, -3, 'reflect'] = _fd_d4_a2_axis3_reflect


def _fd_d4_a2_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 2, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 2, 'periodic', 4)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -2, -2, 2, 'periodic') +
        (-4 / 1)
        * _stencil_shift(halo, -1, -2, 2, 'periodic') +
        (6 / 1)
        * _stencil_shift(halo, 0, -2, 2, 'periodic') +
        (-4 / 1)
        * _stencil_shift(halo, 1, -2, 2, 'periodic') +
        (1 / 1)
        * _stencil_shift(halo, 2, -2, 2, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 2, -2, 'periodic'] = _fd_d4_a2_axis2_periodic


def _fd_d4_a2_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 2, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 2, 'zero', 4)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -2, -2, 2, 'zero') +
        (-4 / 1)
        * _stencil_shift(halo, -1, -2, 2, 'zero') +
        (6 / 1)
        * _stencil_shift(halo, 0, -2, 2, 'zero') +
        (-4 / 1)
        * _stencil_shift(halo, 1, -2, 2, 'zero') +
        (1 / 1)
        * _stencil_shift(halo, 2, -2, 2, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 2, -2, 'zero'] = _fd_d4_a2_axis2_zero


def _fd_d4_a2_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 2, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 2, 'reflect', 4)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -2, -2, 2, 'reflect') +
        (-4 / 1)
        * _stencil_shift(halo, -1, -2, 2, 'reflect') +
        (6 / 1)
        * _stencil_shift(halo, 0, -2, 2, 'reflect') +
        (-4 / 1)
        * _stencil_shift(halo, 1, -2, 2, 'reflect') +
        (1 / 1)
        * _stencil_shift(halo, 2, -2, 2, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 2, -2, 'reflect'] = _fd_d4_a2_axis2_reflect


def _fd_d4_a2_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 2, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 2, 'periodic', 4)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -2, -1, 2, 'periodic') +
        (-4 / 1)
        * _stencil_shift(halo, -1, -1, 2, 'periodic') +
        (6 / 1)
        * _stencil_shift(halo, 0, -1, 2, 'periodic') +
        (-4 / 1)
        * _stencil_shift(halo, 1, -1, 2, 'periodic') +
        (1 / 1)
        * _stencil_shift(halo, 2, -1, 2, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 2, -1, 'periodic'] = _fd_d4_a2_axis1_periodic


def _fd_d4_a2_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 2, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 2, 'zero', 4)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -2, -1, 2, 'zero') +
        (-4 / 1)
        * _stencil_shift(halo, -1, -1, 2, 'zero') +
        (6 / 1)
        * _stencil_shift(halo, 0, -1, 2, 'zero') +
        (-4 / 1)
        * _stencil_shift(halo, 1, -1, 2, 'zero') +
        (1 / 1)
        * _stencil_shift(halo, 2, -1, 2, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 2, -1, 'zero'] = _fd_d4_a2_axis1_zero


def _fd_d4_a2_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 2, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 4.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 2, 'reflect', 4)
    result = (
        (1 / 1)
        * _stencil_shift(halo, -2, -1, 2, 'reflect') +
        (-4 / 1)
        * _stencil_shift(halo, -1, -1, 2, 'reflect') +
        (6 / 1)
        * _stencil_shift(halo, 0, -1, 2, 'reflect') +
        (-4 / 1)
        * _stencil_shift(halo, 1, -1, 2, 'reflect') +
        (1 / 1)
        * _stencil_shift(halo, 2, -1, 2, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 2, -1, 'reflect'] = _fd_d4_a2_axis1_reflect


STENCIL_MOMENTS[4, 4] = (
    (-3, -1, 6),
    (-2, 2, 1),
    (-1, -13, 2),
    (0, 28, 3),
    (1, -13, 2),
    (2, 2, 1),
    (3, -1, 6),
)

def _fd_d4_a4_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 4, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 3, 'periodic', 4)
    result = (
        (-1 / 6)
        * _stencil_shift(halo, -3, -4, 3, 'periodic') +
        (2 / 1)
        * _stencil_shift(halo, -2, -4, 3, 'periodic') +
        (-13 / 2)
        * _stencil_shift(halo, -1, -4, 3, 'periodic') +
        (28 / 3)
        * _stencil_shift(halo, 0, -4, 3, 'periodic') +
        (-13 / 2)
        * _stencil_shift(halo, 1, -4, 3, 'periodic') +
        (2 / 1)
        * _stencil_shift(halo, 2, -4, 3, 'periodic') +
        (-1 / 6)
        * _stencil_shift(halo, 3, -4, 3, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 4, -4, 'periodic'] = _fd_d4_a4_axis4_periodic


def _fd_d4_a4_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 4, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 3, 'zero', 4)
    result = (
        (-1 / 6)
        * _stencil_shift(halo, -3, -4, 3, 'zero') +
        (2 / 1)
        * _stencil_shift(halo, -2, -4, 3, 'zero') +
        (-13 / 2)
        * _stencil_shift(halo, -1, -4, 3, 'zero') +
        (28 / 3)
        * _stencil_shift(halo, 0, -4, 3, 'zero') +
        (-13 / 2)
        * _stencil_shift(halo, 1, -4, 3, 'zero') +
        (2 / 1)
        * _stencil_shift(halo, 2, -4, 3, 'zero') +
        (-1 / 6)
        * _stencil_shift(halo, 3, -4, 3, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 4, -4, 'zero'] = _fd_d4_a4_axis4_zero


def _fd_d4_a4_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 4, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 3, 'reflect', 4)
    result = (
        (-1 / 6)
        * _stencil_shift(halo, -3, -4, 3, 'reflect') +
        (2 / 1)
        * _stencil_shift(halo, -2, -4, 3, 'reflect') +
        (-13 / 2)
        * _stencil_shift(halo, -1, -4, 3, 'reflect') +
        (28 / 3)
        * _stencil_shift(halo, 0, -4, 3, 'reflect') +
        (-13 / 2)
        * _stencil_shift(halo, 1, -4, 3, 'reflect') +
        (2 / 1)
        * _stencil_shift(halo, 2, -4, 3, 'reflect') +
        (-1 / 6)
        * _stencil_shift(halo, 3, -4, 3, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 4, -4, 'reflect'] = _fd_d4_a4_axis4_reflect


def _fd_d4_a4_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 4, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 3, 'periodic', 4)
    result = (
        (-1 / 6)
        * _stencil_shift(halo, -3, -3, 3, 'periodic') +
        (2 / 1)
        * _stencil_shift(halo, -2, -3, 3, 'periodic') +
        (-13 / 2)
        * _stencil_shift(halo, -1, -3, 3, 'periodic') +
        (28 / 3)
        * _stencil_shift(halo, 0, -3, 3, 'periodic') +
        (-13 / 2)
        * _stencil_shift(halo, 1, -3, 3, 'periodic') +
        (2 / 1)
        * _stencil_shift(halo, 2, -3, 3, 'periodic') +
        (-1 / 6)
        * _stencil_shift(halo, 3, -3, 3, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 4, -3, 'periodic'] = _fd_d4_a4_axis3_periodic


def _fd_d4_a4_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 4, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 3, 'zero', 4)
    result = (
        (-1 / 6)
        * _stencil_shift(halo, -3, -3, 3, 'zero') +
        (2 / 1)
        * _stencil_shift(halo, -2, -3, 3, 'zero') +
        (-13 / 2)
        * _stencil_shift(halo, -1, -3, 3, 'zero') +
        (28 / 3)
        * _stencil_shift(halo, 0, -3, 3, 'zero') +
        (-13 / 2)
        * _stencil_shift(halo, 1, -3, 3, 'zero') +
        (2 / 1)
        * _stencil_shift(halo, 2, -3, 3, 'zero') +
        (-1 / 6)
        * _stencil_shift(halo, 3, -3, 3, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 4, -3, 'zero'] = _fd_d4_a4_axis3_zero


def _fd_d4_a4_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 4, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 3, 'reflect', 4)
    result = (
        (-1 / 6)
        * _stencil_shift(halo, -3, -3, 3, 'reflect') +
        (2 / 1)
        * _stencil_shift(halo, -2, -3, 3, 'reflect') +
        (-13 / 2)
        * _stencil_shift(halo, -1, -3, 3, 'reflect') +
        (28 / 3)
        * _stencil_shift(halo, 0, -3, 3, 'reflect') +
        (-13 / 2)
        * _stencil_shift(halo, 1, -3, 3, 'reflect') +
        (2 / 1)
        * _stencil_shift(halo, 2, -3, 3, 'reflect') +
        (-1 / 6)
        * _stencil_shift(halo, 3, -3, 3, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 4, -3, 'reflect'] = _fd_d4_a4_axis3_reflect


def _fd_d4_a4_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 4, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 3, 'periodic', 4)
    result = (
        (-1 / 6)
        * _stencil_shift(halo, -3, -2, 3, 'periodic') +
        (2 / 1)
        * _stencil_shift(halo, -2, -2, 3, 'periodic') +
        (-13 / 2)
        * _stencil_shift(halo, -1, -2, 3, 'periodic') +
        (28 / 3)
        * _stencil_shift(halo, 0, -2, 3, 'periodic') +
        (-13 / 2)
        * _stencil_shift(halo, 1, -2, 3, 'periodic') +
        (2 / 1)
        * _stencil_shift(halo, 2, -2, 3, 'periodic') +
        (-1 / 6)
        * _stencil_shift(halo, 3, -2, 3, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 4, -2, 'periodic'] = _fd_d4_a4_axis2_periodic


def _fd_d4_a4_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 4, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 3, 'zero', 4)
    result = (
        (-1 / 6)
        * _stencil_shift(halo, -3, -2, 3, 'zero') +
        (2 / 1)
        * _stencil_shift(halo, -2, -2, 3, 'zero') +
        (-13 / 2)
        * _stencil_shift(halo, -1, -2, 3, 'zero') +
        (28 / 3)
        * _stencil_shift(halo, 0, -2, 3, 'zero') +
        (-13 / 2)
        * _stencil_shift(halo, 1, -2, 3, 'zero') +
        (2 / 1)
        * _stencil_shift(halo, 2, -2, 3, 'zero') +
        (-1 / 6)
        * _stencil_shift(halo, 3, -2, 3, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 4, -2, 'zero'] = _fd_d4_a4_axis2_zero


def _fd_d4_a4_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 4, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 3, 'reflect', 4)
    result = (
        (-1 / 6)
        * _stencil_shift(halo, -3, -2, 3, 'reflect') +
        (2 / 1)
        * _stencil_shift(halo, -2, -2, 3, 'reflect') +
        (-13 / 2)
        * _stencil_shift(halo, -1, -2, 3, 'reflect') +
        (28 / 3)
        * _stencil_shift(halo, 0, -2, 3, 'reflect') +
        (-13 / 2)
        * _stencil_shift(halo, 1, -2, 3, 'reflect') +
        (2 / 1)
        * _stencil_shift(halo, 2, -2, 3, 'reflect') +
        (-1 / 6)
        * _stencil_shift(halo, 3, -2, 3, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 4, -2, 'reflect'] = _fd_d4_a4_axis2_reflect


def _fd_d4_a4_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 4, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 3, 'periodic', 4)
    result = (
        (-1 / 6)
        * _stencil_shift(halo, -3, -1, 3, 'periodic') +
        (2 / 1)
        * _stencil_shift(halo, -2, -1, 3, 'periodic') +
        (-13 / 2)
        * _stencil_shift(halo, -1, -1, 3, 'periodic') +
        (28 / 3)
        * _stencil_shift(halo, 0, -1, 3, 'periodic') +
        (-13 / 2)
        * _stencil_shift(halo, 1, -1, 3, 'periodic') +
        (2 / 1)
        * _stencil_shift(halo, 2, -1, 3, 'periodic') +
        (-1 / 6)
        * _stencil_shift(halo, 3, -1, 3, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 4, -1, 'periodic'] = _fd_d4_a4_axis1_periodic


def _fd_d4_a4_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 4, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 3, 'zero', 4)
    result = (
        (-1 / 6)
        * _stencil_shift(halo, -3, -1, 3, 'zero') +
        (2 / 1)
        * _stencil_shift(halo, -2, -1, 3, 'zero') +
        (-13 / 2)
        * _stencil_shift(halo, -1, -1, 3, 'zero') +
        (28 / 3)
        * _stencil_shift(halo, 0, -1, 3, 'zero') +
        (-13 / 2)
        * _stencil_shift(halo, 1, -1, 3, 'zero') +
        (2 / 1)
        * _stencil_shift(halo, 2, -1, 3, 'zero') +
        (-1 / 6)
        * _stencil_shift(halo, 3, -1, 3, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 4, -1, 'zero'] = _fd_d4_a4_axis1_zero


def _fd_d4_a4_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 4, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 6.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 3, 'reflect', 4)
    result = (
        (-1 / 6)
        * _stencil_shift(halo, -3, -1, 3, 'reflect') +
        (2 / 1)
        * _stencil_shift(halo, -2, -1, 3, 'reflect') +
        (-13 / 2)
        * _stencil_shift(halo, -1, -1, 3, 'reflect') +
        (28 / 3)
        * _stencil_shift(halo, 0, -1, 3, 'reflect') +
        (-13 / 2)
        * _stencil_shift(halo, 1, -1, 3, 'reflect') +
        (2 / 1)
        * _stencil_shift(halo, 2, -1, 3, 'reflect') +
        (-1 / 6)
        * _stencil_shift(halo, 3, -1, 3, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 4, -1, 'reflect'] = _fd_d4_a4_axis1_reflect


STENCIL_MOMENTS[4, 6] = (
    (-4, 7, 240),
    (-3, -2, 5),
    (-2, 169, 60),
    (-1, -122, 15),
    (0, 91, 8),
    (1, -122, 15),
    (2, 169, 60),
    (3, -2, 5),
    (4, 7, 240),
)

def _fd_d4_a6_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 6, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 4, 'periodic', 4)
    result = (
        (7 / 240)
        * _stencil_shift(halo, -4, -4, 4, 'periodic') +
        (-2 / 5)
        * _stencil_shift(halo, -3, -4, 4, 'periodic') +
        (169 / 60)
        * _stencil_shift(halo, -2, -4, 4, 'periodic') +
        (-122 / 15)
        * _stencil_shift(halo, -1, -4, 4, 'periodic') +
        (91 / 8)
        * _stencil_shift(halo, 0, -4, 4, 'periodic') +
        (-122 / 15)
        * _stencil_shift(halo, 1, -4, 4, 'periodic') +
        (169 / 60)
        * _stencil_shift(halo, 2, -4, 4, 'periodic') +
        (-2 / 5)
        * _stencil_shift(halo, 3, -4, 4, 'periodic') +
        (7 / 240)
        * _stencil_shift(halo, 4, -4, 4, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 6, -4, 'periodic'] = _fd_d4_a6_axis4_periodic


def _fd_d4_a6_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 6, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 4, 'zero', 4)
    result = (
        (7 / 240)
        * _stencil_shift(halo, -4, -4, 4, 'zero') +
        (-2 / 5)
        * _stencil_shift(halo, -3, -4, 4, 'zero') +
        (169 / 60)
        * _stencil_shift(halo, -2, -4, 4, 'zero') +
        (-122 / 15)
        * _stencil_shift(halo, -1, -4, 4, 'zero') +
        (91 / 8)
        * _stencil_shift(halo, 0, -4, 4, 'zero') +
        (-122 / 15)
        * _stencil_shift(halo, 1, -4, 4, 'zero') +
        (169 / 60)
        * _stencil_shift(halo, 2, -4, 4, 'zero') +
        (-2 / 5)
        * _stencil_shift(halo, 3, -4, 4, 'zero') +
        (7 / 240)
        * _stencil_shift(halo, 4, -4, 4, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 6, -4, 'zero'] = _fd_d4_a6_axis4_zero


def _fd_d4_a6_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 6, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 4, 'reflect', 4)
    result = (
        (7 / 240)
        * _stencil_shift(halo, -4, -4, 4, 'reflect') +
        (-2 / 5)
        * _stencil_shift(halo, -3, -4, 4, 'reflect') +
        (169 / 60)
        * _stencil_shift(halo, -2, -4, 4, 'reflect') +
        (-122 / 15)
        * _stencil_shift(halo, -1, -4, 4, 'reflect') +
        (91 / 8)
        * _stencil_shift(halo, 0, -4, 4, 'reflect') +
        (-122 / 15)
        * _stencil_shift(halo, 1, -4, 4, 'reflect') +
        (169 / 60)
        * _stencil_shift(halo, 2, -4, 4, 'reflect') +
        (-2 / 5)
        * _stencil_shift(halo, 3, -4, 4, 'reflect') +
        (7 / 240)
        * _stencil_shift(halo, 4, -4, 4, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 6, -4, 'reflect'] = _fd_d4_a6_axis4_reflect


def _fd_d4_a6_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 6, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 4, 'periodic', 4)
    result = (
        (7 / 240)
        * _stencil_shift(halo, -4, -3, 4, 'periodic') +
        (-2 / 5)
        * _stencil_shift(halo, -3, -3, 4, 'periodic') +
        (169 / 60)
        * _stencil_shift(halo, -2, -3, 4, 'periodic') +
        (-122 / 15)
        * _stencil_shift(halo, -1, -3, 4, 'periodic') +
        (91 / 8)
        * _stencil_shift(halo, 0, -3, 4, 'periodic') +
        (-122 / 15)
        * _stencil_shift(halo, 1, -3, 4, 'periodic') +
        (169 / 60)
        * _stencil_shift(halo, 2, -3, 4, 'periodic') +
        (-2 / 5)
        * _stencil_shift(halo, 3, -3, 4, 'periodic') +
        (7 / 240)
        * _stencil_shift(halo, 4, -3, 4, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 6, -3, 'periodic'] = _fd_d4_a6_axis3_periodic


def _fd_d4_a6_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 6, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 4, 'zero', 4)
    result = (
        (7 / 240)
        * _stencil_shift(halo, -4, -3, 4, 'zero') +
        (-2 / 5)
        * _stencil_shift(halo, -3, -3, 4, 'zero') +
        (169 / 60)
        * _stencil_shift(halo, -2, -3, 4, 'zero') +
        (-122 / 15)
        * _stencil_shift(halo, -1, -3, 4, 'zero') +
        (91 / 8)
        * _stencil_shift(halo, 0, -3, 4, 'zero') +
        (-122 / 15)
        * _stencil_shift(halo, 1, -3, 4, 'zero') +
        (169 / 60)
        * _stencil_shift(halo, 2, -3, 4, 'zero') +
        (-2 / 5)
        * _stencil_shift(halo, 3, -3, 4, 'zero') +
        (7 / 240)
        * _stencil_shift(halo, 4, -3, 4, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 6, -3, 'zero'] = _fd_d4_a6_axis3_zero


def _fd_d4_a6_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 6, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 4, 'reflect', 4)
    result = (
        (7 / 240)
        * _stencil_shift(halo, -4, -3, 4, 'reflect') +
        (-2 / 5)
        * _stencil_shift(halo, -3, -3, 4, 'reflect') +
        (169 / 60)
        * _stencil_shift(halo, -2, -3, 4, 'reflect') +
        (-122 / 15)
        * _stencil_shift(halo, -1, -3, 4, 'reflect') +
        (91 / 8)
        * _stencil_shift(halo, 0, -3, 4, 'reflect') +
        (-122 / 15)
        * _stencil_shift(halo, 1, -3, 4, 'reflect') +
        (169 / 60)
        * _stencil_shift(halo, 2, -3, 4, 'reflect') +
        (-2 / 5)
        * _stencil_shift(halo, 3, -3, 4, 'reflect') +
        (7 / 240)
        * _stencil_shift(halo, 4, -3, 4, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 6, -3, 'reflect'] = _fd_d4_a6_axis3_reflect


def _fd_d4_a6_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 6, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 4, 'periodic', 4)
    result = (
        (7 / 240)
        * _stencil_shift(halo, -4, -2, 4, 'periodic') +
        (-2 / 5)
        * _stencil_shift(halo, -3, -2, 4, 'periodic') +
        (169 / 60)
        * _stencil_shift(halo, -2, -2, 4, 'periodic') +
        (-122 / 15)
        * _stencil_shift(halo, -1, -2, 4, 'periodic') +
        (91 / 8)
        * _stencil_shift(halo, 0, -2, 4, 'periodic') +
        (-122 / 15)
        * _stencil_shift(halo, 1, -2, 4, 'periodic') +
        (169 / 60)
        * _stencil_shift(halo, 2, -2, 4, 'periodic') +
        (-2 / 5)
        * _stencil_shift(halo, 3, -2, 4, 'periodic') +
        (7 / 240)
        * _stencil_shift(halo, 4, -2, 4, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 6, -2, 'periodic'] = _fd_d4_a6_axis2_periodic


def _fd_d4_a6_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 6, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 4, 'zero', 4)
    result = (
        (7 / 240)
        * _stencil_shift(halo, -4, -2, 4, 'zero') +
        (-2 / 5)
        * _stencil_shift(halo, -3, -2, 4, 'zero') +
        (169 / 60)
        * _stencil_shift(halo, -2, -2, 4, 'zero') +
        (-122 / 15)
        * _stencil_shift(halo, -1, -2, 4, 'zero') +
        (91 / 8)
        * _stencil_shift(halo, 0, -2, 4, 'zero') +
        (-122 / 15)
        * _stencil_shift(halo, 1, -2, 4, 'zero') +
        (169 / 60)
        * _stencil_shift(halo, 2, -2, 4, 'zero') +
        (-2 / 5)
        * _stencil_shift(halo, 3, -2, 4, 'zero') +
        (7 / 240)
        * _stencil_shift(halo, 4, -2, 4, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 6, -2, 'zero'] = _fd_d4_a6_axis2_zero


def _fd_d4_a6_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 6, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 4, 'reflect', 4)
    result = (
        (7 / 240)
        * _stencil_shift(halo, -4, -2, 4, 'reflect') +
        (-2 / 5)
        * _stencil_shift(halo, -3, -2, 4, 'reflect') +
        (169 / 60)
        * _stencil_shift(halo, -2, -2, 4, 'reflect') +
        (-122 / 15)
        * _stencil_shift(halo, -1, -2, 4, 'reflect') +
        (91 / 8)
        * _stencil_shift(halo, 0, -2, 4, 'reflect') +
        (-122 / 15)
        * _stencil_shift(halo, 1, -2, 4, 'reflect') +
        (169 / 60)
        * _stencil_shift(halo, 2, -2, 4, 'reflect') +
        (-2 / 5)
        * _stencil_shift(halo, 3, -2, 4, 'reflect') +
        (7 / 240)
        * _stencil_shift(halo, 4, -2, 4, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 6, -2, 'reflect'] = _fd_d4_a6_axis2_reflect


def _fd_d4_a6_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 6, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 4, 'periodic', 4)
    result = (
        (7 / 240)
        * _stencil_shift(halo, -4, -1, 4, 'periodic') +
        (-2 / 5)
        * _stencil_shift(halo, -3, -1, 4, 'periodic') +
        (169 / 60)
        * _stencil_shift(halo, -2, -1, 4, 'periodic') +
        (-122 / 15)
        * _stencil_shift(halo, -1, -1, 4, 'periodic') +
        (91 / 8)
        * _stencil_shift(halo, 0, -1, 4, 'periodic') +
        (-122 / 15)
        * _stencil_shift(halo, 1, -1, 4, 'periodic') +
        (169 / 60)
        * _stencil_shift(halo, 2, -1, 4, 'periodic') +
        (-2 / 5)
        * _stencil_shift(halo, 3, -1, 4, 'periodic') +
        (7 / 240)
        * _stencil_shift(halo, 4, -1, 4, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 6, -1, 'periodic'] = _fd_d4_a6_axis1_periodic


def _fd_d4_a6_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 6, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 4, 'zero', 4)
    result = (
        (7 / 240)
        * _stencil_shift(halo, -4, -1, 4, 'zero') +
        (-2 / 5)
        * _stencil_shift(halo, -3, -1, 4, 'zero') +
        (169 / 60)
        * _stencil_shift(halo, -2, -1, 4, 'zero') +
        (-122 / 15)
        * _stencil_shift(halo, -1, -1, 4, 'zero') +
        (91 / 8)
        * _stencil_shift(halo, 0, -1, 4, 'zero') +
        (-122 / 15)
        * _stencil_shift(halo, 1, -1, 4, 'zero') +
        (169 / 60)
        * _stencil_shift(halo, 2, -1, 4, 'zero') +
        (-2 / 5)
        * _stencil_shift(halo, 3, -1, 4, 'zero') +
        (7 / 240)
        * _stencil_shift(halo, 4, -1, 4, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 6, -1, 'zero'] = _fd_d4_a6_axis1_zero


def _fd_d4_a6_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 6, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 8.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 4, 'reflect', 4)
    result = (
        (7 / 240)
        * _stencil_shift(halo, -4, -1, 4, 'reflect') +
        (-2 / 5)
        * _stencil_shift(halo, -3, -1, 4, 'reflect') +
        (169 / 60)
        * _stencil_shift(halo, -2, -1, 4, 'reflect') +
        (-122 / 15)
        * _stencil_shift(halo, -1, -1, 4, 'reflect') +
        (91 / 8)
        * _stencil_shift(halo, 0, -1, 4, 'reflect') +
        (-122 / 15)
        * _stencil_shift(halo, 1, -1, 4, 'reflect') +
        (169 / 60)
        * _stencil_shift(halo, 2, -1, 4, 'reflect') +
        (-2 / 5)
        * _stencil_shift(halo, 3, -1, 4, 'reflect') +
        (7 / 240)
        * _stencil_shift(halo, 4, -1, 4, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 6, -1, 'reflect'] = _fd_d4_a6_axis1_reflect


STENCIL_MOMENTS[4, 8] = (
    (-5, -41, 7560),
    (-4, 1261, 15120),
    (-3, -541, 840),
    (-2, 4369, 1260),
    (-1, -1669, 180),
    (0, 1529, 120),
    (1, -1669, 180),
    (2, 4369, 1260),
    (3, -541, 840),
    (4, 1261, 15120),
    (5, -41, 7560),
)

def _fd_d4_a8_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 8, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 5, 'periodic', 4)
    result = (
        (-41 / 7560)
        * _stencil_shift(halo, -5, -4, 5, 'periodic') +
        (1261 / 15120)
        * _stencil_shift(halo, -4, -4, 5, 'periodic') +
        (-541 / 840)
        * _stencil_shift(halo, -3, -4, 5, 'periodic') +
        (4369 / 1260)
        * _stencil_shift(halo, -2, -4, 5, 'periodic') +
        (-1669 / 180)
        * _stencil_shift(halo, -1, -4, 5, 'periodic') +
        (1529 / 120)
        * _stencil_shift(halo, 0, -4, 5, 'periodic') +
        (-1669 / 180)
        * _stencil_shift(halo, 1, -4, 5, 'periodic') +
        (4369 / 1260)
        * _stencil_shift(halo, 2, -4, 5, 'periodic') +
        (-541 / 840)
        * _stencil_shift(halo, 3, -4, 5, 'periodic') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -4, 5, 'periodic') +
        (-41 / 7560)
        * _stencil_shift(halo, 5, -4, 5, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 8, -4, 'periodic'] = _fd_d4_a8_axis4_periodic


def _fd_d4_a8_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 8, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 5, 'zero', 4)
    result = (
        (-41 / 7560)
        * _stencil_shift(halo, -5, -4, 5, 'zero') +
        (1261 / 15120)
        * _stencil_shift(halo, -4, -4, 5, 'zero') +
        (-541 / 840)
        * _stencil_shift(halo, -3, -4, 5, 'zero') +
        (4369 / 1260)
        * _stencil_shift(halo, -2, -4, 5, 'zero') +
        (-1669 / 180)
        * _stencil_shift(halo, -1, -4, 5, 'zero') +
        (1529 / 120)
        * _stencil_shift(halo, 0, -4, 5, 'zero') +
        (-1669 / 180)
        * _stencil_shift(halo, 1, -4, 5, 'zero') +
        (4369 / 1260)
        * _stencil_shift(halo, 2, -4, 5, 'zero') +
        (-541 / 840)
        * _stencil_shift(halo, 3, -4, 5, 'zero') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -4, 5, 'zero') +
        (-41 / 7560)
        * _stencil_shift(halo, 5, -4, 5, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 8, -4, 'zero'] = _fd_d4_a8_axis4_zero


def _fd_d4_a8_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 8, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 5, 'reflect', 4)
    result = (
        (-41 / 7560)
        * _stencil_shift(halo, -5, -4, 5, 'reflect') +
        (1261 / 15120)
        * _stencil_shift(halo, -4, -4, 5, 'reflect') +
        (-541 / 840)
        * _stencil_shift(halo, -3, -4, 5, 'reflect') +
        (4369 / 1260)
        * _stencil_shift(halo, -2, -4, 5, 'reflect') +
        (-1669 / 180)
        * _stencil_shift(halo, -1, -4, 5, 'reflect') +
        (1529 / 120)
        * _stencil_shift(halo, 0, -4, 5, 'reflect') +
        (-1669 / 180)
        * _stencil_shift(halo, 1, -4, 5, 'reflect') +
        (4369 / 1260)
        * _stencil_shift(halo, 2, -4, 5, 'reflect') +
        (-541 / 840)
        * _stencil_shift(halo, 3, -4, 5, 'reflect') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -4, 5, 'reflect') +
        (-41 / 7560)
        * _stencil_shift(halo, 5, -4, 5, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 8, -4, 'reflect'] = _fd_d4_a8_axis4_reflect


def _fd_d4_a8_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 8, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 5, 'periodic', 4)
    result = (
        (-41 / 7560)
        * _stencil_shift(halo, -5, -3, 5, 'periodic') +
        (1261 / 15120)
        * _stencil_shift(halo, -4, -3, 5, 'periodic') +
        (-541 / 840)
        * _stencil_shift(halo, -3, -3, 5, 'periodic') +
        (4369 / 1260)
        * _stencil_shift(halo, -2, -3, 5, 'periodic') +
        (-1669 / 180)
        * _stencil_shift(halo, -1, -3, 5, 'periodic') +
        (1529 / 120)
        * _stencil_shift(halo, 0, -3, 5, 'periodic') +
        (-1669 / 180)
        * _stencil_shift(halo, 1, -3, 5, 'periodic') +
        (4369 / 1260)
        * _stencil_shift(halo, 2, -3, 5, 'periodic') +
        (-541 / 840)
        * _stencil_shift(halo, 3, -3, 5, 'periodic') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -3, 5, 'periodic') +
        (-41 / 7560)
        * _stencil_shift(halo, 5, -3, 5, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 8, -3, 'periodic'] = _fd_d4_a8_axis3_periodic


def _fd_d4_a8_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 8, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 5, 'zero', 4)
    result = (
        (-41 / 7560)
        * _stencil_shift(halo, -5, -3, 5, 'zero') +
        (1261 / 15120)
        * _stencil_shift(halo, -4, -3, 5, 'zero') +
        (-541 / 840)
        * _stencil_shift(halo, -3, -3, 5, 'zero') +
        (4369 / 1260)
        * _stencil_shift(halo, -2, -3, 5, 'zero') +
        (-1669 / 180)
        * _stencil_shift(halo, -1, -3, 5, 'zero') +
        (1529 / 120)
        * _stencil_shift(halo, 0, -3, 5, 'zero') +
        (-1669 / 180)
        * _stencil_shift(halo, 1, -3, 5, 'zero') +
        (4369 / 1260)
        * _stencil_shift(halo, 2, -3, 5, 'zero') +
        (-541 / 840)
        * _stencil_shift(halo, 3, -3, 5, 'zero') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -3, 5, 'zero') +
        (-41 / 7560)
        * _stencil_shift(halo, 5, -3, 5, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 8, -3, 'zero'] = _fd_d4_a8_axis3_zero


def _fd_d4_a8_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 8, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 5, 'reflect', 4)
    result = (
        (-41 / 7560)
        * _stencil_shift(halo, -5, -3, 5, 'reflect') +
        (1261 / 15120)
        * _stencil_shift(halo, -4, -3, 5, 'reflect') +
        (-541 / 840)
        * _stencil_shift(halo, -3, -3, 5, 'reflect') +
        (4369 / 1260)
        * _stencil_shift(halo, -2, -3, 5, 'reflect') +
        (-1669 / 180)
        * _stencil_shift(halo, -1, -3, 5, 'reflect') +
        (1529 / 120)
        * _stencil_shift(halo, 0, -3, 5, 'reflect') +
        (-1669 / 180)
        * _stencil_shift(halo, 1, -3, 5, 'reflect') +
        (4369 / 1260)
        * _stencil_shift(halo, 2, -3, 5, 'reflect') +
        (-541 / 840)
        * _stencil_shift(halo, 3, -3, 5, 'reflect') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -3, 5, 'reflect') +
        (-41 / 7560)
        * _stencil_shift(halo, 5, -3, 5, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 8, -3, 'reflect'] = _fd_d4_a8_axis3_reflect


def _fd_d4_a8_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 8, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 5, 'periodic', 4)
    result = (
        (-41 / 7560)
        * _stencil_shift(halo, -5, -2, 5, 'periodic') +
        (1261 / 15120)
        * _stencil_shift(halo, -4, -2, 5, 'periodic') +
        (-541 / 840)
        * _stencil_shift(halo, -3, -2, 5, 'periodic') +
        (4369 / 1260)
        * _stencil_shift(halo, -2, -2, 5, 'periodic') +
        (-1669 / 180)
        * _stencil_shift(halo, -1, -2, 5, 'periodic') +
        (1529 / 120)
        * _stencil_shift(halo, 0, -2, 5, 'periodic') +
        (-1669 / 180)
        * _stencil_shift(halo, 1, -2, 5, 'periodic') +
        (4369 / 1260)
        * _stencil_shift(halo, 2, -2, 5, 'periodic') +
        (-541 / 840)
        * _stencil_shift(halo, 3, -2, 5, 'periodic') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -2, 5, 'periodic') +
        (-41 / 7560)
        * _stencil_shift(halo, 5, -2, 5, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 8, -2, 'periodic'] = _fd_d4_a8_axis2_periodic


def _fd_d4_a8_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 8, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 5, 'zero', 4)
    result = (
        (-41 / 7560)
        * _stencil_shift(halo, -5, -2, 5, 'zero') +
        (1261 / 15120)
        * _stencil_shift(halo, -4, -2, 5, 'zero') +
        (-541 / 840)
        * _stencil_shift(halo, -3, -2, 5, 'zero') +
        (4369 / 1260)
        * _stencil_shift(halo, -2, -2, 5, 'zero') +
        (-1669 / 180)
        * _stencil_shift(halo, -1, -2, 5, 'zero') +
        (1529 / 120)
        * _stencil_shift(halo, 0, -2, 5, 'zero') +
        (-1669 / 180)
        * _stencil_shift(halo, 1, -2, 5, 'zero') +
        (4369 / 1260)
        * _stencil_shift(halo, 2, -2, 5, 'zero') +
        (-541 / 840)
        * _stencil_shift(halo, 3, -2, 5, 'zero') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -2, 5, 'zero') +
        (-41 / 7560)
        * _stencil_shift(halo, 5, -2, 5, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 8, -2, 'zero'] = _fd_d4_a8_axis2_zero


def _fd_d4_a8_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 8, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 5, 'reflect', 4)
    result = (
        (-41 / 7560)
        * _stencil_shift(halo, -5, -2, 5, 'reflect') +
        (1261 / 15120)
        * _stencil_shift(halo, -4, -2, 5, 'reflect') +
        (-541 / 840)
        * _stencil_shift(halo, -3, -2, 5, 'reflect') +
        (4369 / 1260)
        * _stencil_shift(halo, -2, -2, 5, 'reflect') +
        (-1669 / 180)
        * _stencil_shift(halo, -1, -2, 5, 'reflect') +
        (1529 / 120)
        * _stencil_shift(halo, 0, -2, 5, 'reflect') +
        (-1669 / 180)
        * _stencil_shift(halo, 1, -2, 5, 'reflect') +
        (4369 / 1260)
        * _stencil_shift(halo, 2, -2, 5, 'reflect') +
        (-541 / 840)
        * _stencil_shift(halo, 3, -2, 5, 'reflect') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -2, 5, 'reflect') +
        (-41 / 7560)
        * _stencil_shift(halo, 5, -2, 5, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 8, -2, 'reflect'] = _fd_d4_a8_axis2_reflect


def _fd_d4_a8_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 8, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 5, 'periodic', 4)
    result = (
        (-41 / 7560)
        * _stencil_shift(halo, -5, -1, 5, 'periodic') +
        (1261 / 15120)
        * _stencil_shift(halo, -4, -1, 5, 'periodic') +
        (-541 / 840)
        * _stencil_shift(halo, -3, -1, 5, 'periodic') +
        (4369 / 1260)
        * _stencil_shift(halo, -2, -1, 5, 'periodic') +
        (-1669 / 180)
        * _stencil_shift(halo, -1, -1, 5, 'periodic') +
        (1529 / 120)
        * _stencil_shift(halo, 0, -1, 5, 'periodic') +
        (-1669 / 180)
        * _stencil_shift(halo, 1, -1, 5, 'periodic') +
        (4369 / 1260)
        * _stencil_shift(halo, 2, -1, 5, 'periodic') +
        (-541 / 840)
        * _stencil_shift(halo, 3, -1, 5, 'periodic') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -1, 5, 'periodic') +
        (-41 / 7560)
        * _stencil_shift(halo, 5, -1, 5, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 8, -1, 'periodic'] = _fd_d4_a8_axis1_periodic


def _fd_d4_a8_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 8, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 5, 'zero', 4)
    result = (
        (-41 / 7560)
        * _stencil_shift(halo, -5, -1, 5, 'zero') +
        (1261 / 15120)
        * _stencil_shift(halo, -4, -1, 5, 'zero') +
        (-541 / 840)
        * _stencil_shift(halo, -3, -1, 5, 'zero') +
        (4369 / 1260)
        * _stencil_shift(halo, -2, -1, 5, 'zero') +
        (-1669 / 180)
        * _stencil_shift(halo, -1, -1, 5, 'zero') +
        (1529 / 120)
        * _stencil_shift(halo, 0, -1, 5, 'zero') +
        (-1669 / 180)
        * _stencil_shift(halo, 1, -1, 5, 'zero') +
        (4369 / 1260)
        * _stencil_shift(halo, 2, -1, 5, 'zero') +
        (-541 / 840)
        * _stencil_shift(halo, 3, -1, 5, 'zero') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -1, 5, 'zero') +
        (-41 / 7560)
        * _stencil_shift(halo, 5, -1, 5, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 8, -1, 'zero'] = _fd_d4_a8_axis1_zero


def _fd_d4_a8_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 8, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 10.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 5, 'reflect', 4)
    result = (
        (-41 / 7560)
        * _stencil_shift(halo, -5, -1, 5, 'reflect') +
        (1261 / 15120)
        * _stencil_shift(halo, -4, -1, 5, 'reflect') +
        (-541 / 840)
        * _stencil_shift(halo, -3, -1, 5, 'reflect') +
        (4369 / 1260)
        * _stencil_shift(halo, -2, -1, 5, 'reflect') +
        (-1669 / 180)
        * _stencil_shift(halo, -1, -1, 5, 'reflect') +
        (1529 / 120)
        * _stencil_shift(halo, 0, -1, 5, 'reflect') +
        (-1669 / 180)
        * _stencil_shift(halo, 1, -1, 5, 'reflect') +
        (4369 / 1260)
        * _stencil_shift(halo, 2, -1, 5, 'reflect') +
        (-541 / 840)
        * _stencil_shift(halo, 3, -1, 5, 'reflect') +
        (1261 / 15120)
        * _stencil_shift(halo, 4, -1, 5, 'reflect') +
        (-41 / 7560)
        * _stencil_shift(halo, 5, -1, 5, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 8, -1, 'reflect'] = _fd_d4_a8_axis1_reflect


STENCIL_MOMENTS[4, 10] = (
    (-6, 479, 453600),
    (-5, -19, 1050),
    (-4, 643, 4200),
    (-3, -4969, 5670),
    (-2, 4469, 1120),
    (-1, -1769, 175),
    (0, 37037, 2700),
    (1, -1769, 175),
    (2, 4469, 1120),
    (3, -4969, 5670),
    (4, 643, 4200),
    (5, -19, 1050),
    (6, 479, 453600),
)

def _fd_d4_a10_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 10, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 6, 'periodic', 4)
    result = (
        (479 / 453600)
        * _stencil_shift(halo, -6, -4, 6, 'periodic') +
        (-19 / 1050)
        * _stencil_shift(halo, -5, -4, 6, 'periodic') +
        (643 / 4200)
        * _stencil_shift(halo, -4, -4, 6, 'periodic') +
        (-4969 / 5670)
        * _stencil_shift(halo, -3, -4, 6, 'periodic') +
        (4469 / 1120)
        * _stencil_shift(halo, -2, -4, 6, 'periodic') +
        (-1769 / 175)
        * _stencil_shift(halo, -1, -4, 6, 'periodic') +
        (37037 / 2700)
        * _stencil_shift(halo, 0, -4, 6, 'periodic') +
        (-1769 / 175)
        * _stencil_shift(halo, 1, -4, 6, 'periodic') +
        (4469 / 1120)
        * _stencil_shift(halo, 2, -4, 6, 'periodic') +
        (-4969 / 5670)
        * _stencil_shift(halo, 3, -4, 6, 'periodic') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -4, 6, 'periodic') +
        (-19 / 1050)
        * _stencil_shift(halo, 5, -4, 6, 'periodic') +
        (479 / 453600)
        * _stencil_shift(halo, 6, -4, 6, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 10, -4, 'periodic'] = _fd_d4_a10_axis4_periodic


def _fd_d4_a10_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 10, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 6, 'zero', 4)
    result = (
        (479 / 453600)
        * _stencil_shift(halo, -6, -4, 6, 'zero') +
        (-19 / 1050)
        * _stencil_shift(halo, -5, -4, 6, 'zero') +
        (643 / 4200)
        * _stencil_shift(halo, -4, -4, 6, 'zero') +
        (-4969 / 5670)
        * _stencil_shift(halo, -3, -4, 6, 'zero') +
        (4469 / 1120)
        * _stencil_shift(halo, -2, -4, 6, 'zero') +
        (-1769 / 175)
        * _stencil_shift(halo, -1, -4, 6, 'zero') +
        (37037 / 2700)
        * _stencil_shift(halo, 0, -4, 6, 'zero') +
        (-1769 / 175)
        * _stencil_shift(halo, 1, -4, 6, 'zero') +
        (4469 / 1120)
        * _stencil_shift(halo, 2, -4, 6, 'zero') +
        (-4969 / 5670)
        * _stencil_shift(halo, 3, -4, 6, 'zero') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -4, 6, 'zero') +
        (-19 / 1050)
        * _stencil_shift(halo, 5, -4, 6, 'zero') +
        (479 / 453600)
        * _stencil_shift(halo, 6, -4, 6, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 10, -4, 'zero'] = _fd_d4_a10_axis4_zero


def _fd_d4_a10_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 10, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 6, 'reflect', 4)
    result = (
        (479 / 453600)
        * _stencil_shift(halo, -6, -4, 6, 'reflect') +
        (-19 / 1050)
        * _stencil_shift(halo, -5, -4, 6, 'reflect') +
        (643 / 4200)
        * _stencil_shift(halo, -4, -4, 6, 'reflect') +
        (-4969 / 5670)
        * _stencil_shift(halo, -3, -4, 6, 'reflect') +
        (4469 / 1120)
        * _stencil_shift(halo, -2, -4, 6, 'reflect') +
        (-1769 / 175)
        * _stencil_shift(halo, -1, -4, 6, 'reflect') +
        (37037 / 2700)
        * _stencil_shift(halo, 0, -4, 6, 'reflect') +
        (-1769 / 175)
        * _stencil_shift(halo, 1, -4, 6, 'reflect') +
        (4469 / 1120)
        * _stencil_shift(halo, 2, -4, 6, 'reflect') +
        (-4969 / 5670)
        * _stencil_shift(halo, 3, -4, 6, 'reflect') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -4, 6, 'reflect') +
        (-19 / 1050)
        * _stencil_shift(halo, 5, -4, 6, 'reflect') +
        (479 / 453600)
        * _stencil_shift(halo, 6, -4, 6, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 10, -4, 'reflect'] = _fd_d4_a10_axis4_reflect


def _fd_d4_a10_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 10, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 6, 'periodic', 4)
    result = (
        (479 / 453600)
        * _stencil_shift(halo, -6, -3, 6, 'periodic') +
        (-19 / 1050)
        * _stencil_shift(halo, -5, -3, 6, 'periodic') +
        (643 / 4200)
        * _stencil_shift(halo, -4, -3, 6, 'periodic') +
        (-4969 / 5670)
        * _stencil_shift(halo, -3, -3, 6, 'periodic') +
        (4469 / 1120)
        * _stencil_shift(halo, -2, -3, 6, 'periodic') +
        (-1769 / 175)
        * _stencil_shift(halo, -1, -3, 6, 'periodic') +
        (37037 / 2700)
        * _stencil_shift(halo, 0, -3, 6, 'periodic') +
        (-1769 / 175)
        * _stencil_shift(halo, 1, -3, 6, 'periodic') +
        (4469 / 1120)
        * _stencil_shift(halo, 2, -3, 6, 'periodic') +
        (-4969 / 5670)
        * _stencil_shift(halo, 3, -3, 6, 'periodic') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -3, 6, 'periodic') +
        (-19 / 1050)
        * _stencil_shift(halo, 5, -3, 6, 'periodic') +
        (479 / 453600)
        * _stencil_shift(halo, 6, -3, 6, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 10, -3, 'periodic'] = _fd_d4_a10_axis3_periodic


def _fd_d4_a10_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 10, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 6, 'zero', 4)
    result = (
        (479 / 453600)
        * _stencil_shift(halo, -6, -3, 6, 'zero') +
        (-19 / 1050)
        * _stencil_shift(halo, -5, -3, 6, 'zero') +
        (643 / 4200)
        * _stencil_shift(halo, -4, -3, 6, 'zero') +
        (-4969 / 5670)
        * _stencil_shift(halo, -3, -3, 6, 'zero') +
        (4469 / 1120)
        * _stencil_shift(halo, -2, -3, 6, 'zero') +
        (-1769 / 175)
        * _stencil_shift(halo, -1, -3, 6, 'zero') +
        (37037 / 2700)
        * _stencil_shift(halo, 0, -3, 6, 'zero') +
        (-1769 / 175)
        * _stencil_shift(halo, 1, -3, 6, 'zero') +
        (4469 / 1120)
        * _stencil_shift(halo, 2, -3, 6, 'zero') +
        (-4969 / 5670)
        * _stencil_shift(halo, 3, -3, 6, 'zero') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -3, 6, 'zero') +
        (-19 / 1050)
        * _stencil_shift(halo, 5, -3, 6, 'zero') +
        (479 / 453600)
        * _stencil_shift(halo, 6, -3, 6, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 10, -3, 'zero'] = _fd_d4_a10_axis3_zero


def _fd_d4_a10_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 10, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 6, 'reflect', 4)
    result = (
        (479 / 453600)
        * _stencil_shift(halo, -6, -3, 6, 'reflect') +
        (-19 / 1050)
        * _stencil_shift(halo, -5, -3, 6, 'reflect') +
        (643 / 4200)
        * _stencil_shift(halo, -4, -3, 6, 'reflect') +
        (-4969 / 5670)
        * _stencil_shift(halo, -3, -3, 6, 'reflect') +
        (4469 / 1120)
        * _stencil_shift(halo, -2, -3, 6, 'reflect') +
        (-1769 / 175)
        * _stencil_shift(halo, -1, -3, 6, 'reflect') +
        (37037 / 2700)
        * _stencil_shift(halo, 0, -3, 6, 'reflect') +
        (-1769 / 175)
        * _stencil_shift(halo, 1, -3, 6, 'reflect') +
        (4469 / 1120)
        * _stencil_shift(halo, 2, -3, 6, 'reflect') +
        (-4969 / 5670)
        * _stencil_shift(halo, 3, -3, 6, 'reflect') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -3, 6, 'reflect') +
        (-19 / 1050)
        * _stencil_shift(halo, 5, -3, 6, 'reflect') +
        (479 / 453600)
        * _stencil_shift(halo, 6, -3, 6, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 10, -3, 'reflect'] = _fd_d4_a10_axis3_reflect


def _fd_d4_a10_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 10, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 6, 'periodic', 4)
    result = (
        (479 / 453600)
        * _stencil_shift(halo, -6, -2, 6, 'periodic') +
        (-19 / 1050)
        * _stencil_shift(halo, -5, -2, 6, 'periodic') +
        (643 / 4200)
        * _stencil_shift(halo, -4, -2, 6, 'periodic') +
        (-4969 / 5670)
        * _stencil_shift(halo, -3, -2, 6, 'periodic') +
        (4469 / 1120)
        * _stencil_shift(halo, -2, -2, 6, 'periodic') +
        (-1769 / 175)
        * _stencil_shift(halo, -1, -2, 6, 'periodic') +
        (37037 / 2700)
        * _stencil_shift(halo, 0, -2, 6, 'periodic') +
        (-1769 / 175)
        * _stencil_shift(halo, 1, -2, 6, 'periodic') +
        (4469 / 1120)
        * _stencil_shift(halo, 2, -2, 6, 'periodic') +
        (-4969 / 5670)
        * _stencil_shift(halo, 3, -2, 6, 'periodic') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -2, 6, 'periodic') +
        (-19 / 1050)
        * _stencil_shift(halo, 5, -2, 6, 'periodic') +
        (479 / 453600)
        * _stencil_shift(halo, 6, -2, 6, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 10, -2, 'periodic'] = _fd_d4_a10_axis2_periodic


def _fd_d4_a10_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 10, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 6, 'zero', 4)
    result = (
        (479 / 453600)
        * _stencil_shift(halo, -6, -2, 6, 'zero') +
        (-19 / 1050)
        * _stencil_shift(halo, -5, -2, 6, 'zero') +
        (643 / 4200)
        * _stencil_shift(halo, -4, -2, 6, 'zero') +
        (-4969 / 5670)
        * _stencil_shift(halo, -3, -2, 6, 'zero') +
        (4469 / 1120)
        * _stencil_shift(halo, -2, -2, 6, 'zero') +
        (-1769 / 175)
        * _stencil_shift(halo, -1, -2, 6, 'zero') +
        (37037 / 2700)
        * _stencil_shift(halo, 0, -2, 6, 'zero') +
        (-1769 / 175)
        * _stencil_shift(halo, 1, -2, 6, 'zero') +
        (4469 / 1120)
        * _stencil_shift(halo, 2, -2, 6, 'zero') +
        (-4969 / 5670)
        * _stencil_shift(halo, 3, -2, 6, 'zero') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -2, 6, 'zero') +
        (-19 / 1050)
        * _stencil_shift(halo, 5, -2, 6, 'zero') +
        (479 / 453600)
        * _stencil_shift(halo, 6, -2, 6, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 10, -2, 'zero'] = _fd_d4_a10_axis2_zero


def _fd_d4_a10_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 10, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 6, 'reflect', 4)
    result = (
        (479 / 453600)
        * _stencil_shift(halo, -6, -2, 6, 'reflect') +
        (-19 / 1050)
        * _stencil_shift(halo, -5, -2, 6, 'reflect') +
        (643 / 4200)
        * _stencil_shift(halo, -4, -2, 6, 'reflect') +
        (-4969 / 5670)
        * _stencil_shift(halo, -3, -2, 6, 'reflect') +
        (4469 / 1120)
        * _stencil_shift(halo, -2, -2, 6, 'reflect') +
        (-1769 / 175)
        * _stencil_shift(halo, -1, -2, 6, 'reflect') +
        (37037 / 2700)
        * _stencil_shift(halo, 0, -2, 6, 'reflect') +
        (-1769 / 175)
        * _stencil_shift(halo, 1, -2, 6, 'reflect') +
        (4469 / 1120)
        * _stencil_shift(halo, 2, -2, 6, 'reflect') +
        (-4969 / 5670)
        * _stencil_shift(halo, 3, -2, 6, 'reflect') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -2, 6, 'reflect') +
        (-19 / 1050)
        * _stencil_shift(halo, 5, -2, 6, 'reflect') +
        (479 / 453600)
        * _stencil_shift(halo, 6, -2, 6, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 10, -2, 'reflect'] = _fd_d4_a10_axis2_reflect


def _fd_d4_a10_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 10, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 6, 'periodic', 4)
    result = (
        (479 / 453600)
        * _stencil_shift(halo, -6, -1, 6, 'periodic') +
        (-19 / 1050)
        * _stencil_shift(halo, -5, -1, 6, 'periodic') +
        (643 / 4200)
        * _stencil_shift(halo, -4, -1, 6, 'periodic') +
        (-4969 / 5670)
        * _stencil_shift(halo, -3, -1, 6, 'periodic') +
        (4469 / 1120)
        * _stencil_shift(halo, -2, -1, 6, 'periodic') +
        (-1769 / 175)
        * _stencil_shift(halo, -1, -1, 6, 'periodic') +
        (37037 / 2700)
        * _stencil_shift(halo, 0, -1, 6, 'periodic') +
        (-1769 / 175)
        * _stencil_shift(halo, 1, -1, 6, 'periodic') +
        (4469 / 1120)
        * _stencil_shift(halo, 2, -1, 6, 'periodic') +
        (-4969 / 5670)
        * _stencil_shift(halo, 3, -1, 6, 'periodic') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -1, 6, 'periodic') +
        (-19 / 1050)
        * _stencil_shift(halo, 5, -1, 6, 'periodic') +
        (479 / 453600)
        * _stencil_shift(halo, 6, -1, 6, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 10, -1, 'periodic'] = _fd_d4_a10_axis1_periodic


def _fd_d4_a10_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 10, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 6, 'zero', 4)
    result = (
        (479 / 453600)
        * _stencil_shift(halo, -6, -1, 6, 'zero') +
        (-19 / 1050)
        * _stencil_shift(halo, -5, -1, 6, 'zero') +
        (643 / 4200)
        * _stencil_shift(halo, -4, -1, 6, 'zero') +
        (-4969 / 5670)
        * _stencil_shift(halo, -3, -1, 6, 'zero') +
        (4469 / 1120)
        * _stencil_shift(halo, -2, -1, 6, 'zero') +
        (-1769 / 175)
        * _stencil_shift(halo, -1, -1, 6, 'zero') +
        (37037 / 2700)
        * _stencil_shift(halo, 0, -1, 6, 'zero') +
        (-1769 / 175)
        * _stencil_shift(halo, 1, -1, 6, 'zero') +
        (4469 / 1120)
        * _stencil_shift(halo, 2, -1, 6, 'zero') +
        (-4969 / 5670)
        * _stencil_shift(halo, 3, -1, 6, 'zero') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -1, 6, 'zero') +
        (-19 / 1050)
        * _stencil_shift(halo, 5, -1, 6, 'zero') +
        (479 / 453600)
        * _stencil_shift(halo, 6, -1, 6, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 10, -1, 'zero'] = _fd_d4_a10_axis1_zero


def _fd_d4_a10_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 10, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 12.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 6, 'reflect', 4)
    result = (
        (479 / 453600)
        * _stencil_shift(halo, -6, -1, 6, 'reflect') +
        (-19 / 1050)
        * _stencil_shift(halo, -5, -1, 6, 'reflect') +
        (643 / 4200)
        * _stencil_shift(halo, -4, -1, 6, 'reflect') +
        (-4969 / 5670)
        * _stencil_shift(halo, -3, -1, 6, 'reflect') +
        (4469 / 1120)
        * _stencil_shift(halo, -2, -1, 6, 'reflect') +
        (-1769 / 175)
        * _stencil_shift(halo, -1, -1, 6, 'reflect') +
        (37037 / 2700)
        * _stencil_shift(halo, 0, -1, 6, 'reflect') +
        (-1769 / 175)
        * _stencil_shift(halo, 1, -1, 6, 'reflect') +
        (4469 / 1120)
        * _stencil_shift(halo, 2, -1, 6, 'reflect') +
        (-4969 / 5670)
        * _stencil_shift(halo, 3, -1, 6, 'reflect') +
        (643 / 4200)
        * _stencil_shift(halo, 4, -1, 6, 'reflect') +
        (-19 / 1050)
        * _stencil_shift(halo, 5, -1, 6, 'reflect') +
        (479 / 453600)
        * _stencil_shift(halo, 6, -1, 6, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 10, -1, 'reflect'] = _fd_d4_a10_axis1_reflect


STENCIL_MOMENTS[4, 12] = (
    (-7, -59, 277200),
    (-6, 20137, 4989600),
    (-5, -2077, 55440),
    (-4, 31957, 138600),
    (-3, -247081, 226800),
    (-2, 222581, 50400),
    (-1, -90281, 8400),
    (0, 54613, 3780),
    (1, -90281, 8400),
    (2, 222581, 50400),
    (3, -247081, 226800),
    (4, 31957, 138600),
    (5, -2077, 55440),
    (6, 20137, 4989600),
    (7, -59, 277200),
)

def _fd_d4_a12_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 12, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 7, 'periodic', 4)
    result = (
        (-59 / 277200)
        * _stencil_shift(halo, -7, -4, 7, 'periodic') +
        (20137 / 4989600)
        * _stencil_shift(halo, -6, -4, 7, 'periodic') +
        (-2077 / 55440)
        * _stencil_shift(halo, -5, -4, 7, 'periodic') +
        (31957 / 138600)
        * _stencil_shift(halo, -4, -4, 7, 'periodic') +
        (-247081 / 226800)
        * _stencil_shift(halo, -3, -4, 7, 'periodic') +
        (222581 / 50400)
        * _stencil_shift(halo, -2, -4, 7, 'periodic') +
        (-90281 / 8400)
        * _stencil_shift(halo, -1, -4, 7, 'periodic') +
        (54613 / 3780)
        * _stencil_shift(halo, 0, -4, 7, 'periodic') +
        (-90281 / 8400)
        * _stencil_shift(halo, 1, -4, 7, 'periodic') +
        (222581 / 50400)
        * _stencil_shift(halo, 2, -4, 7, 'periodic') +
        (-247081 / 226800)
        * _stencil_shift(halo, 3, -4, 7, 'periodic') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -4, 7, 'periodic') +
        (-2077 / 55440)
        * _stencil_shift(halo, 5, -4, 7, 'periodic') +
        (20137 / 4989600)
        * _stencil_shift(halo, 6, -4, 7, 'periodic') +
        (-59 / 277200)
        * _stencil_shift(halo, 7, -4, 7, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 12, -4, 'periodic'] = _fd_d4_a12_axis4_periodic


def _fd_d4_a12_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 12, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 7, 'zero', 4)
    result = (
        (-59 / 277200)
        * _stencil_shift(halo, -7, -4, 7, 'zero') +
        (20137 / 4989600)
        * _stencil_shift(halo, -6, -4, 7, 'zero') +
        (-2077 / 55440)
        * _stencil_shift(halo, -5, -4, 7, 'zero') +
        (31957 / 138600)
        * _stencil_shift(halo, -4, -4, 7, 'zero') +
        (-247081 / 226800)
        * _stencil_shift(halo, -3, -4, 7, 'zero') +
        (222581 / 50400)
        * _stencil_shift(halo, -2, -4, 7, 'zero') +
        (-90281 / 8400)
        * _stencil_shift(halo, -1, -4, 7, 'zero') +
        (54613 / 3780)
        * _stencil_shift(halo, 0, -4, 7, 'zero') +
        (-90281 / 8400)
        * _stencil_shift(halo, 1, -4, 7, 'zero') +
        (222581 / 50400)
        * _stencil_shift(halo, 2, -4, 7, 'zero') +
        (-247081 / 226800)
        * _stencil_shift(halo, 3, -4, 7, 'zero') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -4, 7, 'zero') +
        (-2077 / 55440)
        * _stencil_shift(halo, 5, -4, 7, 'zero') +
        (20137 / 4989600)
        * _stencil_shift(halo, 6, -4, 7, 'zero') +
        (-59 / 277200)
        * _stencil_shift(halo, 7, -4, 7, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 12, -4, 'zero'] = _fd_d4_a12_axis4_zero


def _fd_d4_a12_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 12, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 7, 'reflect', 4)
    result = (
        (-59 / 277200)
        * _stencil_shift(halo, -7, -4, 7, 'reflect') +
        (20137 / 4989600)
        * _stencil_shift(halo, -6, -4, 7, 'reflect') +
        (-2077 / 55440)
        * _stencil_shift(halo, -5, -4, 7, 'reflect') +
        (31957 / 138600)
        * _stencil_shift(halo, -4, -4, 7, 'reflect') +
        (-247081 / 226800)
        * _stencil_shift(halo, -3, -4, 7, 'reflect') +
        (222581 / 50400)
        * _stencil_shift(halo, -2, -4, 7, 'reflect') +
        (-90281 / 8400)
        * _stencil_shift(halo, -1, -4, 7, 'reflect') +
        (54613 / 3780)
        * _stencil_shift(halo, 0, -4, 7, 'reflect') +
        (-90281 / 8400)
        * _stencil_shift(halo, 1, -4, 7, 'reflect') +
        (222581 / 50400)
        * _stencil_shift(halo, 2, -4, 7, 'reflect') +
        (-247081 / 226800)
        * _stencil_shift(halo, 3, -4, 7, 'reflect') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -4, 7, 'reflect') +
        (-2077 / 55440)
        * _stencil_shift(halo, 5, -4, 7, 'reflect') +
        (20137 / 4989600)
        * _stencil_shift(halo, 6, -4, 7, 'reflect') +
        (-59 / 277200)
        * _stencil_shift(halo, 7, -4, 7, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 12, -4, 'reflect'] = _fd_d4_a12_axis4_reflect


def _fd_d4_a12_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 12, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 7, 'periodic', 4)
    result = (
        (-59 / 277200)
        * _stencil_shift(halo, -7, -3, 7, 'periodic') +
        (20137 / 4989600)
        * _stencil_shift(halo, -6, -3, 7, 'periodic') +
        (-2077 / 55440)
        * _stencil_shift(halo, -5, -3, 7, 'periodic') +
        (31957 / 138600)
        * _stencil_shift(halo, -4, -3, 7, 'periodic') +
        (-247081 / 226800)
        * _stencil_shift(halo, -3, -3, 7, 'periodic') +
        (222581 / 50400)
        * _stencil_shift(halo, -2, -3, 7, 'periodic') +
        (-90281 / 8400)
        * _stencil_shift(halo, -1, -3, 7, 'periodic') +
        (54613 / 3780)
        * _stencil_shift(halo, 0, -3, 7, 'periodic') +
        (-90281 / 8400)
        * _stencil_shift(halo, 1, -3, 7, 'periodic') +
        (222581 / 50400)
        * _stencil_shift(halo, 2, -3, 7, 'periodic') +
        (-247081 / 226800)
        * _stencil_shift(halo, 3, -3, 7, 'periodic') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -3, 7, 'periodic') +
        (-2077 / 55440)
        * _stencil_shift(halo, 5, -3, 7, 'periodic') +
        (20137 / 4989600)
        * _stencil_shift(halo, 6, -3, 7, 'periodic') +
        (-59 / 277200)
        * _stencil_shift(halo, 7, -3, 7, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 12, -3, 'periodic'] = _fd_d4_a12_axis3_periodic


def _fd_d4_a12_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 12, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 7, 'zero', 4)
    result = (
        (-59 / 277200)
        * _stencil_shift(halo, -7, -3, 7, 'zero') +
        (20137 / 4989600)
        * _stencil_shift(halo, -6, -3, 7, 'zero') +
        (-2077 / 55440)
        * _stencil_shift(halo, -5, -3, 7, 'zero') +
        (31957 / 138600)
        * _stencil_shift(halo, -4, -3, 7, 'zero') +
        (-247081 / 226800)
        * _stencil_shift(halo, -3, -3, 7, 'zero') +
        (222581 / 50400)
        * _stencil_shift(halo, -2, -3, 7, 'zero') +
        (-90281 / 8400)
        * _stencil_shift(halo, -1, -3, 7, 'zero') +
        (54613 / 3780)
        * _stencil_shift(halo, 0, -3, 7, 'zero') +
        (-90281 / 8400)
        * _stencil_shift(halo, 1, -3, 7, 'zero') +
        (222581 / 50400)
        * _stencil_shift(halo, 2, -3, 7, 'zero') +
        (-247081 / 226800)
        * _stencil_shift(halo, 3, -3, 7, 'zero') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -3, 7, 'zero') +
        (-2077 / 55440)
        * _stencil_shift(halo, 5, -3, 7, 'zero') +
        (20137 / 4989600)
        * _stencil_shift(halo, 6, -3, 7, 'zero') +
        (-59 / 277200)
        * _stencil_shift(halo, 7, -3, 7, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 12, -3, 'zero'] = _fd_d4_a12_axis3_zero


def _fd_d4_a12_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 12, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 7, 'reflect', 4)
    result = (
        (-59 / 277200)
        * _stencil_shift(halo, -7, -3, 7, 'reflect') +
        (20137 / 4989600)
        * _stencil_shift(halo, -6, -3, 7, 'reflect') +
        (-2077 / 55440)
        * _stencil_shift(halo, -5, -3, 7, 'reflect') +
        (31957 / 138600)
        * _stencil_shift(halo, -4, -3, 7, 'reflect') +
        (-247081 / 226800)
        * _stencil_shift(halo, -3, -3, 7, 'reflect') +
        (222581 / 50400)
        * _stencil_shift(halo, -2, -3, 7, 'reflect') +
        (-90281 / 8400)
        * _stencil_shift(halo, -1, -3, 7, 'reflect') +
        (54613 / 3780)
        * _stencil_shift(halo, 0, -3, 7, 'reflect') +
        (-90281 / 8400)
        * _stencil_shift(halo, 1, -3, 7, 'reflect') +
        (222581 / 50400)
        * _stencil_shift(halo, 2, -3, 7, 'reflect') +
        (-247081 / 226800)
        * _stencil_shift(halo, 3, -3, 7, 'reflect') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -3, 7, 'reflect') +
        (-2077 / 55440)
        * _stencil_shift(halo, 5, -3, 7, 'reflect') +
        (20137 / 4989600)
        * _stencil_shift(halo, 6, -3, 7, 'reflect') +
        (-59 / 277200)
        * _stencil_shift(halo, 7, -3, 7, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 12, -3, 'reflect'] = _fd_d4_a12_axis3_reflect


def _fd_d4_a12_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 12, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 7, 'periodic', 4)
    result = (
        (-59 / 277200)
        * _stencil_shift(halo, -7, -2, 7, 'periodic') +
        (20137 / 4989600)
        * _stencil_shift(halo, -6, -2, 7, 'periodic') +
        (-2077 / 55440)
        * _stencil_shift(halo, -5, -2, 7, 'periodic') +
        (31957 / 138600)
        * _stencil_shift(halo, -4, -2, 7, 'periodic') +
        (-247081 / 226800)
        * _stencil_shift(halo, -3, -2, 7, 'periodic') +
        (222581 / 50400)
        * _stencil_shift(halo, -2, -2, 7, 'periodic') +
        (-90281 / 8400)
        * _stencil_shift(halo, -1, -2, 7, 'periodic') +
        (54613 / 3780)
        * _stencil_shift(halo, 0, -2, 7, 'periodic') +
        (-90281 / 8400)
        * _stencil_shift(halo, 1, -2, 7, 'periodic') +
        (222581 / 50400)
        * _stencil_shift(halo, 2, -2, 7, 'periodic') +
        (-247081 / 226800)
        * _stencil_shift(halo, 3, -2, 7, 'periodic') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -2, 7, 'periodic') +
        (-2077 / 55440)
        * _stencil_shift(halo, 5, -2, 7, 'periodic') +
        (20137 / 4989600)
        * _stencil_shift(halo, 6, -2, 7, 'periodic') +
        (-59 / 277200)
        * _stencil_shift(halo, 7, -2, 7, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 12, -2, 'periodic'] = _fd_d4_a12_axis2_periodic


def _fd_d4_a12_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 12, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 7, 'zero', 4)
    result = (
        (-59 / 277200)
        * _stencil_shift(halo, -7, -2, 7, 'zero') +
        (20137 / 4989600)
        * _stencil_shift(halo, -6, -2, 7, 'zero') +
        (-2077 / 55440)
        * _stencil_shift(halo, -5, -2, 7, 'zero') +
        (31957 / 138600)
        * _stencil_shift(halo, -4, -2, 7, 'zero') +
        (-247081 / 226800)
        * _stencil_shift(halo, -3, -2, 7, 'zero') +
        (222581 / 50400)
        * _stencil_shift(halo, -2, -2, 7, 'zero') +
        (-90281 / 8400)
        * _stencil_shift(halo, -1, -2, 7, 'zero') +
        (54613 / 3780)
        * _stencil_shift(halo, 0, -2, 7, 'zero') +
        (-90281 / 8400)
        * _stencil_shift(halo, 1, -2, 7, 'zero') +
        (222581 / 50400)
        * _stencil_shift(halo, 2, -2, 7, 'zero') +
        (-247081 / 226800)
        * _stencil_shift(halo, 3, -2, 7, 'zero') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -2, 7, 'zero') +
        (-2077 / 55440)
        * _stencil_shift(halo, 5, -2, 7, 'zero') +
        (20137 / 4989600)
        * _stencil_shift(halo, 6, -2, 7, 'zero') +
        (-59 / 277200)
        * _stencil_shift(halo, 7, -2, 7, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 12, -2, 'zero'] = _fd_d4_a12_axis2_zero


def _fd_d4_a12_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 12, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 7, 'reflect', 4)
    result = (
        (-59 / 277200)
        * _stencil_shift(halo, -7, -2, 7, 'reflect') +
        (20137 / 4989600)
        * _stencil_shift(halo, -6, -2, 7, 'reflect') +
        (-2077 / 55440)
        * _stencil_shift(halo, -5, -2, 7, 'reflect') +
        (31957 / 138600)
        * _stencil_shift(halo, -4, -2, 7, 'reflect') +
        (-247081 / 226800)
        * _stencil_shift(halo, -3, -2, 7, 'reflect') +
        (222581 / 50400)
        * _stencil_shift(halo, -2, -2, 7, 'reflect') +
        (-90281 / 8400)
        * _stencil_shift(halo, -1, -2, 7, 'reflect') +
        (54613 / 3780)
        * _stencil_shift(halo, 0, -2, 7, 'reflect') +
        (-90281 / 8400)
        * _stencil_shift(halo, 1, -2, 7, 'reflect') +
        (222581 / 50400)
        * _stencil_shift(halo, 2, -2, 7, 'reflect') +
        (-247081 / 226800)
        * _stencil_shift(halo, 3, -2, 7, 'reflect') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -2, 7, 'reflect') +
        (-2077 / 55440)
        * _stencil_shift(halo, 5, -2, 7, 'reflect') +
        (20137 / 4989600)
        * _stencil_shift(halo, 6, -2, 7, 'reflect') +
        (-59 / 277200)
        * _stencil_shift(halo, 7, -2, 7, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 12, -2, 'reflect'] = _fd_d4_a12_axis2_reflect


def _fd_d4_a12_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 12, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 7, 'periodic', 4)
    result = (
        (-59 / 277200)
        * _stencil_shift(halo, -7, -1, 7, 'periodic') +
        (20137 / 4989600)
        * _stencil_shift(halo, -6, -1, 7, 'periodic') +
        (-2077 / 55440)
        * _stencil_shift(halo, -5, -1, 7, 'periodic') +
        (31957 / 138600)
        * _stencil_shift(halo, -4, -1, 7, 'periodic') +
        (-247081 / 226800)
        * _stencil_shift(halo, -3, -1, 7, 'periodic') +
        (222581 / 50400)
        * _stencil_shift(halo, -2, -1, 7, 'periodic') +
        (-90281 / 8400)
        * _stencil_shift(halo, -1, -1, 7, 'periodic') +
        (54613 / 3780)
        * _stencil_shift(halo, 0, -1, 7, 'periodic') +
        (-90281 / 8400)
        * _stencil_shift(halo, 1, -1, 7, 'periodic') +
        (222581 / 50400)
        * _stencil_shift(halo, 2, -1, 7, 'periodic') +
        (-247081 / 226800)
        * _stencil_shift(halo, 3, -1, 7, 'periodic') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -1, 7, 'periodic') +
        (-2077 / 55440)
        * _stencil_shift(halo, 5, -1, 7, 'periodic') +
        (20137 / 4989600)
        * _stencil_shift(halo, 6, -1, 7, 'periodic') +
        (-59 / 277200)
        * _stencil_shift(halo, 7, -1, 7, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 12, -1, 'periodic'] = _fd_d4_a12_axis1_periodic


def _fd_d4_a12_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 12, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 7, 'zero', 4)
    result = (
        (-59 / 277200)
        * _stencil_shift(halo, -7, -1, 7, 'zero') +
        (20137 / 4989600)
        * _stencil_shift(halo, -6, -1, 7, 'zero') +
        (-2077 / 55440)
        * _stencil_shift(halo, -5, -1, 7, 'zero') +
        (31957 / 138600)
        * _stencil_shift(halo, -4, -1, 7, 'zero') +
        (-247081 / 226800)
        * _stencil_shift(halo, -3, -1, 7, 'zero') +
        (222581 / 50400)
        * _stencil_shift(halo, -2, -1, 7, 'zero') +
        (-90281 / 8400)
        * _stencil_shift(halo, -1, -1, 7, 'zero') +
        (54613 / 3780)
        * _stencil_shift(halo, 0, -1, 7, 'zero') +
        (-90281 / 8400)
        * _stencil_shift(halo, 1, -1, 7, 'zero') +
        (222581 / 50400)
        * _stencil_shift(halo, 2, -1, 7, 'zero') +
        (-247081 / 226800)
        * _stencil_shift(halo, 3, -1, 7, 'zero') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -1, 7, 'zero') +
        (-2077 / 55440)
        * _stencil_shift(halo, 5, -1, 7, 'zero') +
        (20137 / 4989600)
        * _stencil_shift(halo, 6, -1, 7, 'zero') +
        (-59 / 277200)
        * _stencil_shift(halo, 7, -1, 7, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 12, -1, 'zero'] = _fd_d4_a12_axis1_zero


def _fd_d4_a12_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 12, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 14.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 7, 'reflect', 4)
    result = (
        (-59 / 277200)
        * _stencil_shift(halo, -7, -1, 7, 'reflect') +
        (20137 / 4989600)
        * _stencil_shift(halo, -6, -1, 7, 'reflect') +
        (-2077 / 55440)
        * _stencil_shift(halo, -5, -1, 7, 'reflect') +
        (31957 / 138600)
        * _stencil_shift(halo, -4, -1, 7, 'reflect') +
        (-247081 / 226800)
        * _stencil_shift(halo, -3, -1, 7, 'reflect') +
        (222581 / 50400)
        * _stencil_shift(halo, -2, -1, 7, 'reflect') +
        (-90281 / 8400)
        * _stencil_shift(halo, -1, -1, 7, 'reflect') +
        (54613 / 3780)
        * _stencil_shift(halo, 0, -1, 7, 'reflect') +
        (-90281 / 8400)
        * _stencil_shift(halo, 1, -1, 7, 'reflect') +
        (222581 / 50400)
        * _stencil_shift(halo, 2, -1, 7, 'reflect') +
        (-247081 / 226800)
        * _stencil_shift(halo, 3, -1, 7, 'reflect') +
        (31957 / 138600)
        * _stencil_shift(halo, 4, -1, 7, 'reflect') +
        (-2077 / 55440)
        * _stencil_shift(halo, 5, -1, 7, 'reflect') +
        (20137 / 4989600)
        * _stencil_shift(halo, 6, -1, 7, 'reflect') +
        (-59 / 277200)
        * _stencil_shift(halo, 7, -1, 7, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 12, -1, 'reflect'] = _fd_d4_a12_axis1_reflect


STENCIL_MOMENTS[4, 14] = (
    (-8, 266681, 6054048000),
    (-7, -21701, 23648625),
    (-6, 1058149, 113513400),
    (-5, -41981, 675675),
    (-4, 1033649, 3326400),
    (-3, -999349, 779625),
    (-2, 901349, 189000),
    (-1, -372149, 33075),
    (0, 63566689, 4233600),
    (1, -372149, 33075),
    (2, 901349, 189000),
    (3, -999349, 779625),
    (4, 1033649, 3326400),
    (5, -41981, 675675),
    (6, 1058149, 113513400),
    (7, -21701, 23648625),
    (8, 266681, 6054048000),
)

def _fd_d4_a14_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 14, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 8, 'periodic', 4)
    result = (
        (266681 / 6054048000)
        * _stencil_shift(halo, -8, -4, 8, 'periodic') +
        (-21701 / 23648625)
        * _stencil_shift(halo, -7, -4, 8, 'periodic') +
        (1058149 / 113513400)
        * _stencil_shift(halo, -6, -4, 8, 'periodic') +
        (-41981 / 675675)
        * _stencil_shift(halo, -5, -4, 8, 'periodic') +
        (1033649 / 3326400)
        * _stencil_shift(halo, -4, -4, 8, 'periodic') +
        (-999349 / 779625)
        * _stencil_shift(halo, -3, -4, 8, 'periodic') +
        (901349 / 189000)
        * _stencil_shift(halo, -2, -4, 8, 'periodic') +
        (-372149 / 33075)
        * _stencil_shift(halo, -1, -4, 8, 'periodic') +
        (63566689 / 4233600)
        * _stencil_shift(halo, 0, -4, 8, 'periodic') +
        (-372149 / 33075)
        * _stencil_shift(halo, 1, -4, 8, 'periodic') +
        (901349 / 189000)
        * _stencil_shift(halo, 2, -4, 8, 'periodic') +
        (-999349 / 779625)
        * _stencil_shift(halo, 3, -4, 8, 'periodic') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -4, 8, 'periodic') +
        (-41981 / 675675)
        * _stencil_shift(halo, 5, -4, 8, 'periodic') +
        (1058149 / 113513400)
        * _stencil_shift(halo, 6, -4, 8, 'periodic') +
        (-21701 / 23648625)
        * _stencil_shift(halo, 7, -4, 8, 'periodic') +
        (266681 / 6054048000)
        * _stencil_shift(halo, 8, -4, 8, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 14, -4, 'periodic'] = _fd_d4_a14_axis4_periodic


def _fd_d4_a14_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 14, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 8, 'zero', 4)
    result = (
        (266681 / 6054048000)
        * _stencil_shift(halo, -8, -4, 8, 'zero') +
        (-21701 / 23648625)
        * _stencil_shift(halo, -7, -4, 8, 'zero') +
        (1058149 / 113513400)
        * _stencil_shift(halo, -6, -4, 8, 'zero') +
        (-41981 / 675675)
        * _stencil_shift(halo, -5, -4, 8, 'zero') +
        (1033649 / 3326400)
        * _stencil_shift(halo, -4, -4, 8, 'zero') +
        (-999349 / 779625)
        * _stencil_shift(halo, -3, -4, 8, 'zero') +
        (901349 / 189000)
        * _stencil_shift(halo, -2, -4, 8, 'zero') +
        (-372149 / 33075)
        * _stencil_shift(halo, -1, -4, 8, 'zero') +
        (63566689 / 4233600)
        * _stencil_shift(halo, 0, -4, 8, 'zero') +
        (-372149 / 33075)
        * _stencil_shift(halo, 1, -4, 8, 'zero') +
        (901349 / 189000)
        * _stencil_shift(halo, 2, -4, 8, 'zero') +
        (-999349 / 779625)
        * _stencil_shift(halo, 3, -4, 8, 'zero') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -4, 8, 'zero') +
        (-41981 / 675675)
        * _stencil_shift(halo, 5, -4, 8, 'zero') +
        (1058149 / 113513400)
        * _stencil_shift(halo, 6, -4, 8, 'zero') +
        (-21701 / 23648625)
        * _stencil_shift(halo, 7, -4, 8, 'zero') +
        (266681 / 6054048000)
        * _stencil_shift(halo, 8, -4, 8, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 14, -4, 'zero'] = _fd_d4_a14_axis4_zero


def _fd_d4_a14_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 14, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 8, 'reflect', 4)
    result = (
        (266681 / 6054048000)
        * _stencil_shift(halo, -8, -4, 8, 'reflect') +
        (-21701 / 23648625)
        * _stencil_shift(halo, -7, -4, 8, 'reflect') +
        (1058149 / 113513400)
        * _stencil_shift(halo, -6, -4, 8, 'reflect') +
        (-41981 / 675675)
        * _stencil_shift(halo, -5, -4, 8, 'reflect') +
        (1033649 / 3326400)
        * _stencil_shift(halo, -4, -4, 8, 'reflect') +
        (-999349 / 779625)
        * _stencil_shift(halo, -3, -4, 8, 'reflect') +
        (901349 / 189000)
        * _stencil_shift(halo, -2, -4, 8, 'reflect') +
        (-372149 / 33075)
        * _stencil_shift(halo, -1, -4, 8, 'reflect') +
        (63566689 / 4233600)
        * _stencil_shift(halo, 0, -4, 8, 'reflect') +
        (-372149 / 33075)
        * _stencil_shift(halo, 1, -4, 8, 'reflect') +
        (901349 / 189000)
        * _stencil_shift(halo, 2, -4, 8, 'reflect') +
        (-999349 / 779625)
        * _stencil_shift(halo, 3, -4, 8, 'reflect') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -4, 8, 'reflect') +
        (-41981 / 675675)
        * _stencil_shift(halo, 5, -4, 8, 'reflect') +
        (1058149 / 113513400)
        * _stencil_shift(halo, 6, -4, 8, 'reflect') +
        (-21701 / 23648625)
        * _stencil_shift(halo, 7, -4, 8, 'reflect') +
        (266681 / 6054048000)
        * _stencil_shift(halo, 8, -4, 8, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 14, -4, 'reflect'] = _fd_d4_a14_axis4_reflect


def _fd_d4_a14_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 14, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 8, 'periodic', 4)
    result = (
        (266681 / 6054048000)
        * _stencil_shift(halo, -8, -3, 8, 'periodic') +
        (-21701 / 23648625)
        * _stencil_shift(halo, -7, -3, 8, 'periodic') +
        (1058149 / 113513400)
        * _stencil_shift(halo, -6, -3, 8, 'periodic') +
        (-41981 / 675675)
        * _stencil_shift(halo, -5, -3, 8, 'periodic') +
        (1033649 / 3326400)
        * _stencil_shift(halo, -4, -3, 8, 'periodic') +
        (-999349 / 779625)
        * _stencil_shift(halo, -3, -3, 8, 'periodic') +
        (901349 / 189000)
        * _stencil_shift(halo, -2, -3, 8, 'periodic') +
        (-372149 / 33075)
        * _stencil_shift(halo, -1, -3, 8, 'periodic') +
        (63566689 / 4233600)
        * _stencil_shift(halo, 0, -3, 8, 'periodic') +
        (-372149 / 33075)
        * _stencil_shift(halo, 1, -3, 8, 'periodic') +
        (901349 / 189000)
        * _stencil_shift(halo, 2, -3, 8, 'periodic') +
        (-999349 / 779625)
        * _stencil_shift(halo, 3, -3, 8, 'periodic') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -3, 8, 'periodic') +
        (-41981 / 675675)
        * _stencil_shift(halo, 5, -3, 8, 'periodic') +
        (1058149 / 113513400)
        * _stencil_shift(halo, 6, -3, 8, 'periodic') +
        (-21701 / 23648625)
        * _stencil_shift(halo, 7, -3, 8, 'periodic') +
        (266681 / 6054048000)
        * _stencil_shift(halo, 8, -3, 8, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 14, -3, 'periodic'] = _fd_d4_a14_axis3_periodic


def _fd_d4_a14_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 14, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 8, 'zero', 4)
    result = (
        (266681 / 6054048000)
        * _stencil_shift(halo, -8, -3, 8, 'zero') +
        (-21701 / 23648625)
        * _stencil_shift(halo, -7, -3, 8, 'zero') +
        (1058149 / 113513400)
        * _stencil_shift(halo, -6, -3, 8, 'zero') +
        (-41981 / 675675)
        * _stencil_shift(halo, -5, -3, 8, 'zero') +
        (1033649 / 3326400)
        * _stencil_shift(halo, -4, -3, 8, 'zero') +
        (-999349 / 779625)
        * _stencil_shift(halo, -3, -3, 8, 'zero') +
        (901349 / 189000)
        * _stencil_shift(halo, -2, -3, 8, 'zero') +
        (-372149 / 33075)
        * _stencil_shift(halo, -1, -3, 8, 'zero') +
        (63566689 / 4233600)
        * _stencil_shift(halo, 0, -3, 8, 'zero') +
        (-372149 / 33075)
        * _stencil_shift(halo, 1, -3, 8, 'zero') +
        (901349 / 189000)
        * _stencil_shift(halo, 2, -3, 8, 'zero') +
        (-999349 / 779625)
        * _stencil_shift(halo, 3, -3, 8, 'zero') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -3, 8, 'zero') +
        (-41981 / 675675)
        * _stencil_shift(halo, 5, -3, 8, 'zero') +
        (1058149 / 113513400)
        * _stencil_shift(halo, 6, -3, 8, 'zero') +
        (-21701 / 23648625)
        * _stencil_shift(halo, 7, -3, 8, 'zero') +
        (266681 / 6054048000)
        * _stencil_shift(halo, 8, -3, 8, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 14, -3, 'zero'] = _fd_d4_a14_axis3_zero


def _fd_d4_a14_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 14, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 8, 'reflect', 4)
    result = (
        (266681 / 6054048000)
        * _stencil_shift(halo, -8, -3, 8, 'reflect') +
        (-21701 / 23648625)
        * _stencil_shift(halo, -7, -3, 8, 'reflect') +
        (1058149 / 113513400)
        * _stencil_shift(halo, -6, -3, 8, 'reflect') +
        (-41981 / 675675)
        * _stencil_shift(halo, -5, -3, 8, 'reflect') +
        (1033649 / 3326400)
        * _stencil_shift(halo, -4, -3, 8, 'reflect') +
        (-999349 / 779625)
        * _stencil_shift(halo, -3, -3, 8, 'reflect') +
        (901349 / 189000)
        * _stencil_shift(halo, -2, -3, 8, 'reflect') +
        (-372149 / 33075)
        * _stencil_shift(halo, -1, -3, 8, 'reflect') +
        (63566689 / 4233600)
        * _stencil_shift(halo, 0, -3, 8, 'reflect') +
        (-372149 / 33075)
        * _stencil_shift(halo, 1, -3, 8, 'reflect') +
        (901349 / 189000)
        * _stencil_shift(halo, 2, -3, 8, 'reflect') +
        (-999349 / 779625)
        * _stencil_shift(halo, 3, -3, 8, 'reflect') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -3, 8, 'reflect') +
        (-41981 / 675675)
        * _stencil_shift(halo, 5, -3, 8, 'reflect') +
        (1058149 / 113513400)
        * _stencil_shift(halo, 6, -3, 8, 'reflect') +
        (-21701 / 23648625)
        * _stencil_shift(halo, 7, -3, 8, 'reflect') +
        (266681 / 6054048000)
        * _stencil_shift(halo, 8, -3, 8, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 14, -3, 'reflect'] = _fd_d4_a14_axis3_reflect


def _fd_d4_a14_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 14, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 8, 'periodic', 4)
    result = (
        (266681 / 6054048000)
        * _stencil_shift(halo, -8, -2, 8, 'periodic') +
        (-21701 / 23648625)
        * _stencil_shift(halo, -7, -2, 8, 'periodic') +
        (1058149 / 113513400)
        * _stencil_shift(halo, -6, -2, 8, 'periodic') +
        (-41981 / 675675)
        * _stencil_shift(halo, -5, -2, 8, 'periodic') +
        (1033649 / 3326400)
        * _stencil_shift(halo, -4, -2, 8, 'periodic') +
        (-999349 / 779625)
        * _stencil_shift(halo, -3, -2, 8, 'periodic') +
        (901349 / 189000)
        * _stencil_shift(halo, -2, -2, 8, 'periodic') +
        (-372149 / 33075)
        * _stencil_shift(halo, -1, -2, 8, 'periodic') +
        (63566689 / 4233600)
        * _stencil_shift(halo, 0, -2, 8, 'periodic') +
        (-372149 / 33075)
        * _stencil_shift(halo, 1, -2, 8, 'periodic') +
        (901349 / 189000)
        * _stencil_shift(halo, 2, -2, 8, 'periodic') +
        (-999349 / 779625)
        * _stencil_shift(halo, 3, -2, 8, 'periodic') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -2, 8, 'periodic') +
        (-41981 / 675675)
        * _stencil_shift(halo, 5, -2, 8, 'periodic') +
        (1058149 / 113513400)
        * _stencil_shift(halo, 6, -2, 8, 'periodic') +
        (-21701 / 23648625)
        * _stencil_shift(halo, 7, -2, 8, 'periodic') +
        (266681 / 6054048000)
        * _stencil_shift(halo, 8, -2, 8, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 14, -2, 'periodic'] = _fd_d4_a14_axis2_periodic


def _fd_d4_a14_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 14, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 8, 'zero', 4)
    result = (
        (266681 / 6054048000)
        * _stencil_shift(halo, -8, -2, 8, 'zero') +
        (-21701 / 23648625)
        * _stencil_shift(halo, -7, -2, 8, 'zero') +
        (1058149 / 113513400)
        * _stencil_shift(halo, -6, -2, 8, 'zero') +
        (-41981 / 675675)
        * _stencil_shift(halo, -5, -2, 8, 'zero') +
        (1033649 / 3326400)
        * _stencil_shift(halo, -4, -2, 8, 'zero') +
        (-999349 / 779625)
        * _stencil_shift(halo, -3, -2, 8, 'zero') +
        (901349 / 189000)
        * _stencil_shift(halo, -2, -2, 8, 'zero') +
        (-372149 / 33075)
        * _stencil_shift(halo, -1, -2, 8, 'zero') +
        (63566689 / 4233600)
        * _stencil_shift(halo, 0, -2, 8, 'zero') +
        (-372149 / 33075)
        * _stencil_shift(halo, 1, -2, 8, 'zero') +
        (901349 / 189000)
        * _stencil_shift(halo, 2, -2, 8, 'zero') +
        (-999349 / 779625)
        * _stencil_shift(halo, 3, -2, 8, 'zero') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -2, 8, 'zero') +
        (-41981 / 675675)
        * _stencil_shift(halo, 5, -2, 8, 'zero') +
        (1058149 / 113513400)
        * _stencil_shift(halo, 6, -2, 8, 'zero') +
        (-21701 / 23648625)
        * _stencil_shift(halo, 7, -2, 8, 'zero') +
        (266681 / 6054048000)
        * _stencil_shift(halo, 8, -2, 8, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 14, -2, 'zero'] = _fd_d4_a14_axis2_zero


def _fd_d4_a14_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 14, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 8, 'reflect', 4)
    result = (
        (266681 / 6054048000)
        * _stencil_shift(halo, -8, -2, 8, 'reflect') +
        (-21701 / 23648625)
        * _stencil_shift(halo, -7, -2, 8, 'reflect') +
        (1058149 / 113513400)
        * _stencil_shift(halo, -6, -2, 8, 'reflect') +
        (-41981 / 675675)
        * _stencil_shift(halo, -5, -2, 8, 'reflect') +
        (1033649 / 3326400)
        * _stencil_shift(halo, -4, -2, 8, 'reflect') +
        (-999349 / 779625)
        * _stencil_shift(halo, -3, -2, 8, 'reflect') +
        (901349 / 189000)
        * _stencil_shift(halo, -2, -2, 8, 'reflect') +
        (-372149 / 33075)
        * _stencil_shift(halo, -1, -2, 8, 'reflect') +
        (63566689 / 4233600)
        * _stencil_shift(halo, 0, -2, 8, 'reflect') +
        (-372149 / 33075)
        * _stencil_shift(halo, 1, -2, 8, 'reflect') +
        (901349 / 189000)
        * _stencil_shift(halo, 2, -2, 8, 'reflect') +
        (-999349 / 779625)
        * _stencil_shift(halo, 3, -2, 8, 'reflect') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -2, 8, 'reflect') +
        (-41981 / 675675)
        * _stencil_shift(halo, 5, -2, 8, 'reflect') +
        (1058149 / 113513400)
        * _stencil_shift(halo, 6, -2, 8, 'reflect') +
        (-21701 / 23648625)
        * _stencil_shift(halo, 7, -2, 8, 'reflect') +
        (266681 / 6054048000)
        * _stencil_shift(halo, 8, -2, 8, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 14, -2, 'reflect'] = _fd_d4_a14_axis2_reflect


def _fd_d4_a14_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 14, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 8, 'periodic', 4)
    result = (
        (266681 / 6054048000)
        * _stencil_shift(halo, -8, -1, 8, 'periodic') +
        (-21701 / 23648625)
        * _stencil_shift(halo, -7, -1, 8, 'periodic') +
        (1058149 / 113513400)
        * _stencil_shift(halo, -6, -1, 8, 'periodic') +
        (-41981 / 675675)
        * _stencil_shift(halo, -5, -1, 8, 'periodic') +
        (1033649 / 3326400)
        * _stencil_shift(halo, -4, -1, 8, 'periodic') +
        (-999349 / 779625)
        * _stencil_shift(halo, -3, -1, 8, 'periodic') +
        (901349 / 189000)
        * _stencil_shift(halo, -2, -1, 8, 'periodic') +
        (-372149 / 33075)
        * _stencil_shift(halo, -1, -1, 8, 'periodic') +
        (63566689 / 4233600)
        * _stencil_shift(halo, 0, -1, 8, 'periodic') +
        (-372149 / 33075)
        * _stencil_shift(halo, 1, -1, 8, 'periodic') +
        (901349 / 189000)
        * _stencil_shift(halo, 2, -1, 8, 'periodic') +
        (-999349 / 779625)
        * _stencil_shift(halo, 3, -1, 8, 'periodic') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -1, 8, 'periodic') +
        (-41981 / 675675)
        * _stencil_shift(halo, 5, -1, 8, 'periodic') +
        (1058149 / 113513400)
        * _stencil_shift(halo, 6, -1, 8, 'periodic') +
        (-21701 / 23648625)
        * _stencil_shift(halo, 7, -1, 8, 'periodic') +
        (266681 / 6054048000)
        * _stencil_shift(halo, 8, -1, 8, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 14, -1, 'periodic'] = _fd_d4_a14_axis1_periodic


def _fd_d4_a14_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 14, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 8, 'zero', 4)
    result = (
        (266681 / 6054048000)
        * _stencil_shift(halo, -8, -1, 8, 'zero') +
        (-21701 / 23648625)
        * _stencil_shift(halo, -7, -1, 8, 'zero') +
        (1058149 / 113513400)
        * _stencil_shift(halo, -6, -1, 8, 'zero') +
        (-41981 / 675675)
        * _stencil_shift(halo, -5, -1, 8, 'zero') +
        (1033649 / 3326400)
        * _stencil_shift(halo, -4, -1, 8, 'zero') +
        (-999349 / 779625)
        * _stencil_shift(halo, -3, -1, 8, 'zero') +
        (901349 / 189000)
        * _stencil_shift(halo, -2, -1, 8, 'zero') +
        (-372149 / 33075)
        * _stencil_shift(halo, -1, -1, 8, 'zero') +
        (63566689 / 4233600)
        * _stencil_shift(halo, 0, -1, 8, 'zero') +
        (-372149 / 33075)
        * _stencil_shift(halo, 1, -1, 8, 'zero') +
        (901349 / 189000)
        * _stencil_shift(halo, 2, -1, 8, 'zero') +
        (-999349 / 779625)
        * _stencil_shift(halo, 3, -1, 8, 'zero') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -1, 8, 'zero') +
        (-41981 / 675675)
        * _stencil_shift(halo, 5, -1, 8, 'zero') +
        (1058149 / 113513400)
        * _stencil_shift(halo, 6, -1, 8, 'zero') +
        (-21701 / 23648625)
        * _stencil_shift(halo, 7, -1, 8, 'zero') +
        (266681 / 6054048000)
        * _stencil_shift(halo, 8, -1, 8, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 14, -1, 'zero'] = _fd_d4_a14_axis1_zero


def _fd_d4_a14_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 14, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 16.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 8, 'reflect', 4)
    result = (
        (266681 / 6054048000)
        * _stencil_shift(halo, -8, -1, 8, 'reflect') +
        (-21701 / 23648625)
        * _stencil_shift(halo, -7, -1, 8, 'reflect') +
        (1058149 / 113513400)
        * _stencil_shift(halo, -6, -1, 8, 'reflect') +
        (-41981 / 675675)
        * _stencil_shift(halo, -5, -1, 8, 'reflect') +
        (1033649 / 3326400)
        * _stencil_shift(halo, -4, -1, 8, 'reflect') +
        (-999349 / 779625)
        * _stencil_shift(halo, -3, -1, 8, 'reflect') +
        (901349 / 189000)
        * _stencil_shift(halo, -2, -1, 8, 'reflect') +
        (-372149 / 33075)
        * _stencil_shift(halo, -1, -1, 8, 'reflect') +
        (63566689 / 4233600)
        * _stencil_shift(halo, 0, -1, 8, 'reflect') +
        (-372149 / 33075)
        * _stencil_shift(halo, 1, -1, 8, 'reflect') +
        (901349 / 189000)
        * _stencil_shift(halo, 2, -1, 8, 'reflect') +
        (-999349 / 779625)
        * _stencil_shift(halo, 3, -1, 8, 'reflect') +
        (1033649 / 3326400)
        * _stencil_shift(halo, 4, -1, 8, 'reflect') +
        (-41981 / 675675)
        * _stencil_shift(halo, 5, -1, 8, 'reflect') +
        (1058149 / 113513400)
        * _stencil_shift(halo, 6, -1, 8, 'reflect') +
        (-21701 / 23648625)
        * _stencil_shift(halo, 7, -1, 8, 'reflect') +
        (266681 / 6054048000)
        * _stencil_shift(halo, 8, -1, 8, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 14, -1, 'reflect'] = _fd_d4_a14_axis1_reflect


STENCIL_MOMENTS[4, 16] = (
    (-9, -63397, 6810804000),
    (-8, 10949, 51744000),
    (-7, -196909, 84084000),
    (-6, 9601741, 567567000),
    (-5, -5861, 64680),
    (-4, 9381241, 24024000),
    (-3, -9072541, 6237000),
    (-2, 8190541, 1617000),
    (-1, -3427741, 294000),
    (0, 117868837, 7620480),
    (1, -3427741, 294000),
    (2, 8190541, 1617000),
    (3, -9072541, 6237000),
    (4, 9381241, 24024000),
    (5, -5861, 64680),
    (6, 9601741, 567567000),
    (7, -196909, 84084000),
    (8, 10949, 51744000),
    (9, -63397, 6810804000),
)

def _fd_d4_a16_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 16, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 9, 'periodic', 4)
    result = (
        (-63397 / 6810804000)
        * _stencil_shift(halo, -9, -4, 9, 'periodic') +
        (10949 / 51744000)
        * _stencil_shift(halo, -8, -4, 9, 'periodic') +
        (-196909 / 84084000)
        * _stencil_shift(halo, -7, -4, 9, 'periodic') +
        (9601741 / 567567000)
        * _stencil_shift(halo, -6, -4, 9, 'periodic') +
        (-5861 / 64680)
        * _stencil_shift(halo, -5, -4, 9, 'periodic') +
        (9381241 / 24024000)
        * _stencil_shift(halo, -4, -4, 9, 'periodic') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, -3, -4, 9, 'periodic') +
        (8190541 / 1617000)
        * _stencil_shift(halo, -2, -4, 9, 'periodic') +
        (-3427741 / 294000)
        * _stencil_shift(halo, -1, -4, 9, 'periodic') +
        (117868837 / 7620480)
        * _stencil_shift(halo, 0, -4, 9, 'periodic') +
        (-3427741 / 294000)
        * _stencil_shift(halo, 1, -4, 9, 'periodic') +
        (8190541 / 1617000)
        * _stencil_shift(halo, 2, -4, 9, 'periodic') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, 3, -4, 9, 'periodic') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -4, 9, 'periodic') +
        (-5861 / 64680)
        * _stencil_shift(halo, 5, -4, 9, 'periodic') +
        (9601741 / 567567000)
        * _stencil_shift(halo, 6, -4, 9, 'periodic') +
        (-196909 / 84084000)
        * _stencil_shift(halo, 7, -4, 9, 'periodic') +
        (10949 / 51744000)
        * _stencil_shift(halo, 8, -4, 9, 'periodic') +
        (-63397 / 6810804000)
        * _stencil_shift(halo, 9, -4, 9, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 16, -4, 'periodic'] = _fd_d4_a16_axis4_periodic


def _fd_d4_a16_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 16, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 9, 'zero', 4)
    result = (
        (-63397 / 6810804000)
        * _stencil_shift(halo, -9, -4, 9, 'zero') +
        (10949 / 51744000)
        * _stencil_shift(halo, -8, -4, 9, 'zero') +
        (-196909 / 84084000)
        * _stencil_shift(halo, -7, -4, 9, 'zero') +
        (9601741 / 567567000)
        * _stencil_shift(halo, -6, -4, 9, 'zero') +
        (-5861 / 64680)
        * _stencil_shift(halo, -5, -4, 9, 'zero') +
        (9381241 / 24024000)
        * _stencil_shift(halo, -4, -4, 9, 'zero') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, -3, -4, 9, 'zero') +
        (8190541 / 1617000)
        * _stencil_shift(halo, -2, -4, 9, 'zero') +
        (-3427741 / 294000)
        * _stencil_shift(halo, -1, -4, 9, 'zero') +
        (117868837 / 7620480)
        * _stencil_shift(halo, 0, -4, 9, 'zero') +
        (-3427741 / 294000)
        * _stencil_shift(halo, 1, -4, 9, 'zero') +
        (8190541 / 1617000)
        * _stencil_shift(halo, 2, -4, 9, 'zero') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, 3, -4, 9, 'zero') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -4, 9, 'zero') +
        (-5861 / 64680)
        * _stencil_shift(halo, 5, -4, 9, 'zero') +
        (9601741 / 567567000)
        * _stencil_shift(halo, 6, -4, 9, 'zero') +
        (-196909 / 84084000)
        * _stencil_shift(halo, 7, -4, 9, 'zero') +
        (10949 / 51744000)
        * _stencil_shift(halo, 8, -4, 9, 'zero') +
        (-63397 / 6810804000)
        * _stencil_shift(halo, 9, -4, 9, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 16, -4, 'zero'] = _fd_d4_a16_axis4_zero


def _fd_d4_a16_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 16, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 9, 'reflect', 4)
    result = (
        (-63397 / 6810804000)
        * _stencil_shift(halo, -9, -4, 9, 'reflect') +
        (10949 / 51744000)
        * _stencil_shift(halo, -8, -4, 9, 'reflect') +
        (-196909 / 84084000)
        * _stencil_shift(halo, -7, -4, 9, 'reflect') +
        (9601741 / 567567000)
        * _stencil_shift(halo, -6, -4, 9, 'reflect') +
        (-5861 / 64680)
        * _stencil_shift(halo, -5, -4, 9, 'reflect') +
        (9381241 / 24024000)
        * _stencil_shift(halo, -4, -4, 9, 'reflect') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, -3, -4, 9, 'reflect') +
        (8190541 / 1617000)
        * _stencil_shift(halo, -2, -4, 9, 'reflect') +
        (-3427741 / 294000)
        * _stencil_shift(halo, -1, -4, 9, 'reflect') +
        (117868837 / 7620480)
        * _stencil_shift(halo, 0, -4, 9, 'reflect') +
        (-3427741 / 294000)
        * _stencil_shift(halo, 1, -4, 9, 'reflect') +
        (8190541 / 1617000)
        * _stencil_shift(halo, 2, -4, 9, 'reflect') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, 3, -4, 9, 'reflect') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -4, 9, 'reflect') +
        (-5861 / 64680)
        * _stencil_shift(halo, 5, -4, 9, 'reflect') +
        (9601741 / 567567000)
        * _stencil_shift(halo, 6, -4, 9, 'reflect') +
        (-196909 / 84084000)
        * _stencil_shift(halo, 7, -4, 9, 'reflect') +
        (10949 / 51744000)
        * _stencil_shift(halo, 8, -4, 9, 'reflect') +
        (-63397 / 6810804000)
        * _stencil_shift(halo, 9, -4, 9, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 16, -4, 'reflect'] = _fd_d4_a16_axis4_reflect


def _fd_d4_a16_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 16, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 9, 'periodic', 4)
    result = (
        (-63397 / 6810804000)
        * _stencil_shift(halo, -9, -3, 9, 'periodic') +
        (10949 / 51744000)
        * _stencil_shift(halo, -8, -3, 9, 'periodic') +
        (-196909 / 84084000)
        * _stencil_shift(halo, -7, -3, 9, 'periodic') +
        (9601741 / 567567000)
        * _stencil_shift(halo, -6, -3, 9, 'periodic') +
        (-5861 / 64680)
        * _stencil_shift(halo, -5, -3, 9, 'periodic') +
        (9381241 / 24024000)
        * _stencil_shift(halo, -4, -3, 9, 'periodic') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, -3, -3, 9, 'periodic') +
        (8190541 / 1617000)
        * _stencil_shift(halo, -2, -3, 9, 'periodic') +
        (-3427741 / 294000)
        * _stencil_shift(halo, -1, -3, 9, 'periodic') +
        (117868837 / 7620480)
        * _stencil_shift(halo, 0, -3, 9, 'periodic') +
        (-3427741 / 294000)
        * _stencil_shift(halo, 1, -3, 9, 'periodic') +
        (8190541 / 1617000)
        * _stencil_shift(halo, 2, -3, 9, 'periodic') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, 3, -3, 9, 'periodic') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -3, 9, 'periodic') +
        (-5861 / 64680)
        * _stencil_shift(halo, 5, -3, 9, 'periodic') +
        (9601741 / 567567000)
        * _stencil_shift(halo, 6, -3, 9, 'periodic') +
        (-196909 / 84084000)
        * _stencil_shift(halo, 7, -3, 9, 'periodic') +
        (10949 / 51744000)
        * _stencil_shift(halo, 8, -3, 9, 'periodic') +
        (-63397 / 6810804000)
        * _stencil_shift(halo, 9, -3, 9, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 16, -3, 'periodic'] = _fd_d4_a16_axis3_periodic


def _fd_d4_a16_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 16, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 9, 'zero', 4)
    result = (
        (-63397 / 6810804000)
        * _stencil_shift(halo, -9, -3, 9, 'zero') +
        (10949 / 51744000)
        * _stencil_shift(halo, -8, -3, 9, 'zero') +
        (-196909 / 84084000)
        * _stencil_shift(halo, -7, -3, 9, 'zero') +
        (9601741 / 567567000)
        * _stencil_shift(halo, -6, -3, 9, 'zero') +
        (-5861 / 64680)
        * _stencil_shift(halo, -5, -3, 9, 'zero') +
        (9381241 / 24024000)
        * _stencil_shift(halo, -4, -3, 9, 'zero') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, -3, -3, 9, 'zero') +
        (8190541 / 1617000)
        * _stencil_shift(halo, -2, -3, 9, 'zero') +
        (-3427741 / 294000)
        * _stencil_shift(halo, -1, -3, 9, 'zero') +
        (117868837 / 7620480)
        * _stencil_shift(halo, 0, -3, 9, 'zero') +
        (-3427741 / 294000)
        * _stencil_shift(halo, 1, -3, 9, 'zero') +
        (8190541 / 1617000)
        * _stencil_shift(halo, 2, -3, 9, 'zero') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, 3, -3, 9, 'zero') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -3, 9, 'zero') +
        (-5861 / 64680)
        * _stencil_shift(halo, 5, -3, 9, 'zero') +
        (9601741 / 567567000)
        * _stencil_shift(halo, 6, -3, 9, 'zero') +
        (-196909 / 84084000)
        * _stencil_shift(halo, 7, -3, 9, 'zero') +
        (10949 / 51744000)
        * _stencil_shift(halo, 8, -3, 9, 'zero') +
        (-63397 / 6810804000)
        * _stencil_shift(halo, 9, -3, 9, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 16, -3, 'zero'] = _fd_d4_a16_axis3_zero


def _fd_d4_a16_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 16, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 9, 'reflect', 4)
    result = (
        (-63397 / 6810804000)
        * _stencil_shift(halo, -9, -3, 9, 'reflect') +
        (10949 / 51744000)
        * _stencil_shift(halo, -8, -3, 9, 'reflect') +
        (-196909 / 84084000)
        * _stencil_shift(halo, -7, -3, 9, 'reflect') +
        (9601741 / 567567000)
        * _stencil_shift(halo, -6, -3, 9, 'reflect') +
        (-5861 / 64680)
        * _stencil_shift(halo, -5, -3, 9, 'reflect') +
        (9381241 / 24024000)
        * _stencil_shift(halo, -4, -3, 9, 'reflect') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, -3, -3, 9, 'reflect') +
        (8190541 / 1617000)
        * _stencil_shift(halo, -2, -3, 9, 'reflect') +
        (-3427741 / 294000)
        * _stencil_shift(halo, -1, -3, 9, 'reflect') +
        (117868837 / 7620480)
        * _stencil_shift(halo, 0, -3, 9, 'reflect') +
        (-3427741 / 294000)
        * _stencil_shift(halo, 1, -3, 9, 'reflect') +
        (8190541 / 1617000)
        * _stencil_shift(halo, 2, -3, 9, 'reflect') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, 3, -3, 9, 'reflect') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -3, 9, 'reflect') +
        (-5861 / 64680)
        * _stencil_shift(halo, 5, -3, 9, 'reflect') +
        (9601741 / 567567000)
        * _stencil_shift(halo, 6, -3, 9, 'reflect') +
        (-196909 / 84084000)
        * _stencil_shift(halo, 7, -3, 9, 'reflect') +
        (10949 / 51744000)
        * _stencil_shift(halo, 8, -3, 9, 'reflect') +
        (-63397 / 6810804000)
        * _stencil_shift(halo, 9, -3, 9, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 16, -3, 'reflect'] = _fd_d4_a16_axis3_reflect


def _fd_d4_a16_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 16, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 9, 'periodic', 4)
    result = (
        (-63397 / 6810804000)
        * _stencil_shift(halo, -9, -2, 9, 'periodic') +
        (10949 / 51744000)
        * _stencil_shift(halo, -8, -2, 9, 'periodic') +
        (-196909 / 84084000)
        * _stencil_shift(halo, -7, -2, 9, 'periodic') +
        (9601741 / 567567000)
        * _stencil_shift(halo, -6, -2, 9, 'periodic') +
        (-5861 / 64680)
        * _stencil_shift(halo, -5, -2, 9, 'periodic') +
        (9381241 / 24024000)
        * _stencil_shift(halo, -4, -2, 9, 'periodic') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, -3, -2, 9, 'periodic') +
        (8190541 / 1617000)
        * _stencil_shift(halo, -2, -2, 9, 'periodic') +
        (-3427741 / 294000)
        * _stencil_shift(halo, -1, -2, 9, 'periodic') +
        (117868837 / 7620480)
        * _stencil_shift(halo, 0, -2, 9, 'periodic') +
        (-3427741 / 294000)
        * _stencil_shift(halo, 1, -2, 9, 'periodic') +
        (8190541 / 1617000)
        * _stencil_shift(halo, 2, -2, 9, 'periodic') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, 3, -2, 9, 'periodic') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -2, 9, 'periodic') +
        (-5861 / 64680)
        * _stencil_shift(halo, 5, -2, 9, 'periodic') +
        (9601741 / 567567000)
        * _stencil_shift(halo, 6, -2, 9, 'periodic') +
        (-196909 / 84084000)
        * _stencil_shift(halo, 7, -2, 9, 'periodic') +
        (10949 / 51744000)
        * _stencil_shift(halo, 8, -2, 9, 'periodic') +
        (-63397 / 6810804000)
        * _stencil_shift(halo, 9, -2, 9, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 16, -2, 'periodic'] = _fd_d4_a16_axis2_periodic


def _fd_d4_a16_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 16, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 9, 'zero', 4)
    result = (
        (-63397 / 6810804000)
        * _stencil_shift(halo, -9, -2, 9, 'zero') +
        (10949 / 51744000)
        * _stencil_shift(halo, -8, -2, 9, 'zero') +
        (-196909 / 84084000)
        * _stencil_shift(halo, -7, -2, 9, 'zero') +
        (9601741 / 567567000)
        * _stencil_shift(halo, -6, -2, 9, 'zero') +
        (-5861 / 64680)
        * _stencil_shift(halo, -5, -2, 9, 'zero') +
        (9381241 / 24024000)
        * _stencil_shift(halo, -4, -2, 9, 'zero') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, -3, -2, 9, 'zero') +
        (8190541 / 1617000)
        * _stencil_shift(halo, -2, -2, 9, 'zero') +
        (-3427741 / 294000)
        * _stencil_shift(halo, -1, -2, 9, 'zero') +
        (117868837 / 7620480)
        * _stencil_shift(halo, 0, -2, 9, 'zero') +
        (-3427741 / 294000)
        * _stencil_shift(halo, 1, -2, 9, 'zero') +
        (8190541 / 1617000)
        * _stencil_shift(halo, 2, -2, 9, 'zero') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, 3, -2, 9, 'zero') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -2, 9, 'zero') +
        (-5861 / 64680)
        * _stencil_shift(halo, 5, -2, 9, 'zero') +
        (9601741 / 567567000)
        * _stencil_shift(halo, 6, -2, 9, 'zero') +
        (-196909 / 84084000)
        * _stencil_shift(halo, 7, -2, 9, 'zero') +
        (10949 / 51744000)
        * _stencil_shift(halo, 8, -2, 9, 'zero') +
        (-63397 / 6810804000)
        * _stencil_shift(halo, 9, -2, 9, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 16, -2, 'zero'] = _fd_d4_a16_axis2_zero


def _fd_d4_a16_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 16, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 9, 'reflect', 4)
    result = (
        (-63397 / 6810804000)
        * _stencil_shift(halo, -9, -2, 9, 'reflect') +
        (10949 / 51744000)
        * _stencil_shift(halo, -8, -2, 9, 'reflect') +
        (-196909 / 84084000)
        * _stencil_shift(halo, -7, -2, 9, 'reflect') +
        (9601741 / 567567000)
        * _stencil_shift(halo, -6, -2, 9, 'reflect') +
        (-5861 / 64680)
        * _stencil_shift(halo, -5, -2, 9, 'reflect') +
        (9381241 / 24024000)
        * _stencil_shift(halo, -4, -2, 9, 'reflect') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, -3, -2, 9, 'reflect') +
        (8190541 / 1617000)
        * _stencil_shift(halo, -2, -2, 9, 'reflect') +
        (-3427741 / 294000)
        * _stencil_shift(halo, -1, -2, 9, 'reflect') +
        (117868837 / 7620480)
        * _stencil_shift(halo, 0, -2, 9, 'reflect') +
        (-3427741 / 294000)
        * _stencil_shift(halo, 1, -2, 9, 'reflect') +
        (8190541 / 1617000)
        * _stencil_shift(halo, 2, -2, 9, 'reflect') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, 3, -2, 9, 'reflect') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -2, 9, 'reflect') +
        (-5861 / 64680)
        * _stencil_shift(halo, 5, -2, 9, 'reflect') +
        (9601741 / 567567000)
        * _stencil_shift(halo, 6, -2, 9, 'reflect') +
        (-196909 / 84084000)
        * _stencil_shift(halo, 7, -2, 9, 'reflect') +
        (10949 / 51744000)
        * _stencil_shift(halo, 8, -2, 9, 'reflect') +
        (-63397 / 6810804000)
        * _stencil_shift(halo, 9, -2, 9, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 16, -2, 'reflect'] = _fd_d4_a16_axis2_reflect


def _fd_d4_a16_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 16, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 9, 'periodic', 4)
    result = (
        (-63397 / 6810804000)
        * _stencil_shift(halo, -9, -1, 9, 'periodic') +
        (10949 / 51744000)
        * _stencil_shift(halo, -8, -1, 9, 'periodic') +
        (-196909 / 84084000)
        * _stencil_shift(halo, -7, -1, 9, 'periodic') +
        (9601741 / 567567000)
        * _stencil_shift(halo, -6, -1, 9, 'periodic') +
        (-5861 / 64680)
        * _stencil_shift(halo, -5, -1, 9, 'periodic') +
        (9381241 / 24024000)
        * _stencil_shift(halo, -4, -1, 9, 'periodic') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, -3, -1, 9, 'periodic') +
        (8190541 / 1617000)
        * _stencil_shift(halo, -2, -1, 9, 'periodic') +
        (-3427741 / 294000)
        * _stencil_shift(halo, -1, -1, 9, 'periodic') +
        (117868837 / 7620480)
        * _stencil_shift(halo, 0, -1, 9, 'periodic') +
        (-3427741 / 294000)
        * _stencil_shift(halo, 1, -1, 9, 'periodic') +
        (8190541 / 1617000)
        * _stencil_shift(halo, 2, -1, 9, 'periodic') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, 3, -1, 9, 'periodic') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -1, 9, 'periodic') +
        (-5861 / 64680)
        * _stencil_shift(halo, 5, -1, 9, 'periodic') +
        (9601741 / 567567000)
        * _stencil_shift(halo, 6, -1, 9, 'periodic') +
        (-196909 / 84084000)
        * _stencil_shift(halo, 7, -1, 9, 'periodic') +
        (10949 / 51744000)
        * _stencil_shift(halo, 8, -1, 9, 'periodic') +
        (-63397 / 6810804000)
        * _stencil_shift(halo, 9, -1, 9, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 16, -1, 'periodic'] = _fd_d4_a16_axis1_periodic


def _fd_d4_a16_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 16, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 9, 'zero', 4)
    result = (
        (-63397 / 6810804000)
        * _stencil_shift(halo, -9, -1, 9, 'zero') +
        (10949 / 51744000)
        * _stencil_shift(halo, -8, -1, 9, 'zero') +
        (-196909 / 84084000)
        * _stencil_shift(halo, -7, -1, 9, 'zero') +
        (9601741 / 567567000)
        * _stencil_shift(halo, -6, -1, 9, 'zero') +
        (-5861 / 64680)
        * _stencil_shift(halo, -5, -1, 9, 'zero') +
        (9381241 / 24024000)
        * _stencil_shift(halo, -4, -1, 9, 'zero') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, -3, -1, 9, 'zero') +
        (8190541 / 1617000)
        * _stencil_shift(halo, -2, -1, 9, 'zero') +
        (-3427741 / 294000)
        * _stencil_shift(halo, -1, -1, 9, 'zero') +
        (117868837 / 7620480)
        * _stencil_shift(halo, 0, -1, 9, 'zero') +
        (-3427741 / 294000)
        * _stencil_shift(halo, 1, -1, 9, 'zero') +
        (8190541 / 1617000)
        * _stencil_shift(halo, 2, -1, 9, 'zero') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, 3, -1, 9, 'zero') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -1, 9, 'zero') +
        (-5861 / 64680)
        * _stencil_shift(halo, 5, -1, 9, 'zero') +
        (9601741 / 567567000)
        * _stencil_shift(halo, 6, -1, 9, 'zero') +
        (-196909 / 84084000)
        * _stencil_shift(halo, 7, -1, 9, 'zero') +
        (10949 / 51744000)
        * _stencil_shift(halo, 8, -1, 9, 'zero') +
        (-63397 / 6810804000)
        * _stencil_shift(halo, 9, -1, 9, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 16, -1, 'zero'] = _fd_d4_a16_axis1_zero


def _fd_d4_a16_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 16, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 18.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 9, 'reflect', 4)
    result = (
        (-63397 / 6810804000)
        * _stencil_shift(halo, -9, -1, 9, 'reflect') +
        (10949 / 51744000)
        * _stencil_shift(halo, -8, -1, 9, 'reflect') +
        (-196909 / 84084000)
        * _stencil_shift(halo, -7, -1, 9, 'reflect') +
        (9601741 / 567567000)
        * _stencil_shift(halo, -6, -1, 9, 'reflect') +
        (-5861 / 64680)
        * _stencil_shift(halo, -5, -1, 9, 'reflect') +
        (9381241 / 24024000)
        * _stencil_shift(halo, -4, -1, 9, 'reflect') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, -3, -1, 9, 'reflect') +
        (8190541 / 1617000)
        * _stencil_shift(halo, -2, -1, 9, 'reflect') +
        (-3427741 / 294000)
        * _stencil_shift(halo, -1, -1, 9, 'reflect') +
        (117868837 / 7620480)
        * _stencil_shift(halo, 0, -1, 9, 'reflect') +
        (-3427741 / 294000)
        * _stencil_shift(halo, 1, -1, 9, 'reflect') +
        (8190541 / 1617000)
        * _stencil_shift(halo, 2, -1, 9, 'reflect') +
        (-9072541 / 6237000)
        * _stencil_shift(halo, 3, -1, 9, 'reflect') +
        (9381241 / 24024000)
        * _stencil_shift(halo, 4, -1, 9, 'reflect') +
        (-5861 / 64680)
        * _stencil_shift(halo, 5, -1, 9, 'reflect') +
        (9601741 / 567567000)
        * _stencil_shift(halo, 6, -1, 9, 'reflect') +
        (-196909 / 84084000)
        * _stencil_shift(halo, 7, -1, 9, 'reflect') +
        (10949 / 51744000)
        * _stencil_shift(halo, 8, -1, 9, 'reflect') +
        (-63397 / 6810804000)
        * _stencil_shift(halo, 9, -1, 9, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 16, -1, 'reflect'] = _fd_d4_a16_axis1_reflect


STENCIL_MOMENTS[4, 18] = (
    (-10, 514639, 257297040000),
    (-9, -11419, 231567336),
    (-8, 487121, 823350528),
    (-7, -809, 175032),
    (-6, 1933049, 72648576),
    (-5, -9587629, 78828750),
    (-4, 1888949, 4036032),
    (-3, -1827209, 1135134),
    (-2, 1650809, 310464),
    (-1, -698249, 58212),
    (0, 307869749, 19440000),
    (1, -698249, 58212),
    (2, 1650809, 310464),
    (3, -1827209, 1135134),
    (4, 1888949, 4036032),
    (5, -9587629, 78828750),
    (6, 1933049, 72648576),
    (7, -809, 175032),
    (8, 487121, 823350528),
    (9, -11419, 231567336),
    (10, 514639, 257297040000),
)

def _fd_d4_a18_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 18, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 10, 'periodic', 4)
    result = (
        (514639 / 257297040000)
        * _stencil_shift(halo, -10, -4, 10, 'periodic') +
        (-11419 / 231567336)
        * _stencil_shift(halo, -9, -4, 10, 'periodic') +
        (487121 / 823350528)
        * _stencil_shift(halo, -8, -4, 10, 'periodic') +
        (-809 / 175032)
        * _stencil_shift(halo, -7, -4, 10, 'periodic') +
        (1933049 / 72648576)
        * _stencil_shift(halo, -6, -4, 10, 'periodic') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, -5, -4, 10, 'periodic') +
        (1888949 / 4036032)
        * _stencil_shift(halo, -4, -4, 10, 'periodic') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, -3, -4, 10, 'periodic') +
        (1650809 / 310464)
        * _stencil_shift(halo, -2, -4, 10, 'periodic') +
        (-698249 / 58212)
        * _stencil_shift(halo, -1, -4, 10, 'periodic') +
        (307869749 / 19440000)
        * _stencil_shift(halo, 0, -4, 10, 'periodic') +
        (-698249 / 58212)
        * _stencil_shift(halo, 1, -4, 10, 'periodic') +
        (1650809 / 310464)
        * _stencil_shift(halo, 2, -4, 10, 'periodic') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, 3, -4, 10, 'periodic') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -4, 10, 'periodic') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, 5, -4, 10, 'periodic') +
        (1933049 / 72648576)
        * _stencil_shift(halo, 6, -4, 10, 'periodic') +
        (-809 / 175032)
        * _stencil_shift(halo, 7, -4, 10, 'periodic') +
        (487121 / 823350528)
        * _stencil_shift(halo, 8, -4, 10, 'periodic') +
        (-11419 / 231567336)
        * _stencil_shift(halo, 9, -4, 10, 'periodic') +
        (514639 / 257297040000)
        * _stencil_shift(halo, 10, -4, 10, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 18, -4, 'periodic'] = _fd_d4_a18_axis4_periodic


def _fd_d4_a18_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 18, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 10, 'zero', 4)
    result = (
        (514639 / 257297040000)
        * _stencil_shift(halo, -10, -4, 10, 'zero') +
        (-11419 / 231567336)
        * _stencil_shift(halo, -9, -4, 10, 'zero') +
        (487121 / 823350528)
        * _stencil_shift(halo, -8, -4, 10, 'zero') +
        (-809 / 175032)
        * _stencil_shift(halo, -7, -4, 10, 'zero') +
        (1933049 / 72648576)
        * _stencil_shift(halo, -6, -4, 10, 'zero') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, -5, -4, 10, 'zero') +
        (1888949 / 4036032)
        * _stencil_shift(halo, -4, -4, 10, 'zero') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, -3, -4, 10, 'zero') +
        (1650809 / 310464)
        * _stencil_shift(halo, -2, -4, 10, 'zero') +
        (-698249 / 58212)
        * _stencil_shift(halo, -1, -4, 10, 'zero') +
        (307869749 / 19440000)
        * _stencil_shift(halo, 0, -4, 10, 'zero') +
        (-698249 / 58212)
        * _stencil_shift(halo, 1, -4, 10, 'zero') +
        (1650809 / 310464)
        * _stencil_shift(halo, 2, -4, 10, 'zero') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, 3, -4, 10, 'zero') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -4, 10, 'zero') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, 5, -4, 10, 'zero') +
        (1933049 / 72648576)
        * _stencil_shift(halo, 6, -4, 10, 'zero') +
        (-809 / 175032)
        * _stencil_shift(halo, 7, -4, 10, 'zero') +
        (487121 / 823350528)
        * _stencil_shift(halo, 8, -4, 10, 'zero') +
        (-11419 / 231567336)
        * _stencil_shift(halo, 9, -4, 10, 'zero') +
        (514639 / 257297040000)
        * _stencil_shift(halo, 10, -4, 10, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 18, -4, 'zero'] = _fd_d4_a18_axis4_zero


def _fd_d4_a18_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 18, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 10, 'reflect', 4)
    result = (
        (514639 / 257297040000)
        * _stencil_shift(halo, -10, -4, 10, 'reflect') +
        (-11419 / 231567336)
        * _stencil_shift(halo, -9, -4, 10, 'reflect') +
        (487121 / 823350528)
        * _stencil_shift(halo, -8, -4, 10, 'reflect') +
        (-809 / 175032)
        * _stencil_shift(halo, -7, -4, 10, 'reflect') +
        (1933049 / 72648576)
        * _stencil_shift(halo, -6, -4, 10, 'reflect') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, -5, -4, 10, 'reflect') +
        (1888949 / 4036032)
        * _stencil_shift(halo, -4, -4, 10, 'reflect') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, -3, -4, 10, 'reflect') +
        (1650809 / 310464)
        * _stencil_shift(halo, -2, -4, 10, 'reflect') +
        (-698249 / 58212)
        * _stencil_shift(halo, -1, -4, 10, 'reflect') +
        (307869749 / 19440000)
        * _stencil_shift(halo, 0, -4, 10, 'reflect') +
        (-698249 / 58212)
        * _stencil_shift(halo, 1, -4, 10, 'reflect') +
        (1650809 / 310464)
        * _stencil_shift(halo, 2, -4, 10, 'reflect') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, 3, -4, 10, 'reflect') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -4, 10, 'reflect') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, 5, -4, 10, 'reflect') +
        (1933049 / 72648576)
        * _stencil_shift(halo, 6, -4, 10, 'reflect') +
        (-809 / 175032)
        * _stencil_shift(halo, 7, -4, 10, 'reflect') +
        (487121 / 823350528)
        * _stencil_shift(halo, 8, -4, 10, 'reflect') +
        (-11419 / 231567336)
        * _stencil_shift(halo, 9, -4, 10, 'reflect') +
        (514639 / 257297040000)
        * _stencil_shift(halo, 10, -4, 10, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 18, -4, 'reflect'] = _fd_d4_a18_axis4_reflect


def _fd_d4_a18_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 18, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 10, 'periodic', 4)
    result = (
        (514639 / 257297040000)
        * _stencil_shift(halo, -10, -3, 10, 'periodic') +
        (-11419 / 231567336)
        * _stencil_shift(halo, -9, -3, 10, 'periodic') +
        (487121 / 823350528)
        * _stencil_shift(halo, -8, -3, 10, 'periodic') +
        (-809 / 175032)
        * _stencil_shift(halo, -7, -3, 10, 'periodic') +
        (1933049 / 72648576)
        * _stencil_shift(halo, -6, -3, 10, 'periodic') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, -5, -3, 10, 'periodic') +
        (1888949 / 4036032)
        * _stencil_shift(halo, -4, -3, 10, 'periodic') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, -3, -3, 10, 'periodic') +
        (1650809 / 310464)
        * _stencil_shift(halo, -2, -3, 10, 'periodic') +
        (-698249 / 58212)
        * _stencil_shift(halo, -1, -3, 10, 'periodic') +
        (307869749 / 19440000)
        * _stencil_shift(halo, 0, -3, 10, 'periodic') +
        (-698249 / 58212)
        * _stencil_shift(halo, 1, -3, 10, 'periodic') +
        (1650809 / 310464)
        * _stencil_shift(halo, 2, -3, 10, 'periodic') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, 3, -3, 10, 'periodic') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -3, 10, 'periodic') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, 5, -3, 10, 'periodic') +
        (1933049 / 72648576)
        * _stencil_shift(halo, 6, -3, 10, 'periodic') +
        (-809 / 175032)
        * _stencil_shift(halo, 7, -3, 10, 'periodic') +
        (487121 / 823350528)
        * _stencil_shift(halo, 8, -3, 10, 'periodic') +
        (-11419 / 231567336)
        * _stencil_shift(halo, 9, -3, 10, 'periodic') +
        (514639 / 257297040000)
        * _stencil_shift(halo, 10, -3, 10, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 18, -3, 'periodic'] = _fd_d4_a18_axis3_periodic


def _fd_d4_a18_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 18, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 10, 'zero', 4)
    result = (
        (514639 / 257297040000)
        * _stencil_shift(halo, -10, -3, 10, 'zero') +
        (-11419 / 231567336)
        * _stencil_shift(halo, -9, -3, 10, 'zero') +
        (487121 / 823350528)
        * _stencil_shift(halo, -8, -3, 10, 'zero') +
        (-809 / 175032)
        * _stencil_shift(halo, -7, -3, 10, 'zero') +
        (1933049 / 72648576)
        * _stencil_shift(halo, -6, -3, 10, 'zero') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, -5, -3, 10, 'zero') +
        (1888949 / 4036032)
        * _stencil_shift(halo, -4, -3, 10, 'zero') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, -3, -3, 10, 'zero') +
        (1650809 / 310464)
        * _stencil_shift(halo, -2, -3, 10, 'zero') +
        (-698249 / 58212)
        * _stencil_shift(halo, -1, -3, 10, 'zero') +
        (307869749 / 19440000)
        * _stencil_shift(halo, 0, -3, 10, 'zero') +
        (-698249 / 58212)
        * _stencil_shift(halo, 1, -3, 10, 'zero') +
        (1650809 / 310464)
        * _stencil_shift(halo, 2, -3, 10, 'zero') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, 3, -3, 10, 'zero') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -3, 10, 'zero') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, 5, -3, 10, 'zero') +
        (1933049 / 72648576)
        * _stencil_shift(halo, 6, -3, 10, 'zero') +
        (-809 / 175032)
        * _stencil_shift(halo, 7, -3, 10, 'zero') +
        (487121 / 823350528)
        * _stencil_shift(halo, 8, -3, 10, 'zero') +
        (-11419 / 231567336)
        * _stencil_shift(halo, 9, -3, 10, 'zero') +
        (514639 / 257297040000)
        * _stencil_shift(halo, 10, -3, 10, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 18, -3, 'zero'] = _fd_d4_a18_axis3_zero


def _fd_d4_a18_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 18, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 10, 'reflect', 4)
    result = (
        (514639 / 257297040000)
        * _stencil_shift(halo, -10, -3, 10, 'reflect') +
        (-11419 / 231567336)
        * _stencil_shift(halo, -9, -3, 10, 'reflect') +
        (487121 / 823350528)
        * _stencil_shift(halo, -8, -3, 10, 'reflect') +
        (-809 / 175032)
        * _stencil_shift(halo, -7, -3, 10, 'reflect') +
        (1933049 / 72648576)
        * _stencil_shift(halo, -6, -3, 10, 'reflect') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, -5, -3, 10, 'reflect') +
        (1888949 / 4036032)
        * _stencil_shift(halo, -4, -3, 10, 'reflect') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, -3, -3, 10, 'reflect') +
        (1650809 / 310464)
        * _stencil_shift(halo, -2, -3, 10, 'reflect') +
        (-698249 / 58212)
        * _stencil_shift(halo, -1, -3, 10, 'reflect') +
        (307869749 / 19440000)
        * _stencil_shift(halo, 0, -3, 10, 'reflect') +
        (-698249 / 58212)
        * _stencil_shift(halo, 1, -3, 10, 'reflect') +
        (1650809 / 310464)
        * _stencil_shift(halo, 2, -3, 10, 'reflect') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, 3, -3, 10, 'reflect') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -3, 10, 'reflect') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, 5, -3, 10, 'reflect') +
        (1933049 / 72648576)
        * _stencil_shift(halo, 6, -3, 10, 'reflect') +
        (-809 / 175032)
        * _stencil_shift(halo, 7, -3, 10, 'reflect') +
        (487121 / 823350528)
        * _stencil_shift(halo, 8, -3, 10, 'reflect') +
        (-11419 / 231567336)
        * _stencil_shift(halo, 9, -3, 10, 'reflect') +
        (514639 / 257297040000)
        * _stencil_shift(halo, 10, -3, 10, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 18, -3, 'reflect'] = _fd_d4_a18_axis3_reflect


def _fd_d4_a18_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 18, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 10, 'periodic', 4)
    result = (
        (514639 / 257297040000)
        * _stencil_shift(halo, -10, -2, 10, 'periodic') +
        (-11419 / 231567336)
        * _stencil_shift(halo, -9, -2, 10, 'periodic') +
        (487121 / 823350528)
        * _stencil_shift(halo, -8, -2, 10, 'periodic') +
        (-809 / 175032)
        * _stencil_shift(halo, -7, -2, 10, 'periodic') +
        (1933049 / 72648576)
        * _stencil_shift(halo, -6, -2, 10, 'periodic') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, -5, -2, 10, 'periodic') +
        (1888949 / 4036032)
        * _stencil_shift(halo, -4, -2, 10, 'periodic') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, -3, -2, 10, 'periodic') +
        (1650809 / 310464)
        * _stencil_shift(halo, -2, -2, 10, 'periodic') +
        (-698249 / 58212)
        * _stencil_shift(halo, -1, -2, 10, 'periodic') +
        (307869749 / 19440000)
        * _stencil_shift(halo, 0, -2, 10, 'periodic') +
        (-698249 / 58212)
        * _stencil_shift(halo, 1, -2, 10, 'periodic') +
        (1650809 / 310464)
        * _stencil_shift(halo, 2, -2, 10, 'periodic') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, 3, -2, 10, 'periodic') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -2, 10, 'periodic') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, 5, -2, 10, 'periodic') +
        (1933049 / 72648576)
        * _stencil_shift(halo, 6, -2, 10, 'periodic') +
        (-809 / 175032)
        * _stencil_shift(halo, 7, -2, 10, 'periodic') +
        (487121 / 823350528)
        * _stencil_shift(halo, 8, -2, 10, 'periodic') +
        (-11419 / 231567336)
        * _stencil_shift(halo, 9, -2, 10, 'periodic') +
        (514639 / 257297040000)
        * _stencil_shift(halo, 10, -2, 10, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 18, -2, 'periodic'] = _fd_d4_a18_axis2_periodic


def _fd_d4_a18_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 18, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 10, 'zero', 4)
    result = (
        (514639 / 257297040000)
        * _stencil_shift(halo, -10, -2, 10, 'zero') +
        (-11419 / 231567336)
        * _stencil_shift(halo, -9, -2, 10, 'zero') +
        (487121 / 823350528)
        * _stencil_shift(halo, -8, -2, 10, 'zero') +
        (-809 / 175032)
        * _stencil_shift(halo, -7, -2, 10, 'zero') +
        (1933049 / 72648576)
        * _stencil_shift(halo, -6, -2, 10, 'zero') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, -5, -2, 10, 'zero') +
        (1888949 / 4036032)
        * _stencil_shift(halo, -4, -2, 10, 'zero') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, -3, -2, 10, 'zero') +
        (1650809 / 310464)
        * _stencil_shift(halo, -2, -2, 10, 'zero') +
        (-698249 / 58212)
        * _stencil_shift(halo, -1, -2, 10, 'zero') +
        (307869749 / 19440000)
        * _stencil_shift(halo, 0, -2, 10, 'zero') +
        (-698249 / 58212)
        * _stencil_shift(halo, 1, -2, 10, 'zero') +
        (1650809 / 310464)
        * _stencil_shift(halo, 2, -2, 10, 'zero') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, 3, -2, 10, 'zero') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -2, 10, 'zero') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, 5, -2, 10, 'zero') +
        (1933049 / 72648576)
        * _stencil_shift(halo, 6, -2, 10, 'zero') +
        (-809 / 175032)
        * _stencil_shift(halo, 7, -2, 10, 'zero') +
        (487121 / 823350528)
        * _stencil_shift(halo, 8, -2, 10, 'zero') +
        (-11419 / 231567336)
        * _stencil_shift(halo, 9, -2, 10, 'zero') +
        (514639 / 257297040000)
        * _stencil_shift(halo, 10, -2, 10, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 18, -2, 'zero'] = _fd_d4_a18_axis2_zero


def _fd_d4_a18_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 18, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 10, 'reflect', 4)
    result = (
        (514639 / 257297040000)
        * _stencil_shift(halo, -10, -2, 10, 'reflect') +
        (-11419 / 231567336)
        * _stencil_shift(halo, -9, -2, 10, 'reflect') +
        (487121 / 823350528)
        * _stencil_shift(halo, -8, -2, 10, 'reflect') +
        (-809 / 175032)
        * _stencil_shift(halo, -7, -2, 10, 'reflect') +
        (1933049 / 72648576)
        * _stencil_shift(halo, -6, -2, 10, 'reflect') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, -5, -2, 10, 'reflect') +
        (1888949 / 4036032)
        * _stencil_shift(halo, -4, -2, 10, 'reflect') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, -3, -2, 10, 'reflect') +
        (1650809 / 310464)
        * _stencil_shift(halo, -2, -2, 10, 'reflect') +
        (-698249 / 58212)
        * _stencil_shift(halo, -1, -2, 10, 'reflect') +
        (307869749 / 19440000)
        * _stencil_shift(halo, 0, -2, 10, 'reflect') +
        (-698249 / 58212)
        * _stencil_shift(halo, 1, -2, 10, 'reflect') +
        (1650809 / 310464)
        * _stencil_shift(halo, 2, -2, 10, 'reflect') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, 3, -2, 10, 'reflect') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -2, 10, 'reflect') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, 5, -2, 10, 'reflect') +
        (1933049 / 72648576)
        * _stencil_shift(halo, 6, -2, 10, 'reflect') +
        (-809 / 175032)
        * _stencil_shift(halo, 7, -2, 10, 'reflect') +
        (487121 / 823350528)
        * _stencil_shift(halo, 8, -2, 10, 'reflect') +
        (-11419 / 231567336)
        * _stencil_shift(halo, 9, -2, 10, 'reflect') +
        (514639 / 257297040000)
        * _stencil_shift(halo, 10, -2, 10, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 18, -2, 'reflect'] = _fd_d4_a18_axis2_reflect


def _fd_d4_a18_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 18, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 10, 'periodic', 4)
    result = (
        (514639 / 257297040000)
        * _stencil_shift(halo, -10, -1, 10, 'periodic') +
        (-11419 / 231567336)
        * _stencil_shift(halo, -9, -1, 10, 'periodic') +
        (487121 / 823350528)
        * _stencil_shift(halo, -8, -1, 10, 'periodic') +
        (-809 / 175032)
        * _stencil_shift(halo, -7, -1, 10, 'periodic') +
        (1933049 / 72648576)
        * _stencil_shift(halo, -6, -1, 10, 'periodic') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, -5, -1, 10, 'periodic') +
        (1888949 / 4036032)
        * _stencil_shift(halo, -4, -1, 10, 'periodic') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, -3, -1, 10, 'periodic') +
        (1650809 / 310464)
        * _stencil_shift(halo, -2, -1, 10, 'periodic') +
        (-698249 / 58212)
        * _stencil_shift(halo, -1, -1, 10, 'periodic') +
        (307869749 / 19440000)
        * _stencil_shift(halo, 0, -1, 10, 'periodic') +
        (-698249 / 58212)
        * _stencil_shift(halo, 1, -1, 10, 'periodic') +
        (1650809 / 310464)
        * _stencil_shift(halo, 2, -1, 10, 'periodic') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, 3, -1, 10, 'periodic') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -1, 10, 'periodic') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, 5, -1, 10, 'periodic') +
        (1933049 / 72648576)
        * _stencil_shift(halo, 6, -1, 10, 'periodic') +
        (-809 / 175032)
        * _stencil_shift(halo, 7, -1, 10, 'periodic') +
        (487121 / 823350528)
        * _stencil_shift(halo, 8, -1, 10, 'periodic') +
        (-11419 / 231567336)
        * _stencil_shift(halo, 9, -1, 10, 'periodic') +
        (514639 / 257297040000)
        * _stencil_shift(halo, 10, -1, 10, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 18, -1, 'periodic'] = _fd_d4_a18_axis1_periodic


def _fd_d4_a18_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 18, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 10, 'zero', 4)
    result = (
        (514639 / 257297040000)
        * _stencil_shift(halo, -10, -1, 10, 'zero') +
        (-11419 / 231567336)
        * _stencil_shift(halo, -9, -1, 10, 'zero') +
        (487121 / 823350528)
        * _stencil_shift(halo, -8, -1, 10, 'zero') +
        (-809 / 175032)
        * _stencil_shift(halo, -7, -1, 10, 'zero') +
        (1933049 / 72648576)
        * _stencil_shift(halo, -6, -1, 10, 'zero') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, -5, -1, 10, 'zero') +
        (1888949 / 4036032)
        * _stencil_shift(halo, -4, -1, 10, 'zero') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, -3, -1, 10, 'zero') +
        (1650809 / 310464)
        * _stencil_shift(halo, -2, -1, 10, 'zero') +
        (-698249 / 58212)
        * _stencil_shift(halo, -1, -1, 10, 'zero') +
        (307869749 / 19440000)
        * _stencil_shift(halo, 0, -1, 10, 'zero') +
        (-698249 / 58212)
        * _stencil_shift(halo, 1, -1, 10, 'zero') +
        (1650809 / 310464)
        * _stencil_shift(halo, 2, -1, 10, 'zero') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, 3, -1, 10, 'zero') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -1, 10, 'zero') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, 5, -1, 10, 'zero') +
        (1933049 / 72648576)
        * _stencil_shift(halo, 6, -1, 10, 'zero') +
        (-809 / 175032)
        * _stencil_shift(halo, 7, -1, 10, 'zero') +
        (487121 / 823350528)
        * _stencil_shift(halo, 8, -1, 10, 'zero') +
        (-11419 / 231567336)
        * _stencil_shift(halo, 9, -1, 10, 'zero') +
        (514639 / 257297040000)
        * _stencil_shift(halo, 10, -1, 10, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 18, -1, 'zero'] = _fd_d4_a18_axis1_zero


def _fd_d4_a18_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 18, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 20.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 10, 'reflect', 4)
    result = (
        (514639 / 257297040000)
        * _stencil_shift(halo, -10, -1, 10, 'reflect') +
        (-11419 / 231567336)
        * _stencil_shift(halo, -9, -1, 10, 'reflect') +
        (487121 / 823350528)
        * _stencil_shift(halo, -8, -1, 10, 'reflect') +
        (-809 / 175032)
        * _stencil_shift(halo, -7, -1, 10, 'reflect') +
        (1933049 / 72648576)
        * _stencil_shift(halo, -6, -1, 10, 'reflect') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, -5, -1, 10, 'reflect') +
        (1888949 / 4036032)
        * _stencil_shift(halo, -4, -1, 10, 'reflect') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, -3, -1, 10, 'reflect') +
        (1650809 / 310464)
        * _stencil_shift(halo, -2, -1, 10, 'reflect') +
        (-698249 / 58212)
        * _stencil_shift(halo, -1, -1, 10, 'reflect') +
        (307869749 / 19440000)
        * _stencil_shift(halo, 0, -1, 10, 'reflect') +
        (-698249 / 58212)
        * _stencil_shift(halo, 1, -1, 10, 'reflect') +
        (1650809 / 310464)
        * _stencil_shift(halo, 2, -1, 10, 'reflect') +
        (-1827209 / 1135134)
        * _stencil_shift(halo, 3, -1, 10, 'reflect') +
        (1888949 / 4036032)
        * _stencil_shift(halo, 4, -1, 10, 'reflect') +
        (-9587629 / 78828750)
        * _stencil_shift(halo, 5, -1, 10, 'reflect') +
        (1933049 / 72648576)
        * _stencil_shift(halo, 6, -1, 10, 'reflect') +
        (-809 / 175032)
        * _stencil_shift(halo, 7, -1, 10, 'reflect') +
        (487121 / 823350528)
        * _stencil_shift(halo, 8, -1, 10, 'reflect') +
        (-11419 / 231567336)
        * _stencil_shift(halo, 9, -1, 10, 'reflect') +
        (514639 / 257297040000)
        * _stencil_shift(halo, 10, -1, 10, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 18, -1, 'reflect'] = _fd_d4_a18_axis1_reflect


STENCIL_MOMENTS[4, 20] = (
    (-11, -178939, 410646075840),
    (-10, 1189505461, 102661518960000),
    (-9, -1552553, 10352422080),
    (-8, 268141, 212357376),
    (-7, -4822481, 617512896),
    (-6, 235169009, 6175128960),
    (-5, -89727193, 582120000),
    (-4, 229832909, 423783360),
    (-3, -222362369, 127135008),
    (-2, 201017969, 36324288),
    (-1, -85758209, 6985440),
    (0, 169162696711, 10478160000),
    (1, -85758209, 6985440),
    (2, 201017969, 36324288),
    (3, -222362369, 127135008),
    (4, 229832909, 423783360),
    (5, -89727193, 582120000),
    (6, 235169009, 6175128960),
    (7, -4822481, 617512896),
    (8, 268141, 212357376),
    (9, -1552553, 10352422080),
    (10, 1189505461, 102661518960000),
    (11, -178939, 410646075840),
)

def _fd_d4_a20_axis4_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 20, axis -4, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 11, 'periodic', 4)
    result = (
        (-178939 / 410646075840)
        * _stencil_shift(halo, -11, -4, 11, 'periodic') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, -10, -4, 11, 'periodic') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, -9, -4, 11, 'periodic') +
        (268141 / 212357376)
        * _stencil_shift(halo, -8, -4, 11, 'periodic') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, -7, -4, 11, 'periodic') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, -6, -4, 11, 'periodic') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, -5, -4, 11, 'periodic') +
        (229832909 / 423783360)
        * _stencil_shift(halo, -4, -4, 11, 'periodic') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, -3, -4, 11, 'periodic') +
        (201017969 / 36324288)
        * _stencil_shift(halo, -2, -4, 11, 'periodic') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, -1, -4, 11, 'periodic') +
        (169162696711 / 10478160000)
        * _stencil_shift(halo, 0, -4, 11, 'periodic') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, 1, -4, 11, 'periodic') +
        (201017969 / 36324288)
        * _stencil_shift(halo, 2, -4, 11, 'periodic') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, 3, -4, 11, 'periodic') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -4, 11, 'periodic') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, 5, -4, 11, 'periodic') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, 6, -4, 11, 'periodic') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, 7, -4, 11, 'periodic') +
        (268141 / 212357376)
        * _stencil_shift(halo, 8, -4, 11, 'periodic') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, 9, -4, 11, 'periodic') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, 10, -4, 11, 'periodic') +
        (-178939 / 410646075840)
        * _stencil_shift(halo, 11, -4, 11, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 20, -4, 'periodic'] = _fd_d4_a20_axis4_periodic


def _fd_d4_a20_axis4_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 20, axis -4, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 11, 'zero', 4)
    result = (
        (-178939 / 410646075840)
        * _stencil_shift(halo, -11, -4, 11, 'zero') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, -10, -4, 11, 'zero') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, -9, -4, 11, 'zero') +
        (268141 / 212357376)
        * _stencil_shift(halo, -8, -4, 11, 'zero') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, -7, -4, 11, 'zero') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, -6, -4, 11, 'zero') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, -5, -4, 11, 'zero') +
        (229832909 / 423783360)
        * _stencil_shift(halo, -4, -4, 11, 'zero') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, -3, -4, 11, 'zero') +
        (201017969 / 36324288)
        * _stencil_shift(halo, -2, -4, 11, 'zero') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, -1, -4, 11, 'zero') +
        (169162696711 / 10478160000)
        * _stencil_shift(halo, 0, -4, 11, 'zero') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, 1, -4, 11, 'zero') +
        (201017969 / 36324288)
        * _stencil_shift(halo, 2, -4, 11, 'zero') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, 3, -4, 11, 'zero') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -4, 11, 'zero') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, 5, -4, 11, 'zero') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, 6, -4, 11, 'zero') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, 7, -4, 11, 'zero') +
        (268141 / 212357376)
        * _stencil_shift(halo, 8, -4, 11, 'zero') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, 9, -4, 11, 'zero') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, 10, -4, 11, 'zero') +
        (-178939 / 410646075840)
        * _stencil_shift(halo, 11, -4, 11, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 20, -4, 'zero'] = _fd_d4_a20_axis4_zero


def _fd_d4_a20_axis4_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 20, axis -4, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -4, 11, 'reflect', 4)
    result = (
        (-178939 / 410646075840)
        * _stencil_shift(halo, -11, -4, 11, 'reflect') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, -10, -4, 11, 'reflect') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, -9, -4, 11, 'reflect') +
        (268141 / 212357376)
        * _stencil_shift(halo, -8, -4, 11, 'reflect') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, -7, -4, 11, 'reflect') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, -6, -4, 11, 'reflect') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, -5, -4, 11, 'reflect') +
        (229832909 / 423783360)
        * _stencil_shift(halo, -4, -4, 11, 'reflect') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, -3, -4, 11, 'reflect') +
        (201017969 / 36324288)
        * _stencil_shift(halo, -2, -4, 11, 'reflect') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, -1, -4, 11, 'reflect') +
        (169162696711 / 10478160000)
        * _stencil_shift(halo, 0, -4, 11, 'reflect') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, 1, -4, 11, 'reflect') +
        (201017969 / 36324288)
        * _stencil_shift(halo, 2, -4, 11, 'reflect') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, 3, -4, 11, 'reflect') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -4, 11, 'reflect') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, 5, -4, 11, 'reflect') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, 6, -4, 11, 'reflect') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, 7, -4, 11, 'reflect') +
        (268141 / 212357376)
        * _stencil_shift(halo, 8, -4, 11, 'reflect') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, 9, -4, 11, 'reflect') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, 10, -4, 11, 'reflect') +
        (-178939 / 410646075840)
        * _stencil_shift(halo, 11, -4, 11, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 20, -4, 'reflect'] = _fd_d4_a20_axis4_reflect


def _fd_d4_a20_axis3_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 20, axis -3, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 11, 'periodic', 4)
    result = (
        (-178939 / 410646075840)
        * _stencil_shift(halo, -11, -3, 11, 'periodic') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, -10, -3, 11, 'periodic') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, -9, -3, 11, 'periodic') +
        (268141 / 212357376)
        * _stencil_shift(halo, -8, -3, 11, 'periodic') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, -7, -3, 11, 'periodic') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, -6, -3, 11, 'periodic') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, -5, -3, 11, 'periodic') +
        (229832909 / 423783360)
        * _stencil_shift(halo, -4, -3, 11, 'periodic') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, -3, -3, 11, 'periodic') +
        (201017969 / 36324288)
        * _stencil_shift(halo, -2, -3, 11, 'periodic') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, -1, -3, 11, 'periodic') +
        (169162696711 / 10478160000)
        * _stencil_shift(halo, 0, -3, 11, 'periodic') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, 1, -3, 11, 'periodic') +
        (201017969 / 36324288)
        * _stencil_shift(halo, 2, -3, 11, 'periodic') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, 3, -3, 11, 'periodic') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -3, 11, 'periodic') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, 5, -3, 11, 'periodic') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, 6, -3, 11, 'periodic') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, 7, -3, 11, 'periodic') +
        (268141 / 212357376)
        * _stencil_shift(halo, 8, -3, 11, 'periodic') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, 9, -3, 11, 'periodic') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, 10, -3, 11, 'periodic') +
        (-178939 / 410646075840)
        * _stencil_shift(halo, 11, -3, 11, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 20, -3, 'periodic'] = _fd_d4_a20_axis3_periodic


def _fd_d4_a20_axis3_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 20, axis -3, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 11, 'zero', 4)
    result = (
        (-178939 / 410646075840)
        * _stencil_shift(halo, -11, -3, 11, 'zero') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, -10, -3, 11, 'zero') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, -9, -3, 11, 'zero') +
        (268141 / 212357376)
        * _stencil_shift(halo, -8, -3, 11, 'zero') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, -7, -3, 11, 'zero') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, -6, -3, 11, 'zero') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, -5, -3, 11, 'zero') +
        (229832909 / 423783360)
        * _stencil_shift(halo, -4, -3, 11, 'zero') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, -3, -3, 11, 'zero') +
        (201017969 / 36324288)
        * _stencil_shift(halo, -2, -3, 11, 'zero') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, -1, -3, 11, 'zero') +
        (169162696711 / 10478160000)
        * _stencil_shift(halo, 0, -3, 11, 'zero') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, 1, -3, 11, 'zero') +
        (201017969 / 36324288)
        * _stencil_shift(halo, 2, -3, 11, 'zero') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, 3, -3, 11, 'zero') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -3, 11, 'zero') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, 5, -3, 11, 'zero') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, 6, -3, 11, 'zero') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, 7, -3, 11, 'zero') +
        (268141 / 212357376)
        * _stencil_shift(halo, 8, -3, 11, 'zero') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, 9, -3, 11, 'zero') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, 10, -3, 11, 'zero') +
        (-178939 / 410646075840)
        * _stencil_shift(halo, 11, -3, 11, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 20, -3, 'zero'] = _fd_d4_a20_axis3_zero


def _fd_d4_a20_axis3_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 20, axis -3, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -3, 11, 'reflect', 4)
    result = (
        (-178939 / 410646075840)
        * _stencil_shift(halo, -11, -3, 11, 'reflect') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, -10, -3, 11, 'reflect') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, -9, -3, 11, 'reflect') +
        (268141 / 212357376)
        * _stencil_shift(halo, -8, -3, 11, 'reflect') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, -7, -3, 11, 'reflect') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, -6, -3, 11, 'reflect') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, -5, -3, 11, 'reflect') +
        (229832909 / 423783360)
        * _stencil_shift(halo, -4, -3, 11, 'reflect') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, -3, -3, 11, 'reflect') +
        (201017969 / 36324288)
        * _stencil_shift(halo, -2, -3, 11, 'reflect') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, -1, -3, 11, 'reflect') +
        (169162696711 / 10478160000)
        * _stencil_shift(halo, 0, -3, 11, 'reflect') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, 1, -3, 11, 'reflect') +
        (201017969 / 36324288)
        * _stencil_shift(halo, 2, -3, 11, 'reflect') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, 3, -3, 11, 'reflect') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -3, 11, 'reflect') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, 5, -3, 11, 'reflect') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, 6, -3, 11, 'reflect') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, 7, -3, 11, 'reflect') +
        (268141 / 212357376)
        * _stencil_shift(halo, 8, -3, 11, 'reflect') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, 9, -3, 11, 'reflect') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, 10, -3, 11, 'reflect') +
        (-178939 / 410646075840)
        * _stencil_shift(halo, 11, -3, 11, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 20, -3, 'reflect'] = _fd_d4_a20_axis3_reflect


def _fd_d4_a20_axis2_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 20, axis -2, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 11, 'periodic', 4)
    result = (
        (-178939 / 410646075840)
        * _stencil_shift(halo, -11, -2, 11, 'periodic') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, -10, -2, 11, 'periodic') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, -9, -2, 11, 'periodic') +
        (268141 / 212357376)
        * _stencil_shift(halo, -8, -2, 11, 'periodic') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, -7, -2, 11, 'periodic') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, -6, -2, 11, 'periodic') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, -5, -2, 11, 'periodic') +
        (229832909 / 423783360)
        * _stencil_shift(halo, -4, -2, 11, 'periodic') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, -3, -2, 11, 'periodic') +
        (201017969 / 36324288)
        * _stencil_shift(halo, -2, -2, 11, 'periodic') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, -1, -2, 11, 'periodic') +
        (169162696711 / 10478160000)
        * _stencil_shift(halo, 0, -2, 11, 'periodic') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, 1, -2, 11, 'periodic') +
        (201017969 / 36324288)
        * _stencil_shift(halo, 2, -2, 11, 'periodic') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, 3, -2, 11, 'periodic') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -2, 11, 'periodic') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, 5, -2, 11, 'periodic') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, 6, -2, 11, 'periodic') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, 7, -2, 11, 'periodic') +
        (268141 / 212357376)
        * _stencil_shift(halo, 8, -2, 11, 'periodic') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, 9, -2, 11, 'periodic') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, 10, -2, 11, 'periodic') +
        (-178939 / 410646075840)
        * _stencil_shift(halo, 11, -2, 11, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 20, -2, 'periodic'] = _fd_d4_a20_axis2_periodic


def _fd_d4_a20_axis2_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 20, axis -2, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 11, 'zero', 4)
    result = (
        (-178939 / 410646075840)
        * _stencil_shift(halo, -11, -2, 11, 'zero') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, -10, -2, 11, 'zero') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, -9, -2, 11, 'zero') +
        (268141 / 212357376)
        * _stencil_shift(halo, -8, -2, 11, 'zero') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, -7, -2, 11, 'zero') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, -6, -2, 11, 'zero') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, -5, -2, 11, 'zero') +
        (229832909 / 423783360)
        * _stencil_shift(halo, -4, -2, 11, 'zero') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, -3, -2, 11, 'zero') +
        (201017969 / 36324288)
        * _stencil_shift(halo, -2, -2, 11, 'zero') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, -1, -2, 11, 'zero') +
        (169162696711 / 10478160000)
        * _stencil_shift(halo, 0, -2, 11, 'zero') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, 1, -2, 11, 'zero') +
        (201017969 / 36324288)
        * _stencil_shift(halo, 2, -2, 11, 'zero') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, 3, -2, 11, 'zero') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -2, 11, 'zero') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, 5, -2, 11, 'zero') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, 6, -2, 11, 'zero') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, 7, -2, 11, 'zero') +
        (268141 / 212357376)
        * _stencil_shift(halo, 8, -2, 11, 'zero') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, 9, -2, 11, 'zero') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, 10, -2, 11, 'zero') +
        (-178939 / 410646075840)
        * _stencil_shift(halo, 11, -2, 11, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 20, -2, 'zero'] = _fd_d4_a20_axis2_zero


def _fd_d4_a20_axis2_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 20, axis -2, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -2, 11, 'reflect', 4)
    result = (
        (-178939 / 410646075840)
        * _stencil_shift(halo, -11, -2, 11, 'reflect') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, -10, -2, 11, 'reflect') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, -9, -2, 11, 'reflect') +
        (268141 / 212357376)
        * _stencil_shift(halo, -8, -2, 11, 'reflect') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, -7, -2, 11, 'reflect') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, -6, -2, 11, 'reflect') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, -5, -2, 11, 'reflect') +
        (229832909 / 423783360)
        * _stencil_shift(halo, -4, -2, 11, 'reflect') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, -3, -2, 11, 'reflect') +
        (201017969 / 36324288)
        * _stencil_shift(halo, -2, -2, 11, 'reflect') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, -1, -2, 11, 'reflect') +
        (169162696711 / 10478160000)
        * _stencil_shift(halo, 0, -2, 11, 'reflect') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, 1, -2, 11, 'reflect') +
        (201017969 / 36324288)
        * _stencil_shift(halo, 2, -2, 11, 'reflect') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, 3, -2, 11, 'reflect') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -2, 11, 'reflect') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, 5, -2, 11, 'reflect') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, 6, -2, 11, 'reflect') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, 7, -2, 11, 'reflect') +
        (268141 / 212357376)
        * _stencil_shift(halo, 8, -2, 11, 'reflect') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, 9, -2, 11, 'reflect') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, 10, -2, 11, 'reflect') +
        (-178939 / 410646075840)
        * _stencil_shift(halo, 11, -2, 11, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 20, -2, 'reflect'] = _fd_d4_a20_axis2_reflect


def _fd_d4_a20_axis1_periodic(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 20, axis -1, periodic exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 11, 'periodic', 4)
    result = (
        (-178939 / 410646075840)
        * _stencil_shift(halo, -11, -1, 11, 'periodic') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, -10, -1, 11, 'periodic') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, -9, -1, 11, 'periodic') +
        (268141 / 212357376)
        * _stencil_shift(halo, -8, -1, 11, 'periodic') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, -7, -1, 11, 'periodic') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, -6, -1, 11, 'periodic') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, -5, -1, 11, 'periodic') +
        (229832909 / 423783360)
        * _stencil_shift(halo, -4, -1, 11, 'periodic') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, -3, -1, 11, 'periodic') +
        (201017969 / 36324288)
        * _stencil_shift(halo, -2, -1, 11, 'periodic') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, -1, -1, 11, 'periodic') +
        (169162696711 / 10478160000)
        * _stencil_shift(halo, 0, -1, 11, 'periodic') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, 1, -1, 11, 'periodic') +
        (201017969 / 36324288)
        * _stencil_shift(halo, 2, -1, 11, 'periodic') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, 3, -1, 11, 'periodic') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -1, 11, 'periodic') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, 5, -1, 11, 'periodic') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, 6, -1, 11, 'periodic') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, 7, -1, 11, 'periodic') +
        (268141 / 212357376)
        * _stencil_shift(halo, 8, -1, 11, 'periodic') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, 9, -1, 11, 'periodic') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, 10, -1, 11, 'periodic') +
        (-178939 / 410646075840)
        * _stencil_shift(halo, 11, -1, 11, 'periodic')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 20, -1, 'periodic'] = _fd_d4_a20_axis1_periodic


def _fd_d4_a20_axis1_zero(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 20, axis -1, zero exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 11, 'zero', 4)
    result = (
        (-178939 / 410646075840)
        * _stencil_shift(halo, -11, -1, 11, 'zero') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, -10, -1, 11, 'zero') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, -9, -1, 11, 'zero') +
        (268141 / 212357376)
        * _stencil_shift(halo, -8, -1, 11, 'zero') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, -7, -1, 11, 'zero') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, -6, -1, 11, 'zero') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, -5, -1, 11, 'zero') +
        (229832909 / 423783360)
        * _stencil_shift(halo, -4, -1, 11, 'zero') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, -3, -1, 11, 'zero') +
        (201017969 / 36324288)
        * _stencil_shift(halo, -2, -1, 11, 'zero') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, -1, -1, 11, 'zero') +
        (169162696711 / 10478160000)
        * _stencil_shift(halo, 0, -1, 11, 'zero') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, 1, -1, 11, 'zero') +
        (201017969 / 36324288)
        * _stencil_shift(halo, 2, -1, 11, 'zero') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, 3, -1, 11, 'zero') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -1, 11, 'zero') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, 5, -1, 11, 'zero') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, 6, -1, 11, 'zero') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, 7, -1, 11, 'zero') +
        (268141 / 212357376)
        * _stencil_shift(halo, 8, -1, 11, 'zero') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, 9, -1, 11, 'zero') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, 10, -1, 11, 'zero') +
        (-178939 / 410646075840)
        * _stencil_shift(halo, 11, -1, 11, 'zero')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 20, -1, 'zero'] = _fd_d4_a20_axis1_zero


def _fd_d4_a20_axis1_reflect(values: Any, spacing: float = 1.0) -> Any:
    """Derivative 4, accuracy 20, axis -1, reflect exterior.

    Sum_j c_j f(x+j*h) / h**4, exact moments through degree 22.
    Coefficients below are exact rational constants evaluated in input dtype.
    Torch operations preserve the selected device and autograd graph.
    """
    halo, scale = _stencil_prepare(values, spacing, -1, 11, 'reflect', 4)
    result = (
        (-178939 / 410646075840)
        * _stencil_shift(halo, -11, -1, 11, 'reflect') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, -10, -1, 11, 'reflect') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, -9, -1, 11, 'reflect') +
        (268141 / 212357376)
        * _stencil_shift(halo, -8, -1, 11, 'reflect') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, -7, -1, 11, 'reflect') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, -6, -1, 11, 'reflect') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, -5, -1, 11, 'reflect') +
        (229832909 / 423783360)
        * _stencil_shift(halo, -4, -1, 11, 'reflect') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, -3, -1, 11, 'reflect') +
        (201017969 / 36324288)
        * _stencil_shift(halo, -2, -1, 11, 'reflect') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, -1, -1, 11, 'reflect') +
        (169162696711 / 10478160000)
        * _stencil_shift(halo, 0, -1, 11, 'reflect') +
        (-85758209 / 6985440)
        * _stencil_shift(halo, 1, -1, 11, 'reflect') +
        (201017969 / 36324288)
        * _stencil_shift(halo, 2, -1, 11, 'reflect') +
        (-222362369 / 127135008)
        * _stencil_shift(halo, 3, -1, 11, 'reflect') +
        (229832909 / 423783360)
        * _stencil_shift(halo, 4, -1, 11, 'reflect') +
        (-89727193 / 582120000)
        * _stencil_shift(halo, 5, -1, 11, 'reflect') +
        (235169009 / 6175128960)
        * _stencil_shift(halo, 6, -1, 11, 'reflect') +
        (-4822481 / 617512896)
        * _stencil_shift(halo, 7, -1, 11, 'reflect') +
        (268141 / 212357376)
        * _stencil_shift(halo, 8, -1, 11, 'reflect') +
        (-1552553 / 10352422080)
        * _stencil_shift(halo, 9, -1, 11, 'reflect') +
        (1189505461 / 102661518960000)
        * _stencil_shift(halo, 10, -1, 11, 'reflect') +
        (-178939 / 410646075840)
        * _stencil_shift(halo, 11, -1, 11, 'reflect')
    ) * scale
    if torch is not None and isinstance(result, torch.Tensor):
        return _tensor_finite(result, "stencil result")
    return _array(result)

STENCIL_KERNELS[4, 20, -1, 'reflect'] = _fd_d4_a20_axis1_reflect


# END EXACT GENERATED STENCIL SPECIALIZATIONS


class SpectralConv2d(_Module):
    """Truncated Fourier convolution: y_hat[o,k]=sum_i W[o,i,k] x_hat[i,k].

    Both positive and negative first-axis frequencies are learned; disjoint mode
    bands prevent overwrites. NumPy implements inference when Torch is absent.
    """
    is_available = np is not None or torch is not None

    def __init__(self, in_channels: int, out_channels: int, modes1: int = 8,
                 modes2: int = 8, seed: int = 0) -> None:
        super().__init__()
        self.in_channels = _budget(in_channels, 4096)
        self.out_channels = _budget(out_channels, 4096)
        self.modes1, self.modes2 = _budget(modes1, 4096), _budget(modes2, 4096)
        shape = (in_channels, out_channels, modes1, modes2)
        if math.prod(shape) > 16_000_000:
            raise ValueError('Spectral weight budget exceeded')
        scale = 1 / math.sqrt(in_channels * out_channels)
        if torch is not None:
            generator = torch.Generator().manual_seed(seed)
            self.weights1 = nn.Parameter(scale * torch.randn(shape, dtype=torch.cfloat, generator=generator))
            self.weights2 = nn.Parameter(scale * torch.randn(shape, dtype=torch.cfloat, generator=generator))
        else:
            rng = _require(np, 'numpy').random.default_rng(seed)
            self.weights1 = scale * (rng.normal(size=shape) + 1j * rng.normal(size=shape))
            self.weights2 = scale * (rng.normal(size=shape) + 1j * rng.normal(size=shape))

    def forward(self, x: Any) -> Any:
        if torch is not None and isinstance(x, torch.Tensor):
            if x.ndim != 4 or x.shape[1] != self.in_channels or not torch.isfinite(x).all():
                raise ValueError('Expected finite [batch,channels,height,width] tensor')
            h, w = x.shape[-2:]
            m, n = min(self.modes1, h // 2), min(self.modes2, w // 2 + 1)
            if m == 0:
                raise ValueError('At least two spatial rows required')
            ft = torch.fft.rfft2(x)
            out = torch.zeros((x.shape[0], self.out_channels, h, w // 2 + 1), dtype=ft.dtype, device=x.device)
            out[:, :, :m, :n] = torch.einsum('bixy,ioxy->boxy', ft[:, :, :m, :n], self.weights1[:, :, :m, :n].to(dtype=ft.dtype))
            out[:, :, -m:, :n] = torch.einsum('bixy,ioxy->boxy', ft[:, :, -m:, :n], self.weights2[:, :, :m, :n].to(dtype=ft.dtype))
            result = torch.fft.irfft2(out, s=(h, w))
            if not torch.isfinite(result).all():
                raise ValueError('Nonfinite spectral result')
            return result
        x = _array(x, 4)
        if x.shape[1] != self.in_channels:
            raise ValueError('Channel mismatch')
        h, w = x.shape[-2:]
        m, n = min(self.modes1, h // 2), min(self.modes2, w // 2 + 1)
        if m == 0:
            raise ValueError('At least two spatial rows required')
        weights = [v.detach().cpu().numpy() if torch is not None else v for v in (self.weights1, self.weights2)]
        ft = np.fft.rfft2(x)
        out = np.zeros((x.shape[0], self.out_channels, h, w // 2 + 1), complex)
        out[:, :, :m, :n] = np.einsum('bixy,ioxy->boxy', ft[:, :, :m, :n], weights[0][:, :, :m, :n])
        out[:, :, -m:, :n] = np.einsum('bixy,ioxy->boxy', ft[:, :, -m:, :n], weights[1][:, :, :m, :n])
        return _array(np.fft.irfft2(out, s=(h, w)), 4)

    if nn is None:
        __call__ = forward


class FourierNeuralOperator2D(_Module):
    """FNO: lift to width channels, iterate GELU(K_spectral u + W u), project.

    Input and output layouts are [batch,channels,height,width]. Training requires
    Torch; NumPy inference uses identically seeded finite matrices.
    """
    is_available = np is not None or torch is not None

    def __init__(self, in_channels: int = 1, out_channels: int = 1, width: int = 16,
                 modes: int = 8, layers: int = 4, seed: int = 0) -> None:
        super().__init__()
        _budget(width, 512); _budget(layers, 32)
        _budget(in_channels, 4096); _budget(out_channels, 4096)
        self.in_channels = in_channels
        spectral = [SpectralConv2d(width, width, modes, modes, seed + i) for i in range(layers)]
        if nn is not None:
            # fork_rng prevents constructor side effects on the caller's RNG.
            with torch.random.fork_rng(devices=[]):
                torch.random.default_generator.manual_seed(seed)
                self.lift = nn.Conv2d(in_channels, width, 1)
                self.spectral = nn.ModuleList(spectral)
                self.bypass = nn.ModuleList(nn.Conv2d(width, width, 1) for _ in spectral)
                self.projection = nn.Sequential(nn.Conv2d(width, width, 1), nn.GELU(), nn.Conv2d(width, out_channels, 1))
        else:
            rng = _require(np, 'numpy').random.default_rng(seed)
            self.spectral = spectral
            self.lift = rng.normal(size=(width, in_channels)) / math.sqrt(in_channels)
            self.bypass = [rng.normal(size=(width, width)) / math.sqrt(width) for _ in spectral]
            self.projection = rng.normal(size=(out_channels, width)) / math.sqrt(width)

    def forward(self, x: Any) -> Any:
        if nn is not None:
            if not isinstance(x, torch.Tensor) or x.ndim != 4 or x.shape[1] != self.in_channels or not torch.isfinite(x).all():
                raise ValueError('FNO requires a finite Torch NCHW tensor')
            x = self.lift(x)
            for spectral, bypass in zip(self.spectral, self.bypass):
                x = nn.functional.gelu(spectral(x) + bypass(x))
            result = self.projection(x)
            if not torch.isfinite(result).all():
                raise ValueError('Nonfinite FNO result')
            return result
        x = _array(x, 4)
        if x.shape[1] != self.in_channels:
            raise ValueError('FNO channel mismatch')
        x = np.einsum('oi,bihw->bohw', self.lift, x)
        for spectral, bypass in zip(self.spectral, self.bypass):
            x = spectral(x) + np.einsum('oi,bihw->bohw', bypass, x)
            x = .5 * x * (1 + np.tanh(math.sqrt(2 / math.pi) * (x + .044715 * x ** 3)))
        return _array(np.einsum('oi,bihw->bohw', self.projection, x), 4)

    if nn is None:
        __call__ = forward


class DeepONet(_Module):
    """Separable operator G(u)(y)=sum_k branch_k(u) trunk_k(y)+b."""
    is_available = torch is not None

    def __init__(self, sensors: int, coordinates: int = 3, width: int = 64, seed: int = 0) -> None:
        _require(nn, 'torch')
        super().__init__()
        for value in (sensors, coordinates, width):
            _budget(value, 4096)
        with torch.random.fork_rng(devices=[]):
            torch.random.default_generator.manual_seed(seed)
            self.branch = nn.Sequential(nn.Linear(sensors, width), nn.Tanh(), nn.Linear(width, width))
            self.trunk = nn.Sequential(nn.Linear(coordinates, width), nn.Tanh(), nn.Linear(width, width))
            self.bias = nn.Parameter(torch.zeros(1))

    def forward(self, functions: Any, coordinates: Any) -> Any:
        if not torch.isfinite(functions).all() or not torch.isfinite(coordinates).all():
            raise ValueError('DeepONet inputs must be finite')
        result = self.branch(functions) @ self.trunk(coordinates).T + self.bias
        if not torch.isfinite(result).all():
            raise ValueError('Nonfinite DeepONet output')
        return result


class PhysicsInformedEnforcer:
    """Audit viscous momentum residual and relative Hamiltonian drift.

    A callable field with autograd coordinates [t,x,y] uses exact AD derivatives.
    Sampled [time,y,x,2] velocities use finite differences, labelled numerical.
    Pressure-free residual is Burgers momentum; Navier--Stokes also needs pressure
    and divergence. Conservation rejection calls an explicit exact fallback.
    """
    def __init__(self, viscosity: float = .01, spacing: Sequence[float] = (1, 1, 1),
                 exact_fallback: Callable[[Any], Any] | None = None) -> None:
        self.viscosity = _positive(viscosity, zero=True)
        self.spacing = tuple(_positive(v, 'spacing') for v in spacing)
        if len(self.spacing) != 3:
            raise ValueError('Spacing must be dt,dy,dx')
        self.exact_fallback = exact_fallback

    def compute_pde_residual(self, field: Any, pde_type: str = 'navier_stokes', *,
                             coordinates: Any = None, pressure: Any = None) -> Any:
        if pde_type not in {'navier_stokes', 'burgers'}:
            raise ValueError('Unsupported PDE')
        if callable(field):
            _require(torch, 'torch')
            if coordinates is None or not coordinates.requires_grad or coordinates.shape[-1] != 3:
                raise ValueError('Autograd coordinates [t,x,y] required')
            velocity = field(coordinates)
            if velocity.ndim != 2 or velocity.shape[1] != 2 or not torch.isfinite(velocity).all():
                raise ValueError('Field must return finite [n,2] velocities')
            def grad(v: Any) -> Any:
                if not v.requires_grad:
                    return coordinates * 0
                g = torch.autograd.grad(v.sum(), coordinates, create_graph=True, allow_unused=True)[0]
                return coordinates * 0 if g is None else g
            gradients = [grad(velocity[:, i]) for i in range(2)]
            residual = []
            if pde_type == 'navier_stokes':
                if pressure is None:
                    raise ValueError('Navier--Stokes needs a pressure field')
                pg = grad(pressure(coordinates).reshape(-1))
            for i, g in enumerate(gradients):
                lap = grad(g[:, 1])[:, 1] + grad(g[:, 2])[:, 2]
                r = g[:, 0] + (velocity * g[:, 1:]).sum(-1) - self.viscosity * lap
                residual.append(r + pg[:, i + 1] if pde_type == 'navier_stokes' else r)
            if pde_type == 'navier_stokes':
                residual.append(gradients[0][:, 1] + gradients[1][:, 2])
            result = torch.stack(residual, -1)
            if not torch.isfinite(result).all():
                raise ValueError('Nonfinite PDE residual')
            return result
        if torch is not None and isinstance(field, torch.Tensor):
            return self.compute_tensor_residual(field, pressure, pde_type)
        u = _array(field, 4)
        if u.shape[-1] != 2 or min(u.shape[:3]) < 3:
            raise ValueError('Sampled velocity needs [t,y,x,2] with at least three samples per axis')
        dt, dy, dx = self.spacing
        ut, uy, ux = np.gradient(u, dt, dy, dx, axis=(0, 1, 2), edge_order=2)
        lap = np.gradient(uy, dy, axis=1, edge_order=2) + np.gradient(ux, dx, axis=2, edge_order=2)
        r = ut + u[..., 0, None] * ux + u[..., 1, None] * uy - self.viscosity * lap
        if pde_type == 'navier_stokes':
            p = _array(pressure, 3)
            if p.shape != u.shape[:3]:
                raise ValueError('Pressure shape mismatch')
            py, px = np.gradient(p, dy, dx, axis=(1, 2), edge_order=2)
            r += np.stack([px, py], -1)
            r = np.concatenate([r, (ux[..., 0] + uy[..., 1])[..., None]], -1)
        return _array(r)

    def compute_tensor_residual(self, velocity: Any, pressure: Any = None,
                               pde_type: str = 'navier_stokes', accuracy: int = 2,
                               boundary: str = 'periodic') -> Any:
        """Device-native momentum and divergence on [...,time,y,x,2] fields.

        Components are Cartesian (u_x,u_y). The residual is d_t u+u.grad(u)
        +grad(p)-nu Laplacian(u), followed by div(u) for incompressible flow.
        All finite-difference operations remain differentiable Torch tensors.
        """
        velocity = _tensor_finite(velocity, 'velocity')
        if velocity.ndim < 4 or velocity.shape[-1] != 2:
            raise ValueError('Velocity must have shape [...,time,y,x,2]')
        if pde_type not in {'navier_stokes', 'burgers'}:
            raise ValueError('Unsupported tensor PDE')
        dt, dy, dx = self.spacing
        components = velocity.unbind(-1)
        spatial = []
        residuals = []
        for component in components:
            temporal = GPUStencilBank.derivative(component, dt, axis=-3, accuracy=accuracy, boundary=boundary)
            gy = GPUStencilBank.derivative(component, dy, axis=-2, accuracy=accuracy, boundary=boundary)
            gx = GPUStencilBank.derivative(component, dx, axis=-1, accuracy=accuracy, boundary=boundary)
            laplacian = GPUStencilBank.laplacian(component, [dy, dx], accuracy, boundary)
            residuals.append(temporal+components[0]*gx+components[1]*gy-self.viscosity*laplacian)
            spatial.append((gx, gy))
        if pde_type == 'navier_stokes':
            if pressure is None:
                raise ValueError('Navier--Stokes tensor residual needs pressure')
            pressure = torch.as_tensor(pressure, device=velocity.device, dtype=velocity.dtype)
            _tensor_finite(pressure, 'pressure')
            if pressure.shape != velocity.shape[:-1]:
                raise ValueError('Pressure grid must match velocity grid')
            residuals[0] += GPUStencilBank.derivative(pressure, dx, axis=-1, accuracy=accuracy, boundary=boundary)
            residuals[1] += GPUStencilBank.derivative(pressure, dy, axis=-2, accuracy=accuracy, boundary=boundary)
            residuals.append(spatial[0][0]+spatial[1][1])
        return _tensor_finite(torch.stack(residuals, -1), 'PDE residual')

    def enforce_conservation_law(self, field: Any, law: str = 'energy') -> dict[str, Any]:
        if law != 'energy':
            raise ValueError('Provide an explicit Hamiltonian series for energy auditing')
        if torch is not None and isinstance(field, torch.Tensor):
            field = _tensor_finite(field, 'Hamiltonian series').detach().cpu().numpy()
        energies = _array(field, 1)
        baseline = abs(float(energies[0]))
        if baseline:
            # Normalize before subtracting, so opposite-sign finite Hamiltonians
            # cannot overflow their difference. Unrepresentable ratios fail closed.
            with np.errstate(over='ignore'):
                relative = np.abs(energies/baseline-energies[0]/baseline)
            drift = float(relative.max()) if np.isfinite(relative).all() else None
        else:
            drift = 0.0 if np.all(energies == 0) else None
        violation = drift is None or drift > 1e-4
        if violation and self.exact_fallback is None:
            raise RuntimeError('Conservation violation; neural acceleration aborted; exact_fallback required')
        return {'violation': violation, 'relative_drift': drift, 'neural_allowed': not violation,
                'exact_result': self.exact_fallback(field) if violation else None}

# SECTION 2: causal DAGs, NOTEARS, sparse GP and active acquisition
class CausalStructuralModel:
    """Finite discrete Bayesian DAG with exact truncated factorization.

    CPT keys are parent-value tuples in declared parent order; values map states
    to rational probabilities. do(X=x) replaces that factor with a point mass.
    This identifies interventional marginals, not unobserved individual outcomes.
    """
    def __init__(self, domains: Mapping[str, Sequence[Any]], parents: Mapping[str, Sequence[str]],
                 cpts: Mapping[str, Mapping[tuple[Any, ...], Mapping[Any, Any]]]) -> None:
        self.domains = {k: tuple(v) for k, v in domains.items()}
        self.parents = {k: tuple(parents.get(k, ())) for k in domains}
        if not self.domains or math.prod(len(v) for v in self.domains.values()) > 1_000_000:
            raise ValueError('Finite state space exceeds enumeration budget')
        if set(parents) - set(domains) or set(cpts) != set(domains):
            raise ValueError('DAG keys mismatch')
        remaining, order = set(domains), []
        while remaining:
            ready = sorted(k for k in remaining if set(self.parents[k]) <= set(order))
            if not ready:
                raise ValueError('Graph must be a DAG with known parents')
            order.extend(ready); remaining.difference_update(ready)
        self.order = order
        self.cpts: dict[str, Any] = {}
        for k in order:
            if not self.domains[k] or len(set(self.domains[k])) != len(self.domains[k]) or len(set(self.parents[k])) != len(self.parents[k]):
                raise ValueError('Domains and parent lists must be nonempty/unique')
            table = {}
            required = set(itertools.product(*(self.domains[p] for p in self.parents[k])))
            if set(cpts[k]) != required:
                raise ValueError('Incomplete CPT')
            for key, row in cpts[k].items():
                values = {s: Fraction(str(p)) for s, p in row.items()}
                if set(values) != set(self.domains[k]) or any(p < 0 for p in values.values()) or sum(values.values()) != 1:
                    raise ValueError('CPT must be a normalized nonnegative distribution')
                table[key] = values
            self.cpts[k] = table

    def do_calculus(self, target: str, intervention: Mapping[str, Any] | None = None) -> dict[Any, Fraction]:
        intervention = dict(intervention or {})
        if target not in self.domains or any(k not in self.domains or v not in self.domains[k] for k, v in intervention.items()):
            raise ValueError('Unknown intervention or target')
        output = dict.fromkeys(self.domains[target], Fraction(0))
        for states in itertools.product(*(self.domains[k] for k in self.order)):
            assignment = dict(zip(self.order, states))
            if any(assignment[k] != v for k, v in intervention.items()):
                continue
            weight = Fraction(1)
            for k in self.order:
                if k not in intervention:
                    weight *= self.cpts[k][tuple(assignment[p] for p in self.parents[k])][assignment[k]]
            output[assignment[target]] += weight
        if sum(output.values()) != 1:
            raise ArithmeticError('Truncated distribution failed normalization')
        return output


class NOTEARSDiscovery:
    """Linear NOTEARS: least squares + L1 under h(W)=tr exp(W*W)-d=0.

    Augmented Lagrangian iterates expose convergence. Thresholded edges are
    cycle-pruned and reported separately from the continuous optimization.
    Observational DAG fitting alone does not identify causal mechanisms.
    """
    is_available = scipy is not None and np is not None

    def fit(self, data: Any, l1: float = .01, max_iter: int = 20,
            tolerance: float = 1e-8, threshold: float = .3, device: str | None = None,
            seed: int = 0, inner_steps: int = 200, learning_rate: float = .01) -> dict[str, Any]:
        if device is not None:
            return self.fit_torch(data, l1, max_iter, tolerance, threshold, device, seed, inner_steps, learning_rate)
        _require(scipy, 'scipy')
        from scipy.linalg import expm
        from scipy.optimize import minimize
        x = _array(data, 2)
        n, d = x.shape
        if n < 2 or not 1 <= d <= 128:
            raise ValueError('NOTEARS requires >=2 samples and <=128 variables')
        l1 = _positive(l1, zero=True); tolerance = _positive(tolerance)
        threshold = _positive(threshold, zero=True); _budget(max_iter, 1000)
        x = x - x.mean(0)
        w = np.zeros((d, d)); rho, alpha, previous = 1.0, 0.0, math.inf
        bounds = [(0, 0) if i == j else (0, None) for _ in range(2) for i in range(d) for j in range(d)]
        converged = False
        for _ in range(max_iter):
            def objective(v: Any) -> tuple[float, Any]:
                matrix = (v[:d*d] - v[d*d:]).reshape(d, d)
                e = expm(matrix * matrix)
                h = np.trace(e) - d
                residual = x - x @ matrix
                grad = -x.T @ residual / n + (rho * h + alpha) * e.T * 2 * matrix
                loss = .5 * np.sum(residual ** 2) / n + l1 * v.sum() + .5 * rho * h * h + alpha * h
                if not np.isfinite(loss) or not np.isfinite(grad).all():
                    raise ValueError('Nonfinite NOTEARS optimization')
                return float(loss), np.concatenate([grad.ravel() + l1, -grad.ravel() + l1])
            initial = np.concatenate([np.maximum(w, 0).ravel(), np.maximum(-w, 0).ravel()])
            result = minimize(objective, initial, jac=True, bounds=bounds, method='L-BFGS-B')
            w = (result.x[:d*d] - result.x[d*d:]).reshape(d, d)
            h = float(np.trace(expm(w * w)) - d)
            if h <= tolerance:
                converged = bool(result.success); break
            if h > .25 * previous:
                rho *= 10
            alpha += rho * h; previous = h
            if rho > 1e16:
                break
        dag = np.zeros_like(w)
        def reaches(start: int, end: int) -> bool:
            stack, seen = [start], set()
            while stack:
                node = stack.pop()
                if node == end:
                    return True
                if node not in seen:
                    seen.add(node); stack.extend(np.flatnonzero(dag[node]).tolist())
            return False
        for i, j in sorted(itertools.product(range(d), repeat=2), key=lambda ij: -abs(w[ij])):
            if i != j and abs(w[i, j]) > threshold and not reaches(j, i):
                dag[i, j] = w[i, j]
        return {'weights': dag, 'continuous_weights': w, 'acyclicity_residual': h,
                'converged': converged, 'causal_identification': False}

    def fit_torch(self, data: Any, l1: float = .01, max_iter: int = 20,
                  tolerance: float = 1e-8, threshold: float = .3, device: str = 'auto',
                  seed: int = 0, inner_steps: int = 200, learning_rate: float = .01) -> dict[str, Any]:
        """Torch NOTEARS with matrix-exponential gradients on the selected device.

        Nonnegative split parameters W=W_plus-W_minus encode the L1 penalty.
        Projected Adam solves each augmented objective; convergence is measured
        independently by h(W) and is never inferred from an optimizer return code.
        """
        runtime = DeviceRuntime(device, seed, 'float64')
        x = runtime.tensor(data)
        _budget(max_iter, 1000); _budget(inner_steps, 10000)
        l1 = _positive(l1, zero=True); tolerance = _positive(tolerance)
        threshold = _positive(threshold, zero=True); learning_rate = _positive(learning_rate)
        if x.ndim != 2 or x.shape[0] < 2 or not 1 <= x.shape[1] <= 128:
            raise ValueError('NOTEARS requires >=2 samples and <=128 variables')
        runtime.begin()
        x = x-x.mean(0); n, d = x.shape
        split = torch.nn.Parameter(torch.zeros((2, d, d), dtype=x.dtype, device=x.device))
        mask = 1-torch.eye(d, dtype=x.dtype, device=x.device)
        rho, alpha, previous = 1., 0., math.inf
        optimizer = torch.optim.Adam([split], lr=learning_rate)
        h_value = math.inf; loss_value = math.inf
        for outer in range(max_iter):
            for _ in range(inner_steps):
                optimizer.zero_grad(set_to_none=True)
                w = (split[0]-split[1])*mask
                residual = x-x@w
                h = torch.trace(torch.matrix_exp(w.square()))-d
                loss = .5*residual.square().sum()/n+l1*split.sum()+alpha*h+.5*rho*h.square()
                _tensor_finite(loss, 'NOTEARS objective')
                loss.backward(); _tensor_finite(split.grad, 'NOTEARS gradient')
                torch.nn.utils.clip_grad_norm_([split], 100., error_if_nonfinite=True)
                optimizer.step()
                with torch.no_grad():
                    split.clamp_(min=0); split.mul_(mask)
            with torch.no_grad():
                w = (split[0]-split[1])*mask
                h_value = max(0., float((torch.trace(torch.matrix_exp(w.square()))-d).cpu()))
                loss_value = float(loss.detach().cpu())
            if h_value <= tolerance:
                break
            if h_value > .25*previous:
                rho = min(rho*10, 1e16)
            alpha += rho*h_value; previous = h_value
        continuous = _tensor_finite(w.detach(), 'NOTEARS weights')
        host = continuous.cpu().numpy(); dag = np.zeros_like(host)
        def reaches(start: int, end: int) -> bool:
            stack, seen = [start], set()
            while stack:
                node = stack.pop()
                if node == end:
                    return True
                if node not in seen:
                    seen.add(node); stack.extend(np.flatnonzero(dag[node]).tolist())
            return False
        for i, j in sorted(itertools.product(range(d), repeat=2), key=lambda ij: -abs(host[ij])):
            if i != j and abs(host[i, j]) > threshold and not reaches(j, i):
                dag[i, j] = host[i, j]
        runtime.finish()
        return {'weights': torch.as_tensor(dag, dtype=x.dtype, device=x.device),
                'continuous_weights': continuous, 'acyclicity_residual': h_value,
                'converged': h_value <= tolerance, 'objective': loss_value, 'iterations': outer+1,
                'causal_identification': False, 'execution': runtime.information()}


class SparseGaussianProcessSurrogate:
    """Streaming Nyström GP via whitened inducing features phi=K_xm L_mm^-T.

    Bayesian linear regression accumulates A=I+Phi^T Phi/noise and b in O(m²)
    memory; predictive variance is conditional prior residual + phi A^-1 phi^T.
    Uncertainty is model-dependent, not a certified interval for the true system.
    """
    is_available = np is not None

    def __init__(self, inducing_points: Any, length_scale: float = 1, noise: float = 1e-4,
                 device: str | None = None) -> None:
        if device is not None:
            self._initialize_device(inducing_points, length_scale, noise, device)
            return
        self._on_device = False
        self.points = _array(inducing_points, 2)
        if len(self.points) > 2048:
            raise ValueError('Inducing point budget exceeded')
        self.length_scale = _positive(length_scale)
        self.length_scale_squared = _positive(self.length_scale*self.length_scale, 'squared length scale')
        self.noise = _positive(noise)
        self.chol = np.linalg.cholesky(self._kernel(self.points, self.points) + np.eye(len(self.points)) * 1e-10)
        self.a = np.eye(len(self.points)); self.b = np.zeros(len(self.points)); self.samples = 0

    def _kernel(self, x: Any, y: Any) -> Any:
        distance = np.maximum((x*x).sum(1)[:, None] + (y*y).sum(1) - 2 * x @ y.T, 0)
        return _array(np.exp(-.5 * distance / self.length_scale_squared))

    def partial_fit(self, x: Any, y: Any) -> SparseGaussianProcessSurrogate:
        if self._on_device:
            return self._partial_fit_device(x, y)
        x, y = _array(x, 2), _array(y, 1)
        if x.shape[1] != self.points.shape[1] or len(x) != len(y):
            raise ValueError('GP dimensions mismatch')
        for start in range(0, len(x), 4096):
            phi = np.linalg.solve(self.chol, self._kernel(x[start:start+4096], self.points).T).T
            self.a += phi.T @ phi / self.noise
            self.b += phi.T @ y[start:start+4096] / self.noise
        _array(self.a); _array(self.b)
        self.samples += len(x)
        return self

    fit = partial_fit

    def predict(self, x: Any) -> tuple[Any, Any]:
        if self._on_device:
            return self._predict_device(x)
        x = _array(x, 2)
        if self.samples == 0 or x.shape[1] != self.points.shape[1]:
            raise ValueError('Fit GP before prediction with matching dimensions')
        means, variances = [], []
        chol = np.linalg.cholesky(self.a)
        beta = np.linalg.solve(chol.T, np.linalg.solve(chol, self.b))
        for start in range(0, len(x), 4096):
            phi = np.linalg.solve(self.chol, self._kernel(x[start:start+4096], self.points).T).T
            projected = np.linalg.solve(chol, phi.T)
            means.append(phi @ beta)
            variances.append(np.maximum(1 - (phi*phi).sum(1), 0) + (projected*projected).sum(0))
        return _array(np.concatenate(means)), _array(np.concatenate(variances))

    def _initialize_device(self, points: Any, length_scale: float, noise: float, device: str) -> None:
        self.runtime = DeviceRuntime(device, dtype='float64')
        self.points = self.runtime.tensor(points)
        if self.points.ndim != 2 or len(self.points) > 2048:
            raise ValueError('Inducing points must be [m,d], m<=2048')
        self.length_scale = _positive(length_scale)
        self.length_scale_squared = _positive(self.length_scale*self.length_scale, 'squared length scale')
        self.noise = _positive(noise); self.samples = 0; self._on_device = True
        m = len(self.points)
        identity = torch.eye(m, dtype=self.points.dtype, device=self.points.device)
        self.chol = torch.linalg.cholesky(self._kernel_device(self.points, self.points)+1e-10*identity)
        self.a = identity.clone(); self.b = torch.zeros(m, dtype=self.points.dtype, device=self.points.device)

    def _kernel_device(self, x: Any, y: Any) -> Any:
        distance = torch.cdist(x, y).square()
        return _tensor_finite(torch.exp(-.5*distance/self.length_scale_squared), 'RBF kernel')

    def _partial_fit_device(self, x: Any, y: Any) -> SparseGaussianProcessSurrogate:
        x, y = self.runtime.tensor(x), self.runtime.tensor(y)
        if x.ndim != 2 or y.ndim != 1 or x.shape[1] != self.points.shape[1] or len(x) != len(y):
            raise ValueError('GP observation dimensions mismatch')
        self.runtime.begin()
        for start in range(0, len(x), 4096):
            phi = torch.linalg.solve_triangular(self.chol, self._kernel_device(x[start:start+4096], self.points).T, upper=False).T
            self.a += phi.T@phi/self.noise
            self.b += phi.T@y[start:start+4096]/self.noise
        _tensor_finite(self.a, 'GP precision'); _tensor_finite(self.b, 'GP information vector')
        self.samples += len(x); self.runtime.finish()
        return self

    def _predict_device(self, x: Any) -> tuple[Any, Any]:
        x = self.runtime.tensor(x)
        if self.samples == 0 or x.ndim != 2 or x.shape[1] != self.points.shape[1]:
            raise ValueError('Fit GP and provide matching query coordinates')
        chol = torch.linalg.cholesky(self.a)
        beta = torch.cholesky_solve(self.b[:, None], chol)[:, 0]
        means, variances = [], []
        for start in range(0, len(x), 4096):
            phi = torch.linalg.solve_triangular(self.chol, self._kernel_device(x[start:start+4096], self.points).T, upper=False).T
            projected = torch.linalg.solve_triangular(chol, phi.T, upper=False)
            means.append(phi@beta)
            variances.append((1-phi.square().sum(1)).clamp_min(0)+projected.square().sum(0))
        return _tensor_finite(torch.cat(means), 'GP posterior mean'), _tensor_finite(torch.cat(variances), 'GP posterior variance')

    def fit_stream(self, chunks: Iterable[tuple[Any, Any]]) -> SparseGaussianProcessSurrogate:
        """Accumulate inducing-point sufficient statistics over external data chunks."""
        for x, y in chunks:
            self.partial_fit(x, y)
        return self

    def predict_stream(self, chunks: Iterable[Any]) -> Iterator[tuple[Any, Any]]:
        """Yield posterior chunks without materializing an entire query dataset."""
        for x in chunks:
            yield self.predict(x)


class ActiveAcquisitionOptimizer:
    """Maximization acquisition: EI=(mu-best)Phi(z)+sigma phi(z); UCB=mu+k sigma."""
    def score(self, mean: Any, variance: Any, best: float = 0, method: str = 'ei', kappa: float = 2) -> Any:
        if torch is not None and isinstance(mean, torch.Tensor):
            return self.score_torch(mean, variance, best, method, kappa)
        mean, variance = _array(mean), _array(variance)
        if mean.shape != variance.shape or (variance < 0).any():
            raise ValueError('Acquisition variance must be nonnegative and shape-compatible')
        best = _finite(best); kappa = _positive(kappa, zero=True)
        sigma = np.sqrt(variance)
        if method == 'ucb':
            return _array(mean + kappa * sigma)
        if method != 'ei':
            raise ValueError('Acquisition must be ei or ucb')
        delta = mean - best
        z = np.divide(delta, sigma, out=np.zeros_like(delta), where=sigma > 0)
        cdf = .5 * (1 + np.vectorize(math.erf)(z / math.sqrt(2)))
        return _array(np.where(sigma > 0, delta*cdf + sigma*np.exp(-z*z/2)/math.sqrt(2*math.pi), np.maximum(delta, 0)))

    def score_torch(self, mean: Any, variance: Any, best: float = 0,
                    method: str = 'ei', kappa: float = 2) -> Any:
        """EI/UCB on native tensors using differentiable erf and Gaussian density."""
        _tensor_finite(mean); _tensor_finite(variance)
        if mean.shape != variance.shape or mean.device != variance.device or bool((variance < 0).any()):
            raise ValueError('Acquisition mean/variance must share shape/device and variance must be nonnegative')
        best = _finite(best); kappa = _positive(kappa, zero=True)
        sigma = variance.sqrt()
        if method == 'ucb':
            return _tensor_finite(mean+kappa*sigma)
        if method != 'ei':
            raise ValueError('Acquisition must be ei or ucb')
        delta = mean-best
        z = delta/sigma.clamp_min(torch.finfo(sigma.dtype).tiny)
        cdf = .5*(1+torch.erf(z/math.sqrt(2)))
        density = torch.exp(-.5*z.square())/math.sqrt(2*math.pi)
        score = torch.where(sigma > 0, delta*cdf+sigma*density, delta.clamp_min(0))
        return _tensor_finite(score, 'expected improvement')

    def select(self, candidates: Any, surrogate: SparseGaussianProcessSurrogate, **kwargs: Any) -> Any:
        if surrogate._on_device:
            candidates = surrogate.runtime.tensor(candidates)
            return candidates[torch.argmax(self.score(*surrogate.predict(candidates), **kwargs))]
        candidates = _array(candidates, 2)
        return candidates[int(np.argmax(self.score(*surrogate.predict(candidates), **kwargs)))]

# SECTION 3: spectral radiometry and Monte Carlo path integration
@dataclass
class SpectralRay:
    """Ray r(t)=origin+t direction with 32 nonnegative spectral power samples.

    Wavelengths cover 380--780 nm inclusive; direction is normalized so t is a
    geometric distance and Beer--Lambert transmittance uses consistent units.
    """
    origin: Any
    direction: Any
    spd: Any = None

    def __post_init__(self) -> None:
        self.origin = _array(self.origin, 1)
        self.direction = _unit(self.direction)
        self.spd = np.ones(32) if self.spd is None else _array(self.spd, 1)
        if self.origin.shape != (3,) or self.spd.shape != (32,) or (self.spd < 0).any():
            raise ValueError('Ray requires a 3D origin and 32 nonnegative spectral samples')

    @property
    def wavelengths(self) -> Any:
        return np.linspace(380, 780, 32)


class MicrofacetBSDF:
    """Cook--Torrance GGX: f=D(h)G(wi,wo)F(wi.h)/(4 cos_i cos_o).

    Smith masking uses separable GGX G1. Schlick F uses real complex-IOR normal
    reflectance ((n-1)^2+k^2)/((n+1)^2+k^2). A dielectric diffuse substrate
    contributes (1-F)albedo/pi; metallic materials have no diffuse substrate.
    """
    def __init__(self, roughness: float = .4, n: Any = 1.5, k: Any = 0,
                 albedo: Any = .5, metallic: bool = False) -> None:
        _require(np, 'numpy')
        self.roughness = _positive(roughness)
        if self.roughness > 1:
            raise ValueError('Roughness must be <=1')
        self.alpha = max(self.roughness ** 2, 1e-4)
        self.n = np.broadcast_to(_array(n), (32,)).copy()
        self.k = np.broadcast_to(_array(k), (32,)).copy()
        self.albedo = np.broadcast_to(_array(albedo), (32,)).copy()
        if (self.n <= 0).any() or (self.k < 0).any() or (self.albedo < 0).any() or (self.albedo > 1).any():
            raise ValueError('Invalid IOR or reflectance')
        self.metallic = bool(metallic)

    def evaluate(self, incoming: Any, outgoing: Any, normal: Any) -> Any:
        wi, wo, normal = _unit(incoming), _unit(outgoing), _unit(normal)
        ci, co = float(wi @ normal), float(wo @ normal)
        if min(ci, co) <= 0:
            return np.zeros(32)
        half = _unit(wi + wo)
        ch = max(float(half @ normal), 0)
        a2 = self.alpha ** 2
        d = a2 / (math.pi * (ch*ch*(a2-1)+1) ** 2)
        def g1(c: float) -> float:
            return 2*c/(c + math.sqrt(a2 + (1-a2)*c*c))
        f0 = ((self.n-1)**2 + self.k**2)/((self.n+1)**2 + self.k**2)
        fresnel = f0 + (1-f0)*(1-max(0.0, float(wi @ half)))**5
        specular = d * g1(ci) * g1(co) * fresnel / (4*ci*co)
        diffuse = 0 if self.metallic else (1-fresnel)*self.albedo/math.pi
        return _array(specular + diffuse)


class VolumetricMedia:
    """Homogeneous medium: T(d)=exp[-(sigma_a+sigma_s)d].

    Henyey--Greenstein phase p(cos theta)=(1-g²)/(4pi(1+g²-2g cos theta)^1.5).
    Coefficients are spectral inverse lengths, not material presets inferred from
    names. Free-path sampling is available for explicit scattering integrators.
    """
    def __init__(self, sigma_a: Any = 0, sigma_s: Any = 0, g: float = 0) -> None:
        _require(np, 'numpy')
        self.sigma_a = np.broadcast_to(_array(sigma_a), (32,)).copy()
        self.sigma_s = np.broadcast_to(_array(sigma_s), (32,)).copy()
        self.g = _finite(g)
        if (self.sigma_a < 0).any() or (self.sigma_s < 0).any() or abs(self.g) >= 1:
            raise ValueError('Invalid extinction or anisotropy')
        self.extinction = _array(self.sigma_a+self.sigma_s)

    def transmittance(self, distance: float) -> Any:
        return _array(np.exp(-self.extinction * _positive(distance, zero=True)))

    def phase(self, cosine: float) -> float:
        cosine = _finite(cosine)
        if not -1 <= cosine <= 1:
            raise ValueError('Phase cosine outside [-1,1]')
        return (1-self.g**2)/(4*math.pi*(1+self.g**2-2*self.g*cosine)**1.5)

    def sample_free_path(self, uniform: float, wavelength: int = 0) -> float | None:
        uniform = _finite(uniform)
        if not 0 <= uniform < 1 or type(wavelength) is not int or not 0 <= wavelength < 32:
            raise ValueError('Invalid free-path sample')
        extinction = float(self.extinction[wavelength])
        return _finite(-math.log1p(-uniform)/extinction, 'free-path distance') if extinction else None


class CertifiedSpectralPathTracer:
    """Sphere-scene spectral path tracer with environment/BSDF balance MIS.

    Samples both a uniform hemisphere environment proposal and cosine BSDF
    proposal. Contributions use power-heuristic weights p²/(p²+q²). Emissive
    spheres are reached by BSDF paths; per-pixel Welford variance is variance of
    the mean. A receipt certifies bytes/provenance, not convergence or realism.
    The NumPy surface backend handles absorption; the Torch wavefront backend
    handles triangles and bounded homogeneous multiple scattering on CPU/CUDA.
    """
    def __init__(self, scene: Mapping[str, Any] | None = None, seed: int = 0,
                 max_depth: int = 6, media: VolumetricMedia | None = None) -> None:
        _require(np, 'numpy')
        self.seed = seed; self.max_depth = _budget(max_depth, 128)
        self.scene = _json(scene or {'spheres': [], 'environment': 1.0})
        self.environment = np.broadcast_to(_array(self.scene.get('environment', 0)), (32,)).copy()
        if (self.environment < 0).any():
            raise ValueError('Negative environment radiance')
        self.spheres = []
        for sphere in self.scene.get('spheres', []):
            center = _array(sphere['center'], 1)
            emission = np.broadcast_to(_array(sphere.get('emission', 0)), (32,)).copy()
            if center.shape != (3,) or (emission < 0).any():
                raise ValueError('Invalid sphere')
            self.spheres.append((center, _positive(sphere['radius']), MicrofacetBSDF(**sphere.get('material', {})), emission))
        if len(self.spheres) > 10000:
            raise ValueError('Sphere budget exceeded')
        self.media = media if media is not None else (VolumetricMedia(**self.scene['medium']) if 'medium' in self.scene else None)
        self.triangles = []
        for triangle in self.scene.get('triangles', []):
            vertices = _array(triangle['vertices'], 2)
            if vertices.shape != (3, 3) or np.linalg.norm(np.cross(vertices[1]-vertices[0], vertices[2]-vertices[0])) < 1e-12:
                raise ValueError('Triangle must have three noncollinear vertices')
            emission = np.broadcast_to(_array(triangle.get('emission', 0)), (32,)).copy()
            if (emission < 0).any():
                raise ValueError('Negative triangle emission')
            self.triangles.append((vertices, MicrofacetBSDF(**triangle.get('material', {})), emission))
        if len(self.triangles)+len(self.spheres) > 10000:
            raise ValueError('Geometry budget exceeded')
        if self.media is not None:
            self.scene['medium'] = {'sigma_a': self.media.sigma_a.tolist(), 'sigma_s': self.media.sigma_s.tolist(), 'g': self.media.g}

    def _hit(self, ray: SpectralRay) -> Any:
        nearest, result = math.inf, None
        for center, radius, bsdf, emission in self.spheres:
            oc = ray.origin-center
            b = float(oc @ ray.direction); c = float(oc @ oc)-radius*radius
            discriminant = b*b-c
            if not all(math.isfinite(value) for value in (b, c, discriminant)):
                raise ValueError('Sphere intersection overflow; rescale scene coordinates')
            if discriminant < 0:
                continue
            root = math.sqrt(discriminant)
            t = -b-root
            if t <= 1e-6:
                t = -b+root
            if 1e-6 < t < nearest:
                point = ray.origin+t*ray.direction
                normal = _unit(point-center)
                if normal @ ray.direction > 0:
                    normal = -normal
                nearest, result = t, (t, point, normal, bsdf, emission)
        for vertices, bsdf, emission in self.triangles:
            edge1, edge2 = vertices[1]-vertices[0], vertices[2]-vertices[0]
            p = np.cross(ray.direction, edge2); determinant = float(edge1 @ p)
            if abs(determinant) <= 1e-12:
                continue
            relative = ray.origin-vertices[0]; u = float(relative @ p)/determinant
            q = np.cross(relative, edge1); v = float(ray.direction @ q)/determinant
            t = float(edge2 @ q)/determinant
            if u >= 0 and v >= 0 and u+v <= 1 and 1e-6 < t < nearest:
                normal = _unit(np.cross(edge1, edge2))
                if normal @ ray.direction > 0:
                    normal = -normal
                nearest = t; result = (t, ray.origin+t*ray.direction, normal, bsdf, emission)
        return result

    @staticmethod
    def _hemisphere(normal: Any, rng: Any, cosine: bool) -> Any:
        a, b = rng.random(2)
        z = math.sqrt(a) if cosine else a
        radial = math.sqrt(max(0, 1-z*z)); angle = 2*math.pi*b
        helper = np.array([1, 0, 0]) if abs(normal[0]) < .9 else np.array([0, 1, 0])
        tangent = _unit(np.cross(normal, helper)); bitangent = np.cross(normal, tangent)
        return _unit(radial*math.cos(angle)*tangent + radial*math.sin(angle)*bitangent + z*normal)

    @staticmethod
    def _weight(p: float, q: float) -> float:
        return p*p/(p*p+q*q) if p*p+q*q > 0 else 0.0

    def trace(self, ray: SpectralRay, rng: Any) -> Any:
        power = ray.spd.copy(); radiance = np.zeros(32); environment_weight = 1.0
        for depth in range(self.max_depth):
            hit = self._hit(ray)
            if hit is None:
                # An unbounded absorbing homogeneous medium extinguishes infinity.
                attenuation = np.ones(32) if self.media is None else (self.media.sigma_a == 0).astype(float)
                radiance += power*self.environment*environment_weight*attenuation
                break
            distance, point, normal, bsdf, emission = hit
            if self.media is not None:
                power *= self.media.transmittance(distance)
            radiance += power*emission
            outgoing = -ray.direction
            direct = self._hemisphere(normal, rng, False)
            shadow = SpectralRay(point+normal*1e-5, direct)
            if self._hit(shadow) is None:
                cosine = max(0.0, float(normal @ direct))
                p, q = 1/(2*math.pi), cosine/math.pi
                attenuation = np.ones(32) if self.media is None else (self.media.sigma_a == 0).astype(float)
                weight = self._weight(p, q) if depth+1 < self.max_depth else 1.0
                radiance += power*bsdf.evaluate(direct, outgoing, normal)*self.environment*cosine/p*weight*attenuation
            if depth+1 == self.max_depth:
                break
            incoming = self._hemisphere(normal, rng, True)
            cosine = max(float(normal @ incoming), 0)
            pdf = cosine/math.pi
            if pdf <= 0:
                break
            power *= bsdf.evaluate(incoming, outgoing, normal)*cosine/pdf
            environment_weight = self._weight(pdf, 1/(2*math.pi))
            ray = SpectralRay(point+normal*1e-5, incoming)
            if depth >= 3:
                survival = min(.95, max(.05, float(np.max(power))))
                if rng.random() >= survival:
                    break
                power /= survival
        return _array(radiance, 1)

    def render(self, width: int = 16, height: int = 16, samples: int = 16,
               camera: Mapping[str, Any] | None = None, device: str | None = None,
               ray_batch_size: int = 32768, medium_radius: float = 10, dtype: str = 'float32') -> dict[str, Any]:
        if device is not None or (self.media is not None and np.any(self.media.sigma_s)):
            return TorchSpectralIntegrator(self, device or 'cpu', dtype, medium_radius).render(width, height, samples, camera, ray_batch_size)
        _budget(width, 4096); _budget(height, 4096); _budget(samples, 1_000_000)
        if width*height*samples*self.max_depth > 10_000_000 or samples < 2:
            raise ValueError('Render budget exceeded or variance requires >=2 samples')
        camera = dict(camera or {})
        origin = _array(camera.get('origin', [0, 0, -3]), 1)
        forward = _unit(_array(camera.get('target', [0, 0, 0]), 1)-origin)
        right = _unit(np.cross(forward, _unit(camera.get('up', [0, 1, 0]))))
        up = np.cross(right, forward)
        fov = _positive(camera.get('fov', 45))
        if fov >= 179:
            raise ValueError('Camera FOV must be <179 degrees')
        scale = math.tan(math.radians(fov)/2)
        rng = np.random.default_rng(self.seed)
        image = np.zeros((height, width, 32)); m2 = np.zeros_like(image)
        for y in range(height):
            for x in range(width):
                for index in range(1, samples+1):
                    jx, jy = rng.random(2)
                    sx = (2*(x+jx)/width-1)*width/height*scale
                    sy = (1-2*(y+jy)/height)*scale
                    value = self.trace(SpectralRay(origin, forward+sx*right+sy*up), rng)
                    delta = value-image[y, x]
                    image[y, x] += delta/index
                    m2[y, x] += delta*(value-image[y, x])
        return {'image': _array(image), 'variance': _array(np.maximum(m2/(samples-1)/samples, 0)),
                'samples': samples, 'seed': self.seed, 'scene_hash': fingerprint(self.scene),
                'estimator': 'finite-depth spectral Monte Carlo; variance is not an error bound'}

    def export_openexr_with_receipt(self, image_buffer: Any, filename: str | Path,
                                    session: CalculationSession) -> dict[str, Any]:
        image_values = image_buffer['image'] if isinstance(image_buffer, Mapping) else image_buffer
        if torch is not None and isinstance(image_values, torch.Tensor):
            image_values = image_values.detach().cpu().numpy()
        image = _array(image_values, 3)
        if image.shape[2] not in (3, 32) or (image < 0).any():
            raise ValueError('EXR requires nonnegative RGB or 32 spectral channels')
        variance_values = image_buffer.get('variance') if isinstance(image_buffer, Mapping) else None
        if torch is not None and isinstance(variance_values, torch.Tensor):
            variance_values = variance_values.detach().cpu().numpy()
        variance = _array(variance_values, 3) if variance_values is not None else None
        if variance is not None and (variance.shape != image.shape or (variance < 0).any()):
            raise ValueError('Invalid Monte Carlo variance')
        h, w, c = image.shape
        labels = ['R', 'G', 'B'] if c == 3 else [f'S{i:02d}' for i in range(c)]
        channels = dict(zip(labels, np.moveaxis(image, -1, 0)))
        if variance is not None:
            channels.update({f'variance.{k}': v for k, v in zip(labels, np.moveaxis(variance, -1, 0))})
        with np.errstate(over='raise', invalid='raise'):
            planes = {k: v.astype('<f4') for k, v in sorted(channels.items())}
        content_hash = hashlib.sha256(b''.join(v.tobytes() for v in planes.values())).hexdigest()
        audit = session.record_observation('omni_openexr', {'scene_hash': fingerprint(self.scene), 'seed': self.seed},
                {'channel_hash': content_hash, 'shape': list(image.shape)}, backend='python-openexr-scanline',
                metadata={'claim': 'channel integrity only; no physical certification'}).result()
        def attribute(name: str, kind: str, data: bytes) -> bytes:
            return name.encode()+b'\0'+kind.encode()+b'\0'+struct.pack('<I', len(data))+data
        channel_list = b''.join(k.encode()+b'\0'+struct.pack('<iB3xii', 2, 0, 1, 1) for k in planes)+b'\0'
        window = struct.pack('<iiii', 0, 0, w-1, h-1)
        header = struct.pack('<II', 20000630, 2)
        header += attribute('channels', 'chlist', channel_list)
        header += attribute('compression', 'compression', b'\0')
        header += attribute('dataWindow', 'box2i', window)+attribute('displayWindow', 'box2i', window)
        header += attribute('lineOrder', 'lineOrder', b'\0')
        header += attribute('pixelAspectRatio', 'float', struct.pack('<f', 1))
        header += attribute('screenWindowCenter', 'v2f', struct.pack('<ff', 0, 0))
        header += attribute('screenWindowWidth', 'float', struct.pack('<f', 1))
        header += attribute('nablaReceiptSHA256', 'string', audit['content_id'].encode())
        header += attribute('nablaReceipt', 'string', canonical(audit).encode())+b'\0'
        row_size = 8+w*4*len(planes)
        first = len(header)+8*h
        with Path(filename).open('xb') as stream:
            stream.write(header)
            for y in range(h):
                stream.write(struct.pack('<Q', first+y*row_size))
            for y in range(h):
                stream.write(struct.pack('<ii', y, w*4*len(planes)))
                for plane in planes.values():
                    stream.write(plane[y].tobytes())
        return audit

class TorchSpectralIntegrator:
    """Wavefront 32-band path integration on Torch CPU/CUDA.

    Surface proposals use environment/BSDF power MIS. Spheres and triangles use
    vectorized analytic intersections. Homogeneous bounded volumes sample a
    majorant exponential proposal: the spectral scattering weight is
    sigma_s/q_rate * exp((q_rate-sigma_t)*distance), with an analogous survival
    weight at a boundary. Henyey--Greenstein proposals match the physical phase.
    This yields spectral multiple scattering without replacing spectra by RGB.
    """
    def __init__(self, tracer: CertifiedSpectralPathTracer, device: str = 'auto',
                 dtype: str = 'float32', medium_radius: float = 10) -> None:
        self.tracer = tracer
        self.runtime = DeviceRuntime(device, tracer.seed, dtype)
        self.medium_radius = _positive(medium_radius)
        self.centers = self.runtime.tensor([s[0].tolist() for s in tracer.spheres]) if tracer.spheres else None
        self.radii = self.runtime.tensor([s[1] for s in tracer.spheres]) if tracer.spheres else None
        self.vertices = self.runtime.tensor([t[0].tolist() for t in tracer.triangles]) if tracer.triangles else None
        materials = [(s[2], s[3]) for s in tracer.spheres]+[(t[1], t[2]) for t in tracer.triangles]
        if not materials:
            materials = [(MicrofacetBSDF(), np.zeros(32))]
        self.roughness = self.runtime.tensor([m.roughness for m, _ in materials])
        self.ior_n = self.runtime.tensor([m.n.tolist() for m, _ in materials])
        self.ior_k = self.runtime.tensor([m.k.tolist() for m, _ in materials])
        self.albedo = self.runtime.tensor([m.albedo.tolist() for m, _ in materials])
        self.metallic = self.runtime.tensor([float(m.metallic) for m, _ in materials])
        self.emission = self.runtime.tensor([e.tolist() for _, e in materials])
        self.environment = self.runtime.tensor(tracer.environment)
        if any(value is not None and bool((value.abs() > 1e12).any()) for value in (self.centers, self.radii, self.vertices)):
            raise ValueError('Rescale scene geometry to magnitude <=1e12 before tensor rendering')
        self.sigma_t = self.runtime.tensor(tracer.media.extinction) if tracer.media is not None else None
        self.sigma_s = self.runtime.tensor(tracer.media.sigma_s) if tracer.media is not None else None
        self.majorant = float(tracer.media.extinction.max()) if tracer.media is not None else 0.

    @staticmethod
    def normalize(vectors: Any) -> Any:
        return vectors/torch.linalg.vector_norm(vectors, dim=-1, keepdim=True).clamp_min(1e-30)

    def random(self, shape: Sequence[int]) -> Any:
        return torch.rand(tuple(shape), generator=self.runtime.generator, dtype=self.runtime.dtype, device=self.runtime.device)

    def intersections(self, origin: Any, direction: Any) -> tuple[Any, Any, Any]:
        """Nearest sphere/triangle hit, streamed over blocks of 32 primitives."""
        count = len(origin)
        distance = torch.full((count,), math.inf, device=origin.device, dtype=origin.dtype)
        normals = torch.zeros_like(origin)
        material = torch.zeros(count, dtype=torch.long, device=origin.device)
        if self.centers is not None:
            for start in range(0, len(self.centers), 32):
                centers = self.centers[start:start+32]; radii = self.radii[start:start+32]
                relative = origin[:, None, :]-centers[None, :, :]
                b = (relative*direction[:, None, :]).sum(-1)
                c = relative.square().sum(-1)-radii.square()
                determinant = b.square()-c
                root = determinant.clamp_min(0).sqrt()
                first, second = -b-root, -b+root
                candidate = torch.where(first > 1e-5, first, second)
                candidate = torch.where((determinant >= 0) & (candidate > 1e-5), candidate, math.inf)
                best, index = candidate.min(-1); mask = best < distance
                finite_best = torch.where(torch.isfinite(best), best, 0)
                point = origin+finite_best[:, None]*direction
                normal = self.normalize(point-centers[index])
                normal = torch.where((normal*direction).sum(-1, keepdim=True) > 0, -normal, normal)
                normals = torch.where(mask[:, None], normal, normals)
                material = torch.where(mask, index+start, material)
                distance = torch.minimum(distance, best)
        if self.vertices is not None:
            sphere_count = len(self.tracer.spheres)
            for start in range(0, len(self.vertices), 32):
                vertices = self.vertices[start:start+32]
                a, edge1, edge2 = vertices[:, 0], vertices[:, 1]-vertices[:, 0], vertices[:, 2]-vertices[:, 0]
                p = torch.linalg.cross(direction[:, None, :].expand(-1, len(vertices), -1), edge2[None, :, :].expand(count, -1, -1))
                determinant = (edge1[None, :, :]*p).sum(-1)
                invertible = determinant.abs() > 1e-10
                inverse = 1/torch.where(invertible, determinant, 1)
                relative = origin[:, None, :]-a[None, :, :]
                u = (relative*p).sum(-1)*inverse
                q = torch.linalg.cross(relative, edge1[None, :, :].expand(count, -1, -1))
                v = (direction[:, None, :]*q).sum(-1)*inverse
                t = (edge2[None, :, :]*q).sum(-1)*inverse
                valid = invertible & (u >= 0) & (v >= 0) & (u+v <= 1) & (t > 1e-5)
                candidates = torch.where(valid, t, math.inf)
                best, index = candidates.min(-1); mask = best < distance
                normal = self.normalize(torch.linalg.cross(edge1, edge2))[index]
                normal = torch.where((normal*direction).sum(-1, keepdim=True) > 0, -normal, normal)
                normals = torch.where(mask[:, None], normal, normals)
                material = torch.where(mask, index+start+sphere_count, material)
                distance = torch.minimum(distance, best)
        return distance, normals, material

    def hemisphere(self, normal: Any, cosine: bool = True) -> Any:
        random = self.random((len(normal), 2))
        z = random[:, 0].sqrt() if cosine else random[:, 0]
        radial = (1-z.square()).clamp_min(0).sqrt(); phi = 2*math.pi*random[:, 1]
        helper = torch.zeros_like(normal); helper[:, 0] = 1
        alternate = torch.zeros_like(normal); alternate[:, 1] = 1
        helper = torch.where(normal[:, :1].abs() < .9, helper, alternate)
        tangent = self.normalize(torch.linalg.cross(normal, helper))
        bitangent = torch.linalg.cross(normal, tangent)
        return self.normalize(radial[:, None]*phi.cos()[:, None]*tangent+
                              radial[:, None]*phi.sin()[:, None]*bitangent+z[:, None]*normal)

    def phase_direction(self, direction: Any) -> Any:
        g = self.tracer.media.g
        u = self.random((len(direction),))
        if abs(g) < 1e-6:
            cosine = 1-2*u
        else:
            cosine = ((1+g*g)-((1-g*g)/(1-g+2*g*u)).square())/(2*g)
        cosine = cosine.clamp(-1, 1)
        phi = 2*math.pi*self.random((len(direction),))
        helper = torch.zeros_like(direction); helper[:, 0] = 1
        alternate = torch.zeros_like(direction); alternate[:, 1] = 1
        tangent = self.normalize(torch.linalg.cross(direction, torch.where(direction[:, :1].abs() < .9, helper, alternate)))
        bitangent = torch.linalg.cross(direction, tangent)
        radial = (1-cosine.square()).clamp_min(0).sqrt()
        return self.normalize(cosine[:, None]*direction+radial[:, None]*(phi.cos()[:, None]*tangent+phi.sin()[:, None]*bitangent))

    def volume_segment(self, origin: Any, direction: Any, maximum: Any) -> tuple[Any, Any]:
        """Ray overlap with the homogeneous sphere centered at the scene origin."""
        b = (origin*direction).sum(-1)
        determinant = b.square()-origin.square().sum(-1)+self.medium_radius**2
        root = determinant.clamp_min(0).sqrt()
        entry = (-b-root).clamp_min(0)
        exit_distance = (-b+root).clamp_min(0)
        length = (torch.minimum(maximum, exit_distance)-entry).clamp_min(0)
        length = torch.where(determinant > 0, length, 0)
        return entry, length

    def bsdf(self, incoming: Any, outgoing: Any, normal: Any, material: Any) -> Any:
        ci = (incoming*normal).sum(-1).clamp_min(0)
        co = (outgoing*normal).sum(-1).clamp_min(0)
        half = self.normalize(incoming+outgoing)
        ch = (half*normal).sum(-1).clamp(0, 1)
        a2 = self.roughness[material].pow(4).clamp_min(1e-8)
        distribution = a2/(math.pi*(ch.square()*(a2-1)+1).square().clamp_min(1e-20))
        gi = 2*ci/(ci+(a2+(1-a2)*ci.square()).sqrt()).clamp_min(1e-20)
        go = 2*co/(co+(a2+(1-a2)*co.square()).sqrt()).clamp_min(1e-20)
        n, k = self.ior_n[material], self.ior_k[material]
        f0 = ((n-1).square()+k.square())/((n+1).square()+k.square())
        cosine = (incoming*half).sum(-1).clamp(0, 1)
        fresnel = f0+(1-f0)*(1-cosine[:, None]).pow(5)
        specular = (distribution*gi*go/(4*ci*co).clamp_min(1e-20))[:, None]*fresnel
        diffuse = (1-self.metallic[material, None])*(1-fresnel)*self.albedo[material]/math.pi
        return torch.where(((ci > 0) & (co > 0))[:, None], specular+diffuse, 0)

    def trace(self, origin: Any, direction: Any) -> Any:
        count = len(origin)
        power = torch.ones((count, 32), dtype=origin.dtype, device=origin.device)
        radiance = torch.zeros_like(power)
        active = torch.ones(count, dtype=torch.bool, device=origin.device)
        previous_weight = torch.ones(count, dtype=origin.dtype, device=origin.device)
        for depth in range(self.tracer.max_depth):
            if not bool(active.any()):
                break
            distance, normal, material = self.intersections(origin, direction)
            scattering = torch.zeros_like(active)
            event_point, next_phase = origin, direction
            if self.majorant > 0:
                entry, length = self.volume_segment(origin, direction, distance)
                sampled = -torch.log1p(-self.random((count,)))/self.majorant
                scattering = active & (sampled < length)
                travel = torch.where(scattering, sampled, length)
                weight = torch.exp((self.majorant-self.sigma_t[None, :])*travel[:, None])
                weight = torch.where(scattering[:, None], weight*self.sigma_s[None, :]/self.majorant, weight)
                power = power*weight
                event_point = origin+(entry+sampled)[:, None]*direction
                next_phase = self.phase_direction(direction)
            hit = active & ~scattering & torch.isfinite(distance)
            escaped = active & ~scattering & ~torch.isfinite(distance)
            radiance += torch.where(escaped[:, None], power*self.environment[None, :]*previous_weight[:, None], 0)
            radiance += torch.where(hit[:, None], power*self.emission[material], 0)
            safe_distance = torch.where(torch.isfinite(distance), distance, 0)
            point = origin+safe_distance[:, None]*direction
            outgoing = -direction
            direct = self.hemisphere(normal, False)
            shadow_origin = point+1e-4*normal
            shadow_distance, _, _ = self.intersections(shadow_origin, direct)
            visible = hit & ~torch.isfinite(shadow_distance)
            cosine = (direct*normal).sum(-1).clamp_min(0)
            env_pdf = 1/(2*math.pi); bsdf_pdf = cosine/math.pi
            weight = env_pdf**2/(env_pdf**2+bsdf_pdf.square()) if depth+1 < self.tracer.max_depth else torch.ones_like(cosine)
            attenuation = torch.ones_like(power)
            if self.majorant > 0:
                _, segment = self.volume_segment(shadow_origin, direct, shadow_distance)
                attenuation = torch.exp(-segment[:, None]*self.sigma_t[None, :])
            direct_value = power*self.bsdf(direct, outgoing, normal, material)*self.environment[None, :]*attenuation
            direct_value *= (cosine/env_pdf*weight)[:, None]
            radiance += torch.where(visible[:, None], direct_value, 0)
            incoming = self.hemisphere(normal, True)
            cosine = (incoming*normal).sum(-1).clamp_min(0)
            pdf = cosine/math.pi
            surface_power = power*self.bsdf(incoming, outgoing, normal, material)*math.pi
            power = torch.where(hit[:, None], surface_power, power)
            bsdf_weight = pdf.square()/(pdf.square()+env_pdf**2)
            previous_weight = torch.where(scattering, 1, bsdf_weight)
            origin = torch.where(scattering[:, None], event_point+next_phase*1e-5, shadow_origin)
            direction = torch.where(scattering[:, None], next_phase, incoming)
            active = scattering | (hit & (pdf > 0))
            if depth >= 3:
                survival = power.amax(-1).clamp(.05, .95)
                active &= self.random((count,)) < survival
                power = power/survival[:, None]
            _tensor_finite(power, 'spectral throughput')
        return _tensor_finite(radiance, 'spectral radiance')

    def render(self, width: int = 16, height: int = 16, samples: int = 16,
               camera: Mapping[str, Any] | None = None, ray_batch_size: int = 32768) -> dict[str, Any]:
        _budget(width, 4096); _budget(height, 4096); _budget(samples, 1000000)
        _budget(ray_batch_size, 262144)
        if samples < 2 or width*height*samples*self.tracer.max_depth > 10000000:
            raise ValueError('Render budget exceeded or variance needs >=2 samples')
        camera = dict(camera or {})
        origin = self.runtime.tensor(camera.get('origin', [0, 0, -3]))
        target = self.runtime.tensor(camera.get('target', [0, 0, 0]))
        up = self.runtime.tensor(camera.get('up', [0, 1, 0]))
        if origin.shape != (3,) or target.shape != (3,) or up.shape != (3,):
            raise ValueError('Camera vectors must be three-dimensional')
        if bool((origin.abs() > 1e12).any()) or bool((target.abs() > 1e12).any()):
            raise ValueError('Rescale camera coordinates to magnitude <=1e12')
        forward = _unit((target-origin).cpu().numpy())
        right = _unit(np.cross(forward, _unit(up.cpu().numpy())))
        up = np.cross(right, forward)
        forward, right, up = (self.runtime.tensor(v) for v in (forward, right, up))
        fov = _positive(camera.get('fov', 45))
        if fov >= 179:
            raise ValueError('FOV must be <179 degrees')
        scale = math.tan(math.radians(fov)/2)
        self.runtime.begin()
        image = torch.zeros((width*height, 32), device=origin.device, dtype=origin.dtype)
        variance = torch.zeros_like(image)
        for start in range(0, width*height, ray_batch_size):
            end = min(start+ray_batch_size, width*height)
            indices = torch.arange(start, end, device=origin.device)
            x, y = indices.remainder(width), indices.div(width, rounding_mode='floor')
            mean = torch.zeros((end-start, 32), device=origin.device, dtype=origin.dtype)
            m2 = torch.zeros_like(mean)
            for sample in range(1, samples+1):
                jitter = self.random((end-start, 2))
                sx = (2*(x+jitter[:, 0])/width-1)*width/height*scale
                sy = (1-2*(y+jitter[:, 1])/height)*scale
                direction = self.normalize(forward+sx[:, None]*right+sy[:, None]*up)
                value = self.trace(origin.expand(end-start, -1), direction)
                delta = value-mean; mean += delta/sample; m2 += delta*(value-mean)
            image[start:end] = mean
            variance[start:end] = (m2/((samples-1)*samples)).clamp_min(0)
        self.runtime.finish()
        return {'image': _tensor_finite(image.reshape(height, width, 32)),
                'variance': _tensor_finite(variance.reshape(height, width, 32)),
                'samples': samples, 'seed': self.tracer.seed, 'scene_hash': fingerprint(self.tracer.scene),
                'ray_batch_size': ray_batch_size, 'medium_radius': self.medium_radius, 'execution': self.runtime.information(),
                'estimator': 'spectral surface/volume Monte Carlo; sample variance is not an error certificate'}


# SECTION 4: physical Gaussian ellipsoids and projected alpha compositing
@dataclass
class Gaussian3D:
    """Ellipsoid covariance Sigma=R diag(scale²) R^T with SH color and opacity.

    Rotation must be proper orthogonal and scales positive. SH coefficients
    use the real l<=1 basis (one or four RGB coefficients).
    """
    position: Any
    scales: Any
    rotation: Any = None
    color: Any = None
    opacity: float = .8
    stress: Any = None
    strain_rate: Any = None

    def __post_init__(self) -> None:
        self.position = _array(self.position, 1).copy()
        self.scales = _array(self.scales, 1).copy()
        self.rotation = np.eye(3) if self.rotation is None else _array(self.rotation, 2).copy()
        self.color = np.array([[1., 1., 1.]]) if self.color is None else _array(self.color).reshape(-1, 3).copy()
        self.opacity = _finite(self.opacity)
        self.stress = np.zeros((3, 3)) if self.stress is None else _array(self.stress, 2).copy()
        self.strain_rate = np.zeros((3, 3)) if self.strain_rate is None else _array(self.strain_rate, 2).copy()
        if (self.position.shape != (3,) or self.scales.shape != (3,) or (self.scales <= 0).any()
                or self.rotation.shape != (3, 3) or not np.allclose(self.rotation.T @ self.rotation, np.eye(3), atol=1e-8)
                or not np.isclose(np.linalg.det(self.rotation), 1) or not 0 <= self.opacity <= 1
                or self.color.shape not in ((1, 3), (4, 3)) or self.stress.shape != (3, 3) or self.strain_rate.shape != (3, 3)):
            raise ValueError('Invalid physical Gaussian')
        if not np.allclose(self.stress, self.stress.T) or not np.allclose(self.strain_rate, self.strain_rate.T):
            raise ValueError('Stress and strain rate must be symmetric')

    @property
    def covariance(self) -> Any:
        return _array((self.rotation*self.scales**2) @ self.rotation.T, 2)

    def radiance(self, direction: Any) -> Any:
        direction = _unit(direction)
        basis = np.array([.2820947918, -.4886025119*direction[1], .4886025119*direction[2], -.4886025119*direction[0]])
        return np.maximum(basis[:len(self.color)] @ self.color, 0)


class ContinuumMechanicsCoupler:
    """Small-strain isotropic Hooke update with J2/von-Mises radial return.

    sigma_trial=sigma+dt[lambda tr(eps_dot)I+2mu eps_dot]. Deviatoric
    equivalent stress sqrt(3/2 s:s) is clamped to yield stress. Advection and
    F=I+dt grad(v) transport Sigma; eigendecomposition recovers R and scales.
    This local constitutive step requires externally solved velocity gradients.
    """
    def __init__(self, young_modulus: float = 1e3, poisson_ratio: float = .3,
                 yield_stress: float = 1e3) -> None:
        e = _positive(young_modulus); nu = _finite(poisson_ratio)
        if not -1 < nu < .5:
            raise ValueError('Poisson ratio outside stable isotropic range')
        self.mu = e/(2*(1+nu)); self.lam = e*nu/((1+nu)*(1-2*nu))
        self.yield_stress = _positive(yield_stress)

    def step(self, particles: Sequence[Gaussian3D], velocities: Any, gradients: Any,
             dt: float) -> list[Gaussian3D]:
        dt = _positive(dt); v, g = _array(velocities, 2), _array(gradients, 3)
        if v.shape != (len(particles), 3) or g.shape != (len(particles), 3, 3):
            raise ValueError('Particle velocity/gradient shape mismatch')
        updated = []
        for particle, velocity, gradient in zip(particles, v, g):
            strain = .5*(gradient+gradient.T)
            trial = particle.stress+dt*(self.lam*np.trace(strain)*np.eye(3)+2*self.mu*strain)
            mean = np.trace(trial)/3; deviator = trial-mean*np.eye(3)
            equivalent = math.sqrt(max(0, float(1.5*np.sum(deviator**2))))
            stress = mean*np.eye(3)+deviator*min(1.0, self.yield_stress/equivalent if equivalent else 1.0)
            deformation = np.eye(3)+dt*gradient
            if np.linalg.det(deformation) <= 0:
                raise ValueError('Inverted deformation; reduce timestep')
            covariance = deformation @ particle.covariance @ deformation.T
            eigenvalues, rotation = np.linalg.eigh(covariance)
            if min(eigenvalues) <= 0:
                raise ValueError('Degenerate covariance')
            if np.linalg.det(rotation) < 0:
                rotation[:, 0] *= -1
            updated.append(Gaussian3D(particle.position+dt*velocity, np.sqrt(eigenvalues), rotation,
                                      particle.color, particle.opacity, stress, strain))
        return updated


    def step_tensors(self, positions: Any, covariances: Any, stresses: Any, velocities: Any,
                     gradients: Any, dt: float) -> dict[str, Any]:
        """Batched differentiable Hooke/J2 update without leaving the input device.

        F=I+dt grad(v) transports each ellipsoid covariance. A radial return caps
        equivalent deviatoric stress at the material yield stress. Positions,
        stresses and covariances remain Torch tensors suitable for rasterization.
        """
        dt = _positive(dt)
        for value in (positions, covariances, stresses, velocities, gradients):
            _tensor_finite(value)
        n = len(positions)
        if positions.shape != (n, 3) or velocities.shape != (n, 3) or any(v.shape != (n, 3, 3) for v in (covariances, stresses, gradients)):
            raise ValueError('Batched mechanics tensor shapes mismatch')
        if any(v.device != positions.device or v.dtype != positions.dtype for v in (covariances, stresses, velocities, gradients)):
            raise ValueError('Mechanics tensors must share device and dtype')
        if not torch.allclose(covariances, covariances.transpose(-1, -2)) or bool((torch.linalg.eigvalsh(covariances) <= 0).any()):
            raise ValueError('Covariances must be symmetric positive definite')
        if not torch.allclose(stresses, stresses.transpose(-1, -2)):
            raise ValueError('Cauchy stress must be symmetric')
        identity = torch.eye(3, dtype=positions.dtype, device=positions.device)
        strain_rate = .5*(gradients+gradients.transpose(-1, -2))
        trace = strain_rate.diagonal(dim1=-2, dim2=-1).sum(-1)
        trial = stresses+dt*(self.lam*trace[:, None, None]*identity+2*self.mu*strain_rate)
        hydrostatic = trial.diagonal(dim1=-2, dim2=-1).sum(-1)/3
        deviator = trial-hydrostatic[:, None, None]*identity
        equivalent = (1.5*deviator.square().sum((-1, -2))).sqrt()
        ratio = (self.yield_stress/equivalent.clamp_min(1e-30)).clamp(max=1)
        updated_stress = hydrostatic[:, None, None]*identity+ratio[:, None, None]*deviator
        deformation = identity+dt*gradients
        if bool((torch.linalg.det(deformation) <= 0).any()):
            raise ValueError('Inverted deformation; reduce timestep')
        covariance = deformation@covariances@deformation.transpose(-1, -2)
        eigenvalues, rotations = torch.linalg.eigh(covariance)
        if bool((eigenvalues <= 0).any()):
            raise ValueError('Degenerate advected ellipsoid')
        signs = torch.ones((n, 3), device=positions.device, dtype=positions.dtype)
        signs[:, 0] = torch.where(torch.linalg.det(rotations) < 0, -1, 1)
        rotations = rotations*signs[:, None, :]
        result = {'positions': positions+dt*velocities, 'covariances': covariance,
                  'stresses': updated_stress, 'strain_rates': strain_rate,
                  'rotations': rotations, 'scales': eigenvalues.sqrt(),
                  'plastic_strain_increment': (equivalent-self.yield_stress).clamp_min(0)/(3*self.mu)}
        return {key: _tensor_finite(value, key) for key, value in result.items()}


class DifferentiableRasterizer:
    """Perspective Gaussian projection J Sigma J^T and depth alpha blending.

    Pixel alpha=o exp(-0.5 d^T C^-1 d); front-to-back weights are T alpha.
    Torch preserves gradients through positions/covariances/colors/opacities;
    depth order is piecewise constant and changes discontinuously at crossings.
    NumPy implements the same projection for portable inference.
    """
    def rasterize_tensors(self, positions: Any, covariances: Any, colors: Any, opacities: Any,
                          width: int, height: int, focal: float = 32, near: float = 1e-4) -> Any:
        _require(torch, 'torch')
        _budget(width, 4096); _budget(height, 4096); focal = _positive(focal); near = _positive(near)
        n = positions.shape[0]
        if positions.shape != (n, 3) or covariances.shape != (n, 3, 3) or colors.shape != (n, 3) or opacities.shape != (n,):
            raise ValueError('Tensor rasterization shape mismatch')
        if any(not torch.isfinite(v).all() for v in (positions, covariances, colors, opacities)):
            raise ValueError('Nonfinite raster input')
        if (colors < 0).any() or (opacities < 0).any() or (opacities > 1).any():
            raise ValueError('Invalid radiance/opacity')
        if not torch.allclose(covariances, covariances.transpose(-1, -2)) or (torch.linalg.eigvalsh(covariances) <= 0).any():
            raise ValueError('Covariance must be symmetric positive definite')
        yy, xx = torch.meshgrid(torch.arange(height, device=positions.device, dtype=positions.dtype),
                                torch.arange(width, device=positions.device, dtype=positions.dtype), indexing='ij')
        image = torch.zeros((height, width, 3), dtype=positions.dtype, device=positions.device)
        transmission = torch.ones((height, width), dtype=positions.dtype, device=positions.device)
        for index in torch.argsort(positions[:, 2]):
            x, y, z = positions[index].unbind()
            if z <= near:
                continue
            zero = x*0
            jac = torch.stack([torch.stack([focal/z, zero, -focal*x/z**2]), torch.stack([zero, focal/z, -focal*y/z**2])])
            covariance = jac @ covariances[index] @ jac.T + torch.eye(2, device=x.device, dtype=x.dtype)*.25
            delta = torch.stack([xx-(focal*x/z+width/2), yy-(focal*y/z+height/2)], -1)
            power = torch.einsum('...i,ij,...j->...', delta, torch.linalg.inv(covariance), delta)
            alpha = opacities[index]*torch.exp(-.5*power)
            image = image+(transmission*alpha)[..., None]*colors[index]
            transmission = transmission*(1-alpha)
        if not torch.isfinite(image).all():
            raise ValueError('Nonfinite raster result')
        return image

    def render(self, particles: Sequence[Gaussian3D], width: int = 64, height: int = 64,
               focal: float = 32, camera_position: Any = (0, 0, 0)) -> Any:
        _budget(width, 4096); _budget(height, 4096); focal = _positive(focal)
        camera = _array(camera_position, 1)
        if camera.shape != (3,):
            raise ValueError('Camera must be a three-vector')
        yy, xx = np.mgrid[:height, :width]
        image = np.zeros((height, width, 3)); transmission = np.ones((height, width))
        for particle in sorted(particles, key=lambda p: p.position[2]-camera[2]):
            x, y, z = particle.position-camera
            if z <= 1e-4:
                continue
            jac = np.array([[focal/z, 0, -focal*x/z**2], [0, focal/z, -focal*y/z**2]])
            covariance = jac @ particle.covariance @ jac.T+np.eye(2)*.25
            delta = np.stack([xx-(focal*x/z+width/2), yy-(focal*y/z+height/2)], -1)
            exponent = np.einsum('...i,ij,...j->...', delta, np.linalg.inv(covariance), delta)
            alpha = particle.opacity*np.exp(-.5*exponent)
            image += (transmission*alpha)[..., None]*particle.radiance(camera-particle.position)
            transmission *= 1-alpha
        return _array(image, 3)

# SECTION 5: bounded Arrow/Zarr ingestion and incremental Merkle accumulation
class TensorStreamIngestor:
    """Bounded tensor/Arrow/Zarr chunks, capped at 64 MiB of decoded data.

    Contiguous buffers and non-null primitive Arrow arrays yield zero-copy
    memoryviews. Nullable, nested and variable-width Arrow arrays are refused;
    Zarr decompression necessarily allocates, and upstream storage chunk sizes
    must also obey the budget to guarantee bounded decoded working memory.
    """
    def __init__(self, chunk_bytes: int = 64*1024*1024) -> None:
        self.chunk_bytes = _budget(chunk_bytes, 64*1024*1024, 'chunk_bytes')

    def iter_chunks(self, source: Any) -> Iterator[memoryview]:
        if isinstance(source, (str, Path)):
            _require(zarr, 'zarr')
            yield from self.iter_chunks(zarr.open(str(source), mode='r'))
            return
        if pyarrow is not None and isinstance(source, (pyarrow.Table, pyarrow.RecordBatch)):
            for name in source.schema.names:
                yield from self.iter_chunks(source.column(name))
            return
        if pyarrow is not None and isinstance(source, pyarrow.ChunkedArray):
            for chunk in source.chunks:
                yield from self.iter_chunks(chunk)
            return
        if pyarrow is not None and isinstance(source, pyarrow.Array):
            if source.null_count:
                raise ValueError('Null Arrow values require an explicit validity-mask contract')
            try:
                array = source.to_numpy(zero_copy_only=True)
            except (ValueError, TypeError, pyarrow.ArrowException) as exc:
                raise ValueError('Only zero-copy primitive Arrow tensors supported') from exc
            yield from self.iter_chunks(array)
            return
        if zarr is not None and isinstance(source, zarr.Group):
            for _, array in sorted(source.arrays(), key=lambda pair: pair[0]):
                yield from self.iter_chunks(array)
            for _, group in sorted(source.groups(), key=lambda pair: pair[0]):
                yield from self.iter_chunks(group)
            return
        if zarr is not None and isinstance(source, zarr.Array):
            if not source.shape or any(v == 0 for v in source.shape) or source.dtype.hasobject:
                raise ValueError('Zarr requires nonempty numeric arrays')
            chunk_shape = source.chunks
            # Zarr v3 sharding may decode the whole shard, not just a logical chunk.
            physical = getattr(source, 'shards', None) or chunk_shape
            if math.prod(physical)*source.dtype.itemsize > self.chunk_bytes:
                raise ValueError('Decoded Zarr storage chunk exceeds memory budget')
            for starts in itertools.product(*(range(0, size, step) for size, step in zip(source.shape, chunk_shape))):
                slices = tuple(slice(start, min(start+step, size)) for start, step, size in zip(starts, chunk_shape, source.shape))
                yield from self.iter_chunks(source[slices])
            return
        if np is not None and isinstance(source, np.ndarray) and (source.dtype.hasobject or not source.flags.c_contiguous):
            raise ValueError('A contiguous non-object tensor is required for zero-copy access')
        try:
            view = memoryview(source).cast('B')
        except (TypeError, ValueError) as exc:
            raise ValueError('A contiguous buffer, primitive Arrow array or Zarr dataset is required') from exc
        for start in range(0, len(view), self.chunk_bytes):
            yield view[start:start+self.chunk_bytes]


    def iter_device_chunks(self, source: Any, device: str = 'auto', dtype: str = 'float32',
                           pin_memory: bool = True) -> Iterator[Any]:
        """Transfer bounded decoded chunks to Torch, with explicit buffer dtype.

        Writable host buffers share storage with CPU tensors. Read-only Arrow
        buffers are copied before exposing a mutable tensor. CUDA transfers may
        use pinned staging and remain ordered on the current CUDA stream.
        """
        runtime = DeviceRuntime(device, dtype=dtype)
        numpy_dtype = _require(np, 'numpy').dtype(dtype)
        if isinstance(source, np.ndarray) and source.dtype != numpy_dtype:
            raise ValueError('Declared streaming dtype differs from source dtype')
        if pyarrow is not None and isinstance(source, (pyarrow.Array, pyarrow.ChunkedArray)) and source.type != pyarrow.from_numpy_dtype(numpy_dtype):
            raise ValueError('Declared streaming dtype differs from Arrow scalar type')
        if self.chunk_bytes % numpy_dtype.itemsize:
            raise ValueError('Tensor chunk size must align to the declared scalar dtype')
        for chunk in self.iter_chunks(source):
            if len(chunk) % numpy_dtype.itemsize:
                raise ValueError('Source bytes are not aligned to the declared dtype')
            array = np.frombuffer(chunk, dtype=numpy_dtype)
            if not array.flags.writeable:
                array = array.copy()
            tensor = torch.from_numpy(array)
            _tensor_finite(tensor, 'streamed tensor')
            if runtime.device.type == 'cuda':
                if pin_memory:
                    tensor = tensor.pin_memory()
                tensor = tensor.to(runtime.device, dtype=runtime.dtype, non_blocking=pin_memory)
            else:
                tensor = tensor.to(dtype=runtime.dtype)
            yield tensor


class StreamingMerkleHasher:
    """Domain-separated SHA-256 Merkle forest using O(log leaves) memory.

    Leaves H(0x00||chunk), branches H(0x01||left||right); final root also binds
    byte and leaf counts. Chunk boundaries are part of the integrity contract.
    Finalization is O(log leaves) and nondestructive; reading/hashing data is
    O(total bytes), with no hardware-independent throughput promise.
    """
    def __init__(self) -> None:
        self.frontier: list[bytes | None] = []
        self.leaves = 0; self.bytes_read = 0

    def update(self, chunk: Any) -> StreamingMerkleHasher:
        view = memoryview(chunk).cast('B')
        digest = hashlib.sha256(b'\x00')
        digest.update(view); node = digest.digest()
        level = 0
        while level < len(self.frontier) and self.frontier[level] is not None:
            node = hashlib.sha256(b'\x01'+self.frontier[level]+node).digest()
            self.frontier[level] = None; level += 1
        if level == len(self.frontier):
            self.frontier.append(node)
        else:
            self.frontier[level] = node
        self.leaves += 1; self.bytes_read += len(view)
        return self

    def finalize_root_hash(self) -> str:
        node = None
        for subtree in self.frontier:
            if subtree is not None:
                node = subtree if node is None else hashlib.sha256(b'\x01'+subtree+node).digest()
        return hashlib.sha256(b'\x02'+struct.pack('<QQ', self.leaves, self.bytes_read)+(node or b'')).hexdigest()

# SECTION 6: bounded formal PUCT with closed catalog actions
@dataclass
class ProofStateNode:
    """PUCT state: current hypothesis, checked premises, pending goals and N,Q.

    A node is solved only when a verifier closes its goal; rewards never turn an
    unchecked tactic into a theorem. Parent links are excluded from exports.
    """
    hypothesis: str
    proven_premises: list[dict[str, Any]] = field(default_factory=list)
    pending_goals: list[Any] = field(default_factory=list)
    prior: float = 1.0
    visits: int = 0
    value_sum: float = 0.0
    children: list[ProofStateNode] = field(default_factory=list)
    evidence: dict[str, Any] | None = None
    solved: bool = False

    @property
    def value(self) -> float:
        return self.value_sum/self.visits if self.visits else 0.0

    def to_data(self) -> dict[str, Any]:
        return {'hypothesis': self.hypothesis, 'premises': self.proven_premises,
                'pending_goals': self.pending_goals, 'prior': self.prior, 'visits': self.visits,
                'value': self.value, 'solved': self.solved, 'evidence': self.evidence,
                'children': [child.to_data() for child in self.children]}


class FormalMCTSSearcher:
    """PUCT Q+cP sqrt(N)/(1+n), expansion, checked rollout and backpropagation.

    Every supplied tactic is an existing closed CalculationSession operation.
    Macro recursion is excluded. Rational identity goals are closed by exact
    normalization with matching domains; structured SMT goals use AIVerifier's
    killable solver. Lean source runs in a separately bounded async subprocess.
    Search budgets limit exploration and never imply a completeness guarantee.
    """
    def __init__(self, session: CalculationSession | None = None, exploration: float = 1.4) -> None:
        from nablamath.calc.session import AREAS
        self.session = session or CalculationSession()
        self.actions = frozenset(AREAS)-{'omni_superintelligence'}
        self.exploration = _positive(exploration)

    async def verify_external(self, source: str, backend: str = 'lean', timeout: float = 5) -> dict[str, Any]:
        timeout = _positive(timeout)
        if timeout > 30 or len(source.encode()) > 65536:
            raise ValueError('External proof budget exceeded')
        if backend not in {'lean', 'z3'}:
            raise ValueError('Only Lean and Z3 subprocesses supported')
        if backend == 'lean' and re.search(r'\b(sorry|admit|axiom|unsafe|run_cmd|run_tac|initialize)\b|#|\bimport\b', source):
            raise ValueError('Only self-contained Lean theorem declarations without escape hatches are accepted')
        # Proof assistants are not OS sandboxes; only trusted local source belongs here.
        lean = shutil.which('lean')
        if lean is None:
            project = Path(__file__).resolve().parents[3]
            root = project.parent
            pin = project/'lean'/'lean-toolchain'
            version = pin.read_text(encoding='utf-8').strip().split(':v')[-1] if pin.is_file() else ''
            candidate = root/'.tools'/'lean'/f'lean-{version}-linux'/'bin'/'lean'
            if candidate.is_file():
                lean = str(candidate)
        command = [lean or 'lean', '--stdin'] if backend == 'lean' else ['z3', '-in', '-smt2']
        try:
            process = await asyncio.create_subprocess_exec(*command, stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        except FileNotFoundError:
            return {'status': 'unavailable', 'backend': backend, 'verified': False}
        try:
            output, _ = await asyncio.wait_for(process.communicate(source.encode()), timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
            if process.returncode is None:
                process.kill()
            await process.wait()
            if isinstance(exc, asyncio.CancelledError):
                raise
            return {'status': 'timeout', 'backend': backend, 'verified': False}
        text = output[:65536].decode(errors='replace')
        # SMT-LIB subprocess output is diagnostic only: UNSAT can be vacuous and
        # scripts may contain multiple queries. Structured claims use AIVerifier.
        verified = backend == 'lean' and process.returncode == 0 and bool(re.search(r'\btheorem\b', source))
        return {'status': 'checked' if verified else 'unverified', 'backend': backend,
                'verified': verified, 'output': text, 'exit_code': process.returncode}

    def search(self, left: str, right: str, tactics: Sequence[Mapping[str, Any]] | None = None,
               iterations: int = 64, depth: int = 8) -> dict[str, Any]:
        _budget(iterations, 10000); _budget(depth, 32)
        root = ProofStateNode(f'{left} = {right}', pending_goals=[{'left': left, 'right': right}])
        tactics = list(tactics or [{'operation': 'rational_compare', 'arguments': {'left': left, 'right': right}}])
        if not 1 <= len(tactics) <= 128:
            raise ValueError('Tactic budget exceeded')
        for tactic in tactics:
            if set(tactic) != {'operation', 'arguments'} or tactic['operation'] not in self.actions:
                raise ValueError('Tactic must belong to the current Nabla catalog')
        for _ in range(iterations):
            node, path = root, [root]
            while node.children and len(path) <= depth:
                node = max(node.children, key=lambda child: child.value + self.exploration*child.prior*math.sqrt(max(1, node.visits))/(1+child.visits))
                path.append(node)
            if not node.children and not node.solved and len(path) <= depth:
                node.children = [ProofStateNode(node.hypothesis, list(node.proven_premises), list(node.pending_goals), 1/len(tactics)) for _ in tactics]
                for child, tactic in zip(node.children, tactics):
                    try:
                        evidence = self.session.execute(tactic['operation'], **tactic['arguments']).to_data()
                        child.evidence = evidence
                        # Only an identity comparison for this exact goal can close it.
                        args = evidence['request']['arguments']; result = evidence['result']
                        child.solved = (tactic['operation'] == 'rational_compare' and args == {'left': left, 'right': right}
                                        and result['equal_on_common_domain'] and result['domain_equivalence_established'])
                        if child.solved:
                            child.pending_goals = []; child.proven_premises.append(evidence)
                    except (ValueError, ArithmeticError, TypeError, RuntimeError) as exc:
                        child.evidence = {'rejected': str(exc)}
                node = max(node.children, key=lambda child: child.solved)
                path.append(node)
            reward = 1.0 if node.solved else -1.0
            for ancestor in path:
                ancestor.visits += 1; ancestor.value_sum += reward
                if node.solved:
                    ancestor.solved = True
            if root.solved:
                break
        return {'tree': root.to_data(), 'solved': root.solved, 'catalog_action_count': len(self.actions),
                'scope': 'bounded exact rational goal search; no Lean theorem generated', 'formal_proof': False}

    def search_horn(self, facts: Sequence[Any], rules: Sequence[Any], goals: Sequence[Any],
                    iterations: int = 128, depth: int = 32, seed: int = 0) -> dict[str, Any]:
        """PUCT forward-proof search with checked Horn expansions and rollouts.

        Search states are finite sets of ground propositions. Every edge is a
        unification witness of a declared Horn implication; Monte Carlo rollouts
        add only such witnessed consequences. Truth is conditional on the axioms.
        """
        _budget(iterations, 10000); _budget(depth, 128)
        chainer = ForwardAxiomChainer(); rng = random.Random(seed)
        def freeze(value: Any) -> Any:
            return tuple(freeze(v) for v in value) if isinstance(value, (list, tuple)) else value
        initial = frozenset(freeze(v) for v in facts)
        targets = frozenset(freeze(v) for v in goals)
        if not targets or len(initial) > 1000 or len(rules) > 128:
            raise ValueError('Horn search requires goals and bounded axioms/rules')
        # An empty rule list is legitimate when the goal is already an axiom.
        chainer.derive(list(initial), rules, max_rounds=1)
        root = ProofStateNode('Horn consequences of declared axioms',
                              [{'axiom': _json(v)} for v in sorted(initial, key=repr)],
                              [_json(v) for v in sorted(targets-initial, key=repr)])
        states = {id(root): initial}; solved_proof = []
        for _ in range(iterations):
            node, path = root, [root]
            while node.children and len(path) <= depth:
                node = max(node.children, key=lambda child: child.value+self.exploration*child.prior*math.sqrt(max(1, node.visits))/(1+child.visits))
                path.append(node)
            state = states[id(node)]
            if targets <= state:
                reward = 1.; node.solved = True
                solved_proof = list(node.proven_premises)
            else:
                proposals = chainer.derive(list(state), rules, max_rounds=1, max_facts=10000)
                if not node.children and len(path) <= depth:
                    normalizer = sum(2 if proposal['lemma'] in targets else 1 for proposal in proposals) or 1
                    for proposal in proposals[:256]:
                        new_state = state | {proposal['lemma']}
                        evidence = receipt('omni_horn_inference', {'rule': _json(rules[proposal['rule_index']]),
                            'known_facts': _json(sorted(state, key=repr))}, _json(proposal),
                            metadata={'scope': 'first-order consequence of caller-declared Horn axioms'})
                        child = ProofStateNode(str(proposal['lemma']), node.proven_premises+[proposal],
                            [_json(v) for v in sorted(targets-new_state, key=repr)],
                            (2 if proposal['lemma'] in targets else 1)/normalizer, evidence=evidence)
                        node.children.append(child); states[id(child)] = frozenset(new_state)
                rollout = state; proof = list(node.proven_premises)
                for _ in range(depth):
                    if targets <= rollout:
                        break
                    choices = chainer.derive(list(rollout), rules, max_rounds=1, max_facts=10000)
                    if not choices:
                        break
                    relevant = [p for p in choices if p['lemma'] in targets]
                    chosen = rng.choice(relevant or choices)
                    rollout = rollout | {chosen['lemma']}; proof.append(chosen)
                success = targets <= rollout
                reward = 1. if success else len(targets & rollout)/len(targets)-1
                if success:
                    node.solved = True; solved_proof = proof
            for ancestor in path:
                ancestor.visits += 1; ancestor.value_sum += reward
                if node.solved:
                    ancestor.solved = True
            if root.solved:
                break
        return {'solved': root.solved, 'tree': root.to_data(), 'proof': _json(solved_proof),
                'axioms': _json(sorted(initial, key=repr)), 'goals': _json(sorted(targets, key=repr)),
                'scope': 'bounded conditional Horn deduction with exact unification witnesses', 'formal_proof': False}


# SECTION 7: forward Horn inference and inverse problem synthesis
class ForwardAxiomChainer:
    """First-order Horn forward chaining with occurs-check unification.

    Terms are strings, variables prefixed '?' or nested tuples. A rule is
    (premises, conclusion); only substitutions justified by known ground facts
    are emitted. Truth is relative to the caller's axiom set, not absolute.
    """
    @staticmethod
    def unify(left: Any, right: Any, substitution: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
        subs = dict(substitution or {})
        def walk(term: Any) -> Any:
            seen = set()
            while isinstance(term, str) and term.startswith('?') and term in subs:
                if term in seen:
                    raise ValueError('Cyclic substitution')
                seen.add(term); term = subs[term]
            return term
        def occurs(variable: str, term: Any) -> bool:
            term = walk(term)
            return variable == term or (isinstance(term, (tuple, list)) and any(occurs(variable, child) for child in term))
        stack = [(left, right)]
        while stack:
            a, b = (walk(v) for v in stack.pop())
            if a == b:
                continue
            if isinstance(b, str) and b.startswith('?') and not (isinstance(a, str) and a.startswith('?')):
                a, b = b, a
            if isinstance(a, str) and a.startswith('?'):
                if occurs(a, b):
                    return None
                subs[a] = b
            elif isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)) and len(a) == len(b):
                stack.extend(zip(a, b))
            else:
                return None
        def resolve(term: Any) -> Any:
            term = walk(term)
            return tuple(resolve(v) for v in term) if isinstance(term, (tuple, list)) else term
        return {key: resolve(value) for key, value in subs.items()}

    def derive(self, facts: Sequence[Any], rules: Sequence[Any], max_rounds: int = 16,
               max_facts: int = 10000) -> list[dict[str, Any]]:
        _budget(max_rounds, 1000); _budget(max_facts, 100000)
        def freeze(term: Any) -> Any:
            return tuple(freeze(v) for v in term) if isinstance(term, (tuple, list)) else term
        def ground(term: Any) -> bool:
            return all(ground(v) for v in term) if isinstance(term, tuple) else not (isinstance(term, str) and term.startswith('?'))
        known = set(freeze(fact) for fact in facts)
        if not all(ground(fact) for fact in known) or len(known) > max_facts:
            raise ValueError('Ground facts within budget required')
        output = []
        for _ in range(max_rounds):
            additions = []
            for rule_index, (premises, conclusion) in enumerate(rules):
                candidates: list[tuple[dict[str, Any], list[Any]]] = [({}, [])]
                for premise in premises:
                    next_candidates = []
                    for subs, evidence in candidates:
                        for fact in sorted(known, key=repr):
                            unifier = self.unify(freeze(premise), fact, subs)
                            if unifier is not None:
                                next_candidates.append((unifier, evidence+[fact]))
                                if len(next_candidates) > max_facts:
                                    raise ValueError('Unification expansion budget exceeded')
                    candidates = next_candidates
                for subs, evidence in candidates:
                    def apply(term: Any) -> Any:
                        if isinstance(term, (tuple, list)):
                            return tuple(apply(v) for v in term)
                        return subs.get(term, term)
                    lemma = apply(conclusion)
                    if not ground(lemma):
                        raise ValueError('Rule conclusion contains an unbound variable')
                    if lemma not in known and lemma not in [item['lemma'] for item in additions]:
                        additions.append({'lemma': lemma, 'rule_index': rule_index, 'premises': evidence, 'substitution': subs})
                        if len(known)+len(additions) > max_facts:
                            raise ValueError('Derived fact budget exceeded')
            if not additions:
                break
            known.update(item['lemma'] for item in additions); output.extend(additions)
        return output


class InverseProblemSynthesizer:
    """Seeded inverse tasks whose answers are computed by exact Nabla recipes.

    Integrals start from random antiderivatives; eigenvalue tasks use triangular
    matrices; factorization starts from integer roots. Reversible bit circuits
    use exact X/CNOT gates, a rational subset of quantum permutation circuits.
    Each record contains calculation evidence and binds prompt, trace and answer.
    """
    def __init__(self, seed: int = 0, session: CalculationSession | None = None) -> None:
        self.rng = random.Random(seed); self.seed = seed
        self.session = session or CalculationSession()

    def generate(self, kind: str = 'polynomial', difficulty: int = 3) -> dict[str, Any]:
        _budget(difficulty, 8, 'difficulty')
        if kind == 'polynomial':
            coefficients = [self.rng.randint(-9, 9) for _ in range(difficulty+1)]
            coefficients[-1] = self.rng.choice([-1, 1])*self.rng.randint(1, 9)
            derivative = '+'.join(f'({i*coefficients[i]})*x**{i-1}' for i in range(1, len(coefficients)))
            prompt = f'Calcule a integral de 0 a 1 de {derivative}.'
            calculation = self.session.execute('integrate', source=derivative, start=0, end=1).to_data()
            solution = str(sum(coefficients[1:]))
            if calculation['result']['value'] != solution:
                raise ArithmeticError('Inverse polynomial check failed')
        elif kind == 'matrix':
            n = difficulty
            matrix = [[self.rng.randint(-5, 5) if j >= i else 0 for j in range(n)] for i in range(n)]
            prompt = f'Determine os autovalores com multiplicidade da matriz triangular {matrix}.'
            calculation = self.session.execute('matrix_properties', matrix=matrix).to_data()
            solution = sorted(matrix[i][i] for i in range(n))
            # Characteristic polynomial is independently reconstructed from roots.
            expected = [1]
            for root in solution:
                expanded = [0]*(len(expected)+1)
                for i, coefficient in enumerate(expected):
                    expanded[i] -= root*coefficient; expanded[i+1] += coefficient
                expected = expanded
            if [Fraction(v) for v in calculation['result']['characteristic_polynomial']] != expected:
                raise ArithmeticError('Eigenvalue certificate mismatch')
        elif kind == 'factorization':
            roots = [self.rng.randint(-5, 5) for _ in range(difficulty)]
            coefficients = [1]
            for root in roots:
                expanded = [0]*(len(coefficients)+1)
                for i, value in enumerate(coefficients):
                    expanded[i] -= root*value; expanded[i+1] += value
                coefficients = expanded
            prompt = f'Fatore o polinômio de coeficientes ascendentes {coefficients}.'
            calculation = self.session.execute('factor', coefficients=coefficients).to_data()
            solution = {'integer_roots': sorted(roots)}
        elif kind == 'quantum':
            bits = [self.rng.randrange(2) for _ in range(max(2, difficulty))]
            initial = bits.copy(); gates = []
            for _ in range(difficulty):
                control, target = self.rng.sample(range(len(bits)), 2)
                bits[target] ^= bits[control]; gates.append([control, target])
            prompt = f'Inverta as portas CNOT {gates} sobre o estado computacional {bits}.'
            expression = '+'.join(str(bit*2**i) for i, bit in enumerate(initial))
            calculation = self.session.execute('evaluate', source=expression).to_data()
            replay = bits.copy()
            for control, target in reversed(gates):
                replay[target] ^= replay[control]
            if replay != initial:
                raise ArithmeticError('Reversible circuit failed')
            solution = {'basis_state': initial, 'forward_gates': gates, 'output': bits}
        else:
            raise ValueError('Supported synthesis kinds: polynomial, matrix, factorization, quantum')
        trace = [{'operation': calculation['request']['operation'], 'arguments': calculation['request']['arguments'],
                  'result': calculation['result'], 'receipt': calculation}]
        result = {'prompt': prompt, 'solution': solution, 'thinking_trajectory': trace, 'kind': kind, 'seed': self.seed}
        result['receipt'] = receipt('omni_synthetic_problem', {'prompt': prompt, 'kind': kind, 'seed': self.seed},
                                    {'solution': solution, 'thinking_trajectory': trace},
                                    metadata={'verification': 'bounded exact generation', 'formal_proof': False},
                                    parents=[calculation['content_id']])
        return result

    def stream(self, count: int, kind: str = 'polynomial', difficulty: int = 3) -> Iterator[dict[str, Any]]:
        _budget(count, 100_000_000, 'count')
        for _ in range(count):
            yield self.generate(kind, difficulty)


class ChainOfThoughtBuilder:
    """Render concise synthetic solution steps backed by replayable calculations.

    These are generated worked solutions, not private model deliberations.
    Each line is admitted only after replay of the accompanying Nabla receipt.
    """
    def build(self, steps: Sequence[Mapping[str, Any]], solution: Any) -> str:
        lines = []
        if not steps:
            raise ValueError('At least one verified step required')
        for index, step in enumerate(steps, 1):
            audit = step.get('receipt')
            if not isinstance(audit, dict) or 'request' not in audit or not verify_receipt(audit):
                raise ValueError('Every step requires a replayable Nabla calculation')
            if step.get('result') != audit['result'] or step.get('arguments') != audit['request']['arguments'] or step.get('operation') != audit['request']['operation']:
                raise ValueError('Step diverges from its calculation evidence')
            lines.append(f'Passo {index}: {audit["request"]["operation"]}: {canonical(audit["result"])}')
        return '<thought>\n'+'\n'.join(lines)+'\n</thought>\n<solution>\n'+canonical(_json(solution))+'\n</solution>'

# SECTION 8: process reward verification
class ProcessRewardVerifier:
    """Discrete process rewards for atomic equalities and structured implications.

    +1 requires exact rational normalization or PROVEN SMT status; 0 marks an
    identical expression; -1 refuses invalid/unsupported claims. Unavailability
    is recorded explicitly and never represented as a discovered counterexample.
    Free prose cannot be formally validated and is rejected rather than guessed.
    """
    def __init__(self, session: CalculationSession | None = None) -> None:
        self.session = session or CalculationSession()

    @staticmethod
    def split_steps(text: str) -> list[str]:
        if len(text) > 65536:
            raise ValueError('Reasoning exceeds input budget')
        text = re.sub(r'</?(?:thought|solution)>', '', text)
        return [re.sub(r'^(?:Passo|Step)\s*\d+\s*:\s*', '', line.strip(), flags=re.I)
                for line in re.split(r'[\n;]+', text) if line.strip()]

    def verify(self, reasoning: str | Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        steps: Sequence[Any] = self.split_steps(reasoning) if isinstance(reasoning, str) else reasoning
        if not 1 <= len(steps) <= 256:
            raise ValueError('Between 1 and 256 atomic steps required')
        output = []
        for step in steps:
            reward, status, evidence = -1, 'unsupported', None
            try:
                if isinstance(step, str):
                    if step.count('=') != 1 or any(token in step for token in ('<=', '>=', '!=', '=>')):
                        raise ValueError('Text steps must be explicit atomic equalities')
                    left, right = (part.strip() for part in step.split('='))
                    claim: Mapping[str, Any] = {'left': left, 'right': right}
                else:
                    claim = step
                if set(claim) == {'left', 'right'}:
                    evidence = self.session.execute('rational_compare', left=claim['left'], right=claim['right']).to_data()
                    result = evidence['result']
                    valid = result['equal_on_common_domain'] and result['domain_equivalence_established']
                    status = 'valid' if valid else 'invalid'
                    reward = (0 if claim['left'].strip() == claim['right'].strip() else 1) if valid else -1
                elif set(claim) == {'statement'}:
                    from nablamath.formal.statement import FormalStatement
                    statement = FormalStatement.from_data(claim['statement'])
                    verification = AIVerifier().verify(statement)
                    evidence = verification.to_data()
                    # Wall time belongs to the enclosing observation receipt,
                    # not the deterministic logical result replayed by catalog.
                    evidence.pop('elapsed_seconds', None)
                    status = verification.status.value
                    # Inconsistent hypotheses are refused by AIVerifier.
                    reward = (0 if statement.goal.left == statement.goal.right else 1) if status == 'PROVEN' else -1
                else:
                    raise ValueError('Unsupported claim schema')
            except (ValueError, ArithmeticError, TypeError, KeyError, RuntimeError) as exc:
                status = 'rejected: '+str(exc)
            output.append({'step': _json(step), 'reward': reward, 'status': status, 'evidence': evidence})
        return {'steps': output, 'reward': sum(row['reward'] for row in output),
                'all_valid': all(row['reward'] >= 0 for row in output), 'formal_proof': False,
                'scope': 'atomic equalities / structured rational implications; no validation of free prose'}

    def export_dpo(self, prompt: str, chosen: Any, rejected: Any, filename: str | Path) -> dict[str, Any]:
        good, bad = self.verify(chosen), self.verify(rejected)
        if not good['all_valid'] or bad['all_valid'] or good['reward'] <= bad['reward']:
            raise ValueError('DPO pair requires a verified preference with a rejected deduction')
        pair = {'prompt': prompt, 'chosen': chosen, 'rejected': rejected,
                'chosen_verification': good, 'rejected_verification': bad}
        with Path(filename).open('x', encoding='utf-8') as stream:
            stream.write(canonical(pair)+'\n')
        return pair

# SECTION 9: numerical conjectures and counterexample discovery
class RamanujanEngine:
    """Bounded generalized continued-fraction matching against pi,e,zeta(3).

    Convergents are exact rational values b0+a1/(b1+...). Matches are numerical
    hypotheses from a finite coefficient lattice, never identities or proofs.
    Successive-convergent disagreement is reported as a stability diagnostic.
    """
    constants = {'pi': math.pi, 'e': math.e, 'zeta3': 1.2020569031595942}

    def continued_fraction(self, numerators: Sequence[int], denominators: Sequence[int]) -> Fraction:
        if len(denominators) != len(numerators)+1 or not 1 <= len(denominators) <= 512:
            raise ValueError('A continued fraction needs n numerators and n+1 denominators')
        if any(type(v) is not int or abs(v) > 1_000_000 for v in [*numerators, *denominators]):
            raise ValueError('Bounded integer CF coefficients required')
        result = Fraction(denominators[-1])
        for a, b in zip(reversed(numerators), reversed(denominators[:-1])):
            if result == 0:
                raise ZeroDivisionError('Singular continued-fraction tail')
            result = b+Fraction(a)/result
            if max(abs(result.numerator).bit_length(), result.denominator.bit_length()) > 32768:
                raise ValueError('Continued-fraction integer budget exceeded')
        return result

    def search(self, numerators: Sequence[int], denominators: Sequence[int], coefficient_bound: int = 3,
               powers: int = 2, tolerance: float = 1e-8) -> list[dict[str, Any]]:
        _budget(coefficient_bound, 32); _budget(powers, 8); tolerance = _positive(tolerance)
        value = float(self.continued_fraction(numerators, denominators))
        previous = float(self.continued_fraction(numerators[:-1], denominators[:-1])) if numerators else value
        terms = [('1', 1.0)]+[(f'{name}^{power}', constant**power) for name, constant in self.constants.items() for power in range(1, powers+1)]
        if (2*coefficient_bound+1)**len(terms) > 2_000_000:
            raise ValueError('Coefficient lattice exceeds search budget; reduce powers or bound')
        matches = []
        for coefficients in itertools.product(range(-coefficient_bound, coefficient_bound+1), repeat=len(terms)):
            if not any(coefficients):
                continue
            estimate = math.fsum(c*t for c, (_, t) in zip(coefficients, terms))
            error = abs(value-estimate)
            if error <= tolerance:
                matches.append({'coefficients': dict(zip((name for name, _ in terms), coefficients)),
                                'value': value, 'candidate': estimate, 'absolute_error': error,
                                'convergent_delta': abs(value-previous), 'proven': False, 'precision': 'binary64'})
        return sorted(matches, key=lambda row: row['absolute_error'])

    def search_high_precision(self, numerators: Sequence[int], denominators: Sequence[int],
                              precision: int = 80, max_coefficient: int = 10000,
                              powers: int = 2, tolerance: str = '1e-40') -> dict[str, Any]:
        """PSLQ integer-relation search at explicitly declared arbitrary precision.

        Relations involve the finite convergent and powers of pi,e,zeta(3).
        Repeating the relation at twice the precision checks numerical stability,
        but finite-convergent agreement is reported only as a conjecture.
        """
        mp = _require(_optional('mpmath'), 'mpmath')
        _budget(precision, 2000); _budget(max_coefficient, 1000000000); _budget(powers, 8)
        if precision < 30:
            raise ValueError('PSLQ search requires at least 30 decimal digits')
        value = self.continued_fraction(numerators, denominators)
        previous = self.continued_fraction(numerators[:-1], denominators[:-1]) if numerators else value
        with mp.workdps(precision):
            tol = mp.mpf(tolerance)
            if not mp.isfinite(tol) or not 0 < tol < 1:
                raise ValueError('PSLQ tolerance must be finite and in (0,1)')
            constants = [('1', mp.mpf(1))]+[(f'{name}^{power}', base**power)
                for name, base in [('pi', mp.pi), ('e', mp.e), ('zeta3', mp.zeta(3))]
                for power in range(1, powers+1)]
            convergent = mp.mpf(value.numerator)/value.denominator
            relation = mp.pslq(mp.matrix([convergent]+[v for _, v in constants]), tol=tol,
                              maxcoeff=max_coefficient, maxsteps=10000)
            residual = None; stable = False
            if relation is not None and relation[0] and any(relation[2:]):
                with mp.workdps(precision*2):
                    terms = [mp.mpf(value.numerator)/value.denominator, mp.mpf(1)]+[
                        base**power for base in (mp.pi, mp.e, mp.zeta(3)) for power in range(1, powers+1)]
                    residual_value = abs(mp.fsum(c*t for c, t in zip(relation, terms)))
                    residual = mp.nstr(residual_value, precision)
                    stable = bool(residual_value <= mp.mpf(tolerance))
            else:
                relation = None
            delta = abs(convergent-mp.mpf(previous.numerator)/previous.denominator)
            return {'relation': dict(zip(['continued_fraction']+[name for name, _ in constants], relation)) if relation else None,
                    'precision_digits': precision, 'recheck_digits': 2*precision,
                    'residual': residual, 'numerically_stable': stable,
                    'convergent_delta': mp.nstr(delta, precision), 'proven': False,
                    'scope': 'finite-convergent numerical conjecture; no irrational identity proof'}


class CounterexampleFuzzer:
    """Stochastic boundary search or exact-replayed negated rational SMT claims.

    Random search disproves only with a concrete false predicate. A failed
    search is inconclusive. SMT SAT witnesses are accepted only after Nabla's
    AIVerifier replays them using exact rational arithmetic.
    """
    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)

    def check_smt(self, statement: Any) -> dict[str, Any]:
        result = AIVerifier().verify(statement)
        return {'status': result.status.value, 'counterexample': result.counterexample,
                'verification': result.to_data(), 'formal_proof': False}

    def fuzz(self, predicate: Callable[[Mapping[str, float]], bool], bounds: Mapping[str, Sequence[float]],
             trials: int = 1000) -> dict[str, Any]:
        _budget(trials, 1_000_000)
        domain = {}
        for key, pair in bounds.items():
            if len(pair) != 2:
                raise ValueError('Bounds must be [lower,upper]')
            lo, hi = map(_finite, pair)
            if lo >= hi:
                raise ValueError('Invalid fuzzer interval')
            domain[key] = lo, hi
        if not domain:
            raise ValueError('Nonempty fuzzer domain required')
        for index in range(trials):
            sample = {}
            for key, (lo, hi) in domain.items():
                edges = [lo, math.nextafter(lo, hi), hi, math.nextafter(hi, lo), (lo/2+hi/2)]
                uniform = self.rng.random()
                sample[key] = _finite(edges[index % len(edges)] if index < len(edges) else
                                      (1-uniform)*lo+uniform*hi)
            try:
                result = predicate(sample)
                if type(result) is not bool:
                    raise ValueError('Predicate must return a bool')
            except (ArithmeticError, ValueError) as exc:
                return {'status': 'domain_error', 'input': sample, 'reason': str(exc), 'proven': False}
            if not result:
                return {'status': 'counterexample', 'input': sample, 'trials': index+1, 'proven': False}
        return {'status': 'inconclusive', 'trials': trials, 'proven': False}

# SECTION 10: Elo generator/solver curriculum
class SelfPlayCurriculumArena:
    """Elo update R+=K(s-E), E=1/(1+10^((R_opponent-R)/400)).

    Binary solver successes raise its rating and the selected task difficulty;
    failures lower it. Matching task and solver ratings targets E=0.5.
    Failure distillation records observations, never fabricates a valid proof.
    """
    def __init__(self, seed: int = 0, solver_rating: float = 1000, generator_rating: float = 1000,
                 k_factor: float = 24) -> None:
        self.solver_rating = _finite(solver_rating); self.generator_rating = _finite(generator_rating)
        self.k_factor = _positive(k_factor); self.seed = seed
        self.failures: list[dict[str, Any]] = []
        self.rounds = 0

    def update(self, success: bool) -> dict[str, float]:
        if type(success) is not bool:
            raise ValueError('A verified binary outcome is required')
        delta = max(-300, min(300, (self.generator_rating-self.solver_rating)/400))
        expected = 1/(1+10**delta)
        change = self.k_factor*(int(success)-expected)
        solver = _finite(self.solver_rating+change, 'updated solver rating')
        generator = _finite(self.generator_rating-change, 'updated generator rating')
        self.solver_rating, self.generator_rating = solver, generator
        self.rounds += 1
        return {'solver_rating': self.solver_rating, 'generator_rating': self.generator_rating,
                'expected_success': expected, 'target_success': .5}

    def difficulty(self) -> int:
        # Task ladder is monotone in solver skill and remains in generator bounds.
        return max(1, min(8, 3+math.floor((self.solver_rating-1000)/100)))

    def play(self, solver: Callable[[str], Any], rounds: int = 10, kind: str = 'polynomial') -> list[dict[str, Any]]:
        _budget(rounds, 100000)
        forge = InverseProblemSynthesizer(self.seed)
        results = []
        for _ in range(rounds):
            task = forge.generate(kind, self.difficulty())
            answer = _json(solver(task['prompt']))
            success = answer == task['solution']
            rating = self.update(success)
            if not success:
                self.failures.append({'prompt': task['prompt'], 'failed_attempt': answer,
                    'verified_solution': task['solution'], 'evidence': task['receipt'],
                    'reflection': 'Compare the attempted answer with the exact generation recipe before retrying.'})
            results.append({'success': success, 'ratings': rating, 'problem_receipt': task['receipt']['content_id']})
        return results

    def distill_failures(self) -> Iterator[dict[str, Any]]:
        yield from (json.loads(canonical(failure)) for failure in self.failures)

# SECTION 11: streamed RLVR JSONL / Parquet with evidence validation
class FrontierRLVRExporter:
    """Streaming RLVR records with verified evidence, bounded Parquet row groups.

    verifier_signature is a scoped verifier attestation, not a cryptographic
    signature or a guarantee about arbitrary prose. Each record binds its prompt,
    solution and trajectory to a valid receipt plus replayed calculation steps.
    """
    def __init__(self, batch_size: int = 256) -> None:
        self.batch_size = _budget(batch_size, 65536)

    def prepare(self, item: Mapping[str, Any]) -> dict[str, Any]:
        audit = item['receipt']; prompt = item['prompt']; trajectory = item['thinking_trajectory']
        if not verify_receipt(audit) or audit.get('operation') != 'omni_synthetic_problem':
            raise ValueError('Invalid synthetic problem receipt')
        if audit['inputs']['prompt'] != prompt or audit['result'] != {'solution': item['solution'], 'thinking_trajectory': trajectory}:
            raise ValueError('Problem diverges from its bound receipt')
        ChainOfThoughtBuilder().build(trajectory, item['solution'])
        if audit['parents'] != [step['receipt']['content_id'] for step in trajectory]:
            raise ValueError('Trajectory provenance mismatch')
        if len(trajectory) != 1:
            raise ValueError('This generator contract requires one exact generation recipe')
        calculation = trajectory[0]['receipt']
        args, result = calculation['request']['arguments'], calculation['result']
        solution, kind = item['solution'], audit['inputs']['kind']
        operation = calculation['request']['operation']
        if kind == 'polynomial':
            valid = operation == 'integrate' and args.get('start') == 0 and args.get('end') == 1 and solution == result['value']
            valid = valid and prompt == f'Calcule a integral de 0 a 1 de {args.get("source")}.'
        elif kind == 'matrix':
            valid = operation == 'matrix_properties' and isinstance(solution, list)
            coefficients = [Fraction(1)]
            if valid:
                for root in solution:
                    root = Fraction(str(root)); expanded = [Fraction(0)]*(len(coefficients)+1)
                    for i, value in enumerate(coefficients):
                        expanded[i] -= root*value; expanded[i+1] += value
                    coefficients = expanded
                valid = coefficients == [Fraction(v) for v in result['characteristic_polynomial']]
                matrix = args['matrix']
                valid = valid and all(matrix[i][j] == 0 for i in range(len(matrix)) for j in range(i))
                valid = valid and prompt == f'Determine os autovalores com multiplicidade da matriz triangular {matrix}.'
        elif kind == 'factorization':
            valid = operation == 'factor' and isinstance(solution, dict) and set(solution) == {'integer_roots'}
            coefficients = [1]
            if valid:
                for root in solution['integer_roots']:
                    if type(root) is not int:
                        raise ValueError('Integer roots required')
                    expanded = [0]*(len(coefficients)+1)
                    for i, value in enumerate(coefficients):
                        expanded[i] -= root*value; expanded[i+1] += value
                    coefficients = expanded
                valid = coefficients == args['coefficients']
                valid = valid and prompt == f'Fatore o polinômio de coeficientes ascendentes {args["coefficients"]}.'
        elif kind == 'quantum':
            valid = operation == 'evaluate' and isinstance(solution, dict)
            if valid:
                bits = list(solution['output'])
                if any(type(v) is not int or v not in (0, 1) for v in bits+list(solution['basis_state'])):
                    raise ValueError('Computational basis bits required')
                for control, target in reversed(solution['forward_gates']):
                    if type(control) is not int or type(target) is not int or not 0 <= control < len(bits) or not 0 <= target < len(bits) or control == target:
                        raise ValueError('Invalid CNOT gate')
                    bits[target] ^= bits[control]
                valid = bits == solution['basis_state'] and Fraction(result['value']) == sum(bit*2**i for i, bit in enumerate(bits))
                valid = valid and prompt == f'Inverta as portas CNOT {solution["forward_gates"]} sobre o estado computacional {solution["output"]}.'
        else:
            valid = False
        if not valid:
            raise ValueError('Solution is not justified by the exact generation recipe')
        return {'prompt': prompt, 'thinking_trajectory': trajectory, 'solution': item['solution'],
                'verifiable_reward_receipt': audit['content_id'],
                'verifier_signature': {'verifier': 'nabla-exact-replay-v1', 'receipt_integrity': True,
                    'scope': 'replayed generation calculations; not a universal absence-of-hallucination guarantee',
                    'cryptographic_signature': False}, 'receipt': audit}

    def export(self, items: Iterable[Mapping[str, Any]], filename: str | Path) -> dict[str, Any]:
        path = Path(filename)
        if path.suffix not in {'.jsonl', '.parquet'}:
            raise ValueError('Choose .jsonl or .parquet')
        hasher = StreamingMerkleHasher(); count = 0
        # Exclusive creation protects existing datasets. A failure removes only
        # the partial artifact created by this invocation.
        created = False
        try:
            if path.suffix == '.jsonl':
                with path.open('xb') as stream:
                    created = True
                    for item in items:
                        record = self.prepare(item)
                        row = (canonical(record)+'\n').encode()
                        if len(row) > 16*1024*1024:
                            raise ValueError('RLVR row exceeds 16 MiB')
                        stream.write(row); hasher.update(row); count += 1
            else:
                _require(pyarrow, 'pyarrow')
                import pyarrow.parquet as pq
                # Nested trajectories remain canonical JSON strings, avoiding
                # per-task schemas that change across row groups.
                schema = pyarrow.schema([(key, pyarrow.string()) for key in
                    ('prompt', 'thinking_trajectory', 'solution', 'verifiable_reward_receipt', 'verifier_signature', 'receipt')])
                with path.open('xb') as stream:
                    created = True
                    with pq.ParquetWriter(stream, schema) as writer:
                        batch: list[dict[str, str]] = []; batch_bytes = 0
                        for item in items:
                            record = self.prepare(item); row = (canonical(record)+'\n').encode()
                            if len(row) > 16*1024*1024:
                                raise ValueError('RLVR row exceeds 16 MiB')
                            if batch and batch_bytes+len(row) > 64*1024*1024:
                                writer.write_table(pyarrow.Table.from_pylist(batch, schema=schema)); batch = []; batch_bytes = 0
                            batch.append({k: v if isinstance(v, str) else canonical(v) for k, v in record.items()})
                            batch_bytes += len(row); hasher.update(row); count += 1
                            if len(batch) >= self.batch_size:
                                writer.write_table(pyarrow.Table.from_pylist(batch, schema=schema)); batch = []; batch_bytes = 0
                        if batch:
                            writer.write_table(pyarrow.Table.from_pylist(batch, schema=schema))
            return {'records': count, 'logical_row_merkle_root': hasher.finalize_root_hash(), 'filename': str(path),
                    'format': path.suffix[1:], 'parquet_nested_encoding': 'canonical JSON strings'}
        except BaseException:
            if created:
                path.unlink(missing_ok=True)
            raise

    def bundle(self, items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        prepared = [self.prepare(item) for item in items]
        return create_bundle([item['receipt'] for item in prepared], datasets={'rlvr': prepared})

# SECTION 12: unified modules, dispatcher and official observation receipts
class NeuralOperatorModule:
    """FNO training on explicit CPU/CUDA with mini-batches and PINN penalties.

    The objective is supervised mean squared error plus an optional stationary
    diffusion residual ||nu Laplacian(u)-forcing||². Gradients traverse the FFT,
    local bypass and physical stencil. Checkpoints contain weights and optimizer
    state; a JSON manifest binds their SHA-256 bytes to model architecture.
    """
    is_available = torch is not None

    def train(self, inputs: Any, targets: Any, epochs: int = 10, learning_rate: float = 1e-3,
              width: int = 16, modes: int = 8, layers: int = 4, seed: int = 0,
              device: str = 'auto', batch_size: int | None = None, dtype: str = 'float32',
              physics_weight: float = 0, viscosity: float = .01, forcing: Any = None,
              spacing: Sequence[float] = (1, 1), checkpoint_path: str | None = None,
              gradient_clip: float = 10) -> dict[str, Any]:
        runtime = DeviceRuntime(device, seed, dtype)
        _budget(epochs, 10000); learning_rate = _positive(learning_rate)
        physics_weight = _positive(physics_weight, zero=True); viscosity = _positive(viscosity, zero=True)
        gradient_clip = _positive(gradient_clip)
        x, y = runtime.tensor(inputs).detach(), runtime.tensor(targets).detach()
        if x.ndim != 4 or y.ndim != 4 or x.shape[0] != y.shape[0] or x.shape[2:] != y.shape[2:] or min(x.shape[-2:]) < 3:
            raise ValueError('FNO training needs finite NCHW inputs/targets with compatible grids')
        batch_size = len(x) if batch_size is None else _budget(batch_size, len(x))
        if len(spacing) != 2:
            raise ValueError('FNO residual requires dy,dx spacings')
        forcing_tensor = torch.zeros_like(y) if forcing is None else runtime.tensor(forcing)
        if forcing_tensor.shape != y.shape:
            raise ValueError('Forcing must match target shape')
        devices = [runtime.device.index] if runtime.device.type == 'cuda' else []
        runtime.begin()
        with torch.random.fork_rng(devices=devices):
            torch.random.default_generator.manual_seed(seed)
            if devices:
                with torch.cuda.device(runtime.device):
                    torch.cuda.manual_seed(seed)
            model = FourierNeuralOperator2D(x.shape[1], y.shape[1], width, modes, layers, seed).to(device=runtime.device)
            model = model.double() if runtime.dtype == torch.float64 else model.float()
            optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
            losses, physics_losses = [], []
            for _ in range(epochs):
                permutation = torch.randperm(len(x), generator=runtime.generator, device=runtime.device)
                epoch_loss = torch.zeros((), device=runtime.device, dtype=runtime.dtype)
                epoch_physics = torch.zeros_like(epoch_loss)
                for start in range(0, len(x), batch_size):
                    indices = permutation[start:start+batch_size]
                    optimizer.zero_grad(set_to_none=True)
                    prediction = model(x[indices])
                    supervised = (prediction-y[indices]).square().mean()
                    physical = torch.zeros_like(supervised)
                    if physics_weight:
                        residual = viscosity*GPUStencilBank.laplacian(prediction, spacing, accuracy=2)-forcing_tensor[indices]
                        physical = residual.square().mean()
                    loss = supervised+physics_weight*physical
                    _tensor_finite(loss, 'training loss')
                    loss.backward()
                    for parameter in model.parameters():
                        if parameter.grad is not None:
                            _tensor_finite(parameter.grad, 'training gradient')
                    torch.nn.utils.clip_grad_norm_(model.parameters(), gradient_clip, error_if_nonfinite=True)
                    optimizer.step()
                    for parameter in model.parameters():
                        _tensor_finite(parameter, 'trained weight')
                    epoch_loss += loss.detach()*len(indices)/len(x)
                    epoch_physics += physical.detach()*len(indices)/len(x)
                losses.append(float(epoch_loss.cpu())); physics_losses.append(float(epoch_physics.cpu()))
            self.model, self.optimizer = model, optimizer
            architecture = {'in_channels': x.shape[1], 'out_channels': y.shape[1], 'width': width,
                            'modes': modes, 'layers': layers, 'seed': seed}
            self.architecture = architecture
            state = {name: {'shape': list(value.shape), 'dtype': str(value.dtype),
                           'sha256': hashlib.sha256(value.detach().cpu().contiguous().numpy().tobytes()).hexdigest()}
                     for name, value in model.state_dict().items()}
            result = {'losses': losses, 'physics_losses': physics_losses,
                      'weights_hash': fingerprint(state), 'seed': seed, 'device': str(runtime.device),
                      'backend': 'torch-'+runtime.device.type, 'physics_certified': False,
                      'architecture': architecture, 'batch_size': batch_size}
            if checkpoint_path is not None:
                self.save_checkpoint(checkpoint_path)
                result['checkpoint_sha256'] = hashlib.sha256(Path(checkpoint_path).read_bytes()).hexdigest()
        runtime.finish(); self.last_execution = runtime.information()
        return result

    def predict(self, inputs: Any) -> Any:
        """Infer on the fitted model's device, returning a native Torch tensor."""
        if not hasattr(self, 'model'):
            raise RuntimeError('Fit or restore the FNO before prediction')
        parameter = next(self.model.parameters())
        x = torch.as_tensor(inputs, device=parameter.device, dtype=parameter.dtype)
        _tensor_finite(x)
        self.model.eval()
        with torch.no_grad():
            return _tensor_finite(self.model(x), 'prediction')

    def save_checkpoint(self, filename: str | Path) -> dict[str, Any]:
        """Exclusively save tensor state; restore uses Torch's weights-only loader."""
        if not hasattr(self, 'model'):
            raise RuntimeError('No fitted model to save')
        with Path(filename).open('xb') as stream:
            torch.save({'architecture': self.architecture, 'state_dict': self.model.state_dict(),
                        'optimizer': self.optimizer.state_dict()}, stream)
        return {'filename': str(filename), 'sha256': hashlib.sha256(Path(filename).read_bytes()).hexdigest()}

    def load_checkpoint(self, filename: str | Path, expected_sha256: str, device: str = 'auto') -> None:
        """Refuse modified checkpoints before any deserialization or allocation."""
        _require(torch, 'torch')
        path = Path(filename)
        if path.stat().st_size > 1024**3 or hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
            raise ValueError('Checkpoint size/hash mismatch')
        runtime = DeviceRuntime(device)
        payload = torch.load(path, map_location=runtime.device, weights_only=True)
        architecture = payload['architecture']
        model = FourierNeuralOperator2D(**architecture).to(runtime.device)
        if payload['state_dict']['lift.weight'].dtype == torch.float64:
            model = model.double()
        model.load_state_dict(payload['state_dict'], strict=True)
        for parameter in model.parameters():
            _tensor_finite(parameter, 'checkpoint weight')
        self.model = model; self.architecture = architecture
        self.optimizer = torch.optim.Adam(model.parameters())
        self.optimizer.load_state_dict(payload['optimizer'])


class CausalBayesianModule:
    """Facade for finite interventions and continuous linear DAG discovery."""
    @staticmethod
    def discover(**kwargs: Any) -> Any:
        """Fit the linear least-squares NOTEARS objective under acyclicity."""
        return NOTEARSDiscovery().fit(**kwargs)

    @staticmethod
    def intervene(domains: Any, parents: Any, cpts: Any, target: str, intervention: Any = None) -> Any:
        return CausalStructuralModel(domains, parents, cpts).do_calculus(target, intervention)


class PhotorealisticRadiativeModule:
    """Facade for 32-band surface/volume Monte Carlo radiance on CPU/CUDA."""
    @staticmethod
    def render(scene: Any = None, seed: int = 0, max_depth: int = 6, **kwargs: Any) -> Any:
        return CertifiedSpectralPathTracer(scene, seed, max_depth).render(**kwargs)


class MassiveDataStreamModule:
    """Stream buffers through bounded chunks into a provenance Merkle root."""
    @staticmethod
    def hash_stream(source: Any, chunk_bytes: int = 64*1024*1024) -> dict[str, Any]:
        hasher = StreamingMerkleHasher()
        for chunk in TensorStreamIngestor(chunk_bytes).iter_chunks(source):
            hasher.update(chunk)
        return {'root_hash': hasher.finalize_root_hash(), 'bytes': hasher.bytes_read, 'chunks': hasher.leaves,
                'chunk_bytes': chunk_bytes}


class FormalMCTSModule(FormalMCTSSearcher):
    """Public bounded PUCT proof-search module; see FormalMCTSSearcher."""


class SyntheticForgeModule(InverseProblemSynthesizer):
    """Public exact inverse-task stream and recipe generation module."""


class ProcessRewardModule(ProcessRewardVerifier):
    """Public exact/SMT process reward module with fail-closed step auditing."""


class RamanujanConjectureModule(RamanujanEngine):
    """Public numerical continued-fraction candidate search module."""


class SelfPlayCurriculumModule(SelfPlayCurriculumArena):
    """Public bounded Elo curriculum with retained failed-attempt evidence."""


class RLVRExporterModule(FrontierRLVRExporter):
    """Public streaming JSONL/Parquet exporter with exact recipe replay."""


class OmniEngine:
    """Unified bounded science dispatcher with official Nabla receipts.

    execute returns result+observation receipt with CPU/wall/CUDA-event timing
    and a seeded provenance hash. capture_values=False preserves native tensors
    and records chunked SHA-256 content ledgers in the observation receipt. execute_action is the catalog adapter: telemetry is queued
    separately so the canonical calculation result remains replayable. Tensor
    objects must be converted to explicit finite input arrays before dispatch.
    """
    ACTIONS = frozenset({'train_surrogate_fno', 'discover_causal_dag', 'render_certified_radiance',
        'synthesize_synthetic_dataset', 'verify_chain_of_thought', 'run_mcts_proof_search',
        'hash_tensor_stream', 'search_ramanujan_conjecture', 'fit_sparse_gp', 'pde_residual',
        'rasterize_physical_gaussians', 'advance_gaussian_mechanics', 'run_horn_proof_search',
        'search_ramanujan_high_precision'})

    @staticmethod
    def catalog_schema() -> dict[str, Any]:
        """Closed JSON Schema for the in-memory AI/catalog action subset.

        Structured SMT claims, arbitrary catalog tactics and artifact paths stay
        on the Python API. AI callers receive authored nested types, preventing
        unknown parameters from reaching an optional backend or filesystem.
        """
        def record(properties: dict[str, Any], required: Sequence[str] = ()) -> dict[str, Any]:
            return {'type': 'object', 'properties': properties, 'required': list(required), 'additionalProperties': False}
        def array(items: Any, maximum: int = 4096, minimum: int = 1) -> dict[str, Any]:
            return {'type': 'array', 'items': items, 'minItems': minimum, 'maxItems': maximum}
        def integer(maximum: int, minimum: int = 1) -> dict[str, Any]:
            return {'type': 'integer', 'minimum': minimum, 'maximum': maximum}
        number = {'type': 'number'}
        text = {'type': 'string', 'minLength': 1, 'maxLength': 65536}
        positive = {'type': 'number', 'exclusiveMinimum': 0}
        vector3 = array(number, 3, 3)
        matrix = array(array(number))
        tensor = {'$ref': '#/$defs/tensor'}
        spectrum = {'anyOf': [number, array(number, 32, 32)]}
        material = record({'roughness': {'type': 'number', 'exclusiveMinimum': 0, 'maximum': 1},
                           'n': spectrum, 'k': spectrum, 'albedo': spectrum, 'metallic': {'type': 'boolean'}})
        scene = record({'environment': spectrum, 'spheres': array(record({'center': vector3, 'radius': positive,
                        'emission': spectrum, 'material': material}, ('center', 'radius')), 10000, 0)})
        variants = {
            'train_surrogate_fno': ({'inputs': tensor, 'targets': tensor, 'epochs': integer(10000),
                'device': {'type': 'string', 'pattern': '^(auto|cpu|cuda(:[0-9]+)?)$'},
                'batch_size': integer(1000000), 'physics_weight': {'type': 'number', 'minimum': 0},
                'viscosity': {'type': 'number', 'minimum': 0}, 'forcing': tensor,
                'dtype': {'enum': ['float32', 'float64']}, 'gradient_clip': positive, 'spacing': array(positive, 2, 2),
                'learning_rate': positive, 'width': integer(512), 'modes': integer(4096), 'layers': integer(32)}, ('inputs', 'targets')),
            'discover_causal_dag': ({'data': matrix, 'l1': {'type': 'number', 'minimum': 0},
                'max_iter': integer(1000), 'tolerance': positive, 'threshold': {'type': 'number', 'minimum': 0}}, ('data',)),
            'render_certified_radiance': ({'scene': scene, 'width': integer(4096), 'height': integer(4096),
                'samples': integer(1000000, 2), 'max_depth': integer(128),
                'camera': record({'origin': vector3, 'target': vector3, 'up': vector3,
                                  'fov': {'type': 'number', 'exclusiveMinimum': 0, 'exclusiveMaximum': 179}})}, ()),
            'synthesize_synthetic_dataset': ({'count': integer(256), 'difficulty': integer(8),
                'kind': {'enum': ['polynomial', 'matrix', 'factorization', 'quantum']}}, ()),
            'verify_chain_of_thought': ({'reasoning': {'anyOf': [text, array(record({'left': text, 'right': text}, ('left', 'right')), 256)]}}, ('reasoning',)),
            'run_mcts_proof_search': ({'left': text, 'right': text, 'iterations': integer(10000), 'depth': integer(32)}, ('left', 'right')),
            'hash_tensor_stream': ({'source': tensor, 'chunk_bytes': integer(64*1024*1024)}, ('source',)),
            'search_ramanujan_conjecture': ({'numerators': array(integer(1000000, -1000000), 511, 0),
                'denominators': array(integer(1000000, -1000000), 512), 'coefficient_bound': integer(32),
                'powers': integer(8), 'tolerance': positive}, ('numerators', 'denominators')),
        }
        device_schema = {'type': 'string', 'pattern': '^(auto|cpu|cuda(:[0-9]+)?)$'}
        scene['properties']['triangles'] = array(record({'vertices': array(vector3, 3, 3), 'material': material,
                                                       'emission': spectrum}, ('vertices',)), 10000, 0)
        scene['properties']['medium'] = record({'sigma_a': spectrum, 'sigma_s': spectrum,
                                                'g': {'type': 'number', 'exclusiveMinimum': -1, 'exclusiveMaximum': 1}})
        for name in ('train_surrogate_fno', 'discover_causal_dag', 'render_certified_radiance'):
            variants[name][0]['device'] = device_schema
        variants['discover_causal_dag'][0].update(inner_steps=integer(10000), learning_rate=positive)
        variants['render_certified_radiance'][0].update(ray_batch_size=integer(262144), medium_radius=positive,
                                                      dtype={'enum': ['float32', 'float64']})
        native_fields = {'device': device_schema, 'dtype': {'enum': ['float32', 'float64']}}
        variants.update({
            'fit_sparse_gp': ({'inducing_points': matrix, 'inputs': matrix, 'targets': array(number),
                'queries': matrix, 'length_scale': positive, 'noise': positive, 'device': device_schema},
                ('inducing_points', 'inputs', 'targets', 'queries')),
            'pde_residual': ({**native_fields, 'field': tensor, 'pressure': tensor,
                'pde_type': {'enum': ['navier_stokes', 'burgers']}, 'viscosity': {'type': 'number', 'minimum': 0},
                'spacing': array(positive, 3, 3), 'accuracy': {'enum': list(range(2,21,2))},
                'boundary': {'enum': ['periodic', 'zero', 'reflect']}}, ('field',)),
            'rasterize_physical_gaussians': ({**native_fields, 'positions': matrix, 'covariances': tensor,
                'colors': matrix, 'opacities': array(number), 'width': integer(4096), 'height': integer(4096),
                'focal': positive, 'near': positive}, ('positions', 'covariances', 'colors', 'opacities', 'width', 'height')),
            'advance_gaussian_mechanics': ({**native_fields, 'positions': matrix, 'covariances': tensor,
                'stresses': tensor, 'velocities': matrix, 'gradients': tensor, 'dt': positive,
                'young_modulus': positive, 'poisson_ratio': {'type': 'number', 'exclusiveMinimum': -1, 'exclusiveMaximum': .5},
                'yield_stress': positive}, ('positions','covariances','stresses','velocities','gradients','dt')),
            'search_ramanujan_high_precision': ({'numerators': array(integer(1000000, -1000000), 511, 0),
                'denominators': array(integer(1000000, -1000000), 512), 'precision': integer(2000, 30),
                'max_coefficient': integer(1000000000), 'powers': integer(8), 'tolerance': text}, ('numerators','denominators')),
            'run_horn_proof_search': ({'facts': array({'$ref': '#/$defs/term'}, 1000, 0),
                'rules': array({'type': 'array', 'prefixItems': [array({'$ref': '#/$defs/term'}, 32, 0), {'$ref': '#/$defs/term'}], 'items': False, 'minItems': 2, 'maxItems': 2},128),
                'goals': array({'$ref': '#/$defs/term'},128), 'iterations': integer(10000), 'depth': integer(128)},
                ('facts','rules','goals')),
        })
        choices = []
        for action, (properties, required) in variants.items():
            properties['seed'] = integer(2**63-1, 0)
            choices.append(record({'action': {'const': action}, 'parameters': record(properties, required)},
                                  ('action', 'parameters') if required else ('action',)))
        return {'type': 'object', 'oneOf': choices, '$defs': {'tensor': {'anyOf': [number, array(tensor)]},
            'term': {'anyOf': [text, {'type': 'integer'}, array({'$ref': '#/$defs/term'}, 32)]}}}

    def __init__(self, session: CalculationSession | None = None, seed: int = 0, device: str = 'auto') -> None:
        if type(seed) is not int or not 0 <= seed < 2**63:
            raise ValueError('Seed must be an integer in [0,2^63)')
        self.session = session; self.seed = seed; self.device = device
        self.neural = NeuralOperatorModule()

    def _dispatch(self, action: str, kwargs: dict[str, Any]) -> Any:
        if action == 'train_surrogate_fno':
            kwargs.setdefault('device', self.device)
            result = self.neural.train(seed=self.seed, **kwargs)
            self._last_device_execution = self.neural.last_execution
            return result
        if action == 'discover_causal_dag':
            if self.device != 'auto' or (torch is not None and torch.cuda.is_available()):
                kwargs.setdefault('device', self.device)
            return NOTEARSDiscovery().fit(seed=self.seed, **kwargs)
        if action == 'render_certified_radiance':
            if torch is not None or self.device.startswith('cuda'):
                kwargs.setdefault('device', self.device)
            return PhotorealisticRadiativeModule.render(seed=self.seed, **kwargs)
        if action == 'synthesize_synthetic_dataset':
            count = kwargs.pop('count', 1); filename = kwargs.pop('filename', None)
            stream = InverseProblemSynthesizer(self.seed, self.session).stream(count, **kwargs)
            if filename is not None:
                return FrontierRLVRExporter().export(stream, filename)
            if count > 256:
                raise ValueError('For >256 problems provide filename for streaming export')
            return {'problems': list(stream), 'seed': self.seed}
        if action == 'verify_chain_of_thought':
            return ProcessRewardVerifier(self.session).verify(**kwargs)
        if action == 'run_mcts_proof_search':
            return FormalMCTSSearcher(self.session).search(**kwargs)
        if action == 'hash_tensor_stream':
            if isinstance(kwargs.get('source'), list):
                kwargs['source'] = _array(kwargs['source'])
            return MassiveDataStreamModule.hash_stream(**kwargs)
        if action == 'search_ramanujan_conjecture':
            return RamanujanEngine().search(**kwargs)
        if action == 'fit_sparse_gp':
            points = kwargs.pop('inducing_points'); x = kwargs.pop('inputs'); y = kwargs.pop('targets')
            queries = kwargs.pop('queries'); length_scale = kwargs.pop('length_scale', 1.)
            noise = kwargs.pop('noise', 1e-4); device = kwargs.pop('device', self.device)
            if kwargs:
                raise ValueError('Unknown GP parameters')
            selected = device if torch is not None or str(device).startswith('cuda') else None
            self.gp = SparseGaussianProcessSurrogate(points, length_scale, noise, selected).partial_fit(x, y)
            mean, variance = self.gp.predict(queries)
            return {'mean': mean, 'variance': variance, 'samples': self.gp.samples,
                    'execution': self.gp.runtime.information() if self.gp._on_device else {},
                    'uncertainty_scope': 'inducing-point Gaussian model; no certified true-function interval'}
        if action == 'pde_residual':
            runtime = DeviceRuntime(kwargs.pop('device', self.device), self.seed, kwargs.pop('dtype', 'float32'))
            velocity = runtime.tensor(kwargs.pop('field')); pressure = kwargs.pop('pressure', None)
            pressure = runtime.tensor(pressure) if pressure is not None else None
            enforcer = PhysicsInformedEnforcer(kwargs.pop('viscosity', .01), kwargs.pop('spacing', [1, 1, 1]))
            runtime.begin(); value = enforcer.compute_tensor_residual(velocity, pressure, **kwargs); runtime.finish()
            return {'residual': value, 'rms_residual': float(value.square().mean().sqrt().cpu()), 'execution': runtime.information()}
        if action == 'rasterize_physical_gaussians':
            runtime = DeviceRuntime(kwargs.pop('device', self.device), self.seed, kwargs.pop('dtype', 'float32'))
            values = [runtime.tensor(kwargs.pop(key)) for key in ('positions', 'covariances', 'colors', 'opacities')]
            runtime.begin(); image = DifferentiableRasterizer().rasterize_tensors(*values, **kwargs); runtime.finish()
            return {'image': image, 'execution': runtime.information()}
        if action == 'advance_gaussian_mechanics':
            runtime = DeviceRuntime(kwargs.pop('device', self.device), self.seed, kwargs.pop('dtype', 'float32'))
            coupler = ContinuumMechanicsCoupler(kwargs.pop('young_modulus', 1e3), kwargs.pop('poisson_ratio', .3), kwargs.pop('yield_stress', 1e3))
            values = [runtime.tensor(kwargs.pop(key)) for key in ('positions', 'covariances', 'stresses', 'velocities', 'gradients')]
            runtime.begin(); result = coupler.step_tensors(*values, **kwargs); runtime.finish()
            return {**result, 'execution': runtime.information()}
        if action == 'run_horn_proof_search':
            return FormalMCTSSearcher(self.session).search_horn(seed=self.seed, **kwargs)
        if action == 'search_ramanujan_high_precision':
            return RamanujanEngine().search_high_precision(**kwargs)
        raise ValueError('Unknown OmniEngine action: '+str(action))

    def execute(self, action: str, *, capture_values: bool = True, **kwargs: Any) -> dict[str, Any]:
        if action not in self.ACTIONS:
            raise ValueError('Unknown OmniEngine action: '+str(action))
        if type(capture_values) is not bool:
            raise ValueError('capture_values must be a bool')
        if capture_values:
            inputs = json.loads(canonical(_json(kwargs)))
            snapshot = json.loads(canonical(inputs))
        else:
            snapshot, inputs = _native_audit_snapshot(kwargs, clone=True)
        started, cpu = time.perf_counter(), time.process_time()
        self._last_device_execution = {}
        timing_runtime = None
        native_actions = {'train_surrogate_fno','render_certified_radiance','discover_causal_dag',
                          'fit_sparse_gp','pde_residual','rasterize_physical_gaussians','advance_gaussian_mechanics'}
        if action in native_actions and torch is not None:
            timing_runtime = DeviceRuntime(str(snapshot.get('device', self.device)), self.seed, snapshot.get('dtype','float32'))
            timing_runtime.begin()
        result = self._dispatch(action, snapshot)
        if isinstance(result, dict) and 'execution' in result:
            self._last_device_execution = result.pop('execution')
        if timing_runtime is not None:
            elapsed_gpu = timing_runtime.finish()
            information = timing_runtime.information()
            information.update(self._last_device_execution)
            information['gpu_seconds'] = elapsed_gpu
            self._last_device_execution = information
        if capture_values:
            result = _json(result); result_audit = result
        else:
            result, result_audit = _native_audit_snapshot(result)
        telemetry = {'seed': self.seed, 'wall_seconds': time.perf_counter()-started,
                     'cpu_seconds': time.process_time()-cpu, 'gpu_seconds': self._last_device_execution.get('gpu_seconds'),
                     'gpu_timing_status': 'cuda_events' if self._last_device_execution.get('gpu_seconds') is not None else 'not_used', 'provenance_hash': fingerprint({'action': action, 'inputs': inputs, 'seed': self.seed}),
                     'capture_values': capture_values, 'device_execution': self._last_device_execution, 'backend_availability': dict(AVAILABLE), 'claim': 'execution observation; no universal mathematical or physical proof'}
        if self.session is None:
            audit = receipt('omni_superintelligence', {'action': action, 'parameters': inputs, 'seed': self.seed}, result_audit,
                            backend='omni-python', metadata=telemetry)
        else:
            audit = self.session.record_observation('omni_superintelligence',
                {'action': action, 'parameters': inputs, 'seed': self.seed}, result_audit,
                backend='omni-python', metadata=telemetry).result()
        return {'result': result, 'receipt': audit}

    @classmethod
    def execute_action(cls, action_name: str, kwargs: Mapping[str, Any],
                       session: CalculationSession | None = None) -> dict[str, Any]:
        if not isinstance(kwargs, Mapping):
            raise ValueError('Action parameters must be a mapping')
        parameters = dict(kwargs); seed = parameters.pop('seed', 0)
        if any(key in parameters for key in ('filename', 'checkpoint_path')) or (action_name == 'hash_tensor_stream' and isinstance(parameters.get('source'), str)):
            raise ValueError('Catalog replay accepts in-memory actions only; use OmniEngine.execute for external artifacts')
        output = cls(session, seed).execute(action_name, **parameters)
        return output['result']
