from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
from PIL import Image
from ..core.meshlet import build_meshlet_hierarchy, choose_meshlets_for_camera
from .camera import Camera
from .scene import Scene
from .rasterizer import render_triangles
from .pathtracer import PathTraceConfig, PathTracer
@dataclass
class NativeRenderConfig:
    width:int=1400; height:int=900; use_meshlets:bool=True; meshlet_faces:int=64; meshlet_levels:int=5; screen_error_target:float=.016; mode:str='beauty'; pathtrace:PathTraceConfig=field(default_factory=PathTraceConfig); output_path:str='native_render.png'
class NativeRenderer:
    def __init__(self,config:NativeRenderConfig|None=None): self.config=config or NativeRenderConfig()
    def _background(self,scene:Scene):
        h,w=self.config.height,self.config.width; top=np.array(scene.environment.background_top); bot=np.array(scene.environment.background_bottom); t=np.linspace(0,1,h)[:,None]; grad=bot*t+top*(1-t); return np.tile(grad[:,None,:],(1,w,1))
    def render(self,scene:Scene,camera:Camera)->Path:
        w,h=self.config.width,self.config.height; V=camera.view_matrix(); P=camera.projection_matrix(w/h); bg=self._background(scene); final=bg.copy(); depth=np.full((h,w),np.inf); normal_all=np.zeros((h,w,3)); pos_all=np.full((h,w,3),np.nan)
        soup_v=[]; soup_f=[]; soup_n=[]; soup_c=[]; base=0; cam_pos=np.array(camera.eye,float)
        for inst in scene.instances:
            if not inst.visible: continue
            mesh=inst.mesh.transformed(inst.model_matrix); faces=mesh.faces
            if self.config.use_meshlets:
                hier=build_meshlet_hierarchy(mesh,self.config.meshlet_faces,self.config.meshlet_levels); chosen=choose_meshlets_for_camera(hier,cam_pos,self.config.screen_error_target)
                selected=np.unique(np.concatenate([m.face_indices for m in chosen])) if chosen else np.arange(len(faces)); faces=faces[selected]
            world=mesh.vertices; clip=np.concatenate([world,np.ones((len(world),1))],axis=1)@V.T; clip=clip@P.T; clip=clip/np.maximum(np.abs(clip[:,3:4]),1e-8)
            img,d,nrm,pos=render_triangles(w,h,clip[:,:3],world,mesh.normals,mesh.colors,faces,np.array(scene.light.direction),np.array(scene.light.color)*scene.light.intensity,np.array(scene.environment.ambient),{'roughness':inst.material.roughness,'metallic':inst.material.metallic,'specular':inst.material.specular,'mode':self.config.mode},np.array([0,0,0]))
            mask=d<depth; final[mask]=img[mask]; depth[mask]=d[mask]; normal_all[mask]=nrm[mask]; pos_all[mask]=pos[mask]
            soup_v.append(world); soup_f.append(mesh.faces+base); soup_n.append(mesh.normals); soup_c.append(mesh.colors); base+=len(world)
        if soup_v and self.config.pathtrace.enabled and self.config.mode=='beauty':
            tracer=PathTracer(np.concatenate(soup_v),np.concatenate(soup_f),np.concatenate(soup_n),np.concatenate(soup_c),self.config.pathtrace); final=tracer.apply_reflection_pass(final,normal_all,pos_all)
        out=Path(self.config.output_path); out.parent.mkdir(parents=True,exist_ok=True); Image.fromarray((np.clip(final,0,1)*255).astype(np.uint8)).save(out); return out
