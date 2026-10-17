"""Typed AST -> Lean translation without accepting arbitrary Lean source text."""
from __future__ import annotations
from fractions import Fraction
import re
from typing import Iterable, Mapping, TYPE_CHECKING
from ..expression import Binary, Expr, Number, Symbol
from ..symbolic.patterns import RewriteRule, instantiate_expr, pattern_variables
if TYPE_CHECKING:
    from ..research import ResearchResult

_LEAN_THEOREM = re.compile(r"[A-Za-z][A-Za-z0-9_']*\Z")


def certificate_statements(certificate):
    """Translate exact structured witnesses to independently checkable goals.

    A matrix witness becomes scalar dot-product equalities, rather than trusting
    a numerical residual or a CAS boolean. No caller-provided Lean source enters.
    """
    from .statement import FormalStatement
    from ..ops._area_utils import matrix,scalar
    if not isinstance(certificate,dict):raise ValueError('Structured certificate required')
    kind=certificate.get('kind');statements=[]
    if kind=='identity':
        if set(certificate)!={'kind','left','right'}:raise ValueError('Closed identity certificate required')
        statements=[FormalStatement.equality(certificate['left'],certificate['right'])]
    elif kind in {'matrix_product','matrix_inverse','chain_boundary'}:
        required={'kind','left','right','result'} if kind=='matrix_product' else {'kind','left','right'}
        if set(certificate)!=required:raise ValueError('Closed matrix certificate required')
        a,b=matrix(certificate['left'],maximum=16),matrix(certificate['right'],maximum=16)
        if len(a[0])!=len(b):raise ValueError('Certificate matrix shapes do not compose')
        if kind=='matrix_product':target=matrix(certificate['result'],maximum=16)
        elif kind=='matrix_inverse':
            if len(a)!=len(a[0]) or len(b)!=len(b[0]) or len(a)!=len(b):raise ValueError('Square inverse certificate required')
            target=[[int(i==j) for j in range(len(a))] for i in range(len(a))]
        else:target=[[0]*len(b[0]) for _ in a]
        if len(target)!=len(a) or len(target[0])!=len(b[0]):raise ValueError('Certificate output shape mismatch')
        for i,row in enumerate(a):
            for j in range(len(b[0])):
                source='+'.join(f'({v})*({b[k][j]})' for k,v in enumerate(row))
                statements.append(FormalStatement.equality(source,str(target[i][j])))
    else:raise ValueError('Unsupported exact certificate kind')
    return tuple(statements)


def translate_certificate(certificate):
    from .lean_bridge import translate_statement
    from ..core.semantic_ir import fingerprint
    statements=certificate_statements(certificate)
    return {'certificate_id':fingerprint(certificate),'statements':[s.to_data() for s in statements],
            'translations':[translate_statement(s).to_data() for s in statements],
            'formal_proof':False,'scope':'Generated proof obligations; translation itself is not proof execution.'}

def _rational(value: Fraction) -> str:
    numerator=f"({value.numerator} : ℚ)"
    return numerator if value.denominator==1 else f"({numerator} / ({value.denominator} : ℚ))"

def _lean_name(name: str) -> str:
    Symbol(name)
    return f"nabla_{name}"

def _term(expr: Expr, values: Mapping[str, Fraction] | None) -> str:
    if isinstance(expr, Number): return _rational(expr.value)
    if isinstance(expr, Symbol):
        if values is None: return _lean_name(expr.name)
        if expr.name not in values: raise ValueError(f"Sem valor para símbolo {expr.name}")
        return _rational(values[expr.name])
    left,right=_term(expr.left,values),_term(expr.right,values)
    if expr.op=="**":
        exponent=expr.right.value.numerator if isinstance(expr.right,Number) and expr.right.value.denominator==1 else None
        if exponent is None: raise ValueError("Expoente Lean precisa ser literal inteiro")
        base=f"(({left}) ^ ({abs(exponent)} : ℕ))"
        return f"({base})⁻¹" if exponent<0 else base
    return f"({left} {expr.op} {right})"

def lean_term(expr: Expr) -> str: return _term(expr,None)

def free_symbols(expr: Expr) -> tuple[str,...]:
    names=set()
    def visit(node):
        if isinstance(node,Symbol): names.add(node.name)
        elif isinstance(node,Binary): visit(node.left); visit(node.right)
    visit(expr); return tuple(sorted(names))

def lean_source(result: "ResearchResult") -> str:
    values=dict(result.values)
    return ("import Mathlib.Tactic.Ring\nimport Mathlib.Tactic.FieldSimp\nimport Mathlib.Tactic.Linarith\nimport Mathlib.Tactic.NormNum\n\n"
            f"-- Instância racional {result.content_id}; gerada de AST restrita.\n"
            f"example : {_term(result.original,values)} = {_rational(result.value)} := by\n"
            "  norm_num\n")

def universal_lean_source(lhs: Expr, rhs: Expr, *, nonzero: Iterable[Expr]=(),
                          theorem_name: str="nablamath_generated") -> str:
    if not _LEAN_THEOREM.fullmatch(theorem_name): raise ValueError("Nome de teorema Lean inválido")
    from ..core.obligations import domain_obligations
    nonzero=tuple(dict.fromkeys((*tuple(nonzero),
        *(o.expression for side in (lhs,rhs) for o in domain_obligations(side)))))
    names=set(free_symbols(lhs))|set(free_symbols(rhs))
    for expr in nonzero: names.update(free_symbols(expr))
    declarations=" ".join(f"({_lean_name(name)} : ℚ)" for name in sorted(names))
    hypotheses=" ".join(f"(h{i} : {lean_term(expr)} ≠ 0)" for i,expr in enumerate(nonzero))
    binders=" ".join(part for part in (declarations,hypotheses) if part)
    hs=", ".join(f"h{i}" for i in range(len(nonzero)))
    tactic=f"  field_simp [{hs}] <;> ring\n" if hs else "  field_simp <;> ring\n"
    return ("import Mathlib.Tactic.Ring\nimport Mathlib.Tactic.FieldSimp\nimport Mathlib.Tactic.Linarith\nimport Mathlib.Tactic.NormNum\n\n-- Teorema universal gerado de AST tipada pelo NablaMath.\n"
            f"theorem {theorem_name} {binders} : {lean_term(lhs)} = {lean_term(rhs)} := by\n"+tactic)

def rule_lean_source(rule: RewriteRule) -> str:
    bindings={name:Symbol(name) for name in pattern_variables(rule.lhs)}
    lhs=instantiate_expr(rule.lhs,bindings); rhs=instantiate_expr(rule.rhs,bindings)
    nonzero=tuple(bindings[c.variable] for c in rule.conditions if c.kind=="nonzero")
    safe_name="nablamath_rule_"+re.sub(r"[^A-Za-z0-9_]","_",rule.name)
    source=universal_lean_source(lhs,rhs,nonzero=nonzero,theorem_name=safe_name)
    return source.replace("-- Teorema universal gerado de AST tipada pelo NablaMath.\n",
                          f"-- Regra {rule.name}; sha256={rule.rule_hash}\n",1)

__all__=["lean_source","lean_term","free_symbols","universal_lean_source","rule_lean_source"]
