"""Reactive scientific papers: escaped Typst/LaTeX, standalone HTML and PDF.

Documents are structured data, not executable templates. Typst/PDF compilation
uses the existing isolated renderer. LaTeX source is exported but never executed
with shell escape. An experiment attachment and clickable local audit companion
make provenance inspectable without a verification service. Hashes establish
integrity, not the scientific correctness of prose or results.
"""
import base64
from dataclasses import dataclass
import hashlib
import html
import io
import json
from pathlib import Path
import re
import tempfile

from ..artifacts.bundle import load_bundle, verify_bundle
from ..core.semantic_ir import canonical_json
from ..publishing.living_paper import TypstCompiler, _pointer

_BINDING = re.compile(r'\{\{\s*([A-Za-z][A-Za-z0-9_]{0,63})\s*\}\}')
_MAX_BYTES = 16*1024*1024


def _read(path, limit=_MAX_BYTES):
    with Path(path).open('rb') as stream:
        raw = stream.read(limit+1)
    if len(raw)>limit:
        raise ValueError('Publication input budget exceeded')
    return raw


def _latex(value):
    replacements = {'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$',
                    '#':r'\#','_':r'\_','{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}
    return ''.join(replacements.get(c,c) for c in str(value))


def _literal(value):
    # Typst receives only quoted strings, never user-provided markup/math source.
    return json.dumps(str(value),ensure_ascii=False)


@dataclass(frozen=True)
class PaperBuild:
    directory: Path
    experiment_hash: str
    manifest: Path
    pdf: Path | None
    html: Path


class LivingPapersCompiler:
    def __init__(self, *, timeout=60, trust=None, require_signature=False):
        self.renderer = TypstCompiler(timeout=timeout,trust=trust,require_signature=require_signature)

    @staticmethod
    def _bundle(artifact):
        bundle = load_bundle(artifact) if isinstance(artifact,(str,Path)) else json.loads(canonical_json(artifact))
        if not verify_bundle(bundle):
            raise ValueError('Verified experiment bundle required')
        return bundle

    def resolve(self, artifact, document, *, bindings=None):
        """Resolve {{names}} through explicit RFC6901 pointers into a bundle."""
        bundle = self._bundle(artifact)
        if not isinstance(document,dict) or set(document)-{'title','authors','abstract','blocks','language'}:
            raise ValueError('Unknown document fields')
        title = document.get('title')
        if not isinstance(title,str) or not title.strip() or len(title)>4096:
            raise ValueError('Bounded nonempty title required')
        authors = document.get('authors',[])
        if not isinstance(authors,list) or len(authors)>32 or any(not isinstance(a,str) or not a.strip() or len(a)>256 for a in authors):
            raise ValueError('Up to 32 named authors required')
        bindings = bindings or {}
        if not isinstance(bindings,dict) or len(bindings)>128:
            raise ValueError('At most 128 explicit bindings required')
        values = {}
        for name,pointer in bindings.items():
            if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}',name):
                raise ValueError('Invalid binding name')
            value = _pointer(bundle,pointer)
            values[name] = value if isinstance(value,str) else canonical_json(value)
        def text(value, limit=65536):
            if not isinstance(value,str) or len(value)>limit:
                raise ValueError('Bounded document text required')
            def replace(match):
                if match[1] not in values:
                    raise ValueError('Unknown result binding: '+match[1])
                return values[match[1]]
            result = _BINDING.sub(replace,value)
            if len(result)>limit:
                raise ValueError('Resolved text budget exceeded')
            return result
        blocks = document.get('blocks',[])
        if not isinstance(blocks,list) or len(blocks)>256:
            raise ValueError('At most 256 document blocks required')
        resolved = []
        for block in blocks:
            if not isinstance(block,dict):
                raise ValueError('Structured document block required')
            kind = block.get('kind')
            if kind in ('paragraph','heading','equation') and set(block)=={'kind','text'}:
                resolved.append({'kind':kind,'text':text(block['text'])})
            elif kind == 'table' and set(block)=={'kind','headers','rows'}:
                headers,rows = block['headers'],block['rows']
                if not isinstance(headers,list) or not 1<=len(headers)<=16 or not isinstance(rows,list) or len(rows)>1000:
                    raise ValueError('Table dimension budget exceeded')
                if any(not isinstance(row,list) or len(row)!=len(headers) for row in rows):
                    raise ValueError('Rectangular table required')
                resolved.append({'kind':kind,'headers':[text(v,4096) for v in headers],
                                 'rows':[[text(v,4096) for v in row] for row in rows]})
            elif kind == 'figure' and set(block)=={'kind','path','caption'}:
                resolved.append({'kind':kind,'path':text(block['path'],4096),'caption':text(block['caption'],4096)})
            else:
                raise ValueError('Unsupported document block or extra fields')
        language = document.get('language','pt')
        if language not in ('pt','en','es','fr','de'):
            raise ValueError('Unsupported document language')
        return bundle, {'title':text(title,4096),'authors':authors,
                        'abstract':text(document.get('abstract',''),8192),
                        'blocks':resolved,'language':language}

    @staticmethod
    def _sources(document, experiment_hash):
        """Generate two escaped editorial sources with identical block content."""
        typ = ['#nabla-title(nabla.title)', '#text('+_literal(' · '.join(document['authors']))+')',
               '#block(fill: rgb("f2f6f7"), inset: 12pt, radius: 3pt)[#text('+_literal(document['abstract'])+')]']
        tex = [r'\documentclass[11pt,a4paper]{article}',r'\usepackage[margin=22mm]{geometry}',
               r'\usepackage[T1]{fontenc}',r'\usepackage[utf8]{inputenc}',
               r'\usepackage{graphicx,booktabs,longtable,xcolor,fancyhdr,hyperref}',
               r'\hypersetup{colorlinks=true,urlcolor=teal}',r'\pagestyle{fancy}',r'\fancyhf{}',
               r'\fancyfoot[C]{\tiny SHA-256: \texttt{'+_latex(experiment_hash)+r'}\quad\thepage}',
               r'\title{'+_latex(document['title'])+'}',r'\author{'+_latex(' · '.join(document['authors']))+'}',
               r'\date{}',r'\begin{document}\maketitle',r'\begin{abstract}'+_latex(document['abstract'])+r'\end{abstract}']
        figure_index = 0
        for block in document['blocks']:
            kind = block['kind']
            if kind=='paragraph':
                typ.append('#par('+_literal(block['text'])+')')
                tex.append(_latex(block['text'])+'\n\n')
            elif kind=='heading':
                typ.append('#heading('+_literal(block['text'])+')')
                tex.append(r'\section{'+_latex(block['text'])+'}')
            elif kind=='equation':
                # User equation is displayed literally. No arbitrary TeX/Typst execution.
                typ.append('#block(width: 100%, inset: 9pt, fill: rgb("f2f6f7"))[#align(center, text(font: "DejaVu Sans Mono", size: 9pt, '+_literal(block['text'])+'))]')
                tex.append(r'\begin{quote}\ttfamily '+_latex(block['text'])+r'\end{quote}')
            elif kind=='table':
                cells = block['headers']+[v for row in block['rows'] for v in row]
                typ.append('#table(columns: '+str(len(block['headers']))+', '+', '.join('text('+_literal(v)+')' for v in cells)+')')
                tex.extend([r'\begin{longtable}{'+'l'*len(block['headers'])+'}',r'\toprule',
                            ' & '.join(map(_latex,block['headers']))+r'\\\midrule'])
                tex.extend(' & '.join(map(_latex,row))+r'\\' for row in block['rows'])
                tex.append(r'\bottomrule\end{longtable}')
            else:
                suffix = Path(block['path']).suffix.lower()
                path = f'assets/figure-{figure_index}{suffix}'
                typ.append('#figure(link("audit.html", image('+_literal(path)+', width: 92%)), caption: text('+_literal(block['caption'])+'))')
                tex.extend([r'\begin{figure}[ht]\centering',r'\href{audit.html}{\includegraphics[width=.92\linewidth]{'+path+'}}',
                            r'\caption{'+_latex(block['caption'])+r'}\end{figure}'])
                figure_index += 1
        typ.extend(['#pagebreak(weak: true)','#heading("Audit & reproducibility")',
                    '#par("The attached experiment records the computation; integrity does not certify scientific conclusions.")',
                    '#link("audit.html")[Open local audit companion]',
                    '#figure(image("audit-qr.svg", width: 24mm), caption: [Experiment identifier])'])
        tex.extend([r'\section*{Audit and reproducibility}',r'\href{audit.html}{Open local audit companion.}',
                    r'\end{document}'])
        return '\n'.join(typ), '\n'.join(tex)

    @staticmethod
    def _qr(experiment_hash):
        try:
            import qrcode
            from qrcode.image.svg import SvgPathImage
        except ImportError as error:
            raise ImportError('Install nablamath[publishing] for publication QR codes') from error
        stream = io.BytesIO()
        qrcode.make('urn:sha256:'+experiment_hash,image_factory=SvgPathImage,box_size=4,border=4).save(stream)
        return stream.getvalue()

    @staticmethod
    def _html(document, bundle, assets):
        raw = canonical_json(bundle).encode()
        digest = hashlib.sha256(raw).hexdigest()
        encoded = base64.b64encode(raw).decode()
        title = html.escape(document['title'])
        parts = ['<!doctype html><html lang="'+document['language']+'"><meta charset="utf-8">',
                 '<meta name="viewport" content="width=device-width"><title>'+title+'</title>',
                 '<style>body{margin:0;background:#edf2f4;color:#172b3a;font:17px/1.65 Georgia,serif}main{max-width:850px;margin:32px auto;padding:48px;background:white;border-top:5px solid #117879}h1,h2{font-family:system-ui;line-height:1.2}h1{font-size:2.2em}h2{color:#117879}aside{padding:18px;background:#f2f6f7}table{width:100%;border-collapse:collapse;font:14px system-ui}td,th{padding:9px;border-bottom:1px solid #dbe3e7;text-align:left}tr:nth-child(even){background:#f2f6f7}img{max-width:100%}code,pre,footer{overflow-wrap:anywhere;white-space:pre-wrap}footer{font:12px system-ui;border-top:1px solid #cad7dc;padding-top:16px}button{padding:10px;background:#117879;color:white;border:0;cursor:pointer}@media(max-width:650px){main{padding:20px;margin:0}}@media print{body{background:white}main{margin:0;padding:0}button{display:none}}</style><main>',
                 '<h1>'+title+'</h1><p>'+html.escape(' · '.join(document['authors']))+'</p>',
                 '<aside>'+html.escape(document['abstract'])+'</aside>']
        for block in document['blocks']:
            kind = block['kind']
            if kind in ('paragraph','heading','equation'):
                tag = {'paragraph':'p','heading':'h2','equation':'pre'}[kind]
                parts.append('<'+tag+'>'+html.escape(block['text'])+'</'+tag+'>')
            elif kind=='table':
                parts.append('<table><thead><tr>'+''.join('<th>'+html.escape(v)+'</th>' for v in block['headers'])+'</tr></thead><tbody>')
                parts.extend('<tr>'+''.join('<td>'+html.escape(v)+'</td>' for v in row)+'</tr>' for row in block['rows'])
                parts.append('</tbody></table>')
            else:
                asset = assets[block['path']]
                parts.append('<figure><a href="#audit"><img alt="'+html.escape(block['caption'],quote=True)+'" src="'+asset+'"></a><figcaption>'+html.escape(block['caption'])+'</figcaption></figure>')
        parts.append('<footer id="audit"><p>Experiment SHA-256: '+bundle['content_id']+'</p><p>Embedded JSON SHA-256: '+digest+'</p><p id="status">Embedded data available; integrity not checked in this browser yet.</p><button id="download">Download experiment JSON</button><p>Integrity is distinct from mathematical proof and peer review.</p></footer></main>')
        parts.append('<script>const encoded='+json.dumps(encoded)+';const expected='+json.dumps(digest)+';const bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));document.getElementById("download").onclick=()=>{const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([bytes],{type:"application/json"}));a.download="experiment.json";a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};if(globalThis.crypto?.subtle){crypto.subtle.digest("SHA-256",bytes).then(hash=>{const actual=Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,"0")).join("");document.getElementById("status").textContent=actual===expected?"Embedded JSON integrity verified. Receipt replay is a separate Nabla check.":"INTEGRITY FAILURE";});}</script></html>')
        return ''.join(parts)

    def build(self, artifact, destination, document, *, bindings=None, asset_root=None,
              pdf=True, signature=None):
        """Build into a fresh directory, publishing only after all stages succeed.

Rerun with changed receipt data and a fresh destination for reactive rebuilds.
The previous publication is retained. PDF includes the canonical experiment as
an embedded file; the companion HTML supports offline byte-integrity checks.
"""
        bundle, resolved = self.resolve(artifact,document,bindings=bindings)
        if type(pdf) is not bool:
            raise ValueError('pdf must be boolean')
        # Apply signature policy even when only HTML/source is requested.
        from ..publishing.living_paper import _signature
        signature_label, signature_lines = _signature(bundle,signature,self.renderer.trust,self.renderer.require_signature)
        destination = Path(destination)
        if destination.exists() or destination.is_symlink():
            raise FileExistsError('Use a fresh publication directory')
        destination.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.nabla-paper-build-',dir=destination.parent) as temporary:
            stage = Path(temporary)/'publication'
            stage.mkdir()
            assets, figures = {},[]
            for block in resolved['blocks']:
                if block['kind']!='figure':
                    continue
                if asset_root is None:
                    raise ValueError('Figures require explicit asset_root')
                root = Path(asset_root).resolve()
                path = Path(block['path'])
                path = path if path.is_absolute() else root/path
                suffix = path.suffix.lower()
                # Raster assets avoid script/external-reference hazards in standalone HTML.
                if path.is_symlink() or not path.resolve().is_relative_to(root) or suffix not in ('.png','.jpg','.jpeg'):
                    raise ValueError('Figure must be a raster image inside asset_root')
                raw = _read(path)
                from PIL import Image
                with Image.open(io.BytesIO(raw)) as image:
                    if image.width*image.height>40000000:
                        raise ValueError('Image pixel budget exceeded')
                    image.verify()
                target = stage/'assets'/f'figure-{len(figures)}{suffix}'
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(raw)
                mime = 'image/png' if suffix=='.png' else 'image/jpeg'
                assets[block['path']] = 'data:'+mime+';base64,'+base64.b64encode(raw).decode()
                figures.append({'path':str(path),'caption':block['caption']})
            typ,tex = self._sources(resolved,bundle['content_id'])
            from ..documents.typesetting import typst_style
            from ..publishing.living_paper import FOOTER
            paper_data = {'title':resolved['title'],'experiment_hash':bundle['content_id'],
                          'signature_label':signature_label,'signature_lines':signature_lines}
            (stage/'paper-data.json').write_text(canonical_json(paper_data),encoding='utf-8')
            standalone_source = '#let nabla = json("paper-data.json")\n'
            standalone_source += typst_style(resolved['title'],bundle['content_id'],language=resolved['language'])
            standalone_source += '\n'+FOOTER+'\n'+typ
            (stage/'paper.typ').write_text(standalone_source,encoding='utf-8')
            (stage/'audit-qr.svg').write_bytes(self._qr(bundle['content_id']))
            (stage/'paper.tex').write_text(tex,encoding='utf-8')
            (stage/'experiment.json').write_text(canonical_json(bundle),encoding='utf-8')
            (stage/'signature.json').write_text(canonical_json({'envelope':signature,'label':signature_label,'signature_lines':signature_lines}),encoding='utf-8')
            (stage/'audit.html').write_text(self._html(resolved,bundle,assets),encoding='utf-8')
            # The established renderer copies only declared figure assets. Embed QR as
            # a final declared SVG figure, and address its staged asset name.
            qr_index = len(figures)
            typ = typ.replace('image("audit-qr.svg",','image("assets/figure-'+str(qr_index)+'.svg",')
            template = stage/'template.typ'
            template.write_text(typ,encoding='utf-8')
            # Copy all assets to a single explicit renderer root.
            render_root = stage/'render-assets'
            render_root.mkdir()
            render_figures = []
            for i,figure in enumerate(figures):
                suffix = Path(figure['path']).suffix.lower()
                local = render_root/f'input-{i}{suffix}'
                local.write_bytes(_read(figure['path']))
                render_figures.append({'path':local.name,'caption':figure['caption']})
            (render_root/'qr.svg').write_bytes((stage/'audit-qr.svg').read_bytes())
            render_figures.append({'path':'qr.svg','caption':'Experiment identifier'})
            if pdf:
                publication = self.renderer.compile(bundle,stage/'rendered.pdf',template=template,
                    figures=render_figures,asset_root=render_root,title=resolved['title'],
                    authors=resolved['authors'],abstract=resolved['abstract'],language=resolved['language'],signature=signature)
                from pypdf import PdfReader, PdfWriter
                reader = PdfReader(publication.pdf)
                writer = PdfWriter()
                writer.append(reader)
                writer.add_attachment('experiment.json',canonical_json(bundle).encode())
                writer.add_metadata({'/Title':resolved['title'],'/Author':'; '.join(resolved['authors']),
                                     '/NablaExperimentSHA256':bundle['content_id']})
                with (stage/'paper.pdf').open('wb') as stream:
                    writer.write(stream)
                if PdfReader(stage/'paper.pdf').attachments['experiment.json'][0] != canonical_json(bundle).encode():
                    raise ArithmeticError('PDF experiment attachment verification failed')
            files = {path.relative_to(stage).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in sorted(stage.rglob('*')) if path.is_file()}
            manifest = {'schema':'nabla.paper-package.v1','experiment_hash':bundle['content_id'],
                        'files':files,'pdf_compiled':pdf,'signature':signature,
                        'limits':'Hashes bind bytes; scientific conclusions and peer review are separate.'}
            (stage/'manifest.json').write_text(canonical_json(manifest),encoding='utf-8')
            stage.rename(destination)
        return PaperBuild(destination,bundle['content_id'],destination/'manifest.json',
                          destination/'paper.pdf' if pdf else None,destination/'audit.html')

    @staticmethod
    def verify(directory):
        """Check package hashes, experiment integrity and PDF attachment binding."""
        try:
            root = Path(directory)
            if root.is_symlink() or (root/'manifest.json').is_symlink():
                return False
            manifest = json.loads(_read(root/'manifest.json'))
            if manifest['schema']!='nabla.paper-package.v1' or not isinstance(manifest['files'],dict):
                return False
            actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p!=root/'manifest.json'}
            if actual != set(manifest['files']):
                return False
            for relative,digest in manifest['files'].items():
                path = root/relative
                if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or hashlib.sha256(_read(path,256*1024*1024)).hexdigest()!=digest:
                    return False
            bundle = load_bundle(root/'experiment.json')
            if bundle['content_id']!=manifest['experiment_hash']:
                return False
            if manifest['pdf_compiled']:
                from pypdf import PdfReader
                reader = PdfReader(root/'paper.pdf')
                if reader.attachments['experiment.json'][0]!=canonical_json(bundle).encode():
                    return False
            return True
        except (OSError,ValueError,TypeError,KeyError,ImportError):
            return False


