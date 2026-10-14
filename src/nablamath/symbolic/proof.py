"""Independent verification of e-graph rewrite certificates."""
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable, Mapping
from ..expression import Binary, Expr, Number, Symbol, render, to_data
from .assumptions import AssumptionSet
from .patterns import RewriteRule, instantiate_expr, match_expr

def _intrinsic_hash(name:str)->str:
    return hashlib.sha256((name+":exact-rational-constant-fold-v1").encode()).hexdigest()

@dataclass(frozen=True)
class RewriteEvent:
    rule:str
    source_class:int
    target_class:int
    before:Expr|None=None
    after:Expr|None=None
    substitution:tuple[tuple[str,Expr],...]=()
    assumptions:tuple[str,...]=()
    justification:str=""
    rule_hash:str=""
    def to_data(self):
        out={"rule":self.rule,"source_class":self.source_class,"target_class":self.target_class,
             "substitution":{k:to_data(v) for k,v in self.substitution},
             "assumptions":list(self.assumptions),"justification":self.justification,"rule_hash":self.rule_hash}
        if self.before is not None: out["before"]=to_data(self.before)
        if self.after is not None: out["after"]=to_data(self.after)
        return out

@dataclass(frozen=True)
class CertificateVerification:
    valid:bool
    checked_steps:int
    root_connected:bool
    errors:tuple[str,...]=()
    def require_valid(self):
        if not self.valid: raise ValueError("Certificado inválido: "+"; ".join(self.errors))

def constant_fold_event(before:Expr,after:Expr,source_class:int,target_class:int)->RewriteEvent:
    return RewriteEvent("constant_fold",source_class,target_class,before,after,
                        justification="Aritmética racional exata.",rule_hash=_intrinsic_hash("constant_fold"))

def _fold(expr:Binary):
    if not isinstance(expr.left,Number) or not isinstance(expr.right,Number): return None
    a,b=expr.left.value,expr.right.value
    if expr.op=="+": v=a+b
    elif expr.op=="-": v=a-b
    elif expr.op=="*": v=a*b
    elif expr.op=="/": v=None if b==0 else a/b
    elif expr.op=="**" and b.denominator==1 and not(a==0 and b<=0): v=a**b.numerator
    else: v=None
    return None if v is None else Number(v)

def verify_rewrite_event(event:RewriteEvent,rules:Mapping[str,RewriteRule],assumptions:AssumptionSet):
    if event.before is None or event.after is None: return f"{event.rule}: AST ausente"
    if event.rule=="constant_fold":
        if event.rule_hash!=_intrinsic_hash("constant_fold"): return "constant_fold: hash inválido"
        return None if isinstance(event.before,Binary) and _fold(event.before)==event.after else "constant_fold: cálculo inválido"
    rule=rules.get(event.rule)
    if rule is None: return f"{event.rule}: regra ausente"
    if event.rule_hash!=rule.rule_hash: return f"{event.rule}: hash divergente"
    bindings=match_expr(rule.lhs,event.before)
    if bindings is None: return f"{event.rule}: padrão não casa"
    if instantiate_expr(rule.rhs,bindings)!=event.after: return f"{event.rule}: RHS incorreto"
    if dict(event.substitution)!=bindings: return f"{event.rule}: substituição divergente"
    for c in rule.conditions:
        if c.kind=="nonzero" and not assumptions.proves_nonzero(bindings[c.variable]):
            return f"{event.rule}: hipótese não provada"
        if c.kind=="defined" and not assumptions.proves_defined(bindings[c.variable]):
            return f"{event.rule}: domínio não provado"
    expected=tuple((f"{render(bindings[c.variable])} != 0" if c.kind=="nonzero" else f"defined({render(bindings[c.variable])})") for c in rule.conditions)
    return None if event.assumptions==expected else f"{event.rule}: hipóteses divergentes"

def _sub(expr:Expr):
    yield expr
    if isinstance(expr,Binary):
        yield from _sub(expr.left); yield from _sub(expr.right)

class _CC:
    def __init__(self,exprs):
        self.exprs=tuple(dict.fromkeys(exprs)); self.idx={e:i for i,e in enumerate(self.exprs)}
        self.parent=list(range(len(self.exprs)))
    def find(self,i):
        while self.parent[i]!=i:
            self.parent[i]=self.parent[self.parent[i]]; i=self.parent[i]
        return i
    def union(self,a,b):
        ia,ib=self.find(self.idx[a]),self.find(self.idx[b])
        if ia==ib:return False
        lo,hi=min(ia,ib),max(ia,ib); self.parent[hi]=lo; return True
    def close(self):
        while True:
            seen={}; changed=False
            for i,e in enumerate(self.exprs):
                sig=("n",e.value) if isinstance(e,Number) else ("s",e.name) if isinstance(e,Symbol) else (e.op,self.find(self.idx[e.left]),self.find(self.idx[e.right]))
                if sig in seen: changed|=self.union(self.exprs[seen[sig]],e)
                else: seen[sig]=i
            if not changed:return

def verify_saturation_certificate(original:Expr,extracted:Expr,events:Iterable[RewriteEvent],
                                  rules:Iterable[RewriteRule],assumptions:AssumptionSet|None=None)->CertificateVerification:
    assumptions=assumptions or AssumptionSet(); events=tuple(events); registry={r.name:r for r in rules}; errors=[]; exprs=list(_sub(original))+list(_sub(extracted))
    for e in events:
        err=verify_rewrite_event(e,registry,assumptions)
        if err: errors.append(err)
        if e.before is not None: exprs.extend(_sub(e.before))
        if e.after is not None: exprs.extend(_sub(e.after))
    cc=_CC(exprs)
    for e in events:
        if e.before is not None and e.after is not None: cc.union(e.before,e.after)
    cc.close(); connected=cc.find(cc.idx[original])==cc.find(cc.idx[extracted])
    if not connected: errors.append("extração não conectada à raiz")
    return CertificateVerification(not errors and connected,len(events),connected,tuple(errors))

__all__=["RewriteEvent","CertificateVerification","constant_fold_event","verify_rewrite_event","verify_saturation_certificate"]
