"""Real Gamma/Beta/error functions and optional Bessel/Legendre/Airy evaluation (33)."""
import math
from ._area_utils import calculate as _calculate


def special_functions(kind, x, *, y=None, order=0):
    if type(x) not in (int,float) or not math.isfinite(x) or abs(x)>10000:
        raise ValueError('Special-function argument must be finite and bounded')
    if kind=='gamma':value = math.gamma(x)
    elif kind=='logabs_gamma':value = math.lgamma(x)
    elif kind=='erf':value = math.erf(x)
    elif kind=='erfc':value = math.erfc(x)
    elif kind=='beta':
        if type(y) not in (int,float) or not math.isfinite(y) or not 0<x<=10000 or not 0<y<=10000:
            raise ValueError('Real Beta requires positive bounded parameters')
        value = math.exp(math.lgamma(x)+math.lgamma(y)-math.lgamma(x+y))
    elif kind in {'bessel_j','legendre','airy_ai'}:
        if type(order) is not int or not 0<=order<=1000:raise ValueError('Invalid function order')
        try:from scipy import special
        except ImportError as error:raise ImportError('Install nablamath[scipy] for Bessel/Legendre/Airy') from error
        value = float(special.jv(order,x) if kind=='bessel_j' else special.eval_legendre(order,x) if kind=='legendre' else special.airy(x)[0])
    else:raise ValueError('Unsupported special function')
    if not math.isfinite(value):raise ArithmeticError('Special-function evaluation overflowed')
    return {'value':value,'arithmetic':'floating_point','scope':'Real numerical evaluation; no certified enclosure or symbolic identity proof.'}


def calculate(**arguments):return _calculate('special_functions',**arguments)
