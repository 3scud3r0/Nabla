from __future__ import annotations

"""Small NumPy-based reverse-mode tensor autodiff.

This is not a replacement for PyTorch/JAX. It is an educational tensor-autodiff
core with broadcasting-aware addition/multiplication, matrix multiplication,
ReLU, tanh, exp, log, mean and sum.
"""

from typing import Callable, Set, List
import numpy as np


def _unbroadcast(grad: np.ndarray, shape: tuple[int, ...]) -> np.ndarray:
    while grad.ndim > len(shape):
        grad = grad.sum(axis=0)
    for i, size in enumerate(shape):
        if size == 1:
            grad = grad.sum(axis=i, keepdims=True)
    return grad


class TensorVar:
    def __init__(self, data, label: str = "", requires_grad: bool = True):
        self.data = np.asarray(data, dtype=float)
        self.grad = np.zeros_like(self.data, dtype=float)
        self.label = label
        self.requires_grad = requires_grad
        self._prev: Set[TensorVar] = set()
        self._backward: Callable[[], None] = lambda: None
        self._op = "leaf"

    def __repr__(self):
        return f"TensorVar(shape={self.data.shape}, label={self.label!r})"

    def __add__(self, other):
        other = other if isinstance(other, TensorVar) else TensorVar(other, requires_grad=False)
        out = TensorVar(self.data + other.data)
        out._prev = {self, other}
        out._op = "+"
        def _backward():
            if self.requires_grad:
                self.grad += _unbroadcast(out.grad, self.data.shape)
            if other.requires_grad:
                other.grad += _unbroadcast(out.grad, other.data.shape)
        out._backward = _backward
        return out

    __radd__ = __add__

    def __neg__(self):
        return self * -1.0

    def __sub__(self, other):
        return self + (-other if isinstance(other, TensorVar) else -float(other))

    def __rsub__(self, other):
        return other + (-self)

    def __mul__(self, other):
        other = other if isinstance(other, TensorVar) else TensorVar(other, requires_grad=False)
        out = TensorVar(self.data * other.data)
        out._prev = {self, other}
        out._op = "*"
        def _backward():
            if self.requires_grad:
                self.grad += _unbroadcast(other.data * out.grad, self.data.shape)
            if other.requires_grad:
                other.grad += _unbroadcast(self.data * out.grad, other.data.shape)
        out._backward = _backward
        return out

    __rmul__ = __mul__

    def __truediv__(self, other):
        return self * (other ** -1)

    def __rtruediv__(self, other):
        return other * (self ** -1)

    def __pow__(self, power: float):
        out = TensorVar(self.data ** power)
        out._prev = {self}
        out._op = f"**{power}"
        def _backward():
            if self.requires_grad:
                self.grad += power * (self.data ** (power - 1)) * out.grad
        out._backward = _backward
        return out

    def matmul(self, other: "TensorVar"):
        other = other if isinstance(other, TensorVar) else TensorVar(other, requires_grad=False)
        out = TensorVar(self.data @ other.data)
        out._prev = {self, other}
        out._op = "matmul"
        def _backward():
            if self.requires_grad:
                self.grad += out.grad @ other.data.T
            if other.requires_grad:
                other.grad += self.data.T @ out.grad
        out._backward = _backward
        return out

    def relu(self):
        out = TensorVar(np.maximum(0, self.data))
        out._prev = {self}
        out._op = "relu"
        def _backward():
            if self.requires_grad:
                self.grad += (self.data > 0) * out.grad
        out._backward = _backward
        return out

    def tanh(self):
        t = np.tanh(self.data)
        out = TensorVar(t)
        out._prev = {self}
        out._op = "tanh"
        def _backward():
            if self.requires_grad:
                self.grad += (1 - t*t) * out.grad
        out._backward = _backward
        return out

    def exp(self):
        e = np.exp(self.data)
        out = TensorVar(e)
        out._prev = {self}
        out._op = "exp"
        def _backward():
            if self.requires_grad:
                self.grad += e * out.grad
        out._backward = _backward
        return out

    def log(self):
        out = TensorVar(np.log(self.data))
        out._prev = {self}
        out._op = "log"
        def _backward():
            if self.requires_grad:
                self.grad += (1 / self.data) * out.grad
        out._backward = _backward
        return out

    def sum(self):
        out = TensorVar(np.asarray(self.data.sum()))
        out._prev = {self}
        out._op = "sum"
        def _backward():
            if self.requires_grad:
                self.grad += np.ones_like(self.data) * out.grad
        out._backward = _backward
        return out

    def mean(self):
        return self.sum() * (1.0 / self.data.size)

    def zero_grad(self):
        self.grad = np.zeros_like(self.data)

    def backward(self):
        topo: List[TensorVar] = []
        visited: Set[TensorVar] = set()
        def build(v: TensorVar):
            if v not in visited:
                visited.add(v)
                for child in v._prev:
                    build(child)
                topo.append(v)
        build(self)
        self.grad = np.ones_like(self.data)
        for v in reversed(topo):
            v._backward()
