from fractions import Fraction as F
from pathlib import Path
import copy
import hashlib
import json
import sys
import tempfile
import unittest

from nablamath.forge.task_spec import FAMILIES,TaskSpec
from nablamath.forge.reverse_builder import generate_task,generate
from nablamath.forge.solvers import solve_task
from nablamath.forge.sampling import sampling_plan
from nablamath.forge.deduplicate import SemanticIndex,semantic_fingerprint
from nablamath.forge.difficulty import measure,calibrate,validate_calibration
from nablamath.forge.factory import run_factory,verify_factory
from nablamath.verify.trace import verify_candidate,build_trace,VerificationTrace
from nablamath.datasets.splits import SplitPolicy,assign_splits,audit_splits
from nablamath.core.semantic_ir import fingerprint,canonical_json
from nablamath.cli import main


class InverseConstructorsTests(unittest.TestCase):
    def test_all_eight_families_multiple_seeds_sizes_and_independent_strategies(self):
        for family in FAMILIES:
            for size in (1,3,8):
                for seed in (0,17,42):
                    with self.subTest(family=family,size=size,seed=seed):
                        generated=generate_task(family,seed,size)
                        self.assertEqual(generated,generate_task(family,seed,size))
                        self.assertEqual(TaskSpec.from_data(generated.task.to_data()),generated.task)
                        self.assertTrue(verify_candidate(generated.task,generated.witness).valid)
                        for strategy in ('exact','alternate'):
                            answer=solve_task(generated.task,strategy)
                            self.assertTrue(verify_candidate(generated.task,answer).valid,(strategy,answer))

    def test_legacy_seed_and_witness_compatibility(self):
        for family in ('linear_system','polynomial_integral'):
            old=generate(family,42)
            new=generate_task(family,42)
            self.assertEqual(old.task,new.task.legacy())
            key='solution' if family=='linear_system' else 'coefficients'
            self.assertEqual(old.witness,tuple(F(v) for v in new.witness[key]))
            self.assertEqual(old.generator_version,'inverse-v1')

    def test_problem_and_witness_are_defensive_copies(self):
        generated=generate_task('linear_system',42)
        before=generated.task.content_id
        generated.task.problem['rhs'][0]='999'
        generated.witness['solution'][0]='999'
        self.assertEqual(generated.task.content_id,before)
        self.assertTrue(verify_candidate(generated.task,generated.witness).valid)
        with self.assertRaises(ValueError):
            TaskSpec('linear_system',{'matrix':[[1]],'rhs':[1]},1,schema_version=2)
        with self.assertRaises(ValueError):
            TaskSpec('stationary_markov',{'transition':[['1/2']]},1)

    def test_known_answers_and_adversarial_candidates(self):
        examples=[
          ('polynomial_integral',{'coefficients':[0,0,0,0]}),('factored_polynomial',{'roots':[99,99,99]}),
          ('linear_system',{'solution':[99,99,99]}),('prescribed_spectrum',{'eigenvalues':[1,2,3],'eigenvectors':[[0]*3]*3}),
          ('convex_quadratic',{'solution':[99,99,99]}),('stationary_markov',{'stationary':[1,0,0]}),
          ('polynomial_identity',{'expression':{'kind':'number','numerator':999,'denominator':1}}),
          ('counterexample',{'assignment':{'x':99}})]
        for family,candidate in examples:
            with self.subTest(family=family):
                self.assertFalse(verify_candidate(generate_task(family,42).task,candidate).valid)
        task=TaskSpec('convex_quadratic',{'matrix':[['-1']],'linear':['0'],'constant':'0'},1)
        self.assertFalse(verify_candidate(task,{'solution':['0']}).valid)
        # Stationarity alone must not accept a reducible, non-unique chain.
        task=TaskSpec('stationary_markov',{'transition':[['1','0'],['0','1']]},2)
        self.assertFalse(verify_candidate(task,{'stationary':['1/2','1/2']}).valid)

    def test_trace_reexecution_rejects_rehashed_lies(self):
        generated=generate_task('linear_system',42)
        row=build_trace(generated.task,solve_task(generated.task)).to_data()
        self.assertTrue(VerificationTrace.from_data(row).replay())
        row['candidate']['solution'][0]='999'
        row.pop('trace_id');row['trace_id']=fingerprint(row)
        with self.assertRaises(ValueError):
            VerificationTrace.from_data(row)


