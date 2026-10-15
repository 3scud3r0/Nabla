"""Conversão explícita de arrays NumPy para listas JSON serializáveis."""

from __future__ import annotations

from typing import Any


def as_array(values: Any):
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Instale o extra 'viz' para usar o adaptador NumPy") from exc
    array = np.asarray(values)
    if not (array.dtype.kind in 'iuf' and np.isfinite(array).all()):
        raise ValueError("O adaptador aceita somente números finitos")
    return array


def to_data(values: Any) -> dict:
    array = as_array(values)
    return {"shape": list(array.shape), "dtype": str(array.dtype), "values": array.tolist(),
            "backend": "numpy"}


__all__ = ["as_array", "to_data", "from_data"]


def from_data(payload):
    """Reconstruct a bounded real array, checking the declared wire shape/dtype."""
    import math
    if (not isinstance(payload, dict)
            or set(payload) != {'shape', 'dtype', 'values', 'backend'}
            or payload['backend'] != 'numpy'):
        raise ValueError('Invalid NumPy wire envelope')
    shape = payload['shape']
    if (not isinstance(shape, list) or len(shape) > 8
            or any(type(size) is not int or size < 0 for size in shape)
            or math.prod(shape) > 1_000_000):
        raise ValueError('Array shape outside interchange budget')
    import numpy as np
    try:
        dtype = np.dtype(payload['dtype'])
    except (TypeError, ValueError) as exc:
        raise ValueError('Invalid array dtype') from exc
    if dtype.kind not in 'iuf' or dtype.itemsize > 8:
        raise ValueError('Only bounded real numeric dtypes supported')
    array = as_array(payload['values'])
    if list(array.shape) != shape:
        raise ValueError('Declared shape differs from payload')
    converted = array.astype(dtype)
    if not np.isfinite(converted).all() or not np.array_equal(array, converted):
        raise ValueError('Lossy numeric array conversion')
    return converted
