"""Immutable sampled scenes. A polyline is a sample, not an exact continuous curve."""
from dataclasses import dataclass
from fractions import Fraction

from ..core.semantic_ir import PolynomialSpec, ScientificTask, rational


@dataclass(frozen=True)
class Scene:
    task_id: str
    label: str
    points: tuple[tuple[Fraction, Fraction], ...]
    connected: bool = True

    def __post_init__(self) -> None:
        if not 1 <= len(self.points) <= 1024:
            raise ValueError("Cena requer de 1 a 1024 pontos")
        object.__setattr__(self, "points", tuple((rational(x), rational(y)) for x, y in self.points))

    def to_data(self) -> dict:
        return {"task_id": self.task_id, "label": self.label, "connected": self.connected,
                "representation": "rational_samples", "points": [[str(x), str(y)] for x, y in self.points]}

    def pixels(self, width: int = 640, height: int = 400) -> tuple[tuple[int, int], ...]:
        if not 64 <= width <= 2048 or not 64 <= height <= 2048:
            raise ValueError("Dimensões de imagem fora do limite")
        xs, ys = zip(*self.points)
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        dx, dy = xmax - xmin or Fraction(1), ymax - ymin or Fraction(1)
        return tuple((20 + round((x - xmin) / dx * (width - 40)),
                      height - 20 - round((y - ymin) / dy * (height - 40))) for x, y in self.points)


def task_scene(task: ScientificTask, solution: tuple[Fraction, ...]) -> Scene:
    if task.family == "polynomial_integral":
        polynomial = PolynomialSpec(task.coefficients)
        points = tuple((Fraction(i, 8), polynomial.evaluate(Fraction(i, 8))) for i in range(-16, 17))
        return Scene(task.content_id, "Integrando: amostras racionais em [-2, 2]; eixos autoescalados", points)
    return Scene(task.content_id, "Solucao: indice da coordenada versus valor; eixos autoescalados",
                 tuple((Fraction(i + 1), rational(value)) for i, value in enumerate(solution)), False)


# Version 2 is additive: Scene/task_scene v1 and their exact serialized bytes remain supported.
import json
import re
from ..core.semantic_ir import canonical_json,fingerprint
from .coordinate_system import CoordinateSystem
from .geometry_constraints import GeometryConstraint


def _identifier(name):
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,31}',name):
        raise ValueError('Identificador de cena invalido')


@dataclass(frozen=True)
class Point:
    name: str
    x: Fraction
    y: Fraction

    def __post_init__(self):
        _identifier(self.name)
        object.__setattr__(self,'x',rational(self.x));object.__setattr__(self,'y',rational(self.y))


@dataclass(frozen=True)
class Segment:
    name: str
    start: str
    end: str

    def __post_init__(self):
        for name in (self.name,self.start,self.end):_identifier(name)
        if self.start==self.end:raise ValueError('Segmento requer referencias distintas')


@dataclass(frozen=True)
class Circle:
    name: str
    center: str
    radius_squared: Fraction

    def __post_init__(self):
        _identifier(self.name);_identifier(self.center)
        object.__setattr__(self,'radius_squared',rational(self.radius_squared))
        if self.radius_squared<=0:raise ValueError('Circulo requer raio positivo')


@dataclass(frozen=True)
class Polyline:
    name: str
    coordinates: tuple[tuple[Fraction,Fraction],...]
    role: str='sampled_curve'

    def __post_init__(self):
        _identifier(self.name)
        if not 1<=len(self.coordinates)<=2048 or self.role not in {'sampled_curve','numerical_trajectory'}:
            raise ValueError('Curva excede limites ou tem papel desconhecido')
        object.__setattr__(self,'coordinates',tuple((rational(x),rational(y)) for x,y in self.coordinates))


