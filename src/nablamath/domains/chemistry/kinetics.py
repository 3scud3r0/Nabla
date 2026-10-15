"""Ideal closed reversible first-order A↔B kinetics with analytic reference."""
import math
from ..contracts import si,result
from ...core.units import SECOND,MOLE,METER
from ...worlds.integrators import integrate_adaptive
CONCENTRATION=MOLE/METER**3


def reversible_first_order(initial_a,initial_b,forward_rate,reverse_rate,duration,*,atol=1e-10,rtol=1e-8):
    a,b=(float(si(v,CONCENTRATION,nonnegative=True)) for v in (initial_a,initial_b))
    kf,kr=(float(si(v,SECOND**-1,positive=True)) for v in (forward_rate,reverse_rate));end=float(si(duration,SECOND,positive=True))
    if end*(kf+kr)>10000:raise ValueError('Horizonte fora do perfil não rígido')
    def derivative(t,y):
        rate=-kf*y[0]+kr*y[1]
        return rate,-rate
    trajectory=integrate_adaptive(derivative,(a,b),0.,end,atol=atol,rtol=rtol)
    total=a+b;equilibrium=total*kr/(kf+kr)
    exact_a=equilibrium+(a-equilibrium)*math.exp(-(kf+kr)*end)
    error=max(abs(trajectory['final'][0]-exact_a),abs(trajectory['final'][1]-(total-exact_a)))
    conservation=max(abs(sum(state)-total) for _,state in trajectory['trajectory'])
    return result('chemistry','ideal_reversible_first_order',dict(initial_a=initial_a,initial_b=initial_b,forward_rate=forward_rate,reverse_rate=reverse_rate,duration=duration,atol=atol,rtol=rtol),
                  {'final':trajectory['final'],'trajectory':trajectory['trajectory'],'reference_error':error,'conservation_residual':conservation},
                  {'concentration':'mol/m^3','time':'s'},
                  {'conserved_total':conservation<=1e-10*max(1,total),'reference_tolerance':error<=20*(atol+rtol*total),
                   'nonnegative_within_numerical_tolerance':all(min(state)>=-10*atol for _,state in trajectory['trajectory'])},
                  'Ideal closed first-order two-species kinetics; finite non-stiff profile; no experimental calibration.')
