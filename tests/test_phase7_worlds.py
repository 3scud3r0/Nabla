from dataclasses import replace
import math
import unittest
import xml.etree.ElementTree as ET
from nablamath.worlds.model_spec import ModelSpec, HeatModelSpec
from nablamath.worlds.pde import solve_heat
from nablamath.worlds.mesh import UniformMesh
from nablamath.worlds.validation import simulate, compare_observations
from nablamath.worlds.conservation import check_conservation
from nablamath.worlds.convergence import heat_convergence
from nablamath.worlds.sensitivity import sensitivity
from nablamath.worlds.animation import render_animation


class WorldsTests(unittest.TestCase):
    def test_heat_closed_form_boundaries_balance_and_convergence(self):
        model = HeatModelSpec()
        result = solve_heat(model, cells=20, steps=200)
        self.assertLess(result['max_component_error'], 3e-4)
        self.assertEqual(result['model_id'], model.content_id)
        self.assertTrue(all(state[0] == state[-1] == 0 for _,state in result['trajectory']))
        self.assertTrue(check_conservation(result, tolerance=1e-12)['within_tolerance'])
        study = heat_convergence(model)
        self.assertTrue(study['improves'])
        self.assertTrue(study['within_tolerance'])
        self.assertGreater(study['observed_order'], 1.8)
        self.assertLess(study['observed_order'], 2.2)
        self.assertFalse(study['experimental_validation'])

    def test_stability_and_allocation_guards(self):
        with self.assertRaises(ValueError):
            solve_heat(HeatModelSpec(), cells=100, steps=2)
        for model in [dict(diffusivity=-1), dict(length=0), dict(amplitude=float('nan')), dict(mode=True)]:
            with self.subTest(model=model), self.assertRaises(ValueError):
                HeatModelSpec(**model)
        with self.assertRaises(ValueError):
            solve_heat(HeatModelSpec(), cells=2000, steps=100000)
        with self.assertRaises(ValueError):
            UniformMesh(cells=True)

    def test_parameter_sensitivity_matches_independent_derivative(self):
        model = ModelSpec('exponential_decay', (2,), rate=0.7, duration=1.)
        result = sensitivity(model, steps=100)
        expected = -2*math.exp(-.7)
        self.assertAlmostEqual(result['derivative'][0], expected, places=6)
        self.assertLess(result['step_change'], 1e-6)
        oscillator = simulate(ModelSpec('harmonic_oscillator', (1,0)), steps=100)
        self.assertTrue(check_conservation(oscillator)['within_tolerance'])

    def test_observations_units_residuals_and_negative_results(self):
        model = ModelSpec('exponential_decay', (1,))
        result = simulate(model)
        measurements = [{'time': .5, 'values': [math.exp(-.5)], 'uncertainties': [.001]}]
        report = compare_observations(result, measurements, provenance='fixture independent formula', state_units=('dimensionless',))
        self.assertTrue(report['within_tolerance'])
        self.assertFalse(report['independent_provenance_verified'])
        measurements[0]['values'] = [10.]
        self.assertFalse(compare_observations(result, measurements, provenance='fixture', state_units=('dimensionless',))['within_tolerance'])
        with self.assertRaises(ValueError):
            compare_observations(result, measurements, provenance='fixture', state_units=('K',))
        measurements[0]['time'] = 2.
        with self.assertRaises(ValueError):
            compare_observations(result, measurements, provenance='fixture', state_units=('dimensionless',))

    def test_animation_uses_simulated_frames_and_valid_xml(self):
        result = solve_heat(HeatModelSpec(), cells=10, steps=100)
        svg = render_animation(result, max_frames=10)
        root = ET.fromstring(svg)
        self.assertIsNotNone(root.find('.//{http://www.w3.org/2000/svg}animate'))
        self.assertIn('not experimental evidence', svg)
        self.assertEqual(svg, render_animation(result, max_frames=10))
