
import bpy, math
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.samples=256
scene.render.resolution_x=1920
scene.render.resolution_y=1080
scene.render.fps=30
scene.frame_start=1
scene.frame_end=240
scene.render.image_settings.file_format='FFMPEG'
scene.render.ffmpeg.format='MPEG4'
scene.render.ffmpeg.codec='H264'
scene.render.filepath='//nablarender_blender_orbital.mp4'
def mat(name,color,metal=.7,rough=.25,emit=None,strength=0):
    m=bpy.data.materials.new(name); m.use_nodes=True
    bsdf=m.node_tree.nodes['Principled BSDF']; bsdf.inputs['Base Color'].default_value=color; bsdf.inputs['Metallic'].default_value=metal; bsdf.inputs['Roughness'].default_value=rough
    if emit: bsdf.inputs['Emission Color'].default_value=emit; bsdf.inputs['Emission Strength'].default_value=strength
    return m
steel=mat('brushed steel / ceramic TPS',(0.82,0.84,0.88,1),.72,.24)
tile=mat('black ceramic tiles',(0.05,0.05,0.06,1),.1,.65)
plasma=mat('plasma glow',(1,.28,.06,1),0,.2,(1,.22,.05,1),6)
bpy.ops.mesh.primitive_cone_add(vertices=128, radius1=4.6, radius2=0, depth=10.0, location=(5.0,0,0), rotation=(0,math.radians(90),0)); bpy.context.object.data.materials.append(steel)
bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=4.6, depth=38.0, location=(29.0,0,0), rotation=(0,math.radians(90),0)); bpy.context.object.data.materials.append(steel)
bpy.ops.mesh.primitive_cone_add(vertices=96, radius1=4.6, radius2=1.25, depth=6.0, location=(51.0,0,0), rotation=(0,math.radians(90),0)); bpy.context.object.data.materials.append(steel)
for i in range(4):
    ang=i*math.tau/4
    bpy.ops.mesh.primitive_cube_add(size=1, location=(41.54, math.cos(ang)*(6.3999999999999995), math.sin(ang)*(6.3999999999999995)))
    o=bpy.context.object; o.name='fin'; o.dimensions=(7.0,.18,3.6); o.rotation_euler[0]=ang; o.data.materials.append(tile)
bpy.ops.mesh.primitive_cone_add(vertices=64, radius1=0, radius2=2.5, depth=9, location=(58.0,0,0), rotation=(0,math.radians(90),0)); bpy.context.object.data.materials.append(plasma)
cam_data=bpy.data.cameras.new('Camera'); cam=bpy.data.objects.new('Camera',cam_data); scene.collection.objects.link(cam); scene.camera=cam; cam.data.lens=72
sun=bpy.data.lights.new('Key Sun','SUN'); sun.energy=5; sobj=bpy.data.objects.new('Key Sun',sun); scene.collection.objects.link(sobj); sobj.rotation_euler=(math.radians(50),0,math.radians(-35))
for f in range(1,241):
    t=(f-1)/239; a=math.radians(35+280*t); cam.location=(math.cos(a)*52,math.sin(a)*52,18+3*math.sin(2*a)); direction=Vector((27.0,0,3))-cam.location; cam.rotation_euler=direction.to_track_quat('-Z','Y').to_euler(); cam.keyframe_insert(data_path='location',frame=f); cam.keyframe_insert(data_path='rotation_euler',frame=f)
