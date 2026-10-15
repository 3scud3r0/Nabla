"""Explicit measured resource records; unavailable energy stays unavailable."""
from dataclasses import dataclass

from ..core.semantic_contracts import require_text
from ..core.semantic_ir import rational, fingerprint


@dataclass(frozen=True)
class ComputeRecord:
    hardware: str
    measurement_method: str
    elapsed_ns: int
    peak_memory_bytes: int
    energy_joules: str | None = None

    def __post_init__(self):
        require_text(self.hardware, "hardware")
        require_text(self.measurement_method, "measurement_method")
        if (type(self.elapsed_ns) is not int or not 1 <= self.elapsed_ns <= 10**20
                or type(self.peak_memory_bytes) is not int or not 0 <= self.peak_memory_bytes <= 2**60):
            raise ValueError("Bounded nonnegative measurements required")
        if self.energy_joules is not None:
            energy = rational(self.energy_joules)
            if energy < 0:
                raise ValueError("Energy must be nonnegative")
            object.__setattr__(self, "energy_joules", str(energy))

    def to_data(self):
        from dataclasses import asdict
        data = {"schema_version": 1, **asdict(self),
                "scope": "operator-supplied measurements; hardware and instruments not authenticated"}
        return {**data, "record_id": fingerprint(data)}
