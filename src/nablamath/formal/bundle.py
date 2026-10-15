"""Portable question–statement–certificate bundles with pinned toolchain metadata."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from ..core.semantic_ir import canonical_json
from .statement import FormalStatement
from .translation_review import verify_translation_binding
from ..verify.certificate import verify_formal_certificate


def export_formal_bundle(question,statement,certificate,binding,destination,*,project=Path('lean')):
    project=Path(project)
    if not verify_translation_binding(binding,question=question,statement=statement,task_id=binding['task_id']):
        raise ValueError('Vínculo pergunta/enunciado inválido')
    if certificate['statement']!=statement.to_data() or not verify_formal_certificate(certificate,project=project):
        raise ValueError('Certificado não reproduzível para o enunciado')
    destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.formal-',dir=destination.parent))
    try:
        for name,data in (('question.json',{'question':question}),('statement.json',statement.to_data()),
                          ('certificate.json',certificate),('binding.json',binding)):
            (stage/name).write_text(canonical_json(data)+'\n',encoding='utf-8')
        pinned={}
        for name in ('lean-toolchain','lakefile.toml','lake-manifest.json'):
            path=project/name
            if path.is_file():
                content=path.read_bytes()
                if len(content)>2*1024*1024:raise ValueError('Lockfile excede limite')
                (stage/name).write_bytes(content);pinned[name]=hashlib.sha256(content).hexdigest()
        if certificate['backend_receipt']['backend']=='lean4':
            from .lean_bridge import translate_statement
            translation=translate_statement(statement,certificate['backend_receipt']['strategy'])
            (stage/'proof.lean').write_text(translation.source,encoding='utf-8')
        manifest={'schema_version':1,'statement_id':statement.content_id,'certificate_id':certificate['certificate_id'],
                  'toolchain_files':pinned,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()},
                  'review_accepted':binding['accepted'],'reviewer_identity_authenticated':False,
                  'scope':'Backend-rechecked certificate and declared translation review; install pinned dependencies to reproduce.'}
        (stage/'manifest.json').write_text(canonical_json(manifest)+'\n',encoding='utf-8')
        if not verify_formal_bundle(stage,project=project):raise ValueError('Bundle formal não reproduzível')
        stage.rename(destination)
        return manifest
    finally:
        if stage.exists():shutil.rmtree(stage)


def verify_formal_bundle(root,*,project=Path('lean')):
    try:
        root=Path(root);project=Path(project)
        if (root/'manifest.json').stat().st_size>1024*1024:return False
        manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        files={p.name for p in root.iterdir() if p.name!='manifest.json'}
        if manifest['schema_version']!=1 or files!=set(manifest['files']):return False
        allowed={'question.json','statement.json','certificate.json','binding.json','proof.lean','lean-toolchain','lakefile.toml','lake-manifest.json'}
        if not files<=allowed or not {'question.json','statement.json','certificate.json','binding.json'}<=files:return False
        for name,digest in manifest['files'].items():
            path=root/name
            if path.is_symlink() or not path.is_file() or path.stat().st_size>4*1024*1024 or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:return False
        for name,digest in manifest['toolchain_files'].items():
            if name not in ('lean-toolchain','lakefile.toml','lake-manifest.json') or hashlib.sha256((project/name).read_bytes()).hexdigest()!=digest:return False
        def read(name):return json.loads((root/name).read_text(encoding='utf-8'))
        statement=FormalStatement.from_data(read('statement.json'));certificate=read('certificate.json');binding=read('binding.json')
        if not verify_translation_binding(binding,question=read('question.json')['question'],statement=statement,task_id=binding['task_id']):return False
        if (statement.content_id!=manifest['statement_id'] or certificate['certificate_id']!=manifest['certificate_id']
                or certificate['statement']!=statement.to_data() or manifest['review_accepted']!=binding['accepted']
                or manifest['reviewer_identity_authenticated'] is not False):return False
        if certificate['backend_receipt']['backend']=='lean4':
            from .lean_bridge import translate_statement
            if (root/'proof.lean').read_text(encoding='utf-8')!=translate_statement(statement,certificate['backend_receipt']['strategy']).source:return False
        return verify_formal_certificate(certificate,project=project)
    except (ValueError,KeyError,TypeError,OSError):return False
