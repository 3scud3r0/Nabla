"""Declarative patterns and rewrite rules for equality saturation."""
from __future__ import annotations
import ast, hashlib, json, re
from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping, TypeAlias
from ..expression import Binary, Expr, Number, Symbol

_VAR=re.compile(r"\?([A-Za-z][A-Za-z0-9_]*)")
_SENTINEL="NablaPatternVariable"

@dataclass(frozen=True)
class PVar:
    name:str
    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*",self.name): raise ValueError("Nome de variável de padrão inválido")

@dataclass(frozen=True)
class PNode:
    op:str
    children:tuple["Pattern",...]=()
    value:Fraction|str|None=None
    def __post_init__(self):
        if self.op not in {"number","symbol","+","-","*","/","**"}: raise ValueError("Operador de padrão inválido")
        if self.op in {"number","symbol"} and self.children: raise ValueError("Literal não pode ter filhos")
        if self.op not in {"number","symbol"} and len(self.children)!=2: raise ValueError("Operador binário exige dois filhos")

Pattern:TypeAlias=PVar|PNode

@dataclass(frozen=True)
class RuleCondition:
    kind:str
    variable:str
    def __post_init__(self):
        if self.kind not in {"nonzero", "defined"}: raise ValueError("Condição não suportada")
        PVar(self.variable)

@dataclass(frozen=True)
class RewriteRule:
    name:str
    lhs:Pattern
    rhs:Pattern
    conditions:tuple[RuleCondition,...]=()
    domains:tuple[str,...]=("rational",)
    justification:str=""
    lean_theorem:str=""
    version:int=1
    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.+*-]*",self.name): raise ValueError("Nome de regra inválido")
        lhs=pattern_variables(self.lhs)
        if not pattern_variables(self.rhs)<=lhs: raise ValueError("RHS introduz variável")
        if any(c.variable not in lhs for c in self.conditions): raise ValueError("Condição referencia variável ausente")
        if not self.domains: raise ValueError("Regra sem domínio")
    def to_data(self):
        return {"name":self.name,"lhs":pattern_to_data(self.lhs),"rhs":pattern_to_data(self.rhs),
                "conditions":[{"kind":c.kind,"variable":c.variable} for c in self.conditions],
                "domains":list(self.domains),"justification":self.justification,
                "lean_theorem":self.lean_theorem,"version":self.version}
    @property
    def rule_hash(self):
        raw=json.dumps(self.to_data(),sort_keys=True,separators=(",",":"),ensure_ascii=True)
        return hashlib.sha256(raw.encode()).hexdigest()

def parse_pattern(source:str)->Pattern:
    if len(source)>4096: raise ValueError("Padrão grande demais")
    transformed=_VAR.sub(lambda m:_SENTINEL+m.group(1),source.replace("^","**"))
    try: node=ast.parse(transformed,mode="eval").body
    except SyntaxError as exc: raise ValueError("Sintaxe de padrão inválida") from exc
    return _convert(node,0)

def _convert(node,depth):
    if depth>64: raise ValueError("Padrão profundo demais")
    if isinstance(node,ast.Name):
        return PVar(node.id[len(_SENTINEL):]) if node.id.startswith(_SENTINEL) else PNode("symbol",value=node.id)
    if isinstance(node,ast.Constant) and type(node.value) is int: return PNode("number",value=Fraction(node.value))
    if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
        value=_convert(node.operand,depth+1)
        return value if isinstance(node.op,ast.UAdd) else PNode("*",(PNode("number",value=Fraction(-1)),value))
    if isinstance(node,ast.BinOp):
        op={ast.Add:"+",ast.Sub:"-",ast.Mult:"*",ast.Div:"/",ast.Pow:"**"}.get(type(node.op))
        if op is None: raise ValueError("Operador não permitido")
        return PNode(op,(_convert(node.left,depth+1),_convert(node.right,depth+1)))
    raise ValueError("Padrão inválido")

def pattern_variables(pattern:Pattern)->frozenset[str]:
    if isinstance(pattern,PVar): return frozenset({pattern.name})
    out=set()
    for child in pattern.children: out.update(pattern_variables(child))
    return frozenset(out)

def pattern_to_data(pattern:Pattern):
    if isinstance(pattern,PVar): return {"kind":"variable","name":pattern.name}
    value=pattern.value
    if isinstance(value,Fraction): value=[value.numerator,value.denominator]
    out={"kind":"node","op":pattern.op}
    if value is not None: out["value"]=value
    if pattern.children: out["children"]=[pattern_to_data(c) for c in pattern.children]
    return out

def match_expr(pattern:Pattern,expr:Expr,bindings:Mapping[str,Expr]|None=None):
    out=dict(bindings or {})
    if isinstance(pattern,PVar):
        old=out.get(pattern.name)
        if old is not None and old!=expr: return None
        out[pattern.name]=expr; return out
    if pattern.op=="number": return out if isinstance(expr,Number) and expr.value==pattern.value else None
    if pattern.op=="symbol": return out if isinstance(expr,Symbol) and expr.name==pattern.value else None
    if not isinstance(expr,Binary) or expr.op!=pattern.op: return None
    out=match_expr(pattern.children[0],expr.left,out)
    return None if out is None else match_expr(pattern.children[1],expr.right,out)

def instantiate_expr(pattern:Pattern,bindings:Mapping[str,Expr])->Expr:
    if isinstance(pattern,PVar): return bindings[pattern.name]
    if pattern.op=="number": return Number(pattern.value)
    if pattern.op=="symbol": return Symbol(pattern.value)
    return Binary(pattern.op,instantiate_expr(pattern.children[0],bindings),instantiate_expr(pattern.children[1],bindings))

__all__=["PVar","PNode","Pattern","RuleCondition","RewriteRule","parse_pattern","pattern_variables",
         "pattern_to_data","match_expr","instantiate_expr"]
