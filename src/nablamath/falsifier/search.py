"""Enumerate a declared finite integer domain in increasing witness complexity."""
from dataclasses import dataclass, asdict
from fractions import Fraction

from ..expression import DomainError, Number, Symbol, evaluate, parse_expr


@dataclass(frozen=True)
class SearchResult:
    status: str
    checked: int
    skipped_undefined: int
    domain: str
    witness: tuple[tuple[str, int], ...] = ()
    left_value: str | None = None
    right_value: str | None = None
    exhaustive: bool = False
    formal_proof: bool = False

    def to_data(self) -> dict:
        return asdict(self)


def search_equivalence(left: str, right: str, *, radius: int = 3, budget: int = 1000,
                       compare_domains: bool = True) -> SearchResult:
    if type(radius) is not int or not 0 <= radius <= 32 or type(budget) is not int or not 1 <= budget <= 100_000:
        raise ValueError('Limites de busca invalidos')
    if len(left) > 512 or len(right) > 512:
        raise ValueError('Expressao excede o limite da busca')
    lhs, rhs = parse_expr(left), parse_expr(right)
    names = set()

    def inspect(node, depth=0):
        if depth > 12:
            raise ValueError('Expressao profunda demais para busca')
        if isinstance(node, Symbol):
            names.add(node.name)
            return max(1, radius.bit_length())
        if isinstance(node, Number):
            return max(abs(node.value.numerator).bit_length(), node.value.denominator.bit_length(), 1)
        a, b = inspect(node.left, depth+1), inspect(node.right, depth+1)
        if node.op == '**':
            if not isinstance(node.right, Number) or node.right.value.denominator != 1 or abs(node.right.value) > 8:
                raise ValueError('Busca admite apenas potencias inteiras literais de -8 a 8')
            result = a * max(1, abs(node.right.value.numerator))
        else:
            result = a + b + 2
        if result > 16384:
            raise ValueError('Custo aritmetico excede o limite')
        return result

    inspect(lhs)
    inspect(rhs)
    names = tuple(sorted(names))
    if len(names) > 4:
        raise ValueError('Busca limitada a quatro variaveis')
    domain = f'integer_grid:[{-radius},{radius}]^{len(names)};variables={",".join(names)}'
    # Shell enumeration avoids materializing the whole grid. First witness is
    # minimal in L1 norm inside this finite domain, not among all rationals.
    checked = skipped = 0
    for norm in range(len(names) * radius + 1):
        def assignments(index, remaining, prefix=()):
            if index == len(names):
                if remaining == 0:
                    yield prefix
                return
            for v in range(-min(radius, remaining), min(radius, remaining)+1):
                yield from assignments(index+1, remaining-abs(v), prefix+(v,))

        for values in assignments(0, norm):
            if checked == budget:
                return SearchResult('budget_exhausted', checked, skipped, domain)
            checked += 1
            mapping = {name: Fraction(value) for name, value in zip(names, values)}
            results = []
            for expression in (lhs, rhs):
                try:
                    results.append(evaluate(expression, mapping))
                except (DomainError, ZeroDivisionError):
                    results.append(None)
            a, b = results
            if (a is None) != (b is None) and compare_domains:
                return SearchResult('domain_counterexample', checked, skipped, domain, tuple(zip(names, values)),
                                    None if a is None else str(a), None if b is None else str(b))
            if a is None or b is None:
                skipped += 1
                continue
            if a != b:
                return SearchResult('counterexample', checked, skipped, domain, tuple(zip(names, values)), str(a), str(b))
    return SearchResult('no_counterexample_in_finite_domain', checked, skipped, domain, exhaustive=True)


def investigate(left,right,*,radius=3,budget=1000,shrink_budget=10000):
    """A reproducible report retaining failures, absence of evidence and resource limits."""
    from ..core.semantic_ir import fingerprint
    from .shrink import shrink_counterexample
    result=search_equivalence(left,right,radius=radius,budget=budget)
    report={'schema_version':1,'left':left,'right':right,'radius':radius,'budget':budget,
            'search':result.to_data(),'reduction':None,'formal_proof':False}
    if result.status in {'counterexample','domain_counterexample'}:
        report['reduction']=shrink_counterexample(left,right,dict(result.witness),budget=shrink_budget).to_data()
    return {**report,'report_id':fingerprint(report)}
