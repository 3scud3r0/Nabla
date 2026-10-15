"""Identified host/device observations; absent sensors remain null, never zero."""
from __future__ import annotations
import csv
import io
import math
import os
import platform
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass


def hardware_profile():
    result = {"schema_version": 1, "system": platform.system(),
              "machine": platform.machine(), "processor": platform.processor(),
              "python": platform.python_version(), "logical_cpus": os.cpu_count(),
              "cuda_devices": [], "gpu_probe_error": None}
    executable = shutil.which("nvidia-smi")
    if executable is None:
        result["gpu_probe_error"] = "nvidia-smi unavailable"
        return result
    try:
        output = subprocess.run(
            [executable, "--query-gpu=uuid,name,driver_version,memory.total,power.draw",
             "--format=csv,noheader,nounits"], capture_output=True, text=True,
            timeout=5, check=True)
        for row in csv.reader(io.StringIO(output.stdout)):
            if len(row) != 5:
                raise ValueError("Unexpected GPU telemetry columns")
            uuid, name, driver, memory, watts = [s.strip() for s in row]
            def sensor(value):
                try:
                    number = float(value)
                    return number if math.isfinite(number) and number >= 0 else None
                except ValueError:
                    return None
            result["cuda_devices"].append({"uuid": uuid, "name": name,
                "driver": driver, "memory_total_mib": sensor(memory),
                "power_snapshot_watts": sensor(watts)})
    except (subprocess.SubprocessError, OSError, ValueError) as exc:
        result["gpu_probe_error"] = type(exc).__name__
    return result


@dataclass(frozen=True)
class ProfileReceipt:
    backend: str
    repetitions: int
    seconds: tuple[float, ...]
    hardware: dict
    energy_joules: None = None
    peak_vram_bytes: None = None
    limitation: str = "No integrated energy or peak VRAM sensor; wall time includes synchronization"

    def to_data(self):
        return asdict(self)


def profile_operation(operation, *, backend, repetitions=5, synchronize=None):
    if not isinstance(backend, str) or not backend.strip():
        raise ValueError("Backend identity required")
    if type(repetitions) is not int or not 1 <= repetitions <= 100:
        raise ValueError("Repetitions must be in [1,100]")
    times = []
    for _ in range(repetitions):
        if synchronize:
            synchronize()
        start = time.perf_counter()
        operation()
        if synchronize:
            synchronize()
        times.append(time.perf_counter() - start)
    return ProfileReceipt(backend, repetitions, tuple(times), hardware_profile())
