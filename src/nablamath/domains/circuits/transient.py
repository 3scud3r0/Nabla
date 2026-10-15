"""Unit-checked ideal series RC step response with an analytic voltage oracle."""
import math
from ...core.units import AMPERE, SECOND, VOLT, Quantity
from ..contracts import OHM, si, result
from ...worlds.integrators.adaptive import integrate_adaptive

FARAD = AMPERE*SECOND/VOLT


def rc_step(resistance, capacitance, source_voltage, initial_voltage, duration, *, atol=1e-9,
            rtol=1e-6, max_attempts=100000):
    r = float(si(resistance, OHM, positive=True))
    c = float(si(capacitance, FARAD, positive=True))
    source = float(si(source_voltage, VOLT))
    initial = float(si(initial_voltage, VOLT))
    end = float(si(duration, SECOND, positive=True))
    tau = r*c
    if not math.isfinite(tau) or tau <= 0 or end/tau > 10000:
        raise ValueError('Constante RC fora do perfil não rígido')
    trajectory = integrate_adaptive(lambda t,y: ((source-y[0])/tau,), (initial,), 0., end,
                                    atol=atol, rtol=rtol, max_attempts=max_attempts)
    errors = [abs(y[0]-(source+(initial-source)*math.exp(-t/tau)))
              for t,y in trajectory['trajectory']]
    final = trajectory['final'][0]
    current = (source-final)/r
    return result('circuits', 'ideal_series_RC_step',
                  dict(resistance=resistance, capacitance=capacitance, source_voltage=source_voltage,
                       initial_voltage=initial_voltage, duration=duration, atol=atol, rtol=rtol,
                       max_attempts=max_attempts),
                  {'time_constant': tau, 'final_voltage': final, 'final_current': current,
                   'trajectory': trajectory['trajectory'], 'max_reference_error': max(errors),
                   'accepted_steps': trajectory['accepted_steps'], 'rejected_steps': trajectory['rejected_steps']},
                  {'time_constant': 's', 'voltage': 'V', 'current': 'A'},
                  {'local_error_accepted': trajectory['max_accepted_local_error_ratio'] <= 1,
                   'analytic_reference': max(errors) <= 20*(atol+rtol*max(abs(initial), abs(source)))},
                  'Ideal linear RC, constant source, non-stiff finite horizon; no observed validation. '
                  'Local tolerance is not a rigorous global error enclosure.')
