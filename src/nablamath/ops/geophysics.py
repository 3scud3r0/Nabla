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
