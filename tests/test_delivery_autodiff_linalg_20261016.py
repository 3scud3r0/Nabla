"""Differentiable dense linear algebra: independent values, gradients and Hessians."""
import math
import random
from fractions import Fraction

import pytest

from nablamath.autodiff import Tensor,SecondOrderTensor,tensor_jacobian,tensor_hessian
from nablamath.autodiff.linalg import (
    solve,inverse,slogdet,logdet,determinant,cholesky,spd_solve,
    gaussian_negative_log_likelihood,solve_diagnostics,stack_vector,
    matrix_from_entries,diagonal_matrix,trace,
)


def assert_matrix_close(actual,expected,**kwargs):
    assert len(actual)==len(expected)
    for left,right in zip(actual,expected):
        assert left==pytest.approx(right,**kwargs)


def test_pivoted_solve_vector_and_matrix_rhs_match_exact_rational_reference():
    from nablamath.math.linear_algebra.matrices import Matrix
    matrix=Tensor([[0.,2.,1.],[1.,-2.,0.],[2.,1.,3.]])
    rhs=Tensor([[1.,2.],[3.,4.],[5.,6.]])
    result=solve(matrix,rhs)
    reference=Matrix(((0,2,1),(1,-2,0),(2,1,3))).inverse()@Matrix(((1,2),(3,4),(5,6)))
    assert_matrix_close(result.tolist(),[[float(value)for value in row]for row in reference.rows])
    vector=solve(matrix,Tensor([1.,3.,5.]))
    assert vector.tolist()==pytest.approx([row[0]for row in result.tolist()])
    info=solve_diagnostics(matrix,rhs,result)
    assert info.max_absolute_residual<1e-13
    assert info.scaled_residual<1e-14
    assert info.condition_inf_estimate>=1
    assert info.rhs_count==2 and info.dimension==3


def test_inverse_and_signed_determinant_cross_multiple_row_swaps():
    matrix=Tensor([[0.,0.,2.],[3.,0.,0.],[0.,4.,0.]])
    result=inverse(matrix)
    assert_matrix_close((matrix@result).tolist(),[[1,0,0],[0,1,0],[0,0,1]])
    assert determinant(matrix).item()==pytest.approx(24)
    sign,value=slogdet(matrix)
    assert sign==1 and value.item()==pytest.approx(math.log(24))
    negative=Tensor([[0.,2.],[3.,0.]])
    assert determinant(negative).item()==pytest.approx(-6)
    assert slogdet(negative)[0]==-1
    assert slogdet(negative)[1].item()==pytest.approx(math.log(6))
    with pytest.raises(ValueError,match='positive determinant'):logdet(negative)


def test_linear_solve_reverse_cotangent_matches_implicit_formula():
    matrix=Tensor([[3.,1.],[2.,4.]],requires_grad=True)
    rhs=Tensor([2.,1.],requires_grad=True)
    output=solve(matrix,rhs)
    cotangent=Tensor([2.,-3.])
    output.backward(cotangent)
    expected_rhs=solve(matrix.detach().T,cotangent).tolist()
    expected_matrix=[[-expected_rhs[i]*output.tolist()[j]for j in range(2)]for i in range(2)]
    assert rhs.grad==pytest.approx(expected_rhs)
    assert_matrix_close(matrix.grad,expected_matrix)


def test_solve_jacobian_wrt_rhs_is_inverse():
    matrix=Tensor([[3.,1.],[2.,4.]])
    _,jacobian=tensor_jacobian(lambda rhs:solve(matrix,rhs),Tensor([2.,1.]))
    assert_matrix_close(jacobian,inverse(matrix).tolist())


def test_logdet_gradient_is_inverse_transpose_and_trace_gradient_is_identity():
    matrix=Tensor([[3.,1.],[2.,4.]],requires_grad=True)
    value=logdet(matrix)
    value.backward()
    assert_matrix_close(matrix.grad,inverse(matrix.detach()).T.tolist())
    trace(matrix).backward()
    assert_matrix_close(matrix.grad,[[1,0],[0,1]])


def test_inverse_gradient_matches_finite_difference_in_all_coordinates():
    point=[[3.,1.],[2.,4.]]
    matrix=Tensor(point,requires_grad=True)
    objective=(inverse(matrix)**2).sum()
    objective.backward()
    epsilon=1e-5
    for i in range(2):
        for j in range(2):
            plus=[list(row)for row in point];minus=[list(row)for row in point]
            plus[i][j]+=epsilon;minus[i][j]-=epsilon
            reference=((inverse(Tensor(plus))**2).sum().item()-(inverse(Tensor(minus))**2).sum().item())/(2*epsilon)
            assert matrix.grad[i][j]==pytest.approx(reference,rel=1e-8,abs=1e-10)


