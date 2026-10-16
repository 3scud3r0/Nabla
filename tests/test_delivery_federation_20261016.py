"""Authenticated local federation experiments; no WAN or human-identity claims."""
import copy
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from nablamath.core.semantic_contracts import canonical_payload
from nablamath.core.semantic_ir import fingerprint
from nablamath.knowledge.identity import PeerKey, PeerTrust, generate_signing_key, public_key_hex
from nablamath.knowledge.distributed_provenance import ProvenanceLog, provenance_event
from nablamath.network.merkle_inventory import (
    MerkleInventory, EMPTY_ROOT, validate_manifest, verify_membership, verify_page,
)
from nablamath.network.signatures import sign_message
from nablamath.p2p.federation_transport import FederationClient, FederationTransportError
from services.federation.inventory import InventoryStore, verify_revocation_proof
from services.federation.checkpoints import TransferJournal
from services.federation.reconciliation import Reconciler
from services.federation.http import FederationService, FederationGateway, REQUEST_AUDIENCE
from services.registry.app import Registry, AUDIENCE as REGISTRY_AUDIENCE
from services.registry.api import loopback_http
from services.registry.db import RegistryDB
from services.relay.app import Relay
from services.relay.protocol import AUDIENCE as RELAY_AUDIENCE


def ids(count):
    return [hashlib.sha256(str(i).encode()).hexdigest() for i in range(count)]


@pytest.fixture
def setup(tmp_path):
    pytest.importorskip('cryptography')
    keys = {peer: generate_signing_key() for peer in ('source', 'receiver', 'author')}
    trust = PeerTrust([PeerKey(peer, public_key_hex(key)) for peer, key in keys.items()])
    database = RegistryDB(tmp_path / 'source-registry.db')
    registry = Registry(database)
    for peer, key in keys.items():
        database.pin_key(peer, public_key_hex(key), now_unix=10)
        registration = sign_message({'schema_version': 1, 'operation': 'register',
            'capabilities': ['dataset_exchange', 'relay'], 'ttl_seconds': 1000,
            'visible': True, 'consent': True}, key, peer_id=peer,
            audience=REGISTRY_AUDIENCE, nonce='registration-' + peer, issued_unix=10, expires_unix=100)
        registry.submit(registration, now_unix=10)
    source_log = ProvenanceLog(tmp_path / 'source-events.db', trust)
    events = []
    for i in range(7):
        event = provenance_event(keys['author'], operator='author', artifact=f'{i:064x}',
            action='publish', nonce='event-' + str(i), issued_unix=10, expires_unix=1000)
        source_log.ingest(event, now_unix=10)
        events.append(event)
    parent = fingerprint(events[0])
    revoke = provenance_event(keys['author'], operator='author', artifact=f'{0:064x}',
        action='revoke', previous=parent, nonce='revocation', issued_unix=10, expires_unix=1000)
    source_log.ingest(revoke, now_unix=10)
    events.append(revoke)
    store = InventoryStore(database)
    manifest = store.freeze(source_log, now_unix=10)
    destination = ProvenanceLog(tmp_path / 'destination.db', trust)
    reconciler = Reconciler(tmp_path / 'reconciler.db', destination)
    journal_db = RegistryDB(tmp_path / 'journal.db')
    journal = TransferJournal(journal_db)
    service = FederationService(store, keys['source'], peer_id='source')
    gateway = FederationGateway(service, registry, Relay(database), clock=lambda: 20)
    state = dict(keys=keys, trust=trust, database=database, registry=registry,
        source_log=source_log, events=events, store=store, manifest=manifest,
        destination=destination, reconciler=reconciler, journal=journal,
        journal_db=journal_db, service=service, gateway=gateway)
    yield state
    reconciler.close()
    destination.close()
    source_log.close()


def client(state, endpoint, *, remote='source', trust=None, clock=lambda: 20, **kwargs):
    return FederationClient(endpoint, state['keys']['receiver'], state['trust'] if trust is None else trust,
        peer_id='receiver', remote_peer=remote, clock=clock, **kwargs)


@pytest.mark.parametrize('count', [0, 1, 2, 3, 5, 8, 17, 101])
def test_merkle_every_leaf_and_page_tree_shape(count):
    tree = MerkleInventory(reversed(ids(count)))
    assert validate_manifest(tree.manifest) == tree.manifest
    assert tree.identifiers == tuple(sorted(ids(count)))
    if not count:
        assert tree.root == EMPTY_ROOT
        assert verify_page(tree.page()) == []
    for i, identifier in enumerate(tree.identifiers):
        assert verify_membership(tree.manifest, tree.proof(i)) == identifier
    received = []
    start = 0
    while True:
        page = tree.page(start, 7)
        received.extend(verify_page(page, manifest=tree.manifest, expected_start=start))
        if page['next_position'] is None:
            break
        start = page['next_position']
    assert received == list(tree.identifiers)


@pytest.mark.parametrize('mutation', ['root', 'count', 'snapshot', 'index', 'side', 'sibling', 'extra'])
def test_merkle_proof_mutations_rejected(mutation):
    tree = MerkleInventory(ids(7))
    manifest, proof = copy.deepcopy(tree.manifest), copy.deepcopy(tree.proof(2))
    if mutation == 'root':
        manifest['root'] = 'a' * 64
    elif mutation == 'count':
        manifest['count'] = 8
    elif mutation == 'snapshot':
        proof['snapshot_id'] = 'a' * 64
    elif mutation == 'index':
        proof['index'] = True
    elif mutation == 'side':
        proof['siblings'][0]['side'] = 'left' if proof['siblings'][0]['side'] == 'right' else 'right'
    elif mutation == 'sibling':
        proof['siblings'][0]['hash'] = 'b' * 64
    else:
        proof['siblings'].append({'side': 'left', 'hash': 'c' * 64})
    with pytest.raises(ValueError):
        verify_membership(manifest, proof)


