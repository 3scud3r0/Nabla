"""Exact static pressure across finite constant-density layers."""
from ..contracts import si,result,PASCAL
from ...core.units import METER,KILOGRAM,SECOND


def layered_hydrostatics(thicknesses,densities,gravity,surface_pressure):
    if not 1<=len(thicknesses)<=128 or len(thicknesses)!=len(densities):raise ValueError('Camadas fora do perfil')
    h=[si(v,METER,positive=True) for v in thicknesses];rho=[si(v,KILOGRAM/METER**3,positive=True) for v in densities]
    g=si(gravity,METER/SECOND**2,positive=True);p0=si(surface_pressure,PASCAL,nonnegative=True)
    depths=[0];pressures=[p0]
    for length,density in zip(h,rho):depths.append(depths[-1]+length);pressures.append(pressures[-1]+density*g*length)
    return result('earth','layered_static_hydrostatics',dict(thicknesses=thicknesses,densities=densities,gravity=gravity,surface_pressure=surface_pressure),
                  {'interface_depths':depths,'interface_pressures':pressures},{'depth':'m','pressure':'Pa'},
                  {'pressure_monotone':all(a<b for a,b in zip(pressures,pressures[1:]))},
                  'Static incompressible piecewise-constant density layers; no dynamics, mixing or observed validation.')
