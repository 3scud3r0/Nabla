"""Analytic references, pixel fixtures and replay attacks for scientific graphics/SCMs."""
from copy import deepcopy
from fractions import Fraction as F
from io import BytesIO
import json
import xml.etree.ElementTree as ET

import pytest

from nablamath.core.semantic_ir import fingerprint
from nablamath.core.units import ONE, METER, KILOMETER, SECOND
from nablamath.discovery.causal_hypothesis import (
    CausalCoefficient as Edge, StructuralEquation as Equation,
    LinearCausalModel, replay_counterfactual,
)
from nablamath.graphics.coordinate_system import CoordinateSystem
from nablamath.graphics.scene_graph import GeometryScene, Point, Segment, Scene
from nablamath.graphics.scientific_renderer import (
    DataCurve, ScientificPlot, render_scientific_svg,
    replay_scientific_render, render_geometry_with_audit,
)
from nablamath.graphics.visual_regression import (
    compare_scenes, replay_scene_comparison, compare_pixels, replay_pixel_comparison,
)


def chain(*, sufficient=True):
    # X = 1 + Ux; M = 2X + Um; Y = -X + 3M + Uy.
    return LinearCausalModel((Equation('X', intercept=1), Equation('M', (Edge('X', 2),)),
        Equation('Y', (Edge('X', -1), Edge('M', 3)))),
        provenance='analytic supplied hypothesis fixture', causal_sufficiency=sufficient)


def graph(rows, sufficient=True):
    return LinearCausalModel(tuple(Equation(name, tuple(Edge(parent, 1) for parent in parents))
        for name, parents in rows), provenance='declared graph fixture', causal_sufficiency=sufficient)


def plot():
    curve = DataCurve('estimate', ((0, 1), (1, 2), (2, 1)), 'fixture-observations',
        (0, 1, 0), (2, 3, 2), 'absolute_bound')
    return ScientificPlot('Measured samples', (curve,), 'time', 'value',
        'supplied synthetic fixture', 'Bounds supplied by operator; no external calibration')


def scene(*, offset=0, title='Geometry'):
    return GeometryScene(title, CoordinateSystem(-2, 2, -2, 2),
        (Point('A', 0, 0), Point('B', 1, offset)), (Segment('AB', 'A', 'B'),))


def test_structural_prediction_and_analytic_total_effect():
    model = chain()
    predicted = model.predict({'X': 2, 'M': 1, 'Y': -2})
    assert predicted == {'X': 3, 'M': 7, 'Y': 16}
    assert model.total_effect('X', 'Y') == 5  # -1 + 3*2, two directed paths.
    assert model.total_effect('Y', 'X') == 0
    assert model.total_effect('X', 'X') == 1
    assert model.abduct(predicted) == {'X': 2, 'M': 1, 'Y': -2}


def test_counterfactual_preserves_individual_disturbances_and_cuts_incoming_edges():
    model = chain()
    receipt = model.counterfactual({'X': 3, 'M': 7, 'Y': 16}, {'M': 0})
    assert receipt['disturbances'] == {'X': '2', 'M': '1', 'Y': '-2'}
    assert receipt['counterfactual'] == {'X': '3', 'M': '0', 'Y': '-5'}
    assert replay_counterfactual(receipt, model)
    # Conditioning M=0 would alter beliefs about its causes; do(M=0) does not change X.
    receipt['counterfactual']['X'] = '0'
    receipt.pop('counterfactual_id')
    receipt['counterfactual_id'] = fingerprint(receipt)
    assert not replay_counterfactual(receipt, model)


def test_multiple_interventions_and_identity_counterfactual():
    model = chain()
    observed = {'X': 3, 'M': 7, 'Y': 16}
    assert model.counterfactual(observed, {})['counterfactual'] == {key: str(value) for key, value in observed.items()}
    changed = model.counterfactual(observed, {'X': 0, 'M': 1})
    assert changed['counterfactual'] == {'X': '0', 'M': '1', 'Y': '1'}


def test_model_serialization_is_canonical_and_unknown_assumptions_rejected():
    model = chain()
    data = json.loads(json.dumps(model.to_data()))
    rebuilt = LinearCausalModel.from_data(data)
    assert rebuilt.model_id == model.model_id
    assert rebuilt.to_data() == data
    data['assumptions'] = ['causality established from correlation']
    with pytest.raises(ValueError):
        LinearCausalModel.from_data(data)


@pytest.mark.parametrize('equations', [
    (Equation('X', (Edge('Y', 1),)), Equation('Y', (Edge('X', 1),))),
    (Equation('X', (Edge('Missing', 1),)),),
    (Equation('X'), Equation('X')),
])
def test_dag_rejects_cycles_unknown_parents_and_duplicate_variables(equations):
    with pytest.raises(ValueError):
        LinearCausalModel(equations, provenance='invalid fixture')