def test_inventory_rejects_duplicates_and_unbounded_generators():
    with pytest.raises(ValueError, match='Duplicate'):
        MerkleInventory(['a' * 64, 'a' * 64])
    with pytest.raises(ValueError, match='budget'):
        MerkleInventory(f'{i:064x}' for i in range(10001))
    with pytest.raises(ValueError):
        MerkleInventory([{}])


@pytest.mark.parametrize('mutation', ['empty', 'reorder', 'next', 'start', 'extra'])
def test_page_cannot_skip_reorder_or_forge_end(mutation):
    tree = MerkleInventory(ids(7))
    page = tree.page(0, 3)
    if mutation == 'empty': page['proofs'] = []
    elif mutation == 'reorder': page['proofs'].reverse()
    elif mutation == 'next': page['next_position'] = None
    elif mutation == 'start': page['start'] = 1
    else: page['extra'] = 1
    with pytest.raises(ValueError):
        verify_page(page, expected_start=0)


def test_snapshot_immutable_after_later_event_and_restart(setup):
    state = setup
    original = state['manifest']
    event = provenance_event(state['keys']['author'], operator='author', artifact='f' * 64,
        action='publish', nonce='later', issued_unix=10, expires_unix=1000)
    state['source_log'].ingest(event, now_unix=11)
    new = state['store'].freeze(state['source_log'], now_unix=11)
    assert new['count'] == original['count'] + 1 and new['root'] != original['root']
    reopened = InventoryStore(RegistryDB(state['database'].path))
    assert reopened.manifest(original['snapshot_id']) == original
    assert len(reopened.page(original['snapshot_id'], limit=100)['events']) == original['count']
    assert state['store'].freeze(state['source_log'], now_unix=11) == new


def test_snapshot_storage_cap_and_corruption_fail_closed(setup):
    state = setup
    bounded = InventoryStore(state['database'], max_snapshots=1)
    event = provenance_event(state['keys']['author'], operator='author', artifact='e' * 64,
        action='publish', nonce='excess', issued_unix=10, expires_unix=1000)
    state['source_log'].ingest(event, now_unix=11)
    with pytest.raises(ValueError, match='capacity'):
        bounded.freeze(state['source_log'], now_unix=11)
    with state['database'].transaction() as connection:
        connection.execute("UPDATE federation_snapshot_events SET envelope='{}' WHERE position=0")
    with pytest.raises(ValueError, match='corrupted'):
        state['store'].page(state['manifest']['snapshot_id'])


def test_revocation_proof_current_pins_and_historical_scope(setup):
    state = setup
    identifier = fingerprint(state['events'][-1])
    proof = state['store'].revocation_proof(state['manifest']['snapshot_id'], identifier)
    report = verify_revocation_proof(proof, state['trust'], expected_manifest=state['manifest'])
    assert report['valid'] and report['operator'] == 'author'
    assert not report['trusted_timestamp_established'] and not report['scientific_validity_established']
    state['trust'].revoke('author', public_key_hex(state['keys']['author']))
    with pytest.raises(ValueError, match='signature'):
        verify_revocation_proof(proof, state['trust'], expected_manifest=state['manifest'])


@pytest.mark.parametrize('mutation', ['truncate', 'signature', 'membership', 'terminal'])
def test_revocation_proof_chain_and_signature_mutations(setup, mutation):
    state = setup
    proof = state['store'].revocation_proof(state['manifest']['snapshot_id'], fingerprint(state['events'][-1]))
    if mutation == 'truncate': proof['chain'].pop(0)
    elif mutation == 'signature': proof['chain'][0]['event']['signature'] = '0' * 128
    elif mutation == 'membership': proof['chain'][-1]['membership']['index'] = (proof['chain'][-1]['membership']['index'] + 1) % proof['manifest']['count']
    else: proof['chain'][-1]['event']['payload']['action'] = 'endorse'
    with pytest.raises(ValueError):
        verify_revocation_proof(proof, state['trust'], expected_manifest=state['manifest'])


def test_checkpoint_exact_replay_restart_and_finish(setup):
    state = setup
    journal = state['journal']
    session = journal.begin('source', state['manifest'], now_unix=20)
    page = state['store'].page(state['manifest']['snapshot_id'], limit=2)
    receipt = journal.accept(session, page, state['reconciler'], authenticated_peer='source', now_unix=20)
    assert journal.accept(session, page, state['reconciler'], authenticated_peer='source', now_unix=21) == receipt
    reopened = TransferJournal(RegistryDB(state['journal_db'].path))
    assert reopened.status(session)['next_position'] == 2
    while reopened.status(session)['status'] != 'complete':
        start = reopened.status(session)['next_position']
        batch = state['store'].page(state['manifest']['snapshot_id'], start=start, limit=2)
        reopened.accept(session, batch, state['reconciler'], authenticated_peer='source', now_unix=21)
    assert len(state['destination'].export()) == state['manifest']['count']
    assert not reopened.status(session)['formal_proof']
    with pytest.raises(ValueError, match='Completed'):
        reopened.cancel(session, now_unix=21)


def test_checkpoint_crash_after_admission_before_ack_replays(setup):
    state = setup
    journal = state['journal']
    session = journal.begin('source', state['manifest'], now_unix=20)
    batch = state['store'].page(state['manifest']['snapshot_id'], limit=100)
    journal.validate_batch(batch)
    journal._prepare(session, batch, peer='source', now_unix=20)
    state['reconciler'].receive(batch['events'], now_unix=20)
    # Process crash leaves intent durable but its success acknowledgement absent.
    reopened = TransferJournal(RegistryDB(state['journal_db'].path))
    receipt = reopened.resume_prepared(session, state['reconciler'], now_unix=21)
    assert receipt['complete'] and reopened.status(session)['status'] == 'complete'
    assert len(state['destination'].export()) == len(state['events'])


