"""Capabilities for trusted, registered tools; no shell or network tool by default."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Permissions:
    allowed_tools: frozenset[str]
    max_calls: int = 8
    timeout_seconds: float = 10.0
    max_input_bytes: int = 65536
    max_output_bytes: int = 1048576

    def __post_init__(self):
        object.__setattr__(self, 'allowed_tools', frozenset(self.allowed_tools))
        if not self.allowed_tools or any(not isinstance(name, str) or not name for name in self.allowed_tools):
            raise ValueError('Capacidades explícitas obrigatórias')
        if type(self.max_calls) is not int or not 1 <= self.max_calls <= 100:
            raise ValueError('Limite de chamadas inválido')
        if not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 60:
            raise ValueError('Timeout inválido')
        if any(type(v) is not int or not 1 <= v <= 1048576 for v in (self.max_input_bytes, self.max_output_bytes)):
            raise ValueError('Limite de bytes inválido')