def test_equation_rejects_self_edges_duplicates_and_float_coefficients():
    with pytest.raises(ValueError):
        Equation('X', (Edge('X', 1),))
    with pytest.raises(ValueError):
        Equation('Y', (Edge('X', 1), Edge('X', 2)))
    with pytest.raises(ValueError):
        Edge('X', .5)
    with pytest.raises(ValueError):
        Equation('X<script>')


def test_physical_coefficients_convert_units_exactly():
    # X is numerical km; coefficient is 2 seconds/metre; Y is numerical seconds.
    model = LinearCausalModel((Equation('X', unit=KILOMETER),
        Equation('Y', (Edge('X', 2, SECOND / METER),), unit=SECOND)), provenance='unit fixture')
    assert model.predict({'X': 1, 'Y': 0}) == {'X': 1, 'Y': 2000}
    assert model.total_effect('X', 'Y') == 2000
    with pytest.raises(ValueError):
        LinearCausalModel((Equation('X', unit=METER),
            Equation('Y', (Edge('X', 1),), unit=SECOND)), provenance='invalid dimensions')


@pytest.mark.parametrize('assignment', [{}, {'X': 1}, {'X': 1, 'M': 2, 'Y': 3, 'Unknown': 4}])
def test_prediction_requires_complete_known_disturbances(assignment):
    with pytest.raises(ValueError):
        chain().predict(assignment)


def test_chain_fork_and_collider_d_separation():
    causal_chain = graph((('X', ()), ('M', ('X',)), ('Y', ('M',))))
    assert not causal_chain.d_separated({'X'}, {'Y'})
    assert causal_chain.d_separated({'X'}, {'Y'}, conditioned={'M'})
    fork = graph((('Z', ()), ('X', ('Z',)), ('Y', ('Z',))))
    assert not fork.d_separated({'X'}, {'Y'})
    assert fork.d_separated({'X'}, {'Y'}, conditioned={'Z'})
    collider = graph((('X', ()), ('Y', ()), ('C', ('X', 'Y')), ('D', ('C',))))
    assert collider.d_separated({'X'}, {'Y'})
    assert not collider.d_separated({'X'}, {'Y'}, conditioned={'C'})
    assert not collider.d_separated({'X'}, {'Y'}, conditioned={'D'})


def test_backdoor_adjustment_rejects_descendants_and_unknown_confounding():
    model = graph((('Z', ()), ('X', ('Z',)), ('Y', ('X', 'Z')), ('D', ('X',))))
    assert not model.backdoor_adjustment('X', 'Y')['identified_under_declared_assumptions']
    adjusted = model.backdoor_adjustment('X', 'Y', adjustment=('Z',))
    assert adjusted['identified_under_declared_assumptions']
    assert not adjusted['empirical_causal_identification_verified']
    invalid = model.backdoor_adjustment('X', 'Y', adjustment=('Z', 'D'))
    assert invalid['descendants_in_adjustment'] == ['D']
    assert not invalid['identified_under_declared_assumptions']
    assert not chain(sufficient=False).backdoor_adjustment('X', 'Y')['identified_under_declared_assumptions']


def test_graph_set_validation_and_unknown_intervention():
    model = chain()
    for left, right, conditioned in ((set(), {'Y'}, ()), ({'X'}, {'X'}, ()), ({'X'}, {'Y'}, ('Y',)), ({'Unknown'}, {'Y'}, ())):
        with pytest.raises(ValueError):
            model.d_separated(left, right, conditioned=conditioned)
    with pytest.raises(ValueError):
        model.counterfactual({'X': 1, 'M': 2, 'Y': 5}, {'Missing': 0})


def test_semantic_scene_comparison_preserves_metadata_and_numeric_threshold():
    baseline = scene()
    near = scene(offset=F(1, 100))
    receipt = compare_scenes(baseline, near, coordinate_tolerance='1/100')
    assert receipt['accepted']
    assert receipt['maximum_numeric_difference'] == '1/100'
    assert replay_scene_comparison(receipt, baseline, near)
    assert not compare_scenes(baseline, near)['accepted']
    assert not compare_scenes(baseline, scene(title='Different'), coordinate_tolerance=100)['accepted']
    receipt['accepted'] = False
    assert not replay_scene_comparison(receipt, baseline, near)


def test_semantic_declaration_reordering_is_neutral_but_identity_changes_recorded():
    baseline = scene()
    reordered = GeometryScene(baseline.title, baseline.coordinates, tuple(reversed(baseline.points)), baseline.segments)
    receipt = compare_scenes(baseline, reordered)
    assert receipt['accepted'] and receipt['differences'] == []
    assert receipt['baseline_id'] != receipt['candidate_id']
    assert receipt['canonical_baseline_id'] == receipt['canonical_candidate_id']


