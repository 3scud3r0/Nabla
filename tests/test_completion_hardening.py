"""Cross-phase acceptance of actual numerical, streaming and dependency behavior."""
import copy
import io
import math
from pathlib import Path
import tempfile
import unittest

from nablamath.core.semantic_ir import canonical_json
from nablamath.worlds.integrators import integrate_adaptive
from nablamath.worlds import ModelSpec, simulate_adaptive
from nablamath.datasets.serializer import iter_load, write_atomic
from nablamath.forge.reverse_builder import generate_task
from nablamath.datasets.schema import make_record


def dataset_record():
    generated = generate_task('linear_system', 71, 2)
    return make_record(generated.task, generated.witness, license_id='CC0-1.0',
                       provenance='test fixture seed 71', scope='exact rational', limitations='synthetic')


class AdaptiveTests(unittest.TestCase):
    def test_tolerance_refinement_and_rejected_steps(self):
        for model in (ModelSpec('exponential_decay', (3.,), 2., 4.),
                      ModelSpec('harmonic_oscillator', (2., 1.), 3., 5.)):
            loose = simulate_adaptive(model, atol=1e-5, rtol=1e-3, initial_step=model.duration)
            tight = simulate_adaptive(model, atol=1e-12, rtol=1e-10, initial_step=model.duration)
            self.assertLess(tight['max_trajectory_reference_error'], loose['max_trajectory_reference_error'])
            self.assertLess(tight['max_trajectory_reference_error'], 1e-8)
            self.assertGreater(tight['rejected_steps'], 0)
            self.assertEqual(tight['trajectory'][-1][0], model.duration)
            self.assertLessEqual(tight['max_accepted_local_error_ratio'], 1)
            self.assertFalse(tight['global_error_certified'])

    def test_budget_bad_derivative_and_bad_parameters(self):
        with self.assertRaisesRegex(ValueError, 'esgotado'):
            integrate_adaptive(lambda t,y: (-y[0],), (1.,), 0., 10., max_attempts=1)
        for derivative in (lambda t,y: (math.nan,), lambda t,y: (1., 2.)):
            with self.assertRaises(ValueError):
                integrate_adaptive(derivative, (1.,), 0., 1.)
        for options in ({'rtol': -1}, {'atol': 0}, {'initial_step': False}, {'max_attempts': True}):
            with self.assertRaises(ValueError):
                integrate_adaptive(lambda t,y:y, (1.,), 0., 1., **options)

    def test_calculator_replay_and_rc_units_oracle(self):
        from nablamath.calc.session import CalculationSession
        session = CalculationSession()
        calculation = session.execute('ode_adaptive', model='exponential_decay', initial=[1.], rtol=1e-9)
        request = calculation.to_data()['request']
        self.assertEqual(calculation.to_data(), session.replay_request(request).to_data())
        from nablamath.domains.circuits import rc_step, FARAD
        from nablamath.domains.contracts import OHM
        from nablamath.core.units import Quantity, VOLT, SECOND, METER
        from nablamath.knowledge.provenance_audit import replay_domain
        args = (Quantity(1000, OHM), Quantity('1/1000', FARAD), Quantity(5, VOLT),
                Quantity(0, VOLT), Quantity(1, SECOND))
        report = rc_step(*args, rtol=1e-10, atol=1e-12)
        self.assertAlmostEqual(report['outputs']['final_voltage'], 5*(1-math.exp(-1)), places=8)
        self.assertTrue(report['checks_passed'])
        self.assertTrue(replay_domain(report))
        with self.assertRaises(ValueError):
            rc_step(Quantity(1, METER), *args[1:])


