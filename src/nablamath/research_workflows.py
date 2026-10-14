"""Reproducible Discovery/Evolution/domain/knowledge programs with explicit scopes."""
from dataclasses import replace
import hashlib
from pathlib import Path
import shutil
import tempfile
from .core.semantic_ir import canonical_json
from .scientific_workflows import write_json


def discovery_demo():
    from .discovery.hypothesis import Observation,ObservationSet
    from .discovery.research_program import run_research
    from .knowledge.literature import LiteratureCorpus,LiteratureEntry
    from .documents.citations import Citation
    calibration=ObservationSet(tuple(Observation(x,x*x) for x in (-3,-1,0,2)),'synthetic analytic polynomial, calibration inputs','calibration')
    holdout=ObservationSet(tuple(Observation(x,x*x) for x in (-2,1,3,4)),'synthetic analytic polynomial, reserved inputs','holdout')
    corpus=LiteratureCorpus((LiteratureEntry(
        Citation('brunton2016','Discovering governing equations from data by sparse identification of nonlinear dynamical systems',
                 ('Steven L. Brunton','Joshua L. Proctor','J. Nathan Kutz'),2016,
                 url='https://doi.org/10.1073/pnas.1517384113',doi='10.1073/pnas.1517384113'),
        'User-supplied metadata example for sparse model discovery; not a reproduced abstract.',
        ('sparse','model','discovery','polynomial'),'declared bibliographic metadata; publisher not queried','metadata only; no article text'),),
        provenance='Local declared metadata snapshot, no claim of exhaustive literature coverage')
    return run_research(calibration,holdout,corpus,query='polynomial model discovery',reference='x*x')


def evolution_demo(destination,*,generations=2):
    from .evolution.policy_genome import PolicyGenome
    from .evolution.proposal_validator import EvaluationContract
    from .evolution.search import search_policies
    from .evolution.holdout_manager import HoldoutManager
    from .evolution.rollback import PolicyStore
    from .evolution.release_gate import release_gate
    from .worlds import ModelSpec
    if type(generations) is not int or not 1<=generations<=2:raise ValueError('Demo limitada a 1–2 gerações')
    root=Path(destination)
    if root.exists():raise FileExistsError(root)
    root.mkdir(parents=True)
    contract=EvaluationContract();baseline=PolicyGenome('euler',20)
    calibration=(ModelSpec('exponential_decay',(1,),rate=.7),ModelSpec('harmonic_oscillator',(1,0),rate=.8))
    manager=HoldoutManager(root/'holdouts.sqlite3',contract);store=PolicyStore(root/'policies.sqlite3',baseline)
    current=baseline;runs=[]
    for generation in range(1,generations+1):
        candidate,search=search_policies(current,calibration,contract,step_counts=(20,40,80,100) if generation>1 else (10,20,40,80))
        holdout=tuple(ModelSpec('exponential_decay',(1+generation+i/10,),rate=.8+i/10,duration=.7+generation/10) for i in range(8))
        suite=manager.register(holdout,calibration,label=f'fresh-generation-{generation}')
        receipt=manager.evaluate_once(suite,candidate,current,calibration);gate=release_gate(receipt,contract,manager=manager)
        runs.append({'search':search,'receipt':receipt,'gate':gate})
        if not gate['accepted']:
            store.record_rejection(candidate,receipt,contract,manager=manager,expected_active=current.genome_id)
            break
        store.promote(candidate,receipt,contract,manager=manager,expected_active=current.genome_id);current=candidate
    bad=PolicyGenome('euler',2,current.genome_id,current.generation+1)
    negative_cases=tuple(ModelSpec('exponential_decay',(3+i/10,),rate=1.5+i/10,duration=.9) for i in range(8))
    negative=manager.evaluate_once(manager.register(negative_cases,calibration,label='fresh-rejected-proposal'),bad,current,calibration)
    negative_gate=store.record_rejection(bad,negative,contract,manager=manager,expected_active=current.genome_id)
    rolled_back=False
    if current.genome_id!=baseline.genome_id:
        store.rollback(baseline.genome_id,expected_active=current.genome_id,reason='Explicit demonstration of operator rollback to initial baseline')
        rolled_back=True
    report={'contract':contract.to_data(),'per_attempt_alpha':contract.alpha/contract.max_generations,
            'generations':runs,'negative_receipt':negative,'negative_gate':negative_gate,
            'rollback_performed':rolled_back,'final_state':store.snapshot(),
            'limitations':'Declarative Euler/RK4 descendants, fresh synthetic holdouts; not general self-modifying software.'}
    write_json(root/'report.json',report)
    return report


