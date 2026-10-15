"""Ideal series RLC sinusoidal steady-state phasors, peak-voltage convention."""
import math
from ..contracts import OHM,si,result
from ...core.units import VOLT,SECOND,AMPERE
from .transient import FARAD
HENRY=VOLT*SECOND/AMPERE


def series_rlc(resistance,inductance,capacitance,voltage_peak,angular_frequency):
    r=si(resistance,OHM,positive=True);l=si(inductance,HENRY,positive=True);c=si(capacitance,FARAD,positive=True)
    v=si(voltage_peak,VOLT,nonnegative=True);omega=si(angular_frequency,SECOND**-1,positive=True)
    reactance=omega*l-1/(omega*c);z=complex(float(r),float(reactance));current=float(v)/z
    power=float(v)**2*float(r)/(2*abs(z)**2)
    return result('circuits','ideal_series_RLC_phasor',dict(resistance=resistance,inductance=inductance,capacitance=capacitance,
                  voltage_peak=voltage_peak,angular_frequency=angular_frequency),
                  {'impedance_real':r,'impedance_imaginary':reactance,'current_real':current.real,'current_imaginary':current.imag,
                   'average_real_power':power,'resonance_angular_frequency':1/math.sqrt(float(l*c))},
                  {'impedance':'ohm','current':'A peak','power':'W','angular_frequency':'rad/s'},
                  {'power_nonnegative':power>=0,'phasor_kvl_residual':abs(z*current-float(v))<=1e-10*max(1,abs(float(v)))},
                  'Ideal linear sinusoidal steady state; peak convention; no transients, parasitics or observed validation.')
