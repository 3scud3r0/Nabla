"""Analytic references and adversarial cases for later-phase foundations."""
from dataclasses import replace
from fractions import Fraction as F
import json
import math
from pathlib import Path
import tempfile
import unittest

from nablamath.cli import main
from nablamath.domains.circuits import Resistor, solve_dc
from nablamath.evolution import SolverPolicy, select_on_calibration, evaluate_proposal
from nablamath.falsifier import search_equivalence
from nablamath.knowledge.versioned_claims import ClaimRevision, ClaimLedger
from nablamath.worlds import ModelSpec, simulate, convergence_study


class FalsifierTests(unittest.TestCase):
    def test_minimal_counterexample_in_declared_integer_domain(self):
        result = search_equivalence('x*x', 'x', radius=4)
        self.assertEqual(result.status, 'counterexample')
        self.assertEqual(result.witness, (('x', -1),))
        self.assertEqual((result.left_value, result.right_value), ('1', '-1'))

    def test_domain_mismatch_and_skipped_singularities(self):
        result = search_equivalence('x/x', '1')
        self.assertEqual(result.status, 'domain_counterexample')
        self.assertEqual(result.witness, (('x', 0),))
        result = search_equivalence('x/x', '1', compare_domains=False)
        self.assertEqual(result.status, 'no_counterexample_in_finite_domain')
        self.assertEqual(result.skipped_undefined, 1)
        self.assertFalse(result.formal_proof)

    def test_budget_and_finite_domain_are_distinct(self):
        result = search_equivalence('x+y', 'y+x', budget=3)
        self.assertEqual(result.status, 'budget_exhausted')
        self.assertEqual(result.checked, 3)
        self.assertFalse(result.exhaustive)
        result = search_equivalence('x+y', 'y+x', radius=2)
        self.assertEqual(result.checked, 25)
        self.assertTrue(result.exhaustive)
        self.assertFalse(result.formal_proof)
        self.assertEqual(search_equivalence('2', '3').status, 'counterexample')

    def test_reject_cost_and_executable_input(self):
        for left in ['x**100', 'x**y', '__import__("os")', 'a+b+c+d+e', '((x**8)**8)**8**8']:
            with self.subTest(left=left), self.assertRaises(ValueError):
                search_equivalence(left, '0')
        for radius, budget in [(33, 10), (3, 0), (True, 10)]:
            with self.assertRaises(ValueError):
                search_equivalence('x', 'x', radius=radius, budget=budget)

    def test_cli(self):
        self.assertEqual(main(['falsify', 'x*x', 'x']), 0)


class WorldValidationTests(unittest.TestCase):
    def test_convergence_order_against_closed_form(self):
        for name, initial in [('exponential_decay', (1,)), ('harmonic_oscillator', (1, 0))]:
            for method, bounds in [('euler', (.8, 1.2)), ('rk4', (3.8, 4.2))]:
                with self.subTest(name=name, method=method):
                    result = convergence_study(ModelSpec(name, initial), method=method)
                    self.assertGreater(result['observed_order'], bounds[0])
                    self.assertLess(result['observed_order'], bounds[1])
                    self.assertTrue(result['improves'])
                    self.assertFalse(result['experimental_validation'])

    def test_oscillator_energy_and_units(self):
        result = simulate(ModelSpec('harmonic_oscillator', (1, 0)), steps=100)
        self.assertLess(result['energy_drift_per_unit_mass'], 1e-10)
        self.assertEqual(result['state_units'], ('m', 'm/s'))
        self.assertEqual(len(result['trajectory']), 101)
        self.assertAlmostEqual(result['final'][0], math.cos(1), places=8)

    def test_zero_state_roundoff_does_not_invent_an_order(self):
        result = convergence_study(ModelSpec('harmonic_oscillator', (0, 0)))
        self.assertIsNone(result['observed_order'])
        self.assertTrue(result['within_tolerance'])

    def test_invalid_models_and_budgets(self):
        for name, initial, rate, duration in [('other', (1,), 1, 1), ('exponential_decay', (), 1, 1),
                ('harmonic_oscillator', (float('nan'),0), 1,1), ('exponential_decay',(1,),0,1),
                ('exponential_decay',(1,),1,float('inf'))]:
            with self.assertRaises(ValueError):
                ModelSpec(name, initial, rate, duration)
        with self.assertRaises(ValueError):
            simulate(ModelSpec('exponential_decay', (1,)), steps=100001)
        with self.assertRaises(ValueError):
            convergence_study(ModelSpec('exponential_decay', (1,)), tolerance=float('nan'))
        self.assertEqual(main(['simulate','exponential_decay','--initial','1']), 0)
        self.assertEqual(main(['simulate','exponential_decay','--initial','1','--method','euler']), 1)


