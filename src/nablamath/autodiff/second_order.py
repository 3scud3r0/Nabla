"""Dense second-order forward AD over the reference tensor backend.

Derivatives are propagated analytically, including broadcast reductions implicit
in a scalar loss. Storage is O(n² m) for n input and m intermediate elements;
this backend deliberately limits inputs to 64 elements. It is a correctness
reference, not an accelerator or a finite-difference Hessian approximation.
"""
from __future__ import annotations

from math import sin, cos
from typing import Callable
from .tensor import Tensor


class SecondOrderTensor:
    """Tensor value and its first and second derivatives by input coordinate."""

    def __init__(self, value: Tensor, gradient: tuple[Tensor, ...],
                 curvature: tuple[tuple[Tensor, ...], ...]):
        n = len(gradient)
        if len(curvature) != n or any(len(row) != n for row in curvature):
            raise ValueError("curvature must be square")
        if any(d.shape != value.shape for d in gradient):
            raise ValueError("gradient shape mismatch")
        if any(d.shape != value.shape for row in curvature for d in row):
            raise ValueError("curvature shape mismatch")
        self.value = value.detach()
        self.gradient = gradient
        self.curvature = curvature

    @property
    def shape(self):
        return self.value.shape

    @property
    def dimension(self):
        return len(self.gradient)

    @classmethod
    def variable(cls, value: Tensor):
        if not isinstance(value, Tensor) or not 1 <= value.size <= 64:
            raise ValueError("second-order inputs require 1..64 tensor elements")
        n = value.size
        gradient = tuple(Tensor._from_flat(
            [float(i == j) for j in range(n)], value.shape, False)
            for i in range(n))
        zero = Tensor._from_flat([0.0] * n, value.shape, False)
        return cls(value, gradient, tuple(tuple(zero for _ in range(n)) for _ in range(n)))

    def _constant(self, value):
        value = value.detach() if isinstance(value, Tensor) else Tensor(value)
        zero = Tensor._from_flat([0.0] * value.size, value.shape, False)
        return SecondOrderTensor(value, (zero,) * self.dimension,
                                 tuple((zero,) * self.dimension for _ in range(self.dimension)))

    def _coerce(self, value):
        result = value if isinstance(value, SecondOrderTensor) else self._constant(value)
        if result.dimension != self.dimension:
            raise ValueError("derivative dimensions differ")
        return result

    def __add__(self, other):
        b = self._coerce(other)
        return SecondOrderTensor(self.value + b.value,
            tuple(a + c for a, c in zip(self.gradient, b.gradient)),
            tuple(tuple(self.curvature[i][j] + b.curvature[i][j]
                        for j in range(self.dimension)) for i in range(self.dimension)))

    __radd__ = __add__

    def __neg__(self):
        return self * -1

    def __sub__(self, other):
        return self + -self._coerce(other)

    def __rsub__(self, other):
        return self._coerce(other) - self

    def __mul__(self, other):
        b = self._coerce(other)
        return SecondOrderTensor(self.value * b.value,
            tuple(self.gradient[i] * b.value + self.value * b.gradient[i]
                  for i in range(self.dimension)),
            tuple(tuple(self.curvature[i][j] * b.value
                        + self.gradient[i] * b.gradient[j]
                        + self.gradient[j] * b.gradient[i]
                        + self.value * b.curvature[i][j]
                        for j in range(self.dimension)) for i in range(self.dimension)))

    __rmul__ = __mul__

    def _unary(self, value: Tensor, first: Tensor, second: Tensor):
        return SecondOrderTensor(value,
            tuple(first * d for d in self.gradient),
            tuple(tuple(second * self.gradient[i] * self.gradient[j]
                        + first * self.curvature[i][j]
                        for j in range(self.dimension)) for i in range(self.dimension)))

    def __pow__(self, exponent):
        if type(exponent) is not int or not -32 <= exponent <= 32:
            raise ValueError("integer exponent must be in [-32,32]")
        if exponent == 0:
            # Follow the reference backend's exclusion of 0**0.
            return self._constant(self.value ** 0)
        value = self.value ** exponent
        def power(k):
            return self.value._unary(lambda x: x ** k, lambda x: 0.0, "jet_power")
        first = exponent * power(exponent - 1)
        second = (exponent * (exponent - 1) * power(exponent - 2)
                  if exponent != 1 else self._constant(0).value)
        return self._unary(value, first, second)

    def __truediv__(self, other):
        return self * (self._coerce(other) ** -1)

    def __rtruediv__(self, other):
        return self._coerce(other) / self

    def exp(self):
        value = self.value.exp()
        return self._unary(value, value, value)

    def log(self):
        return self._unary(self.value.log(), 1 / self.value, -1 / (self.value * self.value))

    def tanh(self):
        value = self.value.tanh()
        first = 1 - value * value
        return self._unary(value, first, -2 * value * first)

    def sin(self):
        value = self.value._unary(sin, cos, "sin")
        first = self.value._unary(cos, lambda x: -sin(x), "cos")
        return self._unary(value, first, -value)

    def cos(self):
        value = self.value._unary(cos, lambda x: -sin(x), "cos")
        first = -self.value._unary(sin, cos, "sin")
        return self._unary(value, first, -value)

    def _map(self, operation):
        return SecondOrderTensor(operation(self.value),
            tuple(operation(d) for d in self.gradient),
            tuple(tuple(operation(d) for d in row) for row in self.curvature))

    def sum(self, axis=None, keepdims=False):
        return self._map(lambda value: value.sum(axis, keepdims))

    def mean(self, axis=None, keepdims=False):
        return self._map(lambda value: value.mean(axis, keepdims))

    def reshape(self, *shape):
        return self._map(lambda value: value.reshape(*shape))

    def transpose(self, axes=None):
        return self._map(lambda value: value.transpose(axes))

    @property
    def T(self):
        return self.transpose()

    def __matmul__(self, other):
        b = self._coerce(other)
        return SecondOrderTensor(self.value @ b.value,
            tuple(self.gradient[i] @ b.value + self.value @ b.gradient[i]
                  for i in range(self.dimension)),
            tuple(tuple(self.curvature[i][j] @ b.value
                        + self.gradient[i] @ b.gradient[j]
                        + self.gradient[j] @ b.gradient[i]
                        + self.value @ b.curvature[i][j]
                        for j in range(self.dimension)) for i in range(self.dimension)))

    def __rmatmul__(self, other):
        return self._coerce(other) @ self

    def detach(self):
        """Stop all first and second derivative propagation at this value."""
        return self._constant(self.value)


def tensor_hessian(function: Callable[[SecondOrderTensor], SecondOrderTensor], value: Tensor):
    """Return scalar loss, flat gradient, and analytic dense Hessian.

    The callable must use SecondOrderTensor operations and return a scalar.
    No higher derivative graph is retained and no numerical differentiation is used.
    """
    variable = SecondOrderTensor.variable(value)
    result = function(variable)
    if not isinstance(result, SecondOrderTensor) or result.value.shape != ():
        raise ValueError("tensor_hessian requires a scalar SecondOrderTensor result")
    if result.dimension != variable.dimension:
        raise ValueError("Output derivative dimension differs from input coordinates")
    return (result.value.item(), tuple(d.item() for d in result.gradient),
            tuple(tuple(d.item() for d in row) for row in result.curvature))


__all__ = ["SecondOrderTensor", "tensor_hessian"]
