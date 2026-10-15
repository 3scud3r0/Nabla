"""Unit-aware supplied measurement comparisons, without provenance authentication."""
from dataclasses import dataclass
from fractions import Fraction
from ..core.units import Quantity


@dataclass(frozen=True)
class Observation:
    sample_id: str
    measured: Quantity
    uncertainty: Quantity
    source: str
    synthetic: bool = False

    def __post_init__(self):
        if not isinstance(self.sample_id, str) or not self.sample_id.strip() or not isinstance(self.source, str) or not self.source.strip():
            raise ValueError('Sample identity and source required')
        if type(self.synthetic) is not bool or not isinstance(self.measured, Quantity) or not isinstance(self.uncertainty, Quantity):
            raise ValueError('Quantity measurement, uncertainty and boolean synthetic flag required')
        if self.uncertainty.to(self.measured.unit).value < 0:
            raise ValueError('Nonnegative absolute uncertainty required')


def compare_measurements(observations, predictions, *, tolerance):
    """Return signed exact residuals and interval coverage; no statistical calibration claim."""
    observations, predictions = tuple(observations), tuple(predictions)
    if (not observations or len(observations) != len(predictions)
            or not all(isinstance(o, Observation) for o in observations)
            or not isinstance(tolerance, Quantity)):
        raise ValueError('Matched nonempty observations and predictions required')
    if len({o.sample_id for o in observations}) != len(observations):
        raise ValueError('Duplicate sample identity')
    unit = observations[0].measured.unit
    allowed = tolerance.to(unit).value
    if allowed < 0:
        raise ValueError('Nonnegative tolerance required')
    rows = []
    for observation, prediction in zip(observations, predictions):
        if not isinstance(prediction, Quantity):
            raise ValueError('Quantity prediction required')
        residual = prediction.to(unit).value - observation.measured.to(unit).value
        limit = observation.uncertainty.to(unit).value + allowed
        rows.append({'sample_id': observation.sample_id, 'residual': str(residual),
                     'limit': str(limit), 'covered': abs(residual) <= limit,
                     'source': observation.source, 'synthetic': observation.synthetic})
    residuals = [Fraction(r['residual']) for r in rows]
    return {'schema_version': 1, 'comparisons': rows, 'unit': unit.to_data(),
            'mean_signed_residual': str(sum(residuals)/len(rows)),
            'mean_absolute_residual': str(sum(map(abs, residuals))/len(rows)),
            'coverage_fraction': str(Fraction(sum(r['covered'] for r in rows),len(rows))),
            'independent_provenance_verified': False,
            'evidence': 'synthetic_comparison' if any(o.synthetic for o in observations) else 'caller_supplied_measurements',
            'limitations': 'Coverage is descriptive; source authenticity and measurement independence are not established.'}
