"""Deterministic shared geometry for SVG/PNG, clipping and collision-aware point labels."""
from fractions import Fraction
import math


def clip_line(a,b,box):
    xmin,ymin,xmax,ymax=box
    dx,dy=b[0]-a[0],b[1]-a[1];lo,hi=Fraction(),Fraction(1)
    for p,q in ((-dx,a[0]-xmin),(dx,xmax-a[0]),(-dy,a[1]-ymin),(dy,ymax-a[1])):
        if p==0:
            if q<0:return None
            continue
        ratio=Fraction(q,p)
        if p<0:lo=max(lo,ratio)
        else:hi=min(hi,ratio)
        if lo>hi:return None
    return ((round(a[0]+lo*dx),round(a[1]+lo*dy)),(round(a[0]+hi*dx),round(a[1]+hi*dy)))


def place_labels(points,width,height):
    occupied=[];placements=[];warnings=[]
    for name,x,y in points:
        w,h=7*len(name)+6,16
        candidates=((x+8,y-18),(x+8,y+6),(x-w-8,y-18),(x-w-8,y+6),(x-w//2,y-24),(x-w//2,y+10))
        selected=None
        for px,py in candidates:
            rectangle=(px,py,px+w,py+h)
            if px<2 or py<24 or px+w>width-2 or py+h>height-24:continue
            if all(rectangle[2]<=old[0] or rectangle[0]>=old[2] or rectangle[3]<=old[1] or rectangle[1]>=old[3] for old in occupied):
                selected=rectangle;break
        if selected is None:
            selected=(max(2,min(x+8,width-w-2)),max(24,min(y-18,height-h-24)),0,0)
            selected=(selected[0],selected[1],selected[0]+w,selected[1]+h)
            warnings.append('label_collision_or_clipping:'+name)
        occupied.append(selected);placements.append((name,selected[0],selected[1]))
    return placements,warnings


def build_primitives(scene,width=800,height=600):
    transform=scene.coordinates.transform(width,height)
    c=scene.coordinates
    top_left=transform.pixel(c.xmin,c.ymax);bottom_right=transform.pixel(c.xmax,c.ymin)
    box=(*top_left,*bottom_right)
    primitives=[];warnings=[]
    def line(a,b,color='#2456a6',thickness=2):
        clipped=clip_line(a,b,box)
        if clipped:primitives.append({'kind':'line','points':clipped,'color':color,'width':thickness})
    for index in range(6):
        x=c.xmin+(c.xmax-c.xmin)*index/5;y=c.ymin+(c.ymax-c.ymin)*index/5
        line(transform.pixel(x,c.ymin),transform.pixel(x,c.ymax),'#e5e7eb',1)
        line(transform.pixel(c.xmin,y),transform.pixel(c.xmax,y),'#e5e7eb',1)
    if c.xmin<=0<=c.xmax:line(transform.pixel(0,c.ymin),transform.pixel(0,c.ymax),'#777777',1)
    if c.ymin<=0<=c.ymax:line(transform.pixel(c.xmin,0),transform.pixel(c.xmax,0),'#777777',1)
    points={p.name:(p.x,p.y) for p in scene.points}
    for segment in scene.segments:
        line(transform.pixel(*points[segment.start]),transform.pixel(*points[segment.end]))
    for circle in scene.circles:
        x,y=points[circle.center];radius=math.sqrt(float(circle.radius_squared))
        samples=[transform.pixel(x+Fraction(str(radius*math.cos(i*math.tau/128))),y+Fraction(str(radius*math.sin(i*math.tau/128)))) for i in range(129)]
        for a,b in zip(samples,samples[1:]):line(a,b,'#168568',2)
    for curve in scene.curves:
        pixels=[transform.pixel(x,y) for x,y in curve.coordinates]
        color='#cc641f' if curve.role=='numerical_trajectory' else '#2456a6'
        for a,b in zip(pixels,pixels[1:]):line(a,b,color,2)
        if len(pixels)==1 and transform.inside(*curve.coordinates[0]):
            primitives.append({'kind':'point','point':pixels[0],'color':color})
    for arrow in scene.arrows:
        start,end=transform.pixel(*arrow.start),transform.pixel(*arrow.end)
        line(start,end,'#8798ad',1)
        dx,dy=end[0]-start[0],end[1]-start[1];length=math.hypot(dx,dy)
        if length>0:
            ux,uy=dx/length,dy/length
            for sign in (-1,1):
                tip=(round(end[0]-6*ux+sign*3*uy),round(end[1]-6*uy-sign*3*ux))
                line(tip,end,'#8798ad',1)
    label_points=[]
    for point in scene.points:
        if not transform.inside(point.x,point.y):
            warnings.append('point_outside_viewport:'+point.name);continue
        pixel=transform.pixel(point.x,point.y)
        primitives.append({'kind':'point','point':pixel,'color':'#17365f'})
        label_points.append((point.name,*pixel))
    labels,label_warnings=place_labels(label_points,width,height);warnings.extend(label_warnings)
    for name,x,y in labels:primitives.append({'kind':'text','position':(x,y),'text':name,'color':'#17365f'})
    primitives.extend([
        {'kind':'text','position':(12,8),'text':scene.title,'color':'#17365f'},
        {'kind':'text','position':(12,height-34),'text':f'x=[{c.xmin},{c.xmax}] {c.x_unit}; y=[{c.ymin},{c.ymax}] {c.y_unit}','color':'#555555'},
        {'kind':'text','position':(12,height-18),'text':'exact coordinate metadata; curves/trajectories are samples','color':'#555555'}])
    return primitives,{'warnings':warnings,'aspect_preserved':c.preserve_aspect,'circle_rendering':'128-segment approximation',
                       'viewport':list(box),'scene_id':scene.content_id}
