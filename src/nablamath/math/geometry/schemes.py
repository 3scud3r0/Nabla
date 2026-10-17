"""Affine rational polynomial schemes and explicit projective charts.

Ideal computations use a bounded SymPy Groebner backend; no arbitrary CAS text.
Primary decomposition below is deliberately univariate, where factorization is
an actual complete algorithm over Q. No general primary decomposition is implied.
"""
from itertools import combinations
from .._structured import expression,names,sympy,data


def _ideal(equations,variables):
    sp=sympy();variables=names(variables,6)
    if not isinstance(equations,list) or not 1<=len(equations)<=32:raise ValueError('Require 1–32 polynomial generators')
    symbols=tuple(map(sp.Symbol,variables));polynomials=[]
    for raw in equations:
        value,_=expression(raw,variables,functions=False,degree_limit=16)
        p=sp.Poly(value,*symbols,domain=sp.QQ)
        if p.total_degree()>16 or len(p.terms())>256:raise ValueError('Polynomial budget exceeded')
        polynomials.append(p.as_expr())
    return sp,variables,symbols,polynomials


def affine_scheme(equations,variables):
    sp,variables,symbols,polynomials=_ideal(equations,variables)
    gb=sp.groebner(polynomials,*symbols,order='lex',domain=sp.QQ)
    if any(p.as_expr()==1 for p in gb.polys):
        return {'groebner_basis':['1'],'dimension':-1,'empty':True,'zero_dimensional':False}
    supports=[{i for i,power in enumerate(p.monoms()[0]) if power} for p in gb.polys if p.as_expr()!=0]
    height=next(k for k in range(len(symbols)+1) if any(all(set(c)&s for s in supports) for c in combinations(range(len(symbols)),k))) if supports else 0
    return {'groebner_basis':[str(p.as_expr()) for p in gb.polys],'dimension':len(symbols)-height,
            'zero_dimensional':bool(gb.is_zero_dimensional),'empty':False,
            'scope':'Affine scheme defined by the supplied ideal over Q; not automatically reduced.'}


def eliminate(equations,variables,remove):
    sp,variables,symbols,polynomials=_ideal(equations,variables)
    if not set(remove)<=set(variables):raise ValueError('Unknown elimination variable')
    removed=tuple(sp.Symbol(v) for v in remove);remaining=tuple(s for s in symbols if str(s) not in remove)
    gb=sp.groebner(polynomials,*(removed+remaining),order='lex',domain=sp.QQ)
    return {'generators':[str(p.as_expr()) for p in gb.polys if not (p.as_expr().free_symbols&set(removed))],
            'remaining_variables':list(map(str,remaining))}


def saturate(equations,variables,denominator):
    sp,variables,symbols,polynomials=_ideal(equations,variables)
    f,_=expression(denominator,variables,functions=False);sp.Poly(f,*symbols,domain=sp.QQ)
    if f==0:raise ValueError('Cannot localize at zero')
    t=sp.Dummy('localization');gb=sp.groebner(polynomials+[1-t*f],t,*symbols,order='lex',domain=sp.QQ)
    return {'generators':[str(p.as_expr()) for p in gb.polys if t not in p.as_expr().free_symbols],
            'meaning':'I : denominator^infinity; ideal of the closure of the principal-open restriction'}


def univariate_primary(polynomial,variable='x'):
    sp,_,symbols,polys=_ideal([polynomial],[variable]);p=sp.Poly(polys[0],*symbols,domain=sp.QQ)
    if p.is_zero:raise ValueError('Zero ideal requires a separate domain component')
    _,factors=sp.factor_list(p)
    return {'primary_ideals':[[str(f.as_expr()**m)] for f,m in factors],
            'radical_generator':str(sp.prod(f.as_expr() for f,_ in factors)),
            'reduced':all(m==1 for _,m in factors),'coefficient_field':'Q'}


