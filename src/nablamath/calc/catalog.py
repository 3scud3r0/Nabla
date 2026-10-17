"""Bounded public adapters for existing scientific libraries; no parallel math engine."""
import math
from ..core.semantic_ir import rational

# area, mandatory keys, optional keys, exact/approximate contract
OPERATIONS = {
 'polynomial_range': ('calculus', {'coefficients','lower','upper'}, {'subdivisions'}, 'exact rational Bernstein range enclosure, not necessarily sharp extrema'),
 'certified_integral': ('calculus', {'coefficients','lower','upper'}, {'method','tolerance','max_pieces'}, 'exact polynomial quadrature with rigorous derivative remainder and explicit budget'),
 'certified_function': ('numerical', {'kind','value'}, {'tolerance','max_terms'}, 'rational Taylor enclosures of exp/log/sin/cos on bounded arguments'),
 'markov_hitting': ('probability', {'transition','targets'}, set(), 'exact first-hit probability and conditional moments; defective hitting is explicit'),
 'markov_stationary': ('probability', {'transition'}, set(), 'exact stationary extremes of closed communicating classes with period'),
 'markov_rewards': ('probability', {'transition','rewards','discount'}, set(), 'exact discounted rewards for 0<=discount<1 with zero residual'),
 'rational_limit': ('calculus', {'source','point'}, {'direction'}, 'exact sided rational limits, original domain guards and replayable algebraic witness; finite rational points or signed infinity'),
 'least_squares': ('statistics', {'predictors','response'}, {'intercept','weights'}, 'exact multivariate weighted least squares; full-rank design, positive residual degrees of freedom'),
 'rational_compare': ('algebra', {'left','right'}, set(), 'exact univariate rational identity with separate partial domains'),
 'matrix_properties': ('linear_algebra', {'matrix'}, set(), 'exact rational determinant/rank/characteristic polynomial'),
 'matrix_inverse': ('linear_algebra', {'matrix'}, set(), 'exact rational inverse; nonsingular square matrices'),
 'linear_regression': ('statistics', {'x','y'}, set(), 'exact least squares; nonconstant predictor, paired observations'),
 'bayes': ('probability', {'prior','likelihood'}, set(), 'exact finite Bayes; positive evidence'),
 'distribution': ('probability', {'kind','parameters','value'}, set(), 'approximate normal/exponential/Poisson CDF and moments'),
 'time_series': ('statistics', {'values','method'}, {'window','alpha','lag'}, 'approximate differences/moving average/smoothing/autocorrelation/trend'),
 'shortest_paths': ('discrete', {'vertices','edges','source'}, set(), 'exact Dijkstra for nonnegative rational weights'),
 'maximum_flow': ('discrete', {'vertices','edges','source','sink'}, set(), 'exact rational capacity max flow'),
 'sat': ('discrete', {'clauses'}, {'decision_limit'}, 'bounded DPLL; assignment verification; unsat not a Lean theorem'),
}


# Additive experimental operations: same session/CLI/notebook receipt path.
from ..math.exact.adapters import OPERATIONS as ADVANCED_OPERATIONS, execute as execute_advanced
OPERATIONS.update(ADVANCED_OPERATIONS)

from ..ops.catalog import OPERATIONS as ECOSYSTEM_OPERATIONS, execute as execute_ecosystem
OPERATIONS.update(ECOSYSTEM_OPERATIONS)


def _values(values, minimum=1):
    if not isinstance(values,(list,tuple)) or not minimum <= len(values) <= 10000:
        raise ValueError('Amostra fora dos limites')
    return tuple(rational(v) for v in values)


