from __future__ import annotations

"""Named tensor utilities.

The goal is educational reliability: every axis has a name, so shape mistakes
become explicit instead of silent.
"""

from dataclasses import dataclass
from typing import Iterable, Sequence, Dict, Tuple, List
import numpy as np


@dataclass(frozen=True)
class NamedTensor:
    data: np.ndarray
    axes: Tuple[str, ...]

    def __init__(self, data, axes: Sequence[str]):
        arr = np.asarray(data)
        object.__setattr__(self, "data", arr)
        object.__setattr__(self, "axes", tuple(axes))
        if arr.ndim != len(tuple(axes)):
            raise ValueError(f"Número de eixos ({len(tuple(axes))}) difere de ndim ({arr.ndim}).")
        if len(set(tuple(axes))) != len(tuple(axes)):
            raise ValueError("Eixos nomeados não podem se repetir.")

    @property
    def shape_dict(self) -> Dict[str, int]:
        return dict(zip(self.axes, self.data.shape))

    def explain_shape(self) -> str:
        return " × ".join(f"{axis}={size}" for axis, size in self.shape_dict.items())

    def align_to(self, axes: Sequence[str]) -> "NamedTensor":
        axes = tuple(axes)
        missing = [a for a in axes if a not in self.axes]
        if missing:
            raise ValueError(f"Eixos ausentes no tensor: {missing}")
        perm = [self.axes.index(a) for a in axes]
        return NamedTensor(np.transpose(self.data, perm), axes)

    def rename(self, **mapping: str) -> "NamedTensor":
        return NamedTensor(self.data, tuple(mapping.get(a, a) for a in self.axes))

    def sum(self, axis: str | Sequence[str] | None = None) -> "NamedTensor":
        if axis is None:
            return NamedTensor(np.asarray(self.data.sum()), ())
        axes = (axis,) if isinstance(axis, str) else tuple(axis)
        idx = tuple(self.axes.index(a) for a in axes)
        out = self.data.sum(axis=idx)
        out_axes = tuple(a for a in self.axes if a not in axes)
        return NamedTensor(out, out_axes)

    def mean(self, axis: str | Sequence[str] | None = None) -> "NamedTensor":
        if axis is None:
            return NamedTensor(np.asarray(self.data.mean()), ())
        axes = (axis,) if isinstance(axis, str) else tuple(axis)
        idx = tuple(self.axes.index(a) for a in axes)
        out = self.data.mean(axis=idx)
        out_axes = tuple(a for a in self.axes if a not in axes)
        return NamedTensor(out, out_axes)

    def __add__(self, other):
        other = ensure_named(other)
        a, b = align_pair(self, other)
        return NamedTensor(a.data + b.data, a.axes)

    def __sub__(self, other):
        other = ensure_named(other)
        a, b = align_pair(self, other)
        return NamedTensor(a.data - b.data, a.axes)

    def __mul__(self, other):
        other = ensure_named(other)
        a, b = align_pair(self, other)
        return NamedTensor(a.data * b.data, a.axes)

    def matmul(self, other: "NamedTensor", left_axis: str, right_axis: str, out_axis: str | None = None) -> "NamedTensor":
        if left_axis not in self.axes:
            raise ValueError(f"Eixo {left_axis!r} não existe no tensor esquerdo.")
        if right_axis not in other.axes:
            raise ValueError(f"Eixo {right_axis!r} não existe no tensor direito.")
        if self.shape_dict[left_axis] != other.shape_dict[right_axis]:
            raise ValueError("Dimensões incompatíveis para contração.")
        result = np.tensordot(self.data, other.data, axes=([self.axes.index(left_axis)], [other.axes.index(right_axis)]))
        axes = tuple(a for a in self.axes if a != left_axis) + tuple(a for a in other.axes if a != right_axis)
        if out_axis and len(axes) >= 1:
            axes = axes[:-1] + (out_axis,)
        return NamedTensor(result, axes)


def ensure_named(x) -> NamedTensor:
    if isinstance(x, NamedTensor):
        return x
    arr = np.asarray(x)
    return NamedTensor(arr, tuple(f"axis{i}" for i in range(arr.ndim)))


def align_pair(a: NamedTensor, b: NamedTensor) -> Tuple[NamedTensor, NamedTensor]:
    if set(a.axes) != set(b.axes):
        raise ValueError(f"Eixos incompatíveis: {a.axes} vs {b.axes}")
    return a, b.align_to(a.axes)
