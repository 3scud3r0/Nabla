"""Scalar first-order polynomial Euler–Lagrange equations and energy (49)."""
from ._polynomial import parse_polynomial,Polynomial
from ._area_utils import calculate as _calculate


def variational_calculus(lagrangian):
    names = ['t','q','v','a'];lagrange = parse_polynomial(lagrangian,names)
    if any(powers[3] for powers in lagrange.terms):raise ValueError('Lagrangian may depend on t,q,v, not acceleration a')
    momentum = lagrange.derivative(2)
    velocity,acceleration = Polynomial.variable(2,4),Polynomial.variable(3,4)
    mass = momentum.derivative(2)
    force = lagrange.derivative(1)-momentum.derivative(0)-velocity*momentum.derivative(1)
    equation = acceleration*mass-force
    energy = velocity*momentum-lagrange
    return {'euler_lagrange':equation.text(names),'momentum':momentum.text(names),
            'energy':energy.text(names),'acceleration_numerator':force.text(names),
            'acceleration_denominator':mass.text(names),'regular_where':'('+mass.text(names)+') != 0' if mass.terms else None,
            'convention':'t=time, q=coordinate, v=dq/dt, a=dv/dt; Euler–Lagrange expression equals zero',
            'scope':'Polynomial scalar first-order Lagrangians; no general variational minimizer or boundary-value existence proof.'}


def calculate(**arguments):return _calculate('variational_calculus',**arguments)


def euler_lagrange_fields(lagrangian,coordinates,fields,order=1):
    """Several dependent fields in one independent variable, jet order <=3."""
    from ..math._structured import expression,sympy
    sp=sympy()
    if len(coordinates)!=1 or not 1<=len(fields)<=4 or type(order) is not int or not 1<=order<=3:raise ValueError('One time variable, 1–4 fields and order 1–3 required')
    t=coordinates[0];jet_names=[f'{field}_{j}' for field in fields for j in range(2*order+1)]
    value,symbols=expression(lagrangian,[t]+jet_names);time=symbols[0];jets={name:sp.Symbol(name) for name in jet_names}
    if any(value.has(jets[f'{field}_{j}']) for field in fields for j in range(order+1,2*order+1)):raise ValueError('Lagrangian contains derivatives beyond its declared order')
    def total(f):
        return sp.diff(f,time)+sum(jets[f'{field}_{j+1}']*sp.diff(f,jets[f'{field}_{j}']) for field in fields for j in range(2*order))
    equations=[];boundary=[]
    for field in fields:
        result=sp.diff(value,jets[f'{field}_0'])
        for j in range(1,order+1):
            term=sp.diff(value,jets[f'{field}_{j}'])
            for _ in range(j):term=total(term)
            result+=(-1)**j*term
        equations.append(str(sp.expand(result)))
        momenta=[]
        for r in range(order):
            momentum=0
            for j in range(r+1,order+1):
                term=sp.diff(value,jets[f'{field}_{j}'])
                for _ in range(j-r-1):term=-total(term)
                momentum+=term
            momenta.append(str(sp.expand(momentum)))
        boundary.append(momenta)
    hessian=sp.hessian(value,[jets[f'{field}_{order}'] for field in fields])
    return {'equations':equations,'boundary_momenta':boundary,'highest_derivative_hessian':list(map(lambda row:list(map(str,row)),hessian.tolist())),
            'scope':'Local Euler–Lagrange equations and free-endpoint momenta; Hessian alone does not prove a global minimum.'}


def euler_lagrange_density(lagrangian,coordinates,fields):
    """First-order several-field Lagrangian density in up to three coordinates."""
    from ..math._structured import expression,sympy,data
    sp=sympy();n=len(coordinates)
    if not 1<=n<=3 or not 1<=len(fields)<=2:raise ValueError('Field density dimension budget exceeded')
    first=[f'{f}_d{i}' for f in fields for i in range(n)];second=[f'{f}_d{i}d{j}' for f in fields for i in range(n) for j in range(i,n)]
    names=list(coordinates)+list(fields)+first+second;value,symbols=expression(lagrangian,names);s={str(v):v for v in symbols}
    if any(value.has(s[name]) for name in second):raise ValueError('Density must depend on first jets only')
    def total(f,i):
        result=sp.diff(f,s[coordinates[i]])
        for field in fields:
            result+=s[f'{field}_d{i}']*sp.diff(f,s[field])
            for j in range(n):a,b=sorted((i,j));result+=s[f'{field}_d{a}d{b}']*sp.diff(f,s[f'{field}_d{j}'])
        return sp.expand(result)
    equations=[sp.expand(sp.diff(value,s[f])-sum(total(sp.diff(value,s[f'{f}_d{i}']),i) for i in range(n))) for f in fields]
    return {'equations':list(map(str,equations)),'boundary_fluxes':[[str(sp.diff(value,s[f'{f}_d{i}'])) for i in range(n)] for f in fields],
            'legendre_hessian':data(sp.hessian(value,[s[name] for name in first])),
            'scope':'Local field equations; natural boundary condition is normal contraction of the returned flux, subject to allowed variations.'}
