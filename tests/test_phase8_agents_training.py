from dataclasses import replace
import json
import time
import unittest
from nablamath.core.semantic_ir import canonical_json, fingerprint
from nablamath.forge.reverse_builder import generate_task
from nablamath.datasets.schema import make_record
from nablamath.datasets.multimodal import build_sample, MultimodalSample
from nablamath.datasets.alignments import validate_alignment
from nablamath.agents import Permissions, ScientificProposal as Proposal, Action, Planner, scientific_registry
from nablamath.agents.tool_registry import ToolRegistry, Tool
from nablamath.agents.planner import verify_run
from nablamath.training import fit_nearest_neighbor, evaluate, verify_evaluation, compare_evaluations, run_ablations
from nablamath.training.curriculum import curriculum


def sample(family, seed, split, **options):
    generated = generate_task(family, seed, 2)
    record = make_record(generated.task, generated.witness, license_id='CC0-1.0', provenance='test fixture',
                         scope='exact tasks', limitations='no external learning claim', split=split, **options)
    return build_sample(record, include_simulation=family=='polynomial_integral')


def slow_tool():
    time.sleep(5)
    return {'ok': True}


def oversized_tool():
    return {'data': 'x'*1000}


class SolverModel:
    content_id = 'independent-exact-solver-v2'
    def predict(self, inputs):
        from nablamath.forge.task_spec import TaskSpec
        from nablamath.forge.solvers import solve_task
        problem = next(m['content'] for m in inputs['modalities'] if m['kind']=='equation')
        # Inference receives the problem only, not a sample or target record.
        task = TaskSpec(inputs['family'], problem, inputs['size'])
        return solve_task(task)


class WrongModel:
    content_id = 'always-empty-v1'
    def predict(self, inputs):
        assert all(m['role']=='input' for m in inputs['modalities'])
        assert 'record' not in inputs and 'candidate' not in inputs
        return {}


class MultimodalTrainingTests(unittest.TestCase):
    def cohorts(self):
        train = tuple(sample('polynomial_integral', seed, 'train') for seed in (5,9,18))
        heldout = tuple(sample('linear_system', seed, 'test') for seed in (2,8,19))
        return train, heldout

    def test_alignment_recomputes_contents_and_no_target_leakage(self):
        s = sample('polynomial_integral', 7, 'train')
        self.assertTrue(validate_alignment(s))
        self.assertEqual({m['kind'] for m in s.to_data()['modalities']},
                         {'text','equation','diagram','proof','simulation','reasoning'})
        self.assertEqual({m['kind'] for m in s.inputs()['modalities']}, {'text','equation','diagram'})
        with self.assertRaises(ValueError):
            s.inputs(('proof',))
        forged = s.to_data()
        forged['modalities'][0]['content'] = 'different question'
        forged['modalities'][0]['content_id'] = fingerprint({k:v for k,v in forged['modalities'][0].items() if k!='content_id'})
        self.assertFalse(validate_alignment(forged))
        self.assertLess(next(m['content']['absolute_error'] for m in s.to_data()['modalities'] if m['kind']=='simulation'), 1e-7)

    def test_actual_training_exact_grading_and_negative_gain(self):
        train, heldout = self.cohorts()
        model = fit_nearest_neighbor(curriculum(train))
        report = evaluate(model, heldout, training_samples=train, benchmark_name='unseen-family-fixture')
        self.assertEqual(report['total'], 3)
        self.assertTrue(verify_evaluation(report, heldout))
        good = evaluate(SolverModel(), heldout, training_samples=train, benchmark_name='unseen-family-fixture')
        self.assertEqual(good['successes'], 3)
        wrong = evaluate(WrongModel(), heldout, training_samples=train, benchmark_name='unseen-family-fixture')
        comparison = compare_evaluations(good, wrong)
        self.assertEqual(comparison['accuracy_gain'], -1)
        self.assertTrue(comparison['negative_or_zero_result_retained'])
        forged = dict(good); forged['successes'] = 0
        forged['evaluation_id'] = fingerprint({k:v for k,v in forged.items() if k!='evaluation_id'})
        self.assertFalse(verify_evaluation(forged, heldout))
        self.assertEqual(report['external_count'], 0)

    def test_contamination_and_holdout_protection(self):
        train, heldout = self.cohorts()
        with self.assertRaises(ValueError):
            fit_nearest_neighbor(heldout)
        with self.assertRaises(ValueError):
            curriculum(heldout)
        leaked = build_sample(train[0].record.with_split('test'))
        with self.assertRaises(ValueError):
            evaluate(WrongModel(), [leaked], training_samples=train, benchmark_name='leak')
        with self.assertRaises(ValueError):
            evaluate(WrongModel(), [heldout[0],heldout[0]], training_samples=train, benchmark_name='duplicate')

    def test_ablation_retrains_same_cohorts_and_retains_all_reports(self):
        train, heldout = self.cohorts()
        report = run_ablations(train, heldout, benchmark_name='ablation-fixture')
        self.assertEqual(set(report['reports']), {'all','text_only','without_diagram','diagram_only'})
        self.assertFalse(report['selection_performed'])
        for evaluation in report['reports'].values():
            self.assertTrue(verify_evaluation(evaluation, heldout))
        external = sample('linear_system', 41, 'test', origin='external', synthetic=False)
        evaluated = evaluate(WrongModel(), [external], training_samples=train, benchmark_name='declared-import-fixture')
        self.assertEqual(evaluated['external_count'], 1)
        self.assertFalse(evaluated['provenance_independently_authenticated'])


