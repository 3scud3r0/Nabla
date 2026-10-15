"""Adversarial contract checks for local network identity and moderation."""
import copy
import json

import pytest

from nablamath.network.signatures import MessageVerifier, ProtocolTrust, sign_message
from nablamath.knowledge.identity import PeerKey, generate_signing_key, public_key_hex
from nablamath.node.identity import IdentityPolicy, LocalIdentity
from nablamath.p2p.moderation import ModerationGate
from nablamath.p2p.quarantine import Quarantine
from nablamath.p2p.reputation import Reputation


@pytest.fixture
def signed():
    pytest.importorskip('cryptography')
    key = generate_signing_key()
    trust = ProtocolTrust([PeerKey('alice', public_key_hex(key))])
    envelope = sign_message({'claim': 1}, key, peer_id='alice', audience='bob', nonce='1', issued_unix=100, expires_unix=200)
    return key, trust, envelope


def test_signature_forgery_replay_and_audience(signed):
    key, trust, envelope = signed
    verifier = MessageVerifier(trust, 'bob')
    tampered = copy.deepcopy(envelope)
    tampered['payload']['claim'] = 2
    assert not verifier.verify(tampered, now_unix=100)['valid']
    assert not MessageVerifier(trust, 'other').verify(envelope, now_unix=100)['valid']
    assert verifier.verify(envelope, now_unix=100)['valid']
    assert not verifier.verify(envelope, now_unix=101)['valid']


def test_revocation_and_rotation(signed):
    key, trust, envelope = signed
    replacement = generate_signing_key()
    trust.rotate('alice', public_key_hex(replacement))
    assert not MessageVerifier(trust, 'bob').verify(envelope, now_unix=100)['valid']
    with pytest.raises(ValueError):
        trust.pin(PeerKey('alice', public_key_hex(key)))
    fresh = sign_message({}, replacement, peer_id='alice', audience='bob', nonce='2', issued_unix=100, expires_unix=200)
    assert MessageVerifier(trust, 'bob').verify(fresh, now_unix=100)['valid']


@pytest.mark.parametrize('now', [99, 200, -1, True])
def test_bad_times(signed, now):
    _, trust, envelope = signed
    assert not MessageVerifier(trust, 'bob').verify(envelope, now_unix=now)['valid']


def test_replay_capacity_and_clock_rollback(signed):
    key, trust, envelope = signed
    verifier = MessageVerifier(trust, 'bob', max_pending=1)
    assert verifier.verify(envelope, now_unix=100)['valid']
    second = sign_message({}, key, peer_id='alice', audience='bob', nonce='2', issued_unix=100, expires_unix=200)
    assert not verifier.verify(second, now_unix=101)['valid']
    assert not verifier.verify(second, now_unix=99)['valid']
    third = sign_message({}, key, peer_id='alice', audience='bob', nonce='3', issued_unix=200, expires_unix=300)
    assert verifier.verify(third, now_unix=200)['valid']


def test_no_crypto_fails_closed(signed, monkeypatch):
    _, trust, envelope = signed
    def unavailable():
        raise ImportError('optional dependency missing')
    monkeypatch.setattr('nablamath.network.signatures._crypto', unavailable)
    assert not MessageVerifier(trust, 'bob').verify(envelope, now_unix=100)['valid']


def test_identity_requires_explicit_consent():
    identity = LocalIdentity('alice')
    with pytest.raises(PermissionError):
        identity.activate()
    with pytest.raises(PermissionError):
        identity.rotate(recovery=True)
    with pytest.raises(ValueError):
        IdentityPolicy(allow_signing='yes')


def test_identity_revocation_and_recovery(signed):
    identity = LocalIdentity('alice', IdentityPolicy(True, True, True))
    old = identity.activate()
    assert identity.rotate(recovery=True) != old
    assert old in identity.revoked_keys
    identity.revoke()
    assert identity.public_key is None
    with pytest.raises(PermissionError):
        identity.sign({}, audience='bob', nonce='1', issued_unix=1, expires_unix=2)


def test_reputation_deduplicates_and_preserves_negative_observations():
    reputation = Reputation(max_events=3, block_threshold=1)
    assert reputation.record('alice', '1', violation=True, reason='invalid result')
    assert not reputation.record('alice', '1', violation=True, reason='invalid result')
    with pytest.raises(ValueError):
        reputation.record('mallory', '1', violation=False, reason='changed')
    reputation.record('alice', '2', violation=False, reason='valid result')
    assert reputation.report('alice')['blocked']
    assert reputation.report('alice')['scientific_truth_score'] is None
    audit = reputation.audit()
    audit[0]['peer_id'] = 'mutated'
    assert reputation.audit()[0]['peer_id'] == 'alice'


