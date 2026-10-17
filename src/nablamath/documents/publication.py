"""Atomic publication of a shared scientific document and its provenance."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from .document_model import Document, Section
from .exporters import to_html, to_latex, to_typst
from .figures import validate_figure
from .pdf_builder import build_pdf
from ..core.semantic_ir import canonical_json


def research_document(title, *, hypothesis, method, results, discussion, limitations,
                      evidence_ids, equations=(), figures=(), references=(), synthetic=True):
    if not evidence_ids:
        raise ValueError('Resultados requerem identificadores de evidência')
    return Document(title, (Section('Hipótese', hypothesis), Section('Método', method),
                    Section('Resultados', results, tuple(evidence_ids), tuple(equations), tuple(figures)),
                    Section('Discussão', discussion)), synthetic, limitations, tuple(references))


def publish(document: Document, destination: Path, *, asset_root=None, pdf_backend=None, evidence_sources=None, require_evidence=False):
    destination = Path(destination)
    evidence_sources = evidence_sources or {}
    requested = {key for section in document.sections
                 for key in (*section.evidence_ids, *(key for table in section.tables for key in table.evidence_ids))}
    if set(evidence_sources)-requested:
        raise ValueError('Fonte de evidência não citada')
    if require_evidence and requested-set(evidence_sources):
        raise ValueError('Evidência citada sem fonte verificável')
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.studio-', dir=destination.parent))
    try:
        evidence = {}
        for key, source in evidence_sources.items():
            raw = Path(source).read_bytes()
            if len(raw)>32*1024*1024 or hashlib.sha256(raw).hexdigest()!=key:
                raise ValueError('Evidência não corresponde ao SHA-256 citado')
            name = 'evidence/'+key+'.json'
            target = stage/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            evidence[key] = name
        for section in document.sections:
            for figure in section.figures:
                if asset_root is None:
                    raise ValueError('Figuras requerem raiz de artefatos')
                source = validate_figure(figure, asset_root)
                target = stage / figure.path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        for suffix, exporter in [('html', to_html), ('tex', to_latex), ('typ', to_typst)]:
            (stage/f'document.{suffix}').write_text(exporter(document), encoding='utf-8')
        (stage/'document.json').write_text(canonical_json(document.to_data())+'\n', encoding='utf-8')
        if pdf_backend:
            build_pdf(document, stage/'document.pdf', pdf_backend, asset_root=stage)
        manifest = {'schema_version': 1, 'render_profile':'nabla-print-v2','document_id': document.content_id, 'pdf_backend': pdf_backend,
                    'evidence': evidence, 'unresolved_evidence': sorted(requested-set(evidence)),
                    'files': {p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted(stage.rglob('*')) if p.is_file()}}
        (stage/'manifest.json').write_text(canonical_json(manifest)+'\n', encoding='utf-8')
        if not verify_publication(stage):
            raise ValueError('Publicação não reproduzível')
        stage.rename(destination)
        return manifest
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def verify_publication(root):
    try:
        root = Path(root)
        if any(p.is_symlink() for p in root.rglob('*')) or (root/'manifest.json').stat().st_size > 1024*1024:
            return False
        manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        files = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name != 'manifest.json'}
        if set(manifest['files']) != files:
            return False
        for name, digest in manifest['files'].items():
            path = root/name
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                return False
            if path.stat().st_size > 32*1024*1024:
                return False
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                return False
        document = Document.from_data(json.loads((root/'document.json').read_text(encoding='utf-8')))
        if document.content_id != manifest['document_id']:
            return False
        profile = manifest.get('render_profile','nabla-print-v1')
        if profile=='nabla-print-v1':
            from .legacy_exporters import to_html as html,to_latex as latex,to_typst as typst
        elif profile=='nabla-print-v2':
            html,latex,typst = to_html,to_latex,to_typst
        else:
            return False
        for suffix, exporter in [('html', html), ('tex', latex), ('typ', typst)]:
            if (root/f'document.{suffix}').read_text(encoding='utf-8') != exporter(document):
                return False
        expected = {'document.json', 'document.html', 'document.tex', 'document.typ'}
        requested = {key for section in document.sections
                 for key in (*section.evidence_ids, *(key for table in section.tables for key in table.evidence_ids))}
        evidence = manifest['evidence']
        if set(evidence)-requested or manifest['unresolved_evidence'] != sorted(requested-set(evidence)):
            return False
        for key, name in evidence.items():
            if name != 'evidence/'+key+'.json' or hashlib.sha256((root/name).read_bytes()).hexdigest()!=key:
                return False
            expected.add(name)
        for section in document.sections:
            for figure in section.figures:
                validate_figure(figure, root)
                expected.add(figure.path)
        if manifest['pdf_backend'] is not None:
            if manifest['pdf_backend'] not in {'latex', 'typst'} or not (root/'document.pdf').read_bytes().startswith(b'%PDF-'):
                return False
            expected.add('document.pdf')
        if expected != files:
            return False
        return manifest['schema_version'] == 1
    except (ValueError, KeyError, TypeError, OSError):
        return False