def test_second_order_solve_wrt_rhs_has_closed_form_quadratic_hessian():
    matrix=Tensor([[3.,1.],[2.,4.]])
    value,gradient,hessian=tensor_hessian(lambda rhs:(solve(matrix,rhs)**2).sum(),Tensor([2.,1.]))
    inverse_matrix=inverse(matrix)
    gram=2*(inverse_matrix.T@inverse_matrix)
    assert_matrix_close(hessian,gram.tolist())
    solution=solve(matrix,Tensor([2.,1.]))
    expected_gradient=2*(inverse_matrix.T@solution.reshape(2,1))
    assert gradient==pytest.approx([row[0]for row in expected_gradient.tolist()])
    assert value==pytest.approx((solution**2).sum().item())


def test_second_order_logdet_all_matrix_coordinates_matches_sympy():
    sympy=pytest.importorskip('sympy')
    a,b,c,d=sympy.symbols('a b c d')
    expression=sympy.log(a*d-b*c)
    point=[3.,1.,2.,4.]
    _,gradient,hessian=tensor_hessian(logdet,Tensor([[3.,1.],[2.,4.]]))
    substitutions=dict(zip((a,b,c,d),point))
    expected_gradient=[float(sympy.diff(expression,v).subs(substitutions))for v in (a,b,c,d)]
    expected_hessian=sympy.hessian(expression,(a,b,c,d)).subs(substitutions)
    assert gradient==pytest.approx(expected_gradient)
    assert_matrix_close(hessian,[[float(expected_hessian[i,j])for j in range(4)]for i in range(4)])


def test_spd_cholesky_reconstruction_and_solve_equivalence():
    matrix=Tensor([[4.,2.,0.],[2.,5.,1.],[0.,1.,3.]])
    lower=cholesky(matrix)
    assert_matrix_close((lower@lower.T).tolist(),matrix.tolist())
    assert all(lower.tolist()[i][j]==0 for i in range(3)for j in range(i+1,3))
    rhs=Tensor([1.,2.,3.])
    assert spd_solve(matrix,rhs).tolist()==pytest.approx(solve(matrix,rhs).tolist())


def test_cholesky_symmetric_tangent_derivative_matches_finite_difference():
    point=[[4.,1.],[1.,3.]]
    matrix=Tensor(point,requires_grad=True)
    loss=cholesky(matrix).sum()
    loss.backward()
    epsilon=1e-5
    directions=[[[1.,0.],[0.,0.]],[[0.,1.],[1.,0.]],[[0.,0.],[0.,1.]]]
    for direction in directions:
        plus=[[point[i][j]+epsilon*direction[i][j]for j in range(2)]for i in range(2)]
        minus=[[point[i][j]-epsilon*direction[i][j]for j in range(2)]for i in range(2)]
        numerical=(cholesky(Tensor(plus)).sum().item()-cholesky(Tensor(minus)).sum().item())/(2*epsilon)
        analytic=sum(matrix.grad[i][j]*direction[i][j]for i in range(2)for j in range(2))
        assert analytic==pytest.approx(numerical,rel=1e-8,abs=1e-10)
    assert matrix.grad[0][1]==pytest.approx(matrix.grad[1][0])


def test_second_order_cholesky_diagonal_parameterization_has_analytic_hessian():
    value,gradient,hessian=tensor_hessian(lambda diagonal:cholesky(diagonal_matrix(diagonal)).sum(),Tensor([4.,9.]))
    assert value==pytest.approx(5)
    assert gradient==pytest.approx((.25,1/6))
    assert_matrix_close(hessian,[[-1/32,0],[0,-1/108]])


def test_gaussian_loss_residual_gradient_hessian_are_covariance_inverse():
    covariance=Tensor([[3.,1.],[1.,2.]])
    residual=Tensor([1.,-2.])
    value,gradient,hessian=tensor_hessian(lambda r:gaussian_negative_log_likelihood(covariance,r),residual)
    inv=inverse(covariance)
    assert_matrix_close(hessian,inv.tolist())
    expected=solve(covariance,residual)
    assert gradient==pytest.approx(expected.tolist())
    quadratic=sum(a*b for a,b in zip(residual.tolist(),expected.tolist()))
    assert value==pytest.approx((quadratic+math.log(5)+2*math.log(2*math.pi))/2)
    omitted=gaussian_negative_log_likelihood(covariance,residual,include_constant=False).item()
    assert value-omitted==pytest.approx(math.log(2*math.pi))


def test_gaussian_covariance_gradient_matches_independent_closed_form():
    covariance=Tensor([[3.,1.],[1.,2.]],requires_grad=True)
    residual=Tensor([1.,-2.])
    loss=gaussian_negative_log_likelihood(covariance,residual)
    loss.backward()
    inv=inverse(covariance.detach()).tolist()
    solved=solve(covariance.detach(),residual).tolist()
    expected=[[.5*(inv[i][j]-solved[i]*solved[j])for j in range(2)]for i in range(2)]
    assert_matrix_close(covariance.grad,expected)


