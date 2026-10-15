"""Atomic single-blob persistence; validate the complete cycle before committing."""
from pathlib import Path

from ..core.scientific_artifact import ScientificArtifact
from ..store.blobs import BlobStore
from .scientific_cycle import replay_scientific_artifact


class ScientificArtifactStore:
    def __init__(self, root: Path):
        self.blobs = BlobStore(root)

    def put(self, artifact: ScientificArtifact) -> str:
        replay_scientific_artifact(artifact)
        return self.blobs.put(artifact.to_json().encode("utf-8"))

    def get(self, storage_id: str) -> ScientificArtifact:
        artifact = ScientificArtifact.from_json(self.blobs.get(storage_id).decode("utf-8"))
        replay_scientific_artifact(artifact)
        return artifact
