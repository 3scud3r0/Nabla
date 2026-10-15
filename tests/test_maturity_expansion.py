"""Cross-phase tests of new operations, persistent workflows and numerical profiles."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from nablamath.core.semantic_ir import canonical_json
from nablamath.forge.reverse_builder import generate_task

CATALOG_CASES={
 'least_squares':{'predictors':[[0],[1],[2]],'response':[1,3,5]},
 'rational_compare':{'left':'(x*x-1)/(x-1)','right':'x+1'},
 'matrix_properties':{'matrix':[[1,2],[3,4]]},
 'matrix_inverse':{'matrix':[[1,2],[3,4]]},
 'linear_regression':{'x':[1,2,3],'y':[3,5,7]},
 'bayes':{'prior':{'a':'1/2','b':'1/2'},'likelihood':{'a':'1/4','b':'3/4'}},
 'distribution':{'kind':'normal','parameters':{},'value':0},
 'time_series':{'values':[1,2,3,4],'method':'trend'},
 'shortest_paths':{'vertices':['a','b','c'],'edges':[['a','b','1/2'],['b','c',2]],'source':'a'},
 'maximum_flow':{'vertices':['a','b','c'],'edges':[['a','b',2],['b','c',1]],'source':'a','sink':'c'},
 'sat':{'clauses':[[1,2],[-1],[2]]}}


class CatalogTests(unittest.TestCase):
    def test_operations_are_executed_replayed_and_checked(self):
        from nablamath.calc.session import CalculationSession
        from nablamath.calc.catalog import catalog
        from nablamath.calc.catalog import OPERATIONS
        self.assertEqual(set(CATALOG_CASES),set(OPERATIONS))
        self.assertTrue(set(CATALOG_CASES)<={r['name'] for r in catalog()['operations']})
        results={}
        for name,kwargs in CATALOG_CASES.items():
            with self.subTest(operation=name):
                receipt=CalculationSession().execute(name,**kwargs)
                self.assertEqual(receipt.to_data(),CalculationSession.replay_request(receipt.to_data()['request']).to_data())
                results[name]=receipt.to_data()['result']
        self.assertEqual(results['matrix_properties']['determinant'],'-2')
        self.assertEqual(results['linear_regression']['slope'],'2')
        self.assertEqual(results['bayes']['posterior']['b'],'3/4')
        self.assertEqual(results['maximum_flow']['value'],'1')
        self.assertTrue(results['sat']['assignment_verified'])
        self.assertAlmostEqual(results['distribution']['cdf'],.5)

    def test_invalid_domains_and_budgets(self):
        from nablamath.calc.session import CalculationSession
        cases=[('matrix_inverse',{'matrix':[[1,1],[1,1]]}),
               ('shortest_paths',{'vertices':['a','b'],'edges':[['a','b',-1]],'source':'a'}),
               ('linear_regression',{'x':[1,1],'y':[2,3]}),
               ('sat',{'clauses':[[0]]}),('distribution',{'kind':'poisson','parameters':{'rate':2},'value':.5})]
        for name,args in cases:
            with self.subTest(operation=name),self.assertRaises(ValueError):CalculationSession().execute(name,**args)


class BasisTests(unittest.TestCase):
    def test_rational_law_and_holdout_not_used_for_selection(self):
        from nablamath.discovery.hypothesis import Observation,ObservationSet
        from nablamath.discovery.basis_search import discover_basis
        # Fractions are required for exact source observations.
        from fractions import Fraction
        train=ObservationSet(tuple(Observation(x,2+Fraction(3,x)) for x in (1,2,3,4)),'synthetic rational fixture','calibration')
        holdout=ObservationSet(tuple(Observation(x,2+Fraction(3,x)) for x in (5,6,7)),'synthetic reserved','holdout')
        result=discover_basis(train,holdout,basis=('1','x','1/x'),max_terms=2)
        self.assertTrue(result['holdout_result']['matches_all'])
        wrong=ObservationSet(tuple(Observation(x,100+x) for x in (5,6,7)),'altered holdout','holdout')
        other=discover_basis(train,wrong,basis=('1','x','1/x'),max_terms=2)
        self.assertEqual(result['selected'],other['selected'])
        self.assertFalse(other['holdout_result']['matches_all'])
        with self.assertRaises(ValueError):discover_basis(train,train)


class DiffusionTests(unittest.TestCase):
    def test_cn_convergence_and_nonzero_boundary_steady_state(self):
        from nablamath.worlds.pde.diffusion import solve_diffusion
        errors=[]
        for cells in (20,40,80):
            initial=[math.sin(math.pi*i/cells) for i in range(cells+1)];initial[-1]=0.
            result=solve_diffusion(initial,steps=cells*2)
            error=max(abs(v-math.exp(-.1*math.pi**2*.1)*math.sin(math.pi*i/cells)) for i,v in enumerate(result['final']))
            errors.append(error)
            self.assertLess(result['discrete_equation_residual'],1e-12)
        self.assertGreater(math.log2(errors[0]/errors[1]),1.9)
        steady=[2+3*i/20 for i in range(21)]
        for method in ('crank_nicolson','backward_euler'):
            result=solve_diffusion(steady,boundary=(2.,5.),steps=2,method=method)
            self.assertLess(max(abs(a-b) for a,b in zip(steady,result['final'])),1e-12)
        with self.assertRaises(ValueError):solve_diffusion([0.,1.,1.,1.,0.],steps=1,diffusivity=100,method='ftcs')


class PersistentTests(unittest.TestCase):
    def test_dataset_batch_atomicity_and_split_leakage(self):
        from nablamath.datasets.schema import make_record
        from nablamath.datasets.store import RecordStore
        def record(seed):
            g=generate_task('linear_system',seed,2)
            return make_record(g.task,g.witness,license_id='CC0-1.0',provenance='fixture',scope='exact',limitations='synthetic',split='train')
        a,b=record(71),record(72)
        with tempfile.TemporaryDirectory() as tmp:
            store=RecordStore(Path(tmp)/'records.db')
            store.ingest([a],batch_id='first')
            with self.assertRaises(ValueError):store.ingest([b,a.with_split('test')],batch_id='failed')
            self.assertEqual(list(RecordStore(store.path).records()),[a])
            store.ingest([b],batch_id='failed')
            with self.assertRaises(ValueError):store.ingest([a],batch_id='first')
            self.assertEqual(len(list(store.records())),2)

    def test_agent_resume_replays_prefix_and_keeps_receipt(self):
        from nablamath.agents import ScientificProposal,Action,Planner,Permissions,scientific_registry
        from nablamath.agents.run_store import RunStore
        from nablamath.agents.planner import verify_run
        task=generate_task('linear_system',40,2).task.to_data()
        proposal=ScientificProposal('resume fixture',(
            Action('solve1','solve',canonical_json({'task':task})),
            Action('verify1','verify',canonical_json({'task':task,'candidate':{'$result':{'action':'solve1','path':['candidate']}}}),('solve1',))), 'trusted pure tools')
        planner=Planner(scientific_registry(),Permissions(frozenset({'solve','verify'})))
        with tempfile.TemporaryDirectory() as tmp:
            store=RunStore(Path(tmp)/'runs.db')
            partial=planner.run(proposal,store=store,stop_after=1)
            self.assertFalse(partial['completed']);self.assertTrue(verify_run(partial))
            final=planner.run(proposal,store=RunStore(store.path))
            self.assertTrue(final['completed']);self.assertTrue(verify_run(final))
            self.assertEqual(final['receipts'][0],partial['receipts'][0])
            self.assertEqual(planner.run(proposal,store=store),final)
            with self.assertRaises(ValueError):store.save(final,expected_head=partial['final_receipt'])

    def test_signed_snapshot_persistence_delta_and_quarantine(self):
        try:import cryptography
        except ImportError:self.skipTest('federation extra required')
        from nablamath.knowledge.identity import generate_signing_key,public_key_hex,PeerKey,sign_snapshot
        from nablamath.knowledge.federation import export_snapshot
        from nablamath.knowledge.versioned_claims import ClaimLedger,ClaimRevision
        from nablamath.knowledge.storage import SnapshotStore
        private=generate_signing_key();key=PeerKey('a',public_key_hex(private))
        ledger=ClaimLedger((ClaimRevision('c','hypothesis','proposed'),))
        envelope=sign_snapshot(export_snapshot(ledger,{},peer_id='a'),private)
        with tempfile.TemporaryDirectory() as tmp:
            a,b=(SnapshotStore(Path(tmp)/name) for name in ('a.db','b.db'))
            a.pin(key);b.pin(key)
            self.assertTrue(a.ingest(envelope)['valid'])
            for row in a.delta(b.inventory()):self.assertTrue(b.ingest(row)['valid'])
            self.assertEqual(a.inventory(),b.inventory())
            self.assertEqual(a.delta(b.inventory()),[])
            self.assertEqual(len(SnapshotStore(b.path).reconcile()['snapshot_ids']),1)
            bad=copy.deepcopy(envelope);bad['signature']='00'*64
            self.assertTrue(b.ingest(bad)['quarantined'])
            self.assertEqual(len(b.quarantined()),1)
            b.pin(PeerKey('a',key.public_key,True))
            with self.assertRaises(ValueError):SnapshotStore(b.path).delta()


class BibliographyTests(unittest.TestCase):
    def test_snapshot_query_and_missing_metadata_rejected(self):
        from nablamath.knowledge.bibliography_import import import_csl
        rows=[{'title':'Known rational models','author':[{'given':'A','family':'Researcher'}],
               'issued':{'date-parts':[[2020]]},'DOI':'10.example/test','URL':'https://example.org/paper',
               'abstract':'<p>Rational model identification.</p>','keyword':'rational, models'}]
        raw=canonical_json(rows).encode()
        corpus,receipt=import_csl(raw,source_url='https://example.org/export',retrieved_at='2026-10-15',license_id='CC0-1.0')
        self.assertEqual(len(corpus.search('rational')['hits']),1)
        self.assertEqual(receipt['corpus_id'],corpus.corpus_id)
        self.assertFalse(receipt['source_authentication_performed'])
        rows[0]['author']=[]
        with self.assertRaises(ValueError):import_csl(canonical_json(rows).encode(),source_url='https://example.org',retrieved_at='2026-10-15',license_id='CC0')


class ResearchRecordTests(unittest.TestCase):
    def test_mixed_records_transaction_stream_and_tampering(self):
        from nablamath.datasets.research_record import make_research_record,ResearchRecord
        from nablamath.datasets.serializer import iter_load
        from nablamath.datasets.store import RecordStore
        from nablamath.worlds import ModelSpec,simulate_adaptive
        from nablamath.graphics.sampling import adaptive_function_scene
        ode=make_research_record('ode',simulate_adaptive(ModelSpec('exponential_decay',(1.,))),
            license_id='CC0-1.0',provenance='fixture',scope='ideal ODE',limitations='synthetic',synthetic=True,split='train')
        scene=make_research_record('scene',adaptive_function_scene('x*x').to_data(),
            license_id='CC0-1.0',provenance='fixture',scope='rational graph',limitations='synthetic',synthetic=True,split='train')
        altered=ode.to_data();altered['payload']['final'][0]=999
        with self.assertRaises(ValueError):ResearchRecord.from_data(altered)
        with tempfile.TemporaryDirectory() as tmp:
            store=RecordStore(Path(tmp)/'mixed.db');store.ingest([ode,scene],batch_id='mixed')
            path=Path(tmp)/'mixed.jsonl';store.export_jsonl(path)
            with path.open('rb') as stream:
                actual=list(iter_load(stream))
            self.assertEqual({r.content_id for r in actual},{ode.content_id,scene.content_id})
            try:import pyarrow
            except ImportError:return
            from nablamath.export.parquet import write_parquet_stream,iter_parquet_stream
            arrow=Path(tmp)/'mixed.parquet';write_parquet_stream(store.records(),arrow,batch_size=1)
            self.assertEqual({r.content_id for r in iter_parquet_stream(arrow)},{ode.content_id,scene.content_id})
            with self.assertRaises(FileExistsError):write_parquet_stream([ode],arrow)
            fail=Path(tmp)/'failed.parquet'
            with self.assertRaises(ValueError):write_parquet_stream([ode,scene],fail,max_records=1)
            self.assertFalse(fail.exists())

    def test_observational_record_does_not_certify_physical_truth(self):
        from nablamath.datasets.research_record import make_research_record
        record=make_research_record('observation',{'rows':[{'values':[1.],'uncertainties':[.1]}],
            'units':['K'],'instrument':'declared device','calibration':'declared certificate','uncertainty_scope':'one standard uncertainty'},
            license_id='CC0-1.0',provenance='caller observation declaration',scope='single temperature',limitations='not authenticated',synthetic=False)
        self.assertTrue(record.verification()['valid'])
        self.assertFalse(record.verification()['scientific_claim_verified'])
        self.assertFalse(record.verification()['external_provenance_authenticated'])


class RationalIntegrationTests(unittest.TestCase):
    def test_construction_independent_sympy_and_domain_guards(self):
        from nablamath.forge.constructors.rational_integration import construct,verify_primitive
        from nablamath.math.calculus.rational_functions import compare_rational
        result=compare_rational('(x*x-1)/(x-1)','x+1')
        self.assertTrue(result['equal_on_common_domain']);self.assertFalse(result['domain_equivalence_established'])
        for seed in (2,9,73):
            task,primitive=construct(seed,degree=3)
            self.assertTrue(verify_primitive(task,primitive))
            self.assertFalse(verify_primitive(task,'0'))
            # A removable new hole must not be accepted as a primitive over the task's domain.
            self.assertFalse(verify_primitive(task,f'({primitive})*(x-37)/(x-37)'))
            try:import sympy as sp
            except ImportError:continue
            x=sp.Symbol('x')
            self.assertEqual(sp.cancel(sp.diff(sp.sympify(primitive),x)-sp.sympify(task['integrand'])),0)


class NewDomainTests(unittest.TestCase):
    def test_elasticity_ac_kinetics_and_layers_replay(self):
        from nablamath.core.units import Quantity,ONE,METER,SECOND,KILOGRAM,VOLT
        from nablamath.domains.contracts import PASCAL,OHM
        from nablamath.domains.materials import isotropic_elasticity
        from nablamath.domains.circuits import series_rlc,HENRY,FARAD
        from nablamath.domains.chemistry import reversible_first_order,CONCENTRATION
        from nablamath.domains.earth import layered_hydrostatics
        from nablamath.knowledge.provenance_audit import replay_domain
        elastic=isotropic_elasticity(Quantity(1000,PASCAL),Quantity('1/4',ONE),[['1/1000',0,0],[0,0,0],[0,0,0]])
        self.assertEqual(elastic['outputs']['stress'][0][0],'6/5')
        ac=series_rlc(Quantity(10,OHM),Quantity(1,HENRY),Quantity(1,FARAD),Quantity(5,VOLT),Quantity(1,SECOND**-1))
        self.assertEqual(ac['outputs']['impedance_imaginary'],'0')
        self.assertAlmostEqual(ac['outputs']['current_real'],.5)
        kinetics=reversible_first_order(Quantity(1,CONCENTRATION),Quantity(0,CONCENTRATION),Quantity(1,SECOND**-1),Quantity(1,SECOND**-1),Quantity(1,SECOND))
        self.assertAlmostEqual(kinetics['outputs']['final'][0],.5+.5*math.exp(-2),places=7)
        layers=layered_hydrostatics([Quantity(2,METER),Quantity(3,METER)],[Quantity(1000,KILOGRAM/METER**3),Quantity(2000,KILOGRAM/METER**3)],Quantity(10,METER/SECOND**2),Quantity(0,PASCAL))
        self.assertEqual(layers['outputs']['interface_pressures'],['0','20000','80000'])
        for result in (elastic,ac,kinetics,layers):
            self.assertTrue(result['checks_passed']);self.assertTrue(replay_domain(result))


class MultimodalNetworkTests(unittest.TestCase):
    def test_actual_learning_pixel_ablation_checkpoint_and_target_blinding(self):
        try:import numpy
        except ImportError:self.skipTest('research extra required')
        from nablamath.training.multimodal_network import intersection_corpus,MultimodalNetwork,run_multimodal_study
        rows=intersection_corpus(32,seed=151)
        model=MultimodalNetwork(seed=2)
        before={k:v.copy() for k,v in model.weights.items()}
        model.fit(rows,steps=20)
        self.assertTrue(any(not numpy.array_equal(v,before[k]) for k,v in model.weights.items()))
        blinded=[{k:r[k] for k in ('equations','pixels')} for r in rows]
        self.assertEqual(model.predict(rows),model.predict(blinded))
        eq=MultimodalNetwork(seed=2,modalities=('equation',));prediction=eq.predict(blinded)
        changed=copy.deepcopy(blinded)
        for row in changed:row['pixels']=[1.]*512
        self.assertEqual(eq.predict(changed),prediction)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'model.npz';model.save(path)
            self.assertEqual(model.predict(blinded),MultimodalNetwork.load(path).predict(blinded))
        with self.assertRaises(ValueError):run_multimodal_study(rows,rows,steps=1)


class ProfileTests(unittest.TestCase):
    def test_document_profiles_require_evidence_and_retain_common_ast(self):
        from nablamath.documents.profiles import PROFILES,build_profile
        from nablamath.documents.document_model import Section,Document
        for profile,names in PROFILES.items():
            sections={name:Section(name,'Bounded synthetic example',('evidence-id',)) for name in names}
            doc=build_profile(profile,'Example',sections,limitations='synthetic; no independent review')
            self.assertEqual(Document.from_data(doc.to_data()),doc)
            with self.assertRaises(ValueError):build_profile(profile,'Missing',{},limitations='bounded')


class FormalBundleTests(unittest.TestCase):
    def test_rechecked_certificate_bundle_cannot_swap_question(self):
        try:import z3
        except ImportError:self.skipTest('formal extra required')
        from nablamath.formal import FormalStatement
        from nablamath.formal.smt_bridge import solve_statement
        from nablamath.formal.translation_review import bind_translation
        from nablamath.verify.certificate import make_formal_certificate
        from nablamath.formal.bundle import export_formal_bundle,verify_formal_bundle
        statement=FormalStatement.equality('x+1','1+x')
        certificate=make_formal_certificate(statement,solve_statement(statement))
        question='For rational x, is x+1 equal to 1+x?'
        binding=bind_translation(question,statement,task_id='commutativity-fixture',reviewer='declared fixture reviewer',notes='no independent identity',accepted=True)
        with tempfile.TemporaryDirectory() as tmp:
            destination=Path(tmp)/'formal'
            export_formal_bundle(question,statement,certificate,binding,destination)
            self.assertTrue(verify_formal_bundle(destination))
            (destination/'question.json').write_text(canonical_json({'question':'different question'}),encoding='utf-8')
            manifest=json.loads((destination/'manifest.json').read_text(encoding='utf-8'))
            import hashlib
            manifest['files']['question.json']=hashlib.sha256((destination/'question.json').read_bytes()).hexdigest()
            (destination/'manifest.json').write_text(canonical_json(manifest),encoding='utf-8')
            self.assertFalse(verify_formal_bundle(destination))


class ExactRegressionTests(unittest.TestCase):
    def test_weighted_fit_residual_orthogonality_and_nist(self):
        from nablamath.math.statistics.multivariate import exact_least_squares
        from fractions import Fraction
        fit=exact_least_squares([[0],[1],[2],[3]],[1,2,4,5],weights=[1,2,1,2])
        self.assertEqual(sum(w*r for w,r in zip([1,2,1,2],fit.residuals)),0)
        self.assertEqual(sum(w*x*r for w,x,r in zip([1,2,1,2],[0,1,2,3],fit.residuals)),0)
        self.assertGreaterEqual(fit.residual_sum_squares,0)
        with self.assertRaises(ValueError):exact_least_squares([[1],[1],[1]],[1,2,3])
        with self.assertRaises(ValueError):exact_least_squares([[0],[1],[2]],[1,2,3],weights=[1,0,1])
        import importlib.util
        path=Path(__file__).parents[1]/'tools/validate_longley.py'
        spec=importlib.util.spec_from_file_location('nabla_longley_validation',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        report=module.validate(Path(__file__).parents[1]/'benchmarks/fixtures/longley-nist')
        self.assertTrue(report['passed'])
        self.assertLess(max(report['coefficient_relative_errors']),5e-12)


class PortfolioTests(unittest.TestCase):
    def test_fresh_holdout_receipts_promotion_rejection_and_contract(self):
        from nablamath.evolution.portfolio import PortfolioPolicy,select_portfolio,PortfolioCampaign
        from nablamath.forge.deduplicate import semantic_fingerprint
        family='linear_system';seen=set()
        def tasks(seed,count):
            result=[]
            for i in range(1000):
                task=generate_task(family,seed+i,3).task;key=semantic_fingerprint(task)
                if key in seen:continue
                seen.add(key);result.append(task)
                if len(result)==count:return result
            raise ValueError('Unique fixtures unavailable')
        train,holdout=tasks(100,3),tasks(2100,16)
        candidate,_=select_portfolio(train)
        baseline=PortfolioPolicy(((family,'alternate'),))
        with tempfile.TemporaryDirectory() as tmp:
            campaign=PortfolioCampaign(Path(tmp)/'campaign.db',baseline)
            receipt=campaign.evaluate(candidate,train,holdout)
            self.assertTrue(receipt['accepted'])
            altered=copy.deepcopy(receipt);altered['accepted']=False
            with self.assertRaises(ValueError):campaign.promote(altered)
            self.assertEqual(campaign.promote(receipt),candidate)
            event=campaign.rollback(baseline.policy_id,reason='test operator reversal')
            self.assertEqual(event['to'],baseline.policy_id)
            self.assertEqual(campaign.active(),baseline)
            with self.assertRaises(ValueError):campaign.evaluate(candidate,train,holdout)
            with self.assertRaises(ValueError):PortfolioCampaign(campaign.path,baseline,minimum_effect=.99)
            with self.assertRaises(ValueError):campaign.rollback('0'*64,reason='unknown')

    def test_unknown_policy_capability_and_overlap_rejected(self):
        from nablamath.evolution.portfolio import PortfolioPolicy,PortfolioCampaign
        with self.assertRaises(ValueError):PortfolioPolicy((('linear_system','eval'),))
        with tempfile.TemporaryDirectory() as tmp:
            policy=PortfolioPolicy((('linear_system','exact'),));campaign=PortfolioCampaign(Path(tmp)/'c.db',policy)
            task=generate_task('linear_system',1,2).task
            with self.assertRaises(ValueError):campaign.evaluate(policy,[task],[task]*5)


class SignedReviewTests(unittest.TestCase):
    def test_pinned_revision_review_signature_and_conflict_policy(self):
        try:import cryptography
        except ImportError:self.skipTest('federation extra required')
        from nablamath.knowledge.identity import generate_signing_key,public_key_hex,PeerKey,PeerTrust
        from nablamath.knowledge.peer_review import Reviewer,Review,ReviewBoard,sign_review,submit_signed_review
        from nablamath.knowledge.versioned_claims import ClaimLedger,ClaimRevision
        claim=ClaimRevision('c','bounded claim','supported',('declared-evidence',));ledger=ClaimLedger((claim,))
        private=generate_signing_key();trust=PeerTrust((PeerKey('reviewer',public_key_hex(private)),))
        board=ReviewBoard((Reviewer('reviewer',('math',)),),authors={claim.revision_id:('author',)})
        review=Review(claim.revision_id,'reviewer','math','revise','Need independent evidence',('declared-evidence',))
        envelope=sign_review(review,private)
        result=submit_signed_review(board,envelope,ledger,trust)
        self.assertTrue(result['reviewer_key_authenticated'])
        self.assertFalse(result['real_world_identity_and_expertise_verified'])
        tampered=copy.deepcopy(envelope);tampered['review']['decision']='accept'
        with self.assertRaises(ValueError):submit_signed_review(board,tampered,ledger,trust)
        conflict=ReviewBoard((Reviewer('reviewer',('math',)),),authors={claim.revision_id:('reviewer',)})
        with self.assertRaises(ValueError):submit_signed_review(conflict,envelope,ledger,trust)
