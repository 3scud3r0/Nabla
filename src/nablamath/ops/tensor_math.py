"""Bounded N-dimensional tensors using the dependency-free reference engine."""
from math import prod
from ..autodiff.tensor import Tensor, NamedTensor, _broadcast_shape


def tensor_operation(kind, values, *, other=None, axis=None, shape=None, axes=None):
    tensor = Tensor(values)
    if tensor.size > 10000:
        raise ValueError('Tensor exceeds 10000 elements')
    if kind in {'add', 'multiply', 'matmul'}:
        if other is None:
            raise ValueError('A second tensor is required')
        right = Tensor(other)
        if right.size > 10000:
            raise ValueError('Tensor exceeds 10000 elements')
        if kind != 'matmul' and prod(_broadcast_shape(tensor.shape,right.shape)) > 10000:
            raise ValueError('Broadcast result exceeds 10000 elements')
        if kind == 'matmul' and (tensor.ndim != 2 or right.ndim != 2
                                or tensor.shape[0]*tensor.shape[1]*right.shape[1] > 1000000):
            raise ValueError('Matrix multiplication exceeds budget or rank')
        output = {'add': lambda: tensor + right, 'multiply': lambda: tensor * right,
                  'matmul': lambda: tensor @ right}[kind]()
    elif kind in {'sum', 'mean'}:
        output = getattr(tensor, kind)(axis=axis)
    elif kind == 'reshape':
        if shape is None:
            raise ValueError('shape is required')
        output = tensor.reshape(shape)
    elif kind == 'transpose':
        output = tensor.transpose(axes)
    else:
        raise ValueError('Unknown tensor operation')
    return {'values': output.tolist(), 'shape': list(output.shape), 'arithmetic': 'float64_reference'}


__all__ = ['Tensor', 'NamedTensor', 'tensor_operation']
