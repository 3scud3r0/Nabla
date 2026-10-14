"""Independent answers, adversarial candidates and end-to-end reproducibility."""
from dataclasses import replace
from fractions import Fraction as F
import copy
import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zlib

from nablamath.cli import main
from nablamath.core.semantic_ir import PolynomialSpec, ScientificTask, canonical_json
from nablamath.dataset.scientific import make_record, validate_record, audit_contamination, split_for_task
from nablamath.documents import Document, Section, to_html, to_latex, to_typst
from nablamath.documents.document_model import Equation, Figure
from nablamath.documents.pdf_builder import build_pdf
from nablamath.expression import Number, Symbol
from nablamath.forge import generate
from nablamath.forge.pipeline import run_cycle, verify_bundle
from nablamath.graphics import task_scene, render_svg
from nablamath.graphics.raster_renderer import render_png
from nablamath.verify import solve, verify


class ScientificContractTests(unittest.TestCase):
    def test_canonical_polynomial_and_roundtrip(self):
        a = ScientificTask('polynomial_integral', coefficients=(1, 2, 0))
        b = ScientificTask('polynomial_integral', coefficients=(F(1), F(2)))
        self.assertEqual(a.content_id, b.content_id)
        self.assertEqual(a, ScientificTask.from_data(a.to_data()))
        self.assertEqual(PolynomialSpec((1, 2)).evaluate(3), 7)

    def test_reject_ambiguous_or_excessive_inputs(self):
        for coefficients in [(), (True,), (.5,), ('x',), (2**257,), (1,)*34]:
            with self.subTest(coefficients=str(coefficients)[:50]), self.assertRaises((ValueError, ZeroDivisionError)):
                PolynomialSpec(coefficients)
        with self.assertRaises(ValueError):
            ScientificTask('linear_system', matrix=((1, 2),), rhs=(1,))
        with self.assertRaises(ValueError):
            ScientificTask('other')
        row = generate('linear_system', 1).task.to_data()
        row['matrix'] = [1]
        with self.assertRaises(ValueError):
            ScientificTask.from_data(row)
        row = generate('linear_system', 1).task.to_data()
        row['schema_version'] = 2
        with self.assertRaises(ValueError):
            ScientificTask.from_data(row)

    def test_generation_and_independent_solution_many_seeds(self):
        for family in ('polynomial_integral', 'linear_system'):
            for size in (1, 3, 8):
                for seed in range(10):
                    with self.subTest(family=family, size=size, seed=seed):
                        generated = generate(family, seed, size)
                        self.assertEqual(generated, generate(family, seed, size))
                        self.assertEqual(solve(generated.task), generated.witness)
                        self.assertTrue(verify(generated.task, generated.witness).valid)
                        wrong = list(generated.witness)
                        wrong[-1] += 1
                        self.assertFalse(verify(generated.task, tuple(wrong)).valid)

    def test_exact_known_linear_solution_and_singularity(self):
        task = ScientificTask('linear_system', matrix=((2, 1), (1, -1)), rhs=(5, 1))
        self.assertEqual(solve(task), (F(2), F(1)))
        self.assertTrue(verify(task, (2, 1)).valid)
        singular = ScientificTask('linear_system', matrix=((1, 1), (2, 2)), rhs=(2, 4))
        with self.assertRaises(ValueError):
            solve(singular)
        self.assertFalse(verify(singular, (1, 1)).valid)
        self.assertFalse(verify(task, (1,)).valid)

    def test_constant_of_integration_and_polynomial_identity(self):
        task = ScientificTask('polynomial_integral', coefficients=(0, 0, 3))
        self.assertEqual(solve(task), (F(0), F(0), F(0), F(1)))
        self.assertTrue(verify(task, (123, 0, 0, 1)).valid)
        # A perturbation vanishing at x=0,1 would evade a two-sample check.
        self.assertFalse(verify(task, (0, 1, -1, 1)).valid)

    def test_constructor_limits(self):
        for seed, size in [(-1, 3), (True, 3), (2**63, 3), (0, 0), (0, 9)]:
            with self.assertRaises(ValueError):
                generate('linear_system', seed, size)