__all__ = ['LivingPapersCompiler','PaperBuild']

# New directive AST, vector provenance seals, XMP and reactive compilation.
from datetime import datetime, timezone
from threading import Event, Thread, RLock, Condition
import time
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class TypstDirective:
    """A literal span or a closed Nabla directive with exact source offsets."""
    kind: str
    start: int
    end: int
    text: str
    arguments: tuple = ()


class TypstTemplateEngine:
    """Parse Nabla's two directives without interpreting arbitrary Typst code.

    Supported syntax is #nabla-val("binding") and
    #nabla-calc("catalog_operation", {"closed": "JSON arguments"}). Strings,
    raw backtick spans and comments are lexically skipped. The surrounding
    template is a trusted Typst program executed later in the renderer's root.
    This is an extension parser, not a replacement implementation of Typst.
    """
    def __init__(self, *, max_directives=128, max_source_bytes=1048576):
        if type(max_directives) is not int or not 1<=max_directives<=1000 or type(max_source_bytes) is not int or not 1024<=max_source_bytes<=4194304:
            raise ValueError('Invalid template parsing budget')
        self.max_directives=max_directives;self.max_source_bytes=max_source_bytes

    @staticmethod
    def _skip_string(source, start):
        index=start+1
        while index<len(source):
            if source[index]=='\\':index+=2;continue
            if source[index]=='"':return index+1
            index+=1
        raise ValueError('Unterminated Typst string literal')

    @staticmethod
    def _skip_comment(source, start):
        if source.startswith('//',start):
            end=source.find('\n',start+2)
            return len(source) if end<0 else end
        depth=1;index=start+2
        while index<len(source):
            if source.startswith('/*',index):depth+=1;index+=2
            elif source.startswith('*/',index):
                depth-=1;index+=2
                if depth==0:return index
            else:index+=1
            if depth>32:raise ValueError('Typst nested comment depth budget exceeded')
        raise ValueError('Unterminated Typst block comment')

    def parse(self, source):
        if not isinstance(source,str) or len(source.encode())>self.max_source_bytes:
            raise ValueError('Template exceeds source byte budget')
        decoder=json.JSONDecoder();nodes=[];index=0;literal_start=0;count=0
        def whitespace(position):
            while position<len(source) and source[position].isspace():position+=1
            return position
        while index<len(source):
            if source[index]=='\\':index+=2;continue
            if source.startswith('//',index) or source.startswith('/*',index):
                index=self._skip_comment(source,index);continue
            if source[index]=='"':index=self._skip_string(source,index);continue
            if source[index]=='`':
                width=1
                while index+width<len(source) and source[index+width]=='`':width+=1
                end=source.find('`'*width,index+width)
                if end<0:raise ValueError('Unterminated Typst raw span')
                index=end+width;continue
            match=re.match(r'#nabla-(val|calc)\s*\(',source[index:])
            if match is None:index+=1;continue
            count+=1
            if count>self.max_directives:raise ValueError('Template directive budget exceeded')
            if index>literal_start:nodes.append(TypstDirective('literal',literal_start,index,source[literal_start:index]))
            cursor=whitespace(index+match.end())
            try:first,end=decoder.raw_decode(source,cursor)
            except json.JSONDecodeError as error:raise ValueError('Directive first argument must be a JSON string') from error
            if not isinstance(first,str) or not first or len(first)>4096:
                raise ValueError('Directive operation/binding must be a bounded nonempty string')
            cursor=whitespace(end);arguments=(first,)
            if match[1]=='calc':
                if cursor>=len(source) or source[cursor]!=',':raise ValueError('nabla-calc requires operation and argument object')
                cursor=whitespace(cursor+1)
                try:second,end=decoder.raw_decode(source,cursor)
                except json.JSONDecodeError as error:raise ValueError('nabla-calc requires JSON arguments') from error
                if not isinstance(second,dict) or len(canonical_json(second))>65536:
                    raise ValueError('Calculation arguments must be a bounded JSON object')
                arguments=(first,second);cursor=whitespace(end)
            if cursor>=len(source) or source[cursor]!=')':raise ValueError('Unexpected directive arguments or missing closing parenthesis')
            nodes.append(TypstDirective(match[1],index,cursor+1,source[index:cursor+1],arguments))
            index=cursor+1;literal_start=index
        if literal_start<len(source):nodes.append(TypstDirective('literal',literal_start,len(source),source[literal_start:]))
        return tuple(nodes)

    @staticmethod
    def value_source(value):
        """Render data as quoted Typst values and tables, never source interpolation."""
        if isinstance(value,list) and value and all(isinstance(row,list) for row in value):
            width=len(value[0])
            if not 1<=width<=16 or len(value)>1000 or any(len(row)!=width for row in value):
                raise ValueError('Dynamic table must be rectangular within the publication budget')
            return '#table(columns: '+str(width)+', '+', '.join('text('+_literal(cell if isinstance(cell,str) else canonical_json(cell))+')' for row in value for cell in row)+')'
        if isinstance(value,dict):
            if len(value)>128:raise ValueError('Dynamic object table exceeds publication budget')
            cells=[]
            for key,cell in value.items():cells.extend((str(key),cell if isinstance(cell,str) else canonical_json(cell)))
            return '#table(columns: 2, '+', '.join('text('+_literal(v)+')' for v in cells)+')'
        text=value if isinstance(value,str) else canonical_json(value)
        if len(text)>65536:raise ValueError('Dynamic publication value exceeds byte budget')
        return '#text('+_literal(text)+')'

    def evaluate(self, source, artifact, *, bindings=None, session=None):
        from ..calc import CalculationSession
        from ..artifacts.bundle import create_bundle
        bundle=LivingPapersCompiler._bundle(artifact);bindings=bindings or {}
        if not isinstance(bindings,dict) or len(bindings)>128:raise ValueError('Bounded binding pointer map required')
        session=CalculationSession() if session is None else session
        pieces=[];receipts=list(bundle['receipts']);executed=[]
        for node in self.parse(source):
            if node.kind=='literal':pieces.append(node.text)
            elif node.kind=='val':
                name=node.arguments[0]
                if name not in bindings:raise ValueError('Unknown dynamic result binding: '+name)
                pieces.append(self.value_source(_pointer(bundle,bindings[name])))
            else:
                operation,arguments=node.arguments
                calculation=session.execute(operation,**arguments)
                record=calculation.to_data()
                receipts.append(record);executed.append({'operation':operation,'receipt':record['content_id']})
                pieces.append(self.value_source(record['result']))
        updated=create_bundle(receipts,datasets=bundle['datasets'],proofs=bundle['proofs'])
        return {'source':''.join(pieces),'bundle':updated,'executed':executed,
                'input_experiment':bundle['content_id'],'output_experiment':updated['content_id']}


class ProvenanceBadgeGenerator:
    """Vector-only audit badge with escaped text, UTC timestamp and local link."""
    @staticmethod
    def svg(experiment_hash, *, timestamp=None, verification_link='audit.html', version=None):
        from .. import __version__
        if not isinstance(experiment_hash,str) or not re.fullmatch('[0-9a-f]{64}',experiment_hash):
            raise ValueError('Canonical SHA-256 experiment identifier required')
        if timestamp is None:instant=datetime.now(timezone.utc)
        elif isinstance(timestamp,datetime):instant=timestamp
        elif isinstance(timestamp,str):
            try:instant=datetime.fromisoformat(timestamp.replace('Z','+00:00'))
            except ValueError as error:raise ValueError('ISO8601 timestamp required') from error
        else:raise ValueError('Timestamp is datetime or ISO8601 string')
        if instant.tzinfo is None or instant.utcoffset() is None:raise ValueError('Timestamp requires explicit timezone')
        canonical=instant.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
        if verification_link!='audit.html' and not re.fullmatch(r'[A-Za-z0-9_.-]+\.html(?:#[A-Za-z0-9_.-]+)?',verification_link):
            raise ValueError('Badge link must name a local HTML audit companion')
        version=__version__ if version is None else version
        if not isinstance(version,str) or not 1<=len(version)<=32:raise ValueError('Bounded version label required')
        escape=lambda value:html.escape(value,quote=True)
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="420" height="72" viewBox="0 0 420 72" role="img" aria-label="Nabla computational provenance">'
                '<a href="'+escape(verification_link)+'"><rect x="1" y="1" width="418" height="70" rx="7" fill="#f2f6f7" stroke="#b9cdd0"/>'
                '<path d="M17 19 L31 48 L45 19 Z" fill="none" stroke="#117879" stroke-width="3"/>'
                '<g font-family="monospace" fill="#172b3a"><text x="58" y="25" font-size="13">NABLA '+escape(version)+' · AUDIT RECORD</text>'
                '<text x="58" y="43" font-size="11">SHA-256 '+experiment_hash[:24]+'…</text>'
                '<text x="58" y="59" font-size="10">'+canonical+'</text></g></a></svg>')


