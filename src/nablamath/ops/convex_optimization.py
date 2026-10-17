"""Optional SciPy LP/MILP and bounded nonlinear optimization adapters.

Nonlinear optimization returns local solver evidence, never a global certificate.
"""
import math


def conic_program(objective,*,inequalities=(),second_order=(),semidefinite=None,solver=None):
    """Conic/SDP adapter with numerical primal/dual results, never exact proof."""
    try:import cvxpy as cp
    except ImportError as error:raise ImportError('Install nablamath[advanced] for conic optimization') from error
    from ..math._structured import numeric_array
    np,_=_modules();c=numeric_array(objective,ndim=1,maximum=256);x=cp.Variable(len(c));constraints=[]
    for record in inequalities:
        if set(record)!={'matrix','upper'}:raise ValueError('Closed linear inequality required')
        a,b=numeric_array(record['matrix'],ndim=2,maximum=65536),numeric_array(record['upper'],ndim=1)
        if a.shape!=(len(b),len(c)):raise ValueError('Linear constraint shape mismatch')
        constraints.append(a@x<=b)
    for record in second_order:
        if set(record)!={'matrix','offset','linear','constant'}:raise ValueError('Closed SOC constraint required')
        a,b,h=(numeric_array(record[k],ndim=n,maximum=65536) for k,n in (('matrix',2),('offset',1),('linear',1)))
        if a.shape!=(len(b),len(c)) or len(h)!=len(c) or not np.isfinite(record['constant']):raise ValueError('SOC shape mismatch')
        constraints.append(cp.norm(a@x+b,2)<=h@x+record['constant'])
    if semidefinite is not None:
        if len(semidefinite)!=len(c)+1:raise ValueError('SDP requires F0 and one coefficient matrix per variable')
        fs=[numeric_array(v,ndim=2,maximum=4096) for v in semidefinite];n=fs[0].shape[0]
        if any(f.shape!=(n,n) or not np.allclose(f,f.T) for f in fs):raise ValueError('Symmetric equal-shape SDP matrices required')
        constraints.append(fs[0]+sum(x[i]*fs[i+1] for i in range(len(c))) >> 0)
    allowed=set(cp.installed_solvers())&{'CLARABEL','SCS','CVXOPT'}
    if solver is None:solver='CLARABEL' if 'CLARABEL' in allowed else 'SCS' if 'SCS' in allowed else None
    if solver not in allowed:raise ValueError('Supported conic solver unavailable')
    problem=cp.Problem(cp.Minimize(c@x),constraints);value=problem.solve(solver=solver)
    point=None if x.value is None else np.asarray(x.value).tolist()
    return {'status':problem.status,'point':point,'value':float(value) if value is not None and np.isfinite(value) else None,
            'dual_values':[None if con.dual_value is None else np.asarray(con.dual_value).tolist() for con in constraints],
            'max_constraint_violation':max((float(np.max(con.violation())) for con in constraints),default=0.) if point is not None else None,
            'solver':solver,'formal_proof':False,'scope':'Numerical conic evidence; solver status is not an exact optimality certificate.'}


def verify_linear_certificate(objective,matrix,lower,point,dual):
    from ..math._structured import rational_matrix,sympy
    sp=sympy();a=rational_matrix(matrix);c=rational_matrix([[v] for v in objective]);b=rational_matrix([[v] for v in lower]);x=rational_matrix([[v] for v in point]);y=rational_matrix([[v] for v in dual])
    if a.shape!=(len(lower),len(objective)) or x.rows!=c.rows or y.rows!=b.rows:raise ValueError('Certificate dimensions differ')
    primal=all(v>=0 for v in x) and all(v>=0 for v in a*x-b);dual_feasible=all(v>=0 for v in y) and all(v>=0 for v in c-a.T*y)
    gap=(c.T*x-b.T*y)[0]
    return {'primal_feasible':bool(primal),'dual_feasible':bool(dual_feasible),'duality_gap':str(gap),
            'optimal':bool(primal and dual_feasible and gap==0),'arithmetic':'exact_rational',
            'convention':'min c*x subject A*x>=lower and x>=0; dual max lower*y with A.T*y<=c,y>=0'}


def _modules():
    try:
        import numpy as np
        from scipy import optimize
    except ImportError as exc:
        raise ImportError('Install nablamath[scipy] for optimization') from exc
    return np, optimize


