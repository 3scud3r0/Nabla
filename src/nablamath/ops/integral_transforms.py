"""Exact Laplace/Mellin polynomial transforms and finite real Z transforms (44)."""
import math
from ._area_utils import vector,scalar,calculate as _calculate


def integral_transforms(kind, values, parameter):
    values,s = vector(values,maximum=64),scalar(parameter)
    if kind=='laplace_polynomial':
        if s<=0:raise ValueError('Laplace polynomial transform requires positive s')
        result = sum(a*math.factorial(k)/s**(k+1) for k,a in enumerate(values))
        domain = 'Integral from zero to infinity, Re(s)>0; real rational s in this API'
    elif kind=='mellin_unit_polynomial':
        if s<=0:raise ValueError('Unit-interval Mellin transform requires positive s')
        result = sum(a/(s+k) for k,a in enumerate(values));domain = 'Integral x**(s-1) f(x) from zero to one, s>0'
    elif kind=='z_finite':
        if not s:raise ValueError('Finite Z transform excludes z=0')
        result = sum(a/s**k for k,a in enumerate(values));domain = 'Finite one-sided sequence, nonzero real rational z'
    else:raise ValueError('Unsupported integral transform')
    return {'value':result,'domain':domain,'arithmetic':'exact_rational'}


def calculate(**arguments):return _calculate('integral_transforms',**arguments)
