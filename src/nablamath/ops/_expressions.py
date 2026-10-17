"""Small expression AST shared by numerical complex and symbolic metric adapters.

No eval, sympify(string), attribute access, indexing or Python source execution.
"""
import ast
import cmath
import math
import operator

FUNCTIONS = {'sin','cos','tan','sinh','cosh','tanh','exp','log','sqrt'}


class ScientificExpression:
    def __init__(self, source, variables):
        if not isinstance(source,str) or not 1 <= len(source) <= 2048:
            raise ValueError('Expression must contain 1–2048 characters')
        if not all(isinstance(v,str) and v.isidentifier() and not v.startswith('_') and v not in FUNCTIONS|{'pi','E','I'} for v in variables):
            raise ValueError('Invalid expression variables')
        self.variables = tuple(variables)
        self.root = ast.parse(source,mode='eval').body
        if sum(1 for _ in ast.walk(self.root)) > 256:
            raise ValueError('Expression AST exceeds budget')
        self._walk(self.root,{name:1+0j for name in self.variables},symbolic=False,validate=True)

    def _walk(self,node,values,*,symbolic,validate=False):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float,complex):
            value = node.value
            if (type(value) is int and value.bit_length() > 256) or (type(value) is not int and not math.isfinite(abs(value))):
                raise ValueError('Expression constant exceeds budget')
            if symbolic:
                import sympy as sp
                if isinstance(value,complex):
                    return sp.Rational(str(value.real))+sp.I*sp.Rational(str(value.imag))
                return sp.Rational(str(value))
            return value
        if isinstance(node,ast.Name):
            if node.id in values:
                return values[node.id]
            if node.id in {'pi','E','I'}:
                if symbolic:
                    import sympy as sp
                    return {'pi':sp.pi,'E':sp.E,'I':sp.I}[node.id]
                return {'pi':math.pi,'E':math.e,'I':1j}[node.id]
            raise ValueError('Unknown variable: '+node.id)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            value = self._walk(node.operand,values,symbolic=symbolic,validate=validate)
            return -value if isinstance(node.op,ast.USub) else value
        if isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow)):
            left = self._walk(node.left,values,symbolic=symbolic,validate=validate)
            right = self._walk(node.right,values,symbolic=symbolic,validate=validate)
            if isinstance(node.op,ast.Pow):
                exponent = node.right
                if isinstance(exponent,ast.UnaryOp) and isinstance(exponent.op,ast.USub):
                    exponent = exponent.operand
                if not isinstance(exponent,ast.Constant) or type(exponent.value) is not int or abs(exponent.value) > 32:
                    raise ValueError('Only constant integer powers of magnitude <=32 are supported')
            if validate:
                return 1+0j
            operations = {ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow}
            return operations[type(node.op)](left,right)
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in FUNCTIONS and len(node.args) == 1 and not node.keywords:
            value = self._walk(node.args[0],values,symbolic=symbolic,validate=validate)
            if validate:
                return 1+0j
            if symbolic:
                import sympy as sp
                return getattr(sp,node.func.id)(value)
            return getattr(cmath,node.func.id)(value)
        raise ValueError('Expression is outside the closed scientific grammar')

    def evaluate(self, **values):
        if set(values) != set(self.variables):
            raise ValueError('Expression bindings differ from declared variables')
        result = complex(self._walk(self.root,values,symbolic=False))
        if not math.isfinite(result.real) or not math.isfinite(result.imag):
            raise ArithmeticError('Expression produced a nonfinite value')
        return result

    def symbolic(self, symbols):
        return self._walk(self.root,symbols,symbolic=True)