def minimize_linear(objective, *, constraints=None, upper=None, lower=None,
                    bounds=None, integrality=None, time_limit=30):
    np, optimize = _modules()
    c = np.asarray(objective, dtype=float)
    if c.ndim != 1 or not 1 <= c.size <= 1000 or not np.isfinite(c).all():
        raise ValueError('Objective requires 1–1000 finite coefficients')
    if not math.isfinite(time_limit) or not 0 < time_limit <= 60:
        raise ValueError('time_limit must be in (0,60] seconds')
    n = len(c)
    if bounds is None:
        bounds = [(0, None)]*n
    if len(bounds) != n or any(len(pair) != 2 for pair in bounds):
        raise ValueError('One lower/upper bound pair is required per variable')
    lb = np.array([-np.inf if p[0] is None else p[0] for p in bounds], dtype=float)
    ub = np.array([np.inf if p[1] is None else p[1] for p in bounds], dtype=float)
    if np.isnan(lb).any() or np.isnan(ub).any() or (lb > ub).any() or np.isposinf(lb).any() or np.isneginf(ub).any():
        raise ValueError('Invalid bounds')
    constraint = None
    matrix = None
    if constraints is not None:
        matrix = np.asarray(constraints, dtype=float)
        if matrix.ndim != 2 or matrix.shape[1] != n or not 1 <= matrix.shape[0] <= 1000 or not np.isfinite(matrix).all():
            raise ValueError('Invalid constraint matrix')
        if upper is None or len(upper) != len(matrix) or (lower is not None and len(lower) != len(matrix)):
            raise ValueError('Constraint bounds must match rows')
        hi = np.asarray(upper, dtype=float)
        lo = np.full(len(matrix), -np.inf) if lower is None else np.asarray(lower, dtype=float)
        if np.isnan(hi).any() or np.isnan(lo).any() or (lo > hi).any() or np.isposinf(lo).any() or np.isneginf(hi).any():
            raise ValueError('Invalid constraint bounds')
        constraint = optimize.LinearConstraint(matrix, lo, hi)
    elif upper is not None or lower is not None:
        raise ValueError('Bounds require constraints')
    integers = [0]*n if integrality is None else list(integrality)
    if len(integers) != n or any(type(i) is not int or i not in (0,1) for i in integers):
        raise ValueError('integrality requires one 0/1 entry per variable')
    result = optimize.milp(c, integrality=integers, bounds=optimize.Bounds(lb, ub),
                           constraints=constraint, options={'time_limit': float(time_limit)})
    point = None if result.x is None else result.x.tolist()
    residual = None
    if point is not None:
        if not np.isfinite(result.x).all() or not math.isfinite(float(result.fun)):
            raise ArithmeticError('Nonfinite solver result')
        violations = [0.0, float(np.max(lb-result.x)), float(np.max(result.x-ub)),
                      max((abs(x-round(x)) for x,i in zip(point, integers) if i), default=0)]
        if matrix is not None:
            ax = matrix @ result.x
            violations += [float(np.max(lo-ax)), float(np.max(ax-hi))]
        residual = max(violations)
    return {'success': bool(result.success), 'status': int(result.status), 'message': str(result.message),
            'point': point, 'value': None if result.fun is None else float(result.fun),
            'max_constraint_violation': residual, 'backend': 'scipy_highs',
            'limitations': 'Floating point LP/MILP solver result; no exact optimality certificate.'}


def minimize_nonlinear(function, initial, *, jac=None, bounds=None, max_iterations=1000):
    np, optimize = _modules()
    x = np.asarray(initial, dtype=float)
    if x.ndim != 1 or not 1 <= len(x) <= 1000 or not np.isfinite(x).all():
        raise ValueError('Invalid initial point')
    if type(max_iterations) is not int or not 1 <= max_iterations <= 10000:
        raise ValueError('Invalid iteration budget')
    result = optimize.minimize(function, x, jac=jac, bounds=bounds, method='L-BFGS-B',
                               options={'maxiter': max_iterations})
    if not np.isfinite(result.x).all() or not math.isfinite(float(result.fun)):
        raise ArithmeticError('Nonfinite nonlinear solver result')
    return {'point': result.x.tolist(), 'value': float(result.fun), 'success': bool(result.success),
            'message': str(result.message), 'iterations': int(result.nit),
            'limitations': 'Local nonlinear optimum candidate; convexity and global optimality not established.'}
