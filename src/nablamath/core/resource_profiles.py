"""Cooperative resource admission, not OS isolation or measurement of actual usage."""
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from pathlib import Path
from threading import Lock

from .semantic_contracts import load_json, require_fields, require_text


@dataclass(frozen=True)
class ResourceProfile:
    name: str
    cpu_slots: int
    memory_bytes: int
    gpu_memory_bytes: int
    max_tasks: int
    max_task_seconds: int
    distributed: bool = False

    def __post_init__(self):
        require_text(self.name, "profile", limit=128)
        limits = {"cpu_slots": (1, 4096), "memory_bytes": (1, 2**50),
                  "gpu_memory_bytes": (0, 2**50), "max_tasks": (1, 4096),
                  "max_task_seconds": (1, 604800)}
        for name, (lower, upper) in limits.items():
            value = getattr(self, name)
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError(f"Invalid resource limit: {name}")
        if type(self.distributed) is not bool:
            raise ValueError("Explicit distributed capability required")

    def to_data(self):
        return {"schema_version": 1, **asdict(self)}

    @classmethod
    def load(cls, path: Path):
        # JSON is a YAML subset, allowing profiles without a YAML dependency.
        with Path(path).open("rb") as stream:
            raw = stream.read(16385)
        if len(raw) > 16384:
            raise ValueError("Resource profile too large")
        data = load_json(raw.decode("utf-8"))
        require_fields(data, {"schema_version", "name", "cpu_slots", "memory_bytes", "gpu_memory_bytes",
                              "max_tasks", "max_task_seconds", "distributed"})
        version = data.pop("schema_version")
        if type(version) is not int or version != 1:
            raise ValueError("Unsupported profile version")
        return cls(**data)


class ResourceReservations:
    def __init__(self, profile: ResourceProfile):
        if not isinstance(profile, ResourceProfile):
            raise ValueError("ResourceProfile required")
        self.profile = profile
        self._used = [0, 0, 0, 0]
        self._lock = Lock()

    @property
    def used(self):
        with self._lock:
            return tuple(self._used)

    @contextmanager
    def reserve(self, *, cpu_slots=1, memory_bytes=1, gpu_memory_bytes=0, seconds=1, distributed=False):
        request = [cpu_slots, memory_bytes, gpu_memory_bytes, 1]
        if (any(type(value) is not int or value < 0 for value in request)
                or cpu_slots < 1 or memory_bytes < 1 or type(seconds) is not int
                or not 1 <= seconds <= self.profile.max_task_seconds
                or type(distributed) is not bool or distributed and not self.profile.distributed):
            raise ValueError("Invalid or disallowed resource request")
        ceilings = [self.profile.cpu_slots, self.profile.memory_bytes, self.profile.gpu_memory_bytes, self.profile.max_tasks]
        with self._lock:
            if any(used+value > limit for used, value, limit in zip(self._used, request, ceilings)):
                raise ValueError("Resource reservation exceeds profile")
            self._used = [used+value for used, value in zip(self._used, request)]
        try:
            yield
        finally:
            with self._lock:
                self._used = [used-value for used, value in zip(self._used, request)]
