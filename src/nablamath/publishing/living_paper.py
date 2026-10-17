"""Verified bundles -> escaped Typst data -> PDF, with immutable build snapshots.

Templates are trusted Typst programs. Result placeholders are data, never source.
Footer presence is checked in every rendered PDF page. A signature authenticates
its explicit experiment/receipt scope; it is not a PDF signature or truth oracle.
"""
from dataclasses import dataclass
import hashlib
from importlib import resources
from importlib.metadata import version,PackageNotFoundError
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from threading import RLock,Event

from ..artifacts.bundle import load_bundle, verify_bundle
from ..artifacts.process import run_renderer,publication_lock
from ..core.semantic_ir import canonical_json,fingerprint
from ..documents.typesetting import typst_style,typst_literal
from .layout import display_value

MAX_BYTES = 16*1024*1024
PLACEHOLDER = re.compile(r'\{\{\s*([A-Za-z][A-Za-z0-9_]{0,63})\s*\}\}')

FOOTER = r'''
#set page(margin: (left: 22mm, right: 22mm, top: 23mm, bottom: 35mm), footer: context [
  #set text(font: "DejaVu Sans Mono", size: 6.3pt, fill: rgb("526471"))
  #set par(leading: 0.25em, justify: false)
  #line(length: 100%, stroke: 0.4pt + rgb("c9d5db"))
  #v(3pt)
  #grid(columns: (1fr, auto), text("NABLA / AUDITABLE COMPUTATION"),
        [#counter(page).display() / #counter(page).final().at(0)])
  #linebreak()
  #text("Experiment SHA-256: " + nabla.experiment_hash) \
  #text(nabla.signature_label) \
  #for line in nabla.signature_lines { text(line); linebreak() }
])
'''


def _hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):
            digest.update(block)
    return digest.hexdigest()


def _read(path, maximum=MAX_BYTES):
    with Path(path).open('rb') as stream:
        value = stream.read(maximum+1)
    if len(value) > maximum:
        raise ValueError('Publication input exceeds byte budget')
    return value


def _pointer(value, pointer):
    if not isinstance(pointer,str) or (pointer and not pointer.startswith('/')):
        raise ValueError('Result bindings require RFC 6901 JSON pointers')
    for part in pointer.split('/')[1:] if pointer else []:
        part = part.replace('~1','/').replace('~0','~')
        value = value[int(part)] if isinstance(value,list) else value[part]
    return value


def _signature(bundle, envelope, trust, required):
    if envelope is None:
        if required:
            raise ValueError('This publication requires a trusted laboratory signature')
        return 'Unsigned: no laboratory signature supplied',[]
    if trust is None or not trust.verify(envelope):
        raise ValueError('Unknown, invalid or revoked publication signature')
    payload = envelope['payload']
    if payload == bundle:
        scope = 'experiment'
    elif any(payload == calculation for calculation in bundle['receipts']):
        scope = 'receipt '+payload['content_id']
    else:
        raise ValueError('Signature does not cover this experiment or one of its receipts')
    text = envelope['signature']
    return f"Signer: {envelope['signer']}; scope: {scope}",[text[i:i+72] for i in range(0,len(text),72)]


def _verify_footer(pdf, experiment_hash, signature):
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise ImportError('Install nablamath[publishing] to check PDF provenance footers') from error
    reader = PdfReader(pdf)
    if not 1 <= len(reader.pages) <= 1000:
        raise ValueError('PDF page budget exceeded')
    for page in reader.pages:
        text = ''.join((page.extract_text() or '').split())
        if experiment_hash not in text or (signature is not None and signature['signature'] not in text):
            raise ValueError('A rendered page is missing the required experiment hash/signature footer')


@dataclass(frozen=True)
class Publication:
    pdf: Path
    manifest: Path
    experiment_hash: str
    publication_id: str
    changed: bool


