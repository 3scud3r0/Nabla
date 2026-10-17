"""Finite binary algebras: generated subalgebras and congruence quotients (08)."""
from ._area_utils import calculate as _calculate


def universal_algebra(tables, *, generators=None, partition=None):
    if not isinstance(tables,list) or not 1<=len(tables)<=4 or not isinstance(tables[0],list):
        raise ValueError('Require 1–4 finite binary operation tables')
    n = len(tables[0])
    if not 1<=n<=16 or any(len(table)!=n or any(not isinstance(row,list) or len(row)!=n or any(type(v) is not int or not 0<=v<n for v in row) for row in table) for table in tables):
        raise ValueError('Operation tables must be closed on 1–16 elements')
    generators = list(range(n)) if generators is None else generators
    if not isinstance(generators,list) or not generators or any(type(v) is not int or not 0<=v<n for v in generators):
        raise ValueError('Invalid algebra generators')
    closure = set(generators)
    while True:
        enlarged = closure|{table[a][b] for table in tables for a in closure for b in closure}
        if enlarged==closure:break
        closure = enlarged
    result = {'size':n,'generated_subalgebra':sorted(closure),'congruence':None,'quotient_tables':None}
    if partition is not None:
        if not isinstance(partition,list) or len(partition)!=n or any(type(v) is not int or not 0<=v<n for v in partition):
            raise ValueError('Partition requires one finite integer block label per element')
        blocks = sorted(set(partition)); projection = [blocks.index(v) for v in partition]
        for op,table in enumerate(tables):
            for a in range(n):
                for b in range(n):
                    for c in range(n):
                        for d in range(n):
                            if projection[a]==projection[c] and projection[b]==projection[d] and projection[table[a][b]]!=projection[table[c][d]]:
                                return {**result,'congruence':False,'counterexample':{'operation':op,'inputs':[a,b,c,d]}}
        representatives = [projection.index(i) for i in range(len(blocks))]
        result.update(congruence=True,projection=projection,
            quotient_tables=[[[projection[table[a][b]] for b in representatives] for a in representatives] for table in tables])
    return result


def calculate(**arguments):return _calculate('universal_algebra',**arguments)


def finite_signature(size,operations,*,identities=(),variables=('x','y'),generators=None):
    """Total operations of arity 0..4, term evaluation and exhaustive identities."""
    from itertools import product
    if type(size) is not int or not 1<=size<=16 or not isinstance(operations,dict) or not 1<=len(operations)<=8:raise ValueError('Invalid finite algebra signature')
    for name,op in operations.items():
        if set(op)!={'arity','values'} or type(op['arity']) is not int or not 0<=op['arity']<=4 or len(op['values'])!=size**op['arity'] or any(type(v) is not int or not 0<=v<size for v in op['values']):raise ValueError('Operation is not closed and total')
    if len(variables)>4 or len(set(variables))!=len(variables) or size**len(variables)>65536 or len(identities)>32:raise ValueError('Identity budget exceeded')
    def apply(name,args):
        op=operations[name]
        if len(args)!=op['arity']:raise ValueError('Term arity mismatch')
        index=0
        for a in args:index=index*size+a
        return op['values'][index]
    def term(raw,env,depth=0):
        if depth>24:raise ValueError('Term depth exceeded')
        if type(raw) is str and raw in env:return env[raw]
        if isinstance(raw,dict) and set(raw)=={'op','args'} and raw['op'] in operations and isinstance(raw['args'],list):
            return apply(raw['op'],[term(a,env,depth+1) for a in raw['args']])
        raise ValueError('Invalid algebra term')
    outcomes=[]
    for identity in identities:
        if len(identity)!=2:raise ValueError('Paired identity terms required')
        counterexample=None
        for values in product(range(size),repeat=len(variables)):
            env=dict(zip(variables,values))
            if term(identity[0],env)!=term(identity[1],env):counterexample=env;break
        outcomes.append({'holds':counterexample is None,'counterexample':counterexample})
    closure=set(range(size) if generators is None else generators)
    if any(type(v) is not int or not 0<=v<size for v in closure):raise ValueError('Invalid generator')
    while True:
        enlarged=closure|{apply(name,args) for name,op in operations.items() for args in product(closure,repeat=op['arity'])}
        if enlarged==closure:break
        closure=enlarged
    return {'identities':outcomes,'generated_subalgebra':sorted(closure)}


def congruences(table):
    """Enumerate the congruence lattice of one finite binary algebra, n<=7."""
    universal_algebra([table]);n=len(table)
    if n>7:raise ValueError('Congruence enumeration is limited to seven elements')
    partitions=[]
    def visit(prefix):
        if len(prefix)==n:
            if universal_algebra([table],partition=prefix)['congruence']:partitions.append(prefix)
            return
        for label in range(max(prefix,default=-1)+2):visit(prefix+[label])
    visit([0])
    return {'partitions':partitions,'refinement':[[all(a[i]!=a[j] or b[i]==b[j] for i in range(n) for j in range(n)) for b in partitions] for a in partitions]}


def free_term_algebra(table,generators=1,max_functions=256):
    """Term functions give the free algebra in the variety generated by this algebra."""
    from itertools import product
    universal_algebra([table]);n=len(table)
    if type(generators) is not int or not 1<=generators<=3 or n**generators>256 or not 1<=max_functions<=1024:raise ValueError('Free-algebra budget exceeded')
    inputs=list(product(range(n),repeat=generators));functions={tuple(v[i] for v in inputs) for i in range(generators)}
    while True:
        result=functions|{tuple(table[x][y] for x,y in zip(a,b)) for a in functions for b in functions}
        if len(result)>max_functions:raise ValueError('Term-function closure exceeded its explicit budget')
        if result==functions:break
        functions=result
    rows=sorted(functions);index={v:i for i,v in enumerate(rows)}
    return {'term_functions':[list(v) for v in rows],
            'table':[[index[tuple(table[x][y] for x,y in zip(a,b))] for b in rows] for a in rows],
            'scope':'Free algebra on the stated generators in the variety generated by the supplied finite binary algebra.'}