def test_stacking_scalar_graphs_preserves_reverse_and_second_derivatives():
    scalar=Tensor(2.,requires_grad=True)
    matrix=matrix_from_entries(((scalar,1),(1,3)))
    vector=stack_vector((scalar,2))
    output=solve(matrix,vector).sum()
    output.backward()
    epsilon=1e-5
    def evaluate(value):return solve(Tensor([[value,1],[1,3]]),Tensor([value,2])).sum().item()
    assert scalar.grad==pytest.approx((evaluate(2+epsilon)-evaluate(2-epsilon))/(2*epsilon))
    _,gradient,hessian=tensor_hessian(lambda x:logdet(matrix_from_entries(((x,1),(1,3)))),Tensor(2.))
    assert gradient==pytest.approx((3/5,))
    assert_matrix_close(hessian,[[-9/25]])


@pytest.mark.parametrize('matrix',[
    [[1.,2.],[2.,4.]],[[0.,0.],[0.,0.]],[[1.,0.],[0.,1e-15]],
])
def test_singular_or_declared_near_singular_matrix_refusal(matrix):
    value=Tensor(matrix)
    for operation in [inverse,slogdet,logdet,determinant]:
        with pytest.raises(ValueError,match='singular|threshold'):operation(value)
    with pytest.raises(ValueError):solve(value,Tensor([1.,2.]))


@pytest.mark.parametrize('matrix',[
    [[1.,2.],[2.,1.]],[[1.,0.],[0.,0.]],[[1.,2.],[0.,3.]],
])
def test_cholesky_rejects_non_spd_or_nonsymmetric_domains(matrix):
    with pytest.raises(ValueError):cholesky(Tensor(matrix))


@pytest.mark.parametrize('threshold',[True,-1,.1,float('nan'),float('inf'),'1e-12'])
def test_pivot_threshold_refuses_ambiguous_nonfinite_or_unbounded_values(threshold):
    with pytest.raises(ValueError):solve(Tensor([[1.]]),Tensor([1.]),pivot_threshold=threshold)


def test_dimension_shape_and_graph_mixing_refusals():
    for matrix in [Tensor([1.,2.]),Tensor([[1.,2.]]),Tensor([[float(i==j)for j in range(9)]for i in range(9)])]:
        with pytest.raises(ValueError):inverse(matrix)
    matrix=Tensor([[2.,0.],[0.,3.]])
    for rhs in [Tensor(1.),Tensor([1.]),Tensor([[1.,2.,3.]])]:
        with pytest.raises(ValueError):solve(matrix,rhs)
    jet=SecondOrderTensor.variable(Tensor([1.,2.]))
    with pytest.raises(ValueError,match='mix'):
        solve(Tensor([[2.,0.],[0.,3.]],requires_grad=True),jet)
    with pytest.raises(ValueError):stack_vector((Tensor([1.]),))
    with pytest.raises(ValueError):stack_vector((True,))
    with pytest.raises(ValueError):matrix_from_entries(((1,2),(3,)))
    with pytest.raises(ValueError):diagonal_matrix(Tensor([[1.]]))
    with pytest.raises(ValueError):gaussian_negative_log_likelihood(matrix,Tensor([1.,2.]),include_constant=1)
    with pytest.raises(ValueError):solve_diagnostics(matrix,Tensor(1.),Tensor(1.))


def test_multiple_rhs_solve_cotangent_and_pivot_branch_have_correct_gradients():
    matrix=Tensor([[0.,2.],[1.,3.]],requires_grad=True)
    rhs=Tensor([[1.,2.],[3.,4.]],requires_grad=True)
    cotangent=Tensor([[2.,-1.],[1.,3.]])
    result=solve(matrix,rhs)
    result.backward(cotangent)
    db=solve(matrix.detach().T,cotangent)
    da=-(db@result.detach().T)
    assert_matrix_close(rhs.grad,db.tolist())
    assert_matrix_close(matrix.grad,da.tolist())


def test_solve_and_determinant_independent_sympy_24_seeded_rational_matrices():
    sympy=pytest.importorskip('sympy')
    rng=random.Random(2026101604)
    for n in (1,2,3,4):
        for _ in range(6):
            # Strict diagonal dominance gives a reproducible nonsingular domain.
            rows=[[Fraction(rng.randint(-2,2),rng.randint(1,4))for _ in range(n)]for _ in range(n)]
            for i in range(n):rows[i][i]+=n+3
            rational=sympy.Matrix([[sympy.Rational(v.numerator,v.denominator)for v in row]for row in rows])
            matrix=Tensor([[float(v)for v in row]for row in rows])
            rhs=Tensor([float(i+1)for i in range(n)])
            expected=rational.inv()*sympy.Matrix(list(range(1,n+1)))
            assert solve(matrix,rhs).tolist()==pytest.approx([float(v)for v in expected],rel=1e-12,abs=1e-13)
            assert determinant(matrix).item()==pytest.approx(float(rational.det()),rel=1e-12)
            assert solve_diagnostics(matrix,rhs,solve(matrix,rhs)).scaled_residual<1e-14


