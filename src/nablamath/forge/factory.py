"""Balanced eight-family factory with independent traces and optional measured calibration."""
from pathlib import Path
import hashlib
import json
import shutil
import tempfile

from ..core.semantic_ir import canonical_json
from ..datasets.splits import SplitPolicy,assign_splits,audit_splits
from ..verify.trace import build_trace,VerificationTrace
from .task_spec import FAMILIES,TaskSpec
from .reverse_builder import generate_task
from .sampling import sampling_plan
from .deduplicate import SemanticIndex,semantic_fingerprint
from .difficulty import calibrate,validate_calibration
from .solvers import solve_task


def run_factory(destination,*,count=24,seed=42,families=FAMILIES,sizes=(2,3,4),license_id,provenance,calibration=False,budget=1000000):
    if not isinstance(license_id,str) or not license_id.strip() or not isinstance(provenance,str) or not provenance.strip():
        raise ValueError('Licenca e procedencia obrigatorias')
    plan=list(sampling_plan(count,seed,tuple(families),tuple(sizes)))
    if calibration and count>128:
        raise ValueError('Calibracao limitada a 128 tentativas por benchmark')
    destination=Path(destination).absolute()
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.forge-v2-',dir=destination.parent))
    try:
        generated=[];index=SemanticIndex()
        for family,derived,size in plan:
            item=generate_task(family,derived,size)
            if index.add(item.task):
                generated.append(item)
        tasks=[item.task for item in generated]
        policy=SplitPolicy();assignment=assign_splits(tasks,policy)
        profile=calibrate(tasks,budget=budget) if calibration else None
        records=[];partitions={name:[] for name in ('train','validation','test')}
        for item in generated:
            task=item.task
            witness=build_trace(task,item.witness)
            candidate=solve_task(task)
            trace=build_trace(task,candidate)
            if not witness.to_data()['verification']['valid'] or not trace.to_data()['verification']['valid']:
                raise ArithmeticError('Construtor/solver rejeitado pelo verificador')
            row={'schema_version':2,'task':task.to_data(),'task_id':task.content_id,
                 'semantic_id':semantic_fingerprint(task),'seed':item.seed,'generator_version':'inverse-v2',
                 'witness_trace':witness.to_data(),'solution_trace':trace.to_data(),'split':assignment[task.content_id],
                 'license_id':license_id,'provenance':provenance,'synthetic':True,
                 'difficulty':profile['ratings'][task.content_id] if profile else {'label':'uncalibrated'},
                 'calibration_id':profile['calibration_id'] if profile else None}
            records.append(row);partitions[row['split']].append(row)
        for name,rows in [('records',records),*partitions.items()]:
            (stage/f'{name}.jsonl').write_text(''.join(canonical_json(r)+'\n' for r in rows),encoding='utf-8')
        report=index.report()
        report.update({'schema_version':2,'seed':seed,'count':count,'families_requested':list(families),'sizes_requested':list(sizes),
                       'license_id':license_id,'provenance':provenance,'split_policy':policy.to_data(),
                       'splits':{k:len(v) for k,v in partitions.items()},
                       'contamination':audit_splits({k:[TaskSpec.from_data(r['task']) for r in rows] for k,rows in partitions.items()}),
                       'calibration_id':profile['calibration_id'] if profile else None})
        (stage/'card.json').write_text(canonical_json(report)+'\n',encoding='utf-8')
        if profile:
            (stage/'calibration.json').write_text(canonical_json(profile)+'\n',encoding='utf-8')
        manifest={'schema_version':2,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(stage.iterdir())}}
        (stage/'manifest.json').write_text(canonical_json(manifest)+'\n',encoding='utf-8')
        if not verify_factory(stage):
            raise ArithmeticError('Bundle Forge v2 falhou na reexecucao')
        if destination.exists():
            raise FileExistsError(destination)
        stage.rename(destination)
        return report
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def verify_factory(directory):
    try:
        root=Path(directory)
        manifest_path=root/'manifest.json'
        if manifest_path.is_symlink() or manifest_path.stat().st_size>1024*1024:
            return False
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest['schema_version']!=2:
            return False
        actual={p.name for p in root.iterdir() if p.name!='manifest.json'}
        if set(manifest['files'])!=actual:
            return False
        for name,digest in manifest['files'].items():
            path=root/name
            if Path(name).name!=name or path.is_symlink() or not path.is_file() or path.stat().st_size>64*1024*1024:
                return False
            if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                return False
        records=[json.loads(line) for line in (root/'records.jsonl').read_text(encoding='utf-8').splitlines()]
        if not 1<=len(records)<=1000:
            return False
        tasks=[];index=SemanticIndex()
        for row in records:
            task=TaskSpec.from_data(row['task']);tasks.append(task)
            if (row['schema_version']!=2 or row['generator_version']!='inverse-v2' or row['synthetic'] is not True
                    or task.content_id!=row['task_id'] or semantic_fingerprint(task)!=row['semantic_id'] or not index.add(task)):
                return False
            regenerated=generate_task(task.family,row['seed'],task.size)
            if regenerated.task!=task or row['witness_trace']!=build_trace(task,regenerated.witness).to_data():
                return False
            trace=VerificationTrace.from_data(row['solution_trace'])
            if not trace.to_data()['verification']['valid'] or trace.to_data()['task_id']!=task.content_id:
                return False
        card=json.loads((root/'card.json').read_text(encoding='utf-8'))
        expected=[];generation_index=SemanticIndex()
        for family,seed,size in sampling_plan(card['count'],card['seed'],card['families_requested'],card['sizes_requested']):
            item=generate_task(family,seed,size)
            if generation_index.add(item.task):
                expected.append((item.task.content_id,seed))
        if expected!=[(r['task_id'],r['seed']) for r in records]:
            return False
        if any(card.get(k)!=v for k,v in generation_index.report().items()):
            return False
        policy_data=dict(card['split_policy']);group=policy_data.pop('group')
        if group!='constructor_family':
            return False
        policy=SplitPolicy(**policy_data);assignments=assign_splits(tasks,policy)
        partitions={name:[json.loads(line) for line in (root/f'{name}.jsonl').read_text(encoding='utf-8').splitlines()]
                    for name in ('train','validation','test')}
        expected_partitions={name:[r for r in records if r['split']==name] for name in partitions}
        if partitions!=expected_partitions or any(r['split']!=assignments[r['task_id']] for r in records):
            return False
        audit=audit_splits({k:[TaskSpec.from_data(r['task']) for r in rows] for k,rows in partitions.items()})
        if card['contamination']!=audit or not audit['clean'] or card['splits']!={k:len(v) for k,v in partitions.items()}:
            return False
        if not card['license_id'].strip() or not card['provenance'].strip() or any(r['license_id']!=card['license_id'] or r['provenance']!=card['provenance'] for r in records):
            return False
        profile=None
        if card['calibration_id'] is not None:
            profile=json.loads((root/'calibration.json').read_text(encoding='utf-8'))
            if profile['calibration_id']!=card['calibration_id'] or not validate_calibration(profile,tasks):
                return False
        for row in records:
            if row['calibration_id']!=card['calibration_id'] or row['difficulty']!=(profile['ratings'][row['task_id']] if profile else {'label':'uncalibrated'}):
                return False
        return True
    except (ValueError,TypeError,KeyError,OSError,ArithmeticError):
        return False
