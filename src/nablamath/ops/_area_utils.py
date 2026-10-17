"""Bounded exact arithmetic shared by the MSC computational profiles."""
from fractions import Fraction
from ..core.semantic_ir import rational


def scalar(value):
    if type(value) is bool:
        raise ValueError('Boolean is not a rational scalar')
    result = rational(value)
    if max(result.numerator.bit_length(),result.denominator.bit_length()) > 4096:
        raise ValueError('Rational exceeds the 4096-bit input budget')
    return result


def vector(values, *, maximum=1024, minimum=1):
    if not isinstance(values,(tuple,list)) or not minimum <= len(values) <= maximum:
        raise ValueError('Vector exceeds its dimension budget')
    return [scalar(v) for v in values]


def matrix(values, *, maximum=32, square=False):
    if not isinstance(values,(tuple,list)) or not 1 <= len(values) <= maximum:
        raise ValueError('Matrix exceeds its dimension budget')
    result = [vector(row,maximum=maximum) for row in values]
    if len({len(row) for row in result}) != 1 or (square and len(result)!=len(result[0])):
        raise ValueError('A rectangular/square matrix is required')
    return result


def rref(rows, columns=None):
    data = [[scalar(v) if isinstance(v,(int,float,str,Fraction)) else v for v in row] for row in rows]
    n = len(data[0]) if data else columns
    if n is None or n > 64 or len(data) > 256 or any(len(row)!=n for row in data):
        raise ValueError('Invalid elimination dimensions')
    pivots = []
    for col in range(n):
        pivot = next((i for i in range(len(pivots),len(data)) if data[i][col]),None)
        if pivot is None:
            continue
        pos = len(pivots);data[pos],data[pivot] = data[pivot],data[pos]
        scale = data[pos][col];data[pos] = [v/scale for v in data[pos]]
        for i in range(len(data)):
            if i != pos and data[i][col]:
                scale = data[i][col]
                data[i] = [a-scale*b for a,b in zip(data[i],data[pos])]
        pivots.append(col)
        if len(pivots)==len(data):
            break
    return data,pivots


def nullspace(rows, columns):
    reduced,pivots = rref(rows,columns)
    basis = []
    for free in range(columns):
        if free in pivots:
            continue
        value = [Fraction(0)]*columns;value[free] = Fraction(1)
        for row,pivot in zip(reduced,pivots):
            value[pivot] = -row[free]
        basis.append(value)
    return basis


def calculate(operation, **arguments):
    from ..calc import CalculationSession
    return CalculationSession().execute(operation,**arguments)
