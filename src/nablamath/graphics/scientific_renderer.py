"""Auditable SVG plots with exact data and explicit uncertainty semantics.

SVG is a presentation of supplied samples, never evidence of an exact continuous
solution. Units, source receipts, clipping and uncertainty interpretation travel
with the plot. Text is escaped and no external images or scripts are emitted.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from html import escape
from itertools import islice

from ..core.semantic_ir import canonical_json, fingerprint, rational
from ..core.units import ONE, Unit
from .coordinate_system import CoordinateSystem
from .scene_graph import GeometryScene


UNCERTAINTY_KINDS = {'none', 'absolute_bound', 'standard_deviation', 'confidence_interval'}
PALETTE = ('#2456a6', '#b43b28', '#27804a', '#804a9e', '#986c08', '#087f8c')


def _text(value, name, limit=4096):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{name} must be nonempty bounded text')
    if any(not (ord(c) in (9, 10, 13) or 0x20 <= ord(c) <= 0xD7FF
                or 0xE000 <= ord(c) <= 0xFFFD or 0x10000 <= ord(c) <= 0x10FFFF)
           for c in value):
        raise ValueError(f'{name} contains a character forbidden in XML 1.0')
    return value


def _bounded_tuple(value, maximum, name):
    try:
        result = tuple(islice(iter(value), maximum + 1))
    except TypeError as exc:
        raise ValueError(f'{name} must be iterable') from exc
    if len(result) > maximum:
        raise ValueError(f'{name} exceeds the bounded item budget')
    return result


def _unit_data(unit):
    if not isinstance(unit, Unit):
        raise ValueError('Typed axis unit required')
    _text(unit.symbol, 'unit symbol', 24)
    return {**unit.to_data(), 'symbol': unit.symbol}


@dataclass(frozen=True)
class DataCurve:
    name: str
    points: tuple[tuple[Fraction, Fraction], ...]
    source_id: str
    lower: tuple[Fraction, ...] = ()
    upper: tuple[Fraction, ...] = ()
    uncertainty_kind: str = 'none'
    confidence: Fraction | None = None
    x_unit: Unit = ONE
    y_unit: Unit = ONE

    def __post_init__(self):
        _text(self.name, 'curve name', 120)
        _text(self.source_id, 'source identifier', 256)
        if not isinstance(self.x_unit, Unit) or not isinstance(self.y_unit, Unit):
            raise ValueError('Typed axis units required')
        _unit_data(self.x_unit)
        _unit_data(self.y_unit)
        points = _bounded_tuple(self.points, 4096, 'curve points')
        object.__setattr__(self, 'points', tuple((rational(x), rational(y)) for x, y in points))
        object.__setattr__(self, 'lower', tuple(rational(value) for value in _bounded_tuple(self.lower, 4096, 'lower bounds')))
        object.__setattr__(self, 'upper', tuple(rational(value) for value in _bounded_tuple(self.upper, 4096, 'upper bounds')))
        if not 1 <= len(self.points) <= 4096:
            raise ValueError('Curve requires 1..4096 samples')
        if any(a[0] >= b[0] for a, b in zip(self.points, self.points[1:])):
            raise ValueError('Curve sample x coordinates must strictly increase')
        if self.uncertainty_kind not in UNCERTAINTY_KINDS:
            raise ValueError('Unknown uncertainty interpretation')
        if self.uncertainty_kind == 'none':
            if self.lower or self.upper or self.confidence is not None:
                raise ValueError('No-uncertainty curve cannot carry interval declarations')
        else:
            if len(self.lower) != len(self.points) or len(self.upper) != len(self.points):
                raise ValueError('One lower and upper endpoint required per sample')
            if any(not low <= point[1] <= high for point, low, high in zip(self.points, self.lower, self.upper)):
                raise ValueError('Every supplied interval must contain its center estimate')
            if self.uncertainty_kind == 'confidence_interval':
                confidence = rational(self.confidence)
                if not 0 < confidence < 1:
                    raise ValueError('Confidence must be strictly between zero and one')
                object.__setattr__(self, 'confidence', confidence)
            elif self.confidence is not None:
                raise ValueError('Confidence applies only to declared confidence intervals')

    def to_data(self):
        return {'name': self.name, 'points': [[str(x), str(y)] for x, y in self.points],
                'source_id': self.source_id, 'lower': list(map(str, self.lower)),
                'upper': list(map(str, self.upper)), 'uncertainty_kind': self.uncertainty_kind,
                'confidence': None if self.confidence is None else str(self.confidence),
                'x_unit': _unit_data(self.x_unit), 'y_unit': _unit_data(self.y_unit)}

    def converted(self, x_unit, y_unit):
        if not isinstance(x_unit, Unit) or not isinstance(y_unit, Unit) or x_unit.dimensions != self.x_unit.dimensions or y_unit.dimensions != self.y_unit.dimensions:
            raise ValueError('Incompatible plotting units')
        x_scale = self.x_unit.scale / x_unit.scale
        y_scale = self.y_unit.scale / y_unit.scale
        return DataCurve(self.name, tuple((x * x_scale, y * y_scale) for x, y in self.points),
                         self.source_id, tuple(value * y_scale for value in self.lower),
                         tuple(value * y_scale for value in self.upper), self.uncertainty_kind,
                         self.confidence, x_unit, y_unit)


@dataclass(frozen=True)
class ScientificPlot:
    title: str
    curves: tuple[DataCurve, ...]
    x_label: str
    y_label: str
    provenance: str
    limitations: str
    x_unit: Unit = ONE
    y_unit: Unit = ONE

    def __post_init__(self):
        for field in ('title', 'x_label', 'y_label', 'provenance', 'limitations'):
            _text(getattr(self, field), field, 4096 if field in {'provenance', 'limitations'} else 200)
        object.__setattr__(self, 'curves', _bounded_tuple(self.curves, 16, 'plot curves'))
        _unit_data(self.x_unit)
        _unit_data(self.y_unit)
        if not 1 <= len(self.curves) <= 16 or any(not isinstance(curve, DataCurve) for curve in self.curves):
            raise ValueError('Plot requires 1..16 typed curves')
        if len({curve.name for curve in self.curves}) != len(self.curves):
            raise ValueError('Curve names must be unique')
        if sum(len(curve.points) for curve in self.curves) > 20000:
            raise ValueError('Plot exceeds total sample budget')
        for curve in self.curves:
            curve.converted(self.x_unit, self.y_unit)

    def to_data(self):
        return {'schema_version': 1, 'title': self.title,
                'curves': [curve.to_data() for curve in self.curves],
                'x_label': self.x_label, 'y_label': self.y_label,
                'x_unit': _unit_data(self.x_unit), 'y_unit': _unit_data(self.y_unit),
                'provenance': self.provenance, 'limitations': self.limitations,
                'representation': 'supplied_samples_and_declared_uncertainty'}

    @property
    def plot_id(self):
        return fingerprint(self.to_data())

    def coordinate_system(self):
        curves = tuple(curve.converted(self.x_unit, self.y_unit) for curve in self.curves)
        xs = [x for curve in curves for x, _ in curve.points]
        ys = [y for curve in curves for _, y in curve.points]
        ys.extend(value for curve in curves for value in (*curve.lower, *curve.upper))
        xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
        dx, dy = xmax - xmin or Fraction(1), ymax - ymin or Fraction(1)
        return CoordinateSystem(xmin - dx / 20, xmax + dx / 20,
                                ymin - dy / 20, ymax + dy / 20,
                                self.x_unit.symbol, self.y_unit.symbol, False)


def _polyline(points):
    return ' '.join(f'{x},{y}' for x, y in points)


def render_scientific_svg(plot, *, width=800, height=600):
    if not isinstance(plot, ScientificPlot):
        raise ValueError('ScientificPlot required')
    coordinates = plot.coordinate_system()
    transform = coordinates.transform(width, height, padding=64)
    geometry = []
    for index, original in enumerate(plot.curves):
        curve = original.converted(plot.x_unit, plot.y_unit)
        geometry.append({'name': curve.name, 'color': PALETTE[index % len(PALETTE)],
                         'points': [list(transform.pixel(x, y)) for x, y in curve.points],
                         'lower': [list(transform.pixel(point[0], value)) for point, value in zip(curve.points, curve.lower)],
                         'upper': [list(transform.pixel(point[0], value)) for point, value in zip(curve.points, curve.upper)]})
    payload = {'schema_version': 1, 'plot_id': plot.plot_id, 'plot': plot.to_data(),
               'coordinates': coordinates.to_data(), 'width': width, 'height': height,
               'geometry': geometry, 'renderer': 'nabla-scientific-svg-v1',
               'limitations': 'Straight segments connect supplied samples; uncertainty interpretation is declared, not statistically verified.'}
    receipt = {**payload, 'render_id': fingerprint(payload)}
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
             f'<title>{escape(plot.title)}</title>',
             f'<desc>{escape(plot.limitations)}</desc>',
             f'<metadata>{escape(canonical_json(receipt))}</metadata>',
             '<rect width="100%" height="100%" fill="white"/>',
             f'<text x="64" y="28" font-size="16">{escape(plot.title)}</text>',
             f'<path d="M 64 64 V {height - 64} H {width - 64}" fill="none" stroke="#222222"/>']
    for tick in range(5):
        x_value = coordinates.xmin + (coordinates.xmax - coordinates.xmin) * Fraction(tick, 4)
        y_value = coordinates.ymin + (coordinates.ymax - coordinates.ymin) * Fraction(tick, 4)
        x_pixel, _ = transform.pixel(x_value, coordinates.ymin)
        _, y_pixel = transform.pixel(coordinates.xmin, y_value)
        lines.append(f'<path d="M {x_pixel} {height - 64} v 5" stroke="#222222"/>')
        lines.append(f'<text x="{x_pixel}" y="{height - 44}" text-anchor="middle" font-size="10">{x_value}</text>')
        lines.append(f'<path d="M 59 {y_pixel} h 5" stroke="#222222"/>')
        lines.append(f'<text x="56" y="{y_pixel + 3}" text-anchor="end" font-size="10">{y_value}</text>')
    for row in geometry:
        color = row['color']
        if row['lower']:
            polygon = row['lower'] + list(reversed(row['upper']))
            lines.append(f'<polygon points="{_polyline(polygon)}" fill="{color}" fill-opacity="0.16"/>')
        lines.append(f'<polyline points="{_polyline(row["points"])}" fill="none" stroke="{color}" stroke-width="2"/>')
        for x, y in row['points']:
            lines.append(f'<circle cx="{x}" cy="{y}" r="2" fill="{color}"/>')
    lines.extend((f'<text x="{width // 2}" y="{height - 16}" text-anchor="middle">{escape(plot.x_label)} [{escape(plot.x_unit.symbol)}]</text>',
                  f'<text x="8" y="48">{escape(plot.y_label)} [{escape(plot.y_unit.symbol)}]</text>',
                  '</svg>'))
    return {'svg': '\n'.join(lines) + '\n', 'receipt': receipt}


def replay_scientific_render(rendered, plot):
    try:
        receipt = rendered['receipt']
        return rendered == render_scientific_svg(plot, width=receipt['width'], height=receipt['height'])
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return False


def render_geometry_with_audit(scene, *, width=800, height=600):
    """Render an existing exact geometry scene while retaining its full contract."""
    from .rendering import render_rich_svg
    if not isinstance(scene, GeometryScene):
        raise ValueError('GeometryScene required')
    transform = scene.coordinates.transform(width, height)
    outside = sorted(point.name for point in scene.points if not transform.inside(point.x, point.y))
    outside_samples = sum(not transform.inside(x, y) for curve in scene.curves for x, y in curve.coordinates)
    payload = {'schema_version': 1, 'scene_id': scene.content_id,
               'scene': scene.to_data(), 'width': width, 'height': height,
               'outside_point_names': outside, 'outside_curve_samples': outside_samples,
               'geometry_constraints_checked': False,
               'scope': 'render audit only; geometric constraints require separate verification'}
    return {'svg': render_rich_svg(scene, width, height),
            'receipt': {**payload, 'render_id': fingerprint(payload)}}
