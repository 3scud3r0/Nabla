"""Local integration tests: transaction/restart/adversarial registry and relay."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import urllib.error
import urllib.request

import pytest

from nablamath.knowledge.identity import generate_signing_key, public_key_hex
from nablamath.network.signatures import sign_message
from services.registry.app import AUDIENCE as REGISTRY_AUDIENCE, Registry
from services.registry.api import RegistryAPI, loopback_http
from services.registry.db import RegistryDB
from services.registry.metrics import registry_metrics
from services.relay.app import Relay
from services.relay.abuse import RelayLimits
from services.relay.protocol import AUDIENCE as RELAY_AUDIENCE


@pytest.fixture
def world(tmp_path):
    pytest.importorskip('cryptography')
    database = RegistryDB(tmp_path / 'service.sqlite')
    keys = {peer: generate_signing_key() for peer in ['alice', 'bob', 'mallory']}
    for peer, key in keys.items():
        database.pin_key(peer, public_key_hex(key), now_unix=100)
    registry = Registry(database)
    for peer in keys:
        registry.submit(envelope(keys, peer, registration(), 'register-' + peer), now_unix=100)
    return database, keys, registry


def envelope(keys, peer, payload, nonce, *, relay=False, now=100, expires=1000):
    return sign_message(payload, keys[peer], peer_id=peer,
                        audience=RELAY_AUDIENCE if relay else REGISTRY_AUDIENCE,
                        nonce=nonce, issued_unix=now, expires_unix=expires)


def registration(**updates):
    return dict(schema_version=1, operation='register', capabilities=['relay'],
                ttl_seconds=900, visible=True, consent=True, **updates)


def send_body(recipient='bob', body=None, ttl=100):
    return {'schema_version': 1, 'operation': 'send', 'recipient': recipient,
            'body': {'claim': 'unverified'} if body is None else body, 'ttl_seconds': ttl}


def request(keys, peer, operation, nonce, **fields):
    payload = {'schema_version': 1, 'operation': operation, **fields}
    return envelope(keys, peer, payload, nonce, relay=True)


def test_public_discovery_hides_private_entries_and_keys(world):
    database, keys, registry = world
    payload = registration()
    payload['visible'] = False
    registry.submit(envelope(keys, 'mallory', payload, 'private'), now_unix=100)
    discovered = registry.discover(now_unix=100)
    assert [p['peer_id'] for p in discovered['peers']] == ['alice', 'bob']
    assert set(discovered['peers'][0]) == {'peer_id', 'capabilities', 'expires_unix'}
    assert not registry.discover(now_unix=100, capability='simulation')['peers']
    first = registry.discover(now_unix=100, limit=1)
    second = registry.discover(now_unix=100, after=first['next_after'])
    assert [p['peer_id'] for p in second['peers']] == ['bob']


def test_registry_consent_ttl_and_withdrawal(world):
    database, keys, registry = world
    invalid = registration()
    invalid['consent'] = False
    with pytest.raises(PermissionError):
        registry.submit(envelope(keys, 'alice', invalid, 'no-consent'), now_unix=100)
    assert registry.discover(now_unix=100)['peers']
    registry.submit(envelope(keys, 'alice', {'schema_version': 1, 'operation': 'withdraw'}, 'withdraw'), now_unix=100)
    assert 'alice' not in [p['peer_id'] for p in registry.discover(now_unix=100)['peers']]
    assert registry.discover(now_unix=1000)['peers'] == []


def test_registry_replay_survives_reopening(world):
    database, keys, registry = world
    message = envelope(keys, 'alice', registration(), 'renew')
    registry.submit(message, now_unix=100)
    reopened = Registry(RegistryDB(database.path))
    with pytest.raises(PermissionError, match='Replayed'):
        reopened.submit(message, now_unix=100)
    with pytest.raises(ValueError, match='rollback'):
        reopened.discover(now_unix=99)


def test_revocation_rotation_and_unknown_key_fail_closed(world):
    database, keys, registry = world
    old = keys['alice']
    database.revoke_key('alice', public_key_hex(old), now_unix=100)
    assert 'alice' not in [p['peer_id'] for p in registry.discover(now_unix=100)['peers']]
    with pytest.raises(PermissionError):
        registry.submit(envelope(keys, 'alice', registration(), 'revoked'), now_unix=100)
    with pytest.raises(ValueError, match='reactivated'):
        database.pin_key('alice', public_key_hex(old), now_unix=100)
    keys['alice'] = generate_signing_key()
    with pytest.raises(PermissionError):
        registry.submit(envelope(keys, 'alice', registration(), 'unknown'), now_unix=100)
    database.rotate_key('alice', public_key_hex(keys['alice']), now_unix=100)
    registry.submit(envelope(keys, 'alice', registration(), 'new-key'), now_unix=100)
    assert 'alice' in [p['peer_id'] for p in registry.discover(now_unix=100)['peers']]
    persisted = RegistryDB(database.path)
    with pytest.raises(ValueError, match='reactivated'):
        persisted.pin_key('alice', public_key_hex(old), now_unix=100)


@pytest.mark.parametrize('patch', [
    {'capabilities': ['relay', 'relay']}, {'capabilities': ['arbitrary-code']},
    {'ttl_seconds': True}, {'ttl_seconds': 86401}, {'visible': 1},
    {'schema_version': True}, {'unknown': 'field'},
])
def test_registry_rejects_malformed_contracts_atomically(world, patch):
    database, keys, registry = world
    before = database.audit()
    payload = registration()
    payload.update(patch)
    with pytest.raises((ValueError, PermissionError)):
        registry.submit(envelope(keys, 'alice', payload, 'bad'), now_unix=100)
    assert database.audit() == before
    # Rejected transaction did not consume the nonce.
    registry.submit(envelope(keys, 'alice', registration(), 'bad'), now_unix=100)


def test_registry_metrics_suppress_small_cohorts_and_no_identifiers(world):
    database, _, _ = world
    metrics = registry_metrics(database, now_unix=100)
    assert metrics['active_peers'] is None and metrics['active_peers_suppressed']
    assert registry_metrics(database, now_unix=100, minimum_cohort=2)['active_peers'] == 3
    encoded = json.dumps(metrics)
    assert all(peer not in encoded for peer in ['alice', 'bob', 'mallory'])
    with pytest.raises(ValueError):
        registry_metrics(database, now_unix=100, minimum_cohort=1)


def test_registry_audit_is_paginated_and_detached(world):
    database, _, _ = world
    first = database.audit(limit=2)
    second = database.audit(after=first[-1]['sequence'], limit=2)
    assert first[-1]['sequence'] < second[0]['sequence']
    first[0]['detail']['changed'] = True
    assert 'changed' not in database.audit(limit=1)[0]['detail']
    with pytest.raises(ValueError):
        database.audit(limit=1001)


def test_registry_real_loopback_http_registration(world):
    database, keys, registry = world
    api = RegistryAPI(registry, clock=lambda: 100)
    payload = json.dumps(envelope(keys, 'alice', registration(), 'over-http')).encode()
    with loopback_http(api) as address:
        response = urllib.request.urlopen(urllib.request.Request(address + '/v1/registrations', data=payload,
                                            headers={'Content-Type': 'application/json'}), timeout=5)
        assert response.status == 200
        assert json.load(response)['registered']
        with urllib.request.urlopen(address + '/v1/peers?limit=1', timeout=5) as response:
            assert len(json.load(response)['peers']) == 1
            assert response.headers['Cache-Control'] == 'no-store'
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(urllib.request.Request(address + '/v1/registrations', data=payload), timeout=5)
        assert error.value.code == 403


@pytest.mark.parametrize('method,target,body,status', [
    ('GET', '/admin/pin', b'', 404), ('GET', '/v1/peers?limit=1000', b'', 400),
    ('GET', '/v1/peers?limit=1&limit=2', b'', 400),
    ('GET', 'http://attacker/v1/peers', b'', 400),
    ('GET', 'http://[', b'', 400), ('POST', '/v1/registrations', b'{bad', 400),
    ('POST', '/v1/registrations', b'{' * 1000001, 413),
])
def test_api_bad_routes_are_bounded(world, method, target, body, status):
    api = RegistryAPI(world[2], clock=lambda: 100)
    assert api.handle(method, target, body)[0] == status


def test_relay_delivery_lease_ack_and_restart(world):
    database, keys, _ = world
    relay = Relay(database)
    sent = relay.submit(envelope(keys, 'alice', send_body(), 'send', relay=True), now_unix=100)
    polled = relay.submit(request(keys, 'bob', 'poll', 'poll', limit=10), now_unix=100)
    message = polled['messages'][0]
    assert message['message_id'] == sent['message_id'] and message['sender'] == 'alice'
    assert message['body'] == {'claim': 'unverified'}
    reopened = Relay(RegistryDB(database.path))
    assert not reopened.submit(request(keys, 'bob', 'poll', 'poll-2', limit=10), now_unix=100)['messages']
    ack = request(keys, 'bob', 'ack', 'ack', message_id=message['message_id'], lease_token=message['lease_token'])
    assert reopened.submit(ack, now_unix=100)['acknowledged']
    assert relay.status(now_unix=100)['pending_messages'] == 0
    with pytest.raises(PermissionError, match='Replayed'):
        reopened.submit(ack, now_unix=100)


def test_relay_redelivery_replaces_expired_lease(world):
    database, keys, _ = world
    relay = Relay(database, limits=replace(RelayLimits(), lease_seconds=5))
    relay.submit(envelope(keys, 'alice', send_body(), 'send', relay=True), now_unix=100)
    first = relay.submit(request(keys, 'bob', 'poll', 'p1', limit=1), now_unix=100)['messages'][0]
    second = relay.submit(request(keys, 'bob', 'poll', 'p2', limit=1), now_unix=105)['messages'][0]
    assert first['message_id'] == second['message_id']
    assert first['lease_token'] != second['lease_token']
    with pytest.raises(PermissionError):
        relay.submit(request(keys, 'bob', 'ack', 'a1', message_id=first['message_id'], lease_token=first['lease_token']), now_unix=105)
    assert relay.submit(request(keys, 'bob', 'ack', 'a2', message_id=second['message_id'], lease_token=second['lease_token']), now_unix=105)['acknowledged']


def test_relay_recipient_cannot_ack_others_or_cancel_sender_work(world):
    database, keys, _ = world
    relay = Relay(database)
    sent = relay.submit(envelope(keys, 'alice', send_body(), 's', relay=True), now_unix=100)
    message = relay.submit(request(keys, 'bob', 'poll', 'p', limit=1), now_unix=100)['messages'][0]
    with pytest.raises(PermissionError):
        relay.submit(request(keys, 'mallory', 'ack', 'a', message_id=sent['message_id'], lease_token=message['lease_token']), now_unix=100)
    with pytest.raises(PermissionError):
        relay.submit(request(keys, 'bob', 'cancel', 'c', message_id=sent['message_id']), now_unix=100)
    assert relay.submit(request(keys, 'alice', 'cancel', 'c', message_id=sent['message_id']), now_unix=100)['cancelled']
    assert not relay.submit(request(keys, 'alice', 'cancel', 'c2', message_id=sent['message_id']), now_unix=100)['cancelled']


def test_relay_refuses_wrong_audience_tamper_expiry_and_revocation(world):
    database, keys, _ = world
    relay = Relay(database)
    with pytest.raises(PermissionError):
        relay.submit(envelope(keys, 'alice', send_body(), 'wrong-audience'), now_unix=100)
    forged = envelope(keys, 'alice', send_body(), 'tamper', relay=True)
    forged['payload']['body'] = {'poisoned': True}
    with pytest.raises(PermissionError):
        relay.submit(forged, now_unix=100)
    expired = envelope(keys, 'alice', send_body(), 'expired', relay=True, now=0, expires=100)
    with pytest.raises(PermissionError):
        relay.submit(expired, now_unix=100)
    database.revoke_key('alice', public_key_hex(keys['alice']), now_unix=100)
    with pytest.raises(PermissionError):
        relay.submit(envelope(keys, 'alice', send_body(), 'revoked', relay=True), now_unix=100)
    assert relay.status(now_unix=100)['pending_messages'] == 0


def test_relay_requires_sender_and_recipient_opt_in(world):
    database, keys, registry = world
    relay = Relay(database)
    registry.submit(envelope(keys, 'bob', {'schema_version': 1, 'operation': 'withdraw'}, 'withdraw-bob'), now_unix=100)
    with pytest.raises(PermissionError, match='Recipient'):
        relay.submit(envelope(keys, 'alice', send_body(), 's', relay=True), now_unix=100)
    with pytest.raises(PermissionError, match='opt-in'):
        relay.submit(request(keys, 'bob', 'poll', 'p', limit=1), now_unix=100)


def test_relay_quota_and_nonce_rollback_are_atomic(world):
    database, keys, _ = world
    limits = replace(RelayLimits(), messages_per_window=1)
    relay = Relay(database, limits=limits)
    relay.submit(envelope(keys, 'alice', send_body(), 's1', relay=True), now_unix=100)
    second = envelope(keys, 'alice', send_body(), 's2', relay=True)
    with pytest.raises(PermissionError, match='rate'):
        Relay(RegistryDB(database.path), limits=limits).submit(second, now_unix=100)
    # New fixed window permits retry of the rolled-back nonce.
    assert relay.submit(second, now_unix=120)['message_id']


def test_relay_global_queue_and_per_peer_bounds(world):
    database, keys, _ = world
    limits = replace(RelayLimits(), max_messages=2, max_peer_messages=1)
    relay = Relay(database, limits=limits)
    relay.submit(envelope(keys, 'alice', send_body(), 'a1', relay=True), now_unix=100)
    with pytest.raises(ValueError, match='per-peer'):
        relay.submit(envelope(keys, 'alice', send_body(), 'a2', relay=True), now_unix=100)
    relay.submit(envelope(keys, 'mallory', send_body(), 'm1', relay=True), now_unix=100)
    with pytest.raises(ValueError, match='global'):
        relay.submit(envelope(keys, 'bob', send_body('alice'), 'b1', relay=True), now_unix=100)
    assert relay.status(now_unix=100)['pending_messages'] == 2


def test_relay_shutdown_drains_and_survives_restart(world):
    database, keys, _ = world
    relay = Relay(database)
    sent = relay.submit(envelope(keys, 'alice', send_body(), 's', relay=True), now_unix=100)
    assert relay.shutdown(now_unix=100)['state'] == 'draining'
    reopened = Relay(RegistryDB(database.path))
    with pytest.raises(PermissionError, match='shutting'):
        reopened.submit(envelope(keys, 'alice', send_body(), 's2', relay=True), now_unix=100)
    assert not reopened.finish_shutdown(now_unix=100)
    reopened.submit(request(keys, 'alice', 'cancel', 'cancel', message_id=sent['message_id']), now_unix=100)
    assert reopened.finish_shutdown(now_unix=100)
    with pytest.raises(PermissionError):
        reopened.submit(request(keys, 'bob', 'poll', 'p', limit=1), now_unix=100)
    reopened.resume(now_unix=100)
    assert reopened.submit(request(keys, 'bob', 'poll', 'p', limit=1), now_unix=100)['messages'] == []


def test_relay_immediate_shutdown_and_expiration(world):
    database, keys, _ = world
    relay = Relay(database)
    relay.submit(envelope(keys, 'alice', send_body(ttl=2), 's', relay=True), now_unix=100)
    assert not relay.submit(request(keys, 'bob', 'poll', 'p', limit=1), now_unix=102)['messages']
    relay.submit(envelope(keys, 'alice', send_body(), 's2', relay=True), now_unix=102)
    assert relay.shutdown(now_unix=102, cancel_pending=True) == {'state': 'stopped', 'cancelled': 1}
    assert relay.status(now_unix=102)['pending_messages'] == 0
    assert any(event['event'] == 'relay_expired' for event in database.audit())


def test_relay_concurrent_instances_cannot_overrun_quota(world):
    database, keys, _ = world
    limits = replace(RelayLimits(), messages_per_window=1)
    relays = [Relay(RegistryDB(database.path), limits=limits) for _ in range(2)]
    def submit(index):
        try:
            relays[index].submit(envelope(keys, 'alice', send_body(), 'race' + str(index), relay=True), now_unix=100)
            return True
        except PermissionError:
            return False
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(submit, range(2)))
    assert sorted(results) == [False, True]
    assert relays[0].status(now_unix=100)['pending_messages'] == 1


def test_audit_exhaustion_rolls_back_registration_and_replay(tmp_path):
    pytest.importorskip('cryptography')
    database = RegistryDB(tmp_path / 'small.sqlite', max_audit=1)
    key = generate_signing_key()
    database.pin_key('alice', public_key_hex(key), now_unix=100)
    registry = Registry(database)
    message = envelope({'alice': key}, 'alice', registration(), 's')
    with pytest.raises(ValueError, match='Audit capacity'):
        registry.submit(message, now_unix=100)
    assert not registry.discover(now_unix=100)['peers']
    with database.transaction() as connection:
        assert connection.execute('SELECT count(*) FROM replays').fetchone()[0] == 0


def test_database_key_bound_rotation_is_atomic(tmp_path):
    pytest.importorskip('cryptography')
    database = RegistryDB(tmp_path / 'keys.sqlite', max_keys=1)
    old, new = generate_signing_key(), generate_signing_key()
    database.pin_key('alice', public_key_hex(old), now_unix=100)
    with pytest.raises(ValueError, match='capacity'):
        database.rotate_key('alice', public_key_hex(new), now_unix=100)
    with database.transaction() as connection:
        assert connection.execute('SELECT revoked FROM peer_keys').fetchone()[0] == 0


def test_poll_structural_budget_does_not_lease_messages_it_cannot_return(world):
    from nablamath.core.semantic_contracts import canonical_payload
    database, keys, _ = world
    relay = Relay(database)
    for index in range(2):
        relay.submit(envelope(keys, 'alice', send_body(body=[0] * 12000), 'large-' + str(index), relay=True), now_unix=100)
    first = relay.submit(request(keys, 'bob', 'poll', 'p1', limit=50), now_unix=100)
    assert len(first['messages']) == 1
    canonical_payload(first)
    second = relay.submit(request(keys, 'bob', 'poll', 'p2', limit=50), now_unix=100)
    assert len(second['messages']) == 1
    assert first['messages'][0]['message_id'] != second['messages'][0]['message_id']
    canonical_payload(second)


def test_admission_rejects_body_that_cannot_fit_response_depth(world):
    database, keys, _ = world
    relay = Relay(database)
    body = 0
    for _ in range(30):
        body = [body]
    signed = envelope(keys, 'alice', send_body(body=body), 'too-deep-response', relay=True)
    with pytest.raises(ValueError, match='structural budget'):
        relay.submit(signed, now_unix=100)
    assert relay.status(now_unix=100)['pending_messages'] == 0


def test_relay_reused_expired_envelope_nonce_cannot_collide_with_pending_message(world):
    database, keys, _ = world
    relay = Relay(database)
    first = relay.submit(envelope(keys, 'alice', send_body(ttl=300), 'reusable',
                                  relay=True, now=100, expires=110), now_unix=100)
    # The original signature is now unusable, but its queued message lives on.
    second = relay.submit(envelope(keys, 'alice', send_body(ttl=300), 'reusable',
                                   relay=True, now=110, expires=200), now_unix=110)
    assert first['message_id'] != second['message_id']
    messages = relay.submit(request(keys, 'bob', 'poll', 'poll-both', limit=2), now_unix=110)['messages']
    assert {message['message_id'] for message in messages} == {first['message_id'], second['message_id']}
    assert relay.status(now_unix=110)['pending_messages'] == 2


@pytest.mark.parametrize('query', ['limit=&limit=1', 'unknown=', 'capability=', 'limit='])
def test_registry_query_empty_values_cannot_hide_duplicate_or_unknown_fields(world, query):
    api = RegistryAPI(world[2], clock=lambda: 100)
    assert api.handle('GET', '/v1/peers?' + query)[0] == 400


@pytest.mark.parametrize('length', ['+2', '-0', '2_0', '0x2'])
def test_registry_http_rejects_nondecimal_content_length(world, length):
    import http.client
    api = RegistryAPI(world[2], clock=lambda: 100)
    with loopback_http(api) as address:
        from urllib.parse import urlsplit
        endpoint = urlsplit(address)
        connection = http.client.HTTPConnection(endpoint.hostname, endpoint.port, timeout=5)
        try:
            connection.request('POST', '/v1/registrations', body=b'{}', headers={'Content-Length': length})
            response = connection.getresponse()
            assert response.status == 400
            response.read()
        finally:
            connection.close()
