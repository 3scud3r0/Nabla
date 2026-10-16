"""Reference contracts for bounded tensor second derivatives and executable IR."""
import copy
from fractions import Fraction
from math import cos, exp, log, sin, tanh

import pytest

from nablamath.autodiff import Tensor, SecondOrderTensor, tensor_hessian
from nablamath.compiler import lower_expr, compile_program
from nablamath.compiler.ir import Program, Instruction
from nablamath.expression import parse_expr, evaluate


def test_second_order_polynomial_at_zero_and_mixed_partials():
    value, gradient, hessian = tensor_hessian(
        lambda x: ((x * x).sum() + x.sum() ** 3), Tensor([0., 2.]))
    assert value == 12
    assert gradient == (12., 16.)
    assert hessian == ((14., 12.), (12., 14.))


def test_broadcast_loss_has_cross_coordinate_hessian():
    weights = Tensor([[1., 2.], [3., 4.], [5., 6.]])
    _, gradient, hessian = tensor_hessian(
        lambda x: ((x + weights) ** 2).sum(), Tensor([2., 3.]))
    assert gradient == (30., 42.)
    assert hessian == ((6., 0.), (0., 6.))


def test_matrix_loss_hessian_matches_closed_form():
    matrix = Tensor([[1., 2.], [3., 4.]])
    _, gradient, hessian = tensor_hessian(
        lambda x: ((matrix @ x.reshape(2, 1)) ** 2).sum(), Tensor([1., 2.]))
    assert gradient == (76., 108.)
    assert hessian == ((20., 28.), (28., 40.))


@pytest.mark.parametrize("name", ["exp", "log", "sin", "cos", "tanh"])
def test_unary_hessian_against_independent_analytic_functions(name):
    point = .7
    value, gradient, hessian = tensor_hessian(
        lambda x: getattr(x, name)().sum(), Tensor([point]))
    t = tanh(point)
    references = {
        "exp": (exp(point), exp(point), exp(point)),
        "log": (log(point), 1 / point, -1 / point ** 2),
        "sin": (sin(point), cos(point), -sin(point)),
        "cos": (cos(point), -sin(point), -cos(point)),
        "tanh": (t, 1 - t*t, -2*t*(1-t*t)),
    }
    assert (value, gradient[0], hessian[0][0]) == pytest.approx(references[name])


def test_detach_blocks_both_derivative_orders():
    _, gradient, hessian = tensor_hessian(
        lambda x: (x * x.detach()).sum(), Tensor([2., 3.]))
    assert gradient == (2., 3.)
    assert hessian == ((0., 0.), (0., 0.))


def test_reduction_transpose_reshape_and_negative_power():
    value, gradient, hessian = tensor_hessian(
        lambda x: ((x.reshape(2, 1).T / 2).mean() + (x ** -1).sum()), Tensor([2., 4.]))
    assert value == pytest.approx(2.25)
    assert gradient == pytest.approx((0., .1875))
    assert hessian[0] == pytest.approx((.25, 0.))
    assert hessian[1] == pytest.approx((0., .03125))


def test_hessian_rejects_nonscalar_output_and_limits():
    with pytest.raises(ValueError, match="scalar"):
        tensor_hessian(lambda x: x*x, Tensor([1., 2.]))
    with pytest.raises(ValueError, match="1..64"):
        SecondOrderTensor.variable(Tensor([1.] * 65))
    with pytest.raises(ValueError, match="dimensions"):
        SecondOrderTensor.variable(Tensor([1.])) + SecondOrderTensor.variable(Tensor([1., 2.]))
    with pytest.raises(ZeroDivisionError):
        tensor_hessian(lambda x: (1/x).sum(), Tensor([0.]))


def test_ir_serialization_preserves_exact_execution_and_hash():
    expression = parse_expr("(x+1/3)*(x+1/3)/(y**2)")
    program = lower_expr(expression)
    restored = Program.from_data(program.to_data())
    assert restored.content_id == program.content_id
    bindings = {"x": Fraction(-2, 7), "y": Fraction(3, 5)}
    assert compile_program(restored)(bindings) == evaluate(expression, bindings)


@pytest.mark.parametrize("mutation", ["order", "bool_id", "fraction", "power", "schema", "extra"])
def test_ir_rejects_forged_manifests(mutation):
    manifest = copy.deepcopy(lower_expr(parse_expr("x**2+1")).to_data())
    if mutation == "order":
        manifest["instructions"][:2] = reversed(manifest["instructions"][:2])
    elif mutation == "bool_id":
        manifest["instructions"][0]["id"] = False
    elif mutation == "fraction":
        manifest["instructions"][1]["value"] = {"numerator": 4, "denominator": 2}
    elif mutation == "power":
        manifest["instructions"][1]["value"] = {"numerator": 1, "denominator": 2}
    elif mutation == "schema":
        manifest["schema_version"] = True
    else:
        manifest["code"] = "arbitrary input"
    with pytest.raises(ValueError):
        Program.from_data(manifest)