def test_cancel_and_cross_peer_replay_do_not_advance(setup):
    state = setup
    journal = state['journal']
    session = journal.begin('source', state['manifest'], now_unix=20)
    batch = state['store'].page(state['manifest']['snapshot_id'])
    with pytest.raises(ValueError, match='peer'):
        journal.accept(session, batch, state['reconciler'], authenticated_peer='attacker', now_unix=20)
    assert state['destination'].export() == []
    journal.cancel(session, now_unix=20)
    with pytest.raises(ValueError, match='active'):
        journal.accept(session, batch, state['reconciler'], authenticated_peer='source', now_unix=20)
    assert journal.status(session)['next_position'] == 0


def test_transfer_event_mutation_fails_before_durable_intent(setup):
    state = setup
    journal = state['journal']
    session = journal.begin('source', state['manifest'], now_unix=20)
    batch = state['store'].page(state['manifest']['snapshot_id'])
    batch['events'][0]['signature'] = '0' * 128
    with pytest.raises(ValueError, match='binding'):
        journal.accept(session, batch, state['reconciler'], authenticated_peer='source', now_unix=20)
    assert journal.status(session)['next_position'] == 0
    assert state['reconciler'].report()['events'] == []


def test_checkpoint_durable_resource_budgets(setup):
    state = setup
    bounded = TransferJournal(state['journal_db'], max_sessions=1, max_total_bytes=1)
    session = bounded.begin('source', state['manifest'], now_unix=20)
    with pytest.raises(ValueError, match='session capacity'):
        bounded.begin('source', state['manifest'], now_unix=20)
    batch = state['store'].page(state['manifest']['snapshot_id'])
    with pytest.raises(ValueError, match='page capacity'):
        bounded.accept(session, batch, state['reconciler'], authenticated_peer='source', now_unix=20)
    assert state['destination'].export() == []


def test_actual_http_loopback_snapshot_sync_pause_resume_and_revocation(setup):
    state = setup
    with loopback_http(state['gateway']) as endpoint:
        connection = client(state, endpoint)
        paused = connection.sync_snapshot(state['manifest']['snapshot_id'], state['journal'], state['reconciler'],
                                          page_size=2, max_pages=1)
        assert paused['status'] == 'active' and paused['next_position'] == 2
        # New client instance and journal object reproduce a process restart boundary.
        connection = client(state, endpoint)
        resumed = connection.sync_snapshot(state['manifest']['snapshot_id'],
            TransferJournal(RegistryDB(state['journal_db'].path)), state['reconciler'],
            session_id=paused['session_id'], page_size=2)
        assert resumed['status'] == 'complete'
        assert len(state['destination'].export()) == len(state['events'])
        proof = connection.revocation(state['manifest']['snapshot_id'], fingerprint(state['events'][-1]))
        assert verify_revocation_proof(proof, state['trust'], expected_manifest=state['manifest'])['valid']
        assert connection.metrics()['requests'] > 0


def test_http_source_or_receiver_withdrawal_blocks_even_known_snapshot(setup):
    state = setup
    with loopback_http(state['gateway']) as endpoint:
        connection = client(state, endpoint)
        assert connection.manifest(state['manifest']['snapshot_id']) == state['manifest']
        withdrawal = sign_message({'schema_version': 1, 'operation': 'withdraw'}, state['keys']['source'],
            peer_id='source', audience=REGISTRY_AUDIENCE, nonce='withdraw', issued_unix=20, expires_unix=50)
        state['registry'].submit(withdrawal, now_unix=20)
        with pytest.raises(FederationTransportError, match='403'):
            connection.manifest(state['manifest']['snapshot_id'])


def test_http_revoked_request_key_and_wrong_response_peer_fail_closed(setup):
    state = setup
    with loopback_http(state['gateway']) as endpoint:
        connection = client(state, endpoint, remote='author')
        with pytest.raises(FederationTransportError, match='signature'):
            connection.manifest(state['manifest']['snapshot_id'])
        state['database'].revoke_key('receiver', public_key_hex(state['keys']['receiver']), now_unix=20)
        with pytest.raises(FederationTransportError):
            client(state, endpoint).manifest(state['manifest']['snapshot_id'])


def test_http_response_size_budget_is_enforced(setup):
    state = setup
    with loopback_http(state['gateway']) as endpoint:
        with pytest.raises(FederationTransportError, match='budget'):
            client(state, endpoint, max_response_bytes=100).manifest(state['manifest']['snapshot_id'])


def test_signed_response_cannot_be_replayed_for_different_request(setup):
    state = setup
    with loopback_http(state['gateway']) as endpoint:
        connection = client(state, endpoint)
        original = connection._exchange
        captured = []
        def capture(request):
            response = original(request)
            captured.append(response)
            return response
        connection._exchange = capture
        connection.manifest(state['manifest']['snapshot_id'])
        # Fresh verifier to ensure request binding also defeats replay after restart.
        replay = client(state, endpoint)
        replay._exchange = lambda request: captured[0]
        with pytest.raises(FederationTransportError, match='contract'):
            replay.manifest(state['manifest']['snapshot_id'])


@pytest.mark.parametrize('endpoint', ['http://example.org', 'https://user:pass@example.org',
                                      'https://example.org/path', 'http://127.0.0.1/?query=1'])
def test_client_refuses_unsafe_origins(setup, endpoint):
    with pytest.raises(ValueError):
        client(setup, endpoint)


