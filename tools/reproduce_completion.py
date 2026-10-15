"""Reproduce bounded cross-phase completion evidence without external publication.

Usage: python tools/reproduce_completion.py .nabla/completion --pdf-backend typst
Requires extras: graphics, documents (when compiling), federation. Ed25519 demo
keys are ephemeral and kept in memory; only public keys/signatures are exported.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile


def reproduce(destination, *, pdf_backend=None):
    from nablamath.core.semantic_ir import canonical_json, fingerprint
    from nablamath.forge.reverse_builder import generate_task
    from nablamath.datasets.schema import make_record
    from nablamath.datasets.serializer import write_atomic, iter_load
    from nablamath.graphics.sampling import adaptive_function_scene
    from nablamath.graphics.artifacts import export_scene, verify_scene_bundle
    from nablamath.worlds import ModelSpec, simulate_adaptive
    from nablamath.documents.document_model import Table, Section, Document
    from nablamath.documents.publication import publish, verify_publication
    from nablamath.knowledge.identity import generate_signing_key, sign_snapshot, PeerKey, PeerTrust, public_key_hex
    from nablamath.knowledge.federation import export_snapshot, SignedFederation
    from nablamath.knowledge.versioned_claims import ClaimRevision, ClaimLedger
    from nablamath.knowledge.provenance_audit import Evidence
    from nablamath.agents import ScientificProposal, Action, Planner, Permissions, scientific_registry
    from nablamath.agents.planner import verify_run
    from nablamath.benchmarks.analysis import analyze_benchmark
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='.completion-', dir=destination.parent))
    def save(name, data):
        path = root/name
        path.write_text(canonical_json(data)+'\n', encoding='utf-8')
        return hashlib.sha256(path.read_bytes()).hexdigest(), path
    try:
        generated = generate_task('linear_system', 71, 2)
        record = make_record(generated.task, generated.witness, license_id='CC0-1.0',
                            provenance='reproduce_completion seed 71', scope='bounded exact', limitations='synthetic')
        write_atomic((record,), root/'dataset.jsonl')
        with (root/'dataset.jsonl').open('rb') as stream:
            if list(iter_load(stream)) != [record]:
                raise ValueError('Dataset roundtrip failed')
        curves = export_scene(adaptive_function_scene('x*x*x',xmin=-1,xmax=2),root/'curve')
        if not verify_scene_bundle(root/'curve'):
            raise ValueError('Scene replay failed')
        trajectory = simulate_adaptive(ModelSpec('harmonic_oscillator',(2.,1.),3.,5.),atol=1e-12,rtol=1e-10)
        if trajectory['max_trajectory_reference_error'] >= 1e-8:
            raise ValueError('Adaptive reference error exceeded profile')
        trajectory_id, trajectory_path = save('trajectory.json',trajectory)
        task = generated.task.to_data()
        plan = ScientificProposal('Solve and verify a constructed linear system',(
            Action('solve1','solve',canonical_json({'task':task})),
            Action('verify1','verify',canonical_json({'task':task,'candidate':
                   {'$result':{'action':'solve1','path':['candidate']}}}),('solve1',))),
            'Two trusted registered tools; no independent human review')
        agent = Planner(scientific_registry(),Permissions(frozenset({'solve','verify'}))).run(plan)
        if not agent['completed'] or not verify_run(agent):
            raise ValueError('Agent replay failed')
        agent_id, agent_path = save('agent.json',agent)
        evidence = Evidence('exact_trace',canonical_json(agent['receipts'][0]['result']),
                            'seeded local construction verified exactly','CC0-1.0',True)
        ledger = ClaimLedger((ClaimRevision('demo-solution','Constructed linear system has this verified solution',
                              'supported',(evidence.evidence_id,)),))
        private_key = generate_signing_key()
        trust = PeerTrust((PeerKey('completion-demo',public_key_hex(private_key)),))
        envelope = sign_snapshot(export_snapshot(ledger,{evidence.evidence_id:evidence},peer_id='completion-demo'),private_key)
        federation = SignedFederation(trust)
        verification = federation.ingest(envelope)
        if not verification['valid'] or not verification['authenticated']:
            raise ValueError('Signature or provenance failed')
        save('signed-snapshot.json',envelope)
        save('public-trust.json',trust.to_data())
        federation_id, federation_path = save('federation.json',federation.reconcile())
        table = Table('Reexecuted synthetic results',('Check','Result'),(
            ('ODE analytic maximum error',str(trajectory['max_trajectory_reference_error'])),
            ('Agent replay','passed'),('Snapshot signature','Ed25519 pinned key')),
            (trajectory_id,agent_id,federation_id))
        document = Document('Nabla completion evidence',(Section('Results','Bounded local demonstrations, with replay.',tables=(table,)),),
                            limitations='Synthetic evidence; no demonstrated learning gain, experimental validity or real-world peer identity.')
        publish(document,root/'paper',pdf_backend=pdf_backend,
                evidence_sources={trajectory_id:trajectory_path,agent_id:agent_path,federation_id:federation_path},require_evidence=True)
        if not verify_publication(root/'paper'):
            raise ValueError('Publication replay failed')
        repo = Path(__file__).resolve().parents[1]
        benchmark = json.loads((repo/'benchmarks/results/independent-solvers-2026-10.json').read_text(encoding='utf-8'))
        save('solver-analysis.json',analyze_benchmark(benchmark))
        summary = {'schema_version':1,'dataset_roundtrip':True,'curve_replay':curves['model']['valid'],
                   'adaptive_max_reference_error':trajectory['max_trajectory_reference_error'],
                   'adaptive_steps':trajectory['accepted_steps'],'agent_result_binding_replayed':True,
                   'signed_evidence_snapshot_verified':True,'publication_replayed':True,'pdf_backend':pdf_backend,
                   'experimental_validation':False,'learning_gain_established':False,
                   'independent_peer_identity_verified':False,
                   'limitations':'Ephemeral demo signing keys authenticate only the supplied pinned key, not a real-world identity.'}
        save('summary.json',summary)
        files = {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(root.rglob('*')) if p.is_file()}
        save('manifest.json',{'schema_version':1,'files':files,'artifact_id':fingerprint(files)})
        root.rename(destination)
        return summary
    finally:
        if root.exists():
            shutil.rmtree(root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--pdf-backend',choices=('typst','latex'))
    args = parser.parse_args()
    print(json.dumps(reproduce(args.destination,pdf_backend=args.pdf_backend),sort_keys=True))
