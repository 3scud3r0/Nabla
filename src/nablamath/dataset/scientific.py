"""Verified scientific records, semantic deduplication and conservative family splits."""
from fractions import Fraction
from ..core.semantic_ir import ScientificTask, fingerprint
from ..verify.certificate import verify


def family_key(task: ScientificTask) -> str:
    # Keep every coefficient/seed variant of a template in the same partition.
    size = len(task.coefficients) if task.family == 'polynomial_integral' else len(task.rhs)
    return f'{task.family}:size={size}'


def split_for_task(task: ScientificTask) -> str:
    bucket = int(fingerprint({'split_policy': 'template-v1', 'family': family_key(task)})[:8], 16) % 100
    return 'train' if bucket < 80 else 'validation' if bucket < 90 else 'test'


def make_record(task: ScientificTask, solution: tuple[Fraction, ...], *, license_id: str,
                provenance: str, seed: int) -> dict:
    if not license_id.strip() or not provenance.strip():
        raise ValueError('Licenca e procedencia obrigatorias')
    verification = verify(task, solution)
    if not verification.valid:
        raise ValueError('Candidato rejeitado pelo verificador independente')
    return {'schema_version': 1, 'task_id': task.content_id, 'task': task.to_data(),
            'solution': [str(v) for v in solution], 'verification': verification.to_data(),
            'license_id': license_id, 'provenance': provenance, 'synthetic': True,
            'generator': {'name': 'inverse-v1', 'seed': seed},
            'family_key': family_key(task), 'split': split_for_task(task),
            'difficulty': {'status': 'uncalibrated', 'external_benchmark': None},
            'limitations': 'Racionais exatos; sem prova formal ou ganho de treino demonstrado.'}


def validate_record(record: dict) -> bool:
    """Recheck mathematics and metadata; never trust a stored valid=true flag."""
    try:
        task = ScientificTask.from_data(record['task'])
        if (record['schema_version'] != 1 or record['task_id'] != task.content_id
                or record['family_key'] != family_key(task) or record['split'] != split_for_task(task)
                or record['synthetic'] is not True or not isinstance(record['license_id'], str)
                or not isinstance(record['provenance'], str) or not record['license_id'].strip()
                or not record['provenance'].strip()):
            return False
        generator = record['generator']
        if generator['name'] != 'inverse-v1' or type(generator['seed']) is not int:
            return False
        from ..forge.reverse_builder import generate
        size = len(task.coefficients) if task.family == 'polynomial_integral' else len(task.rhs)
        if generate(task.family, generator['seed'], size).task != task:
            return False
        if record['difficulty'] != {'status': 'uncalibrated', 'external_benchmark': None}:
            return False
        if not isinstance(record['solution'], list) or len(record['solution']) > 33:
            return False
        verification = verify(task, tuple(record['solution']))
        # JSON round-trip normalizes tuples in the dataclass report.
        from ..core.semantic_ir import canonical_json
        return verification.valid and canonical_json(record['verification']) == canonical_json(verification.to_data())
    except (KeyError, ValueError, TypeError, ArithmeticError):
        return False


def audit_contamination(partitions: dict[str, list[dict]]) -> dict:
    """Report exact-task and template overlap; this does not audit external corpora."""
    tasks: dict[str, set[str]] = {}
    families: dict[str, set[str]] = {}
    misassigned = []
    for split, records in partitions.items():
        if split not in {'train', 'validation', 'test'}:
            raise ValueError('Particao desconhecida')
        for record in records:
            if not validate_record(record):
                raise ValueError('Registro invalido na auditoria')
            if record['split'] != split:
                misassigned.append(record['task_id'])
            tasks.setdefault(record['task_id'], set()).add(split)
            families.setdefault(record['family_key'], set()).add(split)
    overlaps = {kind: sorted(key for key, splits in index.items() if len(splits) > 1)
                for kind, index in [('tasks', tasks), ('families', families)]}
    return {'clean': not any(overlaps.values()) and not misassigned, 'overlaps': overlaps,
            'misassigned': sorted(misassigned), 'scope': 'local_exact_tasks_and_templates'}
