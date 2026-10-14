"""Exact coordinate verification; pixel appearance is not accepted as evidence."""
from dataclasses import dataclass
from ..core.semantic_ir import fingerprint


@dataclass(frozen=True)
class GeometryVerification:
    scene_id: str
    valid: bool
    checks: tuple[dict,...]
    formal_proof: bool=False

    def to_data(self):
        payload={'scene_id':self.scene_id,'valid':self.valid,'checks':list(self.checks),'formal_proof':False,
                 'method':'exact_rational_coordinate_constraints_v1'}
        return {**payload,'certificate_id':fingerprint(payload)}


def verify_geometry(scene):
    points={p.name:(p.x,p.y) for p in scene.points};checks=[]
    def distance(a,b):return (a[0]-b[0])**2+(a[1]-b[1])**2
    def vector(a,b):return b[0]-a[0],b[1]-a[1]
    def cross(a,b):return a[0]*b[1]-a[1]*b[0]
    for segment in scene.segments:
        value=distance(points[segment.start],points[segment.end])
        checks.append({'object':segment.name,'relation':'nondegenerate_segment','actual':str(value),'valid':value>0})
    for constraint in scene.constraints:
        p=[points[name] for name in constraint.points];kind=constraint.kind;expected=constraint.value
        if kind in {'coincident','distinct','distance_squared','on_circle'}:
            actual=distance(*p)
            valid=(actual==0 if kind=='coincident' else actual!=0 if kind=='distinct' else actual==expected)
        elif kind in {'collinear','noncollinear','orientation'}:
            determinant=cross(vector(p[0],p[1]),vector(p[0],p[2]));actual=determinant
            valid=determinant==0 if kind=='collinear' else determinant!=0 if kind=='noncollinear' else (determinant>0)-(determinant<0)==expected
        elif kind in {'parallel','perpendicular'}:
            a,b=vector(p[0],p[1]),vector(p[2],p[3])
            actual=cross(a,b) if kind=='parallel' else a[0]*b[0]+a[1]*b[1]
            valid=actual==0 and any(a) and any(b)
        elif kind=='equal_distance':
            actual=distance(p[0],p[1])-distance(p[2],p[3]);valid=actual==0
        elif kind=='midpoint':
            actual=(2*p[0][0]-p[1][0]-p[2][0])**2+(2*p[0][1]-p[1][1]-p[2][1])**2;valid=actual==0
        else:
            raise ValueError('Relacao geometrica desconhecida')
        checks.append({'relation':kind,'points':list(constraint.points),'actual':str(actual),
                       'expected':None if expected is None else str(expected),'valid':valid})
    return GeometryVerification(scene.content_id,all(row['valid'] for row in checks),tuple(checks))


def verify_geometry_certificate(scene,certificate):
    return verify_geometry(scene).to_data()==certificate