class VerifiablePDFWriter:
    """Write and inspect standard PDF attachments plus an XMP provenance packet.

    XMP and embedded JSON do not establish PDF/A compliance. Optional AES-256
    encryption protects the PDF as a whole and is incompatible with PDF/A.
    Signatures are laboratory envelopes over an experiment/receipt, not a PDF
    digital-signature field or a certificate that the scientific claim is true.
    """
    NAMESPACE='https://nabla.local/ns/provenance/1.0/'

    @classmethod
    def write(cls, source, destination, artifact, *, signature=None, trust=None,
              require_signature=False, password=None):
        from pypdf import PdfReader,PdfWriter
        from pypdf.generic import DecodedStreamObject,NameObject
        from .living_paper import _signature
        bundle=LivingPapersCompiler._bundle(artifact)
        label,lines=_signature(bundle,signature,trust,require_signature)
        raw=_read(source,256*1024*1024)
        if not raw.startswith(b'%PDF-'):raise ValueError('PDF source required')
        target=Path(destination)
        if target.exists() or target.is_symlink():raise FileExistsError('PDF destination must be fresh')
        if password is not None and (not isinstance(password,str) or not 8<=len(password)<=1024):
            raise ValueError('PDF password must have 8–1024 characters')
        reader=PdfReader(io.BytesIO(raw));writer=PdfWriter();writer.append(reader)
        if not 1<=len(reader.pages)<=1000:raise ValueError('PDF page budget exceeded')
        canonical=canonical_json(bundle).encode();digest=hashlib.sha256(canonical).hexdigest()
        payload={'schema':'nabla.pdf-provenance.v1','bundle_sha256':digest,'experiment_hash':bundle['content_id'],
                 'signature':signature,'signature_scope':label,'pdfa_compliance_established':False}
        writer.add_attachment('nabla-experiment.json',canonical)
        writer.add_attachment('nabla-provenance.json',canonical_json(payload).encode())
        xmp=ET.Element('{adobe:ns:meta/}xmpmeta')
        rdf=ET.SubElement(xmp,'{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF')
        description=ET.SubElement(rdf,'{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description')
        for name,value in [('experimentHash',bundle['content_id']),('bundleSHA256',digest),
                           ('bundleBase64',base64.b64encode(canonical).decode()),
                           ('provenanceBase64',base64.b64encode(canonical_json(payload).encode()).decode())]:
            ET.SubElement(description,'{'+cls.NAMESPACE+'}'+name).text=value
        stream=DecodedStreamObject();stream.set_data(ET.tostring(xmp,encoding='utf-8',xml_declaration=True))
        stream[NameObject('/Type')]=NameObject('/Metadata');stream[NameObject('/Subtype')]=NameObject('/XML')
        writer._root_object[NameObject('/Metadata')]=writer._add_object(stream)
        writer.add_metadata({'/NablaExperimentSHA256':bundle['content_id'],'/NablaBundleSHA256':digest})
        if password is not None:writer.encrypt(password,algorithm='AES-256')
        target.parent.mkdir(parents=True,exist_ok=True)
        buffer=io.BytesIO();writer.write(buffer)
        from ..graphics.webgl_exporter import _publish_bytes
        _publish_bytes(target,buffer.getvalue())
        try:
            inspected=cls.inspect(target,password=password,trust=trust,require_signature=require_signature)
            if inspected['bundle']!=bundle:raise ArithmeticError('PDF round-trip changed the experiment')
        except BaseException:
            target.unlink(missing_ok=True);raise
        return {'pdf':str(target),'experiment_hash':bundle['content_id'],'bundle_sha256':digest,
                'encrypted':password is not None,'pdfa_compliance_established':False}

    @classmethod
    def inspect(cls, path, *, password=None, trust=None, require_signature=False):
        from pypdf import PdfReader
        from .living_paper import _signature
        raw=_read(path,256*1024*1024);reader=PdfReader(io.BytesIO(raw))
        encrypted=reader.is_encrypted
        if encrypted and (password is None or not reader.decrypt(password)):
            raise ValueError('PDF decryption password required or invalid')
        attachments=reader.attachments
        if 'nabla-experiment.json' not in attachments or 'nabla-provenance.json' not in attachments:
            raise ValueError('PDF lacks Nabla experiment/provenance attachments')
        if len(attachments['nabla-experiment.json'])!=1 or len(attachments['nabla-provenance.json'])!=1:
            raise ValueError('Ambiguous duplicate Nabla PDF attachments')
        bundle_raw=attachments['nabla-experiment.json'][0];provenance_raw=attachments['nabla-provenance.json'][0]
        if len(bundle_raw)>_MAX_BYTES or len(provenance_raw)>_MAX_BYTES:raise ValueError('PDF attachment budget exceeded')
        bundle=json.loads(bundle_raw);provenance=json.loads(provenance_raw)
        if not verify_bundle(bundle) or bundle_raw!=canonical_json(bundle).encode():raise ValueError('PDF experiment is not an intact canonical bundle')
        digest=hashlib.sha256(bundle_raw).hexdigest()
        if provenance.get('schema')!='nabla.pdf-provenance.v1' or provenance.get('bundle_sha256')!=digest or provenance.get('experiment_hash')!=bundle['content_id']:
            raise ValueError('PDF provenance binding failed')
        metadata=reader.trailer['/Root'].get('/Metadata')
        if metadata is None:raise ValueError('PDF XMP provenance missing')
        xml=metadata.get_object().get_data()
        if len(xml)>3*_MAX_BYTES:raise ValueError('XMP byte budget exceeded')
        root=ET.fromstring(xml)
        def field(name):
            elements=root.findall('.//{'+cls.NAMESPACE+'}'+name)
            if len(elements)!=1 or elements[0].text is None:raise ValueError('Missing or duplicate XMP '+name)
            return elements[0].text
        if field('experimentHash')!=bundle['content_id'] or field('bundleSHA256')!=digest or base64.b64decode(field('bundleBase64'),validate=True)!=bundle_raw or base64.b64decode(field('provenanceBase64'),validate=True)!=provenance_raw:
            raise ValueError('XMP and attached experiment differ')
        label,_=_signature(bundle,provenance['signature'],trust,require_signature)
        if label!=provenance['signature_scope']:raise ValueError('Signature scope label changed')
        return {'bundle':bundle,'provenance':provenance,'encrypted':encrypted,'pages':len(reader.pages),
                'integrity_verified':True,'signature_verified':provenance['signature'] is not None,
                'pdfa_compliance_established':False}


@dataclass(frozen=True)
class ReactiveBuild:
    pdf: Path
    artifact: Path
    source: Path
    manifest: Path
    experiment_hash: str
    revision: str
    changed: bool


class PaperWatchHandle:
    """Explicit lifecycle and error reporting for a background publication watch."""
    def __init__(self, compiler, delay):
        self.compiler=compiler;self.delay=delay;self.stop_event=Event()
        self.started=Event();self.finished=Event();self.last_build=None;self.error=None
        self.build_count=0;self.last_duration_seconds=None;self._lock=RLock()
        self.thread=Thread(target=self._run,name='nabla-living-paper-watch',daemon=True)
        self.thread.start();self.started.wait(timeout=5)

    def _run(self):
        self.started.set();previous=None
        try:
            while not self.stop_event.is_set():
                identity=self.compiler.input_identity()
                if identity!=previous:
                    started=time.monotonic()
                    result=self.compiler.build()
                    with self._lock:
                        self.last_build=result;self.build_count+=int(result.changed)
                        self.last_duration_seconds=time.monotonic()-started
                    previous=identity
                self.stop_event.wait(self.delay)
        except BaseException as error:
            with self._lock:self.error=error
        finally:self.finished.set()

    def status(self):
        with self._lock:
            return {'running':self.thread.is_alive(),'build_count':self.build_count,
                    'last_duration_seconds':self.last_duration_seconds,
                    'error':None if self.error is None else type(self.error).__name__+': '+str(self.error),
                    'last_revision':None if self.last_build is None else self.last_build.revision}

    def stop(self, timeout=10):
        if type(timeout) not in (int,float) or not 0<=timeout<=600:raise ValueError('Watch stop timeout must be 0–600 seconds')
        self.stop_event.set();self.thread.join(timeout=timeout)
        if self.thread.is_alive():raise TimeoutError('Renderer is still finishing; watch stop deadline exceeded')
        if self.error is not None:raise self.error
        return self.status()

    def wait_for_build(self, count=1, timeout=30):
        if type(count) is not int or count<1 or not 0<timeout<=600:raise ValueError('Invalid watch wait budget')
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            with self._lock:
                if self.error is not None:raise self.error
                if self.build_count>=count:return self.last_build
            if self.finished.wait(min(.05,max(0,deadline-time.monotonic()))):break
        raise TimeoutError('Requested watch build was not observed before the deadline')

    def __enter__(self):return self

    def __exit__(self,*exception):self.stop()


class LivingPaperCompiler:
    """Compile trusted dynamic templates and react to artifacts/session receipts.

    Each immutable revision records its source, artifact, renderer and output
    hashes. A stable output PDF is published atomically from the completed
    revision. Sub-second builds are a measurable performance outcome, not a
    correctness promise of the watch interval. Typst is the default renderer;
    LaTeX fallback requires an explicit .tex template, not an unreliable
    automatic translation from arbitrary Typst programs.
    """
    def __init__(self, template, artifact, output, *, bindings=None, timeout=60,
                 title='Nabla living paper', authors=(), trust=None,
                 require_signature=False, signature=None, latex_fallback=None,
                 figures=(), asset_root=None):
        self.template=Path(template);self.artifact=artifact;self.output=Path(output)
        if self.template.suffix.lower() not in ('.typ','.tex'):
            raise ValueError('Template suffix must be .typ or .tex')
        if not isinstance(bindings if bindings is not None else {},dict):raise ValueError('Binding map required')
        if not isinstance(title,str) or not title.strip() or len(title)>4096:raise ValueError('Bounded title required')
        self.bindings=bindings or {};self.timeout=timeout;self.title=title;self.authors=tuple(authors)
        self.trust=trust;self.require_signature=require_signature;self.signature=signature
        self.latex_fallback=None if latex_fallback is None else Path(latex_fallback)
        if self.latex_fallback is not None and self.latex_fallback.suffix.lower()!='.tex':
            raise ValueError('Fallback must be an explicit trusted .tex template')
        if not isinstance(figures,(list,tuple)) or len(figures)>32 or (figures and asset_root is None):
            raise ValueError('At most 32 explicit figures with asset_root allowed')
        self.figures=tuple(dict(v) for v in figures)
        self.asset_root=None if asset_root is None else Path(asset_root).resolve()
        self.engine=TypstTemplateEngine();self.renderer=TypstCompiler(timeout=timeout,trust=trust,require_signature=require_signature)
        self._lock=RLock();self._observed=[];self._last_identity=None;self._last_result=None
        self._watch=None

    def receive(self, record):
        """CalculationSession receipt_sink callback; retained records are bounded."""
        from ..calc.receipt import verify_receipt
        if not verify_receipt(record):raise ValueError('Watch received an invalid audit receipt')
        canonical=json.loads(canonical_json(record))
        with self._lock:
            if len(self._observed)>=1000:raise BufferError('Living-paper receipt history reached the bundle budget')
            self._observed.append(canonical)

    def session(self, *, background_receipts=True):
        from ..calc import CalculationSession
        return CalculationSession(background_receipts=background_receipts,receipt_sink=self.receive)

    def _current_bundle(self):
        from ..artifacts.bundle import create_bundle
        bundle=LivingPapersCompiler._bundle(self.artifact)
        receipts=list(bundle['receipts'])
        identities={r['content_id'] for r in receipts}
        for receipt in self._observed:
            if receipt['content_id'] not in identities:
                receipts.append(receipt);identities.add(receipt['content_id'])
        return create_bundle(receipts,datasets=bundle['datasets'],proofs=bundle['proofs'])

    def input_identity(self):
        from ..core.semantic_ir import fingerprint
        with self._lock:
            source=_read(self.template,1048576).decode('utf-8')
            bundle=self._current_bundle()
            fallback=None if self.latex_fallback is None else _read(self.latex_fallback,1048576).decode('utf-8')
            return fingerprint({'source':source,'bundle':bundle,'bindings':self.bindings,
                                'title':self.title,'authors':self.authors,'signature':self.signature,
                                'fallback':fallback,'figures':self._figure_identities()})

    def _figure_identities(self):
        result=[]
        for figure in self.figures:
            if set(figure)!={'path','caption'} or not isinstance(figure['caption'],str) or len(figure['caption'])>4096:
                raise ValueError('Figures require path and bounded caption')
            path=Path(figure['path'])
            path=path if path.is_absolute() else self.asset_root/path
            if path.is_symlink() or not path.resolve().is_relative_to(self.asset_root) or path.suffix.lower() not in ('.png','.jpg','.jpeg','.svg'):
                raise ValueError('Figure escapes its asset root or uses an unsupported format')
            raw=_read(path)
            result.append({'path':str(path.resolve()),'caption':figure['caption'],
                           'sha256':hashlib.sha256(raw).hexdigest()})
        return result

    @staticmethod
    def _latex_values(source, bundle, bindings):
        def replace(match):
            name=match[1]
            if name not in bindings:raise ValueError('Unknown LaTeX result binding: '+name)
            value=_pointer(bundle,bindings[name])
            return _latex(value if isinstance(value,str) else canonical_json(value))
        return _BINDING.sub(replace,source)

    def _compile_latex(self, source, bundle, stage):
        import shutil
        from ..artifacts.process import run_renderer
        executable=shutil.which('lualatex') or shutil.which('xelatex')
        if executable is None:raise ImportError('Install LuaLaTeX or XeLaTeX for the explicit LaTeX template')
        body=self._latex_values(source,bundle,self.bindings)
        (stage/'paper.tex').write_text(body,encoding='utf-8')
        command=[executable,'--no-shell-escape','-interaction=nonstopmode','-halt-on-error',
                 '-output-directory='+str(stage),str(stage/'paper.tex')]
        run_renderer(command,cwd=stage,timeout=self.timeout)
        if not (stage/'paper.pdf').is_file():raise RuntimeError('LaTeX did not produce a PDF')
        (stage/'paper.pdf').rename(stage/'latex-rendered.pdf')
        return stage/'latex-rendered.pdf',body,Path(executable).name

    def build(self):
        from ..core.semantic_ir import fingerprint
        from .living_paper import _signature
        import os
        with self._lock:
            identity=self.input_identity()
            if self._last_identity==identity and self._last_result is not None:
                if self.output.is_file() and VerifiablePDFWriter.inspect(self.output,trust=self.trust,require_signature=self.require_signature)['bundle']['content_id']==self._last_result.experiment_hash:
                    old=self._last_result
                    return ReactiveBuild(old.pdf,old.artifact,old.source,old.manifest,old.experiment_hash,old.revision,False)
            original=_read(self.template,1048576).decode('utf-8');bundle=self._current_bundle()
            # Validate a signature's actual scope before running any renderer.
            _signature(bundle,self.signature,self.trust,self.require_signature)
            if self.template.suffix.lower()=='.typ':
                evaluated=self.engine.evaluate(original,bundle,bindings=self.bindings)
                source=evaluated['source'];bundle=evaluated['bundle']
                if self.signature is not None:
                    _signature(bundle,self.signature,self.trust,self.require_signature)
            else:source=original
            revision=fingerprint({'input_id':identity,'evaluated_bundle':bundle,'evaluated_source':source})
            root=self.output.parent/(self.output.name+'.revisions')
            if root.is_symlink() or self.output.is_symlink():raise ValueError('Publication paths must not be symlinks')
            root.mkdir(parents=True,exist_ok=True)
            final=root/revision
            if final.exists():
                if not (final/'manifest.json').is_file():raise ValueError('Existing incomplete publication revision')
                metadata=json.loads(_read(final/'manifest.json'))
                if metadata['pdf_sha256']!=hashlib.sha256(_read(final/'paper.pdf',256*1024*1024)).hexdigest():
                    raise ValueError('Existing publication revision was altered')
                VerifiablePDFWriter.inspect(final/'paper.pdf',trust=self.trust,require_signature=self.require_signature)
            else:
                with tempfile.TemporaryDirectory(prefix='.revision-',dir=root) as temporary:
                    stage=Path(temporary)/'completed';stage.mkdir()
                    (stage/'artifact.json').write_text(canonical_json(bundle),encoding='utf-8')
                    (stage/'template.source').write_text(original,encoding='utf-8')
                    (stage/'provenance-badge.svg').write_text(ProvenanceBadgeGenerator.svg(bundle['content_id']),encoding='utf-8')
                    if self.template.suffix.lower()=='.typ':
                        template=stage/'evaluated.typ'
                        decorated=source+'\n#figure(link("audit.html", image("assets/figure-'+str(len(self.figures))+'.svg", width: 82mm)))\n'
                        template.write_text(decorated,encoding='utf-8')
                        render_figures=[]
                        for index,figure in enumerate(self._figure_identities()):
                            original_asset=Path(figure['path'])
                            local=stage/('figure-input-'+str(index)+original_asset.suffix.lower())
                            local.write_bytes(_read(original_asset))
                            render_figures.append({'path':local.name,'caption':figure['caption']})
                        render_figures.append({'path':'provenance-badge.svg','caption':'Computational provenance'})
                        try:
                            publication=self.renderer.compile(bundle,stage/'rendered.pdf',template=template,
                                figures=render_figures,
                                asset_root=stage,title=self.title,authors=self.authors,signature=self.signature)
                            rendered=publication.pdf;renderer='typst';compiled_source=decorated
                        except (ImportError,FileNotFoundError) as unavailable:
                            if self.latex_fallback is None:raise
                            fallback=_read(self.latex_fallback,1048576).decode('utf-8')
                            rendered,compiled_source,renderer=self._compile_latex(fallback,bundle,stage)
                    else:
                        rendered,compiled_source,renderer=self._compile_latex(source,bundle,stage)
                    VerifiablePDFWriter.write(rendered,stage/'paper.pdf',bundle,signature=self.signature,
                                              trust=self.trust,require_signature=self.require_signature)
                    (stage/'compiled.source').write_text(compiled_source,encoding='utf-8')
                    companion={'title':self.title,'authors':list(self.authors),'abstract':'Computational audit companion',
                               'language':'en','blocks':[{'kind':'paragraph','text':'This document contains the canonical experiment attached to the PDF.'}]}
                    (stage/'audit.html').write_text(LivingPapersCompiler._html(companion,bundle,{}),encoding='utf-8')
                    metadata={'schema':'nabla.reactive-paper.v1','input_id':identity,'revision':revision,
                              'experiment_hash':bundle['content_id'],'renderer':renderer,
                              'pdf_sha256':hashlib.sha256(_read(stage/'paper.pdf',256*1024*1024)).hexdigest(),
                              'source_sha256':hashlib.sha256(compiled_source.encode()).hexdigest(),
                              'scientific_claims_certified':False}
                    (stage/'manifest.json').write_text(canonical_json(metadata),encoding='utf-8')
                    stage.rename(final)
            self.output.parent.mkdir(parents=True,exist_ok=True)
            # Stable PDF and audit companion are conveniences; immutable revisions
            # contain the complete mutually bound experiment and build evidence.
            for name,target in [('paper.pdf',self.output),('audit.html',self.output.parent/'audit.html')]:
                descriptor,temporary=tempfile.mkstemp(prefix='.nabla-live-',dir=target.parent)
                try:
                    with os.fdopen(descriptor,'wb') as stream:
                        stream.write(_read(final/name,256*1024*1024));stream.flush();os.fsync(stream.fileno())
                    os.replace(temporary,target)
                finally:Path(temporary).unlink(missing_ok=True)
            result=ReactiveBuild(self.output,final/'artifact.json',final/'compiled.source',final/'manifest.json',bundle['content_id'],revision,True)
            self._last_identity=identity;self._last_result=result
            return result

    def watch(self, delay=.2):
        if type(delay) not in (int,float) or not .05<=delay<=60:raise ValueError('Watch delay must be .05–60 seconds')
        with self._lock:
            if self._watch is not None and self._watch.thread.is_alive():raise RuntimeError('This compiler already has an active watch')
            handle=PaperWatchHandle(self,delay);self._watch=handle
            return handle

    @staticmethod
    def inspect(path, **policy):
        return VerifiablePDFWriter.inspect(path,**policy)


