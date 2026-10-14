from fractions import Fraction as F
import json
import unittest
from nablamath.discovery import Hypothesis,Observation,ObservationSet,fit_and_evaluate,propose_experiment,assess
from nablamath.discovery.theorem_search import search_identity
from nablamath.discovery.research_program import run_research,verify_research
from nablamath.knowledge.literature import LiteratureEntry,LiteratureCorpus
from nablamath.documents.citations import Citation
from nablamath.core.units import METER,SECOND,ONE
from nablamath.falsifier.counterexample_miner import mine


def corpus():
    return LiteratureCorpus((LiteratureEntry(Citation('synthetic','Synthetic polynomial fixture',('Test author',),2026),
                      'Synthetic local metadata, not an external paper',('polynomial',),'unit test','CC0-1.0','x*x'),),
                      provenance='synthetic test corpus')


def observations():
    calibration=ObservationSet(tuple(Observation(x,x*x) for x in (-3,-1,0,2)),'analytic fixture','calibration')
    holdout=ObservationSet(tuple(Observation(x,x*x) for x in (-2,1,3,4)),'independent input fixture','holdout')
    return calibration,holdout


class DiscoveryTests(unittest.TestCase):
    def test_exact_search_holdout_and_grammar(self):
        calibration,holdout=observations()
        report,hypothesis=fit_and_evaluate(calibration,holdout,max_degree=3)
        self.assertTrue(report['calibration_result']['matches_all'])
        self.assertTrue(report['holdout_result']['matches_all'])
        self.assertEqual(hypothesis.predict(5),25)
        self.assertEqual(report['candidates'][0]['coefficients'],['0','0','1'])
        self.assertFalse(report['formal_proof'])
        bad=ObservationSet((Observation(5,999),),'counter-observation','holdout')
        self.assertFalse(fit_and_evaluate(calibration,bad)[0]['holdout_result']['matches_all'])
        leaked=ObservationSet((Observation(0,0),),'leak','holdout')
        with self.assertRaises(ValueError):fit_and_evaluate(calibration,leaked)

    def test_dimensions_domain_and_missing_values(self):
        with self.assertRaises(ValueError):Hypothesis('x+x*x','bad dimensions',METER,METER)
        with self.assertRaises(ValueError):Hypothesis('__import__("os")','code')
        hypothesis=Hypothesis('x','SI identity',METER,METER)
        self.assertEqual(hypothesis.predict(2),2)
        wrong=ObservationSet((Observation(2,2),),'units','holdout',SECOND,SECOND)
        with self.assertRaises(ValueError):assess(hypothesis,wrong)
        singular=Hypothesis('1/x','rational domain')
        report=assess(singular,ObservationSet((Observation(0,0),),'singular','holdout'))
        self.assertFalse(report['matches_all'])
        with self.assertRaises(ValueError):Observation(1,1,-1)

    def test_design_counterexamples_and_exact_proof_scope(self):
        a,b=Hypothesis('x','linear'),Hypothesis('x*x','quadratic')
        report=propose_experiment((a,b),(-3,-1,0,1,3),observed=(-3,))
        self.assertEqual(report['selected']['x'],'3')
        self.assertFalse(report['experiment_performed'])
        refutation=mine((('x*x','x'),('x/x','1'),('x+x','2*x')))
        self.assertEqual(refutation['counterexamples'],2)
        same=search_identity('(x+1)*(x+1)','x*x+2*x+1')
        self.assertTrue(same['receipt']['equal']);self.assertFalse(same['receipt']['formal_proof'])
        self.assertIsNone(search_identity('x/x','1')['receipt']['equal'])

    def test_program_replays_literature_and_never_claims_global_novelty(self):
        calibration,holdout=observations()
        report=run_research(calibration,holdout,corpus(),query='polynomial',reference='x*x')
        self.assertTrue(verify_research(json.loads(json.dumps(report))))
        self.assertEqual(report['novelty']['status'],'local_equivalent_found')
        self.assertFalse(report['global_novelty_established'])
        report['conclusion']='new scientific law'
        self.assertFalse(verify_research(report))
        empty=run_research(calibration,holdout,LiteratureCorpus((),provenance='empty snapshot'),query='anything')
        self.assertEqual(empty['novelty']['status'],'novelty_not_established')
        self.assertTrue(empty['novelty']['corpus_empty'])

    def test_degree_six_fractional_fit_and_zero_power_domain_are_preserved(self):
        calibration=ObservationSet(tuple(Observation(x,F(x**6,7)+F(x,3)) for x in range(-3,4)),'exact degree-six fixture','calibration')
        holdout=ObservationSet((Observation(4,F(4**6,7)+F(4,3)),),'new input','holdout')
        report,hypothesis=fit_and_evaluate(calibration,holdout,max_degree=6,complexity_penalty='0')
        self.assertTrue(report['holdout_result']['matches_all'])
        self.assertFalse(search_identity('x**0','1')['receipt']['equal'])
