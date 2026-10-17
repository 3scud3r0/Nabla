"""Vertical layered acoustic travel times and infinite-slab gravity (86)."""
import math
from ._area_utils import calculate as _calculate


def geophysics(kind, *, thicknesses=None, velocities=None, densities=None, density=None, height=None):
    if kind=='bouguer_slab':
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in (density,height)) or not 0<=density<=1e6 or abs(height)>1e8:
            raise ValueError('Finite SI slab density and signed thickness are required')
        gravity = 2*math.pi*6.67430e-11*density*height
        return {'gravity_m_s2':gravity,'gravity_mgal':gravity*1e5,
                'scope':'Infinite horizontal slab model; G=6.67430e-11 SI, no terrain or curvature correction.'}
    if kind!='vertical_seismic':raise ValueError('Unknown geophysical model')
    if not isinstance(thicknesses,list) or not isinstance(velocities,list) or not 1<=len(thicknesses)<=1024 or len(thicknesses)!=len(velocities):
        raise ValueError('Require matching finite layer thicknesses and velocities')
    if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<v<=1e8 for v in thicknesses+velocities):
        raise ValueError('Layer thicknesses and velocities must be positive SI values')
    times = [];total = 0.
    for h,v in zip(thicknesses,velocities):total+=2*h/v;times.append(total)
    reflections = None
    if densities is not None:
        if not isinstance(densities,list) or len(densities)!=len(velocities) or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<v<=1e6 for v in densities):
            raise ValueError('Densities must be positive matching SI values')
        impedance = [rho*v for rho,v in zip(densities,velocities)]
        reflections = [(b-a)/(b+a) for a,b in zip(impedance,impedance[1:])]
    return {'two_way_times_seconds':times,'reflection_coefficients':reflections,
            'scope':'Normal-incidence isotropic acoustic horizontal layers; no oblique elastic or anisotropic ray tracing.'}


def calculate(**arguments):return _calculate('geophysics',**arguments)


def gravity_point_masses(points,masses,observations):
    import numpy as np
    from ..math._structured import numeric_array
    p,m,q=(numeric_array(v,ndim=n,maximum=30000) for v,n in ((points,2),(masses,1),(observations,2)))
    if p.shape[1]!=3 or q.shape[1]!=3 or len(m)!=len(p) or len(p)*len(q)>1000000 or np.any(m<0):raise ValueError('Invalid finite SI mass model')
    delta=p[None,:,:]-q[:,None,:];r=np.linalg.norm(delta,axis=2)
    if np.any(r==0):raise ValueError('Observation coincides with a point mass')
    acceleration=6.67430e-11*np.sum(m[None,:,None]*delta/r[:,:,None]**3,axis=1)
    return {'acceleration_m_s2':acceleration.tolist(),'potential_m2_s2':(-6.67430e-11*np.sum(m[None,:]/r,axis=1)).tolist(),'scope':'Newtonian point masses in SI; no finite-body or relativistic correction.'}


def tikhonov_inversion(kernel,observations,regularization=1e-3,noise_standard_deviation=1.):
    import numpy as np
    from ..math._structured import numeric_array
    a,b=numeric_array(kernel,ndim=2,maximum=65536),numeric_array(observations,ndim=1,maximum=4096)
    if a.shape[0]!=len(b) or a.shape[1]>256 or not regularization>0 or not noise_standard_deviation>0 or not np.isfinite([regularization,noise_standard_deviation]).all():raise ValueError('Invalid linear inverse problem')
    precision=a.T@a/noise_standard_deviation**2+regularization*np.eye(a.shape[1]);cov=np.linalg.inv(precision);estimate=cov@a.T@b/noise_standard_deviation**2
    return {'estimate':estimate.tolist(),'posterior_covariance':cov.tolist(),'residual_norm':float(np.linalg.norm(a@estimate-b)),
            'assumptions':'Linear forward model, iid Gaussian noise, zero-mean Gaussian prior of precision regularization.'}


def acoustic_wave_2d(initial,velocity,spacing,time_step,steps):
    import numpy as np
    from ..math._structured import numeric_array
    current=numeric_array(initial,ndim=2,maximum=65536)
    if min(current.shape)<3 or not np.isfinite([velocity,spacing,time_step]).all() or min(velocity,spacing,time_step)<=0 or type(steps) is not int or not 1<=steps<=10000:raise ValueError('Invalid acoustic grid')
    ratio=(velocity*time_step/spacing)**2
    if 2*ratio>1:raise ValueError('Acoustic CFL condition c*dt/dx <= 1/sqrt(2) violated')
    if np.any(current[0]) or np.any(current[-1]) or np.any(current[:,0]) or np.any(current[:,-1]):raise ValueError('Homogeneous Dirichlet boundary required')
    def lap(u):return u[:-2,1:-1]+u[2:,1:-1]+u[1:-1,:-2]+u[1:-1,2:]-4*u[1:-1,1:-1]
    # Zero initial velocity requires a half acceleration on the first step.
    previous=current.copy();new=current.copy();new[1:-1,1:-1]+=.5*ratio*lap(current);current=new
    for _ in range(1,steps):
        new=np.zeros_like(current);new[1:-1,1:-1]=2*current[1:-1,1:-1]-previous[1:-1,1:-1]+ratio*lap(current);previous,current=current,new
    return {'final':current.tolist(),'time':steps*time_step,'cfl':velocity*time_step/spacing,
            'scope':'Constant-speed 2D acoustic scalar wave, zero initial velocity and fixed zero boundaries, caller-consistent units.'}
