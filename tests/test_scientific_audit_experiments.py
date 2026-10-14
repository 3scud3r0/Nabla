import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from nablamath.forge.reverse_builder import generate_task
from nablamath.verify.trace import verify_candidate


@unittest.skipUnless(importlib.util.find_spec('sympy'),'Optional independent SymPy solver')
class IndependentSolverTests(unittest.TestCase):
    def test_all_eight_families_are_checked_with_independent_sympy(self):
        from nablamath.forge.task_spec import FAMILIES
        from nablamath.benchmarks.independent import _independent_call
        for family in FAMILIES:
            task=generate_task(family,79,2).task
            with self.subTest(family=family):
                result=_independent_call(task.to_data(),'sympy')
                self.assertEqual(result['status'],'solved')
                self.assertTrue(verify_candidate(task,result['candidate']).valid)


@unittest.skipUnless(importlib.util.find_spec('numpy'),'Optional open numeric neural model')
class ControlledLearningTests(unittest.TestCase):
    def test_real_training_balanced_protocol_saved_weights_and_prediction_replay(self):
        from nablamath.training.controlled_experiment import ArithmeticExample as E,controlled_experiment,verify_experiment_artifacts
        train=tuple(E('two times '+str(i),2*i,'unit fixture','train') for i in range(1,10))
        test=tuple(E('two times '+str(i),2*i,'unit fixture','test') for i in range(10,13))
        augmentation=tuple(E('double '+str(i),2*i,'synthetic unit fixture','augmentation') for i in range(1,10))
        with tempfile.TemporaryDirectory() as tmp:
            report=controlled_experiment(train,test,augmentation,seeds=(17,23),steps=10,output_directory=tmp)
            self.assertTrue(report['same_optimizer_steps_and_initialization'])
            self.assertFalse(report['external_evaluation'])
            self.assertTrue(verify_experiment_artifacts(report,test,tmp))
            self.assertEqual(len(list(Path(tmp).glob('*.npz'))),4)
            protocol=json.loads((Path(tmp)/'protocol.json').read_text(encoding='utf-8'))
            self.assertEqual(protocol['steps'],10)
            report['mean_accuracy_gain']=99
            self.assertFalse(verify_experiment_artifacts(report,test,tmp))
        with self.assertRaises(ValueError):controlled_experiment(train,test,tuple(E(e.question,e.answer,'leak','augmentation') for e in test),steps=1)

    def test_generation_is_independently_verified_and_test_labels_cannot_train(self):
        from nablamath.training.controlled_experiment import nabla_augmentation,OpenNumericMLP,ArithmeticExample
        rows=nabla_augmentation(16)
        self.assertEqual(len({r.semantic_id for r in rows}),16)
        with self.assertRaises(ValueError):OpenNumericMLP(seed=1).fit([ArithmeticExample('test',1,'test','test')],steps=1)
