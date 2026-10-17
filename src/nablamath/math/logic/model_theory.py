"""First-order satisfaction on explicit finite relational structures."""
from itertools import product


def satisfies(domain,relations,sentence,assignment=None):
    if not isinstance(domain,list) or not 1<=len(domain)<=32 or len(set(map(repr,domain)))!=len(domain) or any(type(v) not in (int,str) for v in domain):raise ValueError('Distinct finite scalar domain required')
    if not isinstance(relations,dict) or len(relations)>32:raise ValueError('Invalid finite signature')
    tables={}
    for name,record in relations.items():
        if set(record)!={'arity','tuples'} or type(record['arity']) is not int or not 0<=record['arity']<=4:raise ValueError('Closed relational signature required')
        tuples=record['tuples']
        if len(tuples)>65536 or any(len(row)!=record['arity'] or any(v not in domain for v in row) for row in tuples):raise ValueError('Relation tuples outside domain')
        tables[name]=(record['arity'],set(map(tuple,tuples)))
    assignments=dict(assignment or {});visits=0
    def term(raw,env):
        if isinstance(raw,dict) and set(raw)=={'var'} and raw['var'] in env:return env[raw['var']]
        if isinstance(raw,dict) and set(raw)=={'constant'} and raw['constant'] in domain:return raw['constant']
        raise ValueError('Invalid or unbound first-order term')
    def evaluate(node,env,depth=0):
        nonlocal visits
        visits+=1
        if visits>100000 or depth>32 or not isinstance(node,dict):raise ValueError('Finite satisfaction budget exceeded')
        op=node.get('op')
        if op=='relation':
            arity,rows=tables[node['name']]
            if len(node['args'])!=arity:raise ValueError('Relation arity mismatch')
            return tuple(term(t,env) for t in node['args']) in rows
        if op=='equal':return term(node['left'],env)==term(node['right'],env)
        if op=='not':return not evaluate(node['body'],env,depth+1)
        if op in ('and','or','imp'):
            a,b=evaluate(node['left'],env,depth+1),evaluate(node['right'],env,depth+1)
            return a and b if op=='and' else a or b if op=='or' else not a or b
        if op in ('forall','exists'):
            variable=node['variable']
            if type(variable) is not str or not variable.isidentifier():raise ValueError('Invalid quantified variable')
            results=(evaluate(node['body'],{**env,variable:v},depth+1) for v in domain)
            return all(results) if op=='forall' else any(results)
        raise ValueError('Unsupported first-order formula')
    if any(v not in domain for v in assignments.values()):raise ValueError('Assignment outside domain')
    result=evaluate(sentence,assignments)
    return {'satisfied':bool(result),'domain_size':len(domain),'evaluations':visits,
            'scope':'Truth in this finite structure, not validity in all structures.'}


def decide_linear_integers(goal,variables,assumptions=(),timeout_ms=5000):
    """Validity in quantifier-free linear integer arithmetic, via bounded Z3."""
    try:import z3
    except ImportError as error:raise ImportError('Install nablamath[formal] for integer arithmetic decisions') from error
    import ast
    from .._structured import expression,sympy,names
    sp=sympy();variables=names(variables,8)
    if type(timeout_ms) is not int or not 1<=timeout_ms<=5000 or len(assumptions)>32:raise ValueError('Integer decision budget exceeded')
    symbols=tuple(map(sp.Symbol,variables));integers={v:z3.Int(v) for v in variables}
    def linear(source):
        value,_=expression(source,variables,functions=False)
        for node in ast.walk(ast.parse(str(source),mode='eval')):
            if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):
                denominator,_=expression(ast.unparse(node.right),variables,functions=False)
                if denominator.free_symbols:raise ValueError('Variable denominators are outside linear integer arithmetic')
            if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Pow) and isinstance(node.right,ast.UnaryOp) and isinstance(node.right.op,ast.USub):
                base,_=expression(ast.unparse(node.left),variables,functions=False)
                if base.free_symbols:raise ValueError('Variable inverse powers are outside linear integer arithmetic')
        p=sp.Poly(value,*symbols,domain=sp.QQ)
        if p.total_degree()>1:raise ValueError('Nonlinear integer expression rejected')
        constant=p.coeff_monomial((0,)*len(symbols));result=z3.RealVal(str(constant))
        for i,name in enumerate(variables):
            monomial=tuple(int(j==i) for j in range(len(symbols)));coefficient=p.coeff_monomial(monomial)
            result+=z3.RealVal(str(coefficient))*integers[name]
        return result
    def predicate(record):
        if not isinstance(record,dict) or set(record)!={'left','relation','right'}:raise ValueError('Closed linear predicate required')
        a,b=linear(record['left']),linear(record['right']);op=record['relation']
        if op not in {'eq','ne','le','lt','ge','gt'}:raise ValueError('Unknown integer relation')
        return {'eq':lambda:a==b,'ne':lambda:a!=b,'le':lambda:a<=b,'lt':lambda:a<b,'ge':lambda:a>=b,'gt':lambda:a>b}[op]()
    solver=z3.Solver();solver.set(timeout=timeout_ms);solver.add(*(predicate(v) for v in assumptions));target=predicate(goal)
    import time
    started=time.monotonic();initial=solver.check()
    if initial==z3.unsat:return {'status':'rejected_inconsistent_assumptions','formal_proof':False}
    if initial==z3.unknown:return {'status':'unknown','reason':solver.reason_unknown(),'formal_proof':False}
    remaining=timeout_ms-int((time.monotonic()-started)*1000)
    if remaining<=0:return {'status':'timeout','formal_proof':False}
    solver.set(timeout=remaining);solver.add(z3.Not(target));result=solver.check()
    if result==z3.unsat:return {'status':'valid_in_fragment','formal_proof':False,'domain':'Z'}
    if result==z3.unknown:return {'status':'unknown','reason':solver.reason_unknown(),'formal_proof':False}
    model=solver.model();return {'status':'counterexample','witness':{v:model.eval(x,model_completion=True).as_long() for v,x in integers.items()},'formal_proof':False,'domain':'Z'}
