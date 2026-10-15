"""Bounded algebraic mixing-length closure and source-declared local calibration.

This module is a one-dimensional shear closure. It is not DNS, LES, a RANS
transport-equation solver or a universal turbulence predictor. Calibration only
fits supplied shear measurements; authenticity and independence are unverified.
All dimensional arguments use SI units and all uncertainties here are absent:
fit residuals must not be interpreted as confidence intervals.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

CONTRACT_VERSION = 1


def _number(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f'{name} must be finite')
    return float(value)


@dataclass(frozen=True)
class MixingLengthModel:
    """nu_t=min(nu_cap, ell**2*abs(du/dy)), ell=kappa*y*damping.

    The optional van Driest damping is 1-exp(-y_plus/A_plus). A positive cap is
    a declared numerical/model bound and is reported whenever it is active.
    Setting wall_units=None disables damping; it does not infer friction speed.
    """

    kappa: float = 0.41
    damping_a_plus: float = 26.0
    max_eddy_viscosity_m2_s: float = 100.0
    max_wall_distance_m: float = 1000.0

    def __post_init__(self) -> None:
        for name in ('kappa', 'damping_a_plus', 'max_eddy_viscosity_m2_s', 'max_wall_distance_m'):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        if not 0.1 <= self.kappa <= 1.0:
            raise ValueError('kappa must be in [0.1,1]')
        if not 1 <= self.damping_a_plus <= 1000:
            raise ValueError('damping A+ must be in [1,1000]')
        if not 1e-12 <= self.max_eddy_viscosity_m2_s <= 1e12:
            raise ValueError('eddy viscosity cap outside [1e-12,1e12]')
        if not 1e-12 <= self.max_wall_distance_m <= 1e6:
            raise ValueError('wall-distance bound outside [1e-12,1e6]')

    def evaluate(
        self,
        wall_distance_m: float,
        velocity_gradient_per_s: float,
        *,
        wall_units: float | None = None,
    ) -> MixingLengthResult:
        y = _number(wall_distance_m, 'wall distance')
        gradient = _number(velocity_gradient_per_s, 'velocity gradient')
        if not 0 <= y <= self.max_wall_distance_m or abs(gradient) > 1e12:
            raise ValueError('wall distance or gradient outside model bounds')
        damping = 1.0
        if wall_units is not None:
            y_plus = _number(wall_units, 'wall units')
            if not 0 <= y_plus <= 1e12:
                raise ValueError('wall units outside [0,1e12]')
            damping = -math.expm1(-y_plus / self.damping_a_plus)
        length = self.kappa * y * damping
        uncapped = length**2 * abs(gradient)
        return MixingLengthResult(
            length,
            min(uncapped, self.max_eddy_viscosity_m2_s),
            uncapped > self.max_eddy_viscosity_m2_s,
            gradient,
        )

    def to_data(self) -> dict:
        from dataclasses import asdict
        return {
            'schema_version': CONTRACT_VERSION,
            **asdict(self),
            'model': 'bounded_algebraic_mixing_length',
            'empirical_generalization_established': False,
        }


@dataclass(frozen=True)
class MixingLengthResult:
    mixing_length_m: float
    eddy_viscosity_m2_s: float
    cap_active: bool
    velocity_gradient_per_s: float

    def shear_stress_pa(self, density_kg_m3: float, molecular_viscosity_m2_s: float) -> float:
        """Total modeled shear rho*(nu+nu_t)*du/dy; sign follows gradient."""
        density = _number(density_kg_m3, 'density')
        molecular = _number(molecular_viscosity_m2_s, 'molecular viscosity')
        if not 1e-12 <= density <= 1e12 or not 0 <= molecular <= 1e6:
            raise ValueError('density or molecular viscosity outside bounds')
        return density * (molecular + self.eddy_viscosity_m2_s) * self.velocity_gradient_per_s


@dataclass(frozen=True)
class ShearMeasurement:
    """One caller-supplied shear observation, with source identity and SI units."""

    sample_id: str
    wall_distance_m: float
    velocity_gradient_per_s: float
    shear_stress_pa: float
    density_kg_m3: float
    molecular_viscosity_m2_s: float
    source: str
    synthetic: bool = False
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.sample_id, str) or not self.sample_id.strip():
            raise ValueError('sample identity required')
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError('source declaration required')
        if type(self.synthetic) is not bool:
            raise ValueError('synthetic must be boolean')
        for name in ('wall_distance_m', 'velocity_gradient_per_s', 'shear_stress_pa',
                     'density_kg_m3', 'molecular_viscosity_m2_s', 'weight'):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        if not 0 <= self.wall_distance_m <= 1e6:
            raise ValueError('wall distance outside bounds')
        if abs(self.velocity_gradient_per_s) > 1e12 or abs(self.shear_stress_pa) > 1e30:
            raise ValueError('gradient or shear outside bounds')
        if not 1e-12 <= self.density_kg_m3 <= 1e12:
            raise ValueError('density outside bounds')
        if not 0 <= self.molecular_viscosity_m2_s <= 1e6 or not 1e-12 <= self.weight <= 1e12:
            raise ValueError('viscosity or weight outside bounds')

    def feature_and_target(self) -> tuple[float, float]:
        """Linear regression feature for kappa**2 without damping or cap."""
        g = self.velocity_gradient_per_s
        feature = self.density_kg_m3 * self.wall_distance_m**2 * abs(g) * g
        target = self.shear_stress_pa - self.density_kg_m3 * self.molecular_viscosity_m2_s * g
        return feature, target


@dataclass(frozen=True)
class MixingLengthCalibration:
    """Weighted least-squares estimate constrained to the declared kappa domain."""

    model: MixingLengthModel
    rows: tuple[dict, ...]
    weighted_squared_residual_pa2: float
    sources: tuple[str, ...]
    synthetic_present: bool
    parameter_at_bound: bool

    def to_data(self) -> dict:
        return {
            'schema_version': CONTRACT_VERSION,
            'model': self.model.to_data(),
            'comparisons': list(self.rows),
            'weighted_squared_residual_pa2': self.weighted_squared_residual_pa2,
            'sources': list(self.sources),
            'synthetic_present': self.synthetic_present,
            'parameter_at_bound': self.parameter_at_bound,
            'source_authenticity_verified': False,
            'holdout_validation_performed': False,
            'limitations': 'Local fit to supplied samples, undamped and uncapped; no external calibration or predictive validity established.',
        }


def calibrate_mixing_length(
    measurements: Sequence[ShearMeasurement],
    *,
    minimum_kappa: float = 0.1,
    maximum_kappa: float = 1.0,
    max_eddy_viscosity_m2_s: float = 100.0,
) -> MixingLengthCalibration:
    """Fit kappa**2 to shear after molecular contribution, with fixed weights.

    The fitting closure is undamped. Samples that would engage the declared
    eddy-viscosity cap are rejected because they invalidate the linear fit.
    Degenerate all-zero features are rejected instead of inventing a parameter.
    """
    if not isinstance(measurements, (list, tuple)) or not 2 <= len(measurements) <= 10000:
        raise ValueError('two to 10000 measurements required')
    if not all(isinstance(m, ShearMeasurement) for m in measurements):
        raise ValueError('ShearMeasurement samples required')
    if len({m.sample_id for m in measurements}) != len(measurements):
        raise ValueError('sample identities must be unique')
    low, high = _number(minimum_kappa, 'minimum kappa'), _number(maximum_kappa, 'maximum kappa')
    if not 0.1 <= low < high <= 1.0:
        raise ValueError('kappa fitting interval must lie within [0.1,1]')
    pairs = [m.feature_and_target() for m in measurements]
    scale = max(abs(x) for x, _ in pairs)
    if scale == 0:
        raise ValueError('unidentifiable kappa: zero shear features')
    # Normalize the feature to reduce squaring-induced overflow/underflow.
    denominator = math.fsum(m.weight * (x / scale)**2 for m, (x, _) in zip(measurements, pairs))
    numerator = math.fsum(m.weight * (x / scale) * (y / scale) for m, (x, y) in zip(measurements, pairs))
    if not math.isfinite(numerator) or not math.isfinite(denominator) or denominator <= 0:
        raise ArithmeticError('ill-scaled calibration')
    coefficient = numerator / denominator
    constrained = min(high**2, max(low**2, coefficient))
    model = MixingLengthModel(math.sqrt(constrained), max_eddy_viscosity_m2_s=max_eddy_viscosity_m2_s,
                             max_wall_distance_m=max(1.0, max(m.wall_distance_m for m in measurements)))
    rows = []
    for sample in measurements:
        closure = model.evaluate(sample.wall_distance_m, sample.velocity_gradient_per_s)
        if closure.cap_active:
            raise ValueError('calibration samples activate the declared cap')
        predicted = closure.shear_stress_pa(sample.density_kg_m3, sample.molecular_viscosity_m2_s)
        rows.append({'sample_id': sample.sample_id, 'observed_pa': sample.shear_stress_pa,
                     'predicted_pa': predicted, 'residual_pa': predicted - sample.shear_stress_pa,
                     'weight': sample.weight, 'source': sample.source, 'synthetic': sample.synthetic})
    squared = math.fsum(r['weight'] * r['residual_pa']**2 for r in rows)
    if not math.isfinite(squared):
        raise ArithmeticError('nonfinite calibration residual')
    return MixingLengthCalibration(model, tuple(rows), squared,
                                   tuple(sorted({m.source for m in measurements})),
                                   any(m.synthetic for m in measurements), constrained != coefficient)
