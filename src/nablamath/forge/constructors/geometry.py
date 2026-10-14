"""Inverse exact Euclidean scenes, rotated by a rational orthogonal transform."""
from fractions import Fraction
from math import isqrt
from ...core.semantic_ir import canonical_json
from ...graphics.scene_graph import GeometryScene,Point,Segment,Circle
from ...graphics.geometry_constraints import GeometryConstraint as Constraint
from ...graphics.coordinate_system import CoordinateSystem
from ...math.geometry.conics import circumcenter
from ...math.geometry.euclidean import Point2
from ..sampling import rng_for

KINDS=('right_triangle','parallelogram','circumcircle')


def construct(seed=42,size=3,kind='right_triangle'):
    rng=rng_for(seed,size)
    if kind not in KINDS:raise ValueError('Construcao geometrica desconhecida')
    t=Fraction(rng.randint(1,3),rng.randint(2,5));cos=(1-t*t)/(1+t*t);sin=2*t/(1+t*t)
    tx,ty=Fraction(rng.randint(-2,2)),Fraction(rng.randint(-2,2))
    a,b=Fraction(rng.randint(2,size+4)),Fraction(rng.randint(2,size+4))
    def point(name,x,y):return Point(name,tx+cos*x-sin*y,ty+sin*x+cos*y)
    circles=[];constraints=[]
    if kind=='parallelogram':
        shift=Fraction(rng.randint(1,3))
        points=[point('A',0,0),point('B',a,0),point('C',a+shift,b),point('D',shift,b),point('O',(a+shift)/2,b/2)]
        segments=[Segment('AB','A','B'),Segment('BC','B','C'),Segment('CD','C','D'),Segment('DA','D','A'),Segment('AC','A','C'),Segment('BD','B','D')]
        constraints=[Constraint('parallel',('A','B','D','C')),Constraint('parallel',('A','D','B','C')),
                     Constraint('midpoint',('O','A','C')),Constraint('midpoint',('O','B','D')),
                     Constraint('equal_distance',('A','B','D','C')),Constraint('noncollinear',('A','B','D'))]
    else:
        shift=Fraction() if kind=='right_triangle' else Fraction(rng.randint(1,3))
        points=[point('A',0,0),point('B',a,0),point('C',shift,b)]
        aa,bb,cc=(Point2(p.x,p.y) for p in points)
        center=circumcenter(aa,bb,cc);points.append(Point('O',center.x,center.y))
        r2=(aa.x-center.x)**2+(aa.y-center.y)**2
        circles=[Circle('circumcircle','O',r2)]
        segments=[Segment('AB','A','B'),Segment('AC','A','C'),Segment('BC','B','C')]
        constraints=[Constraint('noncollinear',('A','B','C'))]+[Constraint('on_circle',(name,'O'),r2) for name in ('A','B','C')]
        if kind=='right_triangle':constraints.extend((Constraint('perpendicular',('A','B','A','C')),Constraint('midpoint',('O','B','C'))))
    xs=[p.x for p in points];ys=[p.y for p in points]
    for circle in circles:
        center=next(p for p in points if p.name==circle.center)
        # Integer outward enclosure, retaining exact squared radius in the object.
        radius=1+isqrt(circle.radius_squared.numerator//circle.radius_squared.denominator)
        xs.extend((center.x-radius,center.x+radius));ys.extend((center.y-radius,center.y+radius))
    coordinates=CoordinateSystem(min(xs)-1,max(xs)+1,min(ys)-1,max(ys)+1)
    model={'kind':'inverse_geometry','construction':kind,'seed':seed,'size':size,'generator_version':'geometry-v1'}
    return GeometryScene('Exact '+kind.replace('_',' '),coordinates,tuple(points),tuple(segments),tuple(circles),
                         constraints=tuple(constraints),model_json=canonical_json(model))
