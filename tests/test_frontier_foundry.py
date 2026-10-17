"""Executable independent contracts for Nabla Frontier Foundry v3."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import sympy as sp

MODULE = Path(__file__).resolve().parents[1] / 'tools' / 'frontier_foundry.py'
spec = importlib.util.spec_from_file_location('frontier_foundry', MODULE)
foundry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(foundry)


class FoundryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name) / 'frontier_100.txt'
        cls.manifest = foundry.build(100,cls.output,True)
        cls.records = [json.loads(x) for x in cls.output.with_suffix('.jsonl').read_text().splitlines()]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_families_and_100_substantive_compositions(self):
        self.assertEqual(len(self.records),100)
        self.assertEqual(len({r['grammar_signature'] for r in self.records}),100)
        self.assertEqual(len({r['domain'] for r in self.records}),10)
        self.assertEqual(self.manifest['distinct_operator_grammars'],100)
        self.assertTrue(all(len([s for s in r['operations'] if s.startswith('optional:')]) in (2,3) for r in self.records))

    def test_sealed_family_disjoint_split(self):
        tr={r['domain'] for r in self.records if r['split']=='train'}
        ev={r['domain'] for r in self.records if r['split']=='test_unseen_family'}
        self.assertEqual(len(tr),8)
        self.assertEqual(len(ev),2)
        self.assertFalse(tr & ev)
        self.assertEqual(self.manifest['train_count'],80)
        self.assertEqual(self.manifest['test_unseen_family_count'],20)

    def test_independent_checks_all_instances(self):
        self.assertTrue(all(all(c is True for c in r['validation_checks'].values()) for r in self.records))
        self.assertTrue(all(r['proof_status']=='INDEPENDENT_EXACT_CHECKS_NOT_FORMAL_PROOF' for r in self.records))

    def test_record_sha256(self):
        for r in self.records:
            x=dict(r);ident=x.pop('record_sha256'); receipt=x.pop('receipt')
            self.assertEqual(foundry.digest(x),ident)
            self.assertTrue(foundry.portable_verify(receipt))

    def test_exact_full_replay_and_manifest(self):
        self.assertTrue(foundry.verify_dataset(self.output,True))
        data=self.output.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),self.manifest['sha256'])

    def test_grade_all_families(self):
        for record in self.records:
            self.assertTrue(foundry.grade_answer(record['answer'],record['answer']))

    def test_grade_rational_equivalence(self):
        self.assertTrue(foundry.grade_answer({'a':'1/2','b':['2/4']},{'a':'2/4','b':['1/2']}))
        self.assertFalse(foundry.grade_answer({'a':'1/2'},{'a':0.5}))
        self.assertFalse(foundry.grade_answer({'a':1},{'a':True}))

    def test_adversarial_tampering_rejected_on_all_100(self):
        for record in self.records:
            self.assertFalse(foundry.grade_answer(record['answer'],foundry.mutate(record['answer'])))
            altered=copy.deepcopy(record['receipt'])
            altered['content_id']='0'*64
            self.assertFalse(foundry.portable_verify(altered))

    def test_reject_missing_and_extra_answer_keys(self):
        for r in self.records:
            bad=copy.deepcopy(r['answer']);bad.pop(next(iter(bad)))
            self.assertFalse(foundry.grade_answer(r['answer'],bad))
            bad=copy.deepcopy(r['answer']);bad['INJECTED']=True
            self.assertFalse(foundry.grade_answer(r['answer'],bad))

    def test_replay_rejects_corrupted_dataset(self):
        original=self.output.read_bytes()
        try:
            self.output.write_bytes(original+b'FALSE RESULTS')
            self.assertFalse(foundry.verify_dataset(self.output,True))
        finally:self.output.write_bytes(original)

    def test_replay_rejects_corrupted_manifest(self):
        p=Path(str(self.output)+'.manifest.json')
        original=p.read_bytes()
        try:
            m=json.loads(original);m['count']=99;p.write_text(foundry.canonical(m))
            self.assertFalse(foundry.verify_dataset(self.output,True))
        finally:p.write_bytes(original)

    def test_replay_rejects_corrupted_test_key(self):
        p=self.output.with_suffix('.eval_answer_key.jsonl')
        original=p.read_bytes()
        try:
            p.write_bytes(original+b'corrupted')
            self.assertFalse(foundry.verify_dataset(self.output,True))
        finally:p.write_bytes(original)

    def test_model_scoring_and_failure_curriculum(self):
        preds=Path(self.temp.name)/'predictions.jsonl'
        rows=[]
        for i,r in enumerate(self.records[:10]):
            rows.append({'problem_id':r['problem_id'],'answer':r['answer'] if i==0 else foundry.mutate(r['answer'])})
        preds.write_text(''.join(foundry.canonical(x)+'\n' for x in rows))
        grade=foundry.score_predictions(self.output.with_suffix('.jsonl'),preds)
        self.assertEqual(grade['attempted'],10)
        self.assertEqual(grade['passed'],1)
        self.assertEqual(sum(x['failed'] for x in grade['curriculum_failure_priorities']),9)

    def test_no_duplicate_predictions(self):
        preds=Path(self.temp.name)/'dupes.jsonl'
        p={'problem_id':self.records[0]['problem_id'],'answer':self.records[0]['answer']}
        preds.write_text(foundry.canonical(p)+'\n'+foundry.canonical(p)+'\n')
        with self.assertRaises(ValueError):foundry.score_predictions(self.output.with_suffix('.jsonl'),preds)

    def test_empty_predictions_rejected(self):
        preds=Path(self.temp.name)/'empty.jsonl';preds.write_text('')
        with self.assertRaises(ValueError):foundry.score_predictions(self.output.with_suffix('.jsonl'),preds)

    def test_all_split_prompts_have_no_answers(self):
        prompts=list(map(json.loads,self.output.with_suffix('.eval_prompts.jsonl').read_text().splitlines()))
        keys=list(map(json.loads,self.output.with_suffix('.eval_answer_key.jsonl').read_text().splitlines()))
        self.assertEqual(len(prompts),20)
        self.assertEqual(len(keys),20)
        self.assertTrue(all('answer' not in x and 'seed' not in x for x in prompts))
        self.assertEqual({x['problem_id'] for x in prompts},{x['problem_id'] for x in keys})

    def test_native_integration_if_installed(self):
        try:
            import nablamath
        except ImportError:
            self.skipTest('Native Nabla absent in offline test environment; required in CI')
        make,verify,mode=foundry.backend(True)
        self.assertEqual(mode,'native_nablamath')
        r=foundry.create_record(1,make,verify,mode)
        self.assertTrue(verify(r['receipt']))

    def test_bounds_and_no_fake_proofs(self):
        with self.assertRaises(ValueError):foundry.build(101,self.output,True)
        with self.assertRaises(ValueError):foundry.create_record(0,*foundry.backend(False))
        self.assertFalse(any(r['receipt'].get('formal_proof') for r in self.records))


if __name__=='__main__':unittest.main()