def test_semantic_units_cannot_be_hidden_by_coordinate_tolerance():
    baseline = scene()
    changed = GeometryScene(baseline.title, CoordinateSystem(-2, 2, -2, 2, x_unit='2'), baseline.points, baseline.segments)
    receipt = compare_scenes(baseline, changed, coordinate_tolerance=100)
    assert not receipt['accepted']
    assert any(row['path'].endswith('/x_unit') and row['kind'] == 'value' for row in receipt['differences'])


def test_v1_scene_samples_compared_numerically_without_ignoring_connectivity():
    baseline = Scene('fixture', 'samples', ((0, 0), (1, 1)))
    changed = Scene('fixture', 'samples', ((0, 0), (1, F(11, 10))))
    assert compare_scenes(baseline, changed, coordinate_tolerance='1/10')['accepted']
    disconnected = Scene('fixture', 'samples', baseline.points, False)
    assert not compare_scenes(baseline, disconnected, coordinate_tolerance=100)['accepted']


def test_scientific_render_preserves_exact_uncertainty_geometry_and_metadata():
    model = plot()
    rendered = render_scientific_svg(model, width=400, height=300)
    assert replay_scientific_render(rendered, model)
    root = ET.fromstring(rendered['svg'])
    namespace = {'s': 'http://www.w3.org/2000/svg'}
    metadata = json.loads(root.find('s:metadata', namespace).text)
    assert metadata == rendered['receipt']
    assert metadata['plot']['curves'][0]['uncertainty_kind'] == 'absolute_bound'
    assert len(root.findall('s:polygon', namespace)) == 1
    assert len(root.findall('s:circle', namespace)) == 3
    coordinates = CoordinateSystem(**metadata['coordinates'])
    transform = coordinates.transform(400, 300, 64)
    assert metadata['geometry'][0]['points'][1] == list(transform.pixel(1, 2))
    assert metadata['geometry'][0]['upper'][1] == list(transform.pixel(1, 3))


def test_svg_escaping_and_replay_detects_presentation_tampering():
    curve = DataCurve('<script>alert(1)</script>', ((0, 0),), 'source')
    model = ScientificPlot('<b>&"title', (curve,), 'x<script>', 'y', 'fixture', 'supplied only')
    rendered = render_scientific_svg(model)
    assert '<script>' not in rendered['svg']
    ET.fromstring(rendered['svg'])
    changed = deepcopy(rendered)
    changed['svg'] = changed['svg'].replace('stroke-width="2"', 'stroke-width="200"')
    assert not replay_scientific_render(changed, model)


def test_curve_conversion_and_confidence_contract():
    curve = DataCurve('distance', ((0, 1), (1, 2)), 'fixture', (0, 1), (2, 3),
        'confidence_interval', F(19, 20), SECOND, KILOMETER)
    converted = curve.converted(SECOND, METER)
    assert converted.points == ((0, 1000), (1, 2000))
    assert converted.upper == (2000, 3000)
    assert converted.confidence == F(19, 20)
    with pytest.raises(ValueError):
        curve.converted(METER, METER)


@pytest.mark.parametrize('kwargs', [
    dict(points=((1, 0), (0, 1))),
    dict(points=((0, 0), (0, 1))),
    dict(points=((0, 1),), lower=(2,), upper=(3,), uncertainty_kind='absolute_bound'),
    dict(points=((0, 1),), lower=(0,), upper=(2,), uncertainty_kind='none'),
    dict(points=((0, 1),), lower=(0,), upper=(2,), uncertainty_kind='confidence_interval', confidence=1),
    dict(points=((0, 1),), uncertainty_kind='unknown'),
])
def test_invalid_curve_contracts(kwargs):
    with pytest.raises((ValueError, TypeError)):
        DataCurve('curve', source_id='fixture', **kwargs)


def test_geometry_audit_reports_outside_points_without_certifying_constraints():
    model = GeometryScene('outside', CoordinateSystem(-1, 1, -1, 1), (Point('A', 2, 0),))
    rendered = render_geometry_with_audit(model)
    assert rendered['receipt']['outside_point_names'] == ['A']
    assert not rendered['receipt']['geometry_constraints_checked']
    assert rendered['receipt']['scene_id'] == model.content_id


