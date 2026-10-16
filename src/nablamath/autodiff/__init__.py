from .api import Dual, Var, cos, exp, grad, hessian, jacobian, jvp, log, sin, tanh, value_and_grad, vjp
from .tensor import NamedTensor, Tensor, tensor_jacobian, tensor_vjp

__all__ = [
    "Dual", "Var", "jvp", "value_and_grad", "grad", "vjp", "jacobian",
    "hessian", "exp", "log", "sin", "cos", "tanh", "Tensor",
    "NamedTensor", "tensor_vjp", "tensor_jacobian",
]

from .second_order import SecondOrderTensor, tensor_hessian
__all__ += ["SecondOrderTensor", "tensor_hessian"]

from .linalg import (solve as tensor_solve, inverse as tensor_inverse,
                     logdet as tensor_logdet, slogdet as tensor_slogdet,
                     cholesky as tensor_cholesky)
__all__ += ["tensor_solve", "tensor_inverse", "tensor_logdet", "tensor_slogdet", "tensor_cholesky"]
