"""Bounded structured expressions shared by optional advanced algorithms.

Never pass request text to sympify/parse_expr/lambdify. Algorithms may be costly;
remote callers must use AgentTools' process budget, not call these APIs in-process.
"""
import ast
from fractions import Fraction
import math


def sympy():
    try:
        import sympy as sp
    except ImportError as error:
        raise ImportError('Install nablamath[research] for symbolic advanced mathematics') from error
    return sp


def names(variables, maximum=16):
    if not isinstance(variables, (list, tuple)) or not 1 <= len(variables) <= maximum:
        raise ValueError('Invalid variable dimension')
    if any(type(v) is not str or not v.isidentifier() or v.startswith('_') for v in variables) or len(set(variables)) != len(variables):
        raise ValueError('Distinct public variable identifiers required')
    return tuple(variables)


def expression(source, variables, *, functions=True, degree_limit=128):
    sp = sympy(); variables = names(variables,32)
    symbols = {v: sp.Symbol(v) for v in variables}
    if type(source) not in (str, int, float, Fraction):
        raise ValueError('Expression must be a scalar or a source string')
    source = str(source)
    if len(source) > 8192:
        raise ValueError('Expression source budget exceeded')
    try:
        tree = ast.parse(source, mode='eval')
    except (SyntaxError, RecursionError) as error:
        raise ValueError('Invalid expression syntax') from error
    if sum(1 for _ in ast.walk(tree)) > 1024:
        raise ValueError('Expression AST budget exceeded')
    def degree_budget(node,depth=0):
        if depth>48:raise ValueError('Expression depth budget exceeded')
        if isinstance(node,ast.Name):return (1,0) if node.id in variables else (0,0)
        if isinstance(node,ast.UnaryOp):return degree_budget(node.operand,depth+1)
        if isinstance(node,ast.Call):
            for arg in node.args:degree_budget(arg,depth+1)
            return (0,0)
        if not isinstance(node,ast.BinOp):return (0,0)
        an,ad=degree_budget(node.left,depth+1);bn,bd=degree_budget(node.right,depth+1)
        if isinstance(node.op,(ast.Add,ast.Sub)):value=max(an+bd,bn+ad),ad+bd
        elif isinstance(node.op,ast.Mult):value=an+bn,ad+bd
        elif isinstance(node.op,ast.Div):value=an+bd,ad+bn
        elif isinstance(node.op,ast.Pow):
            try:power=ast.literal_eval(node.right)
            except (ValueError,TypeError):return (0,0)
            if type(power) is not int:return (0,0)
            value=(an*power,ad*power) if power>=0 else (-ad*power,-an*power)
        else:return (0,0)
        if max(value)>degree_limit:raise ValueError('Symbolic degree budget exceeded before polynomial expansion')
        active=len({v.id for v in ast.walk(node) if isinstance(v,ast.Name) and v.id in variables})
        if active and math.comb(max(value)+active,active)>100000:raise ValueError('Symbolic expansion term budget exceeded before CAS expansion')
        return value
    degree_budget(tree.body)
    allowed = {key: getattr(sp, key) for key in ('sin','cos','tan','exp','log','sqrt','sinh','cosh','tanh','Abs','erf')}
    def bounded(value):
        if value.is_Rational and max(int(value.p).bit_length(),int(value.q).bit_length())>16384:
            raise ValueError('Expression rational arithmetic budget exceeded')
        return value
    def visit(node, depth=0):
        if depth > 48:
            raise ValueError('Expression depth budget exceeded')
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if isinstance(node.value, float) and not math.isfinite(node.value):
                raise ValueError('Nonfinite scalar')
            if isinstance(node.value, int) and node.value.bit_length() > 4096:
                raise ValueError('Integer input budget exceeded')
            return sp.Rational(str(node.value))
        if isinstance(node, ast.Name):
            if node.id in symbols: return symbols[node.id]
            if node.id in ('pi', 'I'): return sp.pi if node.id == 'pi' else sp.I
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand, depth+1)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            a, b = visit(node.left, depth+1), visit(node.right, depth+1)
            if isinstance(node.op, ast.Add): return bounded(a+b)
            if isinstance(node.op, ast.Sub): return bounded(a-b)
            if isinstance(node.op, ast.Mult): return bounded(a*b)
            if isinstance(node.op, ast.Div):
                if b == 0: raise ValueError('Division by zero')
                return bounded(a/b)
            if isinstance(node.op, ast.Pow) and b.is_Rational and abs(b) <= 32:
                if a.is_Rational and b.is_Integer and abs(b)*(max(int(a.p).bit_length(),int(a.q).bit_length()))>16384:
                    raise ValueError('Expression power arithmetic budget exceeded')
                return bounded(a**b)
        if functions and isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in allowed and not node.keywords and len(node.args) == 1:
            return allowed[node.func.id](visit(node.args[0], depth+1))
        raise ValueError('Unsupported expression node')
    return visit(tree.body), tuple(symbols.values())


def rational_matrix(rows, *, maximum=64):
    sp = sympy()
    if not isinstance(rows, (list, tuple)) or not 1 <= len(rows) <= maximum or any(not isinstance(r,(list,tuple)) or not 1 <= len(r) <= maximum for r in rows):
        raise ValueError('Matrix dimension budget exceeded')
    if len({len(row) for row in rows}) != 1: raise ValueError('Ragged matrix')
    from ..ops._area_utils import scalar
    return sp.Matrix([[sp.Rational(str(scalar(v))) for v in row] for row in rows])


def data(value):
    """Portable output: exact symbolic values are strings, never executable code."""
    if isinstance(value, dict): return {str(k): data(v) for k,v in value.items()}
    if isinstance(value, (tuple,list)): return [data(v) for v in value]
    if value is None or type(value) in (str,int,bool,float): return value
    if isinstance(value, Fraction): return str(value)
    if hasattr(value, 'tolist'): return data(value.tolist())
    return str(value)


def numeric_array(values, *, ndim=None, maximum=100000):
    try: import numpy as np
    except ImportError as error: raise ImportError('Install nablamath[scipy]') from error
    a = np.asarray(values, dtype=float)
    if a.size > maximum or (ndim is not None and a.ndim != ndim) or not np.isfinite(a).all():
        raise ValueError('Invalid finite numerical array')
    return a


def domain_conditions(source,variables):
    """Retain syntactic partial-domain guards even if CAS simplification cancels."""
    expression(source,variables)
    tree=ast.parse(str(source),mode='eval');conditions=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):conditions.append(ast.unparse(node.right)+' != 0')
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Pow) and isinstance(node.right,ast.UnaryOp) and isinstance(node.right.op,ast.USub):conditions.append(ast.unparse(node.left)+' != 0')
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in {'log','sqrt'}:
            conditions.append(ast.unparse(node.args[0])+(' > 0 (real branch)' if node.func.id=='log' else ' >= 0 (real branch)'))
    return sorted(set(conditions))
