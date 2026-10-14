"""SymPy/Z3 baselines, isolated budgets and exact independent candidate verification."""
import importlib.metadata
import math
from itertools import product
import time
from ..core.semantic_ir import fingerprint,rational
from ..expression import Number,Symbol
from ..schema.expression import from_data,to_data
from ..forge.task_spec import TaskSpec,FAMILIES
from ..forge.reverse_builder import generate_task
from ..forge.sampling import sampling_plan
from ..verify.trace import verify_candidate


def _convert(expr,number,symbol):
    if isinstance(expr,Number):return number(expr.value)
    if isinstance(expr,Symbol):return symbol(expr.name)
    a,b=_convert(expr.left,number,symbol),_convert(expr.right,number,symbol)
    if expr.op=='**':return a**int(expr.right.value)
    return {'+':lambda:a+b,'-':lambda:a-b,'*':lambda:a*b,'/':lambda:a/b}[expr.op]()


def _sympy(task):
    import sympy as sp
    p,n=task.problem,task.size
    def q(value):
        fraction=rational(value);return sp.Rational(fraction.numerator,fraction.denominator)
    def expression(data):return _convert(from_data(data),lambda v:sp.Rational(v.numerator,v.denominator),sp.Symbol)
    x=sp.Symbol('x')
    if task.family=='polynomial_integral':
        primitive=sp.Poly(sp.integrate(sum(q(v)*x**i for i,v in enumerate(p['coefficients'])),x),x)
        return {'coefficients':[str(primitive.nth(i)) for i in range(n+1)]}
    if task.family=='linear_system':
        a=sp.Matrix([[q(v) for v in row] for row in p['matrix']]);b=sp.Matrix([q(v) for v in p['rhs']])
        return {'solution':[str(v) for v in a.inv()*b]}
    if task.family=='factored_polynomial':
        polynomial=sp.Poly(sum(q(v)*x**i for i,v in enumerate(p['coefficients'])),x)
        roots=sp.polys.polytools.ground_roots(polynomial)
        values=[str(root) for root,multiplicity in sorted(roots.items(),key=lambda r:sp.default_sort_key(r[0])) for _ in range(multiplicity)]
        if len(values)!=n:raise NotImplementedError('Nonrational roots outside exact candidate profile')
        return {'roots':values}
    if task.family=='prescribed_spectrum':
        a=sp.Matrix([[q(v) for v in row] for row in p['matrix']]);vectors=[];eigenvalues=[]
        for value,multiplicity,basis in a.eigenvects():
            if len(basis)!=multiplicity:raise NotImplementedError('Incomplete rational eigenbasis')
            for vector in basis:eigenvalues.append(str(value));vectors.append(vector)
        v=sp.Matrix.hstack(*vectors)
        return {'eigenvalues':eigenvalues,'eigenvectors':[[str(v[i,j]) for j in range(n)] for i in range(n)]}
    if task.family=='convex_quadratic':
        a=sp.Matrix([[q(v) for v in row] for row in p['matrix']]);b=sp.Matrix([q(v) for v in p['linear']])
        return {'solution':[str(v) for v in -a.inv()*b]}
    if task.family=='stationary_markov':
        a=sp.Matrix([[q(v) for v in row] for row in p['transition']]).T-sp.eye(n)
        augmented=a.col_join(sp.ones(1,n));rhs=sp.zeros(n,1).col_join(sp.ones(1,1))
        vector=next(iter(sp.linsolve((augmented,rhs))))
        return {'stationary':[str(v) for v in vector]}
    if task.family=='polynomial_identity':
        from ..expression import parse_expr
        left,right=expression(p['left']),expression(p['right'])
        if sp.expand(left-right)!=0:raise ValueError('Identity refuted')
        return {'expression':to_data(parse_expr(str(sp.expand(left))))}
    if task.family=='counterexample':
        names=p['variables'];left,right=expression(p['left']),expression(p['right'])
        for index,values in enumerate(product(range(-p['radius'],p['radius']+1),repeat=len(names))):
            if index>=10000:raise TimeoutError('Enumeration budget exhausted')
            mapping={sp.Symbol(name):value for name,value in zip(names,values)}
            if left.subs(mapping)!=right.subs(mapping):return {'assignment':{name:str(v) for name,v in zip(names,values)}}
        raise ValueError('No counterexample in bounded domain')
    raise NotImplementedError(task.family)