class StreamingTests(unittest.TestCase):
    def test_stream_roundtrip_and_failure_atomicity(self):
        record = dataset_record()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'records.jsonl'
            stats = write_atomic(iter((record, record)), target)
            with target.open('rb') as stream:
                self.assertEqual(list(iter_load(stream)), [record, record])
            self.assertEqual(stats['bytes'], target.stat().st_size)
            original = target.read_bytes()
            with self.assertRaises(FileExistsError):
                write_atomic([record], target)
            self.assertEqual(target.read_bytes(), original)
            failed = Path(tmp)/'failed.jsonl'
            with self.assertRaises(ValueError):
                write_atomic([record, record], failed, max_records=1)
            self.assertFalse(failed.exists())
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ['records.jsonl'])

    def test_bounded_reads_utf8_and_invalid_solution(self):
        record = dataset_record().to_data()
        record['trace']['candidate']['solution'][0] = '999999'
        for data, options in ((b'\xff\n', {}), (b'\n', {}), (b'x'*100, {'max_line_bytes': 8}),
                              ((canonical_json(record)+'\n').encode(), {})):
            with self.assertRaises(ValueError):
                list(iter_load(io.BytesIO(data), **options))
        with self.assertRaises(ValueError):
            list(iter_load(io.BytesIO(b'')))


class BindingTests(unittest.TestCase):
    def test_agent_solve_then_verify_and_tamper_detection(self):
        from nablamath.agents import ScientificProposal, Action, Planner, Permissions, scientific_registry
        from nablamath.agents.planner import verify_run
        task = generate_task('linear_system', 22, 2).task.to_data()
        proposal = ScientificProposal('Solve and independently verify', (
            Action('solve1', 'solve', canonical_json({'task': task})),
            Action('check1', 'verify', canonical_json({'task': task, 'candidate':
                {'$result': {'action': 'solve1', 'path': ['candidate']}}}), ('solve1',))),
            'Trusted registered tools; no discovery claim')
        report = Planner(scientific_registry(), Permissions(frozenset({'solve', 'verify'}))).run(proposal)
        self.assertTrue(report['completed'])
        self.assertTrue(verify_run(report))
        self.assertTrue(report['receipts'][1]['result']['verification']['valid'])
        tampered = copy.deepcopy(report)
        tampered['receipts'][1]['resolved_arguments']['candidate'] = {}
        self.assertFalse(verify_run(tampered))
        with self.assertRaises(ValueError):
            ScientificProposal('bad', (Action('a', 'verify', canonical_json({'task':task,
                'candidate':{'$result':{'action':'unknown','path':[]}}})),), 'bounded')

    def test_references_reject_missing_keys_and_attributes(self):
        from nablamath.agents.bindings import resolve
        for path in (['missing'], ['__class__'], [-1]):
            with self.assertRaises(ValueError):
                resolve({'$result': {'action':'a', 'path':path}}, {'a': {'value': 1}})

    def test_formal_question_and_domain_binding(self):
        from nablamath.formal.statement import FormalStatement
        from nablamath.formal.translation_review import bind_translation, verify_translation_binding
        statement = FormalStatement.equality('x/x', '1')
        binding = bind_translation('x/x=1 where x is nonzero', statement,
                                   task_id='fixture', reviewer='declared reviewer', notes='domain reviewed', accepted=True)
        self.assertTrue(verify_translation_binding(binding, question=binding['question'], statement=statement, task_id='fixture'))
        self.assertFalse(verify_translation_binding(binding, question='x/x=1 for every x', statement=statement, task_id='fixture'))
        self.assertFalse(verify_translation_binding(binding, question=binding['question'], statement=FormalStatement.equality('x', 'x'), task_id='fixture'))
        self.assertFalse(binding['reviewer_identity_authenticated'])


class DocumentTableTests(unittest.TestCase):
    def test_three_formats_schema_and_real_pdf(self):
        from nablamath.documents.document_model import Table, Section, Document
        from nablamath.documents.exporters import to_html, to_latex, to_typst
        from nablamath.documents.publication import publish, verify_publication
        import hashlib
        evidence = b'{"value":"1/2"}\n'
        digest = hashlib.sha256(evidence).hexdigest()
        table = Table('Measured & calculated', ('Method', 'Value'), (('A < B', '1/2'),), (digest,))
        document = Document('Table example', (Section('Results', 'Synthetic example', tables=(table,)),))
        self.assertEqual(document.to_data()['schema_version'], 2)
        self.assertEqual(Document.from_data(document.to_data()), document)
        self.assertIn('A &lt; B', to_html(document))
        self.assertIn('Measured \\& calculated', to_latex(document))
        self.assertIn('#figure(table(', to_typst(document))
        self.assertEqual(Document('Old', (Section('S','T'),)).to_data()['schema_version'], 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'e.json').write_bytes(evidence)
            manifest = publish(document, root/'paper', evidence_sources={digest:root/'e.json'}, require_evidence=True)
            self.assertEqual(manifest['unresolved_evidence'], [])
            self.assertTrue(verify_publication(root/'paper'))
            # This environment has the optional real Typst compiler.
            import importlib.util
            if importlib.util.find_spec('typst'):
                publish(document, root/'pdf', pdf_backend='typst', evidence_sources={digest:root/'e.json'}, require_evidence=True)
                self.assertTrue((root/'pdf/document.pdf').read_bytes().startswith(b'%PDF-'))
        with self.assertRaises(ValueError):
            Table('ragged', ('A', 'B'), (('one',),))


