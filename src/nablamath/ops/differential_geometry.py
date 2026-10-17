"""Coordinate metric tensors, exact two-jets and optional symbolic manifolds.

The connection is Levi-Civita and the convention is R^a_bcd = d_c Gamma^a_db
- d_d Gamma^a_cb + Gamma^a_cm Gamma^m_db - Gamma^a_dm Gamma^m_cb.
Nondegenerate symmetric metrics may have Riemannian or Lorentzian signature.
"""
from dataclasses import asdict
from fractions import Fraction

from ..core.semantic_ir import rational
from ..math.geometry.riemannian import MetricJet, riemannian_tensors
from ._expressions import ScientificExpression


def _data(value):
    if isinstance(value,(tuple,list)):
        return [_data(v) for v in value]
    if isinstance(value,dict):
        return {k:_data(v) for k,v in value.items()}
    return str(value) if isinstance(value,Fraction) else value


def metric_tensors(metric, *, first=None, second=None):
    if not isinstance(metric,(list,tuple)) or not 1 <= len(metric) <= 4 or any(len(row) != len(metric) for row in metric):
        raise ValueError('A square metric of dimension 1–4 is required')
    n = len(metric)
    if (first is None) != (second is None):
        raise ValueError('Supply both first and second metric jets')
    if first is None:
        first = [[[0 for _ in range(n)] for _ in range(n)] for _ in range(n)]
        second = [[[[0 for _ in range(n)] for _ in range(n)] for _ in range(n)] for _ in range(n)]
    def exact(value):
        return tuple(exact(v) for v in value) if isinstance(value,(list,tuple)) else rational(value)
    jet = MetricJet(exact(metric),exact(first),exact(second))
    for k in range(n):
        for l in range(n):
            for i in range(n):
                if jet.first[k][i][l] != jet.first[k][l][i]:
                    raise ValueError('First metric derivatives must be symmetric in metric indices')
                for j in range(n):
                    if jet.second[k][l][i][j] != jet.second[l][k][i][j] or jet.second[k][l][i][j] != jet.second[k][l][j][i]:
                        raise ValueError('Second metric derivatives must satisfy mixed and metric symmetries')
    result = _data(asdict(riemannian_tensors(jet)))
    return {**result,'dimension':n,'metric':_data(jet.metric),'arithmetic':'exact_rational',
            'limitations':'Coordinate two-jet at one point; no global manifold or physical model validation.'}


def symbolic_metric(metric, coordinates, *, point=None):
    try:
        import sympy as sp
    except ImportError as exc:
        raise ImportError('Install nablamath[research] for symbolic differential geometry') from exc
    if not isinstance(coordinates,(list,tuple)) or not 1 <= len(coordinates) <= 4 or len(set(coordinates)) != len(coordinates):
        raise ValueError('Require 1–4 distinct coordinate names')
    n = len(coordinates)
    if not isinstance(metric,(list,tuple)) or len(metric) != n or any(len(row) != n for row in metric):
        raise ValueError('Metric and coordinate dimensions differ')
    symbols = {name:sp.Symbol(name,real=True) for name in coordinates}
    expressions = [[ScientificExpression(str(value),coordinates).symbolic(symbols) for value in row] for row in metric]
    g = sp.Matrix(expressions)
    if any(value.is_real is False for value in g):
        raise ValueError('Real metric components are required')
    if any(sp.simplify(g[i,j]-g[j,i]) != 0 for i in range(n) for j in range(n)):
        raise ValueError('Metric must be symmetric')
    determinant = sp.simplify(g.det())
    if determinant == 0:
        raise ValueError('Metric must be nondegenerate')
    inv = g.inv(); x = [symbols[name] for name in coordinates]
    gamma = [[[sp.simplify(sum(inv[a,m]*(sp.diff(g[m,j],x[i])+sp.diff(g[m,i],x[j])-sp.diff(g[i,j],x[m]))/2
                              for m in range(n))) for j in range(n)] for i in range(n)] for a in range(n)]
    curvature = [[[[sp.simplify(sp.diff(gamma[a][d][b],x[c])-sp.diff(gamma[a][c][b],x[d])
                     + sum(gamma[a][c][m]*gamma[m][d][b]-gamma[a][d][m]*gamma[m][c][b] for m in range(n)))
                     for d in range(n)] for c in range(n)] for b in range(n)] for a in range(n)]
    ricci = [[sp.simplify(sum(curvature[a][i][a][j] for a in range(n))) for j in range(n)] for i in range(n)]
    scalar = sp.simplify(sum(inv[i,j]*ricci[i][j] for i in range(n) for j in range(n)))
    substitutions = {}
    if point is not None:
        if not isinstance(point,dict) or set(point) != set(coordinates):
            raise ValueError('Point must bind every coordinate exactly once')
        substitutions = {symbols[k]:ScientificExpression(str(v),()).symbolic({}) for k,v in point.items()}
        if any(value.is_real is not True or value.is_finite is not True for value in substitutions.values()):
            raise ValueError('Point coordinates must be finite real numbers')
        if any(sp.simplify(value.subs(substitutions)).is_real is not True for value in g):
            raise ValueError('Metric components must be real at the requested point')
        det_at_point = sp.simplify(determinant.subs(substitutions))
        if det_at_point == 0 or det_at_point.is_finite is False:
            raise ValueError('Point is a metric singularity')
    def stringify(value):
        if isinstance(value,(list,tuple)):
            return [stringify(v) for v in value]
        expression = sp.simplify(value.subs(substitutions)) if substitutions else value
        if expression.has(sp.zoo,sp.oo,-sp.oo,sp.nan):
            raise ValueError('Point is outside the tensor expression domain')
        return str(expression)
    return {'dimension':n,'coordinates':list(coordinates),'metric':stringify(g.tolist()),
            'inverse_metric':stringify(inv.tolist()),'christoffel':stringify(gamma),
            'riemann':stringify(curvature),'ricci':stringify(ricci),'scalar_curvature':stringify(scalar),
            'domain':'real metric components; det(metric) != 0; all displayed expression denominators and functions must be defined',
            'arithmetic':'symbolic_exact','backend':'sympy','backend_version':sp.__version__,
            'limitations':'Local coordinate calculation, not a global manifold, completeness or physical validity proof.'}


def differential_geometry(metric, *, coordinates=None, point=None, first=None, second=None):
    if coordinates is not None:
        if first is not None or second is not None:
            raise ValueError('Choose symbolic coordinates or explicit jets')
        return symbolic_metric(metric,coordinates,point=point)
    if point is not None:
        raise ValueError('A point requires symbolic coordinates')
    return metric_tensors(metric,first=first,second=second)


def calculate(metric, **options):
    from ..calc.session import CalculationSession
    return CalculationSession().execute('differential_geometry',metric=metric,**options)
