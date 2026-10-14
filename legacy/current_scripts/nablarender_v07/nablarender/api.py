from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from .native.renderer import NativeRenderer, NativeRenderConfig
from .native.camera import Camera
from .native.scene import Scene
from .procedural.rocket_factory import RocketSpec, reusable_orbital_vehicle
@dataclass
class RenderBundleResult:
    native_beauty:str|None=None; native_thermal:str|None=None; native_xray:str|None=None; web_index_html:str|None=None; blender_script:str|None=None; report_pdf:str|None=None

def build_demo_scene(spec:RocketSpec|None=None)->Scene:
    scene=Scene();
    for inst in reusable_orbital_vehicle(spec or RocketSpec()): scene.add(inst)
    return scene

def export_all_three(output_dir:str='outputs_v07', rocket_spec:RocketSpec|None=None)->RenderBundleResult:
    from .web.web_renderer import WebRenderConfig, export_web_viewer
    from .blender.export_blender import BlenderExportConfig, export_blender_script
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); scene=build_demo_scene(rocket_spec); camera=Camera(); paths={}
    for mode in ['beauty','thermal','xray']:
        cfg=NativeRenderConfig(width=720,height=450,mode=mode,output_path=str(out/'native'/f'rocket_{mode}.png'))
        paths[mode]=str(NativeRenderer(cfg).render(scene,camera))
    web=export_web_viewer(WebRenderConfig(output_dir=str(out/'web'),title='NablaRender v0.7 Web - Meshlet/Scientific Viewer'),rocket_spec or RocketSpec())
    blender=export_blender_script(BlenderExportConfig(output_script=str(out/'blender'/'rocket_blender_cycles_export.py')),rocket_spec or RocketSpec())
    return RenderBundleResult(paths['beauty'],paths['thermal'],paths['xray'],web['index_html'],blender['blender_script'])
