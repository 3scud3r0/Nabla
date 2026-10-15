"""Atomic dataset bundles: all assets, partitions, card and integrity manifest."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from ..core.semantic_ir import canonical_json
from ..datasets.quality_gate import quality_gate
from ..datasets.model_card import model_card
from .jsonl import write_jsonl, read_jsonl


def export_bundle(records, destination, *, asset_root=None, parquet=False, evaluations=()):
    records, destination = tuple(records), Path(destination)
    quality = quality_gate(records, asset_root=asset_root)
    if not quality['accepted']:
        raise ValueError('Dataset rejeitado: '+str(quality['errors']))
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.dataset-', dir=destination.parent))
    try:
        write_jsonl(records, stage/'records.jsonl')
        for split in ('train', 'validation', 'test'):
            rows = [r for r in records if r.to_data()['split'] == split]
            (stage/f'{split}.jsonl').write_text(''.join(canonical_json(r.to_data())+'\n' for r in rows), encoding='utf-8')
        for record in records:
            for artifact in record.to_data()['artifacts']:
                target = stage/'assets'/artifact['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(Path(asset_root)/artifact['path'], target)
        if parquet:
            from .parquet import write_parquet
            write_parquet(records, stage/'records.parquet')
        (stage/'card.json').write_text(canonical_json(model_card(records, quality, evaluations=evaluations))+'\n', encoding='utf-8')
        manifest = {'schema_version': 1, 'files': {p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                                for p in sorted(stage.rglob('*')) if p.is_file()}}
        (stage/'manifest.json').write_text(canonical_json(manifest)+'\n', encoding='utf-8')
        if not verify_bundle(stage):
            raise ValueError('Bundle não reproduzível')
        stage.rename(destination)
        return manifest
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def verify_bundle(root):
    try:
        root = Path(root)
        if any(p.is_symlink() for p in root.rglob('*')) or (root/'manifest.json').stat().st_size > 1024*1024:
            return False
        manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        if manifest.get('kind') == 'research_dataset_bundle':
            from .research_bundle import verify_research_bundle
            return verify_research_bundle(root)
        actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p != root/'manifest.json'}
        if manifest['schema_version'] != 1 or set(manifest['files']) != actual:
            return False
        for name, digest in manifest['files'].items():
            path = root/name
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                return False
            if path.stat().st_size > 64*1024*1024:
                return False
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                return False
        records = read_jsonl(root/'records.jsonl')
        expected = {'records.jsonl','train.jsonl','validation.jsonl','test.jsonl','card.json'}
        expected.update('assets/'+a['path'] for r in records for a in r.to_data()['artifacts'])
        if (root/'records.parquet').exists():
            expected.add('records.parquet')
        if expected != actual:
            return False
        quality = quality_gate(records, asset_root=root/'assets')
        if not quality['accepted']:
            return False
        card = json.loads((root/'card.json').read_text(encoding='utf-8'))
        if card != model_card(records, quality, evaluations=card['evaluations']):
            return False
        for split in ('train', 'validation', 'test'):
            expected = ''.join(canonical_json(r.to_data())+'\n' for r in records if r.to_data()['split'] == split)
            if (root/f'{split}.jsonl').read_text(encoding='utf-8') != expected:
                return False
        if (root/'records.parquet').exists():
            from .parquet import read_parquet
            if [r.to_data() for r in read_parquet(root/'records.parquet')] != [r.to_data() for r in records]:
                return False
        return True
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        return False
