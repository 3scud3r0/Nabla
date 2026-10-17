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
