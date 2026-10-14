"""Exact world-to-screen transforms; scientific scenes preserve aspect by default."""
from dataclasses import dataclass
from fractions import Fraction
from ..core.semantic_ir import rational


@dataclass(frozen=True)
class CoordinateSystem:
    xmin: Fraction
    xmax: Fraction
    ymin: Fraction
    ymax: Fraction
    x_unit: str='1'
    y_unit: str='1'
    preserve_aspect: bool=True

    def __post_init__(self):
        for name in ('xmin','xmax','ymin','ymax'):
            object.__setattr__(self,name,rational(getattr(self,name)))
        if type(self.preserve_aspect) is not bool:
            raise ValueError('preserve_aspect deve ser booleano')
        if self.xmin>=self.xmax or self.ymin>=self.ymax or len(self.x_unit)>24 or len(self.y_unit)>24:
            raise ValueError('Limites ou unidades de coordenadas invalidos')

    def transform(self,width=800,height=600,padding=48):
        if type(width) is not int or type(height) is not int or not 128<=width<=2048 or not 128<=height<=2048:
            raise ValueError('Imagem cientifica deve ter 128..2048 pixels por eixo')
        if type(padding) is not int or not 16<=padding<min(width,height)/2:
            raise ValueError('Margem invalida')
        sx=Fraction(width-2*padding)/(self.xmax-self.xmin)
        sy=Fraction(height-2*padding)/(self.ymax-self.ymin)
        if self.preserve_aspect:
            sx=sy=min(sx,sy)
        left=(width-sx*(self.xmax-self.xmin))/2
        top=(height-sy*(self.ymax-self.ymin))/2
        return ScreenTransform(self,width,height,sx,sy,left,top)

    def to_data(self):
        return {'xmin':str(self.xmin),'xmax':str(self.xmax),'ymin':str(self.ymin),'ymax':str(self.ymax),
                'x_unit':self.x_unit,'y_unit':self.y_unit,'preserve_aspect':self.preserve_aspect}


@dataclass(frozen=True)
class ScreenTransform:
    system: CoordinateSystem
    width: int
    height: int
    sx: Fraction
    sy: Fraction
    left: Fraction
    top: Fraction

    def pixel(self,x,y):
        return (round(self.left+(rational(x)-self.system.xmin)*self.sx),
                round(self.top+(self.system.ymax-rational(y))*self.sy))

    def world(self,x,y):
        return self.system.xmin+(Fraction(x)-self.left)/self.sx,self.system.ymax-(Fraction(y)-self.top)/self.sy

    def inside(self,x,y):
        return self.system.xmin<=x<=self.system.xmax and self.system.ymin<=y<=self.system.ymax
