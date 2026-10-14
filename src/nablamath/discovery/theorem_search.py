"""Independent polynomial normalization or explicit formal backend checks."""
from ..expression import parse_expr
from ..core.semantic_ir import fingerprint


def search_identity(left, right, *, backend='exact', project=None, timeout=30):
    if backend=='exact':
        from ..math.algebra.groebner import polynomial_from_expr
        try:
            a=polynomial_from_expr(parse_expr(left),('x',))
            b=polynomial_from_expr(parse_expr(right),('x',))
            from ..core.obligations import domain_obligations
            left_domain=domain_obligations(parse_expr(left));right_domain=domain_obligations(parse_expr(right))
            equal=a.terms==b.terms and left_domain==right_domain
            receipt={'backend':'exact_polynomial_normalization','equal':equal,'formal_proof':False,
                     'left_terms':[[list(m),str(c)] for m,c in a.terms],
                     'right_terms':[[list(m),str(c)] for m,c in b.terms]}
        except (ValueError,ArithmeticError) as exc:
            receipt={'backend':'exact_polynomial_normalization','equal':None,'formal_proof':False,'status':'unsupported','reason':str(exc)}
    elif backend in {'lean','smt'}:
        from ..formal import FormalStatement, Predicate, translate_statement, check_lean, solve_statement
        statement=FormalStatement(Predicate(parse_expr(left),'eq',parse_expr(right)))
        if backend=='lean':
            from pathlib import Path
            checked=check_lean(translate_statement(statement),project=Path(project or 'lean'),timeout=timeout)
            receipt=checked.to_data()
        else:
            receipt=solve_statement(statement,timeout_ms=int(timeout*1000))
    else:
        raise ValueError('Backend desconhecido')
    payload={'left':left,'right':right,'receipt':receipt}
    return {**payload,'search_id':fingerprint(payload)}
