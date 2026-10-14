"""Budgeted exact minimization in a declared finite integer box, preserving failure kind."""
from dataclasses import dataclass,asdict
from fractions import Fraction
from ..core.semantic_ir import rational
from ..expression import evaluate,parse_expr,DomainError
from ..formal.translate import free_symbols
from .search import search_equivalence


@dataclass(frozen=True)
class ShrinkResult:
    status: str
    original: tuple[tuple[str,int],...]
    witness: tuple[tuple[str,int],...]
    checked: int
    failure_kind: str
    minimal_in_box: bool
    budget: int

    def to_data(self):
        return asdict(self)


def shrink_counterexample(left,right,assignment,*,budget=10000,compare_domains=True):
    if type(budget) is not int or not 1<=budget<=100000:
        raise ValueError('Orcamento de reducao invalido')
    # Apply the same syntactic/arithmetic resource checks as the search engine.
    lhs,rhs=parse_expr(left),parse_expr(right)
    names=tuple(sorted(set(free_symbols(lhs))|set(free_symbols(rhs))))
    if set(assignment)!=set(names):
        raise ValueError('Testemunho requer exatamente as variaveis do enunciado')
    values={name:rational(v) for name,v in assignment.items()}
    if any(v.denominator!=1 or abs(v)>32 for v in values.values()):
        raise ValueError('Reducao limitada ao dominio inteiro -32..32')
    original=tuple((name,int(values[name])) for name in names)
    def failure(candidate):
        outputs=[]
        for expression in (lhs,rhs):
            try:outputs.append(evaluate(expression,{n:Fraction(v) for n,v in candidate}))
            except (DomainError,ZeroDivisionError):outputs.append(None)
        a,b=outputs
        if (a is None)!=(b is None) and compare_domains:
            return 'domain_counterexample'
        return 'counterexample' if a is not None and b is not None and a!=b else None
    kind=failure(original)
    if kind is None:
        raise ValueError('Entrada nao e contraexemplo reexecutavel')
    limit=max((abs(v) for _,v in original),default=0)
    search_equivalence(left,right,radius=limit,budget=1,compare_domains=compare_domains)
    best=original;checked=0
    # Complete L1 shells prove minimality in the finite box if budget permits.
    def shell(index,remaining,prefix=()):
        if index==len(names):
            if remaining==0:yield prefix
            return
        for value in range(-min(limit,remaining),min(limit,remaining)+1):
            yield from shell(index+1,remaining-abs(value),prefix+(value,))
    for norm in range(sum(abs(v) for _,v in original)+1):
        for vector in shell(0,norm):
            if checked>=budget:
                return ShrinkResult('budget_exhausted',original,best,checked,kind,False,budget)
            checked+=1
            candidate=tuple(zip(names,vector))
            if failure(candidate)==kind:
                return ShrinkResult('minimized',original,candidate,checked,kind,True,budget)
    return ShrinkResult('unchanged',original,best,checked,kind,True,budget)