class SamplingSplitsAndDifficultyTests(unittest.TestCase):
    def test_balanced_plan_and_semantic_deduplication(self):
        plan=list(sampling_plan(24,42,FAMILIES,(2,3,4)))
        self.assertEqual(plan,list(sampling_plan(24,42,FAMILIES,(2,3,4))))
        self.assertEqual({f for f,_,_ in plan},set(FAMILIES))
        self.assertEqual({size for _,_,size in plan},{2,3,4})
        a=TaskSpec('linear_system',{'matrix':[[1,0],[0,1]],'rhs':[2,3]},2)
        b=TaskSpec('linear_system',{'matrix':[[2,0],[0,3]],'rhs':[4,9]},2)
        self.assertNotEqual(a.content_id,b.content_id)
        self.assertEqual(semantic_fingerprint(a),semantic_fingerprint(b))
        index=SemanticIndex();self.assertTrue(index.add(a));self.assertFalse(index.add(b))
        self.assertEqual(index.report()['duplicates'],1)
        with self.assertRaises(ValueError):
            list(sampling_plan(2,42,('unknown',)))

    def test_family_holdout_and_contamination_detection(self):
        tasks=[generate_task(f,seed,size).task for f in FAMILIES for seed in (1,2) for size in (2,3)]
        assignments=assign_splits(tasks)
        self.assertEqual(set(assignments.values()),{'train','validation','test'})
        for family in FAMILIES:
            self.assertEqual(len({assignments[t.content_id] for t in tasks if t.family==family}),1)
        partitions={name:[t for t in tasks if assignments[t.content_id]==name] for name in ('train','validation','test')}
        self.assertTrue(audit_splits(partitions)['clean'])
        partitions['test'].append(partitions['train'][0])
        self.assertFalse(audit_splits(partitions)['clean'])
        with self.assertRaises(ValueError):
            SplitPolicy(80,20,20)

    def test_calibration_runs_two_solvers_and_is_not_size_only(self):
        tasks=[generate_task(f,17,3).task for f in FAMILIES]
        report=calibrate(tasks)
        self.assertEqual(report['outcomes'],{'completed':16})
        self.assertTrue(validate_calibration(report,tasks))
        self.assertGreater(len({row['label'] for row in report['ratings'].values()}),1)
        self.assertTrue(all(row['executed_python_lines']>0 for row in report['observations']))
        report['ratings'][tasks[0].content_id]['label']='invented'
        report.pop('calibration_id');report['calibration_id']=fingerprint(report)
        self.assertFalse(validate_calibration(report,tasks))

    def test_resource_budget_and_tracer_restoration(self):
        task=generate_task('linear_system',42).task
        previous=sys.gettrace()
        observation=measure(task,budget=1)
        self.assertEqual(observation['status'],'budget_exhausted')
        self.assertIs(sys.gettrace(),previous)
        self.assertIsNone(observation['verification'])
        self.assertEqual(measure(task,budget=100000)['status'],'completed')


class FactoryIntegrationTests(unittest.TestCase):
    def test_factory_reproducibility_rights_splits_and_reexecution(self):
        with tempfile.TemporaryDirectory() as directory:
            a,b=Path(directory)/'a',Path(directory)/'b'
            report=run_factory(a,count=24,seed=42,license_id='MIT',provenance='synthetic unit test')
            run_factory(b,count=24,seed=42,license_id='MIT',provenance='synthetic unit test')
            self.assertEqual(report['unique_semantics'],24)
            self.assertEqual(report['splits'],{'train':18,'validation':3,'test':3})
            self.assertTrue(verify_factory(a))
            self.assertEqual((a/'manifest.json').read_bytes(),(b/'manifest.json').read_bytes())
            with self.assertRaises(FileExistsError):
                run_factory(a,count=8,license_id='MIT',provenance='test')
            records=[json.loads(line) for line in (a/'records.jsonl').read_text().splitlines()]
            records[0]['solution_trace']['candidate']['coefficients'][0]='999'
            # Constants of integration can change; corrupt a nonconstant coefficient.
            records[0]['solution_trace']['candidate']['coefficients'][1]='999'
            (a/'records.jsonl').write_text(''.join(canonical_json(r)+'\n' for r in records))
            manifest=json.loads((a/'manifest.json').read_text())
            manifest['files']['records.jsonl']=hashlib.sha256((a/'records.jsonl').read_bytes()).hexdigest()
            (a/'manifest.json').write_text(canonical_json(manifest))
            self.assertFalse(verify_factory(a))

    def test_calibrated_factory_and_cli_verifier(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'calibrated'
            self.assertEqual(main(['forge',str(root),'--all-families','--count','8','--size','2','--calibrate',
                                   '--license','MIT','--provenance','synthetic test']),0)
            self.assertTrue((root/'calibration.json').is_file())
            self.assertEqual(main(['check-bundle',str(root)]),0)
            self.assertEqual(main(['forge',str(Path(directory)/'bad'),'--sizes','2','3',
                                   '--license','MIT','--provenance','test']),1)
            self.assertFalse((Path(directory)/'bad').exists())
