"""Real GLB bytes, real Typst PDFs, signed provenance and live rebuilds."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
from threading import Event
import pytest

from nablamath.calc import CalculationSession
from nablamath.artifacts.bundle import create_bundle,save_bundle
from nablamath.graphics.webgl_exporter import WebGLExporter
from nablamath.graphics.manim_animator import ManimAnimator
from nablamath.publishing import TypstCompiler,verify_publication


def calculation(successes=2):
    return CalculationSession().execute('beta_binomial',successes=successes,trials=3).to_data()


def test_glb_accessor_bytes_indices_provenance_and_corruption(tmp_path):
    exporter = WebGLExporter()
    vertices,faces = exporter.heightfield([[0,1],[2,3]])
    record = calculation()
    path = exporter.export_glb(vertices,faces,tmp_path/'mesh.glb',audit_receipt=record)
    data = exporter.inspect_glb(path)
    assert data['asset']['version'] == '2.0'
    assert data['asset']['extras']['nabla']['receipt_id'] == record['content_id']
    assert data['accessors'][0]['count'] == 4 and data['accessors'][2]['count'] == 6
    raw = path.read_bytes(); size = struct.unpack('<I',raw[12:16])[0]
    binary = raw[28+size:]
    assert struct.unpack('<12f',binary[:48]) == tuple(x for row in vertices for x in row)
    broken = bytearray(raw); broken[-1] ^= 1
    path.write_bytes(broken)
    with pytest.raises(ValueError,match='integrity'):
        exporter.inspect_glb(path)
    with pytest.raises(FileExistsError):
        exporter.export_glb(vertices,faces,path,audit_receipt=record)
    gltf = exporter.export_gltf(vertices,faces,tmp_path/'gltf',audit_receipt=record)
    assert json.loads(gltf.read_text())['buffers'][0]['uri'] == 'mesh.bin'


def test_invalid_mesh_cannot_be_exported(tmp_path):
    exporter = WebGLExporter()
    with pytest.raises(ValueError,match='Degenerate'):
        exporter.export_glb([[0,0,0],[1,0,0],[2,0,0]],[[0,1,2]],tmp_path/'invalid.glb',audit_receipt=calculation())
    assert not (tmp_path/'invalid.glb').exists()


def test_manim_source_only_depicts_recorded_integral_and_ode(tmp_path):
    animator = ManimAnimator(duration=.2)
    for receipt in (CalculationSession().execute('integrate',source='x*x').to_data(),
                    CalculationSession().execute('ode',model='exponential_decay',initial=[1.],steps=10).to_data()):
        source = animator.source(receipt)
        compile(source,'nabla_scene.py','exec')
        assert receipt['content_id'] in source and 'class NablaAnimation(Scene)' in source
    corrupted = calculation(); corrupted['result']['mean'] = '9'
    with pytest.raises(ValueError):
        animator.source(corrupted)


def test_actual_manim_mp4_render(tmp_path):
    pytest.importorskip('manim')
    animator = ManimAnimator(duration=.2)
    receipt = CalculationSession().execute('integrate',source='x*x').to_data()
    rendered = animator.render(receipt,tmp_path/'integral.mp4',timeout=90)
    assert rendered['path'].read_bytes()[4:8] == b'ftyp'
    assert rendered['receipt']['result']['video_sha256'] == hashlib.sha256(rendered['path'].read_bytes()).hexdigest()


def _publishing_dependencies():
    pytest.importorskip('typst'); pytest.importorskip('pypdf')


def test_real_typst_pdf_placeholders_figures_footer_and_update(tmp_path):
    _publishing_dependencies()
    template = tmp_path/'paper.typ'
    template.write_text('= Computed result\nPosterior mean: {{mean}}.\n#image(nabla.images.at(0).path, width: 30mm)\n')
    svg = tmp_path/'figure.svg'; svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"><path d="M0 50 L100 0" stroke="blue"/></svg>')
    compiler = TypstCompiler(); output = tmp_path/'paper.pdf'
    options = {'template':template,'variables':{'mean':'/receipts/0/result/mean'},
               'figures':[{'path':'figure.svg','caption':'A model-linked line'}],'asset_root':tmp_path}
    first = compiler.compile(create_bundle([calculation(2)]),output,**options)
    from pypdf import PdfReader
    text = '\n'.join(page.extract_text() for page in PdfReader(output).pages)
    assert '3/5' in text and first.experiment_hash in ''.join(text.split())
    assert verify_publication(output) and first.changed
    assert not compiler.compile(create_bundle([calculation(2)]),output,**options).changed
    second = compiler.compile(create_bundle([calculation(3)]),output,**options)
    assert second.changed and second.experiment_hash != first.experiment_hash
    assert verify_publication(output)
    assert len(list((tmp_path/'paper.pdf.history').glob('*/paper.pdf'))) == 2
    old = output.read_bytes()
    template.write_text('#panic("broken template")')
    with pytest.raises(RuntimeError):
        compiler.compile(create_bundle([calculation(3)]),output,**options)
    assert output.read_bytes() == old and verify_publication(output)


def test_trusted_signed_footer_revocation_and_literal_result_data(tmp_path):
    _publishing_dependencies(); pytest.importorskip('cryptography')
    from nablamath.federation.crypto_registry import CryptoRegistry,generate_key,public_key_hex,sign
    from nablamath.calc.receipt import receipt
    key = generate_key(); trust = CryptoRegistry(); trust.pin('lab',public_key_hex(key))
    bundle = create_bundle([receipt('external',{}, {'value':'#panic("this is data")'})])
    signed = sign(bundle,key,signer='lab')
    template = tmp_path/'signed.typ'; template.write_text('= Data is literal\n{{value}}\n')
    compiler = TypstCompiler(trust=trust,require_signature=True)
    with pytest.raises(ValueError,match='requires'):
        compiler.compile(bundle,tmp_path/'unsigned.pdf',template=template)
    paper = compiler.compile(bundle,tmp_path/'signed.pdf',template=template,signature=signed)
    assert verify_publication(paper.pdf,trust=trust,require_signature=True)
    trust.revoke('lab',public_key_hex(key))
    assert not verify_publication(paper.pdf,trust=trust,require_signature=True)


def test_live_watcher_rebuilds_from_changed_bundle(tmp_path):
    _publishing_dependencies()
    bundle_path = tmp_path/'bundle.json'; save_bundle(create_bundle([calculation(2)]),bundle_path)
    compiler = TypstCompiler(); stop = Event()
    stream = compiler.watch(bundle_path,tmp_path/'live.pdf',stop_event=stop,poll_interval=.05,max_updates=2)
    first = next(stream)
    replacement = tmp_path/'new.json'; save_bundle(create_bundle([calculation(3)]),replacement)
    replacement.replace(bundle_path)
    second = next(stream)
    assert first.experiment_hash != second.experiment_hash and verify_publication(second.pdf)
    with pytest.raises(StopIteration):
        next(stream)


def test_existing_foreign_pdf_and_escaping_figure_are_refused(tmp_path):
    _publishing_dependencies()
    path = tmp_path/'existing.pdf'; path.write_bytes(b'%PDF-user-data')
    with pytest.raises(FileExistsError):
        TypstCompiler().compile(create_bundle([calculation()]),path)
    assert path.read_bytes() == b'%PDF-user-data'
    root = tmp_path/'assets'; root.mkdir()
    with pytest.raises(ValueError,match='outside'):
        TypstCompiler().compile(create_bundle([calculation()]),tmp_path/'new.pdf',asset_root=root,
                                figures=[{'path':'../existing.pdf','caption':'invalid'}])
