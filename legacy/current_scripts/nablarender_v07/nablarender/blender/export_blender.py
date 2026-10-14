from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
from ..procedural.rocket_factory import RocketSpec, reusable_orbital_vehicle
@dataclass
class BlenderExportConfig:
    output_script:str='blender_v07_cycles_scene.py'; fps:int=30; frame_end:int=240; resolution_x:int=1920; resolution_y:int=1080; cycles_samples:int=256; title:str='NablaRender v0.7 Blender Cycles Export'
def export_blender_script(config:BlenderExportConfig|None=None, rocket_spec:RocketSpec|None=None)->dict[str,str]:
    c=config or BlenderExportConfig(); spec=rocket_spec or RocketSpec(); instances=reusable_orbital_vehicle(spec); blocks=[f"""
import bpy, math
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples={c.cycles_samples}; scene.render.resolution_x={c.resolution_x}; scene.render.resolution_y={c.resolution_y}; scene.render.fps={c.fps}; scene.frame_start=1; scene.frame_end={c.frame_end}; scene.render.image_settings.file_format='FFMPEG'; scene.render.ffmpeg.format='MPEG4'; scene.render.ffmpeg.codec='H264'; scene.render.filepath='//mission_cinematic_v07.mp4'
world=bpy.data.worlds['World']; world.use_nodes=True; bg=world.node_tree.nodes['Background']; bg.inputs[0].default_value=(0.005,0.012,0.030,1); bg.inputs[1].default_value=.8
def mat(name,base,metal=.6,rough=.25,emit=(0,0,0,1),strength=0):
    m=bpy.data.materials.new(name); m.use_nodes=True; b=m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value=base; b.inputs['Metallic'].default_value=metal; b.inputs['Roughness'].default_value=rough; b.inputs['Emission Color'].default_value=emit; b.inputs['Emission Strength'].default_value=strength; return m
steel=mat('brushed steel + ceramic TPS',(0.76,0.78,0.82,1),.72,.24); tile=mat('black ceramic tiles',(0.06,0.06,0.07,1),.08,.68); plume_mat=mat('plasma plume',(1,.45,.12,1),0,.2,(1,.28,.04,1),8)
cam_data=bpy.data.cameras.new('Camera'); cam=bpy.data.objects.new('Camera',cam_data); scene.collection.objects.link(cam); scene.camera=cam; cam.data.lens=72; cam.data.dof.use_dof=True; cam.data.dof.focus_distance=34; cam.data.dof.aperture_fstop=3.0
sun=bpy.data.lights.new('KeySun','SUN'); sun.energy=6; suno=bpy.data.objects.new('KeySun',sun); scene.collection.objects.link(suno); suno.rotation_euler=(math.radians(52),0,math.radians(-35))
bpy.ops.mesh.primitive_plane_add(size=260, location=(22,0,-4.8)); floor=bpy.context.active_object; floor.data.materials.append(mat('matte floor',(0.04,0.05,0.07,1),.02,.94))
"""]
    for idx,inst in enumerate(instances):
        mesh=inst.mesh; m='steel' if idx==0 else 'tile'; blocks.append(f"""verts={mesh.vertices.tolist()}\nfaces={mesh.faces.tolist()}\nmesh=bpy.data.meshes.new('rocket_{idx}_mesh'); mesh.from_pydata(verts,[],faces); mesh.update(); obj=bpy.data.objects.new('rocket_{idx}',mesh); scene.collection.objects.link(obj); obj.data.materials.append({m}); obj.select_set(False)\n""")
    blocks.append(f"""
bpy.ops.mesh.primitive_cone_add(vertices=64, radius1=2.6, radius2=0, depth=11, location=(61,0,0), rotation=(0,math.radians(90),0)); plume=bpy.context.active_object; plume.data.materials.append(plume_mat)
for frame in range(scene.frame_start,scene.frame_end+1):
    t=(frame-1)/max(1,scene.frame_end-1); ang=math.radians(35+300*t); radius=56; cam.location=(math.cos(ang)*radius,math.sin(ang)*radius,18+4*math.sin(ang*1.4)); direction=Vector((24,0,7))-cam.location; cam.rotation_euler=direction.to_track_quat('-Z','Y').to_euler(); cam.keyframe_insert(data_path='location',frame=frame); cam.keyframe_insert(data_path='rotation_euler',frame=frame)
scene.use_nodes=True; nodes=scene.node_tree.nodes; links=scene.node_tree.links
for n in list(nodes):
    if n.name!='Render Layers': nodes.remove(n)
glare=nodes.new('CompositorNodeGlare'); glare.glare_type='FOG_GLOW'; glare.quality='HIGH'; comp=nodes.new('CompositorNodeComposite'); links.new(nodes['Render Layers'].outputs['Image'],glare.inputs['Image']); links.new(glare.outputs['Image'],comp.inputs['Image'])
""")
    path=Path(c.output_script); path.parent.mkdir(parents=True,exist_ok=True); path.write_text('\n'.join(blocks),encoding='utf-8'); meta=path.with_suffix('.json'); meta.write_text(json.dumps({'title':c.title,'rocket_spec':spec.__dict__},indent=2),encoding='utf-8'); return {'blender_script':str(path),'metadata':str(meta)}
