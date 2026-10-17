"""Real PDF attachment/footers, offline artifacts, hashes and refusal paths."""
import ast
import base64
import hashlib
import json
from pathlib import Path
import re
import pytest
for dependency in ("typst", "pypdf", "qrcode", "PIL", "numpy"):
    pytest.importorskip(dependency)

from nablamath.artifacts.bundle import create_bundle
from nablamath.calc import CalculationSession
from nablamath.living_papers_compiler import LivingPapersCompiler
from nablamath.spatial_engine_3d import SpatialEngine3D


def receipt():
    return CalculationSession().execute('beta_binomial',successes=2,trials=3).to_data()


def document():
    return {'title':'Nabla — experimento auditável','authors':['Laboratório Nabla'],
            'abstract':'Uma publicação reprodutível com dados anexados.',
            'blocks':[{'kind':'heading','text':'Resultados'},
                      {'kind':'paragraph','text':'Média posterior: {{mean}}.'},
                      {'kind':'equation','text':'p = (s + 1) / (n + 2)'},
                      {'kind':'table','headers':['Quantidade','Valor'],'rows':[['Média','{{mean}}']]}]}


def test_resolve_closed_bindings_and_reactive_values():
    compiler=LivingPapersCompiler()
    bundle=create_bundle([receipt()])
    _,resolved=compiler.resolve(bundle,document(),bindings={'mean':'/receipts/0/result/mean'})
    assert '{{mean}}' not in resolved['blocks'][1]['text']
    other=create_bundle([CalculationSession().execute('beta_binomial',successes=0,trials=3).to_data()])
    _,changed=compiler.resolve(other,document(),bindings={'mean':'/receipts/0/result/mean'})
    assert changed['blocks'][1]['text']!=resolved['blocks'][1]['text']


def test_real_pdf_html_latex_qr_attachment_and_tampering(tmp_path):
    from pypdf import PdfReader
    compiler=LivingPapersCompiler()
    bundle=create_bundle([receipt()])
    result=compiler.build(bundle,tmp_path/'paper',document(),bindings={'mean':'/receipts/0/result/mean'})
    assert result.pdf.read_bytes().startswith(b'%PDF-')
    reader=PdfReader(result.pdf)
    assert json.loads(reader.attachments['experiment.json'][0])==bundle
    assert bundle['content_id'] in ''.join(p.extract_text() for p in reader.pages)
    assert (result.directory/'paper.tex').read_text().startswith('\\documentclass')
    assert b'<svg' in (result.directory/'audit-qr.svg').read_bytes()
    page=result.html.read_text()
    assert 'crypto.subtle.digest' in page and 'https://' not in page
    assert LivingPapersCompiler.verify(result.directory)
    result.html.write_text(page+'altered')
    assert not LivingPapersCompiler.verify(result.directory)


def test_html_only_assets_escaped_and_failure_atomicity(tmp_path):
    from PIL import Image
    Image.new('RGB',(4,4),(10,100,150)).save(tmp_path/'plot.png')
    doc=document()
    doc['title']='<script>alert(1)</script>'
    doc['blocks'].append({'kind':'figure','path':'plot.png','caption':'<img onerror=alert(1)>'})
    bundle=create_bundle([receipt()])
    result=LivingPapersCompiler().build(bundle,tmp_path/'html',doc,bindings={'mean':'/receipts/0/result/mean'},asset_root=tmp_path,pdf=False)
    page=result.html.read_text()
    assert '<script>alert(1)</script>' not in page and '&lt;script&gt;' in page
    assert 'data:image/png;base64,' in page and result.pdf is None
    assert LivingPapersCompiler.verify(result.directory)
    with pytest.raises(FileExistsError):
        LivingPapersCompiler().build(bundle,result.directory,doc,bindings={'mean':'/receipts/0/result/mean'},pdf=False)
    doc['blocks'][-1]['path']='../outside.png'
    with pytest.raises(ValueError):
        LivingPapersCompiler().build(bundle,tmp_path/'bad',doc,bindings={'mean':'/receipts/0/result/mean'},asset_root=tmp_path,pdf=False)
    assert not (tmp_path/'bad').exists()


def test_typst_latex_code_is_inert_data():
    compiler=LivingPapersCompiler()
    doc={'title':'T','blocks':[{'kind':'paragraph','text':'#panic("bad") \\input{secret} % &'}]}
    _,resolved=compiler.resolve(create_bundle([receipt()]),doc)
    typ,tex=compiler._sources(resolved,receipt()['content_id'])
    assert '#par("#panic(\\"bad\\")' in typ
    assert '\\textbackslash{}input\\{secret\\}' in tex


