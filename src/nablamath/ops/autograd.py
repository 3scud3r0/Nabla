"""Dynamic graph differentiation; never evaluates Python source from requests."""
from ..autodiff.api import Dual, Var, grad, value_and_grad, jvp, vjp, jacobian, hessian
from ..autodiff.tensor import Tensor, tensor_vjp, tensor_jacobian


def differentiate_graph(nodes, inputs, output):
    """Evaluate a closed scalar DAG and differentiate its scalar output."""
    if (not isinstance(nodes, list) or not 1 <= len(nodes) <= 256
            or not isinstance(inputs, dict) or not 1 <= len(inputs) <= 32
            or type(output) is not int or not 0 <= output < len(nodes)):
        raise ValueError('Invalid graph or graph budget')
    leaves = {name: Var(value) for name, value in sorted(inputs.items())}
    values = []
    binary = {'add': lambda a,b: a+b, 'subtract': lambda a,b: a-b,
              'multiply': lambda a,b: a*b, 'divide': lambda a,b: a/b}
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise ValueError('Graph nodes must be objects')
        op = node.get('op')
        if op == 'input' and set(node) == {'op', 'name'}:
            if node['name'] not in leaves:
                raise ValueError('Unknown graph input')
            value = leaves[node['name']]
        elif op == 'constant' and set(node) == {'op', 'value'}:
            value = Var(node['value'], requires_grad=False)
        elif op in {*binary, 'exp', 'log', 'sin', 'cos', 'tanh', 'negate'} and set(node) == {'op', 'args'}:
            args = node['args']
            count = 2 if op in binary else 1
            if not isinstance(args, list) or len(args) != count or any(type(i) is not int or not 0 <= i < index for i in args):
                raise ValueError('Graph must be acyclic with preceding references')
            operands = [values[i] for i in args]
            value = (binary[op](*operands) if op in binary else
                     -operands[0] if op == 'negate' else getattr(operands[0], op)())
        else:
            raise ValueError('Unknown node operation or fields')
        values.append(value)
    values[output].backward()
    return {'value': values[output].value, 'gradient': {k: v.grad for k,v in leaves.items()},
            'arithmetic': 'floating_point_reverse_mode', 'nodes': len(nodes)}


__all__ = ['Dual', 'Var', 'Tensor', 'grad', 'value_and_grad', 'jvp', 'vjp', 'jacobian',
           'hessian', 'tensor_vjp', 'tensor_jacobian', 'differentiate_graph']


def expression_derivatives(source,variables,point,order=2):
    """Exact expression jets used to specify and audit AD primitive rules."""
    from itertools import product
    from ..math._structured import expression,sympy
    sp=sympy();value,symbols=expression(source,variables)
    if len(point)!=len(symbols) or type(order) is not int or not 0<=order<=4 or len(symbols)>8:raise ValueError('Derivative jet budget exceeded')
    substitution={s:sp.Rational(str(v)) for s,v in zip(symbols,point)};derivatives={}
    for powers in product(range(order+1),repeat=len(symbols)):
        if sum(powers)>order:continue
        derivative=value
        for s,n in zip(symbols,powers):derivative=sp.diff(derivative,s,n)
        result=sp.simplify(derivative.subs(substitution))
        if result.has(sp.zoo,sp.nan,sp.oo,-sp.oo):raise ValueError('Derivative outside expression domain')
        derivatives[','.join(map(str,powers))]=str(result)
    return {'derivatives':derivatives,'arithmetic':'symbolic_exact','scope':'Expression jets, distinct from tape-based reverse-mode execution.'}


def implicit_derivative(equations,parameters,unknowns,point):
    from ..math._structured import expression,sympy,data
    sp=sympy();names=list(parameters)+list(unknowns)
    if len(set(names))!=len(names) or not 1<=len(unknowns)<=8 or len(equations)!=len(unknowns) or len(point)!=len(names):raise ValueError('Invalid implicit system dimensions')
    values=[expression(v,names)[0] for v in equations];symbols=tuple(map(sp.Symbol,names));sub={s:sp.Rational(str(v)) for s,v in zip(symbols,point)}
    residual=sp.Matrix(values).subs(sub)
    if any(v!=0 for v in residual):raise ValueError('Point does not satisfy the implicit equations')
    fx=sp.Matrix(values).jacobian(symbols[:len(parameters)]).subs(sub);fy=sp.Matrix(values).jacobian(symbols[len(parameters):]).subs(sub)
    if fy.det()==0:raise ValueError('Implicit Jacobian is singular')
    return {'jacobian':data(-fy.inv()*fx),'regularity_hypothesis':'Equations C^1 near the point; exact nonsingular unknown Jacobian checked.'}


def linear_solve_vjp(matrix,rhs,cotangent):
    import numpy as np
    from ..math._structured import numeric_array
    a,b,g=(numeric_array(v,ndim=n,maximum=4096) for v,n in ((matrix,2),(rhs,1),(cotangent,1)))
    if a.shape!=(len(b),len(b)) or len(g)!=len(b):raise ValueError('Linear-solve VJP dimensions differ')
    x=np.linalg.solve(a,b);adjoint=np.linalg.solve(a.T,g)
    return {'solution':x.tolist(),'rhs_cotangent':adjoint.tolist(),'matrix_cotangent':(-np.outer(adjoint,x)).tolist(),
            'residual':float(np.linalg.norm(a@x-b)),'scope':'Real nonsingular linear solve VJP, floating-point arithmetic.'}