def test_access_session_sequenced_reads_retries_and_durable_cancellation(setup):
    state = setup
    with loopback_http(state['gateway']) as endpoint:
        connection = client(state, endpoint)
        grant = connection.open_session(state['manifest']['snapshot_id'], max_pages=10)
        first = connection.session_page(grant['session_id'], grant['snapshot_id'], sequence=0, start=0, limit=2)
        cached = connection.session_page(grant['session_id'], grant['snapshot_id'], sequence=0, start=0, limit=2)
        assert cached == first
        status = connection.session_status(grant['session_id'])
        assert status['next_sequence'] == 1 and status['next_position'] == 2
        assert status['used_response_bytes'] > 0
        # Cached retries do not double-charge the session response-byte budget.
        again = connection.session_status(grant['session_id'])
        assert again['used_response_bytes'] == status['used_response_bytes']
        with pytest.raises(FederationTransportError, match='400'):
            connection.session_page(grant['session_id'], grant['snapshot_id'], sequence=0, start=0, limit=3)
        cancelled = connection.cancel_session(grant['session_id'])
        assert cancelled['state'] == 'cancelled'
        with pytest.raises(FederationTransportError, match='403'):
            connection.session_page(grant['session_id'], grant['snapshot_id'], sequence=1, start=2, limit=2)
        # A service restart retains cancellation and its original accounting.
        restarted = FederationService(state['store'], state['keys']['source'], peer_id='source')
        with state['database'].transaction() as db:
            report = restarted.access.status(db, 'receiver', grant['session_id'], now_unix=20)
        assert report['state'] == 'cancelled' and report['next_sequence'] == 1


def test_access_session_expiry_and_live_key_revocation(setup):
    state = setup
    clock = [20]
    state['gateway'].clock = lambda: clock[0]
    with loopback_http(state['gateway']) as endpoint:
        connection = client(state, endpoint, clock=lambda: clock[0])
        grant = connection.open_session(state['manifest']['snapshot_id'], ttl_seconds=1)
        clock[0] = 21
        assert connection.session_status(grant['session_id'])['state'] == 'expired'
        with pytest.raises(FederationTransportError, match='403'):
            connection.session_page(grant['session_id'], grant['snapshot_id'], sequence=0)
        fresh = connection.open_session(state['manifest']['snapshot_id'])
        state['database'].revoke_key('receiver', public_key_hex(state['keys']['receiver']), now_unix=21)
        with pytest.raises(FederationTransportError):
            connection.session_page(fresh['session_id'], fresh['snapshot_id'], sequence=0)


def test_access_session_cannot_cross_peer_snapshot_or_sequence(setup):
    state = setup
    with loopback_http(state['gateway']) as endpoint:
        connection = client(state, endpoint)
        grant = connection.open_session(state['manifest']['snapshot_id'])
        attacker = FederationClient(endpoint, state['keys']['author'], state['trust'],
            peer_id='author', remote_peer='source', clock=lambda: 20)
        with pytest.raises(FederationTransportError, match='403'):
            attacker.session_status(grant['session_id'])
        with pytest.raises(FederationTransportError, match='403'):
            attacker.cancel_session(grant['session_id'])
        with pytest.raises(FederationTransportError, match='400'):
            connection.session_page(grant['session_id'], 'a' * 64, sequence=0)
        with pytest.raises(FederationTransportError, match='400'):
            connection.session_page(grant['session_id'], grant['snapshot_id'], sequence=2)
        assert connection.session_status(grant['session_id'])['next_sequence'] == 0


def test_access_response_budget_failure_does_not_commit_sequence(setup):
    state = setup
    with loopback_http(state['gateway']) as endpoint:
        connection = client(state, endpoint)
        grant = connection.open_session(state['manifest']['snapshot_id'], max_response_bytes=1)
        with pytest.raises(FederationTransportError, match='400'):
            connection.session_page(grant['session_id'], grant['snapshot_id'], sequence=0)
        status = connection.session_status(grant['session_id'])
        assert status['used_response_bytes'] == status['next_sequence'] == 0


def test_access_page_budget_and_durable_capacity(setup):
    from services.federation.access_sessions import InventoryAccess
    state = setup
    with loopback_http(state['gateway']) as endpoint:
        connection = client(state, endpoint)
        grant = connection.open_session(state['manifest']['snapshot_id'], max_pages=1)
        connection.session_page(grant['session_id'], grant['snapshot_id'], sequence=0, limit=1)
        with pytest.raises(FederationTransportError, match='400'):
            connection.session_page(grant['session_id'], grant['snapshot_id'], sequence=1, start=1, limit=1)
        state['service'].access = InventoryAccess(state['database'], max_sessions=1)
        with pytest.raises(FederationTransportError, match='400'):
            connection.open_session(state['manifest']['snapshot_id'])


def test_access_sync_pause_restart_and_resume_actual_http(setup):
    state = setup
    with loopback_http(state['gateway']) as endpoint:
        connection = client(state, endpoint)
        grant = connection.open_session(state['manifest']['snapshot_id'])
        paused = connection.sync_session(grant['session_id'], state['journal'], state['reconciler'],
                                         page_size=2, max_pages=1)
        assert paused['next_position'] == 2 and paused['status'] == 'active'
        restarted = client(state, endpoint)
        finished = restarted.sync_session(grant['session_id'], TransferJournal(RegistryDB(state['journal_db'].path)),
            state['reconciler'], transfer_id=paused['session_id'], page_size=3)
        assert finished['status'] == 'complete'
        assert len(state['destination'].export()) == state['manifest']['count']


