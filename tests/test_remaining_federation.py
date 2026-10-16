"""Configured issuer trust and durable causal provenance, not external accreditation."""
import copy
import pytest
from nablamath.knowledge.identity import PeerTrust, PeerKey, generate_signing_key, public_key_hex
from nablamath.knowledge.institutional_identity import issue_attestation, AttestationVerifier
from nablamath.knowledge.distributed_provenance import provenance_event, ProvenanceLog
from services.federation.reconciliation import Reconciler

@pytest.fixture
def keys():
    pytest.importorskip('cryptography')
    key=generate_signing_key()
    return key,PeerTrust([PeerKey('operator',public_key_hex(key))])


def event(key,nonce='root',previous=None,action='publish',artifact='a'*64):
    return provenance_event(key,operator='operator',artifact=artifact,action=action,
                            previous=previous,nonce=nonce,issued_unix=10,expires_unix=100)


def test_attestation_pin_expiry_revocation_and_claim_limits(keys):
    key,trust=keys
    credential=issue_attestation(key,issuer='operator',subject='alice',institution='declared university',
                                competencies=['algebra'],issued_unix=10,expires_unix=90,serial='credential1')
    verifier=AttestationVerifier(trust)
    result=verifier.verify(credential,now_unix=20)
    assert result['valid'] and not result['real_world_identity_verified']
    assert verifier.verify(credential,now_unix=20)['valid']
    assert not verifier.verify(credential,now_unix=90)['valid']
    verifier.revoke('operator','credential1')
    assert not verifier.verify(credential,now_unix=20)['valid']
    assert not AttestationVerifier(PeerTrust()).verify(credential,now_unix=20)['valid']


def test_durable_revocation_and_operator_forks(tmp_path,keys):
    key,trust=keys; path=tmp_path/'log.db'
    log=ProvenanceLog(path,trust)
    root=event(key);identifier=log.ingest(root,now_unix=20)
    assert log.ingest(root,now_unix=20)==identifier
    revocation=event(key,'revoked',identifier,'revoke')
    log.ingest(revocation,now_unix=21)
    with pytest.raises(ValueError,match='fork|terminal'):
        log.ingest(event(key,'fork',identifier,'endorse'),now_unix=22)
    assert log.status('a'*64)['operators'][0]['revoked']
    log.close();log=ProvenanceLog(path,trust)
    assert log.status('a'*64)['operators'][0]['revoked']
    with pytest.raises(ValueError,match='rollback'):
        log.ingest(root,now_unix=19)
    log.close()


def test_persistent_nonce_prevents_replay_on_different_artifact(tmp_path,keys):
    key,trust=keys;log=ProvenanceLog(tmp_path/'log',trust)
    log.ingest(event(key),now_unix=20);log.close()
    log=ProvenanceLog(tmp_path/'log',trust)
    with pytest.raises(ValueError,match='replay'):
        log.ingest(event(key,artifact='b'*64),now_unix=20)
    assert len(log.export())==1
    log.close()


def test_partition_reorder_restart_and_recovery(tmp_path,keys):
    key,trust=keys
    from nablamath.core.semantic_ir import fingerprint
    root=event(key);child=event(key,'child',fingerprint(root),'endorse')
    log=ProvenanceLog(tmp_path/'log',trust); inbox=tmp_path/'inbox'
    reconciler=Reconciler(inbox,log)
    report=reconciler.receive([child],now_unix=20)
    assert report['events'][0]['state']=='pending'
    reconciler.close();reconciler=Reconciler(inbox,log)
    assert len(reconciler.missing([fingerprint(root),fingerprint(child)]))==2
    report=reconciler.receive([root,root],now_unix=21)
    assert {e['state'] for e in report['events']}=={'accepted'}
    assert len(log.export())==2
    reconciler.close();log.close()


def test_reconciliation_quarantines_forged_signature(tmp_path,keys):
    key,trust=keys;log=ProvenanceLog(tmp_path/'log',trust)
    reconciler=Reconciler(tmp_path/'inbox',log)
    bad=copy.deepcopy(event(key));bad['payload']['artifact']='b'*64
    report=reconciler.receive([bad],now_unix=20)
    assert report['events'][0]['state']=='quarantined' and not log.export()
    reconciler.close();log.close()


