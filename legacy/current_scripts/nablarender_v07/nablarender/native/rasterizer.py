from __future__ import annotations
import math, numpy as np
from ..core.math3d import normalize

def _edge(ax,ay,bx,by,px,py): return (px-ax)*(by-ay)-(py-ay)*(bx-ax)
def render_triangles(width,height,clip_positions,world_positions,normals,colors,faces,light_dir,light_color,ambient,material_params,background):
    color=np.zeros((height,width,3),float); depth=np.full((height,width),np.inf); normal_buf=np.zeros((height,width,3)); pos_buf=np.full((height,width,3),np.nan); color[:]=background
    sx=(clip_positions[:,0]*.5+.5)*(width-1); sy=(1-(clip_positions[:,1]*.5+.5))*(height-1); sz=clip_positions[:,2]
    ldir=normalize(np.asarray(light_dir,float)); lcol=np.asarray(light_color,float); amb=np.asarray(ambient,float); rough=float(material_params.get('roughness',.32)); metal=float(material_params.get('metallic',.4)); spec=float(material_params.get('specular',.5)); mode=material_params.get('mode','beauty')
    for tri in faces:
        i0,i1,i2=map(int,tri); x0,y0,z0=sx[i0],sy[i0],sz[i0]; x1,y1,z1=sx[i1],sy[i1],sz[i1]; x2,y2,z2=sx[i2],sy[i2],sz[i2]; area=_edge(x0,y0,x1,y1,x2,y2)
        if abs(area)<1e-10: continue
        minx=max(0,int(math.floor(min(x0,x1,x2)))); maxx=min(width-1,int(math.ceil(max(x0,x1,x2)))); miny=max(0,int(math.floor(min(y0,y1,y2)))); maxy=min(height-1,int(math.ceil(max(y0,y1,y2))))
        for py in range(miny,maxy+1):
            for px in range(minx,maxx+1):
                w0=_edge(x1,y1,x2,y2,px+.5,py+.5)/area; w1=_edge(x2,y2,x0,y0,px+.5,py+.5)/area; w2=1-w0-w1
                if w0<0 or w1<0 or w2<0: continue
                z=w0*z0+w1*z1+w2*z2
                if z>=depth[py,px]: continue
                p=w0*world_positions[i0]+w1*world_positions[i1]+w2*world_positions[i2]; n=normalize(w0*normals[i0]+w1*normals[i1]+w2*normals[i2]); alb=np.clip(w0*colors[i0]+w1*colors[i1]+w2*colors[i2],0,1)
                ndl=max(0,float(n@(-ldir))); view=normalize(-p); halfv=normalize((-ldir)+view); ndh=max(0,float(n@halfv)); sh=max(4,2+(1-rough)*100); sp=(ndh**sh)*spec*(.06+metal*.45)
                final=alb*(amb+ndl*lcol)+sp
                if mode=='thermal': heat=float(np.clip(alb.mean(),0,1)); final=np.array([min(1,heat*1.35),heat**.6,max(.05,1-heat*.7)])
                if mode=='infrared': heat=float(np.clip(alb.mean(),0,1)); final=np.array([heat,heat**.75,0.03])
                if mode=='xray': rim=(1-max(0,float(n@view)))**.55; final=np.array([.35,.9,1.0])*(.18+rim*.82)
                color[py,px]=np.clip(final,0,1); depth[py,px]=z; normal_buf[py,px]=n; pos_buf[py,px]=p
    return color,depth,normal_buf,pos_buf
