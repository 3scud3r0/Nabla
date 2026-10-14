from dataclasses import replace
from fractions import Fraction as F
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from nablamath.core.semantic_ir import fingerprint,canonical_json
from nablamath.expression import parse_expr
from nablamath.formal.statement import Predicate,FormalStatement
from nablamath.formal.lean_bridge import translate_statement
from nablamath.formal.translation_review import review_translation
from nablamath.formal.lean_checker import find_lake,check_lean,prove_statement
from nablamath.formal.smt_bridge import solve_statement
from nablamath.verify.certificate import make_formal_certificate,verify_formal_certificate
from nablamath.falsifier.shrink import shrink_counterexample
from nablamath.falsifier.search import investigate
from nablamath.cli import main

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'lean'
MATHLIB_READY=(PROJECT/'.lake/packages/mathlib/.lake/build/lib/lean/Mathlib/Tactic/NormNum.olean').is_file()
Z3_AVAILABLE=importlib.util.find_spec('z3') is not None


class TypedFormalTranslationTests(unittest.TestCase):
    def test_explicit_domain_and_roundtrip(self):
        statement=FormalStatement.equality('(x+x)/x','2')
        self.assertEqual(statement.variables,('x',))
        self.assertEqual(len(statement.domain),1)
        self.assertEqual(FormalStatement.from_data(statement.to_data()),statement)
        translation=translate_statement(statement)
        self.assertIn('h0 : nabla_x ≠',translation.source)
        self.assertIn('#print axioms nabla_generated',translation.source)
        self.assertTrue(review_translation(translation).accepted)
        self.assertFalse(review_translation(translation).human_reviewed)
        for source in (translation.source.replace('= (2 : ℚ)','= (3 : ℚ)'),translation.source+'\naxiom invented : False\n'):
            self.assertFalse(review_translation(replace(translation,source=source)).accepted)

    def test_domain_zero_power_and_assumption_denominators(self):
        hypothesis=Predicate(parse_expr('1/y'),'gt',parse_expr('0'))
        statement=FormalStatement(Predicate(parse_expr('x**0'),'eq',parse_expr('1')),(hypothesis,))
        self.assertEqual(len(statement.domain),2)
        self.assertEqual(statement.variables,('x','y'))
        row=statement.to_data();row['domain_obligations']=[]
        with self.assertRaises(ValueError):FormalStatement.from_data(row)

    def test_closed_proof_surface_and_resource_limits(self):
        statement=FormalStatement.equality('x','x')
        with self.assertRaises(ValueError):translate_statement(statement,'by sorry')
        with self.assertRaises(ValueError):FormalStatement.equality('__import__("os")','0')
        with self.assertRaises(ValueError):FormalStatement.equality('((x**16)**16)**16','0')
        self.assertEqual(check_lean(translate_statement(statement),ROOT/'missing-lean').status,'unavailable')
        edited=replace(translate_statement(statement),source='example : False := by sorry')
        self.assertEqual(check_lean(edited,PROJECT).status,'translation_rejected')


@unittest.skipUnless(Z3_AVAILABLE,'optional formal extra (z3) absent')
class SMTBackendTests(unittest.TestCase):
    def test_linear_proof_and_exact_counterexample_replay(self):
        statement=FormalStatement(Predicate(parse_expr('x'),'le',parse_expr('2*x')),
                                 (Predicate(parse_expr('x'),'ge',parse_expr('0')),))
        result=solve_statement(statement)
        self.assertEqual(result['status'],'unsat')
        self.assertIn('proof',result)
        self.assertFalse(result['formal_proof'])
        false=solve_statement(FormalStatement.equality('x+1','x'))
        self.assertEqual(false['status'],'counterexample')
        self.assertTrue(false['exact_replay'])
        self.assertTrue(all(F(v).denominator>0 for v in false['witness'].values()))

    def test_hypothesis_inconsistency_and_fragment_boundaries(self):
        statement=FormalStatement(Predicate(parse_expr('x'),'eq',parse_expr('0')),
            (Predicate(parse_expr('x'),'gt',parse_expr('1')),Predicate(parse_expr('x'),'lt',parse_expr('0'))))
        self.assertEqual(solve_statement(statement)['status'],'inconsistent_assumptions')
        self.assertEqual(solve_statement(FormalStatement.equality('x*x','x'))['status'],'unsupported')
        self.assertEqual(solve_statement(FormalStatement.equality('x/x','1'))['status'],'unsupported')
        self.assertEqual(solve_statement(FormalStatement.equality('x/2+x/2','x'))['status'],'unsat')
        with self.assertRaises(ValueError):solve_statement(FormalStatement.equality('x','x'),timeout_ms=0)

    def test_receipts_are_rechecked_not_trusted(self):
        statement=FormalStatement.equality('x+0','x')
        receipt=solve_statement(statement)
        certificate=make_formal_certificate(statement,receipt)
        self.assertTrue(verify_formal_certificate(certificate))
        certificate['statement']=FormalStatement.equality('x+1','x').to_data()
        certificate.pop('certificate_id');certificate['certificate_id']=fingerprint(certificate)
        self.assertFalse(verify_formal_certificate(certificate))

    def test_smt_cli_and_persistent_failure_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);proof=root/'proof.json';failure=root/'failure.json'
            self.assertEqual(main(['prove','x','2*x','--relation','le','--assumption','x >= 0','--backend','smt','--output',str(proof)]),0)
            self.assertEqual(main(['check-formal',str(proof)]),0)
            self.assertEqual(main(['prove','x+1','x','--backend','smt','--output',str(failure)]),1)
            report=json.loads(failure.read_text())
            self.assertEqual(report['backend_receipt']['status'],'counterexample')


