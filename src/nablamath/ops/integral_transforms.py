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


def symbolic_transform(kind,source,variable='t',parameter='s'):
    from ..math._structured import expression,sympy
    sp=sympy()
    if variable==parameter:raise ValueError('Transform variables must differ')
    f,(t,s)=expression(source,[variable,parameter]);conditions=None
    if kind=='laplace':value,abscissa,conditions=sp.laplace_transform(f,t,s);conditions={'abscissa':str(abscissa),'conditions':str(conditions)}
    elif kind=='inverse_laplace':value=sp.inverse_laplace_transform(f,s,t)
    elif kind=='fourier':value=sp.fourier_transform(f,t,s)
    elif kind=='inverse_fourier':value=sp.inverse_fourier_transform(f,s,t)
    elif kind=='mellin':
        result=sp.mellin_transform(f,t,s)
        if isinstance(result,tuple):value,strip,condition=result;conditions={'strip':list(map(str,strip)),'conditions':str(condition)}
        else:value=result
    else:raise ValueError('Unsupported symbolic transform')
    return {'expression':str(value),'conditions':conditions,
            'evaluated':not value.has(sp.Integral,sp.LaplaceTransform,sp.InverseLaplaceTransform,sp.FourierTransform,sp.InverseFourierTransform,sp.MellinTransform),
            'scope':'Closed AST delegated to SymPy; unevaluated transforms are reported explicitly, no formal certificate.'}


def oscillatory_integral(source,lower,upper,frequency,*,weight='cos',variable='x',tolerance=1e-9):
    from scipy.integrate import quad
    from ..math._structured import expression,sympy
    from ._area_utils import scalar
    import math
    f,(x,)=expression(source,[variable]);sp=sympy();a,b,w=(float(scalar(v)) for v in (lower,upper,frequency))
    if not all(math.isfinite(v) for v in (a,b,w,tolerance)) or a>=b or not 0<tolerance<1 or weight not in {'sin','cos'}:raise ValueError('Invalid oscillatory quadrature data')
    def evaluate(value):return float(f.subs(x,sp.Float(value)))
    value,error=quad(evaluate,a,b,weight=weight,wvar=w,epsabs=tolerance,epsrel=tolerance,limit=256)
    return {'value':value,'estimated_absolute_error':error,'certified_enclosure':False}
