"""Rational points and Zariski tangent spaces of affine schemes (MSC 14).

The listed generators define the scheme: no radical ideal or smoothness claim.
"""
from ._polynomial import parse_polynomial
from ._area_utils import vector,rref,nullspace,calculate as _calculate


def algebraic_geometry(equations, variables, point):
    if not isinstance(equations,list) or not 1<=len(equations)<=32:
        raise ValueError('Require 1–32 polynomial equations')
    polynomials = [parse_polynomial(source,variables) for source in equations]
    point = vector(point,maximum=4)
    if len(point)!=len(variables):raise ValueError('Point and coordinate dimensions differ')
    residuals = [p.evaluate(point) for p in polynomials]
    jacobian = [[p.derivative(i).evaluate(point) for i in range(len(variables))] for p in polynomials]
    rank = len(rref(jacobian)[1]);member = not any(residuals)
    return {'point_on_scheme':member,'residuals':residuals,'jacobian':jacobian,'jacobian_rank':rank,
            'tangent_dimension':len(variables)-rank if member else None,
            'tangent_basis':nullspace(jacobian,len(variables)) if member else None,
            'scope':'Affine scheme at a rational point; no radicalization, global dimension or smoothness certification.'}


def calculate(**arguments):return _calculate('algebraic_geometry',**arguments)


def ideal_analysis(equations,variables,*,remove=(),denominator=None):
    from ..math.geometry.schemes import affine_scheme,eliminate,saturate
    result=affine_scheme(equations,variables)
    if remove:result['elimination']=eliminate(equations,variables,remove)
    if denominator is not None:result['localization']=saturate(equations,variables,denominator)
    return result
