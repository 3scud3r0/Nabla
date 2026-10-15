"""Truthful worker execution boundary: arbitrary code remains disabled.

A killable trusted-tool child process is useful resource control, not containment
of hostile Python. This module never starts a container, shell, generated script,
interpreter command, plugin or executable supplied by a task. A deployment that
needs hostile-code execution must provide and independently validate real
isolation in a separate implementation; setting a boolean here cannot enable it.
"""
from dataclasses import asdict, dataclass
from nablamath.agents.permissions import Permissions
from nablamath.core.semantic_ir import fingerprint


@dataclass(frozen=True)
class IsolationPolicy:
    max_calls: int = 8
    timeout_seconds: float = 10.0
    max_input_bytes: int = 65536
    max_output_bytes: int = 262144
    allow_network: bool = False
    allow_filesystem_write: bool = False
    allow_arbitrary_code: bool = False

    def __post_init__(self):
        for flag in (self.allow_network, self.allow_filesystem_write, self.allow_arbitrary_code):
            if type(flag) is not bool or flag:
                raise ValueError('External capabilities and arbitrary code are unavailable')
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float)):
            raise ValueError('Numeric worker deadline required')
        # Reuse the existing strict transport and process timeout contracts.
        self.permissions({'solve'})

    def permissions(self, tools):
        tools = frozenset(tools)
        if not tools or not tools <= {'solve', 'verify', 'simulate'}:
            raise PermissionError('Only reviewed scientific tools may cross this boundary')
        return Permissions(tools, self.max_calls, self.timeout_seconds,
                           self.max_input_bytes, self.max_output_bytes)

    def to_data(self):
        return asdict(self)

    @property
    def policy_id(self):
        return fingerprint(self.to_data())

    @classmethod
    def from_data(cls, data):
        if not isinstance(data, dict) or set(data) != set(cls.__dataclass_fields__):
            raise ValueError('Exact isolation policy fields required')
        return cls(**data)


def capabilities(policy):
    if not isinstance(policy, IsolationPolicy):
        raise ValueError('Typed worker policy required')
    return dict(policy_id=policy.policy_id, arbitrary_code=False, network=False,
                filesystem_write=False, os_sandbox=False,
                child_process='Trusted registered tools with wall-time and transport limits',
                boundary='Policy denies requested capabilities; trusted tool code is not OS-confined')


def run_untrusted(source, *, policy=None):
    """Always refuse, including empty programs and apparently harmless expressions."""
    raise PermissionError('Arbitrary code execution disabled; no verified hostile-code isolation backend')


def require_isolation(*, arbitrary_code=False, network=False, filesystem_write=False):
    """Fail closed before a caller might dispatch an unavailable capability."""
    flags = (arbitrary_code, network, filesystem_write)
    if any(type(flag) is not bool for flag in flags):
        raise ValueError('Explicit boolean capabilities required')
    if any(flags):
        raise PermissionError('Requested capability requires an external validated isolation backend')
    return True
