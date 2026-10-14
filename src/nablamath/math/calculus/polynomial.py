"""Unified exact calculus API backed by canonical symbolic implementations."""
from fractions import Fraction
from ...expression import evaluate,parse_expr
from ...symbolic import differentiate,integrate_polynomial,rational_limit,taylor_series
from ...math.equations.ode import integrate as integrate_ode


def derivative(source,variable='x'):
    return differentiate(parse_expr(source),variable)


def primitive(source,variable='x'):
    return integrate_polynomial(parse_expr(source),variable)


def definite_integral(source,start,end,variable='x'):
    certificate=primitive(source,variable)
    return evaluate(certificate.antiderivative,{variable:Fraction(end)})-evaluate(certificate.antiderivative,{variable:Fraction(start)})


def limit(numerator,denominator,point,variable='x'):
    return rational_limit(parse_expr(numerator),parse_expr(denominator),variable,Fraction(point))


def series(source,center=0,order=4,variable='x'):
    if type(order) is not int or not 0<=order<=8:
        raise ValueError('Serie publica limitada a ordem 8')
    return taylor_series(parse_expr(source),variable,Fraction(center),order)