@dataclass(frozen=True)
class Arrow:
    name: str
    start: tuple[Fraction,Fraction]
    end: tuple[Fraction,Fraction]
    vector: tuple[Fraction,Fraction]

    def __post_init__(self):
        _identifier(self.name)
        for field in ('start','end','vector'):
            values=getattr(self,field)
            if len(values)!=2:raise ValueError('Vetor deve ser planar')
            object.__setattr__(self,field,tuple(rational(v) for v in values))


@dataclass(frozen=True)
class GeometryScene:
    title: str
    coordinates: CoordinateSystem
    points: tuple[Point,...]=()
    segments: tuple[Segment,...]=()
    circles: tuple[Circle,...]=()
    curves: tuple[Polyline,...]=()
    arrows: tuple[Arrow,...]=()
    constraints: tuple[GeometryConstraint,...]=()
    model_json: str='{}'

    def __post_init__(self):
        if not isinstance(self.title,str) or not self.title.strip() or len(self.title)>200:
            raise ValueError('Titulo de cena invalido')
        for name in ('points','segments','circles','curves','arrows','constraints'):
            object.__setattr__(self,name,tuple(getattr(self,name)))
        objects=(*self.points,*self.segments,*self.circles,*self.curves,*self.arrows)
        if not 1<=len(objects)<=2048 or len(self.points)>512 or len(self.constraints)>512 or len(self.arrows)>256:
            raise ValueError('Cena excede limites de objetos')
        names=[obj.name for obj in objects]
        if len(names)!=len(set(names)):raise ValueError('Nomes de objetos repetidos')
        point_names={p.name for p in self.points}
        references=[n for segment in self.segments for n in (segment.start,segment.end)]
        references.extend(circle.center for circle in self.circles)
        references.extend(n for constraint in self.constraints for n in constraint.points)
        if any(n not in point_names for n in references):raise ValueError('Referencia a ponto ausente')
        if len(self.model_json)>64000 or not isinstance(json.loads(self.model_json),dict):
            raise ValueError('Modelo cientifico invalido')
        object.__setattr__(self,'model_json',canonical_json(json.loads(self.model_json)))
        if sum(len(curve.coordinates) for curve in self.curves)>20000:
            raise ValueError('Total de amostras excede limite')

    def to_data(self):
        return {'schema_version':2,'title':self.title,'coordinates':self.coordinates.to_data(),
            'points':[{'name':p.name,'x':str(p.x),'y':str(p.y)} for p in self.points],
            'segments':[{'name':s.name,'start':s.start,'end':s.end} for s in self.segments],
            'circles':[{'name':c.name,'center':c.center,'radius_squared':str(c.radius_squared)} for c in self.circles],
            'curves':[{'name':c.name,'coordinates':[[str(x),str(y)] for x,y in c.coordinates],'role':c.role} for c in self.curves],
            'arrows':[{'name':a.name,'start':list(map(str,a.start)),'end':list(map(str,a.end)),'vector':list(map(str,a.vector))} for a in self.arrows],
            'constraints':[c.to_data() for c in self.constraints],'model':json.loads(self.model_json)}

    @property
    def content_id(self):return fingerprint(self.to_data())

    @classmethod
    def from_data(cls,data):
        fields={'schema_version','title','coordinates','points','segments','circles','curves','arrows','constraints','model'}
        if not isinstance(data,dict) or set(data)!=fields or data['schema_version']!=2:
            raise ValueError('Contrato de cena desconhecido')
        coords=dict(data['coordinates'])
        scene=cls(data['title'],CoordinateSystem(**coords),
            tuple(Point(**p) for p in data['points']),tuple(Segment(**s) for s in data['segments']),
            tuple(Circle(**c) for c in data['circles']),
            tuple(Polyline(c['name'],tuple(tuple(p) for p in c['coordinates']),c['role']) for c in data['curves']),
            tuple(Arrow(a['name'],a['start'],a['end'],a['vector']) for a in data['arrows']),
            tuple(GeometryConstraint(c['kind'],tuple(c['points']),c['value']) for c in data['constraints']),canonical_json(data['model']))
        if scene.to_data()!=data:raise ValueError('Cena nao canonica')
        return scene
