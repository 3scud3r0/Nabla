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