def test_access_sync_lost_remote_reply_reuses_original_operation_size(setup):
    state = setup
    with loopback_http(state['gateway']) as endpoint:
        connection = client(state, endpoint)
        grant = connection.open_session(state['manifest']['snapshot_id'])
        transfer = state['journal'].begin('source', state['manifest'], now_unix=20)
        state['journal'].bind_access(transfer, grant['session_id'])
        outgoing = state['journal'].prepare_access_request(transfer, grant['session_id'], page_size=2)
        connection.session_page(**outgoing)  # Remote committed; local reply lost.
        assert state['journal'].status(transfer)['next_position'] == 0
        assert connection.session_status(grant['session_id'])['next_sequence'] == 1
        resumed = client(state, endpoint).sync_session(grant['session_id'], state['journal'],
            state['reconciler'], transfer_id=transfer, page_size=5)
        assert resumed['status'] == 'complete'
        with state['journal_db'].transaction() as db:
            first = db.execute('SELECT payload FROM federation_transfer_requests WHERE session=? AND sequence=0',
                               (transfer,)).fetchone()
        assert json.loads(first['payload'])['limit'] == 2


def test_local_transfer_cannot_switch_remote_grants(setup):
    state = setup
    journal = state['journal']
    transfer = journal.begin('source', state['manifest'], now_unix=20)
    journal.bind_access(transfer, 'a' * 32)
    journal.bind_access(transfer, 'a' * 32)
    with pytest.raises(ValueError, match='switch'):
        journal.bind_access(transfer, 'b' * 32)
    with pytest.raises(ValueError, match='bound'):
        journal.prepare_access_request(transfer, 'b' * 32, page_size=2)
    assert journal.prepare_access_request(transfer, 'a' * 32, page_size=2)['limit'] == 2
    assert journal.prepare_access_request(transfer, 'a' * 32, page_size=100)['limit'] == 2


def test_gateway_uses_real_existing_registry_and_relay_transport(setup):
    from urllib.request import Request, urlopen
    state = setup
    with loopback_http(state['gateway']) as endpoint:
        def post(path, payload, key, peer, audience, nonce):
            envelope = sign_message(payload, key, peer_id=peer, audience=audience,
                nonce=nonce, issued_unix=20, expires_unix=80)
            with urlopen(Request(endpoint + path, data=canonical_payload(envelope).encode(),
                                 headers={'Content-Type': 'application/json'}), timeout=3) as response:
                return json.load(response)
        sent = post('/v1/relay', {'schema_version': 1, 'operation': 'send', 'recipient': 'receiver',
            'body': {'snapshot_id': state['manifest']['snapshot_id']}, 'ttl_seconds': 100},
            state['keys']['source'], 'source', RELAY_AUDIENCE, 'relay-send')
        polled = post('/v1/relay', {'schema_version': 1, 'operation': 'poll', 'limit': 1},
            state['keys']['receiver'], 'receiver', RELAY_AUDIENCE, 'relay-poll')
        assert polled['messages'][0]['message_id'] == sent['message_id']
        assert polled['messages'][0]['body']['snapshot_id'] == state['manifest']['snapshot_id']
        message = polled['messages'][0]
        acknowledgement = post('/v1/relay', {'schema_version': 1, 'operation': 'ack',
            'message_id': message['message_id'], 'lease_token': message['lease_token']},
            state['keys']['receiver'], 'receiver', RELAY_AUDIENCE, 'relay-ack')
        assert acknowledgement['acknowledged']
        with urlopen(endpoint + '/v1/peers?capability=dataset_exchange&limit=10', timeout=3) as response:
            discovery = json.load(response)
        assert {peer['peer_id'] for peer in discovery['peers']} == {'source', 'receiver', 'author'}


def watch_evidence(state, connection, manifest=None):
    manifest = state['manifest'] if manifest is None else manifest
    manifest_exchange = connection.request_evidence({'schema_version': 1, 'operation': 'manifest',
                                                    'snapshot_id': manifest['snapshot_id']})
    revocation_exchange = connection.request_evidence({'schema_version': 1, 'operation': 'revocation',
        'snapshot_id': manifest['snapshot_id'], 'event_id': fingerprint(state['events'][-1]), 'max_chain': 100})
    return manifest_exchange, revocation_exchange


def test_revocation_monitor_real_signed_exchanges_restart_and_external_head(setup, tmp_path):
    from nablamath.knowledge.revocation_monitor import RevocationMonitor
    state = setup
    path = tmp_path / 'watch.db'
    with loopback_http(state['gateway']) as endpoint:
        exchanges = watch_evidence(state, client(state, endpoint))
        monitor = RevocationMonitor(path, state['trust'], client_peer='receiver')
        receipt = monitor.observe(*exchanges, source_peer='source', now_unix=20)
        assert receipt == monitor.observe(*exchanges, source_peer='source', now_unix=20)
        report = monitor.audit()
        assert report['valid'] and report['observations'] == 1
        assert report['head'] == fingerprint(receipt)
        restarted = RevocationMonitor(path, state['trust'], client_peer='receiver')
        assert restarted.status(f'{0:064x}')['revoked']
        assert not restarted.status('e' * 64)['revoked']
        assert restarted.audit(expected_head=report['head'])['valid']
        with pytest.raises(ValueError, match='external head'):
            restarted.audit(expected_head='a' * 64)