class TypstCompiler:
    def __init__(self, *, executable=None, trust=None, require_signature=False, timeout=60):
        if type(require_signature) is not bool or type(timeout) not in (int,float) or not 0 < timeout <= 600:
            raise ValueError('Invalid publication policy or renderer timeout')
        self.executable = executable or shutil.which('typst')
        self.trust,self.require_signature,self.timeout = trust,require_signature,timeout
        self._lock = RLock()

    def compile(self, artifact, destination, *, template=None, variables=None, figures=(),
                asset_root=None, title='Nabla living paper', signature=None,
                authors=(), abstract='', language='en'):
        with self._lock:
            destination = Path(destination)
            if destination.is_symlink():
                raise ValueError('Publication PDF cannot be a symlink')
            with publication_lock(destination.with_suffix(destination.suffix+'.lock')):
                return self._compile(artifact,destination,template=template,variables=variables,
                                     figures=figures,asset_root=asset_root,title=title,signature=signature,
                                     authors=authors,abstract=abstract,language=language)

    def _compile(self, artifact, destination, *, template, variables, figures, asset_root, title, signature,authors,abstract,language):
        bundle = load_bundle(artifact) if isinstance(artifact,(str,Path)) else json.loads(canonical_json(artifact))
        if not verify_bundle(bundle):
            raise ValueError('Living papers require a verified Nabla artifact bundle')
        label,signature_lines = _signature(bundle,signature,self.trust,self.require_signature)
        if not isinstance(title,str) or not title.strip() or len(title) > 4096:
            raise ValueError('A bounded publication title is required')
        if not isinstance(authors,(tuple,list)) or len(authors)>32 or any(not isinstance(v,str) or not v.strip() or len(v)>256 for v in authors):
            raise ValueError('A publication accepts at most 32 named authors')
        if not isinstance(abstract,str) or len(abstract)>8192:
            raise ValueError('Abstract exceeds its publication budget')
        preamble = typst_style(title,bundle['content_id'],language=language)
        template_text = (_read(template,1048576).decode() if template is not None else
                         resources.files('nablamath.publishing').joinpath('templates/living_paper.typ').read_text(encoding='utf-8'))
        if variables is None:
            result = bundle['receipts'][0]['result'] if bundle['receipts'] else {}
            variables = {k:'/receipts/0/result/'+k.replace('~','~0').replace('/','~1')
                         for k in result if re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,63}',k)} if isinstance(result,dict) else {}
        if not isinstance(variables,dict) or len(variables) > 128:
            raise ValueError('A publication accepts at most 128 result bindings')
        bindings,results = {},[]
        for name,pointer in variables.items():
            if not isinstance(name,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,63}',name):
                raise ValueError('Invalid result binding name')
            value = _pointer(bundle,pointer)
            text = value if isinstance(value,str) else canonical_json(value)
            if len(text) > 65536:
                raise ValueError('Select a result summary instead of embedding an oversized data array')
            bindings[name] = text
            results.append({'name':name.replace('_',' '),'value':display_value(value)})
        def replace(match):
            name = match.group(1)
            if name not in bindings:
                raise ValueError('Unknown template result binding: '+name)
            return '#nabla.bindings.at('+json.dumps(name)+')'
        body = PLACEHOLDER.sub(replace,template_text)
        if len(figures) > 32 or (figures and asset_root is None):
            raise ValueError('At most 32 figures with an explicit asset_root are allowed')
        images,assets = [],[]
        for i,figure in enumerate(figures):
            if not isinstance(figure,dict) or set(figure) != {'path','caption'} or not isinstance(figure['caption'],str) or len(figure['caption']) > 4096:
                raise ValueError('Figures require path and bounded caption')
            root = Path(asset_root).resolve()
            path = Path(figure['path'])
            path = path if path.is_absolute() else root/path
            if path.is_symlink() or not path.resolve().is_relative_to(root) or path.suffix.lower() not in {'.png','.jpg','.jpeg','.svg'}:
                raise ValueError('Figure is outside asset_root or has an unsupported format')
            raw = _read(path); relative = f'assets/figure-{i}{path.suffix.lower()}'
            assets.append((relative,raw))
            images.append({'path':relative,'caption':figure['caption'],'sha256':hashlib.sha256(raw).hexdigest()})
        data = {'title':title,'experiment_hash':bundle['content_id'],'bindings':bindings,'images':images,
                'signature_label':json.loads(typst_literal(label)),'signature_lines':signature_lines,'results':results,
                'authors':list(authors),'abstract':abstract,'language':language}
        renderer = self.executable or 'python-typst'
        try:
            renderer_version = version('typst') if self.executable is None else 'external-cli'
        except PackageNotFoundError as error:
            raise ImportError('Install nablamath[publishing] or a Typst executable') from error
        identity = fingerprint({'experiment':bundle,'template':template_text,'data':data,
                                'signature':signature,'renderer':renderer,'version':renderer_version,'footer_template':FOOTER,'style':preamble})
        destination = Path(destination)
        manifest_path = destination.with_suffix(destination.suffix+'.nabla.json')
        if destination.exists():
            if not verify_publication(destination,trust=self.trust,require_signature=self.require_signature):
                raise FileExistsError('Existing PDF has no intact Nabla publication manifest; it will not be overwritten')
            old = json.loads(_read(manifest_path))
            if old['input_id'] == identity:
                return Publication(destination,manifest_path,bundle['content_id'],old['content_id'],False)
        elif manifest_path.exists():
            raise ValueError('Publication manifest exists without its PDF')
        destination.parent.mkdir(parents=True,exist_ok=True)
        history = destination.parent/(destination.name+'.history')
        if history.is_symlink():
            raise ValueError('Publication history cannot be a symlink')
        history.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.nabla-paper-',dir=history) as directory:
            stage = Path(directory)
            (stage/'experiment.json').write_text(canonical_json(data),encoding='utf-8')
            (stage/'bundle.json').write_text(canonical_json(bundle),encoding='utf-8')
            (stage/'template.typ').write_text(template_text,encoding='utf-8')
            source = '#let nabla = json("experiment.json")\n'+preamble+'\n'+FOOTER+'\n'+body
            (stage/'paper.typ').write_text(source,encoding='utf-8')
            for relative,raw in assets:
                path = stage/relative; path.parent.mkdir(exist_ok=True); path.write_bytes(raw)
            if self.executable:
                command = [str(self.executable),'compile','--root',str(stage),str(stage/'paper.typ'),str(stage/'paper.pdf')]
            else:
                command = [sys.executable,'-m','nablamath.publishing._typst_worker',str(stage/'paper.typ'),str(stage/'paper.pdf'),str(stage)]
            run_renderer(command,cwd=stage,timeout=self.timeout)
            pdf = _read(stage/'paper.pdf',256*1024*1024)
            if not pdf.startswith(b'%PDF-'):
                raise RuntimeError('Typst did not produce a PDF')
            _verify_footer(stage/'paper.pdf',bundle['content_id'],signature)
            body_manifest = {'schema_version':1,'kind':'nabla_living_paper','input_id':identity,
                'experiment_hash':bundle['content_id'],'signature':signature,'images':images,
                'pdf_sha256':hashlib.sha256(pdf).hexdigest(),'template_sha256':hashlib.sha256(template_text.encode()).hexdigest(),
                'rendered_source_sha256':hashlib.sha256(source.encode()).hexdigest(),
                'renderer':renderer,'renderer_version':renderer_version,
                'limitations':'Signature scope is explicit; prose, experimental validity and independent scientific review are not certified.'}
            manifest = {**body_manifest,'content_id':fingerprint(body_manifest)}
            snapshot = history/(identity+'-'+manifest['pdf_sha256'][:16])
            if snapshot.exists():
                if _hash(snapshot/'paper.pdf') != manifest['pdf_sha256']:
                    raise ValueError('Historical publication snapshot was altered')
            else:
                shutil.copytree(stage,snapshot)
            manifest['snapshot'] = snapshot.name
            # The pointer to an immutable snapshot is part of the manifest digest.
            manifest['content_id'] = fingerprint({k:v for k,v in manifest.items() if k != 'content_id'})
            if not (snapshot/'manifest.json').exists():
                with (snapshot/'manifest.json').open('x',encoding='utf-8') as stream:
                    stream.write(canonical_json(manifest))
            descriptor,temporary = tempfile.mkstemp(prefix='.nabla-pdf-',dir=destination.parent)
            try:
                with os.fdopen(descriptor,'wb') as stream:
                    stream.write(pdf); stream.flush(); os.fsync(stream.fileno())
                if destination.exists():
                    # Recheck immediately before publication; never replace an edited PDF.
                    if not verify_publication(destination,trust=self.trust,require_signature=self.require_signature):
                        raise ValueError('Publication changed during compilation')
                    os.replace(temporary,destination)
                else:
                    os.link(temporary,destination)
            finally:
                Path(temporary).unlink(missing_ok=True)
            descriptor,temporary = tempfile.mkstemp(prefix='.nabla-manifest-',dir=destination.parent)
            try:
                with os.fdopen(descriptor,'w',encoding='utf-8') as stream:
                    stream.write(canonical_json(manifest)); stream.flush(); os.fsync(stream.fileno())
                os.replace(temporary,manifest_path)
            finally:
                Path(temporary).unlink(missing_ok=True)
        return Publication(destination,manifest_path,bundle['content_id'],manifest['content_id'],True)

    def watch(self, artifact, destination, *, stop_event=None, poll_interval=.5,max_updates=None,**options):
        if not isinstance(artifact,(str,Path)) or not .05 <= poll_interval <= 60:
            raise ValueError('Watch requires a bundle path and poll interval in [.05,60] seconds')
        if max_updates is not None and (type(max_updates) is not int or max_updates < 1):
            raise ValueError('max_updates must be positive or None')
        stop_event = stop_event or Event(); updates = 0
        while not stop_event.is_set():
            publication = self.compile(artifact,destination,**options)
            if publication.changed:
                yield publication
                updates += 1
                if max_updates is not None and updates >= max_updates:
                    return
            stop_event.wait(poll_interval)


