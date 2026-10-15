"""Evidence requirements by claim kind, without promoting declarations to truth."""
from dataclasses import dataclass

from ..core.semantic_contracts import require_digest, require_text

REQUIRED = {
    "computed": frozenset({"request", "result", "replay"}),
    "numerical": frozenset({"request", "result", "error_bound", "reference"}),
    "formal": frozenset({"statement", "assumptions", "kernel", "certificate"}),
    "empirical": frozenset({"observations", "protocol", "uncertainty", "calibration"}),
}


@dataclass(frozen=True)
class EvidenceRequirement:
    kind: str
    statement: str
    links: tuple[tuple[str, str], ...]

    def __post_init__(self):
        if not isinstance(self.kind, str) or self.kind not in REQUIRED:
            raise ValueError("Unsupported evidence kind")
        require_text(self.statement, "statement")
        if not isinstance(self.links, (tuple, list)) or len(self.links) > 32:
            raise ValueError("Invalid evidence links")
        links = []
        for pair in self.links:
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise ValueError("Evidence links require role and digest")
            role, digest = pair
            links.append((require_text(role, "role", limit=128), require_digest(digest)))
        if len(dict(links)) != len(links) or not REQUIRED[self.kind] <= dict(links).keys():
            raise ValueError("Missing or duplicate evidence role")
        object.__setattr__(self, "links", tuple(sorted(links)))

    def validate_references(self, available):
        if any(digest not in available for _, digest in self.links):
            raise ValueError("Evidence refers to unavailable content")

    def to_data(self):
        return {"kind": self.kind, "statement": self.statement, "links": dict(self.links),
                "scope": "declared requirements only; content requires independent verification"}