@pytest.mark.parametrize('mutation', ['response_signature', 'request_signature', 'request_binding', 'source_peer', 'operation'])
def test_watch_rejects_unbound_or_unauthenticated_evidence(setup, tmp_path, mutation):
    from nablamath.knowledge.revocation_monitor import RevocationMonitor
    state = setup
    with loopback_http(state['gateway']) as endpoint:
        exchanges = list(watch_evidence(state, client(state, endpoint)))
    if mutation == 'response_signature':
        exchanges[0]['response']['signature'] = '0' * 128
    elif mutation == 'request_signature':
        exchanges[0]['request']['signature'] = '0' * 128
    elif mutation == 'request_binding':
        exchanges[0]['request'], exchanges[1]['request'] = exchanges[1]['request'], exchanges[0]['request']
    elif mutation == 'operation':
        exchanges[0]['response']['payload']['operation'] = 'page'
    monitor = RevocationMonitor(tmp_path / 'watch.db', state['trust'], client_peer='receiver')
    with pytest.raises(ValueError):
        monitor.observe(*exchanges, source_peer='author' if mutation == 'source_peer' else 'source', now_unix=20)
    assert not monitor.status(f'{0:064x}')['revoked']
    assert monitor.audit()['observations'] == 0


def test_watch_source_rollback_and_same_size_equivocation_rejected(setup, tmp_path):
    from nablamath.knowledge.revocation_monitor import RevocationMonitor
    state = setup
    monitor = RevocationMonitor(tmp_path / 'watch.db', state['trust'], client_peer='receiver')
    with loopback_http(state['gateway']) as endpoint:
        connection = client(state, endpoint)
        monitor.observe(*watch_evidence(state, connection), source_peer='source', now_unix=20)
        subset = ProvenanceLog(tmp_path / 'subset.db', state['trust'])
        subset.ingest(state['events'][0], now_unix=10)
        subset.ingest(state['events'][-1], now_unix=10)
        smaller = state['store'].freeze(subset, now_unix=20)
        with pytest.raises(ValueError, match='rollback'):
            monitor.observe(*watch_evidence(state, connection, smaller), source_peer='source', now_unix=20)
        subset.close()
        fork = ProvenanceLog(tmp_path / 'fork.db', state['trust'])
        for event in state['events']:
            if event is not state['events'][1]:
                fork.ingest(event, now_unix=10)
        replacement = provenance_event(state['keys']['author'], operator='author', artifact='f' * 64,
            action='publish', nonce='fork-replacement', issued_unix=10, expires_unix=1000)
        fork.ingest(replacement, now_unix=10)
        different = state['store'].freeze(fork, now_unix=20)
        assert different['count'] == state['manifest']['count'] and different['root'] != state['manifest']['root']
        with pytest.raises(ValueError, match='equivocated'):
            monitor.observe(*watch_evidence(state, connection, different), source_peer='source', now_unix=20)
        fork.close()
    assert monitor.audit()['observations'] == 1 and monitor.status(f'{0:064x}')['revoked']


def test_watch_storage_limits_and_author_revocation_do_not_restore_artifact(setup, tmp_path):
    from nablamath.knowledge.revocation_monitor import RevocationMonitor
    state = setup
    monitor = RevocationMonitor(tmp_path / 'watch.db', state['trust'], client_peer='receiver', max_observations=1)
    with loopback_http(state['gateway']) as endpoint:
        connection = client(state, endpoint)
        monitor.observe(*watch_evidence(state, connection), source_peer='source', now_unix=20)
        with pytest.raises(ValueError, match='capacity'):
            monitor.observe(*watch_evidence(state, connection), source_peer='source', now_unix=20)
    state['trust'].revoke('author', public_key_hex(state['keys']['author']))
    report = monitor.status(f'{0:064x}')
    assert report['revoked'] and not report['observations'][0]['author_key_currently_trusted']
    with pytest.raises(ValueError, match='signature'):
        monitor.audit()


def test_watch_audit_detects_local_receipt_and_semantic_index_corruption(setup, tmp_path):
    from nablamath.knowledge.revocation_monitor import RevocationMonitor
    state = setup
    path = tmp_path / 'watch.db'
    monitor = RevocationMonitor(path, state['trust'], client_peer='receiver')
    with loopback_http(state['gateway']) as endpoint:
        monitor.observe(*watch_evidence(state, client(state, endpoint)), source_peer='source', now_unix=20)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE watch_observations SET artifact=?", ('f' * 64,))
    with pytest.raises(ValueError, match='semantic'):
        monitor.audit()


def test_watch_expired_evidence_cannot_be_newly_recorded(setup, tmp_path):
    from nablamath.knowledge.revocation_monitor import RevocationMonitor
    state = setup
    with loopback_http(state['gateway']) as endpoint:
        exchanges = watch_evidence(state, client(state, endpoint))
    monitor = RevocationMonitor(tmp_path / 'watch.db', state['trust'], client_peer='receiver')
    with pytest.raises(ValueError, match='freshness'):
        monitor.observe(*exchanges, source_peer='source', now_unix=100)
    assert monitor.audit()['observations'] == 0


def test_maximum_merkle_profile_proofs_use_bounded_cached_subtrees():
    tree = MerkleInventory(f'{i:064x}' for i in range(10000))
    assert len(tree._subtrees) == 19999
    before = len(tree._subtrees)
    for index in (0, 1, 4999, 5000, 9998, 9999):
        proof = tree.proof(index)
        assert len(proof['siblings']) <= 14
        assert verify_membership(tree.manifest, proof) == f'{index:064x}'
    assert len(tree._subtrees) == before


def test_snapshot_cached_subtree_corruption_and_full_audit(setup):
    state = setup
    snapshot = state['manifest']['snapshot_id']
    before = state['store'].audit_snapshot(snapshot)
    assert before['valid'] and before['subtrees'] == 2 * before['events'] - 1
    with state['database'].transaction() as connection:
        # Corrupt every proper subtree, guaranteeing any non-singleton proof reads it.
        connection.execute('UPDATE federation_snapshot_nodes SET hash=? WHERE stop-start<?',
                           ('f' * 64, state['manifest']['count']))
    with pytest.raises(ValueError, match='root mismatch'):
        state['store'].page(snapshot, start=0, limit=1)
    with pytest.raises(ValueError, match='cache corrupted'):
        state['store'].audit_snapshot(snapshot)


