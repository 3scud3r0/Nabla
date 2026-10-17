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


def high_precision(kind,x,*,parameters=(),digits=50):
    import mpmath as mp
    from .spectral import _complex
    if type(digits) is not int or not 15<=digits<=500 or len(parameters)>16:raise ValueError('Precision/parameter budget exceeded')
    z=_complex(x)
    if abs(z)>1e4:raise ValueError('Argument budget exceeded')
    with mp.workdps(digits):
        # Decimal representations preserve the supplied components; no source evaluation.
        z=mp.mpc(str(z.real),str(z.imag))
        functions={'gamma':mp.gamma,'loggamma':mp.loggamma,'erf':mp.erf,'airy_ai':mp.airyai,
                   'elliptic_k':mp.ellipk,'elliptic_e':mp.ellipe,'zeta':mp.zeta}
        if kind in functions:value=functions[kind](z)
        elif kind=='bessel_j':
            if len(parameters)!=1:raise ValueError('Bessel J needs its order')
            value=mp.besselj(mp.mpf(str(parameters[0])),z)
        elif kind=='hypergeometric':
            if len(parameters)!=2 or any(not isinstance(v,list) or len(v)>8 for v in parameters):raise ValueError('Hypergeometric numerator/denominator parameter lists required')
            value=mp.hyper([mp.mpf(str(v)) for v in parameters[0]],[mp.mpf(str(v)) for v in parameters[1]],z,maxterms=100000)
        else:raise ValueError('Unsupported high-precision special function')
        if not mp.isfinite(value):raise ArithmeticError('Nonfinite special-function result')
        return {'real':mp.nstr(value.real,digits),'imaginary':mp.nstr(value.imag,digits),
                'digits':digits,'branch':'mpmath principal branches','certified_enclosure':False}
