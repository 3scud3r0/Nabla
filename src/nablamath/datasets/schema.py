"""Immutable v3 records with independently replayable mathematics and provenance."""
from dataclasses import dataclass
import json
import re
from ..core.semantic_ir import canonical_json, fingerprint
from ..forge.task_spec import TaskSpec
from ..verify.trace import build_trace, VerificationTrace, VERIFIER_VERSION

SPLITS = {'unassigned', 'train', 'validation', 'test'}
MODALITIES = {'text', 'equation', 'diagram', 'simulation', 'proof', 'reasoning'}


@dataclass(frozen=True)
class ScientificRecord:
    payload_json: str

    def __post_init__(self):
        data = json.loads(self.payload_json)
        required = {'schema_version', 'task', 'trace', 'attempts', 'artifacts', 'license_id',
                    'provenance', 'scope', 'limitations', 'difficulty', 'defects', 'split',
                    'synthetic', 'origin', 'verifier_version', 'formal_certificates'}
        if set(data) != required or data['schema_version'] != 3:
            raise ValueError('Contrato de dataset v3 inválido')
        if len(self.payload_json.encode()) > 4*1024*1024:
            raise ValueError('Registro excede 4 MiB')
        task = TaskSpec.from_data(data['task'])
        trace = VerificationTrace.from_data(data['trace']).to_data()
        if trace['task_id'] != task.content_id or not trace['verification']['valid']:
            raise ValueError('Solução não verificada')
        for attempt in data['attempts']:
            if VerificationTrace.from_data(attempt).to_data()['task_id'] != task.content_id:
                raise ValueError('Tentativa pertence a outro problema')
        for name in ('license_id', 'provenance', 'scope', 'limitations'):
            if not isinstance(data[name], str) or not data[name].strip():
                raise ValueError(f'Metadado obrigatório: {name}')
        if (data['verifier_version'] != VERIFIER_VERSION or data['split'] not in SPLITS
                or type(data['synthetic']) is not bool or data['origin'] not in {'generated', 'external'}):
            raise ValueError('Versão, partição ou origem inválida')
        if data['origin']=='generated' and data['synthetic'] is not True:
            raise ValueError('Geração deve ser marcada como sintética')
        if not isinstance(data['defects'], list) or any(not isinstance(d, str) for d in data['defects']):
            raise ValueError('Defeitos devem ser listados')
        if (not isinstance(data['difficulty'], dict) or data['difficulty'].get('label') not in
                {'uncalibrated', 'easy', 'medium', 'hard'}):
            raise ValueError('Dificuldade explícita obrigatória')
        for artifact in data['artifacts']:
            if set(artifact) != {'path', 'sha256', 'modality', 'task_id'}:
                raise ValueError('Contrato de artefato inválido')
            path = artifact['path']
            if (not re.fullmatch(r'[A-Za-z0-9_./-]+', path) or path.startswith('/')
                    or any(p in {'', '.', '..'} for p in path.split('/'))
                    or not re.fullmatch(r'[a-f0-9]{64}', artifact['sha256'])
                    or artifact['modality'] not in MODALITIES or artifact['task_id'] != task.content_id):
                raise ValueError('Artefato sem vínculo ou caminho inválido')
        from ..verify.certificate import verify_formal_certificate
        for certificate in data['formal_certificates']:
            if not verify_formal_certificate(certificate):
                raise ValueError('Certificado formal rejeitado')
        object.__setattr__(self, 'payload_json', canonical_json(data))

    @property
    def content_id(self):
        return fingerprint(self.to_data())

    @property
    def task(self):
        return TaskSpec.from_data(self.to_data()['task'])

    def to_data(self):
        return json.loads(self.payload_json)

    @classmethod
    def from_data(cls, data):
        return cls(canonical_json(data))

    def with_split(self, split):
        return self.from_data({**self.to_data(), 'split': split})


def make_record(task, candidate, *, license_id, provenance, scope, limitations,
                difficulty=None, defects=(), attempts=(), artifacts=(), split='unassigned',
                synthetic=True, origin='generated', formal_certificates=()):
    return ScientificRecord.from_data({
        'schema_version': 3, 'task': task.to_data(), 'trace': build_trace(task, candidate).to_data(),
        'attempts': [build_trace(task, c).to_data() for c in attempts], 'artifacts': list(artifacts),
        'license_id': license_id, 'provenance': provenance, 'scope': scope, 'limitations': limitations,
        'difficulty': difficulty or {'label': 'uncalibrated'}, 'defects': list(defects), 'split': split,
        'synthetic': synthetic, 'origin': origin, 'verifier_version': VERIFIER_VERSION,
        'formal_certificates': list(formal_certificates)})
