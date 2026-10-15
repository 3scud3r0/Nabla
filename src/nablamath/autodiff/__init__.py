from .api import Dual, Var, cos, exp, grad, hessian, jacobian, jvp, log, sin, tanh, value_and_grad, vjp
from .tensor import NamedTensor, Tensor, tensor_jacobian, tensor_vjp

__all__ = [
    "Dual", "Var", "jvp", "value_and_grad", "grad", "vjp", "jacobian",
    "hessian", "exp", "log", "sin", "cos", "tanh", "Tensor",
    "NamedTensor", "tensor_vjp", "tensor_jacobian",
]

from .second_order import SecondOrderTensor, tensor_hessian
__all__ += ["SecondOrderTensor", "tensor_hessian"]