__all__ += ['TypstDirective','TypstTemplateEngine','ProvenanceBadgeGenerator',
            'VerifiablePDFWriter','ReactiveBuild','PaperWatchHandle','LivingPaperCompiler']


def provenance_badge(experiment_hash, timestamp, verification_link='audit.html'):
    return {'format':'svg','source':ProvenanceBadgeGenerator.svg(experiment_hash,timestamp=timestamp,verification_link=verification_link)}


__all__ += ['provenance_badge']

# Scientific editorial semantics: numbers, equations, labels and references.
from decimal import Decimal, localcontext, InvalidOperation
from fractions import Fraction
from urllib.parse import urlsplit


class ScientificNumberFormatter:
    """Round uncertainty and value together using decimal, not binary rounding.

    Formatting is a presentation operation: the original exact values remain
    in the experiment. Significant-digit rounding never mutates a receipt or
    upgrades a floating estimate into an exact mathematical statement.
    """
    @staticmethod
    def decimal(value):
        if isinstance(value,bool):raise ValueError('Boolean is not a scientific numeric value')
        if isinstance(value,Fraction):
            if max(value.numerator.bit_length(),value.denominator.bit_length())>4096:raise ValueError('Numeric formatting bit budget exceeded')
            with localcontext() as context:
                context.prec=128
                result=Decimal(value.numerator)/Decimal(value.denominator)
        elif isinstance(value,(str,int,float,Decimal)):
            if len(str(value))>4096:raise ValueError('Numeric formatting character budget exceeded')
            try:
                if isinstance(value,str) and '/' in value:
                    fraction=Fraction(value)
                    return ScientificNumberFormatter.decimal(fraction)
                result=Decimal(str(value))
            except (InvalidOperation,ValueError,ZeroDivisionError) as error:raise ValueError('Finite decimal or rational value required') from error
        else:raise ValueError('Unsupported scientific numeric value')
        if not result.is_finite() or abs(result.adjusted())>10000:raise ValueError('Nonfinite or excessive numeric exponent')
        return result

    @classmethod
    def significant(cls, value, digits=6, *, notation='auto'):
        if type(digits) is not int or not 1<=digits<=64 or notation not in ('auto','fixed','scientific'):
            raise ValueError('Invalid significant-digit presentation policy')
        number=cls.decimal(value)
        with localcontext() as context:
            context.prec=max(128,digits+abs(number.adjusted())+4)
            exponent=number.adjusted() if number else 0
            quantum=Decimal(1).scaleb(exponent-digits+1)
            rounded=number.quantize(quantum)
            rounded_exponent=rounded.adjusted() if rounded else 0
            if rounded and rounded_exponent!=exponent:
                exponent=rounded_exponent
                quantum=Decimal(1).scaleb(exponent-digits+1)
                rounded=number.quantize(quantum)
            scientific=notation=='scientific' or (notation=='auto' and (exponent>=digits or exponent<=-4))
            if scientific:
                coefficient=rounded.scaleb(-exponent)
                return format(coefficient,f'.{digits-1}f')+'e'+str(exponent)
            places=max(0,digits-1-exponent)
            return format(rounded,f'.{places}f')

    @classmethod
    def uncertainty(cls, value, uncertainty, *, uncertainty_digits=2, unit=''):
        if type(uncertainty_digits) is not int or not 1<=uncertainty_digits<=4:
            raise ValueError('Uncertainty precision must be 1–4 significant digits')
        number=cls.decimal(value);error=cls.decimal(uncertainty)
        if error<=0:raise ValueError('A strictly positive uncertainty is required')
        if not isinstance(unit,str) or len(unit)>256:raise ValueError('Bounded unit label required')
        with localcontext() as context:
            context.prec=128+max(abs(number.adjusted()),abs(error.adjusted()))
            exponent=error.adjusted()-uncertainty_digits+1;quantum=Decimal(1).scaleb(exponent)
            rounded_error=error.quantize(quantum)
            # A carry in uncertainty can change its leading decimal position.
            if rounded_error.adjusted()!=error.adjusted():
                exponent=rounded_error.adjusted()-uncertainty_digits+1;quantum=Decimal(1).scaleb(exponent)
                rounded_error=error.quantize(quantum)
            rounded_value=number.quantize(quantum);places=max(0,-exponent)
            return {'value':format(rounded_value,f'.{places}f'),
                    'uncertainty':format(rounded_error,f'.{places}f'),'unit':unit,
                    'text':format(rounded_value,f'.{places}f')+' ± '+format(rounded_error,f'.{places}f')+(' '+unit if unit else ''),
                    'rounding_quantum':str(quantum),'original_value':str(number),'original_uncertainty':str(error)}


class ScientificEquation:
    """A closed arithmetic equation rendered to native Typst math and LaTeX.

    This parser accepts a scalar expression or a single relation between two
    scalar expressions. It does not accept arbitrary TeX macros, file includes
    or Typst function calls. The equation's truth is not implied by typesetting.
    """
    def __init__(self, source, variables):
        from ..math._structured import expression,names
        self.variables=names(variables,16)
        if not isinstance(source,str) or len(source)>8192:raise ValueError('Bounded equation source required')
        matches=list(re.finditer(r'<=|>=|!=|=|<|>',source))
        if len(matches)>1:raise ValueError('Use one relation per scientific equation')
        self.relation=None
        if matches:
            relation=matches[0];self.relation=relation[0]
            self.left=expression(source[:relation.start()],self.variables)[0]
            self.right=expression(source[relation.end():],self.variables)[0]
        else:self.left=expression(source,self.variables)[0];self.right=None
        self.source=source

    @staticmethod
    def _typst(value):
        from ..math._structured import sympy
        sp=sympy()
        if value==sp.pi:return 'pi'
        if value==sp.I:return 'upright("i")'
        if isinstance(value,sp.Symbol):
            name=str(value)
            greek={'alpha','beta','gamma','delta','epsilon','zeta','eta','theta','iota','kappa','lambda','mu','nu','xi','omicron','pi','rho','sigma','tau','upsilon','phi','chi','psi','omega'}
            if name in greek:return name
            return name if len(name)==1 and name.isalpha() else 'upright('+_literal(name)+')'
        if isinstance(value,sp.Integer):return str(value)
        if isinstance(value,sp.Rational):return 'frac('+str(value.p)+','+str(value.q)+')'
        if isinstance(value,sp.Add):
            terms=[]
            for index,term in enumerate(value.as_ordered_terms()):
                negative=term.could_extract_minus_sign();piece=ScientificEquation._typst(-term if negative else term)
                terms.append(('-' if negative else '+' if index else '')+piece)
            return ' '.join(terms)
        if isinstance(value,sp.Mul):
            numerator,denominator=sp.fraction(value)
            if denominator!=1:return 'frac('+ScientificEquation._typst(numerator)+','+ScientificEquation._typst(denominator)+')'
            return ' dot '.join('('+ScientificEquation._typst(v)+')' for v in value.as_ordered_factors())
        if isinstance(value,sp.Pow):
            if value.exp==sp.Rational(1,2):return 'sqrt('+ScientificEquation._typst(value.base)+')'
            return '('+ScientificEquation._typst(value.base)+')^('+ScientificEquation._typst(value.exp)+')'
        allowed={sp.sin:'sin',sp.cos:'cos',sp.tan:'tan',sp.exp:'exp',sp.log:'ln',sp.sinh:'sinh',sp.cosh:'cosh',sp.tanh:'tanh',sp.Abs:'abs',sp.erf:'upright("erf")'}
        if value.func in allowed and len(value.args)==1:
            return allowed[value.func]+'('+ScientificEquation._typst(value.args[0])+')'
        raise ValueError('Equation expression has an unsupported presentation node')

    def typst(self, *, numbered=True):
        if type(numbered) is not bool:raise ValueError('numbered must be boolean')
        relation={'=':'=','!=':'!=','<':'<','>':'>','<=':'<=','>=':'>='}
        body=self._typst(self.left)
        if self.right is not None:body+=' '+relation[self.relation]+' '+self._typst(self.right)
        return '#math.equation(block: true, numbering: '+('"(1)"' if numbered else 'none')+')[$ '+body+' $]'

    def latex(self):
        from ..math._structured import sympy
        sp=sympy();body=sp.latex(self.left)
        relations={'=':'=','!=':r'\ne','<':'<','>':'>','<=':r'\le','>=':r'\ge'}
        if self.right is not None:body+=' '+relations[self.relation]+' '+sp.latex(self.right)
        return body

    def html(self):
        # Source text remains usable without MathJax/CDN. LaTeX is exposed as
        # escaped data for optional downstream math renderers, never executable.
        return '<div class="equation" data-latex="'+html.escape(self.latex(),quote=True)+'">'+equation_mathml(self)+'</div>'