def png(size, pixels):
    Image = pytest.importorskip('PIL.Image')
    image = Image.new('RGBA', size)
    image.putdata(pixels)
    output = BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def test_pixel_metrics_match_analytic_rgba_reference_and_bound_changes():
    baseline = png((2, 2), [(0, 0, 0, 255)] * 4)
    candidate = png((2, 2), [(0, 0, 0, 255), (4, 0, 0, 255), (0, 0, 0, 255), (0, 0, 0, 255)])
    receipt = compare_pixels(baseline, candidate, maximum_changed_fraction='1/4', maximum_mean_error='1/4')
    assert receipt['accepted']
    assert receipt['changed_pixels'] == 1
    assert receipt['changed_fraction'] == '1/4'
    assert receipt['mean_absolute_error'] == '1/4'  # 4 / (4 pixels * 4 channels).
    assert receipt['maximum_channel_error'] == 4
    assert receipt['changed_bounds'] == [1, 0, 1, 0]
    assert replay_pixel_comparison(receipt, baseline, candidate)
    assert not compare_pixels(baseline, candidate)['accepted']
    receipt['accepted'] = False
    receipt.pop('comparison_id')
    receipt['comparison_id'] = fingerprint(receipt)
    assert not replay_pixel_comparison(receipt, baseline, candidate)


def test_pixel_alpha_policy_and_channel_tolerance_are_explicit():
    left = png((1, 1), [(255, 0, 0, 0)])
    right = png((1, 1), [(0, 0, 255, 0)])
    assert not compare_pixels(left, right)['accepted']
    assert compare_pixels(left, right, alpha_policy='composite_white')['accepted']
    # Tolerating channels does not silently waive the independent mean threshold.
    receipt = compare_pixels(left, right, channel_tolerance=255)
    assert receipt['changed_pixels'] == 0 and not receipt['accepted']
    assert compare_pixels(left, right, channel_tolerance=255, maximum_mean_error=255)['accepted']


def test_pixel_dimension_mismatch_and_decode_failures():
    left = png((1, 1), [(0, 0, 0, 255)])
    right = png((2, 1), [(0, 0, 0, 255)] * 2)
    receipt = compare_pixels(left, right)
    assert receipt['status'] == 'dimension_mismatch' and not receipt['accepted']
    assert replay_pixel_comparison(receipt, left, right)
    with pytest.raises(ValueError):
        compare_pixels(b'not image', left)
    with pytest.raises(ValueError):
        compare_pixels(left, right, channel_tolerance=True)
    with pytest.raises(ValueError):
        compare_pixels(left, right, maximum_changed_fraction=2)
    with pytest.raises(ValueError):
        compare_pixels(left, right, alpha_policy='ignore-all-pixels')


def test_semantic_numeric_model_metadata_is_strict_even_with_large_coordinate_tolerance():
    left = scene()
    right = GeometryScene(left.title, left.coordinates, left.points, left.segments,
        model_json='{"value":"1"}')
    baseline = GeometryScene(left.title, left.coordinates, left.points, left.segments,
        model_json='{"value":"0"}')
    result = compare_scenes(baseline, right, coordinate_tolerance=10)
    assert not result['accepted']
    assert result['differences'][0]['kind'] == 'value'


def test_plot_singleton_nonzero_extent_and_axis_tick_labels():
    curve = DataCurve('single', ((3, 7),), 'fixture')
    model = ScientificPlot('Singleton', (curve,), 'x', 'y', 'fixture', 'one observation only')
    coordinates = model.coordinate_system()
    assert coordinates.xmin < 3 < coordinates.xmax
    assert coordinates.ymin < 7 < coordinates.ymax
    rendered = render_scientific_svg(model)
    root = ET.fromstring(rendered['svg'])
    ns = {'s': 'http://www.w3.org/2000/svg'}
    tick_labels = [node.text for node in root.findall('s:text', ns)]
    assert str(coordinates.xmin) in tick_labels
    assert str(coordinates.ymax) in tick_labels


def test_bounded_resource_contracts_for_models_curves_and_render_dimensions():
    with pytest.raises(ValueError):
        LinearCausalModel(tuple(Equation(f'X{i}') for i in range(33)), provenance='too large')
    with pytest.raises(ValueError):
        DataCurve('too many', tuple((i, i) for i in range(4097)), 'fixture')
    with pytest.raises(ValueError):
        render_scientific_svg(plot(), width=8192)
    with pytest.raises(ValueError):
        compare_scenes(scene(), scene(), coordinate_tolerance=-1)


def test_pixel_decoder_rejects_animation_and_budget_before_loading(monkeypatch):
    Image = pytest.importorskip('PIL.Image')
    import nablamath.graphics.visual_regression as regression
    first = Image.new('RGBA', (2, 2), (255, 0, 0, 255))
    second = Image.new('RGBA', (2, 2), (0, 255, 0, 255))
    output = BytesIO()
    first.save(output, format='GIF', save_all=True, append_images=[second])
    with pytest.raises(ValueError, match='multiframe'):
        compare_pixels(output.getvalue(), output.getvalue())
    simple = png((2, 2), [(0, 0, 0, 255)] * 4)
    monkeypatch.setattr(regression, 'MAX_IMAGE_PIXELS', 3)
    with pytest.raises(ValueError, match='pixel budget'):
        compare_pixels(simple, simple)