class DiscoveryConstraintsTests(unittest.TestCase):
    def test_cost_changes_experiment_and_exclusions_are_preserved(self):
        from nablamath.discovery.hypothesis import Hypothesis
        from nablamath.discovery.experimental_design import propose_constrained_experiment
        models = (Hypothesis('x', 'bounded comparison'), Hypothesis('x*x', 'bounded comparison'))
        result = propose_constrained_experiment(models, [1,2,3], costs={1:1,2:1,3:100}, budget=2)
        self.assertEqual(result['selected']['x'], '2')
        self.assertEqual(result['skipped_constraints'], [{'x':'3','reason':'over_budget'}])
        self.assertFalse(result['experiment_performed'])
        none = propose_constrained_experiment(models,[1],costs={1:1},budget=2,excluded=[1])
        self.assertIsNone(none['selected'])


class SignedFederationTests(unittest.TestCase):
    def test_signature_pinning_tamper_revocation_and_rotation(self):
        try:
            import cryptography
        except ImportError:
            self.skipTest('federation optional dependency')
        from nablamath.knowledge.identity import (generate_signing_key, public_key_hex, sign_snapshot,
                                                   PeerKey, PeerTrust, verify_signed_snapshot)
        from nablamath.knowledge.federation import export_snapshot, SignedFederation
        from nablamath.knowledge.versioned_claims import ClaimLedger
        # Empty ledger is a valid transport fixture, not scientific evidence.
        snapshot = export_snapshot(ClaimLedger(), {}, peer_id='peer-a')
        private = generate_signing_key()
        public = public_key_hex(private)
        trust = PeerTrust([PeerKey('peer-a', public)])
        envelope = sign_snapshot(snapshot, private)
        self.assertTrue(verify_signed_snapshot(envelope, trust)['authenticated'])
        federation = SignedFederation(trust)
        federation.ingest(envelope)
        federation.ingest(envelope)
        self.assertEqual(len(federation.reconcile()['snapshot_ids']), 1)
        changed = copy.deepcopy(envelope); changed['snapshot']['peer_id']='peer-b'
        self.assertFalse(verify_signed_snapshot(changed, trust)['valid'])
        changed = copy.deepcopy(envelope); changed['signature']='00'*64
        self.assertFalse(verify_signed_snapshot(changed, trust)['valid'])
        trust.revoke('peer-a', public)
        with self.assertRaises(ValueError):
            federation.reconcile()
        with self.assertRaises(ValueError):
            trust.pin(PeerKey('peer-a', public))
        next_key = generate_signing_key()
        trust.pin(PeerKey('peer-a', public_key_hex(next_key)))
        rotated = sign_snapshot(snapshot, next_key)
        self.assertTrue(verify_signed_snapshot(rotated, PeerTrust.from_data(trust.to_data()))['valid'])
        self.assertFalse(verify_signed_snapshot(envelope, trust)['valid'])


