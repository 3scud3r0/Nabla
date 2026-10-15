"""Atomic mixed research dataset releases, shared cards, gates and Hub preparation."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from ..core.semantic_ir import canonical_json
from ..datasets.store import RecordStore
from ..datasets.research_record import ResearchRecord
from ..datasets.serializer import iter_load,write_atomic


def _card(records,*,require_training_splits,allow_observations):
    rows=[r.to_data() for r in records]
    if not rows or len(rows)>10000:raise ValueError('Release requer 1–10000 registros')
    splits=Counter(r['split'] for r in rows)
    if require_training_splits and (set(splits)!={'train','validation','test'}):raise ValueError('Treino requer três partições e nenhum registro não atribuído')
    observations=sum(isinstance(r,ResearchRecord) and r.to_data()['kind']=='observation' for r in records)
    if observations and not allow_observations:raise ValueError('Observações exigem perfil explícito de integridade, sem validação física')
    computational=0
    for r in records:
        if isinstance(r,ResearchRecord):
            verification=r.verification()
            if not verification['valid']:raise ValueError('Replay de artefato falhou')
            computational+=r.to_data()['kind']!='observation'
        else:computational+=1
    return {'schema_version':1,'profile':'mixed-research-v1','count':len(rows),
            'licenses':sorted({r['license_id'] for r in rows}),'sources':sorted({r['provenance'] for r in rows}),
            'scopes':sorted({r['scope'] for r in rows}),'limitations':sorted({r['limitations'] for r in rows}),
            'record_profiles':dict(sorted(Counter(r.get('kind','forge_task') for r in rows).items())),
            'verifier_versions':sorted({r['verifier_version'] for r in rows}),'splits':dict(sorted(splits.items())),
            'synthetic_count':sum(r['synthetic'] for r in rows),'computationally_replayed':computational,
            'observational_integrity_only':observations,'require_training_splits':require_training_splits,
            'allow_observations':allow_observations,'training_gain':'not_established','external_provenance_authenticated':False}


def export_research_bundle(records,destination,*,parquet=True,require_training_splits=False,allow_observations=False):
    if any(type(v) is not bool for v in (parquet,require_training_splits,allow_observations)):raise ValueError('Perfil de exportação deve ser explícito')
    target=Path(destination)
    if target.exists():raise FileExistsError(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.research-dataset-',dir=target.parent))
    try:
        store=RecordStore(stage/'staging.sqlite3');store.ingest(records,batch_id='release')
        rows=tuple(store.records());card=_card(rows,require_training_splits=require_training_splits,allow_observations=allow_observations)
        store.export_jsonl(stage/'records.jsonl')
        for split in ('train','validation','test','unassigned'):
            selected=[r for r in rows if r.to_data()['split']==split]
            if selected:write_atomic(selected,stage/f'{split}.jsonl')
            else:(stage/f'{split}.jsonl').write_bytes(b'')
        if parquet:
            from .parquet import write_parquet_stream
            write_parquet_stream(store.records(),stage/'records.parquet')
        (stage/'staging.sqlite3').unlink()
        (stage/'card.json').write_text(canonical_json(card)+'\n',encoding='utf-8')
        manifest={'schema_version':1,'kind':'research_dataset_bundle','files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()}}
        (stage/'manifest.json').write_text(canonical_json(manifest)+'\n',encoding='utf-8')
        if not verify_research_bundle(stage):raise ValueError('Release não reproduzível')
        stage.rename(target);return manifest
    finally:
        if stage.exists():shutil.rmtree(stage)


def verify_research_bundle(directory):
    root=Path(directory)
    try:
        if (root/'manifest.json').is_symlink() or (root/'manifest.json').stat().st_size>1024*1024:return False
        manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        if manifest['schema_version']!=1 or manifest['kind']!='research_dataset_bundle':return False
        expected={'records.jsonl','train.jsonl','validation.jsonl','test.jsonl','unassigned.jsonl','card.json'}
        if 'records.parquet' in manifest['files']:expected.add('records.parquet')
        if set(manifest['files'])!=expected or {p.name for p in root.iterdir()}!=expected|{'manifest.json'}:return False
        for name,digest in manifest['files'].items():
            p=root/name
            if p.is_symlink() or not p.is_file() or p.stat().st_size>64*1024*1024 or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:return False
        with (root/'records.jsonl').open('rb') as stream:records=tuple(iter_load(stream))
        if len({r.content_id for r in records})!=len(records):return False
        # The same transactional split gate used at ingestion also audits import.
        semantics={}
        from ..datasets.semantic_fingerprint import semantic_fingerprint
        for r in records:
            key=r.semantic_id if isinstance(r,ResearchRecord) else semantic_fingerprint(r);split=r.to_data()['split']
            if key in semantics and semantics[key]!=split:return False
            semantics[key]=split
        card=json.loads((root/'card.json').read_text(encoding='utf-8'))
        if type(card['require_training_splits']) is not bool or type(card['allow_observations']) is not bool:return False
        if card!=_card(records,require_training_splits=card['require_training_splits'],allow_observations=card['allow_observations']):return False
        for split in ('train','validation','test','unassigned'):
            raw=(root/f'{split}.jsonl').read_text(encoding='utf-8')
            if raw!=''.join(canonical_json(r.to_data())+'\n' for r in records if r.to_data()['split']==split):return False
        if 'records.parquet' in expected:
            from .parquet import iter_parquet_stream
            if tuple(r.content_id for r in iter_parquet_stream(root/'records.parquet'))!=tuple(r.content_id for r in records):return False
        return True
    except (ValueError,KeyError,TypeError,OSError,ArithmeticError):return False