def execute(operation, a):
    if operation in ECOSYSTEM_OPERATIONS:
        return execute_ecosystem(operation, a)
    if operation in ADVANCED_OPERATIONS:
        return execute_advanced(operation, a)
    if operation=='polynomial_range':
        from ..math.analysis.intervals import polynomial_range
        return polynomial_range(**a)
    if operation=='certified_integral':
        from ..math.analysis.quadrature import certified_polynomial_integral
        return certified_polynomial_integral(**a)
    if operation=='certified_function':
        from ..math.analysis.certified_functions import certified_function
        return certified_function(**a)
    if operation.startswith('markov_'):
        from ..math.probability.absorption import hitting_statistics,stationary_classes,discounted_rewards
        functions={'markov_hitting':hitting_statistics,'markov_stationary':stationary_classes,'markov_rewards':discounted_rewards}
        return functions[operation](**a)
    if operation=='rational_limit':
        from ..math.calculus.limits import rational_sided_limit
        return rational_sided_limit(a['source'],a['point'],direction=a.get('direction','both'))
    if operation=='least_squares':
        from ..math.statistics.multivariate import exact_least_squares
        return exact_least_squares(a['predictors'],a['response'],intercept=a.get('intercept',True),weights=a.get('weights'))
    if operation=='rational_compare':
        from ..math.calculus.rational_functions import compare_rational
        return compare_rational(a['left'],a['right'])
    if operation.startswith('matrix_'):
        from ..math.linear_algebra import Matrix
        from ..math.linear_algebra.solvers import bounded, characteristic_polynomial
        matrix = Matrix(tuple(_values(row) for row in a['matrix']))
        bounded(matrix)
        if operation == 'matrix_inverse':
            return {'inverse':matrix.inverse().rows}
        return {'rank':matrix.echelon()[1], 'shape':matrix.shape,
                'determinant':matrix.determinant() if matrix.shape[0]==matrix.shape[1] else None,
                'characteristic_polynomial':characteristic_polynomial(matrix) if matrix.shape[0]==matrix.shape[1] else None}
    if operation == 'linear_regression':
        from ..math.statistics.regression import linear_regression
        return linear_regression(_values(a['x'],2),_values(a['y'],2))
    if operation == 'bayes':
        from ..math.statistics.bayesian import posterior, predictive
        p,l = a['prior'],a['likelihood']
        if not isinstance(p,dict) or not isinstance(l,dict) or not 1<=len(p)<=128 or p.keys()!=l.keys():
            raise ValueError('Prior e verossimilhança devem compartilhar 1–128 hipóteses')
        p,l = ({k:rational(v) for k,v in d.items()} for d in (p,l))
        if sum(p.values())!=1 or any(v<0 or v>1 for v in (*p.values(),*l.values())):
            raise ValueError('Probabilidades inválidas')
        return {'posterior':posterior(p,l),'evidence':predictive(p,l)}
    if operation == 'distribution':
        from ..math.probability.continuous import NormalDistribution, ExponentialDistribution, PoissonDistribution
        constructors={'normal':NormalDistribution,'exponential':ExponentialDistribution,'poisson':PoissonDistribution}
        if a['kind'] not in constructors or not isinstance(a['parameters'],dict):
            raise ValueError('Distribuição desconhecida')
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1e6 for v in a['parameters'].values()):
            raise ValueError('Parâmetros de distribuição fora do domínio')
        value=a['value']
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or abs(value)>10000:
            raise ValueError('Ponto de distribuição fora do domínio')
        distribution=constructors[a['kind']](**a['parameters'])
        return {'cdf':distribution.cdf(value), 'density_or_mass':getattr(distribution,'pdf',getattr(distribution,'pmf',None))(value),
                'arithmetic':'float approximation, not certified interval'}
    if operation == 'time_series':
        from ..math.statistics import time_series as ts
        values=tuple(float(v) for v in _values(a['values'],2))
        method=a['method']
        if method=='differences': return {'values':ts.differences(values)}
        if method=='moving_average': return {'values':ts.moving_average(values,a.get('window',2))}
        if method=='smoothing': return {'values':ts.exponential_smoothing(values,a.get('alpha',.5))}
        if method=='autocorrelation': return {'value':ts.autocorrelation(values,a.get('lag',1))}
        if method=='trend': return {'intercept_slope':ts.linear_trend(values)}
        raise ValueError('Método temporal desconhecido')
    if operation in {'shortest_paths','maximum_flow'}:
        from ..math.graph_theory.weighted import WeightedDigraph
        from ..math.graph_theory.flows import maximum_flow
        vertices=a['vertices'];edges=a['edges']
        if not isinstance(vertices,list) or not 1<=len(vertices)<=128 or len(set(vertices))!=len(vertices) or len(edges)>4096:
            raise ValueError('Grafo fora dos limites')
        weights={}
        for row in edges:
            if len(row)!=3 or tuple(row[:2]) in weights: raise ValueError('Aresta inválida ou duplicada')
            weights[tuple(row[:2])]=rational(row[2])
        graph=WeightedDigraph(frozenset(vertices),weights)
        if operation=='shortest_paths': return {'distances':graph.shortest_distances(a['source'])}
        value,flows=maximum_flow(frozenset(vertices),weights,a['source'],a['sink'])
        return {'value':value,'flows':[[u,v,f] for (u,v),f in sorted(flows.items())]}
    if operation=='sat':
        from ..math.logic.sat import solve_sat,normalize_cnf,verify_assignment
        clauses=a['clauses'];limit=a.get('decision_limit',10000)
        if (not isinstance(clauses,list) or len(clauses)>512 or any(len(row)>32 for row in clauses)
                or any(type(v) is not int or not 1<=abs(v)<=128 for row in clauses for v in row)
                or type(limit) is not int or not 1<=limit<=100000):
            raise ValueError('SAT fora do orçamento')
        result=solve_sat(clauses,decision_limit=limit)
        return {'satisfiable':result.satisfiable,'assignment':result.assignment,
                'assignment_verified':verify_assignment(normalize_cnf(clauses),dict(result.assignment)) if result.satisfiable else None,
                'decisions':result.decisions,'formal_proof':False}
    raise ValueError('Operação desconhecida')


def catalog():
    from .session import AREAS,REQUIRED,OPTIONAL
    return {'schema_version':1,'operations':[{'name':name,'area':area,'required':sorted(REQUIRED[name]),
            'optional':sorted(OPTIONAL.get(name,set())),
            'contract':OPERATIONS[name][3] if name in OPERATIONS else 'bounded legacy scientific operation; explicit receipt and domain checks'}
            for name,area in sorted(AREAS.items())], 'scope':'declared bounded operations, not complete mathematical coverage'}
