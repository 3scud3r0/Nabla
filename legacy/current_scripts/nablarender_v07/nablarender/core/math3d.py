from __future__ import annotations
import math
from dataclasses import dataclass
import numpy as np
Array = np.ndarray

def normalize(v: Array, eps: float=1e-9) -> Array:
    v=np.asarray(v,dtype=np.float64); n=np.linalg.norm(v,axis=-1,keepdims=True); return v/np.maximum(n,eps)
def dot(a:Array,b:Array)->Array: return np.sum(a*b,axis=-1)
def cross(a:Array,b:Array)->Array: return np.cross(a,b)
def perspective(fovy_deg:float, aspect:float, near:float, far:float)->Array:
    f=1.0/math.tan(math.radians(fovy_deg)/2.0); M=np.zeros((4,4),dtype=np.float64)
    M[0,0]=f/aspect; M[1,1]=f; M[2,2]=(far+near)/(near-far); M[2,3]=(2*far*near)/(near-far); M[3,2]=-1.0; return M
def look_at(eye:Array,target:Array,up:Array=np.array([0.,0.,1.]))->Array:
    eye=np.asarray(eye,dtype=np.float64); target=np.asarray(target,dtype=np.float64); up=normalize(np.asarray(up,dtype=np.float64))
    f=normalize(target-eye); s=normalize(np.cross(f,up)); u=np.cross(s,f); M=np.eye(4); M[0,:3]=s; M[1,:3]=u; M[2,:3]=-f; T=np.eye(4); T[:3,3]=-eye; return M@T
def transform_points(points:Array,M:Array)->Array:
    h=np.concatenate([np.asarray(points,dtype=np.float64),np.ones((len(points),1))],axis=1); o=h@M.T; return o[:,:3]/np.maximum(np.abs(o[:,3:4]),1e-9)
def transform_vectors(v:Array,M:Array)->Array: return np.asarray(v,dtype=np.float64)@M[:3,:3].T
def translation_matrix(tx=0.,ty=0.,tz=0.):
    M=np.eye(4); M[:3,3]=[tx,ty,tz]; return M
def scale_matrix(sx=1.,sy=1.,sz=1.):
    M=np.eye(4); M[0,0]=sx; M[1,1]=sy; M[2,2]=sz; return M
def rotation_matrix_xyz(rx_deg=0.,ry_deg=0.,rz_deg=0.):
    rx,ry,rz=map(math.radians,[rx_deg,ry_deg,rz_deg]); cx,sx=math.cos(rx),math.sin(rx); cy,sy=math.cos(ry),math.sin(ry); cz,sz=math.cos(rz),math.sin(rz)
    Rx=np.array([[1,0,0,0],[0,cx,-sx,0],[0,sx,cx,0],[0,0,0,1]],float); Ry=np.array([[cy,0,sy,0],[0,1,0,0],[-sy,0,cy,0],[0,0,0,1]],float); Rz=np.array([[cz,-sz,0,0],[sz,cz,0,0],[0,0,1,0],[0,0,0,1]],float); return Rz@Ry@Rx
@dataclass
class Transform:
    translation:tuple[float,float,float]=(0,0,0); rotation_deg:tuple[float,float,float]=(0,0,0); scale:tuple[float,float,float]=(1,1,1)
    def matrix(self)->Array: return translation_matrix(*self.translation)@rotation_matrix_xyz(*self.rotation_deg)@scale_matrix(*self.scale)