class ScientificDatasetTests(unittest.TestCase):
    def setUp(self):
        self.generated = generate('linear_system', 42)
        self.record = make_record(self.generated.task, solve(self.generated.task), license_id='MIT',
                                  provenance='synthetic unit test', seed=42)

    def test_record_reexecution_rejects_tampering(self):
        self.assertTrue(validate_record(self.record))
        for key, value in [('solution', ['0', '0', '0']), ('task_id', 'bad'), ('split', 'invalid'),
                           ('license_id', ''), ('license_id', 5), ('verification', {'valid': True}),
                           ('difficulty', {'status': 'calibrated'}),
                           ('generator', {'name': 'inverse-v1', 'seed': 43})]:
            with self.subTest(key=key):
                row = copy.deepcopy(self.record)
                row[key] = value
                self.assertFalse(validate_record(row))

    def test_variants_stay_in_one_partition(self):
        splits = {split_for_task(generate('linear_system', seed).task) for seed in range(30)}
        self.assertEqual(len(splits), 1)
        self.assertTrue(audit_contamination({'train': [self.record]})['clean'])
        audit = audit_contamination({'train': [self.record], 'test': [self.record]})
        self.assertFalse(audit['clean'])
        self.assertEqual(len(audit['overlaps']['tasks']), 1)
        self.assertEqual(len(audit['overlaps']['families']), 1)

    def test_missing_rights_and_wrong_candidate_rejected(self):
        with self.assertRaises(ValueError):
            make_record(self.generated.task, self.generated.witness, license_id='', provenance='test', seed=42)
        with self.assertRaises(ValueError):
            make_record(self.generated.task, (F(0),)*3, license_id='MIT', provenance='test', seed=42)


