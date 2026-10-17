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
