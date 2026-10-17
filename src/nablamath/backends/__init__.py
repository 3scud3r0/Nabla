"""Optional hardware backends. No silent CPU fallback or exactness claims."""
from ..compiler.backends import BackendUnavailable

__all__ = ['BackendUnavailable']
