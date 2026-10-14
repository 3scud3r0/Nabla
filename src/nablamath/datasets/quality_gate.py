"""Independent quality gate: integrity, semantics, provenance and contamination."""
import hashlib
from pathlib import Path
from .schema import ScientificRecord
from .semantic_fingerprint import semantic_fingerprint
from .split_policy import audit


def quality_gate(records, *, asset_root=None, require_partitions=True):
    errors, seen = [], set()
    records = tuple(records)
    if not records:
        errors.append('empty_dataset')
    for record in records:
        try:
            checked = ScientificRecord.from_data(record.to_data())
            key = semantic_fingerprint(checked)
            if key in seen:
                errors.append('duplicate_semantics:'+key)
            seen.add(key)
            for artifact in checked.to_data()['artifacts']:
                if asset_root is None:
                    raise ValueError('Artefatos exigem raiz de dados')
                root = Path(asset_root).resolve()
                path = root / artifact['path']
                if path.is_symlink() or not path.resolve().is_relative_to(root):
                    raise ValueError('Artefato fora da raiz')
                if path.stat().st_size > 32 * 1024 * 1024:
                    raise ValueError('Artefato excede 32 MiB')
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != artifact['sha256']:
                    raise ValueError('Hash de artefato divergente')
                from .multimodal import _modalities
                from ..core.semantic_ir import canonical_json
                expected = next(m['content'] for m in _modalities(checked, artifact['modality']=='simulation')
                                if m['kind']==artifact['modality'])
                rendered = expected if isinstance(expected, str) else canonical_json(expected)
                if raw.decode('utf-8').rstrip('\n') != rendered:
                    raise ValueError('Artefato não corresponde ao modelo matemático')
            if checked.to_data()['defects']:
                errors.append('declared_defects:'+checked.content_id)
        except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
            errors.append(str(exc))
    contamination = audit(records)
    if require_partitions and not contamination['clean']:
        errors.append('contamination_or_unassigned')
    return {'accepted': not errors, 'count': len(records), 'unique_semantics': len(seen),
            'errors': errors, 'contamination': contamination,
            'external_training_utility': 'not_established_by_this_gate'}