class ScientificArtifactTests(unittest.TestCase):
    def test_svg_png_and_exact_metadata(self):
        task = generate('polynomial_integral', 3).task
        scene = task_scene(task, solve(task))
        root = ET.fromstring(render_svg(scene))
        data = json.loads(root.find('{http://www.w3.org/2000/svg}metadata').text)
        self.assertEqual(data, scene.to_data())
        png = render_png(scene, 100, 100)
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        offset = 8
        compressed = b''
        while offset < len(png):
            length = struct.unpack('>I', png[offset:offset+4])[0]
            kind = png[offset+4:offset+8]
            payload = png[offset+8:offset+8+length]
            crc = struct.unpack('>I', png[offset+8+length:offset+12+length])[0]
            self.assertEqual(crc, zlib.crc32(kind+payload))
            if kind == b'IDAT':
                compressed += payload
            if kind == b'tEXt':
                self.assertEqual(json.loads(payload.split(b'\0',1)[1]), data)
            offset += 12+length
        self.assertEqual(len(zlib.decompress(compressed)), 100*(1+100*3))

    def test_text_is_escaped_in_all_document_backends(self):
        document = Document('<script>_%\\input{bad}', (Section('Heading', '<img src=x> #panic("bad")'),))
        html = to_html(document)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img src=x>', html)
        tex = to_latex(document)
        self.assertNotIn('\\input{bad}', tex)
        self.assertIn(r'\_', tex)
        typst = to_typst(document)
        self.assertIn('#text(', typst)
        self.assertIn('\\"bad\\"', typst)
        with self.assertRaises(ValueError):
            Figure('../outside.png', 'bad')

    def test_cycle_is_reproducible_and_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory)/'a', Path(directory)/'b'
            summary = run_cycle(a, count=8, seed=13, license_id='MIT', provenance='synthetic test')
            self.assertEqual(summary['accepted'], 8)
            self.assertEqual(summary['formal_proofs'], 0)
            self.assertTrue(verify_bundle(a))
            run_cycle(b, count=8, seed=13, license_id='MIT', provenance='synthetic test')
            self.assertEqual((a/'manifest.json').read_bytes(), (b/'manifest.json').read_bytes())
            for path in a.rglob('*'):
                if path.is_file():
                    self.assertEqual(path.read_bytes(), (b/path.relative_to(a)).read_bytes())
            with self.assertRaises(FileExistsError):
                run_cycle(a, count=1, seed=0, license_id='MIT', provenance='test')
            records = (a/'records.jsonl').read_text()
            (a/'records.jsonl').write_text(records.replace('"formal_proof":false', '"formal_proof":true'))
            self.assertFalse(verify_bundle(a))
            # Even updating the hash cannot make a falsified certificate pass.
            manifest = json.loads((a/'manifest.json').read_text())
            manifest['files']['records.jsonl'] = hashlib.sha256((a/'records.jsonl').read_bytes()).hexdigest()
            (a/'manifest.json').write_text(json.dumps(manifest))
            self.assertFalse(verify_bundle(a))

    def test_failed_cycle_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'result'
            with self.assertRaises(ValueError):
                run_cycle(target, count=2, seed=0, size=9, license_id='MIT', provenance='test')
            self.assertEqual(list(Path(directory).iterdir()), [])

    @unittest.skipUnless(shutil.which('pdflatex'), 'optional pdflatex absent')
    def test_pdf_compiles_with_escaped_content_and_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            doc = Document('Synthetic report', (Section('Result', 'Exact: 2 & 3, 100% _ # $ { } ~ ^',
                           equations=(Equation(Symbol('x'), Number(F(1, 3))),)),))
            path = build_pdf(doc, Path(directory)/'result.pdf', 'latex')
            self.assertTrue(path.read_bytes().startswith(b'%PDF-'))
            with self.assertRaises(FileExistsError):
                build_pdf(doc, path, 'latex')

    def test_cli_cycle_and_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'cycle'
            self.assertEqual(main(['forge', str(target), '--count', '2', '--license', 'MIT', '--provenance', 'test']), 0)
            self.assertEqual(main(['check-bundle', str(target)]), 0)
            self.assertEqual(main(['check-bundle', str(target/'missing')]), 1)


class MultimodalAlignmentTests(unittest.TestCase):
    def test_rehashed_wrong_scene_is_rejected(self):
        from nablamath.dataset.alignments import validate_alignment
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'bundle'
            run_cycle(target,count=2,seed=1,license_id='MIT',provenance='synthetic test')
            record = json.loads((target/'records.jsonl').read_text().splitlines()[0])
            self.assertTrue(validate_alignment(record,target))
            path = target/'figures'/f"{record['task_id']}.json"
            data = json.loads(path.read_text())
            data['points'][0][1] = '999'
            path.write_text(json.dumps(data))
            manifest = json.loads((target/'manifest.json').read_text())
            manifest['files'][path.relative_to(target).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
            (target/'manifest.json').write_text(json.dumps(manifest))
            self.assertFalse(validate_alignment(record,target))
            self.assertFalse(verify_bundle(target))

    def test_misplaced_partition_is_not_clean(self):
        generated = generate('linear_system',42)
        row = make_record(generated.task,generated.witness,license_id='MIT',provenance='test',seed=42)
        wrong = 'test' if row['split'] == 'train' else 'train'
        self.assertFalse(audit_contamination({wrong:[row]})['clean'])

    def test_rehashed_false_card_counts_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'bundle'
            run_cycle(root,count=2,seed=1,license_id='MIT',provenance='synthetic test')
            card = json.loads((root/'card.json').read_text())
            card['accepted'] = 999
            (root/'card.json').write_text(json.dumps(card))
            manifest = json.loads((root/'manifest.json').read_text())
            manifest['files']['card.json'] = hashlib.sha256((root/'card.json').read_bytes()).hexdigest()
            (root/'manifest.json').write_text(json.dumps(manifest))
            self.assertFalse(verify_bundle(root))
