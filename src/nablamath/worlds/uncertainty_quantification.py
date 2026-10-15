"""Exact interval propagation for a constant acceleration model, not probabilities."""
from ..core.uncertainty import UncertainQuantity
from ..core.precision import RationalInterval
from ..core.units import METER, SECOND, ONE


def constant_acceleration(position, velocity, acceleration, duration):
    """Enclose x=x0+v0*t+a*t^2/2 and v=v0+a*t for nonnegative time.

    Inputs may be dependent: interval arithmetic remains conservative but may widen.
    The result bounds this algebraic ideal model, excluding unmodeled dynamics.
    """
    if not all(isinstance(v, UncertainQuantity) for v in (position, velocity, acceleration, duration)):
        raise ValueError('UncertainQuantity inputs required')
    x = position.to(METER)
    v = velocity.to(METER/SECOND)
    a = acceleration.to(METER/SECOND**2)
    t = duration.to(SECOND)
    if t.interval.lower < 0:
        raise ValueError('Time interval must be nonnegative')
    half = UncertainQuantity(RationalInterval('1/2', '1/2'), ONE)
    return {'schema_version': 1, 'position': x+v*t+half*a*t*t,
            'velocity': v+a*t, 'time': t,
            'interpretation': 'conservative bounded enclosure, not a confidence interval',
            'experimental_validation': False}