def test_variable_exponents_rejected_instead_of_silently_truncated():
    with pytest.raises(ValueError):
        lower_expr(parse_expr("x**y"))


def test_second_order_hessian_matches_gradient_finite_differences():
    from nablamath.autodiff import tensor_jacobian
    point = [0.4, -0.8]
    function = lambda x: ((x*x).sum() + x.sum().exp())
    _, gradient, hessian = tensor_hessian(function, Tensor(point))
    epsilon = 1e-5
    for column in range(2):
        plus, minus = list(point), list(point)
        plus[column] += epsilon
        minus[column] -= epsilon
        _, gp = tensor_jacobian(function, Tensor(plus))
        _, gm = tensor_jacobian(function, Tensor(minus))
        for row in range(2):
            assert hessian[row][column] == pytest.approx(
                (gp[0][row]-gm[0][row])/(2*epsilon), rel=1e-8, abs=1e-9)


def test_kernel_only_contracts_compile_without_additional_axioms():
    import os
    from pathlib import Path
    import shutil
    import subprocess
    executable = os.environ.get("NABLA_LEAN") or shutil.which("lean")
    if executable is None:
        pytest.skip("Lean toolchain is optional")
    source = Path(__file__).resolve().parents[1] / "lean/Nabla/KernelContracts.lean"
    result = subprocess.run([executable, str(source)], text=True,
                            capture_output=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("does not depend on any axioms") == 6
    assert "depends on axioms:" not in result.stdout


def test_independent_rule_audit_finds_domain_and_value_counterexamples():
    from nablamath.symbolic.patterns import RewriteRule, RuleCondition, parse_pattern
    from nablamath.symbolic.rule_audit import audit_rule
    unsafe = RewriteRule("unsafe", parse_pattern("?a/?a"), parse_pattern("1"))
    result = audit_rule(unsafe)
    assert result.failure == "definedness mismatch"
    assert result.counterexample == (("a", "0"),)
    safe = RewriteRule("guarded", unsafe.lhs, unsafe.rhs, (RuleCondition("nonzero", "a"),))
    result = audit_rule(safe)
    assert result.passed and result.excluded == 1
    assert result.to_data()["formal_proof"] is False
    false = RewriteRule("false", parse_pattern("?a+1"), parse_pattern("?a+2"))
    assert audit_rule(false).failure == "value mismatch"


def test_every_builtin_rewrite_rule_survives_exact_scalar_audit():
    from nablamath.symbolic.rules import DEFAULT_EGRAPH_RULES
    from nablamath.symbolic.rule_audit import audit_rule
    for rule in DEFAULT_EGRAPH_RULES:
        result = audit_rule(rule)
        assert result.passed, result.to_data()


def test_rule_audit_rejects_unbounded_and_inexact_grids():
    from nablamath.symbolic.rules import DEFAULT_EGRAPH_RULES
    from nablamath.symbolic.rule_audit import audit_rule
    for values in [[], [0.1], [True], [2**129]]:
        with pytest.raises(ValueError):
            audit_rule(DEFAULT_EGRAPH_RULES[0], values)
    with pytest.raises(ValueError, match="budget"):
        audit_rule(DEFAULT_EGRAPH_RULES[0], max_cases=1)


@pytest.mark.parametrize('opcode',[[],{},None,False,1])
def test_ir_malformed_opcode_fails_with_validation_error(opcode):
    manifest=lower_expr(parse_expr('x+1')).to_data()
    manifest['instructions'][0]['op']=opcode
    with pytest.raises(ValueError):
        Program.from_data(manifest)


@pytest.mark.parametrize('operation',[
    lambda x:x.reshape(2.9), lambda x:x.reshape(True,2),
    lambda x:x.sum(True),lambda x:x.sum(0,keepdims=1),
    lambda x:x.mean(4),lambda x:x.mean(-2),lambda x:x.mean(0.5),
    lambda x:x.transpose((False,)),
])
def test_tensor_shape_and_axis_metadata_are_strict(operation):
    with pytest.raises(ValueError):
        operation(Tensor([1.,2.]))


def test_hessian_preserves_input_coordinate_dimension():
    with pytest.raises(ValueError,match='dimension'):
        tensor_hessian(lambda x:SecondOrderTensor.variable(Tensor(2.)),Tensor([1.,2.]))


@pytest.mark.parametrize('power',[1,2,3,4])
def test_hessian_polynomial_chain_rule_at_zero(power):
    _,gradient,hessian=tensor_hessian(lambda x:(x**power).sum(),Tensor([0.]))
    assert gradient==(float(power==1),)
    assert hessian==((2. if power==2 else 0.,),)
