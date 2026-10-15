"""Immutable declared corpus manifests; rights declarations are not legal proof."""
from dataclasses import dataclass
import hashlib

from ..core.semantic_contracts import canonical_payload, load_json, require_fields, require_digest, require_text
from ..core.semantic_ir import fingerprint
from ..store.blobs import BlobStore


@dataclass(frozen=True)
class CorpusManifest:
    manifest_json: str

    def __post_init__(self):
        data = load_json(self.manifest_json)
        require_fields(data, {"schema_version", "name", "license_id", "provenance", "split", "records"})
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ValueError("Unsupported corpus version")
        for field in ("name", "license_id", "provenance"):
            require_text(data[field], field)
        if data["split"] not in ("train", "validation", "test"):
            raise ValueError("Explicit corpus split required")
        if not isinstance(data["records"], list) or not 1 <= len(data["records"]) <= 10000:
            raise ValueError("Corpus requires 1–10000 record digests")
        records = [require_digest(key) for key in data["records"]]
        if len(set(records)) != len(records):
            raise ValueError("Duplicate corpus record")
        data["records"] = sorted(records)
        object.__setattr__(self, "manifest_json", canonical_payload(data))

    @classmethod
    def create(cls, *, name, license_id, provenance, split, records):
        return cls(canonical_payload({"schema_version": 1, "name": name, "license_id": license_id,
                                     "provenance": provenance, "split": split, "records": records}))

    def to_data(self):
        return load_json(self.manifest_json)

    @property
    def content_id(self):
        return fingerprint(self.to_data())

    def verify_records(self, records: dict) -> bool:
        if not isinstance(records, dict) or set(records) != set(self.to_data()["records"]):
            return False
        return all(isinstance(raw, bytes) and hashlib.sha256(raw).hexdigest() == key for key, raw in records.items())


class CorpusRegistry:
    def __init__(self, root):
        self.blobs = BlobStore(root)

    def register(self, corpus: CorpusManifest):
        if not isinstance(corpus, CorpusManifest):
            raise ValueError("CorpusManifest required")
        return self.blobs.put(corpus.manifest_json.encode("utf-8"))

    def get(self, corpus_id):
        corpus = CorpusManifest(self.blobs.get(require_digest(corpus_id)).decode("utf-8"))
        if corpus.content_id != corpus_id:
            raise ValueError("Noncanonical corpus registry entry")
        return corpus
