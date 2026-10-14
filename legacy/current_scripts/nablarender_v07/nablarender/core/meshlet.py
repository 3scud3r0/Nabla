from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from .mesh import Mesh
@dataclass
class Meshlet: face_indices:np.ndarray; center:np.ndarray; radius:float; lod:int
@dataclass
class MeshletHierarchy: levels:list[list[Meshlet]]
def build_meshlet_hierarchy(mesh:Mesh, faces_per_meshlet:int=64, max_levels:int=5)->MeshletHierarchy:
    levels=[]; ids=np.arange(len(mesh.faces),dtype=np.int32)
    for lod in range(max_levels):
        sampled=ids[::max(1,2**lod)]; level=[]
        for i in range(0,len(sampled),faces_per_meshlet):
            block=sampled[i:i+faces_per_meshlet]; pts=mesh.vertices[mesh.faces[block].reshape(-1)]; c=pts.mean(axis=0); r=float(np.max(np.linalg.norm(pts-c,axis=1))); level.append(Meshlet(block,c,r,lod))
        levels.append(level)
    return MeshletHierarchy(levels)
def choose_meshlets_for_camera(h:MeshletHierarchy,camera_pos:np.ndarray,screen_error_target:float=0.018)->list[Meshlet]:
    cam=np.asarray(camera_pos,float); chosen=[]
    for lod,level in enumerate(h.levels):
        for m in level:
            err=m.radius/(np.linalg.norm(m.center-cam)+1e-6)
            if err<screen_error_target*(2**lod) or lod==len(h.levels)-1: chosen.append(m)
    return chosen or (h.levels[-1] if h.levels else [])