def test_moderation_quarantines_forgery_without_penalizing_claimed_peer(signed, tmp_path):
    _, trust, envelope = signed
    gate = ModerationGate(MessageVerifier(trust, 'bob'), Quarantine(tmp_path))
    forged = copy.deepcopy(envelope)
    forged['payload']['claim'] = 'poisoned'
    denied = gate.receive(json.dumps(forged).encode(), source='transport-1', now_unix=100)
    assert not denied['accepted'] and denied['quarantine_id']
    assert gate.reputation.report('alice')['observations'] == 0
    accepted = gate.receive(json.dumps(envelope).encode(), source='transport-1', now_unix=100)
    assert accepted['accepted'] and accepted['payload'] == {'claim': 1}
    assert not gate.receive(json.dumps(envelope).encode(), source='transport-1', now_unix=100)['accepted']
    assert not gate.receive(b'{bad', source='transport-1', now_unix=100)['accepted']


def test_moderation_enforces_local_abuse_policy(signed, tmp_path):
    _, trust, envelope = signed
    reputation = Reputation(block_threshold=1)
    reputation.record('alice', 'operator-observation', violation=True, reason='reviewed abuse')
    gate = ModerationGate(MessageVerifier(trust, 'bob'), Quarantine(tmp_path), reputation=reputation, max_decisions=1)
    result = gate.receive(json.dumps(envelope).encode(), source='socket', now_unix=100)
    assert not result['accepted'] and 'payload' not in result
    with pytest.raises(ValueError, match='Audit capacity'):
        gate.receive(b'{}', source='socket', now_unix=100)


def test_claimed_peer_cannot_reuse_another_peers_key(signed):
    key, trust, _ = signed
    forged_identity = sign_message({}, key, peer_id='mallory', audience='bob', nonce='2', issued_unix=100, expires_unix=200)
    assert not MessageVerifier(trust, 'bob').verify(forged_identity, now_unix=100)['valid']


def test_signing_copies_payload_and_rejects_unbounded_lifetime(signed):
    key, trust, _ = signed
    payload = {'nested': [1]}
    envelope = sign_message(payload, key, peer_id='alice', audience='bob', nonce='2', issued_unix=100, expires_unix=200)
    payload['nested'].append(2)
    assert MessageVerifier(trust, 'bob').verify(envelope, now_unix=100)['payload'] == {'nested': [1]}
    with pytest.raises(ValueError, match='lifetime'):
        sign_message({}, key, peer_id='alice', audience='bob', nonce='3', issued_unix=100, expires_unix=1000000)


def test_reputation_capacity_fails_closed_without_erasing_history():
    reputation = Reputation(max_events=1, block_threshold=1)
    reputation.record('alice', '1', violation=True, reason='reviewed abuse')
    with pytest.raises(ValueError, match='capacity'):
        reputation.record('bob', '2', violation=False, reason='new event')
    assert reputation.report('alice')['blocked']


def test_unsigned_or_schema_confused_messages_fail_closed(signed):
    _, trust, envelope = signed
    verifier = MessageVerifier(trust, 'bob')
    for malformed in (None, [], {}, {'signature': '00'}, {**envelope, 'schema_version': True}, {**envelope, 'unknown_field': 'x'}):
        assert not verifier.verify(malformed, now_unix=100)['valid']


@pytest.mark.parametrize('signature', ['a' * 129, 'a' * 127, 'A' * 128, 'z' * 128, 123, 'ab' * 600000])
def test_signature_encoding_rejected_before_crypto(signed, monkeypatch, signature):
    _, trust, envelope = signed
    envelope['signature'] = signature
    def must_not_decode():
        raise AssertionError('Malformed signature reached cryptography')
    monkeypatch.setattr('nablamath.network.signatures._crypto', must_not_decode)
    assert not MessageVerifier(trust, 'bob').verify(envelope, now_unix=100)['valid']


@pytest.mark.parametrize('payload', [{1: 'integer key'}, {'tuple': (1, 2)}, {'nan': float('nan')}, {'nodes': [0] * 20001}])
def test_signature_payload_requires_bounded_native_json(signed, payload):
    key, trust, envelope = signed
    with pytest.raises(ValueError):
        sign_message(payload, key, peer_id='alice', audience='bob', nonce='new', issued_unix=100, expires_unix=200)
    envelope['payload'] = payload
    assert not MessageVerifier(trust, 'bob').verify(envelope, now_unix=100)['valid']


def test_signature_payload_depth_checked_before_copy(signed):
    key, trust, envelope = signed
    nested = []
    for _ in range(1100):
        nested = [nested]
    with pytest.raises(ValueError, match='structural budget'):
        sign_message(nested, key, peer_id='alice', audience='bob', nonce='deep', issued_unix=100, expires_unix=200)
    envelope['payload'] = nested
    assert not MessageVerifier(trust, 'bob').verify(envelope, now_unix=100)['valid']
