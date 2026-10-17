"""Exact rational barycentric polynomial interpolation and the Lebesgue function (41)."""
from ._area_utils import vector,calculate as _calculate
from fractions import Fraction


def approximation_theory(nodes, values, points):
    nodes,values,points = vector(nodes,maximum=64),vector(values,maximum=64),vector(points,maximum=512)
    if len(nodes)!=len(values) or len(set(nodes))!=len(nodes):raise ValueError('Distinct paired interpolation nodes required')
    weights = []
    for i,x in enumerate(nodes):
        product = Fraction(1)
        for j,y in enumerate(nodes):
            if i!=j:product *= x-y
        weights.append(1/product)
    result,lebesgue = [],[]
    for x in points:
        if x in nodes:
            result.append(values[nodes.index(x)]);lebesgue.append(1)
        else:
            terms = [w/(x-node) for w,node in zip(weights,nodes)];denominator = sum(terms)
            basis = [v/denominator for v in terms]
            result.append(sum(a*b for a,b in zip(basis,values)));lebesgue.append(sum(abs(v) for v in basis))
    return {'values':result,'weights':weights,'lebesgue_at_queries':lebesgue,
            'scope':'Exact interpolating polynomial; finite query amplification, not a global minimax/error certificate.'}


def calculate(**arguments):return _calculate('approximation_theory',**arguments)


def spline(nodes,values,points,*,boundary='natural'):
    from scipy.interpolate import CubicSpline
    import numpy as np
    from ..math._structured import numeric_array
    x,y,q=(numeric_array(v,ndim=1,maximum=4096) for v in (nodes,values,points))
    if len(x)<2 or len(x)!=len(y) or np.any(np.diff(x)<=0) or boundary not in {'natural','clamped','not-a-knot','periodic'}:raise ValueError('Invalid cubic spline data')
    curve=CubicSpline(x,y,bc_type=boundary,extrapolate=False)
    result=curve(q)
    if not np.isfinite(result).all():raise ValueError('Query outside interpolation domain')
    return {'values':result.tolist(),'derivatives':curve(q,1).tolist(),'coefficients':curve.c.tolist(),'boundary':boundary}


def chebyshev_fit(nodes,values,degree,points):
    import numpy as np
    from ..math._structured import numeric_array
    x,y,q=(numeric_array(v,ndim=1,maximum=4096) for v in (nodes,values,points))
    if len(x)!=len(y) or type(degree) is not int or not 0<=degree<min(len(x),65) or np.min(x)==np.max(x):raise ValueError('Invalid Chebyshev approximation data')
    polynomial=np.polynomial.Chebyshev.fit(x,y,degree)
    return {'coefficients':polynomial.coef.tolist(),'domain':polynomial.domain.tolist(),'values':polynomial(q).tolist(),
            'sample_residual_inf':float(np.max(np.abs(polynomial(x)-y))),'scope':'Discrete least squares in a scaled Chebyshev basis; no uniform error guarantee.'}


def remez_grid(nodes,values,degree):
    """Discrete minimax via a linear program, valid on the supplied finite grid."""
    import numpy as np
    from scipy.optimize import linprog
    from ..math._structured import numeric_array
    x,y=(numeric_array(v,ndim=1,maximum=4096) for v in (nodes,values))
    if len(x)!=len(y) or type(degree) is not int or not 0<=degree<min(len(x),33):raise ValueError('Invalid discrete minimax data')
    v=np.polynomial.chebyshev.chebvander(x,degree);ones=-np.ones((len(x),1))
    fit=linprog([0]*(degree+1)+[1],A_ub=np.vstack((np.hstack((v,ones)),np.hstack((-v,ones)))),b_ub=np.r_[y,-y],bounds=[(None,None)]*(degree+1)+[(0,None)],method='highs')
    if not fit.success:raise ArithmeticError('Discrete minimax optimization failed: '+fit.message)
    return {'coefficients':fit.x[:-1].tolist(),'grid_max_error':float(fit.x[-1]),'scope':'Finite-grid Chebyshev minimax LP; not a continuous-interval Remez certificate.'}


def pade(coefficients,denominator_degree):
    from scipy.interpolate import pade as scipy_pade
    from ..math._structured import numeric_array
    c=numeric_array(coefficients,ndim=1,maximum=128)
    if type(denominator_degree) is not int or not 0<=denominator_degree<len(c):raise ValueError('Invalid Pade denominator degree')
    p,q=scipy_pade(c,denominator_degree)
    return {'numerator_descending':p.c.tolist(),'denominator_descending':q.c.tolist(),'scope':'Local power-series Pade approximation; poles and global error require separate analysis.'}


def remez_polynomial(coefficients,degree,lower=-1,upper=1,tolerance=1e-10,max_iterations=50):
    """Continuous polynomial Remez exchange plus exact Bernstein error enclosure."""
    import numpy as np
    from ..math.analysis.intervals import polynomial_range
    from ._area_utils import scalar
    target=vector(coefficients,maximum=17);a,b=scalar(lower),scalar(upper)
    if a>=b or type(degree) is not int or not 0<=degree<len(target) or degree>12 or not 0<tolerance<1 or type(max_iterations) is not int or not 1<=max_iterations<=200:raise ValueError('Remez polynomial budget exceeded')
    n=degree+2;nodes=np.sort((float(a)+float(b))/2+(float(b)-float(a))/2*np.cos(np.arange(n)*np.pi/(n-1)))
    target_float=np.array([float(v) for v in target]);converged=False;candidate=None
    for iteration in range(1,max_iterations+1):
        vandermonde=np.polynomial.polynomial.polyvander(nodes,degree);system=np.c_[vandermonde,(-1.)**np.arange(n)]
        solution=np.linalg.solve(system,np.polynomial.polynomial.polyval(nodes,target_float));candidate=solution[:-1]
        error=target_float.copy();error[:len(candidate)]-=candidate
        derivative=np.polynomial.polynomial.polyder(error)
        roots=np.polynomial.polynomial.polyroots(derivative) if np.any(derivative) else []
        extrema=np.array(sorted({float(a),float(b)}|{float(z.real) for z in roots if abs(z.imag)<1e-9 and float(a)<z.real<float(b)}))
        values=np.polynomial.polynomial.polyval(extrema,error);maximum=float(np.max(abs(values)))
        if maximum-abs(solution[-1])<=tolerance*(1+maximum):converged=True;break
        alternating=[]
        for x,value in zip(extrema,values):
            if alternating and np.sign(value)==np.sign(alternating[-1][1]):
                if abs(value)>abs(alternating[-1][1]):alternating[-1]=(x,value)
            else:alternating.append((x,value))
        if len(alternating)<n:break
        blocks=[alternating[i:i+n] for i in range(len(alternating)-n+1)];chosen=max(blocks,key=lambda block:min(abs(v) for _,v in block));nodes=np.array([x for x,_ in chosen])
    rational_candidate=[Fraction(str(float(v))) for v in candidate]
    exact_error=target+[Fraction(0)]*max(0,len(rational_candidate)-len(target))
    for i,v in enumerate(rational_candidate):exact_error[i]-=v
    certificate=polynomial_range(exact_error,a,b,subdivisions=32);enclosure=certificate['enclosure'];bound=max(abs(Fraction(enclosure['lower'])),abs(Fraction(enclosure['upper'])))
    return {'coefficients':list(map(str,rational_candidate)),'iterations':iteration,'exchange_converged':converged,
            'uniform_error_upper_bound':str(bound),'error_range_certificate':certificate,
            'scope':'Numerical continuous Remez exchange; exact Bernstein bound for the returned rational polynomial, not a proof of exact minimax optimality.'}
