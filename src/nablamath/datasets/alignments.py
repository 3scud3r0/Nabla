"""Recompute modality contents, not just identity labels or claimed hashes."""
from .multimodal import MultimodalSample


def validate_alignment(sample):
    try:
        MultimodalSample(sample.payload_json if isinstance(sample, MultimodalSample) else __import__('json').dumps(sample))
        return True
    except (ValueError, KeyError, TypeError, ArithmeticError):
        return False
