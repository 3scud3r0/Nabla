"""Finite sums of Dirac derivatives, plus regular polynomial distributions."""
from .._structured import expression,sympy
from ...ops._area_utils import scalar


def dirac_pairing(terms,test_function,variable='x'):
    sp=sympy();f,(x,)=expression(test_function,[variable]);total=sp.Integer(0)
    if not isinstance(terms,list) or len(terms)>128:raise ValueError('Dirac sum budget exceeded')
    for term in terms:
        if set(term)!={'weight','point','order'} or type(term['order']) is not int or not 0<=term['order']<=16:raise ValueError('Invalid Dirac derivative')
        w,a=(sp.Rational(str(scalar(term[k]))) for k in ('weight','point'))
        total+=w*(-1)**term['order']*sp.diff(f,x,term['order']).subs(x,a)
    return {'pairing':str(sp.simplify(total)),'scope':'Finite Dirac derivatives acting on the supplied smooth test germ.'}


def derivative(terms,order=1):
    if type(order) is not int or not 0<=order<=16:raise ValueError('Invalid derivative order')
    # Reuse the closed input validation without executing caller code.
    dirac_pairing(terms,'1')
    output=[{**term,'order':term['order']+order} for term in terms]
    if any(term['order']>16 for term in output):raise ValueError('Derivative budget exceeded')
    return output


def fourier(terms,frequency='w'):
    sp=sympy();dirac_pairing(terms,'1');_,(w,)=expression(frequency,[frequency]);value=0
    for term in terms:
        weight,point=(sp.Rational(str(scalar(term[k]))) for k in ('weight','point'))
        value+=weight*(sp.I*w)**term['order']*sp.exp(-sp.I*w*point)
    return {'transform':str(value),'convention':'F[T](w)=<T, exp(-I*w*x)>; no 2*pi normalization'}


def regular_pairing(density,test_function,lower,upper,variable='x'):
    sp=sympy();p,(x,)=expression(density,[variable],functions=False);f,_=expression(test_function,[variable])
    sp.Poly(p,x,domain=sp.QQ);a,b=(sp.Rational(str(scalar(v))) for v in (lower,upper))
    if a>=b:raise ValueError('Increasing support interval required')
    result=sp.integrate(p*f,(x,a,b))
    return {'pairing':str(result),'evaluated':not result.has(sp.Integral),'support_interval':[str(a),str(b)]}
