"""Hydrostatic columns at constant density and gravity, with SI pressure balance."""
from ..contracts import si,result,KILOGRAM,METER,SECOND,PASCAL


def hydrostatic_pressure(density,gravity,depth,surface_pressure):
    rho=si(density,KILOGRAM/METER**3,positive=True);g=si(gravity,METER/SECOND**2,positive=True)
    h=si(depth,METER,nonnegative=True);p0=si(surface_pressure,PASCAL,nonnegative=True)
    pressure=p0+rho*g*h
    return result('earth','constant_density_hydrostatics',
                  {'density':density,'gravity':gravity,'depth':depth,'surface_pressure':surface_pressure},
                  {'pressure':pressure,'gauge_pressure':pressure-p0}, {'pressure':'Pa','gauge_pressure':'Pa'},
                  {'hydrostatic_balance':pressure-p0==rho*g*h},
                  'Constant density/gravity and static fluid; no compressibility, flow or geophysical validation.')
