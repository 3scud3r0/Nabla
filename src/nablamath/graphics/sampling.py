"""Model-linked rational curve/field samples and explicitly numerical phase trajectories."""
from fractions import Fraction
import json
from ..core.semantic_ir import SemanticExpression,canonical_json,rational
from ..core.precision import RationalInterval
from ..expression import Binary,Number,Symbol,evaluate,parse_expr,DomainError,to_data
from ..math.equations.ode import integrate
from .scene_graph import GeometryScene,Polyline,Arrow
from .coordinate_system import CoordinateSystem


def _interval(expr,lower,upper):
    if isinstance(expr,Number):return RationalInterval(expr.value,expr.value)
    if isinstance(expr,Symbol):return RationalInterval(lower,upper)
    left,right=_interval(expr.left,lower,upper),_interval(expr.right,lower,upper)
    if expr.op=='+':return left+right
    if expr.op=='-':return left+RationalInterval(-right.upper,-right.lower)
    if expr.op=='*':return left*right
    if expr.op=='/':return left/right
    exponent=expr.right.value.numerator
    if exponent<0:return RationalInterval(1,1)/_interval(Binary('**',expr.left,Number(Fraction(-exponent))),lower,upper)
    if exponent==0:return RationalInterval(1,1)
    values=(left.lower**exponent,left.upper**exponent)
    return RationalInterval(0 if exponent%2==0 and left.lower<=0<=left.upper else min(values),max(values))


def function_scene(source,*,xmin=-2,xmax=2,samples=65):
    if type(samples) is not int or not 3<=samples<=513:
        raise ValueError('Curva requer 3..513 amostras')
    semantic=SemanticExpression.parse(source)
    if set(n for n,_ in semantic.variable_types)-{'x'}:
        raise ValueError('Curva aceita apenas a variavel x')
    xmin,xmax=rational(xmin),rational(xmax)
    if xmin>=xmax:raise ValueError('Intervalo de curva invalido')
    curves=[];current=[];invalid=0;guarded=0;all_points=[]
    def flush():
        nonlocal current
        if current:curves.append(Polyline('curve'+str(len(curves)),tuple(current)))
        current=[]
    previous=None
    for i in range(samples):
        x=xmin+(xmax-xmin)*i/(samples-1)
        try:
            y=evaluate(semantic.expression,{'x':x});rational(y)
            if previous is not None:
                continuous=True
                for obligation in semantic.obligations:
                    try:
                        bound=_interval(obligation.expression,previous,x)
                        if bound.lower<=0<=bound.upper:continuous=False
                    except (ValueError,ArithmeticError):continuous=False
                if not continuous:flush();guarded+=1
            current.append((x,y));all_points.append((x,y));previous=x
        except (DomainError,ZeroDivisionError):
            flush();previous=None;invalid+=1
    flush()
    if not all_points:raise ValueError('Nenhuma amostra definida no intervalo')
    ys=[y for _,y in all_points];ymin,ymax=min(ys),max(ys);padding=(ymax-ymin)/10 or Fraction(1)
    coordinates=CoordinateSystem(xmin,xmax,ymin-padding,ymax+padding,preserve_aspect=False)
    model={'kind':'function','source':source,'xmin':str(xmin),'xmax':str(xmax),'samples':samples,
           'undefined_samples':invalid,'guarded_intervals':guarded,'continuity_guard':'conservative interval exclusion of domain zeroes'}
    return GeometryScene('Rational function samples',coordinates,curves=tuple(curves),model_json=canonical_json(model))


def vector_field_scene(dx='-y',dy='x',*,bounds=(-2,2,-2,2),grid=9):
    if type(grid) is not int or not 2<=grid<=16 or len(bounds)!=4:
        raise ValueError('Campo requer grade de 2..16 por eixo')
    expressions=(SemanticExpression.parse(dx).expression,SemanticExpression.parse(dy).expression)
    from ..formal.translate import free_symbols
    if any(set(free_symbols(expr))-{'x','y'} for expr in expressions):
        raise ValueError('Campo aceita apenas x e y')
    c=CoordinateSystem(*bounds);arrows=[];undefined=0;stationary=0
    spacing=min(c.xmax-c.xmin,c.ymax-c.ymin)/(grid-1)
    for i in range(grid):
        for j in range(grid):
            x=c.xmin+(c.xmax-c.xmin)*i/(grid-1);y=c.ymin+(c.ymax-c.ymin)*j/(grid-1)
            try:
                u,v=(evaluate(expr,{'x':x,'y':y}) for expr in expressions);rational(u);rational(v)
            except (DomainError,ZeroDivisionError):undefined+=1;continue
            magnitude=max(abs(u),abs(v))
            if not magnitude:stationary+=1;continue
            scale=spacing*Fraction(3,8)/magnitude
            arrows.append(Arrow(f'vector{i}_{j}',(x,y),(x+scale*u,y+scale*v),(u,v)))
    if not arrows:raise ValueError('Campo sem vetores nao nulos definidos')
    model={'kind':'vector_field','dx':dx,'dy':dy,'bounds':[str(rational(v)) for v in bounds],'grid':grid,
           'normalization':'display length scaled by infinity norm; raw vector retained','undefined_samples':undefined,'stationary_samples':stationary}
    return GeometryScene('Vector field',c,arrows=tuple(arrows),model_json=canonical_json(model))


def phase_portrait_scene(dx='y',dy='-x',*,initials=((1,0),(0,1)),duration=6,steps=300,bounds=(-2,2,-2,2),grid=9):
    if type(steps) is not int or not 2<=steps<=2000 or not 1<=len(initials)<=8 or any(len(v)!=2 for v in initials):
        raise ValueError('Retrato requer 1..8 trajetorias e 2..2000 passos')
    duration=rational(duration)
    if not 0<duration<=100:raise ValueError('Duracao deve ser positiva e limitada a 100')
    field=vector_field_scene(dx,dy,bounds=bounds,grid=grid)
    expressions=(parse_expr(dx),parse_expr(dy));curves=[]
    def derivative(time,state):
        values={'x':Fraction(str(state[0])),'y':Fraction(str(state[1]))}
        return tuple(float(evaluate(expr,values)) for expr in expressions)
    normalized=tuple(tuple(rational(v) for v in state) for state in initials)
    for i,state in enumerate(normalized):
        result=integrate(derivative,tuple(float(v) for v in state),0,float(duration),steps,'rk4')
        coordinates=tuple((Fraction(str(x)),Fraction(str(y))) for _,(x,y) in result)
        curves.append(Polyline(f'trajectory{i}',coordinates,'numerical_trajectory'))
    model={'kind':'phase_portrait','dx':dx,'dy':dy,'initials':[[str(v) for v in row] for row in normalized],
           'duration':str(duration),'steps':steps,'method':'rk4_float','bounds':[str(rational(v)) for v in bounds],
           'grid':grid,'limitation':'Numerical trajectories, no experimental validation or analytic guarantee.'}
    return GeometryScene('Phase portrait: RK4 samples',field.coordinates,curves=tuple(curves),arrows=field.arrows,model_json=canonical_json(model))
