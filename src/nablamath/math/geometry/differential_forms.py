"""Coordinate differential forms over a closed symbolic expression grammar."""
from itertools import combinations
from .._structured import expression, names, sympy, data


def _form(coordinates, components):
    coordinates=names(coordinates,8);sp=sympy();result={}
    if not isinstance(components,dict) or len(components)>256:raise ValueError('Finite form components required')
    for key,value in components.items():
        indices=tuple(int(i) for i in key.split(',')) if key else ()
        if tuple(sorted(set(indices)))!=indices or any(not 0<=i<len(coordinates) for i in indices):raise ValueError('Canonical increasing form indices required')
        result[indices]=expression(value,coordinates)[0]
    if len({len(k) for k in result})>1:raise ValueError('A differential form has one degree')
    return coordinates,result


def _wedge(a,b):
    sp=sympy();result={}
    for left,x in a.items():
        for right,y in b.items():
            if set(left)&set(right):continue
            sign=(-1)**sum(i>j for i in left for j in right);key=tuple(sorted(left+right))
            result[key]=sp.expand(result.get(key,0)+sign*x*y)
    return {k:v for k,v in result.items() if v!=0}


def exterior_derivative(coordinates,components):
    coordinates,form=_form(coordinates,components);sp=sympy();out={}
    for key,value in form.items():
        for i,name in enumerate(coordinates):
            for target,coefficient in _wedge({(i,):sp.diff(value,sp.Symbol(name))},{key:sp.Integer(1)}).items():
                out[target]=sp.expand(out.get(target,0)+coefficient)
    return {','.join(map(str,k)):str(v) for k,v in out.items() if v!=0}


def wedge(coordinates,left,right):
    _,a=_form(coordinates,left);_,b=_form(coordinates,right)
    return {','.join(map(str,k)):str(v) for k,v in _wedge(a,b).items()}


def pullback(source_coordinates,target_coordinates,mapping,components):
    sp=sympy();target_coordinates,form=_form(target_coordinates,components);source_coordinates=names(source_coordinates,8)
    if len(mapping)!=len(target_coordinates):raise ValueError('Map dimension mismatch')
    functions=[expression(v,source_coordinates)[0] for v in mapping]
    substitution=dict(zip(map(sp.Symbol,target_coordinates),functions));result={}
    for key,value in form.items():
        term={():value.subs(substitution,simultaneous=True)}
        for i in key:
            term=_wedge(term,{(j,):sp.diff(functions[i],sp.Symbol(name)) for j,name in enumerate(source_coordinates)})
        for k,v in term.items():result[k]=sp.expand(result.get(k,0)+v)
    return {','.join(map(str,k)):str(v) for k,v in result.items() if v!=0}


def integrate_box(coordinates,components,bounds):
    sp=sympy();coordinates,form=_form(coordinates,components);n=len(coordinates)
    if set(form)-{tuple(range(n))} or len(bounds)!=n:raise ValueError('Top-degree form and one interval per coordinate required')
    value=form.get(tuple(range(n)),sp.Integer(0))
    from ...ops._area_utils import scalar
    for name,interval in zip(coordinates,bounds):
        if len(interval)!=2:raise ValueError('Two interval endpoints required')
        a,b=(sp.Rational(str(scalar(v))) for v in interval)
        if a>=b:raise ValueError('Increasing box intervals required')
        value=sp.integrate(value,(sp.Symbol(name),a,b))
    return {'integral':str(value),'evaluated':not value.has(sp.Integral),'orientation':list(coordinates)}
