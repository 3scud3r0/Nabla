"""Conservative bounded uncertainty with exact SI conversion; not probabilities."""
from dataclasses import dataclass

from .precision import RationalInterval
from .semantic_ir import rational
from .units import ONE, Unit
from ..numeric.intervals import subtract


@dataclass(frozen=True)
class UncertainQuantity:
    interval: RationalInterval
    unit: Unit = ONE

    def __post_init__(self):
        if not isinstance(self.interval, RationalInterval) or not isinstance(self.unit, Unit):
            raise ValueError("Interval and SI unit required")

    @classmethod
    def around(cls, value, radius, unit=ONE):
        value, radius = rational(value), rational(radius)
        if radius < 0:
            raise ValueError("Uncertainty radius must be nonnegative")
        return cls(RationalInterval(value-radius, value+radius), unit)

    def to(self, unit):
        if not isinstance(unit, Unit) or unit.dimensions != self.unit.dimensions:
            raise ValueError("Incompatible uncertainty units")
        scale = self.unit.scale / unit.scale
        return UncertainQuantity(RationalInterval(self.interval.lower*scale, self.interval.upper*scale), unit)

    def __add__(self, other):
        return UncertainQuantity(self.interval + other.to(self.unit).interval, self.unit)

    def __sub__(self, other):
        return UncertainQuantity(subtract(self.interval, other.to(self.unit).interval), self.unit)

    def __mul__(self, other):
        return UncertainQuantity(self.interval * other.interval, self.unit * other.unit)

    def __truediv__(self, other):
        return UncertainQuantity(self.interval / other.interval, self.unit / other.unit)

    def to_data(self):
        return {"schema_version": 1, "lower": str(self.interval.lower),
                "upper": str(self.interval.upper), "unit": self.unit.to_data(),
                "interpretation": "bounded interval; dependence may widen enclosure; not a confidence interval"}
