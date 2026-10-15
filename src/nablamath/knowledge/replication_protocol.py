"""Immutable preregistration contracts; declarations do not authenticate people."""
from dataclasses import asdict, dataclass
from ..core.semantic_ir import fingerprint


@dataclass(frozen=True)
class ReplicationProtocol:
    claim_revision: str
    owner: str
    authors: tuple[str, ...]
    metric: str
    minimum: float
    maximum: float
    evidence_ids: tuple[str, ...]
    procedure: str
    schema_version: int = 1

    def __post_init__(self):
        import math
        object.__setattr__(self, 'authors', tuple(self.authors))
        object.__setattr__(self, 'evidence_ids', tuple(self.evidence_ids))
        if type(self.schema_version) is not int or self.schema_version != 1 or any(not isinstance(x, str) or not x.strip() for x in
                (self.claim_revision, self.owner, self.metric, self.procedure, *self.authors, *self.evidence_ids)):
            raise ValueError('Versioned protocol requires nonempty declarations')
        if not 1 <= len(self.authors) <= 1000 or not 1 <= len(self.evidence_ids) <= 10000 or len(set(self.authors)) != len(self.authors) or len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError('Authors and evidence required')
        if any(type(x) not in (float, int) or not math.isfinite(x) for x in (self.minimum, self.maximum)) or self.minimum > self.maximum:
            raise ValueError('Finite ordered acceptance interval required')

    @property
    def protocol_id(self):
        return fingerprint(asdict(self))

    def to_data(self):
        return {**asdict(self), 'protocol_id': self.protocol_id}

    @classmethod
    def from_data(cls, data):
        row = dict(data)
        identifier = row.pop('protocol_id')
        protocol = cls(**row)
        if identifier != protocol.protocol_id:
            raise ValueError('Protocol altered')
        return protocol