class LabelRegistry:
    """Deterministic typed numbering with duplicate and dangling-reference checks."""
    def __init__(self):
        self._labels={};self._counts={};self._references=[]

    @staticmethod
    def validate(label):
        if not isinstance(label,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.:-]{0,95}',label):
            raise ValueError('Label must be a bounded public identifier')
        return label

    def define(self, label, kind):
        self.validate(label)
        if kind not in ('section','equation','figure','table','reference','appendix'):raise ValueError('Unknown scientific label kind')
        if label in self._labels:raise ValueError('Duplicate scientific label: '+label)
        number=self._counts.get(kind,0)+1;self._counts[kind]=number
        self._labels[label]={'kind':kind,'number':number}
        return dict(self._labels[label])

    def reference(self, label):
        self.validate(label);self._references.append(label)
        return label

    def resolve(self, label):
        self.validate(label)
        if label not in self._labels:raise ValueError('Dangling scientific reference: '+label)
        value=self._labels[label]
        return {'label':label,**value,'text':value['kind'].capitalize()+' '+str(value['number'])}

    def validate_all(self):
        for label in self._references:self.resolve(label)
        return {'labels':{k:dict(v) for k,v in self._labels.items()},'references':list(self._references)}


class Bibliography:
    """Validated CSL-like records and escaped local BibTeX/HTML renderings.

    References identify their submitted metadata. No DOI lookup, peer-review
    authenticity or novelty search is inferred from syntactically valid fields.
    """
    def __init__(self, entries):
        if not isinstance(entries,(list,tuple)) or len(entries)>1000:raise ValueError('At most 1000 bibliography entries allowed')
        self.entries={}
        for entry in entries:
            if not isinstance(entry,dict) or set(entry)-{'id','type','title','authors','year','container','volume','issue','pages','doi','url','publisher'}:
                raise ValueError('Unknown bibliography fields')
            key=LabelRegistry.validate(entry.get('id'))
            if key in self.entries:raise ValueError('Duplicate bibliography identifier: '+key)
            kind=entry.get('type','article')
            if kind not in ('article','book','dataset','software','proceedings','preprint'):raise ValueError('Unsupported reference type')
            title=entry.get('title')
            if not isinstance(title,str) or not title.strip() or len(title)>4096:raise ValueError('Reference title required')
            authors=entry.get('authors',[])
            if not isinstance(authors,list) or len(authors)>256 or any(not isinstance(a,str) or not a.strip() or len(a)>256 for a in authors):
                raise ValueError('Reference authors must be bounded names')
            year=entry.get('year')
            if type(year) is not int or not 1<=year<=9999:raise ValueError('Reference year must be explicit')
            for name in ('container','volume','issue','pages','publisher'):
                if name in entry and (not isinstance(entry[name],str) or len(entry[name])>4096):raise ValueError('Invalid reference '+name)
            doi=entry.get('doi')
            if doi is not None and (not isinstance(doi,str) or not re.fullmatch(r'10\.[0-9]{4,9}/[^\s<>"{}]{1,256}',doi)):
                raise ValueError('Invalid DOI syntax')
            url=entry.get('url')
            if url is not None:
                if not isinstance(url,str) or len(url)>4096:raise ValueError('Invalid reference URL')
                parsed=urlsplit(url)
                if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.username or parsed.password:
                    raise ValueError('Reference URL must be an HTTP(S) URL without credentials')
            self.entries[key]={**entry,'type':kind,'authors':list(authors)}

    def cite(self, identifiers):
        if not isinstance(identifiers,(list,tuple)) or not 1<=len(identifiers)<=32:raise ValueError('Citation supports 1–32 references')
        for key in identifiers:
            if key not in self.entries:raise ValueError('Unknown cited reference: '+str(key))
        return '['+'; '.join((', '.join(self.entries[key]['authors'][:1]) or self.entries[key]['title'])+', '+str(self.entries[key]['year']) for key in identifiers)+']'

    def text(self, key):
        if key not in self.entries:raise ValueError('Unknown bibliography identifier')
        entry=self.entries[key];parts=[]
        if entry['authors']:parts.append('; '.join(entry['authors']))
        parts.extend((str(entry['year']),entry['title']))
        for name in ('container','volume','issue','pages','publisher'):
            if entry.get(name):parts.append(entry[name])
        if entry.get('doi'):parts.append('doi:'+entry['doi'])
        elif entry.get('url'):parts.append(entry['url'])
        return '. '.join(parts)+'.'

    def html(self):
        rows=[]
        for key in self.entries:
            rows.append('<li id="ref-'+html.escape(key,quote=True)+'">'+html.escape(self.text(key))+'</li>')
        return '<ol class="bibliography">'+''.join(rows)+'</ol>'

    def bibtex(self):
        result=[]
        kinds={'article':'article','book':'book','proceedings':'inproceedings',
               'preprint':'misc','dataset':'misc','software':'misc'}
        for key,entry in self.entries.items():
            # BibTeX keys use a stricter alphabet than document cross-references.
            safe=re.sub('[^A-Za-z0-9_.:-]','_',key)
            fields={'title':entry['title'],'year':str(entry['year']),
                    'author':' and '.join(entry['authors'])}
            for name in ('volume','issue','pages','doi','url','publisher'):
                if entry.get(name):fields['number' if name=='issue' else name]=entry[name]
            if entry.get('container'):fields['journal' if entry['type']=='article' else 'booktitle']=entry['container']
            result.append('@'+kinds[entry['type']]+'{'+safe+',\n'+',\n'.join('  '+name+' = {'+_latex(value)+'}' for name,value in fields.items())+'\n}')
        return '\n\n'.join(result)+'\n'


@dataclass(frozen=True)
class JournalStyle:
    """Explicit typographic profiles; none impersonates an official journal."""
    name: str = 'research'
    columns: int = 1
    body_points: float = 10.5
    margin_mm: float = 22.
    accent: str = '117879'

    def __post_init__(self):
        if self.name not in ('research','compact','two-column') or type(self.columns) is not int or self.columns not in (1,2):
            raise ValueError('Unknown journal profile/column count')
        if not 8<=self.body_points<=14 or not 15<=self.margin_mm<=35 or not re.fullmatch('[0-9a-fA-F]{6}',self.accent):
            raise ValueError('Invalid journal typography policy')

    @classmethod
    def profile(cls, name):
        if name=='research':return cls()
        if name=='compact':return cls(name='compact',body_points=9.5,margin_mm=18.)
        if name=='two-column':return cls(name='two-column',columns=2,body_points=9.5,margin_mm=18.)
        raise ValueError('Journal profile is research, compact or two-column')

    def typst_settings(self):
        return ('#set text(size: '+str(self.body_points)+'pt)\n'
                '#set page(margin: (left: '+str(self.margin_mm)+'mm, right: '+str(self.margin_mm)+'mm, top: 23mm, bottom: 35mm))\n'
                '#let journal-accent = rgb("'+self.accent+'")\n')


__all__ += ['ScientificNumberFormatter','ScientificEquation','LabelRegistry',
            'Bibliography','JournalStyle']


class ScientificPaper:
    """Typed editorial AST with equations, references, captions and cross-links.

    Mathematical equations use ScientificEquation instead of arbitrary markup.
    Figure paths are resolved only within a declared asset root during build.
    Generated labels are semantic IDs, not hashes of mutable page numbering.
    """
    def __init__(self, title, *, authors=(), abstract='', language='en',
                 bibliography=(), style='research'):
        if not isinstance(title,str) or not title.strip() or len(title)>4096:raise ValueError('Bounded paper title required')
        if not isinstance(authors,(list,tuple)) or len(authors)>64 or any(not isinstance(a,str) or not a.strip() or len(a)>256 for a in authors):
            raise ValueError('Named authors within the paper budget required')
        if not isinstance(abstract,str) or len(abstract)>16384 or language not in ('pt','en','es','fr','de'):
            raise ValueError('Invalid paper abstract or language')
        self.title=title;self.authors=tuple(authors);self.abstract=abstract;self.language=language
        self.bibliography=Bibliography(bibliography)
        self.style=JournalStyle.profile(style);self.labels=LabelRegistry();self.blocks=[]
        for key in self.bibliography.entries:self.labels.define('ref:'+key,'reference')

    @staticmethod
    def _text(value, maximum=65536):
        if not isinstance(value,str) or len(value)>maximum:raise ValueError('Bounded editorial text required')
        return value

    def _append(self, block):
        if len(self.blocks)>=1000:raise ValueError('Scientific paper block budget exceeded')
        self.blocks.append(block);return self

    def section(self, title, label, *, level=1):
        self._text(title,4096)
        if type(level) is not int or not 1<=level<=3:raise ValueError('Section level must be 1–3')
        number=self.labels.define(label,'section')
        return self._append({'kind':'section','title':title,'label':label,'level':level,'number':number['number']})

    def paragraph(self, text):
        return self._append({'kind':'paragraph','text':self._text(text)})

    def equation(self, source, variables, label):
        equation=ScientificEquation(source,variables);number=self.labels.define(label,'equation')
        return self._append({'kind':'equation','source':source,'variables':list(equation.variables),
                             'label':label,'number':number['number']})

    def table(self, headers, rows, caption, label, *, units=None):
        if not isinstance(headers,(list,tuple)) or not 1<=len(headers)<=16 or not isinstance(rows,(list,tuple)) or len(rows)>2000:
            raise ValueError('Scientific table dimensions exceed the publication budget')
        self._text(caption,4096)
        normalized=[]
        for row in rows:
            if not isinstance(row,(list,tuple)) or len(row)!=len(headers):raise ValueError('Scientific table must be rectangular')
            normalized.append([self._text(v,8192) if isinstance(v,str) else canonical_json(v) for v in row])
        if units is not None and (len(units)!=len(headers) or any(not isinstance(v,str) or len(v)>256 for v in units)):
            raise ValueError('One unit label per table column required')
        number=self.labels.define(label,'table')
        return self._append({'kind':'table','headers':[self._text(v,4096) for v in headers],
                             'rows':normalized,'caption':caption,'label':label,'number':number['number'],
                             'units':list(units) if units is not None else None})

    def figure(self, path, caption, label, *, width=.9):
        self._text(path,4096);self._text(caption,4096)
        if type(width) not in (int,float) or not 0<width<=1:raise ValueError('Figure relative width must lie in (0,1]')
        number=self.labels.define(label,'figure')
        return self._append({'kind':'figure','path':path,'caption':caption,'label':label,
                             'number':number['number'],'width':width})

    def citation(self, identifiers):
        text=self.bibliography.cite(identifiers)
        for key in identifiers:self.labels.reference('ref:'+key)
        return self._append({'kind':'citation','identifiers':list(identifiers),'text':text})

    def reference(self, label, *, prefix=''):
        self.labels.reference(label);self._text(prefix,4096)
        return self._append({'kind':'reference','label':label,'prefix':prefix})

    def footnote(self, text):
        return self._append({'kind':'footnote','text':self._text(text,8192)})

    def validate(self):
        labels=self.labels.validate_all()
        if not self.blocks:raise ValueError('A scientific paper needs at least one content block')
        for block in self.blocks:
            if block['kind']=='equation':ScientificEquation(block['source'],block['variables'])
        return {'blocks':len(self.blocks),'labels':labels,'bibliography_entries':len(self.bibliography.entries)}

    def to_data(self):
        self.validate()
        return {'schema':'nabla.scientific-paper.v1','title':self.title,'authors':list(self.authors),
                'abstract':self.abstract,'language':self.language,'style':self.style.name,
                'bibliography':list(self.bibliography.entries.values()),'blocks':json.loads(canonical_json(self.blocks))}

    @classmethod
    def from_data(cls, value):
        if not isinstance(value,dict) or set(value)!={'schema','title','authors','abstract','language','style','bibliography','blocks'} or value['schema']!='nabla.scientific-paper.v1':
            raise ValueError('Unknown scientific-paper AST contract')
        paper=cls(value['title'],authors=value['authors'],abstract=value['abstract'],language=value['language'],
                  bibliography=value['bibliography'],style=value['style'])
        if not isinstance(value['blocks'],list) or len(value['blocks'])>1000:raise ValueError('Scientific-paper AST exceeds block budget')
        for block in value['blocks']:
            if not isinstance(block,dict):raise ValueError('Scientific-paper block must be an object')
            kind=block.get('kind')
            if kind=='section' and set(block)=={'kind','title','label','level','number'}:paper.section(block['title'],block['label'],level=block['level'])
            elif kind=='paragraph' and set(block)=={'kind','text'}:paper.paragraph(block['text'])
            elif kind=='equation' and set(block)=={'kind','source','variables','label','number'}:paper.equation(block['source'],block['variables'],block['label'])
            elif kind=='table' and set(block)=={'kind','headers','rows','caption','label','number','units'}:
                paper.table(block['headers'],block['rows'],block['caption'],block['label'],units=block['units'])
            elif kind=='figure' and set(block)=={'kind','path','caption','label','number','width'}:
                paper.figure(block['path'],block['caption'],block['label'],width=block['width'])
            elif kind=='citation' and set(block)=={'kind','identifiers','text'}:paper.citation(block['identifiers'])
            elif kind=='reference' and set(block)=={'kind','label','prefix'}:paper.reference(block['label'],prefix=block['prefix'])
            elif kind=='footnote' and set(block)=={'kind','text'}:paper.footnote(block['text'])
            else:raise ValueError('Unknown scientific-paper block or fields')
            if paper.blocks[-1]!=block:raise ValueError('Scientific-paper numbering/derived citation text was altered')
        paper.validate();return paper

    def typst(self, experiment_hash, *, figure_paths=None):
        """Emit native math, numbered captions and explicit cross-references."""
        self.validate();figure_paths=figure_paths or {}
        if not re.fullmatch('[0-9a-f]{64}',experiment_hash):raise ValueError('Canonical experiment hash required')
        pieces=[self.style.typst_settings(), '#show math.equation: set text(size: 12pt)', '#nabla-title('+_literal(self.title)+')',
                '#text('+_literal(' · '.join(self.authors))+')',
                '#block(fill: rgb("f2f6f7"), inset: 12pt, radius: 3pt)[#text('+_literal(self.abstract)+')]',
                '#set page(columns: '+str(self.style.columns)+')']
        for block in self.blocks:
            kind=block['kind']
            if kind=='section':pieces.append('#heading(level: '+str(block['level'])+', numbering: none, '+_literal(str(block['number'])+'. '+block['title'])+') <'+block['label']+'>')
            elif kind=='paragraph':pieces.append('#par('+_literal(block['text'])+')')
            elif kind=='equation':pieces.append(ScientificEquation(block['source'],block['variables']).typst()+' <'+block['label']+'>')
            elif kind=='table':
                headers=[header+(' ['+unit+']' if unit else '') for header,unit in zip(block['headers'],block['units'] or ['']*len(block['headers']))]
                cells=headers+[cell for row in block['rows'] for cell in row]
                table='#table(columns: '+str(len(headers))+', '+', '.join('text('+_literal(v)+')' for v in cells)+')'
                pieces.append('#figure('+table[1:]+', kind: table, caption: text('+_literal(block['caption'])+')) <'+block['label']+'>')
            elif kind=='figure':
                if block['path'] not in figure_paths:raise ValueError('Figure path was not staged: '+block['path'])
                path=figure_paths[block['path']]
                pieces.append('#figure(link("audit.html", image('+_literal(path)+', width: '+str(block['width']*100)+'%)), caption: text('+_literal(block['caption'])+')) <'+block['label']+'>')
            elif kind=='citation':pieces.append('#par('+_literal(block['text'])+')')
            elif kind=='reference':pieces.append('#par('+_literal(block['prefix']+self.labels.resolve(block['label'])['text'])+')')
            elif kind=='footnote':pieces.append('#footnote('+_literal(block['text'])+')')
        if self.bibliography.entries:
            pieces.append('#heading(numbering: none, "References")')
            for key in self.bibliography.entries:pieces.append('#par('+_literal(self.bibliography.text(key))+') <ref:'+key+'>')
        pieces.extend(['#heading(numbering: none, "Computational provenance")','#link("audit.html")[Open local audit companion]',
                       '#par('+_literal('Experiment SHA-256: '+experiment_hash)+')'])
        return '\n\n'.join(pieces)+'\n'

    def latex(self):
        self.validate()
        columns=',twocolumn' if self.style.columns==2 else ''
        pieces=[r'\documentclass['+'10pt'+columns+r']{article}',
                r'\usepackage[margin='+str(self.style.margin_mm)+r'mm]{geometry}',
                r'\usepackage{amsmath,amssymb,booktabs,longtable,graphicx,hyperref}',
                r'\title{'+_latex(self.title)+'}',r'\author{'+_latex(' · '.join(self.authors))+'}',
                r'\date{}\begin{document}\maketitle',r'\begin{abstract}'+_latex(self.abstract)+r'\end{abstract}']
        for block in self.blocks:
            kind=block['kind']
            if kind=='section':
                command={1:'section',2:'subsection',3:'subsubsection'}[block['level']]
                pieces.append(r'\hypertarget{'+block['label']+'}{}'+ '\\'+command+'*{'+_latex(str(block['number'])+'. '+block['title'])+'}')
            elif kind=='paragraph':pieces.append(_latex(block['text'])+'\n')
            elif kind=='equation':pieces.append(r'\begin{equation}'+ScientificEquation(block['source'],block['variables']).latex()+r'\label{'+block['label']+r'}\end{equation}')
            elif kind=='reference':pieces.append(_latex(block['prefix'])+r'\hyperlink{'+block['label']+'}{'+_latex(self.labels.resolve(block['label'])['text'])+'}')
            elif kind=='citation':pieces.append(_latex(block['text']))
            elif kind=='footnote':pieces.append(r'\footnote{'+_latex(block['text'])+'}')
            elif kind=='table':
                headers=[h+(' ['+u+']' if u else '') for h,u in zip(block['headers'],block['units'] or ['']*len(block['headers']))]
                pieces.extend([r'\begin{table}[ht]\centering\caption{'+_latex(block['caption'])+r'}\label{'+block['label']+'}',
                               r'\begin{tabular}{'+'l'*len(headers)+r'}\toprule',
                               ' & '.join(map(_latex,headers))+r'\\\midrule'])
                pieces.extend(' & '.join(map(_latex,row))+r'\\' for row in block['rows'])
                pieces.append(r'\bottomrule\end{tabular}\end{table}')
            elif kind=='figure':
                # Generated project staging uses deterministic safe paths.
                number=sum(1 for other in self.blocks[:self.blocks.index(block)] if other['kind']=='figure')
                suffix=Path(block['path']).suffix.lower();path='assets/figure-'+str(number)+suffix
                pieces.extend([r'\begin{figure}[ht]\centering',r'\href{audit.html}{\includegraphics[width='+str(block['width'])+r'\linewidth]{'+path+'}}',
                               r'\caption{'+_latex(block['caption'])+r'}\label{'+block['label']+r'}\end{figure}'])
        if self.bibliography.entries:
            pieces.append(r'\section*{References}')
            pieces.extend(_latex(self.bibliography.text(key))+'\n\n' for key in self.bibliography.entries)
        pieces.append(r'\end{document}')
        return '\n'.join(pieces)+'\n'

    def html(self):
        self.validate()
        pieces=['<!doctype html><html lang="'+self.language+'"><meta charset="utf-8"><meta name="viewport" content="width=device-width">',
                '<title>'+html.escape(self.title)+'</title><style>body{max-width:900px;margin:40px auto;padding:24px;color:#172b3a;font:17px/1.65 Georgia}h1,h2,h3,h4{font-family:system-ui;color:#117879}table{border-collapse:collapse;width:100%}th,td{padding:7px;border-bottom:1px solid #cddade}aside{background:#f2f6f7;padding:16px}.equation{padding:12px;text-align:center;overflow:auto}img{max-width:100%}</style>',
                '<h1>'+html.escape(self.title)+'</h1><p>'+html.escape(' · '.join(self.authors))+'</p><aside>'+html.escape(self.abstract)+'</aside>']
        for block in self.blocks:
            kind=block['kind']
            if kind=='section':
                tag='h'+str(block['level']+1)
                pieces.append('<'+tag+' id="'+html.escape(block['label'],quote=True)+'">'+html.escape(block['title'])+'</'+tag+'>')
            elif kind=='paragraph':pieces.append('<p>'+html.escape(block['text'])+'</p>')
            elif kind=='equation':pieces.append('<div id="'+html.escape(block['label'],quote=True)+'">'+ScientificEquation(block['source'],block['variables']).html()+' ('+str(block['number'])+')</div>')
            elif kind=='reference':pieces.append('<p>'+html.escape(block['prefix'])+'<a href="#'+html.escape(block['label'],quote=True)+'">'+html.escape(self.labels.resolve(block['label'])['text'])+'</a></p>')
            elif kind=='citation':pieces.append('<p>'+html.escape(block['text'])+'</p>')
            elif kind=='footnote':pieces.append('<aside>'+html.escape(block['text'])+'</aside>')
            elif kind=='table':
                pieces.append('<figure id="'+html.escape(block['label'],quote=True)+'"><table><thead><tr>'+''.join('<th>'+html.escape(v)+'</th>' for v in block['headers'])+'</tr></thead><tbody>')
                pieces.extend('<tr>'+''.join('<td>'+html.escape(v)+'</td>' for v in row)+'</tr>' for row in block['rows'])
                pieces.append('</tbody></table><figcaption>Table '+str(block['number'])+': '+html.escape(block['caption'])+'</figcaption></figure>')
            elif kind=='figure':
                path=block['path']
                if Path(path).is_absolute() or '..' in Path(path).parts or ':' in path:raise ValueError('HTML figure path must be a local safe relative path')
                pieces.append('<figure id="'+html.escape(block['label'],quote=True)+'"><img src="'+html.escape(path,quote=True)+'" alt="'+html.escape(block['caption'],quote=True)+'"><figcaption>'+html.escape(block['caption'])+'</figcaption></figure>')
        pieces.append(self.bibliography.html()+'</html>')
        return ''.join(pieces)