@pytest.mark.parametrize('doc',[
    {'title':'T','unknown':1}, {'title':'T','blocks':[{'kind':'raw','text':'execute'}]},
    {'title':'T','blocks':[{'kind':'paragraph','text':'{{missing}}'}]},
    {'title':'T','blocks':[{'kind':'table','headers':['a'],'rows':[['a','b']]}]},
])
def test_bad_documents(doc):
    with pytest.raises(ValueError):LivingPapersCompiler().resolve(create_bundle([receipt()]),doc)


def test_unsigned_policy_and_invalid_bundle(tmp_path):
    with pytest.raises(ValueError):
        LivingPapersCompiler(require_signature=True).build(create_bundle([receipt()]),tmp_path/'unsigned',{'title':'T'},pdf=False)
    bundle=create_bundle([receipt()]);bundle['content_id']='0'*64
    with pytest.raises(ValueError):LivingPapersCompiler().resolve(bundle,{'title':'T'})
    assert not LivingPapersCompiler.verify(tmp_path/'missing')


def test_scalar_mesh_offline_html_gltf_glb_and_script(tmp_path):
    engine=SpatialEngine3D()
    mesh=engine.scalar_field([[0,1],[2,3]])
    record=receipt()
    page=engine.standalone(mesh['vertices'],mesh['triangles'],tmp_path/'scene.html',audit_receipt=record,colors=mesh['colors'],title='<scene>')
    content=page.read_text()
    assert '&lt;scene&gt;' in content and 'getContext(\'webgl\'' in content
    assert 'https://' not in content and record['content_id'] in content
    scene=json.loads(re.search(r'<script id="scene" type="application/json">(.*?)</script>',content).group(1))
    assert len(scene['positions'])==4 and len(scene['indices'])==6
    glb=engine.export_glb(mesh['vertices'],mesh['triangles'],tmp_path/'mesh.glb',audit_receipt=record,colors=mesh['colors'])
    assert engine.exporter.inspect_glb(glb)['asset']['version']=='2.0'
    gltf=engine.export_gltf(mesh['vertices'],mesh['triangles'],tmp_path/'gltf',audit_receipt=record)
    assert json.loads(gltf.read_text())['accessors'][0]['count']==4
    with pytest.raises(FileExistsError):
        engine.standalone(mesh['vertices'],mesh['triangles'],page,audit_receipt=record)
    integral=CalculationSession().execute('integrate',source='x*x').to_data()
    source=engine.manim(integral,tmp_path/'scene.py')
    ast.parse(source.read_text())


def test_vector_glyphs_and_orbital_animation(tmp_path):
    engine=SpatialEngine3D()
    mesh=engine.vector_field([[0,0,0],[1,1,1]],[[1,0,0],[0,0,0]])
    assert len(mesh['vertices'])==4 and len(mesh['triangles'])==2
    engine.export_glb(mesh['vertices'],mesh['triangles'],tmp_path/'vectors.glb',audit_receipt=receipt())
    source=engine.trajectory_animation([[0,0,0],[1,2,3]],receipt(),errors=[.1,.2])
    ast.parse(source)
    assert 'ThreeDScene' in source and 'begin_ambient_camera_rotation' in source
    assert 'Line(axes.c2p' in source


def test_optional_three_script_is_embedded_locally(tmp_path):
    engine=SpatialEngine3D();mesh=engine.scalar_field([[0,1],[2,3]])
    path=tmp_path/'three.js';path.write_text('/* Trusted test fixture THREE */')
    page=engine.standalone(mesh['vertices'],mesh['triangles'],tmp_path/'three.html',audit_receipt=receipt(),three_js=path)
    assert 'data:text/javascript;base64,' in page.read_text()


@pytest.mark.parametrize('call',[
    lambda:SpatialEngine3D.scalar_field([[0,float('nan')],[1,2]]),
    lambda:SpatialEngine3D.vector_field([[0,0,0]],[[0,0,0]]),
    lambda:SpatialEngine3D.trajectory_animation([[0,0,0],[1,1,1]],receipt(),errors=[-1,0]),
    lambda:SpatialEngine3D.trajectory_animation([[0,0,0]],receipt()),
])
def test_spatial_refusals(call):
    with pytest.raises(ValueError):call()
