"""Adaptive complex contour quadrature and conformal Möbius maps."""
import math
from ._expressions import ScientificExpression
from .spectral import _complex


def contour_integral(source, contour, *, tolerance=1e-9, max_evaluations=100000, closed=False):
    if not isinstance(contour,(list,tuple)) or not 2 <= len(contour) <= 1024:
        raise ValueError('A contour requires 2–1024 complex vertices')
    points = [_complex(z) for z in contour]
    if type(closed) is not bool or type(max_evaluations) is not int or not 10 <= max_evaluations <= 1000000:
        raise ValueError('Invalid contour budget')
    if type(tolerance) not in (int,float) or not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('A finite positive absolute tolerance is required')
    if closed and points[0] != points[-1]:
        points.append(points[0])
    expression = ScientificExpression(source,('z',))
    count = 0
    def evaluate(z, delta):
        nonlocal count
        if count >= max_evaluations:
            raise RuntimeError('Contour evaluation budget exhausted')
        count += 1
        return expression.evaluate(z=z)*delta
    total,error = 0j,0.
    for start,end in zip(points,points[1:]):
        delta = end-start
        if not delta:
            raise ValueError('Consecutive contour vertices must be distinct')
        f = lambda t: evaluate(start+t*delta,delta)
        a,b,c = f(0),f(.5),f(1)
        whole = (a+4*b+c)/6
        stack = [(0.,1.,a,b,c,whole,tolerance/(len(points)-1),0)]
        while stack:
            lo,hi,fl,fm,fr,estimate,budget,depth = stack.pop()
            middle = (lo+hi)/2
            q1,q3 = f((lo+middle)/2),f((middle+hi)/2)
            left = (middle-lo)*(fl+4*q1+fm)/6
            right = (hi-middle)*(fm+4*q3+fr)/6
            difference = left+right-estimate
            local_error = abs(difference)/15
            if local_error <= budget:
                total += left+right+difference/15; error += local_error
            else:
                if depth >= 30:
                    raise RuntimeError('Contour refinement depth exhausted')
                stack.append((middle,hi,fm,q3,fr,right,budget/2,depth+1))
                stack.append((lo,middle,fl,q1,fm,left,budget/2,depth+1))
    return {'value':[total.real,total.imag],'estimated_absolute_error':error,'evaluations':count,
            'contour':[[z.real,z.imag] for z in points],
            'limitations':'Adaptive Simpson estimate; not a rigorous enclosure or an automatic analyticity/pole certificate.'}


def conformal_map(points, coefficients):
    if not isinstance(points,(list,tuple)) or not 1 <= len(points) <= 10000 or len(coefficients) != 4:
        raise ValueError('Möbius mapping requires points and four coefficients')
    a,b,c,d = [_complex(z) for z in coefficients]
    determinant = a*d-b*c
    if determinant == 0:
        raise ValueError('Degenerate Möbius map')
    mapped,derivatives = [],[]
    for point in points:
        z = _complex(point); denominator = c*z+d
        if denominator == 0:
            raise ZeroDivisionError('Point is a pole of the conformal map')
        value,derivative = (a*z+b)/denominator,determinant/denominator**2
        if not all(math.isfinite(v) for v in (value.real,value.imag,derivative.real,derivative.imag)):
            raise ArithmeticError('Nonfinite conformal map result')
        mapped.append([value.real,value.imag]); derivatives.append([derivative.real,derivative.imag])
    return {'values':mapped,'derivatives':derivatives,'domain':'complex plane excluding c*z+d=0',
            'limitations':'Floating point Möbius map; conditioning deteriorates near poles.'}


def complex_analysis(kind, *, source=None, contour=None, points=None, coefficients=None,
                     tolerance=1e-9,max_evaluations=100000,closed=False):
    if kind == 'contour':
        return contour_integral(source,contour,tolerance=tolerance,max_evaluations=max_evaluations,closed=closed)
    if kind == 'mobius':
        return conformal_map(points,coefficients)
    raise ValueError('Unknown complex analysis operation')


def calculate(kind, **options):
    from ..calc.session import CalculationSession
    return CalculationSession().execute('complex_analysis',kind=kind,**options)