class PaperArchive:
    """Reproducible ZIP transport with bounded, traversal-safe extraction.

    Each member is covered by a manifest SHA-256. This protects against damage;
    authenticity requires an external signature or a trusted manifest digest.
    ZIP timestamps are fixed to make identical input bytes reproducible.
    """
    @staticmethod
    def create(directory, destination, *, maximum_bytes=256*1024*1024):
        import zipfile
        root=Path(directory).resolve();target=Path(destination)
        if not root.is_dir() or target.resolve().is_relative_to(root):raise ValueError('Archive output must be outside the paper directory')
        files=sorted(p for p in root.rglob('*') if p.is_file())
        if len(files)>4096:raise ValueError('Paper archive member budget exceeded')
        total=0;payload=[];manifest={}
        for path in files:
            if path.is_symlink() or not path.resolve().is_relative_to(root):raise ValueError('Archive source cannot follow symlinks')
            relative=path.relative_to(root).as_posix()
            if relative=='NABLA-ARCHIVE-MANIFEST.json':raise ValueError('Reserved archive manifest name')
            raw=_read(path,maximum_bytes);total+=len(raw)
            if total>maximum_bytes:raise ValueError('Paper archive uncompressed byte budget exceeded')
            payload.append((relative,raw));manifest[relative]=hashlib.sha256(raw).hexdigest()
        body={'schema':'nabla.paper-archive.v1','files':manifest,'uncompressed_bytes':total}
        payload.append(('NABLA-ARCHIVE-MANIFEST.json',canonical_json(body).encode()))
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for name,raw in payload:
                info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=0o100644<<16;archive.writestr(info,raw)
        from ..graphics.webgl_exporter import _publish_bytes
        _publish_bytes(target,stream.getvalue())
        return {'archive':str(target),'sha256':hashlib.sha256(stream.getvalue()).hexdigest(),'files':len(files),'uncompressed_bytes':total}

    @staticmethod
    def extract(source, destination, *, maximum_bytes=256*1024*1024):
        import zipfile
        root=Path(destination)
        if root.exists() or root.is_symlink():raise FileExistsError('Archive extraction requires a fresh directory')
        raw=_read(source,maximum_bytes)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos=archive.infolist();names=[entry.filename for entry in infos]
            if len(infos)>4097 or len(names)!=len(set(names)) or sum(i.file_size for i in infos)>maximum_bytes+1048576:
                raise ValueError('Archive member/expanded-byte budget or uniqueness failed')
            for entry in infos:
                path=Path(entry.filename)
                if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or ':' in entry.filename or entry.is_dir() or ((entry.external_attr>>16)&0o170000)==0o120000:
                    raise ValueError('Unsafe archive member path/type')
            manifest=json.loads(archive.read('NABLA-ARCHIVE-MANIFEST.json'))
            if manifest.get('schema')!='nabla.paper-archive.v1' or set(names)-{'NABLA-ARCHIVE-MANIFEST.json'}!=set(manifest['files']):
                raise ValueError('Archive manifest membership failed')
            root.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.paper-extract-',dir=root.parent) as temporary:
                stage=Path(temporary)/'paper';stage.mkdir();total=0
                for name,digest in manifest['files'].items():
                    member=archive.read(name);total+=len(member)
                    if total>maximum_bytes or hashlib.sha256(member).hexdigest()!=digest:raise ValueError('Archive member hash/budget failed')
                    path=stage/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(member)
                if total!=manifest['uncompressed_bytes']:raise ValueError('Archive uncompressed size binding failed')
                stage.rename(root)
        return {'directory':str(root),'files':len(manifest['files']),'uncompressed_bytes':total,'integrity_verified':True}


__all__ += ['ScientificPaper','PaperArchive']


class PDFQualityInspector:
    """Measured PDF geometry, text clipping and font diagnostics via PyMuPDF.

    Passing these checks is an editorial regression signal, not a proof of
    aesthetic quality, accessibility compliance or PDF/A conformance. Text
    bounding boxes do not detect every overlap between text and vector artwork.
    """
    @staticmethod
    def _open(path, password=None):
        try:import pymupdf
        except ImportError as error:raise ImportError('Install nablamath[editorial] for PDF layout inspection') from error
        raw=_read(path,256*1024*1024);document=pymupdf.open(stream=raw,filetype='pdf')
        if document.needs_pass and (password is None or not document.authenticate(password)):
            document.close();raise ValueError('PDF password required for layout inspection')
        if not 1<=len(document)<=1000:
            document.close();raise ValueError('PDF page budget exceeded')
        return document

    @classmethod
    def inspect(cls, path, *, experiment_hash=None, password=None,
                minimum_font_points=5.5, tolerance_points=1.):
        if not 1<=minimum_font_points<=24 or not 0<=tolerance_points<=10:
            raise ValueError('Invalid PDF inspection thresholds')
        document=cls._open(path,password);pages=[];issues=[];fonts={}
        try:
            for index,page in enumerate(document):
                rectangle=page.rect
                if rectangle.width<=0 or rectangle.height<=0:raise ValueError('PDF page has invalid dimensions')
                extracted=page.get_text('dict');text_fragments=[];text_boxes=[]
                for block in extracted.get('blocks',[]):
                    if block.get('type')!=0:continue
                    for line in block.get('lines',[]):
                        for span in line.get('spans',[]):
                            text=span.get('text','');text_fragments.append(text)
                            if not text.strip():continue
                            x0,y0,x1,y1=span['bbox'];size=float(span['size'])
                            text_boxes.append({'text':text,'bbox':[x0,y0,x1,y1],'points':size})
                            if size<minimum_font_points:issues.append({'page':index+1,'kind':'small_text','text':text,'points':size})
                            if x0 < -tolerance_points or y0 < -tolerance_points or x1>rectangle.width+tolerance_points or y1>rectangle.height+tolerance_points:
                                issues.append({'page':index+1,'kind':'text_outside_page','text':text,'bbox':[x0,y0,x1,y1]})
                full_text=''.join(text_fragments)
                if experiment_hash is not None and experiment_hash not in ''.join(full_text.split()):
                    issues.append({'page':index+1,'kind':'missing_experiment_hash'})
                page_fonts=[]
                for font in page.get_fonts(full=True):
                    xref,extension,font_type,base_name,resource_name,encoding,*rest=font
                    key=(xref,base_name)
                    if key not in fonts:
                        embedded=False
                        if xref:
                            try:embedded=bool(document.extract_font(xref)[3])
                            except (RuntimeError,ValueError):embedded=False
                        fonts[key]={'name':base_name,'type':font_type,'extension':extension,'embedded':embedded}
                    page_fonts.append(dict(fonts[key]))
                links=[]
                for link in page.get_links():
                    links.append({key:value for key,value in link.items() if key in ('kind','uri','file','page')})
                pages.append({'page':index+1,'width_points':rectangle.width,'height_points':rectangle.height,
                              'text_spans':text_boxes,'fonts':page_fonts,'links':links})
        finally:document.close()
        return {'pages':pages,'issues':issues,'layout_checks_passed':not issues,
                'font_summary':list(fonts.values()),'pdfa_compliance_established':False,
                'scope':'Measured text/page geometry; human editorial review remains separate'}

    @classmethod
    def preview(cls, path, destination, *, page=1, dpi=144, password=None):
        if type(page) is not int or page<1 or type(dpi) is not int or not 36<=dpi<=300:
            raise ValueError('Positive page and 36–300 preview DPI required')
        document=cls._open(path,password)
        try:
            if page>len(document):raise ValueError('Preview page exceeds PDF page count')
            pixmap=document[page-1].get_pixmap(dpi=dpi,alpha=False)
            if pixmap.width*pixmap.height>40000000:raise ValueError('PDF preview pixel budget exceeded')
            raw=pixmap.tobytes('png')
        finally:document.close()
        from ..graphics.webgl_exporter import _publish_bytes
        return _publish_bytes(destination,raw)


