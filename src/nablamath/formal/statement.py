"""Restricted rational propositions with partial-expression domain obligations."""
from dataclasses import dataclass
from ..core.semantic_ir import SemanticExpression,canonical_json,fingerprint,rational
from ..core.obligations import domain_obligations
from ..expression import Expr,Number,parse_expr,to_data,evaluate
from ..schema.expression import from_data
from .translate import free_symbols

RELATIONS={'eq':'=','ne':'≠','le':'≤','lt':'<','ge':'≥','gt':'>'}


@dataclass(frozen=True)
class Predicate:
    left: Expr
    relation: str
    right: Expr

    def __post_init__(self):
        if self.relation not in RELATIONS:
            raise ValueError('Relacao formal invalida')
        SemanticExpression(self.left);SemanticExpression(self.right)

    def to_data(self):
        return {'left':to_data(self.left),'relation':self.relation,'right':to_data(self.right)}

    def evaluate(self,values):
        a,b=evaluate(self.left,values),evaluate(self.right,values)
        return {'eq':a==b,'ne':a!=b,'le':a<=b,'lt':a<b,'ge':a>=b,'gt':a>b}[self.relation]

    @classmethod
    def from_data(cls,data):
        if not isinstance(data,dict) or set(data)!={'left','relation','right'}:
            raise ValueError('Predicado serializado invalido')
        return cls(from_data(data['left']),data['relation'],from_data(data['right']))


@dataclass(frozen=True)
class FormalStatement:
    goal: Predicate
    assumptions: tuple[Predicate,...]=()

    def __post_init__(self):
        if len(self.assumptions)>32:
            raise ValueError('Maximo 32 hipoteses')
        object.__setattr__(self,'assumptions',tuple(self.assumptions))
        if len(self.variables)>8:
            raise ValueError('Maximo oito variaveis formais')

    @classmethod
    def equality(cls,left,right,assumptions=()):
        return cls(Predicate(parse_expr(left),'eq',parse_expr(right)),tuple(assumptions))

    @property
    def variables(self):
        names=set()
        for predicate in (self.goal,*self.assumptions):
            names.update(free_symbols(predicate.left));names.update(free_symbols(predicate.right))
        return tuple(sorted(names))

    @property
    def domain(self):
        obligations=[]
        for predicate in (self.goal,*self.assumptions):
            for side in (predicate.left,predicate.right):
                obligations.extend(domain_obligations(side))
        return tuple(dict.fromkeys(Predicate(o.expression,'ne',Number(rational(0))) for o in obligations))

    @property
    def hypotheses(self):
        return tuple(dict.fromkeys((*self.domain,*self.assumptions)))

    def to_data(self):
        return {'schema_version':1,'domain':'partial_rational','goal':self.goal.to_data(),
                'assumptions':[p.to_data() for p in self.assumptions],
                'domain_obligations':[p.to_data() for p in self.domain],'variables':list(self.variables)}

    @property
    def content_id(self):
        return fingerprint(self.to_data())

    @classmethod
    def from_data(cls,data):
        if not isinstance(data,dict) or set(data)!={'schema_version','domain','goal','assumptions','domain_obligations','variables'} or data['schema_version']!=1 or data['domain']!='partial_rational':
            raise ValueError('Contrato de enunciado invalido')
        result=cls(Predicate.from_data(data['goal']),tuple(Predicate.from_data(p) for p in data['assumptions']))
        if result.to_data()!=data:
            raise ValueError('Dominio ou variaveis divergentes')
        return result
