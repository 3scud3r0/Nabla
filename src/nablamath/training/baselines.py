"""A real, deliberately small nearest-neighbor learning baseline, without ML dependencies."""
from dataclasses import dataclass
import hashlib
import json
import math
import re
from ..core.semantic_ir import canonical_json, fingerprint
from ..datasets.multimodal import INPUT_MODALITIES


def features(inputs, dimensions=128):
    vector = [0.0]*dimensions
    for modality in inputs['modalities']:
        text = canonical_json(modality['content'])
        for token in re.findall(r'[A-Za-z_]+|-?\d+(?:/\d+)?', text):
            digest = hashlib.sha256((modality['kind']+':'+token).encode()).digest()
            vector[int.from_bytes(digest[:4], 'big') % dimensions] += 1 if digest[4] & 1 else -1
    norm = math.sqrt(sum(v*v for v in vector)) or 1
    return tuple(v/norm for v in vector)


@dataclass(frozen=True)
class NearestNeighbor:
    rows: tuple
    modalities: tuple[str, ...]
    training_ids: tuple[str, ...]

    def predict(self, inputs):
        selected = {'modalities': [m for m in inputs['modalities'] if m['kind'] in self.modalities]}
        point = features(selected)
        best = min(self.rows, key=lambda row: (sum((a-b)**2 for a,b in zip(point,row[0])), row[2]))
        return json.loads(best[1])

    def to_data(self):
        return {'algorithm': 'hashed-nearest-neighbor-v1', 'rows': self.rows,
                'modalities': self.modalities, 'training_ids': self.training_ids}

    @classmethod
    def from_data(cls, data):
        if data['algorithm'] != 'hashed-nearest-neighbor-v1' or not data['rows']:
            raise ValueError('Modelo de baseline inválido')
        rows = tuple((tuple(row[0]), row[1], row[2]) for row in data['rows'])
        if any(len(row[0])!=128 or not all(math.isfinite(v) for v in row[0]) for row in rows):
            raise ValueError('Vetor de características inválido')
        return cls(rows, tuple(data['modalities']), tuple(data['training_ids']))

    @property
    def content_id(self):
        return fingerprint({'algorithm': 'hashed-nearest-neighbor-v1', 'rows': self.rows,
                            'modalities': self.modalities, 'training_ids': self.training_ids})


def fit_nearest_neighbor(samples, *, modalities=INPUT_MODALITIES):
    samples = tuple(samples)
    if not 1 <= len(samples) <= 10000:
        raise ValueError('Treino requer 1–10000 amostras')
    if any(s.record.to_data()['split'] != 'train' for s in samples):
        raise ValueError('Treino não pode consumir holdout')
    rows = tuple((features(s.inputs(modalities)), canonical_json(s.record.to_data()['trace']['candidate']),
                  s.record.task.content_id) for s in samples)
    return NearestNeighbor(rows, tuple(modalities), tuple(sorted(s.record.task.content_id for s in samples)))