class PaperRevisionLedger:
    """Append-only hash-linked publication revisions with optional trusted tip.

    A hash chain detects changes relative to a known tip. It does not prevent an
    attacker from rewriting the entire chain and presenting a new root; callers
    must keep a trusted tip or sign it in their laboratory registry.
    """
    def __init__(self, path, *, maximum_entries=10000):
        self.path=Path(path)
        if type(maximum_entries) is not int or not 1<=maximum_entries<=100000:
            raise ValueError('Ledger entry budget invalid')
        self.maximum_entries=maximum_entries

    def records(self, *, expected_tip=None):
        from ..core.semantic_ir import fingerprint
        if self.path.is_symlink():raise ValueError('Revision ledger cannot be a symlink')
        if not self.path.exists():
            if expected_tip is not None:raise ValueError('Expected revision tip but ledger is absent')
            return []
        raw=_read(self.path,64*1024*1024)
        if raw and not raw.endswith(b'\n'):raise ValueError('Revision ledger has an incomplete final line')
        rows=[];previous=None
        for line in raw.splitlines():
            if len(line)>65536:raise ValueError('Revision ledger record exceeds byte budget')
            row=json.loads(line)
            if not isinstance(row,dict) or set(row)!={'schema','index','previous','experiment_hash','pdf_sha256','source_sha256','created_utc','content_id'}:
                raise ValueError('Unknown revision ledger record fields')
            body={key:value for key,value in row.items() if key!='content_id'}
            if row['schema']!='nabla.paper-revision.v1' or row['index']!=len(rows) or row['previous']!=previous or fingerprint(body)!=row['content_id']:
                raise ValueError('Revision ledger chain integrity failed')
            for name in ('experiment_hash','pdf_sha256','source_sha256'):
                if not isinstance(row[name],str) or not re.fullmatch('[0-9a-f]{64}',row[name]):raise ValueError('Invalid revision digest')
            timestamp=datetime.fromisoformat(row['created_utc'].replace('Z','+00:00'))
            if timestamp.tzinfo is None or timestamp.utcoffset()!=timezone.utc.utcoffset(timestamp):
                raise ValueError('Revision timestamp must be UTC')
            rows.append(row);previous=row['content_id']
            if len(rows)>self.maximum_entries:raise ValueError('Revision ledger entry budget exceeded')
        if expected_tip is not None and previous!=expected_tip:raise ValueError('Revision ledger differs from trusted tip')
        return rows

    def append(self, pdf, source, *, trust=None, require_signature=False, expected_tip=None,
               timestamp=None):
        import os
        from ..artifacts.process import publication_lock
        from ..core.semantic_ir import fingerprint
        inspected=VerifiablePDFWriter.inspect(pdf,trust=trust,require_signature=require_signature)
        source_raw=_read(source,16*1024*1024);pdf_raw=_read(pdf,256*1024*1024)
        instant=datetime.now(timezone.utc) if timestamp is None else datetime.fromisoformat(timestamp.replace('Z','+00:00'))
        if instant.tzinfo is None:raise ValueError('Revision append timestamp needs a timezone')
        canonical=instant.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with publication_lock(self.path.with_suffix(self.path.suffix+'.lock')):
            rows=self.records(expected_tip=expected_tip)
            if len(rows)>=self.maximum_entries:raise BufferError('Revision ledger is full')
            body={'schema':'nabla.paper-revision.v1','index':len(rows),
                  'previous':rows[-1]['content_id'] if rows else None,
                  'experiment_hash':inspected['bundle']['content_id'],
                  'pdf_sha256':hashlib.sha256(pdf_raw).hexdigest(),
                  'source_sha256':hashlib.sha256(source_raw).hexdigest(),'created_utc':canonical}
            row={**body,'content_id':fingerprint(body)}
            with self.path.open('ab') as stream:
                stream.write(canonical_json(row).encode()+b'\n');stream.flush();os.fsync(stream.fileno())
        return row

    def tip(self):
        records=self.records()
        return None if not records else records[-1]['content_id']

    def changes(self, first_index, second_index):
        rows=self.records()
        if type(first_index) is not int or type(second_index) is not int or not 0<=first_index<len(rows) or not 0<=second_index<len(rows):
            raise ValueError('Two valid revision indices required')
        first,second=rows[first_index],rows[second_index]
        return {'first':first_index,'second':second_index,
                'experiment_changed':first['experiment_hash']!=second['experiment_hash'],
                'source_changed':first['source_sha256']!=second['source_sha256'],
                'pdf_changed':first['pdf_sha256']!=second['pdf_sha256']}


__all__ += ['PDFQualityInspector','PaperRevisionLedger']


class ScientificPaperProject:
    """Versioned builds of a typed ScientificPaper with reactive result bindings.

    Generated Typst contains native equations/tables and escaped prose. Each
    revision binds the authored AST, materialized values, assets and experiment.
    Asset and input changes produce a new immutable build directory; a watch
    never replaces a previous revision's evidence.
    """
    def __init__(self, paper, artifact, destination, *, bindings=None, asset_root=None,
                 timeout=60, signature=None, trust=None, require_signature=False):
        if not isinstance(paper,ScientificPaper):raise ValueError('ScientificPaper instance required')
        if not isinstance(bindings if bindings is not None else {},dict):raise ValueError('Binding map required')
        self.paper=paper;self.artifact=artifact;self.destination=Path(destination)
        self.bindings=bindings or {};self.asset_root=None if asset_root is None else Path(asset_root).resolve()
        self.timeout=timeout;self.signature=signature;self.trust=trust;self.require_signature=require_signature
        self._lock=RLock();self._last_result=None;self._last_identity=None;self._observed=[]

    def _assets(self):
        result=[]
        for block in self.paper.blocks:
            if block['kind']!='figure':continue
            if self.asset_root is None:raise ValueError('Scientific-paper figures require asset_root')
            path=Path(block['path']);path=path if path.is_absolute() else self.asset_root/path
            if path.is_symlink() or not path.resolve().is_relative_to(self.asset_root) or path.suffix.lower() not in ('.png','.jpg','.jpeg'):
                raise ValueError('Scientific-paper figure must be a raster image inside asset_root')
            raw=_read(path)
            result.append({'source':path,'path':block['path'],'caption':block['caption'],
                           'sha256':hashlib.sha256(raw).hexdigest(),'bytes':raw})
        if len(result)>32:raise ValueError('Scientific-paper figure budget exceeded')
        return result

    def _bundle(self):
        from ..artifacts.bundle import create_bundle
        base=LivingPapersCompiler._bundle(self.artifact);receipts=list(base['receipts']);known={r['content_id'] for r in receipts}
        for record in self._observed:
            if record['content_id'] not in known:receipts.append(record);known.add(record['content_id'])
        return create_bundle(receipts,datasets=base['datasets'],proofs=base['proofs'])

    def receive(self, receipt):
        from ..calc.receipt import verify_receipt
        if not verify_receipt(receipt):raise ValueError('Scientific-paper project received an invalid receipt')
        with self._lock:
            if len(self._observed)>=1000:raise BufferError('Scientific-paper observed receipt budget exceeded')
            self._observed.append(json.loads(canonical_json(receipt)))

    def session(self, *, background_receipts=True):
        from ..calc import CalculationSession
        return CalculationSession(background_receipts=background_receipts,receipt_sink=self.receive)

    def input_identity(self):
        from ..core.semantic_ir import fingerprint
        with self._lock:
            assets=self._assets()
            return fingerprint({'paper':self.paper.to_data(),'bundle':self._bundle(),'bindings':self.bindings,
                                'assets':[{'path':a['path'],'sha256':a['sha256']} for a in assets],
                                'signature':self.signature})

    def _materialize(self, bundle):
        values={}
        for key,pointer in self.bindings.items():
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}',key):raise ValueError('Invalid project result binding')
            value=_pointer(bundle,pointer);values[key]=value if isinstance(value,str) else canonical_json(value)
        def substitute(value, depth=0):
            if depth>32:raise ValueError('Paper materialization depth budget exceeded')
            if isinstance(value,str):
                def replace(match):
                    if match[1] not in values:raise ValueError('Unknown project result binding: '+match[1])
                    return values[match[1]]
                replaced=_BINDING.sub(replace,value)
                if len(replaced)>65536:raise ValueError('Materialized paper field exceeds byte budget')
                return replaced
            if isinstance(value,list):return [substitute(v,depth+1) for v in value]
            if isinstance(value,dict):return {k:substitute(v,depth+1) for k,v in value.items()}
            return value
        # Regeneration verifies that dynamic values have not altered label
        # numbering, citation records or structural AST keys.
        return ScientificPaper.from_data(substitute(self.paper.to_data()))

    def build(self):
        from ..core.semantic_ir import fingerprint
        with self._lock:
            identity=self.input_identity();final=self.destination/identity
            bundle=self._bundle();materialized=self._materialize(bundle)
            if self._last_identity==identity and self._last_result is not None:
                old=self._last_result
                self.verify_revision(old.manifest.parent,trust=self.trust,require_signature=self.require_signature)
                return ReactiveBuild(old.pdf,old.artifact,old.source,old.manifest,old.experiment_hash,old.revision,False)
            self.destination.mkdir(parents=True,exist_ok=True)
            if self.destination.is_symlink() or final.is_symlink():raise ValueError('Scientific-paper project paths cannot be symlinks')
            if final.exists():
                manifest=json.loads(_read(final/'project.json'))
                if manifest['identity']!=identity:raise ValueError('Existing scientific-paper revision has the wrong identity')
                if hashlib.sha256(_read(final/'paper.pdf',256*1024*1024)).hexdigest()!=manifest['pdf_sha256']:
                    raise ValueError('Existing scientific-paper PDF changed')
                self.verify_revision(final,trust=self.trust,require_signature=self.require_signature)
            else:
                with tempfile.TemporaryDirectory(prefix='.scientific-paper-',dir=self.destination) as temporary:
                    stage=Path(temporary)/'completed';stage.mkdir();assets=self._assets();figures=[];paths={}
                    for i,asset in enumerate(assets):
                        filename='figure-'+str(i)+asset['source'].suffix.lower()
                        (stage/filename).write_bytes(asset['bytes']);paths[asset['path']]='assets/'+filename
                        figures.append({'path':filename,'caption':asset['caption']})
                    source=materialized.typst(bundle['content_id'],figure_paths=paths)
                    template=stage/'paper.typ';template.write_text(source,encoding='utf-8')
                    (stage/'paper.tex').write_text(materialized.latex(),encoding='utf-8')
                    (stage/'references.bib').write_text(materialized.bibliography.bibtex(),encoding='utf-8')
                    (stage/'paper-ast.json').write_text(canonical_json(materialized.to_data()),encoding='utf-8')
                    (stage/'artifact.json').write_text(canonical_json(bundle),encoding='utf-8')
                    compiler=LivingPaperCompiler(template,bundle,stage/'paper.pdf',timeout=self.timeout,
                        title=materialized.title,authors=materialized.authors,signature=self.signature,
                        trust=self.trust,require_signature=self.require_signature,figures=figures,asset_root=stage)
                    built=compiler.build()
                    # Export a directly compilable source, including the same
                    # footer macro and staged images used for the actual PDF.
                    from ..documents.typesetting import typst_style
                    from .living_paper import FOOTER, _signature
                    label,lines=_signature(bundle,self.signature,self.trust,self.require_signature)
                    paper_data={'title':materialized.title,'experiment_hash':bundle['content_id'],
                                'signature_label':label,'signature_lines':lines}
                    (stage/'paper-data.json').write_text(canonical_json(paper_data),encoding='utf-8')
                    exported_assets=stage/'assets';exported_assets.mkdir(exist_ok=True)
                    for i,asset in enumerate(assets):
                        (exported_assets/('figure-'+str(i)+asset['source'].suffix.lower())).write_bytes(asset['bytes'])
                    badge=built.manifest.parent/'provenance-badge.svg'
                    (exported_assets/('figure-'+str(len(assets))+'.svg')).write_bytes(_read(badge))
                    full_source='#let nabla = json("paper-data.json")\n'
                    full_source+=typst_style(materialized.title,bundle['content_id'],language=materialized.language)+'\n'+FOOTER+'\n'
                    full_source+=_read(built.source,1048576).decode('utf-8')
                    (stage/'paper.typ').write_text(full_source,encoding='utf-8')
                    html_source=materialized.html()
                    # The paper's HTML embeds image bytes while retaining its
                    # semantic figure labels/captions and native local links.
                    for asset in assets:
                        mime='image/png' if asset['source'].suffix.lower()=='.png' else 'image/jpeg'
                        old='src="'+html.escape(asset['path'],quote=True)+'"'
                        new='src="data:'+mime+';base64,'+base64.b64encode(asset['bytes']).decode()+'"'
                        html_source=html_source.replace(old,new)
                    (stage/'paper.html').write_text(html_source,encoding='utf-8')
                    manifest={'schema':'nabla.scientific-paper-project.v1','identity':identity,
                              'experiment_hash':bundle['content_id'],
                              'pdf_sha256':hashlib.sha256(_read(stage/'paper.pdf',256*1024*1024)).hexdigest(),
                              'ast_sha256':fingerprint(materialized.to_data()),
                              'assets':[{'path':a['path'],'sha256':a['sha256']} for a in assets],
                              'scientific_acceptance_established':False,
                              'files':{p.relative_to(stage).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(stage.rglob('*')) if p.is_file()}}
                    (stage/'project.json').write_text(canonical_json(manifest),encoding='utf-8')
                    stage.rename(final)
            result=ReactiveBuild(final/'paper.pdf',final/'artifact.json',final/'paper.typ',final/'project.json',bundle['content_id'],identity,True)
            self._last_identity=identity;self._last_result=result
            return result

    @staticmethod
    def verify_revision(directory, *, trust=None, require_signature=False):
        root=Path(directory)
        if root.is_symlink():raise ValueError('Scientific revision cannot be a symlink')
        manifest=json.loads(_read(root/'project.json'))
        if manifest.get('schema')!='nabla.scientific-paper-project.v1' or not isinstance(manifest.get('files'),dict):
            raise ValueError('Scientific revision manifest contract invalid')
        actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name!='project.json'}
        if actual!=set(manifest['files']):raise ValueError('Scientific revision file membership changed')
        for relative,digest in manifest['files'].items():
            path=root/relative
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):raise ValueError('Scientific revision follows an external path')
            if hashlib.sha256(_read(path,256*1024*1024)).hexdigest()!=digest:raise ValueError('Scientific revision file hash changed: '+relative)
        inspected=VerifiablePDFWriter.inspect(root/'paper.pdf',trust=trust,require_signature=require_signature)
        if inspected['bundle']['content_id']!=manifest['experiment_hash']:raise ValueError('Scientific revision experiment binding changed')
        return {'valid':True,'experiment_hash':manifest['experiment_hash'],'files':len(actual)}

    def watch(self, delay=.2):
        if type(delay) not in (int,float) or not .05<=delay<=60:raise ValueError('Watch delay must be .05–60 seconds')
        return PaperWatchHandle(self,delay)


