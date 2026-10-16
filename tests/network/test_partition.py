"""Partition simulation with signed, conflicting operator histories."""
import pytest
from nablamath.core.semantic_ir import fingerprint
from nablamath.knowledge.identity import generate_signing_key,public_key_hex,PeerKey,PeerTrust
from nablamath.knowledge.distributed_provenance import ProvenanceLog,provenance_event
from services.federation.reconciliation import Reconciler


def test_conflicting_partition_history_is_retained_in_quarantine(tmp_path):
    pytest.importorskip('cryptography')
    key=generate_signing_key();trust=PeerTrust([PeerKey('A',public_key_hex(key))])
    def make(nonce,previous=None):
        return provenance_event(key,operator='A',artifact='a'*64,action='publish' if previous is None else 'endorse',
                                previous=previous,nonce=nonce,issued_unix=1,expires_unix=50)
    root=make('root');parent=fingerprint(root);left=make('left',parent);right=make('right',parent)
    log=ProvenanceLog(tmp_path/'log',trust);service=Reconciler(tmp_path/'inbox',log)
    service.receive([left,right],now_unix=2)
    report=service.receive([root],now_unix=3)
    states=[r['state'] for r in report['events']]
    assert states.count('accepted')==2 and states.count('quarantined')==1
    assert len(log.export())==2
    service.close();log.close()
