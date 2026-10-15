"""Actual signature verification rejects changed bytes and unauthorized operators."""
import copy
import pytest
from nablamath.knowledge.identity import generate_signing_key,public_key_hex,PeerKey,PeerTrust
from nablamath.knowledge.distributed_provenance import ProvenanceLog,provenance_event


@pytest.mark.parametrize('mutation',['artifact','signature','operator'])
def test_poisoned_event_never_admitted(tmp_path,mutation):
    pytest.importorskip('cryptography')
    key=generate_signing_key();trust=PeerTrust([PeerKey('A',public_key_hex(key))])
    event=provenance_event(key,operator='A',artifact='a'*64,action='publish',nonce='n',issued_unix=1,expires_unix=50)
    event=copy.deepcopy(event)
    if mutation=='artifact':event['payload']['artifact']='b'*64
    elif mutation=='signature':event['signature']='00'*64
    else:event['peer_id']='B'
    log=ProvenanceLog(tmp_path/'log',trust)
    with pytest.raises(ValueError):log.ingest(event,now_unix=2)
    assert log.export()==[]
    log.close()
