"""Reproduce integrated bounded maturity profiles, without external publication."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile


def reproduce(destination,*,learning_directory=None,pdf_backend='typst'):
    from nablamath.core.semantic_ir import canonical_json,fingerprint
    from nablamath.calc.catalog import catalog
    from nablamath.calc.session import CalculationSession
    from nablamath.datasets.research_record import make_research_record
    from nablamath.datasets.store import RecordStore
    from nablamath.export.research_bundle import export_research_bundle
    from nablamath.export.huggingface import prepare_hub
    from nablamath.datasets.serializer import iter_load
    from nablamath.export.parquet import write_parquet_stream,iter_parquet_stream
    from nablamath.worlds import ModelSpec,simulate_adaptive
    from nablamath.worlds.pde.diffusion import solve_diffusion
    from nablamath.graphics.sampling import adaptive_function_scene,vector_field_scene,phase_portrait_scene
    from nablamath.graphics.artifacts import export_scene
    from nablamath.forge.constructors.geometry import construct as geometry
    from nablamath.forge.constructors.rational_integration import construct,verify_primitive
    from nablamath.forge.reverse_builder import generate_task
    from nablamath.forge.deduplicate import semantic_fingerprint
    from nablamath.discovery.hypothesis import Observation,ObservationSet
    from nablamath.discovery.basis_search import discover_basis
    from nablamath.knowledge.bibliography_import import import_csl
    from nablamath.documents.document_model import Section,Table
    from nablamath.documents.profiles import PROFILES,build_profile
    from nablamath.documents.figures import ingest_figure
    from nablamath.documents.publication import publish,verify_publication
    from nablamath.agents import Planner,ScientificProposal,Action,Permissions,scientific_registry
    from nablamath.agents.run_store import RunStore
    from nablamath.formal import FormalStatement,solve_statement,prove_statement
    from nablamath.verify.certificate import make_formal_certificate
    from nablamath.formal.translation_review import bind_translation
    from nablamath.formal.bundle import export_formal_bundle
    from nablamath.knowledge.identity import generate_signing_key,public_key_hex,PeerKey,sign_snapshot
    from nablamath.knowledge.storage import SnapshotStore
    from nablamath.knowledge.federation import export_snapshot
    from nablamath.knowledge.versioned_claims import ClaimLedger,ClaimRevision
    from nablamath.knowledge.provenance_audit import Evidence
    from nablamath.evolution.portfolio import select_portfolio,PortfolioPolicy,PortfolioCampaign
    from fractions import Fraction
    from validate_longley import validate
    destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.maturity-',dir=destination.parent))
    def save(name,data):
        path=stage/name;path.write_text(canonical_json(data)+'\n',encoding='utf-8')
        return hashlib.sha256(path.read_bytes()).hexdigest(),path
    try:
        save('calculator-catalog.json',catalog())
        receipt=CalculationSession().execute('least_squares',predictors=[[0],[1],[2]],response=[1,3,5])
        if CalculationSession.replay_request(receipt.to_data()['request']).to_data()!=receipt.to_data():raise ValueError('Calculation replay failed')
        save('calculation.json',receipt.to_data())
        integrals=[]
        import sympy as sp
        x=sp.Symbol('x')
        for seed in (12,41,113):
            task,primitive=construct(seed,degree=3)
            exact=verify_primitive(task,primitive)
            independent=sp.cancel(sp.diff(sp.sympify(primitive),x)-sp.sympify(task['integrand']))==0
            if not exact or not independent:raise ValueError('Inverse rational integration failed')
            integrals.append({'task':task,'primitive':primitive,'verified':exact,'sympy_derivative_checked':independent})
        save('rational-integrals.json',integrals)
        # Independent known-data numerical reference, not a new scientific finding.
        nist=validate(Path(__file__).resolve().parents[1]/'benchmarks/fixtures/longley-nist')
        if not nist['passed']:raise ValueError('NIST regression failed')
        nist_id,nist_path=save('nist.json',nist)
        ode=simulate_adaptive(ModelSpec('harmonic_oscillator',(1.,0.),2.,3.),atol=1e-11,rtol=1e-9)
        initial=[math.sin(math.pi*i/40) for i in range(41)];initial[-1]=0.
        diffusion=solve_diffusion(initial,steps=80)
        diff_error=max(abs(v-math.exp(-.1*math.pi**2*.1)*math.sin(math.pi*i/40)) for i,v in enumerate(diffusion['final']))
        if diff_error>1e-4:raise ValueError('Diffusion analytic reference error exceeded budget')
        scene=adaptive_function_scene('x*x*x',xmin=-1,xmax=2)
        scenes=[scene,vector_field_scene(),phase_portrait_scene(steps=100)]
        for kind in ('right_triangle','parallelogram','circumcircle'):scenes.append(geometry(42,3,kind))
        for index,item in enumerate(scenes):export_scene(item,stage/f'scene-{index}')
        def record(kind,payload):return make_research_record(kind,payload,license_id='CC0-1.0',provenance='maturity laboratory',scope='bounded synthetic model',limitations='no observed validation',synthetic=True,split='train')
        records=[record('ode',ode),record('diffusion',diffusion),record('scene',scene.to_data())]
        store=RecordStore(stage/'records.sqlite3');store.ingest(records,batch_id='models')
        task=generate_task('linear_system',113,3).task.to_data()
        proposal=ScientificProposal('Solve then independently verify',(
            Action('solve1','solve',canonical_json({'task':task})),
            Action('verify1','verify',canonical_json({'task':task,'candidate':{'$result':{'action':'solve1','path':['candidate']}}}),('solve1',))), 'trusted replayable tools only')
        planner=Planner(scientific_registry(),Permissions(frozenset({'solve','verify'})))
        runs=RunStore(stage/'agent.sqlite3');partial=planner.run(proposal,store=runs,stop_after=1)
        resumed=planner.run(proposal,store=RunStore(runs.path))
        if not resumed['completed'] or resumed['receipts'][0]!=partial['receipts'][0]:raise ValueError('Durable resume failed')
        agent_id,agent_path=save('agent-resumed.json',resumed)
        train=ObservationSet(tuple(Observation(v,2+Fraction(3,v)) for v in (1,2,3,4)),'synthetic rational law','calibration')
        test=ObservationSet(tuple(Observation(v,2+Fraction(3,v)) for v in (5,6,7)),'reserved synthetic points','holdout')
        discovery=discover_basis(train,test,basis=('1','x','1/x'),max_terms=2)
        if not discovery['holdout_result']['matches_all']:raise ValueError('Rational basis recovery failed')
        discovery_id,discovery_path=save('basis-discovery.json',discovery)
        discovery_record=record('basis_discovery',discovery)
        store.ingest([discovery_record],batch_id='discovery')
        records.append(discovery_record)
        store.export_jsonl(stage/'records.jsonl')
        write_parquet_stream(store.records(),stage/'records.parquet',batch_size=1)
        with (stage/'records.jsonl').open('rb') as stream:
            if {r.content_id for r in iter_load(stream)}!={r.content_id for r in records}:raise ValueError('Mixed JSONL replay failed')
        if {r.content_id for r in iter_parquet_stream(stage/'records.parquet')}!={r.content_id for r in records}:raise ValueError('Mixed Parquet replay failed')
        export_research_bundle(store.records(),stage/'dataset-release')
        if prepare_hub(stage/'dataset-release')['publication_performed']:raise ValueError('Unexpected publication')
        csl=[{'title':'An Appraisal of Least Squares Programs for the Electronic Computer from the Viewpoint of the User',
              'author':[{'given':'J. W.','family':'Longley'}],'issued':{'date-parts':[[1967]]},
              'URL':'https://github.com/statsmodels/statsmodels','abstract':'Published numerical least squares reference.'}]
        corpus,bibliography=import_csl(canonical_json(csl).encode(),source_url='https://github.com/statsmodels/statsmodels',retrieved_at='2026-10-15',license_id='LicenseRef-Public-Domain')
        save('bibliography.json',{'import':bibliography,'query':corpus.search('least squares')})
        statement=FormalStatement.equality('x*(x+1)','x*x+x');question='For rational x, does x*(x+1) equal x*x+x?'
        formal=prove_statement(statement,project=Path('lean'),strategy='ring').to_data()
        if formal['status']!='proved':raise ValueError('Pinned Lean proof failed: '+formal['diagnostics'])
        certificate=make_formal_certificate(statement,formal)
        binding=bind_translation(question,statement,task_id='maturity-ring-example',reviewer='automatic draft',notes='Human correspondence review still pending',accepted=False)
        export_formal_bundle(question,statement,certificate,binding,stage/'formal')
        evidence=Evidence('exact_trace',canonical_json(resumed['receipts'][0]['result']),'seeded local construction','CC0-1.0',True)
        claim=ClaimRevision('constructed-system','The exact constructed system has the supplied solution','supported',(evidence.evidence_id,))
        discovery_evidence=Evidence('discovery',canonical_json(discovery),'bounded rational grammar, reserved synthetic points','CC0-1.0',True)
        if not discovery_evidence.verify()['valid']:raise ValueError('Discovery evidence replay failed')
        discovery_claim=ClaimRevision('rational-law','The rational basis candidate matches these reserved synthetic observations','supported',(discovery_evidence.evidence_id,))
        ledger=ClaimLedger((claim,discovery_claim));private=generate_signing_key();key=PeerKey('demo-peer',public_key_hex(private))
        envelope=sign_snapshot(export_snapshot(ledger,{evidence.evidence_id:evidence,discovery_evidence.evidence_id:discovery_evidence},peer_id=key.peer_id),private)
        peers=[SnapshotStore(stage/f'peer-{i}.sqlite3') for i in (1,2)]
        for peer in peers:peer.pin(key)
        if not peers[0].ingest(envelope)['valid']:raise ValueError('Signed evidence ingest failed')
        for row in peers[0].delta(peers[1].inventory()):
            if not peers[1].ingest(row)['valid']:raise ValueError('Delta synchronization failed')
        if peers[0].inventory()!=peers[1].inventory():raise ValueError('Peer convergence failed')
        federation_id,federation_path=save('federation.json',peers[1].reconcile())
        table=Table('Reproduced computational evidence',('Check','Outcome'),(
            ('Published NIST numerical reference','passed'),('Durable agent resume','passed'),
            ('Rational basis holdout','matched'),('Signed delta exchange','passed')), (nist_id,agent_id,discovery_id,federation_id))
        figure=ingest_figure(stage/'scene-0/scene.png',stage/'assets','Model-linked rational curve, vertical interpolation tolerance 1/1000; source scene is replayable.')
        publications=[]
        for profile,names in PROFILES.items():
            sections={name:Section(name,'Bounded examples. NIST data are published observations; other examples are synthetic.',
                     tables=(table,) if name in ('Results','Verification','Worked examples') else (),
                     figures=(figure,) if name in ('Results','Worked examples') else ()) for name in names}
            document=build_profile(profile,'Nabla '+profile,sections,limitations='Computational checks only; no global novelty, physical validation or independent peer review.',references=tuple(e.citation for e in corpus.entries))
            publish(document,stage/profile,pdf_backend=pdf_backend,asset_root=stage/'assets',evidence_sources={nist_id:nist_path,agent_id:agent_path,discovery_id:discovery_path,federation_id:federation_path},require_evidence=True)
            if not verify_publication(stage/profile):raise ValueError('Publication replay failed')
            publications.append(profile)
        learning_verified=None
        if learning_directory is not None:
            from nablamath.training.multimodal_network import verify_multimodal_study
            learning_verified=verify_multimodal_study(learning_directory)
            if not learning_verified:raise ValueError('Multimodal checkpoint replay failed')
        summary={'schema_version':1,'calculator_operations':len(catalog()['operations']),'rational_integrals_independently_checked':len(integrals),
                 'nist_reference_passed':nist['passed'],'diffusion_reference_max_error':diff_error,'ode_reference_max_error':ode['max_trajectory_reference_error'],
                 'visual_scenes':len(scenes),'mixed_artifact_profiles':4,'jsonl_parquet_roundtrip':True,'durable_agent_resume':True,
                 'rational_basis_holdout_matched':True,'pinned_lean_proof':True,'human_translation_review_accepted':False,
                 'durable_signed_peer_exchange':True,'compiled_publication_profiles':publications,'pdf_backend':pdf_backend,
                 'multimodal_checkpoint_predictions_verified':learning_verified,
                 'global_novelty_established':False,'experimental_physical_validation':False,'external_learning_gain_established':False}
        save('summary.json',summary)
        save('manifest.json',{'schema_version':1,'files':{p.relative_to(stage).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(stage.rglob('*')) if p.is_file()}})
        stage.rename(destination);return summary
    finally:
        if stage.exists():shutil.rmtree(stage)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path);parser.add_argument('--learning-directory',type=Path)
    parser.add_argument('--pdf-backend',choices=('typst','latex'),default='typst')
    args=parser.parse_args()
    print(json.dumps(reproduce(args.destination,learning_directory=args.learning_directory,pdf_backend=args.pdf_backend),sort_keys=True))