class PolicyEvolutionTests(unittest.TestCase):
    def setUp(self):
        self.calibration = (ModelSpec('exponential_decay', (1,), .75),)
        self.holdout = tuple(ModelSpec('exponential_decay', (1,), r) for r in (.5,.6,.7,.8,.9,1.))
        self.baseline, self.candidate = SolverPolicy('euler',20), SolverPolicy('rk4',20)

    def test_selection_then_heldout_paired_evaluation(self):
        chosen = select_on_calibration((self.baseline,self.candidate), self.calibration)
        self.assertEqual(chosen,self.candidate)
        result = evaluate_proposal(chosen,self.baseline,self.calibration,self.holdout)
        self.assertTrue(result['accepted'])
        self.assertEqual(result['wins'],6)
        self.assertEqual(result['sign_test_p_value'],1/64)
        self.assertEqual(result['candidate_derivative_calls'],80)
        self.assertEqual(result['rollback_policy'], {'method':'euler','steps':20})

    def test_contamination_duplicates_budget_and_regressions(self):
        with self.assertRaises(ValueError):
            evaluate_proposal(self.candidate,self.baseline,self.calibration,(self.calibration[0],)+self.holdout)
        with self.assertRaises(ValueError):
            evaluate_proposal(self.candidate,self.baseline,self.calibration,(self.holdout[0],)*5)
        self.assertFalse(evaluate_proposal(self.candidate,self.baseline,self.calibration,self.holdout,
                                         max_derivative_calls=30)['accepted'])
        self.assertFalse(evaluate_proposal(self.baseline,self.candidate,self.calibration,self.holdout)['accepted'])
        ties = evaluate_proposal(self.baseline,self.baseline,self.calibration,self.holdout)
        self.assertFalse(ties['accepted'])
        self.assertEqual(ties['sign_test_p_value'],1)
        self.assertEqual(ties['ties'],6)


class CircuitTests(unittest.TestCase):
    def test_series_and_parallel_against_hand_calculations(self):
        series = solve_dc((Resistor('a','b',10),Resistor('b','0',10)),{'a':1})
        self.assertEqual(dict(series.voltages),{'0':0,'a':20,'b':10})
        self.assertEqual(series.branch_currents,(1,1))
        self.assertEqual(series.dissipated_power,20)
        self.assertTrue(series.verified)
        parallel = solve_dc((Resistor('a','0',10),Resistor('a','0',20)),{'a':3})
        self.assertEqual(dict(parallel.voltages)['a'],20)
        self.assertEqual(parallel.branch_currents,(2,1))
        self.assertEqual(parallel.supplied_power,60)

    def test_ground_balance_and_disconnected_network(self):
        for r in (0,-1):
            with self.assertRaises(ValueError):
                Resistor('a','0',r)
        with self.assertRaises(ValueError):
            solve_dc((Resistor('a','0',10),Resistor('b','c',10)),{'a':1})
        with self.assertRaises(ValueError):
            solve_dc((Resistor('a','0',10),),{'a':1,'0':0})
        result = solve_dc((Resistor('a','0',10),),{'a':1,'0':-1})
        self.assertTrue(result.verified)
        with self.assertRaises(ValueError):
            solve_dc((Resistor('a','0',10),),{'missing':1})


class VersionedClaimsTests(unittest.TestCase):
    def test_revision_dependencies_refutation_and_impact(self):
        ledger = ClaimLedger()
        a = ClaimRevision('A','Model A','proposed')
        aid = ledger.append(a)
        b = ClaimRevision('B','Depends on model A','supported', ('experiment:01',), (aid,))
        bid = ledger.append(b)
        refuted = ClaimRevision('A','Model A','refuted', ('counterexample:02',), previous=aid)
        rid = ledger.append(refuted)
        self.assertEqual(ledger.latest('A'),refuted)
        self.assertEqual(set(ledger.affected_by(aid)), {bid,rid})
        self.assertEqual(ledger.revisions[0],a)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'claims.jsonl'
            ledger.save(path)
            self.assertEqual(ClaimLedger.load(path).revisions,ledger.revisions)
            with self.assertRaises(FileExistsError):
                ledger.save(path)
            path.write_text(path.read_text().replace('Model A','Model Z'))
            with self.assertRaises(ValueError):
                ClaimLedger.load(path)

    def test_missing_evidence_stale_revision_or_dependency(self):
        with self.assertRaises(ValueError):
            ClaimRevision('A','Statement','supported')
        ledger = ClaimLedger((ClaimRevision('A','Statement','proposed'),))
        with self.assertRaises(ValueError):
            ledger.append(ClaimRevision('A','Changed','proposed'))
        with self.assertRaises(ValueError):
            ledger.append(ClaimRevision('B','Statement','proposed',dependencies=('missing',)))
        self.assertEqual(len(ledger.revisions),1)
