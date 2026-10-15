"""Adversarial review: authentic signatures bind semantics and audience."""
import copy
import pytest
from nablamath.knowledge.identity import PeerTrust, PeerKey, generate_signing_key, public_key_hex
from nablamath.knowledge.institutional_identity import issue_attestation, AttestationVerifier, CONTEXT
from nablamath.knowledge.distributed_provenance import ProvenanceLog
from nablamath.network.signatures import sign_message


@pytest.fixture
def signing():
    pytest.importorskip('cryptography')
    key=generate_signing_key()
    return key,PeerTrust([PeerKey('issuer',public_key_hex(key))])


@pytest.mark.parametrize('field,value',[('subject','mallory'),('institution','other institution'),('competencies',['admin']),('serial','replacement')])
def test_attestation_payload_tamper_is_not_authenticated(signing,field,value):
    key,trust=signing
    credential=issue_attestation(key,issuer='issuer',subject='alice',institution='declared institution',
        competencies=['algebra'],issued_unix=10,expires_unix=90,serial='credential')
    forged=copy.deepcopy(credential); forged['payload'][field]=value
    assert not AttestationVerifier(trust).verify(forged,now_unix=20)['valid']


def test_valid_issuer_signature_cannot_omit_serial_binding(signing):
    key,trust=signing
    envelope=sign_message({'kind':CONTEXT,'subject':'alice','institution':'institute','competencies':['algebra'],'serial':'a'},
        key,peer_id='issuer',audience=CONTEXT,nonce='b',issued_unix=10,expires_unix=90)
    result=AttestationVerifier(trust).verify(envelope,now_unix=20)
    assert not result['valid'] and 'Serial binding' in result['reason']


def test_credentials_cannot_be_replayed_as_provenance_events(tmp_path,signing):
    key,trust=signing
    credential=issue_attestation(key,issuer='issuer',subject='alice',institution='institute',
        competencies=['algebra'],issued_unix=10,expires_unix=90,serial='credential')
    log=ProvenanceLog(tmp_path/'log',trust)
    try:
        with pytest.raises(ValueError,match='audience'):log.ingest(credential,now_unix=20)
        assert log.export()==[]
    finally:log.close()
