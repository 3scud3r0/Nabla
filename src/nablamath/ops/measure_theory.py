"""Finite measures and exact conditional expectations on atomic sigma-algebras (28)."""
from fractions import Fraction
from ._area_utils import vector,calculate as _calculate


def measure_theory(weights, values, *, partition=None):
    weights,values = vector(weights),vector(values)
    if len(weights)!=len(values) or any(w<0 for w in weights) or not sum(weights):
        raise ValueError('Require equal dimensions and a nonzero nonnegative measure')
    n = len(weights);partition = list(range(n)) if partition is None else partition
    if not isinstance(partition,list) or len(partition)!=n or any(type(v) is not int or not 0<=v<n for v in partition):
        raise ValueError('Invalid sigma-algebra atom labels')
    atoms = []
    expected = [Fraction(0)]*n
    for label in sorted(set(partition)):
        members = [i for i in range(n) if partition[i]==label]
        mass = sum(weights[i] for i in members)
        average = sum(weights[i]*values[i] for i in members)/mass if mass else Fraction(0)
        for i in members:expected[i] = average
        atoms.append({'members':members,'measure':mass,'conditional_value':average})
    integral = sum(w*v for w,v in zip(weights,values))
    return {'total_measure':sum(weights),'integral':integral,'normalized_mean':integral/sum(weights),
            'conditional_expectation':expected,'atoms':atoms,'sigma_algebra_size':2**len(atoms),
            'tower_integral_verified':sum(w*v for w,v in zip(weights,expected))==integral,
            'scope':'Finite atomic measure; conditional value chosen as zero on null atoms.'}


def calculate(**arguments):return _calculate('measure_theory',**arguments)


def radon_nikodym(reference,target):
    reference,target=vector(reference),vector(target)
    if len(reference)!=len(target) or any(v<0 for v in reference+target):raise ValueError('Paired nonnegative atomic measures required')
    if any(a==0 and b!=0 for a,b in zip(reference,target)):raise ValueError('Target measure is not absolutely continuous')
    derivative=[b/a if a else Fraction(0) for a,b in zip(reference,target)]
    return {'density':derivative,'null_atom_convention':0,'reconstruction_verified':all(a*d==b for a,b,d in zip(reference,target,derivative))}


def product_measure(left,right):
    a,b=vector(left,maximum=256),vector(right,maximum=256)
    if any(v<0 for v in a+b):raise ValueError('Nonnegative measures required')
    return {'weights':[[x*y for y in b] for x in a],'total_measure':sum(a)*sum(b)}


def continuous_integral(density,integrand,lower,upper,variable='x'):
    from ..math._structured import expression,sympy
    from ._area_utils import scalar
    sp=sympy();p,(x,)=expression(density,[variable],functions=False);f,_=expression(integrand,[variable])
    poly=sp.Poly(p,x,domain=sp.QQ);a,b=(sp.Rational(str(scalar(v))) for v in (lower,upper))
    if a>=b or poly.degree()>16:raise ValueError('Invalid interval or density degree')
    # Exact polynomial critical points and endpoints determine the minimum.
    minimum=sp.calculus.util.minimum(p,x,sp.Interval(a,b))
    if minimum.is_nonnegative is not True:raise ValueError('Density nonnegativity could not be established')
    mass=sp.integrate(p,(x,a,b));value=sp.integrate(p*f,(x,a,b))
    return {'mass':str(mass),'integral':str(value),'evaluated':not value.has(sp.Integral),
            'density_nonnegative':True,'scope':'Continuous polynomial density on the declared bounded interval.'}
