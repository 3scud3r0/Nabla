"""Historical Mercury excess precession comparison; not a new empirical experiment.

43 arcsec/century is the rounded historical residual attributed to GR, not a raw
measurement or independent modern calibration dataset.
"""
import math
import pytest
from nablamath.physics.relativity.general import SchwarzschildMetric


def test_mercury_historical_rounded_reference():
    sun = SchwarzschildMetric(1.98847e30)
    radians = sun.weak_field_periapsis_advance_rad_per_orbit(57.909e9, .20563)
    arcseconds_per_century = radians * 180/math.pi * 3600 * 36525/87.969
    assert arcseconds_per_century == pytest.approx(43, abs=.2)