def _z3(task):
    import z3
    p,n=task.problem,task.size;solver=z3.Solver();solver.set(timeout=5000)
    def q(value):return z3.RealVal(str(rational(value)))
    variables=[z3.Real('v'+str(i)) for i in range(n+1)]
    key=None
    if task.family=='linear_system':
        for row,b in zip(p['matrix'],p['rhs']):solver.add(sum(q(a)*variables[i] for i,a in enumerate(row))==q(b))
        key='solution';variables=variables[:n]
    elif task.family=='convex_quadratic':
        for row,b in zip(p['matrix'],p['linear']):solver.add(sum(q(a)*variables[i] for i,a in enumerate(row))+q(b)==0)
        key='solution';variables=variables[:n]
    elif task.family=='polynomial_integral':
        solver.add(variables[0]==0)
        for i,value in enumerate(p['coefficients']):solver.add((i+1)*variables[i+1]==q(value))
        key='coefficients'
    elif task.family=='stationary_markov':
        variables=variables[:n];solver.add(sum(variables)==1)
        solver.add(*(v>=0 for v in variables))
        for j in range(n):solver.add(sum(variables[i]*q(p['transition'][i][j]) for i in range(n))==variables[j])
        key='stationary'
    elif task.family in {'counterexample','polynomial_identity'}:
        names=p['variables'];symbols={name:z3.Int(name) if task.family=='counterexample' else z3.Real(name) for name in names}
        left=_convert(from_data(p['left']),q,lambda name:symbols[name]);right=_convert(from_data(p['right']),q,lambda name:symbols[name])
        solver.add(left!=right)
        if task.family=='counterexample':solver.add(*(z3.And(v>=-p['radius'],v<=p['radius']) for v in symbols.values()))
        status=solver.check()
        if status==z3.unknown:raise TimeoutError(solver.reason_unknown())
        if task.family=='polynomial_identity' and status==z3.unsat:return {'expression':p['left']}
        if task.family=='counterexample' and status==z3.sat:return {'assignment':{name:str(solver.model().eval(v,model_completion=True)) for name,v in symbols.items()}}
        raise ValueError('SMT result incompatible with task')
    else:
        raise NotImplementedError('Z3 baseline profile: linear systems, integration, convex quadratics, Markov and polynomial claims')
    status=solver.check()
    if status==z3.unknown:raise TimeoutError(solver.reason_unknown())
    if status!=z3.sat:raise ValueError('No solution')
    return {key:[str(rational(solver.model().eval(v,model_completion=True).as_fraction())) for v in variables]}


def _independent_call(task,backend):
    task=TaskSpec.from_data(task)
    # Import overhead is excluded from solver time, retained in wall time by caller.
    if backend=='sympy':__import__('sympy');operation=_sympy;version=importlib.metadata.version('sympy')
    elif backend=='z3':__import__('z3');operation=_z3;version=importlib.metadata.version('z3-solver')
    elif backend=='nabla':
        from ..forge.solvers import solve_task
        operation=solve_task;version='forge-v2'
    else:raise ValueError('Unknown baseline')
    start=time.perf_counter()
    try:
        candidate=operation(task);status='solved' if verify_candidate(task,candidate).valid else 'incorrect'
        return {'status':status,'candidate':candidate,'solver_seconds':time.perf_counter()-start,'version':version}
    except NotImplementedError as exc:
        return {'status':'unsupported','reason':str(exc),'solver_seconds':time.perf_counter()-start,'version':version}
    except TimeoutError as exc:
        return {'status':'timeout','reason':str(exc),'solver_seconds':time.perf_counter()-start,'version':version}


def run_benchmark(*,count=24,seed=103,sizes=(2,4,8),timeout=15):
    from ..agents.tool_registry import ToolRegistry,Tool
    from ..agents.permissions import Permissions
    if not 1<=count<=96:raise ValueError('Benchmark limited to 1–96 tasks')
    registry=ToolRegistry((Tool('independent',_independent_call,frozenset({'task','backend'})),))
    permissions=Permissions(frozenset({'independent'}),timeout_seconds=timeout)
    rows=[];seen=set()
    for family,derived,size in sampling_plan(count,seed,FAMILIES,sizes):
        task=generate_task(family,derived,size).task
        from ..forge.deduplicate import semantic_fingerprint
        key=semantic_fingerprint(task)
        if key in seen:continue
        seen.add(key);results={}
        for backend in ('nabla','sympy','z3'):
            start=time.perf_counter()
            try:result=registry.execute('independent',{'task':task.to_data(),'backend':backend},permissions)
            except TimeoutError as exc:result={'status':'timeout','reason':str(exc)}
            except (ValueError,ImportError) as exc:result={'status':'error','reason':str(exc)}
            result['wall_seconds']=time.perf_counter()-start
            if result['status']=='solved' and not verify_candidate(task,result['candidate']).valid:result['status']='incorrect'
            results[backend]=result
        external=[results[name] for name in ('sympy','z3') if results[name]['status']!='unsupported']
        challenging=results['nabla']['status']=='solved' and any(r['status'] in {'timeout','incorrect'} for r in external)
        rows.append({'task':task.to_data(),'task_id':task.content_id,'semantic_id':key,'seed':derived,'results':results,
                     'difficulty':'backend_challenge_observed' if challenging else 'advanced_difficulty_not_demonstrated'})
    payload={'schema_version':1,'seed':seed,'sizes':list(sizes),'timeout_seconds':timeout,'tasks':rows,
             'summary':{name:{status:sum(r['results'][name]['status']==status for r in rows) for status in ('solved','incorrect','timeout','unsupported','error')} for name in ('nabla','sympy','z3')},
             'advanced_tasks_observed':sum(r['difficulty']=='backend_challenge_observed' for r in rows),
             'scope':'synthetic constructor tasks; measured backend difficulty, not expert reasoning or training utility'}
    return {**payload,'benchmark_id':fingerprint(payload)}
