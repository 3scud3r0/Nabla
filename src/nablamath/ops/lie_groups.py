"""SO(3) exponential, quaternion and left Jacobian from rotation vectors (22)."""
import math
from ._area_utils import calculate as _calculate


def lie_groups(rotation_vector):
    if not isinstance(rotation_vector,list) or len(rotation_vector)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>10000 for v in rotation_vector):
        raise ValueError('Require a bounded finite rotation vector in radians')
    x,y,z = rotation_vector;theta = math.hypot(x,y,z);t2 = theta*theta
    skew = [[0.,-z,y],[z,0.,-x],[-y,x,0.]]
    squared = [[sum(skew[i][k]*skew[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    if theta<1e-4:
        a = 1-t2/6+t2*t2/120;b = .5-t2/24+t2*t2/720;c = 1/6-t2/120+t2*t2/5040
    else:
        a = math.sin(theta)/theta;b = (1-math.cos(theta))/t2;c = (theta-math.sin(theta))/(t2*theta)
    rotation = [[float(i==j)+a*skew[i][j]+b*squared[i][j] for j in range(3)] for i in range(3)]
    jacobian = [[float(i==j)+b*skew[i][j]+c*squared[i][j] for j in range(3)] for i in range(3)]
    scale = math.sin(theta/2)/theta if theta else .5
    residual = max(abs(sum(rotation[k][i]*rotation[k][j] for k in range(3))-int(i==j)) for i in range(3) for j in range(3))
    return {'rotation':rotation,'quaternion_wxyz':[math.cos(theta/2),x*scale,y*scale,z*scale],
            'left_jacobian':jacobian,'orthogonality_residual':residual,
            'scope':'Numerical SO(3) exponential in radians; no arbitrary Lie group classification.'}


def calculate(**arguments):return _calculate('lie_groups',**arguments)


def matrix_group(kind,matrix,*,operation='exp',direction=None,tolerance=1e-9):
    import numpy as np
    from scipy.linalg import expm,logm,expm_frechet
    from ..math._structured import numeric_array
    from .spectral import _complex
    if kind=='SU':
        if not isinstance(matrix,list) or not 1<=len(matrix)<=16 or any(not isinstance(row,list) or len(row)!=len(matrix) for row in matrix):raise ValueError('Square complex SU matrix required')
        a=np.array([[_complex(v) for v in row] for row in matrix],dtype=complex)
    else:a=numeric_array(matrix,ndim=2,maximum=256)
    if a.shape[0]!=a.shape[1] or not 1<=a.shape[0]<=16 or kind not in {'SO','SL','SU','SE3'} or not 0<tolerance<=1e-3:raise ValueError('Invalid matrix-group profile')
    n=len(a)
    if operation=='exp':
        if kind in {'SO','SU'} and np.max(np.abs(a+a.conj().T))>tolerance:raise ValueError('Skew-Hermitian SU / skew-symmetric SO generator required')
        if kind in {'SL','SU'} and abs(np.trace(a))>tolerance:raise ValueError('Traceless Lie-algebra input required')
        if kind=='SE3' and (n!=4 or np.max(np.abs(a[3]))>tolerance or np.max(np.abs(a[:3,:3]+a[:3,:3].T))>tolerance):raise ValueError('Invalid se(3) generator')
        result=expm(a);extra={}
        if direction is not None:
            e=numeric_array(direction,ndim=2,maximum=256)
            if e.shape!=a.shape:raise ValueError('Frechet direction shape mismatch')
            derivative=expm_frechet(a,e,compute_expm=False)
            extra['frechet_derivative']=[[[float(v.real),float(v.imag)] for v in row] for row in derivative] if kind=='SU' else derivative.tolist()
    elif operation=='log':
        if kind in {'SO','SU'} and (np.linalg.norm(a.conj().T@a-np.eye(n),ord=np.inf)>tolerance or abs(np.linalg.det(a)-1)>tolerance):raise ValueError('Input outside the declared compact group')
        if kind=='SL' and abs(np.linalg.det(a)-1)>tolerance:raise ValueError('SL input must have determinant one')
        if kind=='SE3' and (n!=4 or np.linalg.norm(a[3]-[0,0,0,1])>tolerance or np.linalg.norm(a[:3,:3].T@a[:3,:3]-np.eye(3))>tolerance or abs(np.linalg.det(a[:3,:3])-1)>tolerance):raise ValueError('Invalid SE(3) element')
        result=logm(a);extra={}
        if kind=='SU' and abs(np.trace(result))>tolerance:raise ValueError('Principal logarithm leaves su(n); choose a different branch explicitly')
        if kind!='SU':
            if np.max(np.abs(result.imag))>tolerance:raise ValueError('Principal logarithm is not real on this branch')
            result=result.real
    else:raise ValueError('Unsupported matrix-group operation')
    if not np.isfinite(result).all():raise ArithmeticError('Nonfinite matrix-group result')
    output=[[[float(v.real),float(v.imag)] for v in row] for row in result] if kind=='SU' else result.tolist()
    return {'matrix':output,**extra,'arithmetic':'floating_point','branch':'principal logarithm when requested'}


def se3_adjoint(transform):
    import numpy as np
    from ..math._structured import numeric_array
    t=numeric_array(transform,ndim=2,maximum=16)
    matrix_group('SE3',transform,operation='log')
    r,p=t[:3,:3],t[:3,3];x,y,z=p;skew=np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
    return np.block([[r,np.zeros((3,3))],[skew@r,r]]).tolist()


def integrate_group(generators,step,kind='SO'):
    import numpy as np
    from ..math._structured import numeric_array
    if not generators or len(generators)>10000 or type(step) not in (int,float) or not math.isfinite(step) or step<=0:raise ValueError('Bounded group integration data required')
    from .spectral import _complex
    def portable(a):return [[[float(v.real),float(v.imag)] for v in row] for row in a] if kind=='SU' else a.tolist()
    current=np.eye(len(generators[0]),dtype=complex if kind=='SU' else float);trajectory=[portable(current)]
    for raw in generators:
        a=np.array([[_complex(v) for v in row] for row in raw]) if kind=='SU' else numeric_array(raw,ndim=2,maximum=256)
        result=matrix_group(kind,portable(step*a))['matrix']
        result=np.array([[_complex(v) for v in row] for row in result]) if kind=='SU' else np.asarray(result)
        current=current@result;trajectory.append(portable(current))
    return {'trajectory':trajectory,'scheme':'right multiplication by exact step exponential for piecewise-constant generators'}