class CounterexampleReductionTests(unittest.TestCase):
    def test_minimality_failure_kind_and_budget(self):
        result=shrink_counterexample('x*x','x',{'x':12})
        self.assertEqual(result.witness,(('x',-1),))
        self.assertTrue(result.minimal_in_box)
        self.assertLess(sum(abs(v) for _,v in result.witness),12)
        limited=shrink_counterexample('x*x','x',{'x':12},budget=1)
        self.assertEqual(limited.status,'budget_exhausted')
        self.assertFalse(limited.minimal_in_box)
        domain=shrink_counterexample('x/x','1',{'x':0})
        self.assertEqual(domain.failure_kind,'domain_counterexample')
        with self.assertRaises(ValueError):shrink_counterexample('x','x',{'x':2})
        with self.assertRaises(ValueError):shrink_counterexample('x','x+1',{'x':'1/2'})

    def test_report_preserves_absence_limits_and_reproducibility(self):
        a=investigate('x*x','x',radius=3)
        self.assertEqual(a,investigate('x*x','x',radius=3))
        self.assertEqual(a['search']['status'],'counterexample')
        self.assertTrue(a['reduction']['minimal_in_box'])
        self.assertFalse(a['formal_proof'])
        self.assertIsNone(investigate('x','x',radius=1)['reduction'])
        self.assertEqual(investigate('x+y','y+x',budget=1)['search']['status'],'budget_exhausted')


@unittest.skipUnless(find_lake(PROJECT) and MATHLIB_READY,'optional pinned Lean/Mathlib build absent')
class LeanKernelIntegrationTests(unittest.TestCase):
    def test_actual_numeric_polynomial_and_conditional_proofs(self):
        for left,right in [('(3+3)/3','2'),('x*y+x*z','x*(y+z)'),('(x+x)/x','2')]:
            with self.subTest(left=left):
                result=prove_statement(FormalStatement.equality(left,right),PROJECT,timeout=120)
                self.assertTrue(result.verified,result.diagnostics)
                self.assertTrue(result.to_data()['formal_proof'])
                self.assertNotIn('sorryAx',result.axioms)

    def test_real_linear_implication_and_false_statement(self):
        statement=FormalStatement(Predicate(parse_expr('x'),'le',parse_expr('2*x')),
                                 (Predicate(parse_expr('x'),'ge',parse_expr('0')),))
        result=prove_statement(statement,PROJECT,timeout=120)
        self.assertTrue(result.verified,result.diagnostics)
        rejected=prove_statement(FormalStatement.equality('x+1','x'),PROJECT,timeout=120)
        self.assertEqual(rejected.status,'failed')
        self.assertFalse(rejected.to_data()['formal_proof'])

    def test_kernel_receipt_replay(self):
        statement=FormalStatement.equality('x+0','x')
        receipt=prove_statement(statement,PROJECT,strategy='ring',timeout=120).to_data()
        self.assertEqual(receipt['status'],'proved',receipt['diagnostics'])
        self.assertTrue(verify_formal_certificate(make_formal_certificate(statement,receipt),project=PROJECT))
        receipt['source_hash']='0'*64
        receipt.pop('receipt_id');receipt['receipt_id']=fingerprint(receipt)
        self.assertFalse(verify_formal_certificate(make_formal_certificate(statement,receipt),project=PROJECT))


class LeanProcessBoundaryTests(unittest.TestCase):
    def test_timeout_terminates_the_checker_process(self):
        import os,sys,subprocess
        from nablamath.formal.lean_checker import run_lean_process
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(subprocess.TimeoutExpired):
                run_lean_process([sys.executable,'-c','import time; time.sleep(10)'],cwd=directory,
                                 env=dict(os.environ),timeout=.05)
