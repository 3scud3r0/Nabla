"""Editable scene bundles with hashes, exact constraint checks and model replay."""
from pathlib import Path
import hashlib
import json
import tempfile
import shutil
from ..core.semantic_ir import canonical_json
from ..verify.geometry import verify_geometry
from .scene_graph import GeometryScene
from .svg_renderer import render_svg
from .raster_renderer import render_png


def replay_model(scene):
    model=json.loads(scene.model_json);kind=model.get('kind')
    if kind=='inverse_geometry':
        from ..forge.constructors.geometry import construct
        expected=construct(model['seed'],model['size'],model['construction'])
    elif kind=='function':
        from .sampling import function_scene
        expected=function_scene(model['source'],xmin=model['xmin'],xmax=model['xmax'],samples=model['samples'])
    elif kind=='vector_field':
        from .sampling import vector_field_scene
        expected=vector_field_scene(model['dx'],model['dy'],bounds=tuple(model['bounds']),grid=model['grid'])
    elif kind=='phase_portrait':
        from .sampling import phase_portrait_scene
        expected=phase_portrait_scene(model['dx'],model['dy'],initials=tuple(tuple(v) for v in model['initials']),
             duration=model['duration'],steps=model['steps'],bounds=tuple(model['bounds']),grid=model['grid'])
    elif not model:
        return {'status':'not_applicable','valid':True,'scope':'user_authored_scene; constraints checked separately'}
    else:
        return {'status':'unknown_model','valid':False}
    return {'status':'replayed','valid':scene.to_data()==expected.to_data(),'scope':'reconstruction from declared model, not empirical validation'}


def export_scene(scene,destination,*,width=800,height=600):
    geometry=verify_geometry(scene);model=replay_model(scene)
    if not geometry.valid or not model['valid']:
        raise ValueError('Cena falhou em restricoes ou reexecucao do modelo')
    target=Path(destination).absolute()
    if target.exists():raise FileExistsError(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.nabla-diagram-',dir=target.parent))
    try:
        (stage/'scene.json').write_text(canonical_json(scene.to_data())+'\n',encoding='utf-8')
        (stage/'scene.svg').write_text(render_svg(scene,width,height),encoding='utf-8')
        (stage/'scene.png').write_bytes(render_png(scene,width,height))
        report={'schema_version':1,'scene_id':scene.content_id,'geometry':geometry.to_data(),'model':model,
                'width':width,'height':height,'formal_proof':False}
        (stage/'verification.json').write_text(canonical_json(report)+'\n',encoding='utf-8')
        manifest={'schema_version':1,'kind':'scientific_scene','files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(stage.iterdir())}}
        (stage/'manifest.json').write_text(canonical_json(manifest)+'\n',encoding='utf-8')
        if not verify_scene_bundle(stage):raise ArithmeticError('Bundle visual falhou na verificacao')
        if target.exists():raise FileExistsError(target)
        stage.rename(target)
        return report
    finally:
        if stage.exists():shutil.rmtree(stage)


def verify_scene_bundle(directory):
    try:
        root=Path(directory)
        paths=('scene.json','scene.svg','scene.png','verification.json','manifest.json')
        if {p.name for p in root.iterdir()}!=set(paths):return False
        if any((root/name).is_symlink() or (root/name).stat().st_size>16*1024*1024 for name in paths):return False
        manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        if manifest['kind']!='scientific_scene' or manifest['schema_version']!=1 or set(manifest['files'])!=set(paths)-{'manifest.json'}:return False
        if any(hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest for name,digest in manifest['files'].items()):return False
        scene=GeometryScene.from_data(json.loads((root/'scene.json').read_text(encoding='utf-8')))
        report=json.loads((root/'verification.json').read_text(encoding='utf-8'))
        geometry=verify_geometry(scene);model=replay_model(scene)
        if not geometry.valid or not model['valid']:return False
        if report!={'schema_version':1,'scene_id':scene.content_id,'geometry':geometry.to_data(),'model':model,
                   'width':report['width'],'height':report['height'],'formal_proof':False}:return False
        return ((root/'scene.svg').read_text(encoding='utf-8')==render_svg(scene,report['width'],report['height'])
                and (root/'scene.png').read_bytes()==render_png(scene,report['width'],report['height']))
    except (OSError,ValueError,KeyError,TypeError,ArithmeticError):
        return False
