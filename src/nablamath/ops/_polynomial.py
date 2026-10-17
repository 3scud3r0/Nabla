"""Closed rational polynomial AST: no eval, CAS parser or optional dependency."""
import ast
from fractions import Fraction
from ._area_utils import scalar


class Polynomial:
    def __init__(self,terms,dimension):
        self.n = dimension
        self.terms = {tuple(k):Fraction(v) for k,v in terms.items() if v}
        if len(self.terms)>256 or any(len(k)!=dimension or sum(k)>16 for k in self.terms):
            raise ValueError('Polynomial exceeds degree 16 / 256 terms')
        if any(max(v.numerator.bit_length(),v.denominator.bit_length())>16384 for v in self.terms.values()):
            raise ValueError('Polynomial coefficient exceeds its arithmetic budget')

    @classmethod
    def constant(cls,value,n):
        return cls({(0,)*n:scalar(value)},n)

    @classmethod
    def variable(cls,index,n):
        powers = [0]*n;powers[index] = 1
        return cls({tuple(powers):1},n)

    def __add__(self,other):
        if not isinstance(other,Polynomial):
            other = self.constant(other,self.n)
        terms = dict(self.terms)
        for key,value in other.terms.items():
            terms[key] = terms.get(key,0)+value
        return Polynomial(terms,self.n)

    __radd__ = __add__

    def __neg__(self):
        return Polynomial({k:-v for k,v in self.terms.items()},self.n)

    def __sub__(self,other):
        return self+-other if isinstance(other,Polynomial) else self+-self.constant(other,self.n)

    def __mul__(self,other):
        if not isinstance(other,Polynomial):
            other = self.constant(other,self.n)
        terms = {}
        for left,a in self.terms.items():
            for right,b in other.terms.items():
                key = tuple(i+j for i,j in zip(left,right))
                if sum(key)>16:
                    raise ValueError('Polynomial degree exceeds 16')
                terms[key] = terms.get(key,0)+a*b
                if len(terms)>256:
                    raise ValueError('Polynomial exceeds its term budget')
        return Polynomial(terms,self.n)

    __rmul__ = __mul__

    def derivative(self,index):
        terms = {}
        for powers,value in self.terms.items():
            if powers[index]:
                key = list(powers);key[index]-=1
                terms[tuple(key)] = value*powers[index]
        return Polynomial(terms,self.n)

    def evaluate(self,point):
        result = 0
        for powers,value in self.terms.items():
            term = value
            for x,power in zip(point,powers):
                term *= x**power
            result += term
        return result

    def text(self,names):
        parts = []
        for powers,coefficient in sorted(self.terms.items(),reverse=True):
            factors = [name+(f'**{power}' if power!=1 else '') for name,power in zip(names,powers) if power]
            parts.append(str(coefficient)+(' * '+' * '.join(factors) if factors else ''))
        return ' + '.join(parts).replace('+ -','- ') or '0'


def parse_polynomial(source,variables):
    if not isinstance(variables,(list,tuple)) or not 1<=len(variables)<=4 or len(set(variables))!=len(variables) or any(not isinstance(v,str) or not v.isidentifier() or v.startswith('_') for v in variables):
        raise ValueError('Require 1–4 distinct polynomial variables')
    if not isinstance(source,str) or not 1<=len(source)<=2048:
        raise ValueError('Polynomial expression exceeds its source budget')
    try:
        root = ast.parse(source,mode='eval').body
    except SyntaxError as error:
        raise ValueError('Invalid polynomial syntax') from error
    if sum(1 for _ in ast.walk(root))>256:
        raise ValueError('Polynomial AST exceeds its budget')
    n = len(variables)
    def visit(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):
            return Polynomial.constant(str(node.value),n)
        if isinstance(node,ast.Name) and node.id in variables:
            return Polynomial.variable(variables.index(node.id),n)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd)):
            value = visit(node.operand)
            return -value if isinstance(node.op,ast.USub) else value
        if isinstance(node,ast.BinOp):
            left = visit(node.left)
            if isinstance(node.op,ast.Pow):
                if not isinstance(node.right,ast.Constant) or type(node.right.value) is not int or not 0<=node.right.value<=16:
                    raise ValueError('Polynomial powers must be integers in [0,16]')
                result = Polynomial.constant(1,n)
                for _ in range(node.right.value):
                    result = result*left
                return result
            right = visit(node.right)
            if isinstance(node.op,ast.Add):return left+right
            if isinstance(node.op,ast.Sub):return left-right
            if isinstance(node.op,ast.Mult):return left*right
            if isinstance(node.op,ast.Div) and set(right.terms)=={(0,)*n}:
                return left*(1/right.terms[(0,)*n])
        raise ValueError('Expression is outside the rational polynomial grammar')
    return visit(root)
