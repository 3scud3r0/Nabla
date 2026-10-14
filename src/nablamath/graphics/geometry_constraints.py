"""Typed coordinate relations; constraints remain data independently of rendering."""
from dataclasses import dataclass
from ..core.semantic_ir import rational

ARITY={'coincident':2,'distinct':2,'collinear':3,'noncollinear':3,'parallel':4,'perpendicular':4,
       'equal_distance':4,'distance_squared':2,'on_circle':2,'midpoint':3,'orientation':3}


@dataclass(frozen=True)
class GeometryConstraint:
    kind: str
    points: tuple[str,...]
    value: object=None

    def __post_init__(self):
        if self.kind not in ARITY or len(self.points)!=ARITY[self.kind]:
            raise ValueError('Relacao geometrica ou aridade invalida')
        object.__setattr__(self,'points',tuple(self.points))
        if self.kind in {'distance_squared','on_circle','orientation'}:
            if self.value is None:
                raise ValueError('Relacao requer valor')
            object.__setattr__(self,'value',rational(self.value))
            if self.kind!='orientation' and self.value<0:
                raise ValueError('Distancia quadrada nao pode ser negativa')
            if self.kind=='orientation' and self.value not in (-1,0,1):
                raise ValueError('Orientacao deve ser -1, 0 ou 1')
        elif self.value is not None:
            raise ValueError('Relacao nao admite valor adicional')

    def to_data(self):
        return {'kind':self.kind,'points':list(self.points),'value':None if self.value is None else str(self.value)}
