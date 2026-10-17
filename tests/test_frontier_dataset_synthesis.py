"""Adversarial and inverse-replay tests for synthetic mathematical records."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

try:
    import sympy
except ImportError:
    sympy=None

src=Path(__file__).resolve().parents[1] / 'tools' / 'generate_frontier_1000.py'
if not src.is_file():
    src=Path(__file__).with_name('generate_frontier_1000.py')
frontier=None
if sympy is not None:
    spec=importlib.util.spec_from_file_location('frontier_generator',src)
    frontier=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(frontier)


@unittest.skipUnless(sympy is not None, "Install nablamath[research] for exact symbolic checks")
class FrontierTests(unittest.TestCase):
    def test_native_canonical_contract_is_deterministic(self):
        self.assertEqual(frontier.fingerprint({'z':1,'a':'á'}),
                         hashlib.sha256('{"a":"\\u00e1","z":1}'.encode()).hexdigest())

    def test_exact_inverse_construction_each_family(self):
        for i in range(1,51):
            with self.subTest(i=i):
                record=frontier.create_record(i,frontier.portable_receipt,frontier.portable_verify,'portable_reference_contract')
                self.assertTrue(all(record['checks'].values()))
                self.assertEqual(frontier.fingerprint({k:v for k,v in record.items() if k not in ('receipt','record_sha256')}), record['record_sha256'])
                self.assertTrue(frontier.portable_verify(record['receipt']))
                replay=frontier.create_record(i,frontier.portable_receipt,frontier.portable_verify,'portable_reference_contract')
                self.assertEqual(record,replay)

    def test_hash_and_result_tamper_fail_closed(self):
        record=frontier.create_record(3,frontier.portable_receipt,frontier.portable_verify,'portable_reference_contract')
        forged=copy.deepcopy(record['receipt'])
        forged['result']['solution']='fake proof'
        self.assertFalse(frontier.portable_verify(forged))
        forged=copy.deepcopy(record['receipt'])
        forged['content_id']='0'*64
        self.assertFalse(frontier.portable_verify(forged))

    def test_one_thousand_five_domains_and_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            a=Path(directory)/'a.txt';b=Path(directory)/'b.txt'
            ma=frontier.generate(25,a,portable=True)
            mb=frontier.generate(25,b,portable=True)
            self.assertEqual(a.read_bytes(),b.read_bytes())
            self.assertEqual(ma,mb)
            self.assertEqual(sum(ma['domains'].values()),25)
            self.assertEqual(len(ma['domains']),5)
            self.assertTrue(ma['unique_record_hashes'])
            self.assertEqual(ma['file_sha256'],hashlib.sha256(a.read_bytes()).hexdigest())
            self.assertEqual(a.read_text().count('PROBLEM_ID:'),25)

    def test_portable_explicit_and_native_never_silently_fallback(self):
        make,verify,backend=frontier.receipt_backend(True)
        self.assertEqual(backend,'portable_reference_contract')
        self.assertTrue(verify(make('t',{}, {}, metadata={})))
        try:
            import nablamath
        except ImportError:
            with self.assertRaises(ImportError):frontier.receipt_backend(False)

    def test_claims_are_scoped_not_fraudulent(self):
        for i in range(1,6):
            record=frontier.create_record(i,frontier.portable_receipt,frontier.portable_verify,'portable_reference_contract')
            self.assertFalse(record['receipt']['formal_proof'])
            self.assertFalse(record['receipt']['replayable'])
            self.assertEqual(record['receipt']['metadata']['proof_status'],'CHECKED_EXACT_CONSTRUCTION_NOT_FORMAL_PROOF')

    def test_reject_invalid_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            for count in (0,-1,100001,True):
                with self.subTest(count=count),self.assertRaises(ValueError):
                    frontier.generate(count,Path(directory)/'wrong.txt',portable=True)

    def test_full_replay_and_byte_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'data.txt'
            frontier.generate(10,path,portable=True)
            self.assertTrue(frontier.verify_dataset(path,portable=True))
            path.write_bytes(path.read_bytes().replace(b'ENUNCIADO',b'ENUNCIAD0',1))
            with self.assertRaises(ValueError):
                frontier.verify_dataset(path,portable=True)

    def test_native_receipt_integration_when_installed(self):
        try:
            make,verify,backend=frontier.receipt_backend(False)
        except ImportError:
            self.skipTest('Nabla is unavailable in the offline runner')
        self.assertEqual(backend,'native_nablamath')
        for i in range(1,6):
            record=frontier.create_record(i,make,verify,backend)
            self.assertTrue(verify(record['receipt']))

    def test_finite_field_rational_points(self):
        for i in range(4,55,5):
            domain,params,problem,steps,solution,checks=frontier.FAMILIES[3]((i-1)//5,1000000+37*i)
            self.assertTrue(checks['rational_points_enumerated'])
            self.assertLessEqual(params['degree'],7)
            self.assertIn('F_',solution)

    def test_ramanujan_never_claims_exact_infinite_value(self):
        record=frontier.create_record(5,frontier.portable_receipt,frontier.portable_verify,'portable_reference_contract')
        self.assertIn('limite certificado', ' '.join(record['derivation']))
        self.assertIn('≤',record['solution'])

    def test_sde_has_necessary_positive_recurrence_condition(self):
        for j in range(200):
            result=frontier.ito_fokker_planck(j,1000000+j*37)
            self.assertTrue(all(result[-1].values()))
            alpha,beta,sigma=result[1]['alpha'],result[1]['beta'],result[1]['sigma']
            self.assertGreater(2*alpha,sigma*sigma)


if __name__=='__main__':unittest.main()