def test_consent_budget_replay_and_auditable_admission(tmp_path,keys):
    import json
    from nablamath.node.local import LocalNode
    from nablamath.node.consent import Consent,ConsentStore
    from nablamath.node.policies import IngestPolicy
    from nablamath.node.resources import ResourceBudget
    from nablamath.node.federated_session import FederatedSession,AUDIENCE
    from nablamath.network.objects import KnowledgeObject
    from nablamath.network.signatures import sign_message
    key,trust=keys
    node=LocalNode(tmp_path/'node',IngestPolicy(frozenset({'problem'}),frozenset({'MIT'})))
    consent=ConsentStore(tmp_path/'consent')
    session=FederatedSession(tmp_path/'session',node,consent,trust,ResourceBudget(network_bytes=10000))
    with pytest.raises(PermissionError):session.receive(b'{}',now_unix=20)
    consent.save(Consent(contribute=True,allow_network=True,expires_unix=50))
    obj=KnowledgeObject('problem',{'expression':'x+1'},license='MIT',provenance={'source':'test'})
    envelope=sign_message({'object':json.loads(obj.to_bytes()),'expected_id':obj.object_id},key,
                          peer_id='operator',audience=AUDIENCE,nonce='admit',issued_unix=10,expires_unix=50)
    raw=json.dumps(envelope).encode()
    receipt=session.receive(raw,now_unix=20)
    assert node.store.contains(obj.object_id) and not receipt['scientific_validity_established']
    assert session.telemetry()['total_admitted_bytes']==len(raw)
    session.close()
    session=FederatedSession(tmp_path/'session',node,consent,trust,ResourceBudget(network_bytes=10000))
    with pytest.raises(ValueError,match='replay'):session.receive(raw,now_unix=21)
    with pytest.raises(PermissionError):session.receive(raw,now_unix=21,on_battery=True)
    session.close()
    session=FederatedSession(tmp_path/'session',node,consent,trust,ResourceBudget(network_bytes=len(raw)))
    with pytest.raises(PermissionError,match='quota'):session.receive(raw,now_unix=21)
    with pytest.raises(PermissionError):session.receive(raw,now_unix=50)
    with pytest.raises(ValueError,match='rollback'):session.receive(raw,now_unix=21)
    session.close()


def test_inbox_total_capacity_includes_quarantined_rows(tmp_path,keys):
    key,trust=keys;log=ProvenanceLog(tmp_path/'log',trust)
    reconciler=Reconciler(tmp_path/'inbox',log,max_pending=1,max_total=1)
    bad=event(key);bad['signature']='00'*64
    assert reconciler.receive([bad],now_unix=20)['events'][0]['state']=='quarantined'
    with pytest.raises(ValueError,match='capacity'):
        reconciler.receive([event(key,'second')],now_unix=20)
    reconciler.close();log.close()


def test_recovery_of_committed_event_does_not_recheck_expired_credential(tmp_path,keys):
    from nablamath.core.semantic_contracts import canonical_payload
    from nablamath.core.semantic_ir import fingerprint
    key,trust=keys;log=ProvenanceLog(tmp_path/'log',trust);envelope=event(key)
    identifier=log.ingest(envelope,now_unix=20)
    reconciler=Reconciler(tmp_path/'inbox',log)
    # Crash boundary: event durable, inbox acknowledgement not yet committed.
    with reconciler.db:
        reconciler.db.execute("INSERT INTO inbox VALUES(?,?,'pending',NULL)",(identifier,canonical_payload(envelope)))
    report=reconciler.receive([],now_unix=1000)
    assert report['events'][0]['state']=='accepted'
    reconciler.close();log.close()


def test_unhashable_references_rejected_with_domain_error(keys):
    from nablamath.knowledge.distributed_provenance import validate_payload
    with pytest.raises(ValueError,match='SHA256'):
        validate_payload(dict(kind='distributed-provenance-v1',artifact='a'*64,action='publish',previous=None,references=[{}]))


def test_concurrent_connections_cannot_fork_operator_chain(tmp_path,keys):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    key,trust=keys;path=tmp_path/'log';log=ProvenanceLog(path,trust)
    root=log.ingest(event(key),now_unix=20);log.close();barrier=Barrier(2)
    def append(nonce):
        local=ProvenanceLog(path,trust);barrier.wait(timeout=3)
        try:
            local.ingest(event(key,nonce,root,'endorse'),now_unix=21)
            return True
        except ValueError:
            return False
        finally:local.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(append,['left','right']))==[False,True]


def test_canonical_frame_roundtrip_tampering_and_version():
    import json
    from nablamath.network.framing import encode_frame,decode_frame
    raw=encode_frame({'ids':['a'*64]},kind='inventory')
    assert decode_frame(raw)['payload']['ids']==['a'*64]
    with pytest.raises(ValueError,match='Unsupported'):
        decode_frame(b'NBL2'+raw[4:])
    with pytest.raises(ValueError,match='length'):
        decode_frame(raw+b'x')
    body=json.loads(raw[8:]);body['payload']['ids']=['b'*64]
    from nablamath.core.semantic_contracts import canonical_payload
    encoded=canonical_payload(body).encode()
    with pytest.raises(ValueError,match='digest'):
        decode_frame(b'NBL1'+len(encoded).to_bytes(4,'big')+encoded)


def test_fragmented_stream_and_midframe_disconnect():
    import socket
    from concurrent.futures import ThreadPoolExecutor
    from nablamath.network.framing import encode_frame,receive_frame
    raw=encode_frame({'key':'value'},kind='objects')
    left,right=socket.socketpair()
    def send():
        with left:
            for byte in raw:left.sendall(bytes([byte]))
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            task=pool.submit(send)
            assert receive_frame(right)['payload']=={'key':'value'}
            task.result(timeout=2)
    finally:right.close()
    left,right=socket.socketpair()
    left.sendall(raw[:10]);left.close()
    try:
        with pytest.raises(ConnectionError,match='Truncated'):
            receive_frame(right)
    finally:right.close()


def test_local_frame_bound_checked_before_payload_read():
    import socket
    from nablamath.network.framing import receive_frame
    left,right=socket.socketpair()
    left.sendall(b'NBL1'+(10000).to_bytes(4,'big'))
    try:
        with pytest.raises(ValueError,match='bound'):
            receive_frame(right,max_bytes=100)
    finally:left.close();right.close()
