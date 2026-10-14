from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from .math3d import normalize, transform_points, transform_vectors
Array=np.ndarray
@dataclass
class Mesh:
    vertices:Array; faces:Array; normals:Optional[Array]=None; colors:Optional[Array]=None; scalar_field:Optional[Array]=None; name:str='mesh'
    def __post_init__(self):
        self.vertices=np.asarray(self.vertices,dtype=np.float64); self.faces=np.asarray(self.faces,dtype=np.int32)
        self.normals=self.compute_vertex_normals() if self.normals is None else np.asarray(self.normals,dtype=np.float64)
        self.colors=np.ones((len(self.vertices),3))*0.75 if self.colors is None else np.asarray(self.colors,dtype=np.float64)
        if self.scalar_field is not None: self.scalar_field=np.asarray(self.scalar_field,dtype=np.float64)
    def compute_vertex_normals(self):
        v=self.vertices; f=self.faces; fn=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]); fn=normalize(fn); vn=np.zeros_like(v)
        for i,tri in enumerate(f): vn[tri]+=fn[i]
        return normalize(vn)
    def transformed(self,M:Array)->'Mesh':
        return Mesh(transform_points(self.vertices,M), self.faces.copy(), normalize(transform_vectors(self.normals,M)), self.colors.copy(), None if self.scalar_field is None else self.scalar_field.copy(), self.name)
@dataclass
class Material:
    base_color:tuple[float,float,float]=(0.85,0.85,0.87); metallic:float=0.45; roughness:float=0.32; specular:float=0.5; emissive_color:tuple[float,float,float]=(0,0,0); emission_strength:float=0.0; thermal_overlay:bool=False; ir_mode:bool=False; xray_mode:bool=False; name:str='material'
@dataclass
class MeshInstance:
    mesh:Mesh; material:Material=field(default_factory=Material); model_matrix:Array=field(default_factory=lambda:np.eye(4)); visible:bool=True; metadata:dict=field(default_factory=dict)
