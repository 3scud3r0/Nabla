"""DataFrame/array bridges with explicit copy semantics.

The Nabla reference Tensor owns Python floats, so conversion to it always copies.
Zero-copy export is offered separately and fails when the source cannot share memory.
"""
from dataclasses import dataclass
from ..autodiff.tensor import Tensor


@dataclass(frozen=True)
class ArrayView:
    array: object
    owner: object
    copied: bool


def to_numpy(frame, *, allow_copy=False):
    import numpy as np
    module = type(frame).__module__.split('.')[0]
    if module == 'polars':
        try:
            array = frame.to_numpy(allow_copy=False)
            copied = False
        except RuntimeError:
            if not allow_copy:
                raise ValueError('Polars export requires a copy') from None
            array = frame.to_numpy(allow_copy=True)
            copied = True
    elif module == 'pandas':
        if frame.ndim != 2 or len(set(frame.dtypes)) != 1:
            if not allow_copy:
                raise ValueError('Zero-copy requires a homogeneous Pandas frame')
        array = frame.to_numpy(copy=False)
        shared = all(np.shares_memory(array, frame.iloc[:,i].to_numpy(copy=False)) for i in range(frame.shape[1]))
        if not shared and not allow_copy:
            raise ValueError('Pandas export requires a copy')
        copied = not shared
    else:
        raise TypeError('Expected a Pandas or Polars DataFrame')
    if array.dtype.kind not in 'iuf' or not np.isfinite(array).all():
        raise ValueError('A finite, real numeric frame is required')
    if not allow_copy:
        array = array.view()
        array.flags.writeable = False
    return ArrayView(array, frame, copied)


def to_tensor(frame, *, requires_grad=False):
    view = to_numpy(frame, allow_copy=True)
    return Tensor(view.array.tolist(), requires_grad=requires_grad)


def from_tensor(tensor, *, columns=None, library='pandas'):
    if not isinstance(tensor,Tensor) or tensor.ndim != 2:
        raise ValueError('Expected a rank-two Nabla Tensor')
    if columns is not None and (len(columns) != tensor.shape[1] or len(set(columns)) != len(columns)):
        raise ValueError('Columns must be unique and match tensor width')
    if library == 'pandas':
        import pandas as pd
        return pd.DataFrame(tensor.tolist(),columns=columns)
    if library == 'polars':
        import polars as pl
        return pl.DataFrame(tensor.tolist(),schema=columns,orient='row')
    raise ValueError('library must be pandas or polars')
