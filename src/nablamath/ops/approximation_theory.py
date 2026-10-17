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
