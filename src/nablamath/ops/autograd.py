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
