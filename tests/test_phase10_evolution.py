import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from nablamath.core.semantic_ir import fingerprint
from nablamath.worlds import ModelSpec
from nablamath.evolution.policy_genome import PolicyGenome
from nablamath.evolution.proposal_validator import EvaluationContract,validate_proposal
from nablamath.evolution.search import search_policies
from nablamath.evolution.holdout_manager import HoldoutManager
from nablamath.evolution.release_gate import release_gate,verify_policy_receipt
from nablamath.evolution.rollback import PolicyStore
from nablamath.evolution.statistical_tests import paired_sign_test
from nablamath.evolution.lineage import Lineage


def cases():
    calibration=(ModelSpec('exponential_decay',(1,),rate=.7),ModelSpec('harmonic_oscillator',(1,0),rate=.8))
    holdout=tuple(ModelSpec('exponential_decay',(1+i/10,),rate=1+i/10,duration=.8) for i in range(8))
    return calibration,holdout


class EvolutionTests(unittest.TestCase):
    def test_search_one_use_gate_release_and_rollback(self):
        calibration,holdout=cases();baseline=PolicyGenome('euler',20);contract=EvaluationContract()
        candidate,search=search_policies(baseline,calibration,contract)
        self.assertTrue(search['calibration_only'])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manager=HoldoutManager(root/'holdouts.db',contract)
            suite=manager.register(holdout,calibration,label='fresh-1')
            receipt=manager.evaluate_once(suite,candidate,baseline,calibration)
            self.assertTrue(verify_policy_receipt(receipt))
            self.assertTrue(release_gate(receipt,contract,manager=manager)['accepted'])
            with self.assertRaises(ValueError):manager.evaluate_once(suite,candidate,baseline,calibration)
            with self.assertRaises(ValueError):manager.register(holdout,calibration,label='different-name-same-cases')
            store=PolicyStore(root/'release.db',baseline)
            store.promote(candidate,receipt,contract,manager=manager,expected_active=baseline.genome_id)
            self.assertEqual(store.snapshot()['active'],candidate.genome_id)
            with self.assertRaises(ValueError):store.promote(candidate,receipt,contract,manager=manager,expected_active=baseline.genome_id)
            snapshot=store.rollback(baseline.genome_id,expected_active=candidate.genome_id,reason='operator regression observation')
            self.assertEqual(snapshot['active'],baseline.genome_id)
            self.assertEqual(snapshot['events'][-1]['action'],'rollback')
            self.assertEqual(PolicyStore(root/'release.db',baseline).snapshot(),snapshot)

    def test_tampering_contracts_budget_and_immutable_inputs(self):
        baseline=PolicyGenome('euler',20);candidate=PolicyGenome('rk4',80,baseline.genome_id,1)
        with self.assertRaises(ValueError):PolicyGenome.from_data({'method':'rk4','steps':10,'code':'print(1)'})
        with self.assertRaises(ValueError):validate_proposal(candidate,baseline,EvaluationContract(max_derivative_calls=40))
        with self.assertRaises(ValueError):replace(EvaluationContract(),evaluator_id='0'*64).assert_current()
        calibration,holdout=cases()
        with tempfile.TemporaryDirectory() as tmp:
            contract=EvaluationContract();manager=HoldoutManager(Path(tmp)/'vault.db',contract)
            with self.assertRaises(ValueError):manager.register((*holdout[:7],calibration[0]),calibration,label='leak')
            receipt=manager.evaluate_once(manager.register(holdout,calibration,label='fresh'),candidate,baseline,calibration)
            forged=json.loads(json.dumps(receipt));forged['evaluation']['candidate_errors'][0]=999
            forged['receipt_id']=fingerprint({k:v for k,v in forged.items() if k!='receipt_id'})
            self.assertFalse(release_gate(forged,contract,manager=manager)['accepted'])
            self.assertFalse(verify_policy_receipt(forged))

    def test_failed_candidate_is_retained_and_not_released(self):
        calibration,holdout=cases();baseline=PolicyGenome('rk4',80);candidate=PolicyGenome('euler',2,baseline.genome_id,1)
        contract=EvaluationContract()
        with tempfile.TemporaryDirectory() as tmp:
            manager=HoldoutManager(Path(tmp)/'vault.db',contract)
            receipt=manager.evaluate_once(manager.register(holdout,calibration,label='negative'),candidate,baseline,calibration)
            self.assertFalse(release_gate(receipt,contract,manager=manager)['accepted'])
            self.assertTrue(manager.contains_receipt(receipt))
            self.assertTrue(verify_policy_receipt(receipt))
        stats=paired_sign_test([1]*8,[2]*8,alpha=.05/8)
        self.assertAlmostEqual(stats['p_value'],1/256)
        self.assertTrue(stats['significant'])
        self.assertFalse(paired_sign_test([None],[1])['valid'])

    def test_lineage_hash_tampering_and_unknown_rollback(self):
        lineage=Lineage();lineage.append(action='baseline',genome_id='a')
        rows=list(lineage.events);rows[0]['genome_id']='other'
        with self.assertRaises(ValueError):Lineage(rows)
        baseline=PolicyGenome('euler',20)
        with tempfile.TemporaryDirectory() as tmp:
            store=PolicyStore(Path(tmp)/'state.db',baseline)
            with self.assertRaises(ValueError):store.rollback('missing',expected_active=baseline.genome_id,reason='test')