def test_second_order_gaussian_covariance_parameterization_against_sympy():
    sympy=pytest.importorskip('sympy')
    variable=sympy.Symbol('variance',positive=True)
    # Covariance [[variance,1],[1,3]], residual [1,-2].
    matrix=sympy.Matrix([[variable,1],[1,3]])
    residual=sympy.Matrix([1,-2])
    expression=((residual.T*matrix.inv()*residual)[0]+sympy.log(matrix.det()))/2
    loss=lambda x:gaussian_negative_log_likelihood(
        matrix_from_entries(((x,1),(1,3))),Tensor([1.,-2.]),include_constant=False)
    value,gradient,hessian=tensor_hessian(loss,Tensor(2.))
    assert value==pytest.approx(float(expression.subs(variable,2)))
    assert gradient[0]==pytest.approx(float(sympy.diff(expression,variable).subs(variable,2)))
    assert hessian[0][0]==pytest.approx(float(sympy.diff(expression,variable,2).subs(variable,2)))


def test_cholesky_loss_hessian_matches_reverse_gradient_finite_differences():
    loss=lambda diagonal:(cholesky(diagonal_matrix(diagonal))**3).sum()
    point=[4.,9.]
    _,gradient,hessian=tensor_hessian(loss,Tensor(point))
    epsilon=1e-4
    for j in range(2):
        plus,minus=list(point),list(point)
        plus[j]+=epsilon;minus[j]-=epsilon
        _,gp=tensor_jacobian(loss,Tensor(plus))
        _,gm=tensor_jacobian(loss,Tensor(minus))
        for i in range(2):
            assert hessian[i][j]==pytest.approx((gp[0][i]-gm[0][i])/(2*epsilon),rel=1e-8,abs=1e-10)


def test_detached_matrix_stops_covariance_gradient_without_stopping_rhs():
    matrix=Tensor([[3.,1.],[1.,2.]],requires_grad=True)
    rhs=Tensor([1.,2.],requires_grad=True)
    solve(matrix.detach(),rhs).sum().backward()
    assert_matrix_close(matrix.grad,[[0,0],[0,0]])
    assert rhs.grad==pytest.approx(solve(matrix.detach().T,Tensor([1.,1.])).tolist())


def test_implicit_solve_jvp_matches_finite_direction_and_adjoint_duality():
    from nablamath.autodiff.linalg import solve_jvp,solve_vjp
    matrix=Tensor([[3.,1.],[2.,4.]])
    rhs=Tensor([2.,1.])
    da=Tensor([[.1,-.3],[.2,.5]])
    db=Tensor([.4,-.7])
    cotangent=Tensor([2.,-1.])
    value,jvp=solve_jvp(matrix,rhs,da,db)
    other,(vjp_a,vjp_b)=solve_vjp(matrix,rhs,cotangent)
    assert value.tolist()==pytest.approx(other.tolist())
    epsilon=1e-5
    finite=(solve(matrix+epsilon*da,rhs+epsilon*db)-solve(matrix-epsilon*da,rhs-epsilon*db))/(2*epsilon)
    assert jvp.tolist()==pytest.approx(finite.tolist(),rel=1e-8,abs=1e-10)
    lhs=(jvp*cotangent).sum().item()
    rhs=(vjp_a*da).sum().item()+(vjp_b*db).sum().item()
    assert lhs==pytest.approx(rhs)
    assert_matrix_close(matrix.grad,[[0,0],[0,0]])


def test_implicit_multiple_rhs_jvp_vjp_shapes_and_refusals():
    from nablamath.autodiff.linalg import solve_jvp,solve_vjp
    matrix=Tensor([[2.,1.],[1.,3.]])
    rhs=Tensor([[1.,2.],[3.,4.]])
    tangent=Tensor([[.2,.1],[-.3,.7]])
    _,jvp=solve_jvp(matrix,rhs,Tensor([[0.,0.],[0.,0.]]),tangent)
    assert_matrix_close(jvp.tolist(),solve(matrix,tangent).tolist())
    _,(ga,gb)=solve_vjp(matrix,rhs,tangent)
    assert ga.shape==matrix.shape and gb.shape==rhs.shape
    with pytest.raises(ValueError):solve_jvp(matrix,rhs,Tensor([0.,0.]),tangent)
    with pytest.raises(ValueError):solve_vjp(matrix,rhs,Tensor([0.,0.]))
