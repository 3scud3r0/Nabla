"""Current-driven electrothermal feedback with an independent analytic temperature oracle."""
import math
from ...domains.contracts import si,result,AMPERE,OHM,KELVIN,JOULE,WATT,SECOND,ONE
from ...math.equations.ode import integrate


def electrothermal(current,resistance,thermal_capacity,conductance,temperature_coefficient,duration,*,steps=200):
    i=si(current,AMPERE);r=si(resistance,OHM,positive=True);c=si(thermal_capacity,JOULE/KELVIN,positive=True)
    g=si(conductance,WATT/KELVIN,positive=True);alpha=si(temperature_coefficient,ONE/KELVIN,nonnegative=True)
    t=si(duration,SECOND,positive=True);power=i*i*r;effective=g-power*alpha
    if effective<=0:
        raise ValueError('Perfil estacionário rejeita realimentação térmica instável')
    if type(steps) is not int or not 2<=steps<=100000 or effective*t/c/steps>1/10:
        raise ValueError('Passo eletrotérmico fora do regime limitado')
    def derivative(time,state):
        temperature=state[0]
        joule=float(power)*(1+float(alpha)*temperature)
        return ((joule-float(g)*temperature)/float(c),)
    trajectory=integrate(derivative,(0.,),0.,float(t),steps,'rk4')
    reference=float(power/effective)*(1-math.exp(-float(effective*t/c)))
    final=trajectory[-1][1][0]
    def net(state):return float(power)*(1+float(alpha)*state[0])-float(g)*state[0]
    dt=float(t)/steps
    heat=sum((net(a)+net(b))*dt/2 for (_,a),(_,b) in zip(trajectory,trajectory[1:]))
    energy_residual=abs(float(c)*final-heat)
    electrical=[{'time':time,'temperature_rise':state[0],'resistance':float(r)*(1+float(alpha)*state[0]),
                 'joule_power':float(power)*(1+float(alpha)*state[0])} for time,state in trajectory]
    return result('multiphysics','linear_current_driven_electrothermal',
                  {'current':current,'resistance':resistance,'thermal_capacity':thermal_capacity,'conductance':conductance,
                   'temperature_coefficient':temperature_coefficient,'duration':duration,'steps':steps},
                  {'final_temperature_rise':final,'analytic_reference':reference,'absolute_error':abs(final-reference),
                   'trajectory':electrical,'integrated_energy_residual':energy_residual},
                  {'temperature_rise':'K','time':'s','resistance':'ohm','joule_power':'W','integrated_energy_residual':'J'},
                  {'analytic_agreement':abs(final-reference)<1e-6*max(1,abs(reference)),
                   'positive_resistance':all(row['resistance']>0 for row in electrical)},
                  'Lumped linear temperature coefficient and fixed ambient; no spatial heat transfer or experimental validation.')
