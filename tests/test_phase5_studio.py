import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from nablamath.documents.document_model import Document, Section, Equation
from nablamath.documents.citations import Citation
from nablamath.documents.figures import ingest_figure, validate_figure
from nablamath.documents.publication import research_document, publish, verify_publication
from nablamath.documents.exporters import to_html, to_latex, to_typst
from nablamath.documents.pdf_builder import build_pdf
from nablamath.expression import parse_expr


class StudioTests(unittest.TestCase):
    def document(self):
        return research_document('Estudo & teste', hypothesis='H < 2', method='Comparação exata',
                                 results='Resultado sintético delimitado', discussion='Não extrapolar',
                                 limitations='Sem observações externas', evidence_ids=('receipt-1',),
                                 equations=(Equation(parse_expr('x*x'), parse_expr('x^2')),),
                                 references=(Citation('ref1', 'Título', ('Autor',), 2026),))

    def test_roundtrip_citations_and_export_escaping(self):
        document = self.document()
        self.assertEqual(document, Document.from_data(json.loads(json.dumps(document.to_data()))))
        for exporter in (to_html, to_latex, to_typst):
            text = exporter(document)
            self.assertIn('ref1', text)
            self.assertIn('Sintetico: True', text)
        dangerous = Document('<script>', (Section('Seção', r'\input{secret} #evil <img>'),))
        self.assertNotIn('<script>', to_html(dangerous))
        self.assertNotIn(r'\input{secret}', to_latex(dangerous))
        self.assertIn('#text(', to_typst(dangerous))
        with self.assertRaises(ValueError):
            Document('X', (Section('S', 'T', citations=('missing',)),))

    def test_publication_tampering_and_nonoverwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'article'
            publish(self.document(), target)
            self.assertTrue(verify_publication(target))
            with self.assertRaises(FileExistsError):
                publish(self.document(), target)
            (target/'document.html').write_text('forged')
            self.assertFalse(verify_publication(target))
            manifest = json.loads((target/'manifest.json').read_text())
            manifest['files']['document.html'] = hashlib.sha256(b'forged').hexdigest()
            (target/'manifest.json').write_text(json.dumps(manifest))
            self.assertFalse(verify_publication(target))

    def test_figure_hash_and_traceable_pdf(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow opcional')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new('RGB', (40, 20), 'blue').save(root/'source.png')
            figure = ingest_figure(root/'source.png', root/'assets', 'Modelo sintético')
            doc = Document('Figura', (Section('Modelo', 'Construção testada', figures=(figure,)),))
            publish(doc, root/'publication', asset_root=root/'assets')
            self.assertTrue(verify_publication(root/'publication'))
            if shutil.which('pdflatex'):
                build_pdf(doc, root/'figure.pdf', 'latex', asset_root=root/'assets')
                self.assertTrue((root/'figure.pdf').read_bytes().startswith(b'%PDF-'))
            (root/'assets'/figure.path).write_bytes(b'changed')
            with self.assertRaises(ValueError):
                validate_figure(figure, root/'assets')

    def test_real_pdf_compilers(self):
        import importlib.util
        used = 0
        with tempfile.TemporaryDirectory() as tmp:
            for backend in ('latex', 'typst'):
                available = shutil.which('pdflatex' if backend == 'latex' else 'typst')
                if backend == 'typst':
                    available = available or importlib.util.find_spec('typst')
                if not available:
                    continue
                with self.subTest(backend=backend):
                    path = Path(tmp)/f'{backend}.pdf'
                    build_pdf(self.document(), path, backend)
                    used += 1
                    self.assertTrue(path.read_bytes().startswith(b'%PDF-'))

        if not used:
            self.skipTest('Compiladores PDF opcionais ausentes')

    def test_evidence_is_resolved_by_content_not_claimed_identifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/'receipt.json'
            source.write_text('{"measured": 3}\n')
            key = hashlib.sha256(source.read_bytes()).hexdigest()
            document = Document('Evidence',(Section('Result','Three units',evidence_ids=(key,)),))
            with self.assertRaises(ValueError):
                publish(document,root/'missing',require_evidence=True)
            publish(document,root/'article',evidence_sources={key:source},require_evidence=True)
            self.assertTrue(verify_publication(root/'article'))
            (root/'article'/'evidence'/f'{key}.json').write_text('{"measured": 4}\n')
            self.assertFalse(verify_publication(root/'article'))
