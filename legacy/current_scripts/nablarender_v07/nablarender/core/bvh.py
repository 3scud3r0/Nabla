from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np
Array=np.ndarray
@dataclass
class BVHNode:
    bounds_min:Array; bounds_max:Array; left:Optional[int]=None; right:Optional[int]=None; tri_indices:Optional[Array]=None
class BVH:
    def __init__(self, vertices:Array, faces:Array, max_leaf:int=8):
        self.vertices=np.asarray(vertices,float); self.faces=np.asarray(faces,np.int32); self.max_leaf=max_leaf
        tris=self.vertices[self.faces]; self.tri_min=tris.min(axis=1); self.tri_max=tris.max(axis=1); self.centers=tris.mean(axis=1)
        self.nodes:list[BVHNode]=[]; self.root=self._build(np.arange(len(self.faces),dtype=np.int32))
    def _build(self, idx:Array)->int:
        bmin=self.tri_min[idx].min(axis=0); bmax=self.tri_max[idx].max(axis=0); node_id=len(self.nodes); self.nodes.append(BVHNode(bmin,bmax))
        if len(idx)<=self.max_leaf:
            self.nodes[node_id].tri_indices=idx; return node_id
        ext=bmax-bmin; axis=int(np.argmax(ext)); order=np.argsort(self.centers[idx,axis]); mid=len(idx)//2
        self.nodes[node_id].left=self._build(idx[order[:mid]]); self.nodes[node_id].right=self._build(idx[order[mid:]]); return node_id
    @staticmethod
    def _intersect_aabb(ro:Array,rd_inv:Array,bmin:Array,bmax:Array)->bool:
        t1=(bmin-ro)*rd_inv; t2=(bmax-ro)*rd_inv; tmin=np.maximum.reduce(np.minimum(t1,t2)); tmax=np.minimum.reduce(np.maximum(t1,t2)); return bool(tmax>=max(tmin,0.0))
    def intersect(self, ro:Array, rd:Array):
        rd_inv=1.0/np.where(np.abs(rd)<1e-9, np.sign(rd)*1e-9+1e-9, rd); best_t=np.inf; best=None; stack=[self.root]
        while stack:
            ni=stack.pop(); n=self.nodes[ni]
            if not self._intersect_aabb(ro,rd_inv,n.bounds_min,n.bounds_max): continue
            if n.tri_indices is not None:
                for ti in n.tri_indices:
                    hit=self._tri_hit(ro,rd,ti)
                    if hit is not None and hit[0]<best_t: best_t=hit[0]; best=(ti,*hit)
            else:
                stack.append(n.left); stack.append(n.right)
        return best
    def _tri_hit(self,ro,rd,ti):
        v0,v1,v2=self.vertices[self.faces[ti]]; e1=v1-v0; e2=v2-v0; p=np.cross(rd,e2); det=e1@p
        if abs(det)<1e-9: return None
        inv=1.0/det; tvec=ro-v0; u=(tvec@p)*inv
        if u<0 or u>1: return None
        q=np.cross(tvec,e1); v=(rd@q)*inv
        if v<0 or u+v>1: return None
        t=(e2@q)*inv
        if t<=1e-5: return None
        return float(t),float(u),float(v)
