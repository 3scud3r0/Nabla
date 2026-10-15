"""Explicitly consented caller-supplied inference; never opens network connections."""
from dataclasses import dataclass
import json
from copy import deepcopy
from ._bounded import bounded_tuple
from ..core.semantic_ir import fingerprint
from ..core.semantic_contracts import canonical_payload


@dataclass(frozen=True)
class Consent:
    owner: str
    provider: str
    model_version: str
    allowed_input_ids: tuple[str, ...]
    approved: bool = False

    def __post_init__(self):
        object.__setattr__(self, 'allowed_input_ids', bounded_tuple(self.allowed_input_ids,10000,label='consented inputs'))
        if any(not isinstance(x, str) or not x.strip() for x in (self.owner, self.provider, self.model_version)):
            raise ValueError('Owner, provider and pinned model required')
        if type(self.approved) is not bool or not self.allowed_input_ids or len(set(self.allowed_input_ids)) != len(self.allowed_input_ids):
            raise ValueError('Explicit approval and unique input scope required')
        if any(not isinstance(x, str) or len(x) != 64 or any(c not in '0123456789abcdef' for c in x) for x in self.allowed_input_ids):
            raise ValueError('Input digests required')


class FrontierAdapter:
    def __init__(self, consent, *, transport=None, enabled=False, max_calls=100):
        if not isinstance(consent, Consent) or type(enabled) is not bool or type(max_calls) is not int or not 1 <= max_calls <= 10000:
            raise ValueError('Invalid inference contract')
        self.consent, self.transport, self.enabled = consent, transport, enabled
        self.max_calls, self._receipts, self._calls = max_calls, [], 0

    @property
    def receipts(self):
        return deepcopy(self._receipts)

    @property
    def content_id(self):
        return fingerprint({'provider':self.consent.provider,'model_version':self.consent.model_version})

    def predict(self, inputs):
        # Canonicalization and allowlist checks precede any caller transport.
        payload = json.loads(canonical_payload(inputs))
        input_id = fingerprint(payload)
        if not self.enabled or not self.consent.approved:
            raise PermissionError('Inference disabled or consent absent')
        if input_id not in self.consent.allowed_input_ids:
            raise PermissionError('Input outside consent scope')
        if self._calls >= self.max_calls:
            raise RuntimeError('Inference budget exhausted')
        if not callable(self.transport):
            raise RuntimeError('No transport configured')
        row = {'input_id':input_id,'model_id':self.content_id,'status':'started'}
        self._calls += 1
        self._receipts.append(row)
        try:
            output = self.transport(payload, model_version=self.consent.model_version)
            encoded = canonical_payload(output)
            if len(encoded.encode()) > 1000000:
                raise ValueError('Oversize response')
            row.update(status='completed',output_id=fingerprint(output))
            return json.loads(encoded)
        except Exception:
            row['status'] = 'failed'
            raise