def domain_suite():
    from .core.units import Quantity as Q,ONE,METER,SECOND,KILOGRAM,KELVIN,AMPERE,MOLE,NEWTON,JOULE
    from .domains.contracts import PASCAL,WATT,OHM
    from .domains.engineering import axial_bar,cantilever_tip
    from .domains.materials import thermoelastic
    from .domains.chemistry import balance_reaction,two_species_equilibrium
    from .domains.control import StateSpace
    from .domains.earth import hydrostatic_pressure
    from .domains.biology import logistic,sir
    from .worlds.multiphysics import electrothermal
    from .domains.circuits import Resistor,solve_dc
    circuits=solve_dc((Resistor('source','ground','10'),),{'source':'2','ground':'-2'},ground='ground')
    return {'engineering':axial_bar(Q(100,NEWTON),Q(2,METER),Q('1/100',METER**2),Q(1000000,PASCAL)),
            'beam':cantilever_tip(Q(1,NEWTON),Q(1,METER),Q(1000000,PASCAL),Q('1/1000',METER**4)),
            'materials':thermoelastic(Q(200000000000,PASCAL),Q('1/100000',ONE/KELVIN),Q(10,KELVIN),Q(0,ONE)),
            'chemistry':balance_reaction(('C2H6','O2'),('CO2','H2O')),
            'equilibrium':two_species_equilibrium(Q(3,MOLE),Q(2,ONE)),
            'control':StateSpace(((0,1),(-2,-3)),(0,1),(1,0)).analyze(),
            'earth':hydrostatic_pressure(Q(1000,KILOGRAM/METER**3),Q('981/100',METER/SECOND**2),Q(10,METER),Q(101325,PASCAL)),
            'logistic':logistic(Q(10,ONE),Q(100,ONE),Q(1,ONE/SECOND),Q(2,SECOND)),
            'sir':sir(('99/100','1/100','0'),Q('3/10',ONE/SECOND),Q('1/10',ONE/SECOND),Q(10,SECOND)),
            'multiphysics':electrothermal(Q(2,AMPERE),Q(10,OHM),Q(100,JOULE/KELVIN),Q(5,WATT/KELVIN),Q('1/1000',ONE/KELVIN),Q(10,SECOND)),
            'circuits_summary':{'verified':circuits.verified,'voltages':[[n,str(v)] for n,v in circuits.voltages],
                                'power_W':str(circuits.dissipated_power),'scope':'exact ideal DC resistor network'}}


def team_demo():
    from .agents import Permissions
    from .agents.proposals import Action,Proposal
    from .agents.scientific_teams import TeamMember,TeamJob,ScientificTeam
    from .agents.tool_registry import scientific_registry
    from .forge.reverse_builder import generate_task
    generated=generate_task('linear_system',42,2)
    proposer=TeamMember('local-proposer','proposer',Permissions(frozenset({'solve'})))
    verifier=TeamMember('local-verifier','verifier',Permissions(frozenset({'verify'})))
    first=Proposal('Solve exact task',(Action('solve','solve',canonical_json({'task':generated.task.to_data()})),),'Synthetic local tool, not autonomous discovery')
    second=Proposal('Independently check candidate',(Action('verify','verify',canonical_json({'task':generated.task.to_data(),'candidate':generated.witness})),),'Declared verifier identity, not authenticated human peer review')
    return ScientificTeam((proposer,verifier),scientific_registry()).run((TeamJob('proposal',proposer.member_id,first),TeamJob('verification',verifier.member_id,second,('proposal',))))


