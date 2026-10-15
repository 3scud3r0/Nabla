"""Inverse rational integration: construct primitive then exact quotient derivative."""
from random import Random
from ...math.calculus.rational_functions import RationalFunction,rational_form
from ...math.polynomials.univariate import Polynomial
from ...expression import render
from ...core.semantic_ir import fingerprint


def construct(seed,*,degree=3):
    if type(seed) is not int or type(degree) is not int or not 1<=degree<=4:raise ValueError('Semente e grau inválidos')
    rng=Random(seed)
    numerator=Polynomial(tuple(rng.randint(-9,9) for _ in range(degree))+(rng.choice((-3,-1,1,3)),))
    denominator=Polynomial((1,))
    for _ in range(degree):denominator=denominator*Polynomial((rng.choice((-5,-3,-1,1,3,5)),1))
    primitive=RationalFunction(numerator,denominator);derivative=primitive.derivative()
    problem={'schema_version':1,'family':'constructed_rational_integral','seed':seed,'degree':degree,
             'integrand':render(derivative.expression()),'domain':'Exclude all denominator zeroes; no extension across poles',
             'scope':'exact univariate rational primitive construction, no advanced difficulty claim'}
    return {**problem,'task_id':fingerprint(problem)},render(primitive.expression())


def verify_primitive(task,candidate):
    try:
        payload={k:v for k,v in task.items() if k!='task_id'}
        if fingerprint(payload)!=task['task_id']:return False
        expected,_=construct(task['seed'],degree=task['degree'])
        if expected!=task:return False
        # Independent polynomial quotient derivative rather than sample equality.
        integrand=rational_form(task['integrand'])
        from ...core.obligations import domain_obligations
        from ...expression import parse_expr
        from ...math.polynomials.univariate import polynomial_gcd
        for obligation in domain_obligations(parse_expr(candidate)):
            polynomial=rational_form(render(obligation.expression)).numerator
            if polynomial.is_zero:return False
            if polynomial.degree>0:
                squarefree=polynomial.divmod(polynomial_gcd(polynomial,polynomial.derivative()))[0].monic()
                if not integrand.denominator.divmod(squarefree)[1].is_zero:return False
        return rational_form(candidate).derivative().to_data()==integrand.to_data()
    except (ValueError,KeyError,TypeError,ArithmeticError):return False
