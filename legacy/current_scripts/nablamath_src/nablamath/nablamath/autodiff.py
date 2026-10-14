from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Set
import math


class Var:
    """Tiny reverse-mode autodiff scalar.

    This is the educational seed of NablaMath's differentiable engine.
    It supports scalar computation graphs and .backward().
    """

    def __init__(self, value: float, label: str = ""):
        self.value = float(value)
        self.grad = 0.0
        self.label = label
        self._prev: Set[Var] = set()
        self._backward: Callable[[], None] = lambda: None
        self._op = "leaf"

    def __repr__(self) -> str:
        return f"Var(value={self.value:.6g}, grad={self.grad:.6g}, label={self.label!r})"

    def __add__(self, other):
        other = other if isinstance(other, Var) else Var(other)
        out = Var(self.value + other.value)
        out._prev = {self, other}
        out._op = "+"
        def _backward():
            self.grad += out.grad
            other.grad += out.grad
        out._backward = _backward
        return out

    def __radd__(self, other):
        return self + other

    def __mul__(self, other):
        other = other if isinstance(other, Var) else Var(other)
        out = Var(self.value * other.value)
        out._prev = {self, other}
        out._op = "*"
        def _backward():
            self.grad += other.value * out.grad
            other.grad += self.value * out.grad
        out._backward = _backward
        return out

    def __rmul__(self, other):
        return self * other

    def __neg__(self):
        return self * -1.0

    def __sub__(self, other):
        return self + (-other if isinstance(other, Var) else -float(other))

    def __rsub__(self, other):
        return other + (-self)

    def __truediv__(self, other):
        return self * (other ** -1)

    def __rtruediv__(self, other):
        return other * (self ** -1)

    def __pow__(self, power: float):
        out = Var(self.value ** power)
        out._prev = {self}
        out._op = f"**{power}"
        def _backward():
            self.grad += power * (self.value ** (power - 1)) * out.grad
        out._backward = _backward
        return out

    def tanh(self):
        t = math.tanh(self.value)
        out = Var(t)
        out._prev = {self}
        out._op = "tanh"
        def _backward():
            self.grad += (1 - t * t) * out.grad
        out._backward = _backward
        return out

    def relu(self):
        out = Var(max(0.0, self.value))
        out._prev = {self}
        out._op = "relu"
        def _backward():
            self.grad += (1.0 if self.value > 0 else 0.0) * out.grad
        out._backward = _backward
        return out

    def exp(self):
        e = math.exp(self.value)
        out = Var(e)
        out._prev = {self}
        out._op = "exp"
        def _backward():
            self.grad += e * out.grad
        out._backward = _backward
        return out

    def log(self):
        out = Var(math.log(self.value))
        out._prev = {self}
        out._op = "log"
        def _backward():
            self.grad += (1.0 / self.value) * out.grad
        out._backward = _backward
        return out

    def backward(self):
        topo: List[Var] = []
        visited: Set[Var] = set()
        def build(v: Var):
            if v not in visited:
                visited.add(v)
                for child in v._prev:
                    build(child)
                topo.append(v)
        build(self)
        self.grad = 1.0
        for v in reversed(topo):
            v._backward()