def run_research_laboratory(destination):
    from .knowledge.versioned_claims import ClaimRevision,ClaimLedger
    from .knowledge.provenance_audit import Evidence,audit_ledger
    from .knowledge.federation import export_snapshot,Federation
    from .knowledge.claim_graph import ClaimGraph
    from .knowledge.dependency_impact import dependency_impact
    from .knowledge.peer_review import Reviewer,Review,ReviewBoard
    from .falsifier.search import investigate
    from .documents.publication import research_document,publish
    destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.research-',dir=destination.parent))
    try:
        discovery=discovery_demo();write_json(stage/'discovery.json',discovery)
        evolution=evolution_demo(stage/'evolution')
        domains=domain_suite();write_json(stage/'domains.json',domains)
        teams=team_demo();write_json(stage/'teams.json',teams)
        registry={}
        def evidence(kind,payload,origin):
            item=Evidence(kind,canonical_json(payload),origin,'MIT',True)
            registry[item.evidence_id]=item
            return item.evidence_id
        discovery_id=evidence('discovery',discovery,'Nabla bounded synthetic research program')
        ledger=ClaimLedger()
        hypothesis=ClaimRevision('quadratic-model',discovery['regression']['selected']['expression'],'supported',(discovery_id,))
        ledger.append(hypothesis)
        for name,report in domains.items():
            if name=='circuits_summary':continue
            key=evidence('domain_result',report,'Nabla bounded '+name+' model')
            ledger.append(ClaimRevision('domain-'+name,report['model']+' agrees with its declared residual checks','supported',(key,)))
        for i,run in enumerate(evolution['generations']):
            key=evidence('policy',run['receipt'],'Trusted local policy evaluator')
            status='supported' if run['gate']['accepted'] else 'refuted'
            ledger.append(ClaimRevision('policy-improvement-'+str(i+1),'Candidate policy improves declared synthetic holdout within contract',status,(key,)))
        false=ClaimRevision('universal-false-identity','x*x = x for every real x','proposed');ledger.append(false)
        dependent=ClaimRevision('dependent-conjecture','Downstream proposal depending on an unproved identity','proposed',dependencies=(false.revision_id,));ledger.append(dependent)
        before_refutation=ledger.to_data()
        refutation=evidence('refutation',investigate('x*x','x',radius=4,budget=1000),'Exact bounded counterexample search')
        corrected=replace(false,status='refuted',evidence=(refutation,),previous=false.revision_id);ledger.append(corrected)
        alternate=ClaimLedger.from_data(before_refutation);alternate.append(replace(false,status='withdrawn',previous=false.revision_id))
        impact=dependency_impact(ClaimGraph(ledger),false.revision_id);write_json(stage/'dependency-impact.json',impact)
        authors={hypothesis.revision_id:('local-proposer',)}
        board=ReviewBoard((Reviewer('declared-reviewer-a',('mathematics',)),Reviewer('declared-reviewer-b',('mathematics',))),authors=authors)
        for who in ('declared-reviewer-a','declared-reviewer-b'):
            board.submit(Review(hypothesis.revision_id,who,'mathematics','accept','Synthetic review declaration after reproducibility check',(discovery_id,)),ledger)
        review=board.decision(hypothesis.revision_id);write_json(stage/'peer-review.json',review)
        audit=audit_ledger(ledger,registry)
        if not audit['valid']:raise ValueError('Knowledge provenance audit failed: '+str(audit))
        write_json(stage/'provenance.json',audit)
        snapshot=export_snapshot(ledger,registry,peer_id='local-lab-a');write_json(stage/'knowledge.json',snapshot)
        other=export_snapshot(alternate,registry,peer_id='local-lab-b')
        federation=Federation(allow_unsigned=True);federation.ingest(snapshot);federation.ingest(other)
        reconciliation=federation.reconcile();write_json(stage/'federation.json',reconciliation)
        sources={hashlib.sha256((stage/name).read_bytes()).hexdigest():stage/name for name in ('discovery.json','domains.json','provenance.json','evolution/report.json')}
        document=research_document('Nabla: Discovery, Evolution and versioned scientific knowledge',
             hypothesis='Bounded models and policy changes can be investigated with reproducible evidence and explicit refutation.',
             method='Exact polynomial grammar; separate calibration/holdout inputs; one-use numerical holdouts; SI disciplinary models; version-addressed evidence.',
             results=f'Discovery holdout match: {discovery["regression"]["holdout_result"]["matches_all"]}. Accepted policy generations: {sum(r["gate"]["accepted"] for r in evolution["generations"])}. Domain artifacts: {len(domains)-1}. Provenance audit: {audit["valid"]}.',
             discussion='A local corpus query does not establish global novelty. Declared local reviewers and unsigned demo peers do not constitute independent scientific peer review.',
             limitations='Selected synthetic models, no universal scientific discovery, general RSI or experimental validation. Conflicting revisions are preserved rather than silently merged.',
             evidence_ids=tuple(sources))
        publish(document,stage/'article',pdf_backend='typst',evidence_sources=sources,require_evidence=True)
        summary={'discovery_program_id':discovery['program_id'],'accepted_policy_generations':sum(r['gate']['accepted'] for r in evolution['generations']),
                 'rollback_demonstrated':evolution['rollback_performed'],'domain_models':len(domains)-1,
                 'knowledge_revisions':len(ledger.revisions),'provenance_valid':audit['valid'],
                 'concurrent_claims_preserved':len(reconciliation['concurrent_heads']),
                 'team_completed':teams['completed'],'global_novelty_established':False,'experimental_validation':False}
        write_json(stage/'summary.json',summary)
        write_json(stage/'manifest.json',{'files':{p.relative_to(stage).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(stage.rglob('*')) if p.is_file()}})
        stage.rename(destination)
        return summary
    finally:
        if stage.exists():shutil.rmtree(stage)
