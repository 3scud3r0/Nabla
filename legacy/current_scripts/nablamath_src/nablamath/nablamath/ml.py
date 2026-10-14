from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple
import math
import random

from .autodiff import Var


@dataclass
class Neuron:
    n_inputs: int
    activation: str = "tanh"

    def __post_init__(self):
        scale = 1 / math.sqrt(max(1, self.n_inputs))
        self.w = [Var(random.uniform(-scale, scale), label=f"w{i}") for i in range(self.n_inputs)]
        self.b = Var(0.0, label="b")

    def __call__(self, x: List[Var | float]) -> Var:
        out = self.b
        for wi, xi in zip(self.w, x):
            xi = xi if isinstance(xi, Var) else Var(float(xi))
            out = out + wi * xi
        if self.activation == "tanh":
            return out.tanh()
        if self.activation == "relu":
            return out.relu()
        if self.activation == "linear":
            return out
        raise ValueError(f"activation desconhecida: {self.activation}")

    def parameters(self) -> List[Var]:
        return self.w + [self.b]


@dataclass
class Layer:
    n_inputs: int
    n_outputs: int
    activation: str = "tanh"

    def __post_init__(self):
        self.neurons = [Neuron(self.n_inputs, self.activation) for _ in range(self.n_outputs)]

    def __call__(self, x: List[Var | float]) -> List[Var]:
        return [n(x) for n in self.neurons]

    def parameters(self) -> List[Var]:
        return [p for n in self.neurons for p in n.parameters()]


class MLP:
    def __init__(self, sizes: List[int], activation: str = "tanh", output_activation: str = "linear"):
        self.layers = []
        for i in range(len(sizes) - 1):
            act = output_activation if i == len(sizes) - 2 else activation
            self.layers.append(Layer(sizes[i], sizes[i + 1], act))

    def __call__(self, x: List[float | Var]) -> List[Var]:
        out = x
        for layer in self.layers:
            out = layer(out)
        return out

    def parameters(self) -> List[Var]:
        return [p for layer in self.layers for p in layer.parameters()]

    def zero_grad(self):
        for p in self.parameters():
            p.grad = 0.0

    def parameter_count(self) -> int:
        return len(self.parameters())

    def train_regression(self, X: List[List[float]], y: List[float], lr: float = 0.03, epochs: int = 200) -> List[float]:
        history: List[float] = []
        for _ in range(epochs):
            preds = [self(x)[0] for x in X]
            losses = [(pred - yi) ** 2 for pred, yi in zip(preds, y)]
            loss = sum(losses[1:], losses[0]) * (1.0 / len(losses))
            self.zero_grad()
            loss.backward()
            for p in self.parameters():
                p.value -= lr * p.grad
            history.append(loss.value)
        return history
