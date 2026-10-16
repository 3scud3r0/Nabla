"""Differentiable dense linear algebra on Nabla's reference tensor graphs.

LU solve, inverse, determinant and Cholesky are built from scalar differentiable
operations, so reverse Tensor gradients and analytic SecondOrderTensor Hessians
share the same algorithms. Partial pivoting selects by primal values, without
rounding or detaching arithmetic. Floating-point resource/reference backend only;
no GPU, arbitrary precision or formal nonsingularity certificate is claimed.

The public domain is matrices of dimension <=8 with finite entries and pivots
above a caller-declared relative threshold. SPD operations use the symmetric
extension (A+A.T)/2 and require the submitted primal matrix to be symmetric.
Derivatives of Cholesky are therefore meaningful on symmetric perturbations.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt,isfinite
from typing import Callable

from .tensor import Tensor
from .second_order import SecondOrderTensor

Differentiable = Tensor | SecondOrderTensor
MAX_DIMENSION=8


def _primal(value):
    return value.value if isinstance(value,SecondOrderTensor) else value


def _typed(value,label):
    if not isinstance(value,(Tensor,SecondOrderTensor)):
        raise ValueError(label+' must be Tensor or SecondOrderTensor')
    return value


def _matrix(value):
    _typed(value,'Matrix')
    shape=_primal(value).shape
    if len(shape)!=2 or shape[0]!=shape[1] or not 1<=shape[0]<=MAX_DIMENSION:
        raise ValueError('Differentiable matrix must be square, dimension 1..8')
    return shape[0]


def _threshold(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not isfinite(value) or not 0<=value<=.01:
        raise ValueError('Relative pivot threshold must be finite in [0,.01]')
    return float(value)


def _constant(value,like):
    return like._constant(value) if isinstance(like,SecondOrderTensor) else Tensor(value)


def _compatible(left,right):
    _typed(left,'Matrix')
    _typed(right,'Right hand side')
    if isinstance(left,SecondOrderTensor) and isinstance(right,SecondOrderTensor):
        if left.dimension!=right.dimension:
            raise ValueError('Derivative coordinate dimensions differ')
        return left,right
    if isinstance(left,SecondOrderTensor):
        # A Tensor carrying its own reverse graph cannot be silently detached.
        if right.requires_grad:
            raise ValueError('Do not mix reverse Tensor graph and SecondOrderTensor graph')
        return left,left._constant(right)
    if isinstance(right,SecondOrderTensor):
        if left.requires_grad:
            raise ValueError('Do not mix reverse Tensor graph and SecondOrderTensor graph')
        return right._constant(left),right
    return left,right


def _scalar_tensor(value,index):
    if not 0<=index<value.size:
        raise ValueError('Scalar extraction index outside tensor')
    parents=[]
    if value.requires_grad:
        def backward(gradient,*,index=index,size=value.size):
            result=[0.0]*size
            result[index]=gradient[0]
            return result
        parents.append((value,backward))
    return Tensor._from_flat((value._flat[index],),(),bool(parents),parents,'linalg_extract')


def _scalar(value,index):
    if isinstance(value,SecondOrderTensor):
        return value._map(lambda tensor:_scalar_tensor(tensor,index))
    return _scalar_tensor(value,index)


def _stack_tensors(values,shape):
    if any(not isinstance(value,Tensor) or value.shape!=() for value in values):
        raise ValueError('Scalar tensors required for differentiable stacking')
    parents=[]
    for index,value in enumerate(values):
        if value.requires_grad:
            parents.append((value,lambda gradient,index=index:[gradient[index]]))
    return Tensor._from_flat(tuple(value.item() for value in values),shape,bool(parents),parents,'linalg_stack')


def _stack(values,shape):
    if not values:
        raise ValueError('Nonempty differentiable stack required')
    if isinstance(values[0],SecondOrderTensor):
        dimension=values[0].dimension
        if any(not isinstance(value,SecondOrderTensor) or value.dimension!=dimension for value in values):
            raise ValueError('Stack derivative dimensions differ')
        return SecondOrderTensor(_stack_tensors([value.value for value in values],shape),
            tuple(_stack_tensors([value.gradient[i] for value in values],shape) for i in range(dimension)),
            tuple(tuple(_stack_tensors([value.curvature[i][j] for value in values],shape)
                        for j in range(dimension)) for i in range(dimension)))
    return _stack_tensors(values,shape)


def stack_vector(entries):
    """Build a length<=8 vector without discarding scalar derivative graphs."""
    if not isinstance(entries,(tuple,list)) or not 1<=len(entries)<=8:
        raise ValueError('Finite sequence of 1..8 scalar entries required')
    prototype=next((value for value in entries if isinstance(value,SecondOrderTensor)),None)
    values=[]
    for value in entries:
        if isinstance(value,SecondOrderTensor):
            if value.dimension!=prototype.dimension:
                raise ValueError('Derivative coordinate dimensions differ')
        elif isinstance(value,Tensor):
            if prototype is not None:
                if value.requires_grad:
                    raise ValueError('Do not mix reverse and second-order derivative graphs')
                value=prototype._constant(value)
        else:
            if isinstance(value,bool) or not isinstance(value,(int,float)):
                raise ValueError('Scalar tensor or finite numeric entry required')
            value=prototype._constant(value) if prototype is not None else Tensor(value)
        if _primal(value).shape!=():
            raise ValueError('Stack entries must be scalars')
        values.append(value)
    return _stack(values,(len(values),))


def matrix_from_entries(rows):
    """Build a bounded rectangular matrix from scalar differentiable entries."""
    if not isinstance(rows,(tuple,list)) or not 1<=len(rows)<=8:
        raise ValueError('Finite matrix rows required')
    if any(not isinstance(row,(tuple,list)) or not 1<=len(row)<=8 for row in rows):
        raise ValueError('Each matrix row requires 1..8 scalar entries')
    width=len(rows[0])
    if any(len(row)!=width for row in rows):
        raise ValueError('Matrix entries must be rectangular')
    flattened=[value for row in rows for value in row]
    # Reuse scalar coercion with a bounded collection; vector public limit is8.
    prototype=next((value for value in flattened if isinstance(value,SecondOrderTensor)),None)
    converted=[]
    for row in rows:
        if prototype is None:
            vector=stack_vector(row)
        else:
            converted_row=[]
            for value in row:
                if isinstance(value,Tensor) and value.requires_grad:
                    raise ValueError('Do not mix reverse and second-order derivative graphs')
                if not isinstance(value,SecondOrderTensor):
                    if isinstance(value,bool) or not isinstance(value,(int,float,Tensor)):
                        raise ValueError('Scalar tensor or finite numeric entry required')
                    value=prototype._constant(value)
                converted_row.append(value)
            vector=stack_vector(converted_row)
        converted.extend(_scalar(vector,index) for index in range(width))
    return _stack(converted,(len(rows),width))


def diagonal_matrix(vector):
    _typed(vector,'Diagonal vector')
    if len(_primal(vector).shape)!=1 or not 1<=_primal(vector).size<=8:
        raise ValueError('Diagonal vector dimension must be in [1,8]')
    n=_primal(vector).size
    return matrix_from_entries(tuple(tuple(_scalar(vector,i) if i==j else 0 for j in range(n)) for i in range(n)))


def trace(matrix):
    n=_matrix(matrix)
    result=_constant(0,matrix)
    for i in range(n):
        result=result+_scalar(matrix,i*n+i)
    return result


def _sqrt(value):
    primal=_primal(value)
    if primal.shape!=() or primal.item()<=0:
        raise ValueError('Differentiable square root requires positive scalar')
    root=primal._unary(sqrt,lambda x:.5/sqrt(x),'sqrt')
    if isinstance(value,SecondOrderTensor):
        return value._unary(root,.5/root,-.25/(primal*root))
    return root


def _rows(matrix):
    n=_matrix(matrix)
    return [[_scalar(matrix,i*n+j) for j in range(n)] for i in range(n)]


def _scale_of(matrix):
    value=_primal(matrix)
    n=value.shape[0]
    return max(sum(abs(value._flat[i*n+j]) for j in range(n)) for i in range(n))


def _lu(matrix,*,pivot_threshold):
    n=_matrix(matrix)
    threshold=_threshold(pivot_threshold)*_scale_of(matrix)
    rows=_rows(matrix)
    swaps=[]
    for column in range(n):
        pivot=max(range(column,n),key=lambda row:abs(_primal(rows[row][column]).item()))
        if abs(_primal(rows[pivot][column]).item())<=threshold:
            raise ValueError('Matrix is singular or pivot falls below declared threshold')
        swaps.append(pivot)
        if pivot!=column:
            rows[column],rows[pivot]=rows[pivot],rows[column]
        for row in range(column+1,n):
            rows[row][column]=rows[row][column]/rows[column][column]
            for j in range(column+1,n):
                rows[row][j]=rows[row][j]-rows[row][column]*rows[column][j]
    return rows,tuple(swaps)


def solve(matrix,rhs,*,pivot_threshold=1e-12):
    """Solve A@X=B with differentiable pivoted LU; B is (n,) or (n,k).

    Derivatives propagate through A and B, including broadcasting already used
    to construct those tensors. The algorithm rejects rank-deficient matrices;
    least squares and pseudoinverses require different contracts.
    """
    matrix,rhs=_compatible(matrix,rhs)
    n=_matrix(matrix)
    shape=_primal(rhs).shape
    if len(shape) not in (1,2) or shape[0]!=n or (len(shape)==2 and not 1<=shape[1]<=8):
        raise ValueError('Right hand side must have shape (n,) or (n,k), k<=8')
    width=1 if len(shape)==1 else shape[1]
    lu,swaps=_lu(matrix,pivot_threshold=pivot_threshold)
    rows=[[_scalar(rhs,i*width+j) for j in range(width)] for i in range(n)]
    for column,pivot in enumerate(swaps):
        if pivot!=column:
            rows[column],rows[pivot]=rows[pivot],rows[column]
    for row in range(n):
        for column in range(row):
            for j in range(width):
                rows[row][j]=rows[row][j]-lu[row][column]*rows[column][j]
    for row in reversed(range(n)):
        for column in range(row+1,n):
            for j in range(width):
                rows[row][j]=rows[row][j]-lu[row][column]*rows[column][j]
        for j in range(width):
            rows[row][j]=rows[row][j]/lu[row][row]
    return _stack([value for row in rows for value in row],shape)


def solve_jvp(matrix,rhs,matrix_tangent,rhs_tangent,*,pivot_threshold=1e-12):
    """Implicit directional derivative dX=A^-1(dB-dA@X), without finite differences.

    This first-order interface accepts ordinary Tensor inputs. It never invokes
    backward or mutates stored gradients; its returned tensors can retain graphs.
    """
    if any(not isinstance(value,Tensor) for value in (matrix,rhs,matrix_tangent,rhs_tangent)):
        raise ValueError('Implicit solve JVP requires Tensor inputs')
    n=_matrix(matrix)
    if matrix_tangent.shape!=matrix.shape or rhs_tangent.shape!=rhs.shape:
        raise ValueError('Solve tangent shapes differ from primal shapes')
    solution=solve(matrix,rhs,pivot_threshold=pivot_threshold)
    vector=solution.ndim==1
    column_solution=solution.reshape(n,1) if vector else solution
    correction=matrix_tangent@column_solution
    if vector:
        correction=correction.reshape(n)
    tangent=solve(matrix,rhs_tangent-correction,pivot_threshold=pivot_threshold)
    return solution,tangent


def solve_vjp(matrix,rhs,cotangent,*,pivot_threshold=1e-12):
    """Implicit cotangents dB=A^-T G and dA=-dB X.T for vector/multiple RHS.

    Returns (solution,(matrix_cotangent,rhs_cotangent)). No leaf gradients are
    overwritten, so callers can combine this result with their own accumulators.
    """
    if any(not isinstance(value,Tensor) for value in (matrix,rhs,cotangent)):
        raise ValueError('Implicit solve VJP requires Tensor inputs')
    solution=solve(matrix,rhs,pivot_threshold=pivot_threshold)
    if cotangent.shape!=solution.shape:
        raise ValueError('Solve cotangent shape differs from solution')
    rhs_cotangent=solve(matrix.T,cotangent,pivot_threshold=pivot_threshold)
    n=_matrix(matrix)
    if solution.ndim==1:
        matrix_cotangent=-(rhs_cotangent.reshape(n,1)@solution.reshape(1,n))
    else:
        matrix_cotangent=-(rhs_cotangent@solution.T)
    return solution,(matrix_cotangent,rhs_cotangent)


def inverse(matrix,*,pivot_threshold=1e-12):
    """Differentiable inverse via solve(A,I), with the same nonsingular domain."""
    n=_matrix(matrix)
    unit=_constant([[float(i==j) for j in range(n)] for i in range(n)],matrix)
    return solve(matrix,unit,pivot_threshold=pivot_threshold)


def slogdet(matrix,*,pivot_threshold=1e-12):
    """Return discrete determinant sign and differentiable log(abs(det(A)))."""
    lu,swaps=_lu(matrix,pivot_threshold=pivot_threshold)
    sign=(-1)**sum(i!=pivot for i,pivot in enumerate(swaps))
    result=_constant(0,matrix)
    for i,row in enumerate(lu):
        diagonal=row[i]
        local_sign=1 if _primal(diagonal).item()>0 else -1
        sign*=local_sign
        result=result+(diagonal*local_sign).log()
    return sign,result


def logdet(matrix,*,pivot_threshold=1e-12):
    """Real log determinant on the open domain det(A)>0."""
    sign,result=slogdet(matrix,pivot_threshold=pivot_threshold)
    if sign<0:
        raise ValueError('Real log determinant requires positive determinant')
    return result


def determinant(matrix,*,pivot_threshold=1e-12):
    """Determinant on a declared nonsingular domain, retaining its signed value."""
    lu,swaps=_lu(matrix,pivot_threshold=pivot_threshold)
    result=_constant((-1)**sum(i!=pivot for i,pivot in enumerate(swaps)),matrix)
    for i,row in enumerate(lu):
        result=result*row[i]
    return result


def cholesky(matrix,*,pivot_threshold=1e-12,symmetry_tolerance=1e-12):
    """Differentiable lower Cholesky factor of an explicitly symmetric SPD matrix.

    The graph uses (A+A.T)/2. This gives a symmetric cotangent convention; the
    caller must use symmetric perturbations when interpreting derivatives.
    A positive pivot is a numerical domain check, not a proof of conditioning.
    """
    n=_matrix(matrix)
    relative=_threshold(pivot_threshold)
    tolerance=_threshold(symmetry_tolerance)
    scale=_scale_of(matrix)
    original=_primal(matrix)
    for i in range(n):
        for j in range(i):
            if abs(original._flat[i*n+j]-original._flat[j*n+i])>tolerance*scale:
                raise ValueError('Cholesky requires symmetric primal input')
    rows=_rows(matrix)
    for i in range(n):
        for j in range(i):
            symmetric=(rows[i][j]+rows[j][i])/2
            rows[i][j]=rows[j][i]=symmetric
    lower=[[_constant(0,matrix) for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(i+1):
            value=rows[i][j]
            for k in range(j):
                value=value-lower[i][k]*lower[j][k]
            if i==j:
                if _primal(value).item()<=relative*scale:
                    raise ValueError('Matrix is not positive definite or Cholesky pivot is below threshold')
                lower[i][j]=_sqrt(value)
            else:
                lower[i][j]=value/lower[j][j]
    return _stack([value for row in lower for value in row],(n,n))


def spd_solve(matrix,rhs,*,pivot_threshold=1e-12,symmetry_tolerance=1e-12):
    """Solve SPD A@X=B using its differentiable Cholesky factors."""
    matrix,rhs=_compatible(matrix,rhs)
    lower=cholesky(matrix,pivot_threshold=pivot_threshold,symmetry_tolerance=symmetry_tolerance)
    # LU handles triangular factors while retaining the full derivative graph.
    first=solve(lower,rhs,pivot_threshold=pivot_threshold)
    return solve(lower.T,first,pivot_threshold=pivot_threshold)


def gaussian_negative_log_likelihood(covariance,residual,*,include_constant=True,pivot_threshold=1e-12):
    """Single zero-mean Gaussian loss, explicit SPD covariance and vector residual.

    A model likelihood calculation does not establish calibration or empirical
    Gaussianity. Both covariance and residual may depend on differentiable inputs.
    """
    covariance,residual=_compatible(covariance,residual)
    n=_matrix(covariance)
    if _primal(residual).shape!=(n,) or type(include_constant) is not bool:
        raise ValueError('Gaussian loss requires residual vector and bool constant flag')
    lower=cholesky(covariance,pivot_threshold=pivot_threshold)
    solution=solve(lower,residual,pivot_threshold=pivot_threshold)
    log_variance=_constant(0,covariance)
    for i in range(n):
        log_variance=log_variance+2*_scalar(lower,i*n+i).log()
    from math import log,pi
    constant=n*log(2*pi) if include_constant else 0
    return ((solution*solution).sum()+log_variance+constant)/2


@dataclass(frozen=True)
class SolveDiagnostics:
    dimension: int
    rhs_count: int
    max_absolute_residual: float
    scaled_residual: float
    condition_inf_estimate: float
    scope: str = 'Floating residual and inverse-norm estimate; not a certified forward-error bound'


def solve_diagnostics(matrix,rhs,solution,*,pivot_threshold=1e-12):
    """Primal-only diagnostics, deliberately outside the derivative graph."""
    n=_matrix(matrix)
    _typed(rhs,'Right hand side')
    _typed(solution,'Solution')
    a,b,x=(_primal(value) for value in (matrix,rhs,solution))
    if not isinstance(b,Tensor) or not isinstance(x,Tensor) or b.shape!=x.shape or len(b.shape) not in (1,2) or b.shape[0]!=n:
        raise ValueError('Diagnostic solution and rhs shapes differ')
    width=1 if len(b.shape)==1 else b.shape[1]
    residual=max(abs(sum(a._flat[i*n+k]*x._flat[k*width+j] for k in range(n))-b._flat[i*width+j])
                 for i in range(n) for j in range(width))
    a_norm=_scale_of(a)
    x_norm=max(sum(abs(x._flat[i*width+j]) for j in range(width)) for i in range(n))
    b_norm=max(sum(abs(b._flat[i*width+j]) for j in range(width)) for i in range(n))
    denominator=a_norm*x_norm+b_norm
    scaled=residual/denominator if denominator else residual
    inv=inverse(a,pivot_threshold=pivot_threshold)
    condition=a_norm*_scale_of(inv)
    if not all(isfinite(v) for v in (residual,scaled,condition)):
        raise ValueError('Diagnostics overflowed the finite numerical domain')
    return SolveDiagnostics(n,width,residual,scaled,condition)


__all__=['solve','inverse','slogdet','logdet','determinant','cholesky','spd_solve',
         'gaussian_negative_log_likelihood','SolveDiagnostics','solve_diagnostics',
         'stack_vector','matrix_from_entries','diagonal_matrix','trace','solve_jvp','solve_vjp']
