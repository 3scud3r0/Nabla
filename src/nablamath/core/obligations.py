"""Domain obligations are retained independently from simplification and presentation."""
from dataclasses import dataclass
from ..expression import Binary,Expr,Number,Symbol,evaluate,to_data
from .semantic_ir import rational


@dataclass(frozen=True)
class Obligation:
    expression: Expr
    relation: str='nonzero'

    def __post_init__(self):
        if self.relation not in {'nonzero','positive','nonnegative'}:
            raise ValueError('Relacao de dominio nao suportada')

    def check(self, values) -> str:
        try:
            value=evaluate(self.expression,{k:rational(v) for k,v in values.items()})
        except KeyError:
            return 'unresolved'
        except ValueError as exc:
            if str(exc).startswith('Falta valor'):
                return 'unresolved'
            return 'violated'
        except ArithmeticError:
            return 'violated'
        valid={'nonzero':value!=0,'positive':value>0,'nonnegative':value>=0}[self.relation]
        return 'satisfied' if valid else 'violated'

    def to_data(self):
        return {'expression':to_data(self.expression),'relation':self.relation}


def domain_obligations(expr: Expr) -> tuple[Obligation,...]:
    result=[]
    def visit(node):
        if not isinstance(node,Binary):
            return
        visit(node.left)
        visit(node.right)
        if node.op=='/':
            result.append(Obligation(node.right))
        if node.op=='**':
            if not isinstance(node.right,Number) or node.right.value.denominator!=1:
                raise ValueError('Expoente deve ser inteiro literal')
            if node.right.value<=0:
                result.append(Obligation(node.left))
    visit(expr)
    return tuple(dict.fromkeys(result))


def require_obligations(obligations,values):
    for obligation in obligations:
        status=obligation.check(values)
        if status!='satisfied':
            raise ValueError(f'Obrigacao de dominio {status}: {obligation.relation}')