def projective_chart(equations,variables,index):
    sp,variables,symbols,polys=_ideal(equations,variables)
    if type(index) is not int or not 0<=index<len(symbols):raise ValueError('Invalid projective chart')
    for p in polys:
        degrees={sum(m) for m,c in sp.Poly(p,*symbols).terms() if c}
        if len(degrees)>1:raise ValueError('Projective equations must be homogeneous')
    return {'variables':[v for i,v in enumerate(variables) if i!=index],
            'equations':[str(p.subs(symbols[index],1)) for p in polys],
            'chart':variables[index]+' != 0'}


def _quotient_dimension(gb):
    from itertools import product
    leading=[p.monoms()[0] for p in gb.polys if p.as_expr()!=0];n=len(gb.gens)
    if any(not any(m) for m in leading):return 0
    bounds=[]
    for i in range(n):
        powers=[m[i] for m in leading if m[i] and all(v==0 for j,v in enumerate(m) if j!=i)]
        if not powers:raise ValueError('Zero-dimensional ideal required')
        bounds.append(min(powers))
    import math
    if math.prod(bounds)>4096:raise ValueError('Quotient staircase budget exceeded')
    return sum(not any(all(a>=b for a,b in zip(monomial,lead)) for lead in leading) for monomial in product(*(range(v) for v in bounds)))


def zero_dimensional_radical(equations,variables):
    sp,variables,symbols,polys=_ideal(equations,variables);gb=sp.groebner(polys,*symbols,domain=sp.QQ,order='lex')
    if any(p.as_expr()==1 for p in gb.polys):return {'generators':['1'],'quotient_dimension':0}
    dimension=_quotient_dimension(gb)
    if dimension>128:raise ValueError('Radical quotient dimension budget exceeded')
    additions=[]
    for s in symbols:
        order=tuple(v for v in symbols if v!=s)+(s,);elimination=sp.groebner(polys,*order,domain=sp.QQ,order='lex')
        candidates=[sp.Poly(p.as_expr(),s,domain=sp.QQ) for p in elimination.polys if p.as_expr()!=0 and p.as_expr().free_symbols<={s}]
        if not candidates:raise ArithmeticError('Zero-dimensional elimination failed')
        minimal=min(candidates,key=lambda p:p.degree());additions.append(minimal.sqf_part().as_expr())
    radical=sp.groebner(polys+additions,*symbols,domain=sp.QQ,order='lex')
    return {'generators':[str(p.as_expr()) for p in radical.polys],'quotient_dimension':_quotient_dimension(radical),
            'original_quotient_dimension':dimension,'scope':'Exact radical of a zero-dimensional Q ideal via square-free coordinate annihilators.'}


def zero_dimensional_primary(equations,variables):
    sp,variables,symbols,polys=_ideal(equations,variables);radical=zero_dimensional_radical(equations,variables);dimension=radical['quotient_dimension']
    if dimension==0:return {'primary_ideals':[],'empty':True}
    t=sp.Dummy('primitive');chosen=None
    for base in range(1,17):
        linear=sum(base**i*s for i,s in enumerate(symbols));gb=sp.groebner(polys+[t-linear],*symbols,t,order='lex',domain=sp.QQ)
        univariate=[sp.Poly(p.as_expr(),t,domain=sp.QQ) for p in gb.polys if p.as_expr()!=0 and p.as_expr().free_symbols<={t}]
        if not univariate:continue
        minimal=min(univariate,key=lambda p:p.degree())
        if minimal.sqf_part().degree()==dimension:chosen=(linear,minimal);break
    if chosen is None:raise ArithmeticError('Separating linear form search budget exhausted')
    linear,minimal=chosen;_,factors=sp.factor_list(minimal);components=[]
    for factor,multiplicity in factors:
        relation=factor.as_expr().subs(t,linear)**multiplicity
        component=sp.groebner(polys+[relation],*symbols,order='lex',domain=sp.QQ)
        components.append([str(p.as_expr()) for p in component.polys])
    return {'primary_ideals':components,'separating_form':str(linear),'annihilator':str(minimal.as_expr()).replace(str(t),'T'),
            'scope':'Zero-dimensional rational primary decomposition using a separating reduced-algebra primitive element; no positive-dimensional decomposition claim.'}