class AgentTests(unittest.TestCase):
    def test_scientific_plan_receipts_and_roundtrip(self):
        generated = generate_task('linear_system', 19, 2)
        proposal = Proposal('Resolver e simular', (
            Action('solve1', 'solve', canonical_json({'task': generated.task.to_data()})),
            Action('world1', 'simulate', canonical_json({'name':'exponential_decay','initial':[1], 'steps':20}), ('solve1',)),
        ), 'Ferramentas delimitadas; não descoberta autônoma')
        self.assertEqual(proposal, Proposal.from_data(proposal.to_data()))
        report = Planner(scientific_registry(), Permissions(frozenset({'solve','simulate'}))).run(proposal)
        self.assertTrue(report['completed'])
        self.assertTrue(verify_run(report))
        self.assertTrue(report['receipts'][0]['result']['verification']['valid'])
        report['receipts'][0]['result'] = {'forged':True}
        self.assertFalse(verify_run(report))
        receipt = report['receipts'][0]
        receipt['receipt_id'] = fingerprint({k:v for k,v in receipt.items() if k!='receipt_id'})
        self.assertFalse(verify_run(report))

    def test_preflight_permissions_cycles_and_call_budget(self):
        proposal = Proposal('Q', (Action('a','shell','{}'),), 'L')
        with self.assertRaises(PermissionError):
            Planner(scientific_registry(), Permissions(frozenset({'solve'}))).run(proposal)
        with self.assertRaises(ValueError):
            Proposal('Q', (Action('a','solve','{}', ('b',)), Action('b','solve','{}', ('a',))), 'L')
        with self.assertRaises(ValueError):
            Proposal('Q', (Action('a','solve','[]'),), 'L')

    def test_timeout_stops_worker_and_output_budget(self):
        registry = ToolRegistry((Tool('slow',slow_tool,frozenset()), Tool('large',oversized_tool,frozenset())))
        permissions = Permissions(frozenset({'slow','large'}), timeout_seconds=.2, max_output_bytes=100)
        start = time.monotonic()
        with self.assertRaises(TimeoutError):
            registry.execute('slow',{},permissions)
        self.assertLess(time.monotonic()-start, 2)
        with self.assertRaises(ValueError):
            registry.execute('large',{},replace(permissions, timeout_seconds=3))
