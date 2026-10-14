from dataclasses import replace
import json
import secrets
import unittest
from nablamath.core.semantic_ir import canonical_json,fingerprint
from nablamath.knowledge.versioned_claims import ClaimRevision,ClaimLedger
from nablamath.knowledge.claim_graph import ClaimGraph,ClaimRelation
from nablamath.knowledge.dependency_impact import dependency_impact
from nablamath.knowledge.peer_review import Review,Reviewer,ReviewBoard
from nablamath.knowledge.provenance_audit import Evidence,audit_ledger
from nablamath.knowledge.federation import Federation,export_snapshot,verify_snapshot
from nablamath.knowledge.semantic_reconciliation import reconcile,semantic_key
from nablamath.core.units import Quantity as Q,METER,NEWTON
from nablamath.domains.contracts import PASCAL
from nablamath.domains.engineering import axial_bar


def fixture():
    report=axial_bar(Q(1,NEWTON),Q(1,METER),Q(1,METER**2),Q(1000,PASCAL))
    evidence=Evidence('domain_result',canonical_json(report),'synthetic material fixture','CC0-1.0',True)
    registry={evidence.evidence_id:evidence}
    claim=ClaimRevision('bar-extension','Extension is 1/1000 m under declared conditions','supported',(evidence.evidence_id,))
    return ClaimLedger((claim,)),registry,claim


class KnowledgeTests(unittest.TestCase):
    def test_evidence_replays_and_hash_only_tampering_is_rejected(self):
        ledger,evidence,claim=fixture()
        self.assertTrue(audit_ledger(ledger,evidence)['valid'])
        data=next(iter(evidence.values())).payload
        data['outputs']['extension']='999'
        payload={k:v for k,v in data.items() if k!='result_id'};data['result_id']=fingerprint(payload)
        forged=Evidence('domain_result',canonical_json(data),'fixture','CC0-1.0',True)
        bad=ClaimLedger((replace(claim,evidence=(forged.evidence_id,)),))
        self.assertFalse(audit_ledger(bad,{forged.evidence_id:forged})['valid'])
        self.assertFalse(audit_ledger(ledger,{})['valid'])
        self.assertEqual(ClaimLedger.from_data(ledger.to_data()).to_data(),ledger.to_data())

    def test_refutation_impact_preserves_historical_results_and_rejects_cycles(self):
        ledger,evidence,claim=fixture()
        child=ClaimRevision('derived','Derived from bar','supported',claim.evidence,(claim.revision_id,))
        ledger.append(child)
        correction=replace(claim,status='refuted',previous=claim.revision_id)
        ledger.append(correction)
        graph=ClaimGraph(ledger)
        report=dependency_impact(graph,claim.revision_id)
        self.assertIn(child.revision_id,report['affected'])
        self.assertTrue(next(a for a in report['alerts'] if a['revision_id']==child.revision_id)['requires_review'])
        self.assertEqual(ledger.get(child.revision_id).status,'supported')
        with self.assertRaises(ValueError):ClaimGraph(ledger,(ClaimRelation(claim.revision_id,child.revision_id,'uses','bad cycle'),))

    def test_review_independence_conflicts_versions_and_no_auto_promotion(self):
        ledger,evidence,claim=fixture()
        board=ReviewBoard((Reviewer('a',('engineering',)),Reviewer('b',('engineering',)),Reviewer('author',('engineering',)),
                           Reviewer('conflict',('engineering',),('author',))),authors={claim.revision_id:('author',)})
        for reviewer in ('author','conflict'):
            with self.assertRaises(ValueError):board.submit(Review(claim.revision_id,reviewer,'engineering','accept','check',claim.evidence),ledger)
        for reviewer in ('a','b'):
            board.submit(Review(claim.revision_id,reviewer,'engineering','accept','checked equations',claim.evidence),ledger)
        decision=board.decision(claim.revision_id)
        self.assertTrue(decision['recommended']);self.assertFalse(decision['claim_status_changed'])
        old=decision['reviews'][0]
        board.submit(Review(claim.revision_id,old['reviewer_id'],'engineering','revise','new limitation',claim.evidence,old['review_id']),ledger)
        self.assertFalse(board.decision(claim.revision_id)['recommended'])

    def test_authenticated_federation_preserves_concurrent_heads(self):
        ledger,evidence,claim=fixture();key=secrets.token_bytes(32)
        ledger.append(replace(claim,status='refuted',previous=claim.revision_id))
        bundle=export_snapshot(ledger,evidence,peer_id='lab-a',key=key)
        self.assertTrue(verify_snapshot(bundle,key=key)['authenticated'])
        self.assertFalse(verify_snapshot(bundle,key=secrets.token_bytes(32))['valid'])
        fork=ClaimLedger((claim,replace(claim,status='withdrawn',previous=claim.revision_id)))
        bundle2=export_snapshot(fork,evidence,peer_id='lab-b',key=key)
        federation=Federation(trusted_peers={'lab-a':key,'lab-b':key})
        federation.ingest(bundle);federation.ingest(bundle2)
        report=federation.reconcile()
        self.assertIn(claim.claim,report['concurrent_heads'])
        self.assertFalse(report['automatic_merge_performed'])
        unsigned=export_snapshot(ledger,evidence,peer_id='local')
        self.assertFalse(verify_snapshot(unsigned)['valid'])
        self.assertTrue(verify_snapshot(unsigned,allow_unsigned=True)['valid'])

    def test_semantic_reconciliation_respects_domains_units_and_statement(self):
        a=ClaimRevision('a','x*x','proposed');b=ClaimRevision('b','x^2','proposed')
        metadata={'kind':'polynomial','expression':'x*x','domain':['-1','1'],
                  'input_unit':{'dimensions':[0]*7,'scale':'1'},'output_unit':{'dimensions':[0]*7,'scale':'1'},'assumptions':[]}
        key=semantic_key(a,metadata)
        other={**metadata,'expression':'x^2'}
        self.assertEqual(key,semantic_key(b,other))
        self.assertNotEqual(key,semantic_key(b,{**other,'domain':['0','1']}))
        with self.assertRaises(ValueError):semantic_key(a,{**metadata,'expression':'x+1'})

    def test_successive_snapshots_are_not_misclassified_as_concurrent_forks(self):
        ledger,evidence,claim=fixture()
        original=ClaimLedger.from_data(ledger.to_data())
        ledger.append(replace(claim,status='withdrawn',previous=claim.revision_id))
        self.assertEqual(reconcile((original,ledger))['concurrent_heads'],{})


class ScientificTeamTests(unittest.TestCase):
    def test_independent_local_roles_and_verified_candidate(self):
        from nablamath.research_workflows import team_demo
        report=team_demo()
        self.assertTrue(report['completed'])
        self.assertTrue(report['all_candidates_verified'])
        self.assertEqual([job['role'] for job in report['jobs']],['proposer','verifier'])
        self.assertFalse(report['identities_independently_authenticated'])

    def test_role_capabilities_are_validated_before_any_job_runs(self):
        from nablamath.agents.permissions import Permissions
        from nablamath.agents.scientific_teams import TeamMember
        with self.assertRaises(ValueError):TeamMember('reviewer','reviewer',Permissions(frozenset({'solve'})))