def verify_publication(pdf, *, trust=None, require_signature=False):
    try:
        pdf = Path(pdf); path = pdf.with_suffix(pdf.suffix+'.nabla.json')
        manifest = json.loads(_read(path))
        body = {k:v for k,v in manifest.items() if k != 'content_id'}
        if manifest['schema_version'] != 1 or manifest['kind'] != 'nabla_living_paper' or fingerprint(body) != manifest['content_id'] or _hash(pdf) != manifest['pdf_sha256']:
            return False
        name = manifest['snapshot']
        if not isinstance(name,str) or not re.fullmatch('[0-9a-f]{64}-[0-9a-f]{16}',name):
            return False
        root = pdf.parent/(pdf.name+'.history')/name
        if root.is_symlink() or root.parent.is_symlink() or any((root/file).is_symlink() for file in ('bundle.json','paper.pdf','template.typ','paper.typ')):
            return False
        bundle = load_bundle(root/'bundle.json')
        if bundle['content_id'] != manifest['experiment_hash'] or _hash(root/'paper.pdf') != manifest['pdf_sha256'] or _hash(root/'template.typ') != manifest['template_sha256'] or _hash(root/'paper.typ') != manifest['rendered_source_sha256']:
            return False
        for image in manifest['images']:
            asset = root/image['path']
            if not asset.resolve().is_relative_to(root.resolve()) or _hash(asset) != image['sha256']:
                return False
        _signature(bundle,manifest['signature'],trust,require_signature)
        _verify_footer(pdf,bundle['content_id'],manifest['signature'])
        return True
    except (OSError,ValueError,TypeError,KeyError,IndexError,RecursionError):
        return False