def test_bounded_page_read_does_not_touch_unselected_event_payloads(setup):
    state = setup
    snapshot = state['manifest']['snapshot_id']
    first = state['store'].page(snapshot, start=0, limit=1)
    assert len(first['events']) == 1
    with state['database'].transaction() as connection:
        connection.execute("UPDATE federation_snapshot_events SET envelope='{}' WHERE position=7")
    # The first page still verifies from its own event bytes and committed sibling
    # roots; serving one page does not falsely claim that every other page is sound.
    assert state['store'].page(snapshot, start=0, limit=1) == first
    with pytest.raises(ValueError, match='corrupted'):
        state['store'].page(snapshot, start=7, limit=1)
    with pytest.raises(ValueError, match='corrupted'):
        state['store'].audit_snapshot(snapshot)


def test_access_remote_service_restart_preserves_exact_retry_and_progress(setup):
    state = setup
    snapshot = state['manifest']['snapshot_id']
    with loopback_http(state['gateway']) as endpoint:
        connection = client(state, endpoint)
        grant = connection.open_session(snapshot)
        original = connection.session_page(grant['session_id'], snapshot, sequence=0, limit=2)
    # Completely new database/service objects serve a different TCP port. The
    # signed source identity and immutable data remain the same across restart.
    db = RegistryDB(state['database'].path)
    service = FederationService(InventoryStore(db), state['keys']['source'], peer_id='source')
    gateway = FederationGateway(service, Registry(db), Relay(db), clock=lambda: 20)
    with loopback_http(gateway) as endpoint:
        restarted = client(state, endpoint)
        assert restarted.session_status(grant['session_id'])['next_sequence'] == 1
        assert restarted.session_page(grant['session_id'], snapshot, sequence=0, limit=2) == original
        subsequent = restarted.session_page(grant['session_id'], snapshot, sequence=1, start=2, limit=2)
        assert subsequent['next_sequence'] == 2


def test_concurrent_same_access_sequence_commits_one_cache_and_one_charge(setup):
    from concurrent.futures import ThreadPoolExecutor
    state = setup
    snapshot = state['manifest']['snapshot_id']
    with loopback_http(state['gateway']) as endpoint:
        grant = client(state, endpoint).open_session(snapshot)
        def read(_):
            return client(state, endpoint).session_page(grant['session_id'], snapshot, sequence=0, limit=2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(read, range(2)))
        assert responses[0] == responses[1]
        status = client(state, endpoint).session_status(grant['session_id'])
        assert status['next_sequence'] == 1
        with state['database'].transaction() as connection:
            rows = connection.execute('SELECT response_bytes FROM federation_access_responses WHERE session=?',
                                      (grant['session_id'],)).fetchall()
        assert len(rows) == 1 and rows[0]['response_bytes'] == status['used_response_bytes']


def test_cryptographic_domains_prevent_cross_service_request_reuse(setup):
    state = setup
    request = sign_message({'schema_version': 1, 'operation': 'manifest',
        'snapshot_id': state['manifest']['snapshot_id']}, state['keys']['receiver'],
        peer_id='receiver', audience=RELAY_AUDIENCE, nonce='cross-protocol', issued_unix=20, expires_unix=80)
    status, result = state['gateway'].handle('POST', '/v1/federation', canonical_payload(request).encode())
    assert status == 403 and result['error'] == 'not_authorized'
    assert 'snapshot_id' not in result


def test_actual_http_identical_request_nonce_rejected_after_success(setup):
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen
    state = setup
    request = sign_message({'schema_version': 1, 'operation': 'manifest',
        'snapshot_id': state['manifest']['snapshot_id']}, state['keys']['receiver'],
        peer_id='receiver', audience=REQUEST_AUDIENCE, nonce='request-replay', issued_unix=20, expires_unix=80)
    raw = canonical_payload(request).encode()
    with loopback_http(state['gateway']) as endpoint:
        with urlopen(Request(endpoint + '/v1/federation', data=raw), timeout=3) as response:
            assert response.status == 200
        with pytest.raises(HTTPError) as error:
            urlopen(Request(endpoint + '/v1/federation', data=raw), timeout=3)
        assert error.value.code == 403
        error.value.close()


@pytest.mark.parametrize('case', ['duplicate_length', 'oversized_length', 'redirect', 'wrong_content_type', 'truncated', 'compression'])
def test_http_transport_rejects_ambiguous_or_unsafe_response_framing(setup, case):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Thread
    state = setup
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(302 if case == 'redirect' else 200)
            self.send_header('Content-Type', 'text/plain' if case == 'wrong_content_type' else 'application/json')
            if case == 'redirect':
                self.send_header('Location', '/must-not-follow')
            if case == 'compression':
                self.send_header('Content-Encoding', 'gzip')
            if case == 'duplicate_length':
                self.send_header('Content-Length', '2')
            length = 1000001 if case == 'oversized_length' else 10 if case == 'truncated' else 2
            self.send_header('Content-Length', str(length))
            self.end_headers()
            self.wfile.write(b'{}')
        def log_message(self, *_):pass
    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = client(state, 'http://127.0.0.1:' + str(server.server_port))
        with pytest.raises(FederationTransportError):
            connection.manifest(state['manifest']['snapshot_id'])
    finally:
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()