class CertifiedCurveTests(unittest.TestCase):
    def test_bound_replay_and_rendered_bundle(self):
        from fractions import Fraction
        from nablamath.graphics.sampling import adaptive_function_scene
        from nablamath.graphics.artifacts import replay_model, export_scene, verify_scene_bundle
        from nablamath.expression import evaluate, parse_expr
        import json
        scene = adaptive_function_scene('x*x*x', xmin=-1, xmax=2, tolerance='1/1000')
        model = json.loads(scene.model_json)
        expression = parse_expr('x*x*x')
        for segment in model['segments']:
            a, b, bound = (Fraction(segment[key]) for key in ('left','right','vertical_error_bound'))
            self.assertLessEqual(bound, Fraction(1,1000))
            for i in range(11):
                x = a+(b-a)*i/10
                linear = evaluate(expression,{'x':a})+(x-a)/(b-a)*(evaluate(expression,{'x':b})-evaluate(expression,{'x':a}))
                self.assertLessEqual(abs(evaluate(expression,{'x':x})-linear), bound)
        self.assertTrue(replay_model(scene)['valid'])
        try:
            import PIL
        except ImportError:
            return  # Exact bound and replay do not require optional raster backend.
        with tempfile.TemporaryDirectory() as tmp:
            export_scene(scene, Path(tmp)/'curve')
            self.assertTrue(verify_scene_bundle(Path(tmp)/'curve'))

    def test_poles_and_exhausted_budget_fail_closed(self):
        from nablamath.graphics.sampling import adaptive_function_scene
        with self.assertRaises(ValueError):
            adaptive_function_scene('1/x', xmin=-1, xmax=1)
        with self.assertRaises(ValueError):
            adaptive_function_scene('x*x', tolerance='1/100000000', max_segments=2)


class EvolutionEffectTests(unittest.TestCase):
    def test_significance_does_not_imply_useful_effect(self):
        from nablamath.evolution.statistical_tests import practical_effect, paired_sign_test
        from nablamath.evolution.proposal_validator import EvaluationContract
        baseline = [1.] * 16
        barely = [1.-1e-10] * 16
        self.assertTrue(paired_sign_test(barely, baseline)['significant'])
        self.assertFalse(practical_effect(barely, baseline, minimum_relative_reduction=.01)['passed'])
        self.assertTrue(practical_effect([.5]*16, baseline, minimum_relative_reduction=.1)['passed'])
        self.assertFalse(practical_effect([0.]*16,[0.]*16)['passed'])
        with self.assertRaises(ValueError):
            EvaluationContract(minimum_relative_reduction=-1)

    def test_release_gate_enforces_frozen_practical_threshold(self):
        from nablamath.evolution.policy_genome import PolicyGenome
        from nablamath.evolution.proposal_validator import EvaluationContract
        from nablamath.evolution.holdout_manager import HoldoutManager
        from nablamath.evolution.release_gate import release_gate
        baseline = PolicyGenome('rk4', 80)
        candidate = PolicyGenome('rk4',100,baseline.genome_id,1)
        calibration = (ModelSpec('exponential_decay',(1.,),1.,1.),)
        holdout = tuple(ModelSpec('exponential_decay',(1.+i/10,),1.,1.) for i in range(1,9))
        contract = EvaluationContract(minimum_relative_reduction=.99)
        with tempfile.TemporaryDirectory() as tmp:
            manager = HoldoutManager(Path(tmp)/'vault.db', contract)
            # Use the same public holdout registration/evaluation APIs as the lab.
            token = manager.register(holdout, calibration, label='effect-fixture')
            receipt = manager.evaluate_once(token, candidate, baseline, calibration)
            decision = release_gate(receipt, contract, manager=manager)
            self.assertFalse(decision['accepted'])
            self.assertFalse(decision['practical_effect']['passed'])


class BenchmarkAnalysisTests(unittest.TestCase):
    def test_independent_results_rechecked_and_unsupported_separate(self):
        import json
        from nablamath.benchmarks.analysis import analyze_benchmark
        from nablamath.core.semantic_ir import fingerprint
        report = json.loads((Path(__file__).parents[1]/'benchmarks/results/independent-solvers-2026-10.json').read_text(encoding='utf-8'))
        result = analyze_benchmark(report)
        z3 = next(s for s in result['strata'] if s['backend']=='z3' and s['family']=='*')
        self.assertEqual(z3['supported_count'],18)
        self.assertEqual(z3['supported_success_rate'],1.)
        self.assertLess(z3['success_wilson_95'][0],1.)
        self.assertFalse(result['expert_difficulty_established'])
        forged = copy.deepcopy(report)
        target = next(r for r in forged['tasks'] if r['task']['family']=='linear_system')
        target['results']['sympy']['candidate']['solution'][0] = '999999'
        forged['benchmark_id'] = fingerprint({k:v for k,v in forged.items() if k!='benchmark_id'})
        with self.assertRaises(ValueError):
            analyze_benchmark(forged)
