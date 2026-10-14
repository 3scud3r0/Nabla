from __future__ import annotations
from dataclasses import dataclass
import math, numpy as np
from ..core.mesh import Mesh, Material, MeshInstance
from ..core.math3d import Transform
@dataclass
class RocketSpec:
    total_length_m:float=56.0; body_radius_m:float=4.6; nose_length_m:float=10.5; cylinder_length_m:float=38.0; tail_length_m:float=7.5; fin_count:int=4; fin_span_m:float=3.6; fin_root_chord_m:float=7.3; fin_tip_chord_m:float=2.6; fin_thickness_m:float=0.16; circum_segments:int=72

def _lathe_mesh(x,r,circ):
    theta=np.linspace(0,2*np.pi,circ,endpoint=False); verts=[]; scalar=[]; faces=[]
    for i,xx in enumerate(x):
        for t in theta: verts.append([xx,r[i]*math.cos(t),r[i]*math.sin(t)]); scalar.append(i/max(1,len(x)-1))
    for i in range(len(x)-1):
        for j in range(circ):
            a=i*circ+j; b=i*circ+(j+1)%circ; c=(i+1)*circ+j; d=(i+1)*circ+(j+1)%circ; faces += [[a,c,b],[b,c,d]]
    scalar=np.array(scalar); colors=np.stack([0.62+0.24*scalar,0.63+0.20*scalar,0.66+0.14*scalar],axis=1)
    # ceramic belly tiles + heat gradient
    for i,v in enumerate(verts):
        angle=math.atan2(v[2],v[1]); xnorm=v[0]/x[-1]
        if -2.35<angle<-0.75 and xnorm>0.17: colors[i]=[0.08,0.08,0.09]
        if xnorm<0.11: colors[i]=0.65*colors[i]+0.35*np.array([1.0,0.48,0.16])
    return Mesh(np.array(verts),np.array(faces,dtype=np.int32),colors=colors,scalar_field=scalar,name='reusable_rocket_body')

def _fin(spec,idx):
    phi=2*np.pi*idx/spec.fin_count; n=np.array([0,math.cos(phi),math.sin(phi)]); chord=np.array([-1.,0,0]); thick=np.cross(chord,n)*spec.fin_thickness_m*0.5
    root_x=spec.nose_length_m+spec.cylinder_length_m*0.78; r=spec.body_radius_m
    p0=np.array([root_x,r*n[1],r*n[2]]); p1=p0+chord*spec.fin_root_chord_m; p2=p0+n*spec.fin_span_m+chord*(spec.fin_root_chord_m-spec.fin_tip_chord_m)*0.62; p3=p2+chord*spec.fin_tip_chord_m
    verts=np.array([p0+thick,p1+thick,p2+thick,p3+thick,p0-thick,p1-thick,p2-thick,p3-thick]); faces=np.array([[0,1,2],[1,3,2],[4,6,5],[5,6,7],[0,4,1],[1,4,5],[1,5,3],[3,5,7],[3,7,2],[2,7,6],[2,6,0],[0,6,4]],dtype=np.int32); colors=np.tile([[0.10,0.10,0.115]],(len(verts),1)); return Mesh(verts,faces,colors=colors,name=f'fin_{idx}')

def reusable_orbital_vehicle(spec:RocketSpec|None=None, transform:Transform|None=None)->list[MeshInstance]:
    spec=spec or RocketSpec(); transform=transform or Transform(); x1=np.linspace(0,spec.nose_length_m,24); r1=spec.body_radius_m*(x1/max(spec.nose_length_m,1e-9))**0.72
    x2=np.linspace(spec.nose_length_m,spec.nose_length_m+spec.cylinder_length_m,42); r2=np.ones_like(x2)*spec.body_radius_m
    x3=np.linspace(spec.nose_length_m+spec.cylinder_length_m,spec.total_length_m,22); frac=(x3-x3.min())/max(np.ptp(x3),1e-9); r3=spec.body_radius_m-(spec.body_radius_m-spec.body_radius_m*0.34)*frac**1.25
    body=_lathe_mesh(np.concatenate([x1,x2,x3]),np.concatenate([r1,r2,r3]),spec.circum_segments)
    steel=Material(name='brushed_steel_ceramic_tps',metallic=0.72,roughness=0.24,specular=0.65); fins=Material(name='black_ceramic_fins',metallic=0.12,roughness=0.65,specular=0.22)
    out=[MeshInstance(body,steel,transform.matrix())]
    for i in range(spec.fin_count): out.append(MeshInstance(_fin(spec,i),fins,transform.matrix()))
    return out
