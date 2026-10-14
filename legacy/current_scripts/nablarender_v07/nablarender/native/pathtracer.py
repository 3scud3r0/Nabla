from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from ..core.bvh import BVH
from ..core.math3d import normalize
@dataclass
class PathTraceConfig:
    enabled:bool=True; samples_per_pixel:int=1; max_bounces:int=2; shadow_rays:bool=True; reflection_strength:float=.18
class PathTracer:
    def __init__(self, vertices, faces, normals, colors, config:PathTraceConfig|None=None):
        self.vertices=np.asarray(vertices,float); self.faces=np.asarray(faces,np.int32); self.normals=np.asarray(normals,float); self.colors=np.asarray(colors,float); self.bvh=BVH(self.vertices,self.faces,max_leaf=8); self.config=config or PathTraceConfig()
    def sample_hit(self, ro, rd):
        hit=self.bvh.intersect(ro,rd)
        if hit is None: return None
        ti,t,u,v=hit; tri=self.faces[ti]; w=1-u-v; p=ro+t*rd; n=normalize(w*self.normals[tri[0]]+u*self.normals[tri[1]]+v*self.normals[tri[2]]); c=np.clip(w*self.colors[tri[0]]+u*self.colors[tri[1]]+v*self.colors[tri[2]],0,1); return p,n,c
    def ambient_occlusion(self, p, n, rays:int=8):
        # Deterministic hemisphere probe set; small but useful for report-grade AO.
        dirs=[]
        for i in range(rays):
            a=2*np.pi*i/rays; z=(i+.5)/rays; r=np.sqrt(max(0,1-z*z)); d=normalize(np.array([r*np.cos(a),r*np.sin(a),z]));
            if d@n<0: d=-d
            dirs.append(d)
        occ=0
        for d in dirs:
            if self.bvh.intersect(p+n*1e-3,d) is not None: occ+=1
        return 1.0-occ/max(1,rays)
    def apply_reflection_pass(self, image, normal_buf, pos_buf):
        out=image.copy(); h,w,_=image.shape
        for y in range(0,h,10):
            for x in range(0,w,10):
                p=pos_buf[y,x]; n=normal_buf[y,x]
                if not np.isfinite(p).all() or np.linalg.norm(n)<1e-8: continue
                view=normalize(-p); rd=normalize(view-2*(view@n)*n); hit=self.sample_hit(p+n*1e-3,rd)
                if hit is None: continue
                hp,hn,hc=hit; ao=self.ambient_occlusion(hp,hn,rays=6); shade=.2+.8*max(0,hn@normalize(np.array([.35,-.6,.72])))*ao
                out[y,x]=np.clip((1-self.config.reflection_strength)*out[y,x]+self.config.reflection_strength*hc*shade,0,1)
        return out