class PublicationDataInspector:
    """Portable extraction and semantic diff of experiments attached to PDFs."""
    @staticmethod
    def extract(pdf, destination, *, password=None, trust=None, require_signature=False):
        inspected=VerifiablePDFWriter.inspect(pdf,password=password,trust=trust,require_signature=require_signature)
        raw=canonical_json(inspected['bundle']).encode()
        from ..graphics.webgl_exporter import _publish_bytes
        _publish_bytes(destination,raw)
        return {'path':str(destination),'experiment_hash':inspected['bundle']['content_id'],
                'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}

    @staticmethod
    def compare(first_pdf, second_pdf, *, trust=None):
        first=VerifiablePDFWriter.inspect(first_pdf,trust=trust)['bundle']
        second=VerifiablePDFWriter.inspect(second_pdf,trust=trust)['bundle']
        left={record['content_id']:record for record in first['receipts']}
        right={record['content_id']:record for record in second['receipts']}
        changed=[]
        by_request={canonical_json(record.get('request',{})):record for record in first['receipts'] if 'request' in record}
        for record in second['receipts']:
            if 'request' not in record:continue
            key=canonical_json(record['request'])
            if key in by_request and by_request[key]['result']!=record['result']:
                changed.append({'request':record['request'],'first_receipt':by_request[key]['content_id'],
                                'second_receipt':record['content_id']})
        return {'first_experiment':first['content_id'],'second_experiment':second['content_id'],
                'identical_experiment':first==second,'added_receipts':sorted(right.keys()-left.keys()),
                'removed_receipts':sorted(left.keys()-right.keys()),'same_request_different_results':changed,
                'datasets_changed':first['datasets']!=second['datasets'],
                'proof_attachments_changed':first['proofs']!=second['proofs'],
                'scope':'Recorded-data comparison; changed results are not automatically scientific refutations'}

    @staticmethod
    def receipt_index(pdf, *, trust=None):
        inspected=VerifiablePDFWriter.inspect(pdf,trust=trust);rows=[]
        for index,record in enumerate(inspected['bundle']['receipts']):
            request=record.get('request',{})
            rows.append({'index':index,'content_id':record['content_id'],
                         'operation':request.get('operation',record.get('operation')),
                         'kind':record.get('kind','calculation'),
                         'formal_proof':record.get('formal_proof',False)})
        return {'experiment_hash':inspected['bundle']['content_id'],'receipts':rows}


__all__ += ['ScientificPaperProject','PublicationDataInspector']


def _presentation_mathml(expression_value):
    """Convert a validated symbolic tree to browser-native presentation MathML."""
    from ..math._structured import sympy
    from html.entities import html5
    fragment=sympy().printing.mathml(expression_value,printer='presentation')
    def entity(match):
        name=match[1]
        if name in ('amp','lt','gt','quot','apos'):return match[0]
        value=html5.get(name+';')
        if value is None:raise ValueError('Unsupported MathML entity generated by the presentation backend')
        return ''.join('&#'+str(ord(character))+';' for character in value)
    fragment=re.sub(r'&([A-Za-z][A-Za-z0-9]+);',entity,fragment)
    if len(fragment)>1048576:raise ValueError('MathML presentation byte budget exceeded')
    root=ET.fromstring(fragment)
    allowed={'mrow','mi','mn','mo','mfrac','msup','msub','msubsup','msqrt','mroot','mfenced',
             'mtable','mtr','mtd','munder','mover','munderover','mstyle','mtext','ms','mpadded','mspace'}
    nodes=list(root.iter())
    if len(nodes)>8192 or any(node.tag not in allowed for node in nodes):
        raise ValueError('MathML generated outside the closed presentation profile')
    return root


def equation_mathml(equation):
    """Offline native MathML for a ScientificEquation, with escaped accessible text."""
    if not isinstance(equation,ScientificEquation):raise ValueError('ScientificEquation instance required')
    root=ET.Element('math',{'xmlns':'http://www.w3.org/1998/Math/MathML','display':'block',
                            'aria-label':equation.source})
    row=ET.SubElement(root,'mrow');row.append(_presentation_mathml(equation.left))
    if equation.right is not None:
        symbols={'=':'=','!=':'≠','<':'<','>':'>','<=':'≤','>=':'≥'}
        ET.SubElement(row,'mo').text=symbols[equation.relation]
        row.append(_presentation_mathml(equation.right))
    return ET.tostring(root,encoding='unicode')


class PublicationRecompiler:
    """Replay a portable Typst source and compare PDF text/page structure.

    Recompilation verifies the editable publication source still reproduces the
    displayed text. It does not prove pixel identity across font/renderer
    versions, or establish mathematical correctness from matching documents.
    """
    @staticmethod
    def typst(source, reference_pdf, *, root=None, timeout=60):
        import sys
        from pypdf import PdfReader
        from ..artifacts.process import run_renderer
        source=Path(source).resolve();reference=Path(reference_pdf).resolve()
        root=source.parent if root is None else Path(root).resolve()
        if source.is_symlink() or not source.is_relative_to(root) or not source.is_file():
            raise ValueError('Typst source must be a regular file within the declared root')
        if type(timeout) not in (int,float) or not 1<=timeout<=600:raise ValueError('Publication replay timeout invalid')
        with tempfile.TemporaryDirectory(prefix='nabla-publication-replay-') as directory:
            output=Path(directory)/'recompiled.pdf'
            run_renderer([sys.executable,'-m','nablamath.publishing._typst_worker',str(source),str(output),str(root)],cwd=root,timeout=timeout)
            raw=_read(output,256*1024*1024);expected=_read(reference,256*1024*1024)
            actual_reader=PdfReader(io.BytesIO(raw));reference_reader=PdfReader(io.BytesIO(expected))
            actual_text=[''.join((page.extract_text() or '').split()) for page in actual_reader.pages]
            reference_text=[''.join((page.extract_text() or '').split()) for page in reference_reader.pages]
            return {'page_count_matches':len(actual_reader.pages)==len(reference_reader.pages),
                    'text_matches':actual_text==reference_text,
                    'byte_identical':raw==expected,'recompiled_sha256':hashlib.sha256(raw).hexdigest(),
                    'reference_sha256':hashlib.sha256(expected).hexdigest(),
                    'source_sha256':hashlib.sha256(_read(source)).hexdigest(),
                    'scope':'Current renderer text/page replay; not cross-platform pixel identity or scientific proof'}


class EditorialChecklist:
    """Explicit pre-publication findings from document AST and real PDF evidence."""
    @staticmethod
    def inspect(paper, pdf, *, artifact=None, trust=None, require_signature=False,
                require_embedded_fonts=True):
        if not isinstance(paper,ScientificPaper):raise ValueError('ScientificPaper required')
        structure=paper.validate();findings=[]
        inspected=VerifiablePDFWriter.inspect(pdf,trust=trust,require_signature=require_signature)
        if artifact is not None:
            bundle=LivingPapersCompiler._bundle(artifact)
            if inspected['bundle']!=bundle:raise ValueError('Submitted paper PDF contains a different experiment')
        if not paper.abstract.strip():findings.append({'kind':'missing_abstract','severity':'editorial'})
        if not paper.authors:findings.append({'kind':'missing_authors','severity':'editorial'})
        if not paper.bibliography.entries:findings.append({'kind':'no_bibliography','severity':'editorial'})
        for block in paper.blocks:
            if block['kind'] in ('figure','table') and not block['caption'].strip():
                findings.append({'kind':'empty_caption','label':block['label'],'severity':'editorial'})
        layout=PDFQualityInspector.inspect(pdf,experiment_hash=inspected['bundle']['content_id'])
        findings.extend({**issue,'severity':'layout'} for issue in layout['issues'])
        if type(require_embedded_fonts) is not bool:raise ValueError('Font policy must be boolean')
        if require_embedded_fonts:
            findings.extend({'kind':'font_not_embedded','font':font['name'],'severity':'portability'} for font in layout['font_summary'] if not font['embedded'])
        return {'structure':structure,'findings':findings,'automated_checks_passed':not findings,
                'experiment_hash':inspected['bundle']['content_id'],'pdfa_compliance_established':False,
                'scientific_review_established':False,
                'scope':'Automated editorial checklist; accessibility, rights and independent scientific review are separate'}


__all__ += ['equation_mathml','PublicationRecompiler','EditorialChecklist']


class PublicationTable:
    """Bounded rectangular scientific data with safe CSV/HTML/Typst exports.

    Spreadsheet formula escaping is enabled by default in CSV exports. Numeric
    values retain their real types internally, so a negative number remains a
    number; strings beginning with formula characters receive a leading quote.
    """

    def __init__(self, headers, rows, *, caption='', units=None):
        if not isinstance(headers, (list, tuple)) or not 1 <= len(headers) <= 64:
            raise ValueError('Table requires 1–64 headers')
        if any(not isinstance(h, str) or not h or len(h) > 4096 for h in headers):
            raise ValueError('Nonempty bounded text headers required')
        if len(set(headers)) != len(headers):
            raise ValueError('Table headers must be unique')
        if not isinstance(rows, (list, tuple)) or len(rows) > 10000:
            raise ValueError('Table row budget exceeded')
        if len(rows)*len(headers) > 100000:
            raise ValueError('Table cell budget exceeded')
        if not isinstance(caption, str) or len(caption) > 16384:
            raise ValueError('Bounded caption required')
        values = []
        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) != len(headers):
                raise ValueError('Table row width mismatch')
            converted = []
            for value in row:
                if value is not None and type(value) not in (str, int, float, bool):
                    raise ValueError('Table cells must be scalar JSON values')
                if isinstance(value, str) and len(value) > 16384:
                    raise ValueError('Table cell text budget exceeded')
                if type(value) is float and not __import__('math').isfinite(value):
                    raise ValueError('Nonfinite table value')
                if type(value) is int and value.bit_length() > 4096:
                    raise ValueError('Table integer budget exceeded')
                converted.append(value)
            values.append(tuple(converted))
        if units is None:
            units = ['']*len(headers)
        if not isinstance(units, (list, tuple)) or len(units) != len(headers):
            raise ValueError('One unit per column required')
        if any(not isinstance(unit, str) or len(unit) > 128 for unit in units):
            raise ValueError('Bounded text units required')
        self.headers = tuple(headers)
        self.rows = tuple(values)
        self.caption = caption
        self.units = tuple(units)

    @staticmethod
    def _cell(value):
        return '' if value is None else str(value)

    def csv(self, *, spreadsheet_safe=True):
        import csv
        if type(spreadsheet_safe) is not bool:
            raise ValueError('Spreadsheet safety policy must be boolean')
        def safe(value):
            if spreadsheet_safe and isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')):
                return "'"+value
            return self._cell(value)
        stream = io.StringIO(newline='')
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow([safe(value) for value in self.headers])
        writer.writerows([[safe(value) for value in row] for row in self.rows])
        return stream.getvalue()

    def html(self):
        headings = [header+(' / '+unit if unit else '') for header, unit in zip(self.headers, self.units)]
        output = '<table><caption>'+html.escape(self.caption)+'</caption><thead><tr>'
        output += ''.join('<th scope="col">'+html.escape(h)+'</th>' for h in headings)
        output += '</tr></thead><tbody>'
        for row in self.rows:
            output += '<tr>'+''.join('<td>'+html.escape(self._cell(value))+'</td>' for value in row)+'</tr>'
        return output+'</tbody></table>'

    def typst(self):
        cells = [_literal(header+(' / '+unit if unit else '')) for header, unit in zip(self.headers, self.units)]
        cells += [_literal(self._cell(value)) for row in self.rows for value in row]
        return '#figure(table(columns: '+str(len(self.headers))+', '+', '.join(cells)+'), caption: '+_literal(self.caption)+')'

    def column_summary(self, header):
        import math
        if header not in self.headers:
            raise ValueError('Unknown column')
        index = self.headers.index(header)
        values = [row[index] for row in self.rows if row[index] is not None]
        if not values or any(type(value) not in (int, float) for value in values):
            raise ValueError('Nonempty numeric column required for summary')
        mean = math.fsum(value/len(values) for value in values)
        variance = math.fsum((value-mean)**2/(len(values)-1) for value in values) if len(values) > 1 else None
        if not math.isfinite(mean) or (variance is not None and not math.isfinite(variance)):
            raise ArithmeticError('Numeric summary overflow')
        return {'count': len(values), 'missing': len(self.rows)-len(values),
                'mean': mean, 'sample_variance': variance,
                'minimum': min(values), 'maximum': max(values), 'unit': self.units[index]}

    def to_data(self):
        return {'headers': list(self.headers), 'rows': [list(row) for row in self.rows],
                'caption': self.caption, 'units': list(self.units)}


__all__ += ['PublicationTable']
