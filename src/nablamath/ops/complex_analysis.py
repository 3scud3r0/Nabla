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


def meromorphic_analysis(source,variable='z',point=0,order=6):
    from ..math._structured import expression,sympy
    sp=sympy();f,(z,)=expression(source,[variable]);a,_=expression(point,[variable])
    if a.free_symbols or type(order) is not int or not 1<=order<=16:raise ValueError('Constant expansion point and bounded order required')
    numerator,denominator=sp.fraction(sp.cancel(f));poles=None
    if denominator.is_polynomial(z):poles=list(map(str,sp.solve(denominator,z)))
    residue=sp.residue(f,z,a)
    return {'residue':str(residue),'laurent_series':str(sp.series(f,z,a,order)),
            'candidate_poles_of_reduced_rational_part':poles,'branch':'principal elementary branches',
            'scope':'Local symbolic expansion; branch points are not classified as poles and global analyticity is not inferred.'}


def contour_clearance(source,contour,*,minimum_distance=1e-6):
    from ..math._structured import expression,sympy
    sp=sympy();f,(z,)=expression(source,['z'],functions=False);p,q=map(lambda v:sp.Poly(v,z,domain=sp.QQ),sp.fraction(sp.cancel(f)))
    if q.degree()>16 or minimum_distance<=0:raise ValueError('Rational-pole budget exceeded')
    roots=[complex(v) for v in sp.nroots(q,maxsteps=200)] if q.degree()>0 else []
    points=[_complex(v) for v in contour]
    if not 2<=len(points)<=1024:raise ValueError('Polygonal contour required')
    clearance=float('inf')
    for a,b in zip(points,points[1:]):
        if a==b:raise ValueError('Degenerate segment')
        for root in roots:
            t=max(0.,min(1.,((root-a)*(b-a).conjugate()).real/abs(b-a)**2));clearance=min(clearance,abs(root-(a+t*(b-a))))
    if clearance<minimum_distance:raise ValueError('Contour is too close to a computed pole')
    return {'computed_poles':[[v.real,v.imag] for v in roots],'minimum_computed_clearance':None if not roots else clearance,
            'certified_enclosure':False,'scope':'Numerical rational pole detection; use certified root isolation for proof obligations.'}