def test_journal_independent_connections_cannot_double_charge_exact_page(setup, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    state = setup
    session = state['journal'].begin('source', state['manifest'], now_unix=20)
    batch = state['store'].page(state['manifest']['snapshot_id'], limit=100)
    def accept(_):
        log = ProvenanceLog(tmp_path / 'destination.db', state['trust'])
        reconciler = Reconciler(tmp_path / 'reconciler.db', log)
        journal = TransferJournal(RegistryDB(state['journal_db'].path))
        try:
            return journal.accept(session, batch, reconciler, authenticated_peer='source', now_unix=20)
        finally:
            reconciler.close()
            log.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(accept, range(2)))
    assert receipts[0] == receipts[1]
    assert state['journal'].status(session)['transferred_bytes'] == len(canonical_payload(batch).encode())


def test_revocation_monitor_rejects_rehashed_semantic_index_corruption(setup, tmp_path):
    from nablamath.knowledge.revocation_monitor import RevocationMonitor
    state = setup
    path = tmp_path / 'watch.db'
    monitor = RevocationMonitor(path, state['trust'], client_peer='receiver')
    with loopback_http(state['gateway']) as endpoint:
        monitor.observe(*watch_evidence(state, client(state, endpoint)), source_peer='source', now_unix=20)
    with sqlite3.connect(path) as connection:
        connection.execute('UPDATE watch_observations SET public_key=?', ('f' * 64,))
    with pytest.raises(ValueError, match='semantic'):
        monitor.audit()


def test_revocation_source_cache_is_derived_and_audited(setup, tmp_path):
    from nablamath.knowledge.revocation_monitor import RevocationMonitor
    state = setup
    path = tmp_path / 'watch.db'
    monitor = RevocationMonitor(path, state['trust'], client_peer='receiver')
    with loopback_http(state['gateway']) as endpoint:
        monitor.observe(*watch_evidence(state, client(state, endpoint)), source_peer='source', now_unix=20)
    with sqlite3.connect(path) as connection:
        connection.execute('UPDATE watch_sources SET count=count+1')
    with pytest.raises(ValueError, match='source cache'):
        monitor.audit()


def test_empty_snapshot_full_transfer_audit_and_authenticated_session(setup, tmp_path):
    state = setup
    empty_log = ProvenanceLog(tmp_path / 'empty.db', state['trust'])
    manifest = state['store'].freeze(empty_log, now_unix=20)
    assert manifest['count'] == 0 and manifest['root'] == EMPTY_ROOT
    assert state['store'].audit_snapshot(manifest['snapshot_id'])['events'] == 0
    with loopback_http(state['gateway']) as endpoint:
        connection = client(state, endpoint)
        grant = connection.open_session(manifest['snapshot_id'])
        finished = connection.sync_session(grant['session_id'], state['journal'], state['reconciler'])
        assert finished['status'] == 'complete' and finished['next_position'] == 0
        assert connection.session_status(grant['session_id'])['next_sequence'] == 1
    empty_log.close()


def test_session_read_fails_after_source_signing_key_revoked(setup):
    state = setup
    with loopback_http(state['gateway']) as endpoint:
        connection = client(state, endpoint)
        grant = connection.open_session(state['manifest']['snapshot_id'])
        state['database'].revoke_key('source', public_key_hex(state['keys']['source']), now_unix=20)
        with pytest.raises(FederationTransportError, match='403'):
            connection.session_page(grant['session_id'], grant['snapshot_id'], sequence=0)


def test_gateway_wrong_route_and_method_never_expose_local_administration(setup):
    state = setup
    for target in ('/v1/pin-key', '/v1/revoke-key', '/v1/freeze', '/v1/admin'):
        status, body = state['gateway'].handle('POST', target, b'{}')
        assert status == 404 and body['error'] == 'route_not_found'
    status, body = state['gateway'].handle('GET', '/v1/federation')
    assert status == 405
    for target in ('https://evil.invalid/v1/federation', '//evil.invalid/v1/federation',
                   '/v1/federation?operation=admin', '/v1/federation#admin'):
        status, body = state['gateway'].handle('POST', target, b'{}')
        assert status == 400 and body['error'] == 'invalid_request'


def test_client_clock_rollback_rejects_freshly_fetched_signed_response(setup):
    state = setup
    observed = [20]
    with loopback_http(state['gateway']) as endpoint:
        connection = client(state, endpoint, clock=lambda: observed[0])
        connection.manifest(state['manifest']['snapshot_id'])
        # This request would also be future-dated relative to its own client
        # clock; both the signature interval and verifier monotonic clock reject.
        observed[0] = 19
        with pytest.raises(FederationTransportError):
            connection.manifest(state['manifest']['snapshot_id'])


def test_pending_invalid_signature_prevents_claiming_complete_snapshot(setup, tmp_path):
    state = setup
    from nablamath.network.merkle_inventory import MerkleInventory
    bad = copy.deepcopy(state['events'][0])
    bad['signature'] = '0' * 128
    tree = MerkleInventory([fingerprint(bad)])
    batch = {'schema_version': 1, 'inventory_page': tree.page(), 'events': [bad]}
    session = state['journal'].begin('source', tree.manifest, now_unix=20)
    with pytest.raises(ValueError, match='quarantined'):
        state['journal'].accept(session, batch, state['reconciler'], authenticated_peer='source', now_unix=20)
    assert state['journal'].status(session)['status'] == 'failed'
    assert state['destination'].export() == []


def test_missing_external_parent_cannot_finish_even_with_valid_merkle_membership(setup):
    state = setup
    child = state['events'][-1]
    tree = MerkleInventory([fingerprint(child)])
    batch = {'schema_version': 1, 'inventory_page': tree.page(), 'events': [child]}
    session = state['journal'].begin('source', tree.manifest, now_unix=20)
    with pytest.raises(ValueError, match='unresolved'):
        state['journal'].accept(session, batch, state['reconciler'], authenticated_peer='source', now_unix=20)
    assert state['journal'].status(session)['status'] == 'failed'
    assert state['reconciler'].report()['events'][0]['state'] == 'pending'
