"""Signed consent-gated federation reads using the existing registry and relay.

The reusable HTTP adapter binds loopback only. Remote TLS termination, Internet
availability and multi-host validation require independent deployment evidence.
Administrative snapshot export and key pinning are never public API operations.
"""
from urllib.parse import urlsplit

from nablamath.core.semantic_contracts import canonical_payload, load_json, require_fields, require_digest
from nablamath.core.semantic_ir import fingerprint
from nablamath.network.signatures import sign_message
from services.registry.api import RegistryAPI
from services.registry.db import RegistryDB
from .inventory import InventoryStore
from .access_sessions import InventoryAccess

REQUEST_AUDIENCE = 'Nabla-federation-request-v1'
RESPONSE_PREFIX = 'Nabla-federation-response-v1:'
OPERATIONS = {
    'open_session': {'schema_version', 'operation', 'snapshot_id', 'ttl_seconds', 'max_pages', 'max_response_bytes'},
    'session_page': {'schema_version', 'operation', 'snapshot_id', 'session_id', 'sequence', 'start', 'limit'},
    'session_status': {'schema_version', 'operation', 'session_id'},
    'cancel_session': {'schema_version', 'operation', 'session_id'},
    'manifest': {'schema_version', 'operation', 'snapshot_id'},
    'page': {'schema_version', 'operation', 'snapshot_id', 'start', 'limit'},
    'revocation': {'schema_version', 'operation', 'snapshot_id', 'event_id', 'max_chain'},
}


class FederationService:
    """Transactional nonce/consent checks and signed immutable snapshot reads."""
    def __init__(self, store, private_key, *, peer_id):
        if not isinstance(store, InventoryStore) or type(peer_id) is not str or not peer_id.strip() or len(peer_id) > 200:
            raise ValueError('Explicit snapshot store and service identity required')
        self.store = store
        self.database = store.database
        self.private_key = private_key
        self.peer_id = peer_id
        from nablamath.knowledge.identity import public_key_hex
        self.public_key = public_key_hex(private_key)
        self.access = InventoryAccess(self.database)

    @staticmethod
    def _validate(payload):
        if type(payload) is not dict or type(payload.get('schema_version')) is not int or payload.get('schema_version') != 1:
            raise ValueError('Unsupported federation request version')
        operation = payload.get('operation')
        if type(operation) is not str or operation not in OPERATIONS:
            raise ValueError('Unsupported federation read operation')
        require_fields(payload, OPERATIONS[operation])
        if 'snapshot_id' in payload:
            require_digest(payload['snapshot_id'])
        if 'session_id' in payload:
            InventoryAccess._id(payload['session_id'])
        if operation == 'open_session':
            InventoryAccess.validate_open(payload)
        if operation in {'page', 'session_page'}:
            if type(payload['start']) is not int or not 0 <= payload['start'] <= 10000:
                raise ValueError('Invalid inventory start position')
            if type(payload['limit']) is not int or not 1 <= payload['limit'] <= 100:
                raise ValueError('Invalid inventory page limit')
        if operation == 'revocation':
            require_digest(payload['event_id'])
            if type(payload['max_chain']) is not int or not 1 <= payload['max_chain'] <= 100:
                raise ValueError('Invalid revocation proof limit')
        return operation

    def submit(self, envelope, *, now_unix):
        canonical_payload(envelope)
        with self.database.transaction() as connection:
            peer, payload = self.database.authenticate(connection, envelope,
                audience=REQUEST_AUDIENCE, now_unix=now_unix)
            operation = self._validate(payload)
            if not self.database.active_peer(connection, peer, now_unix=now_unix, capability='dataset_exchange'):
                raise PermissionError('Active dataset-exchange opt-in required')
            if not self.database.active_peer(connection, self.peer_id, now_unix=now_unix, capability='dataset_exchange'):
                raise PermissionError('Source operator withdrew dataset-exchange consent')
            # Check the local signing key against the same current trust state.
            row = connection.execute('SELECT revoked FROM peer_keys WHERE peer_id=? AND public_key=?',
                                     (self.peer_id, self.public_key)).fetchone()
            if row is None or row['revoked']:
                raise PermissionError('Source signing key is not currently pinned')
            snapshot_id = payload.get('snapshot_id')
            cached = None
            if operation == 'open_session':
                self.store._manifest_in_transaction(connection, snapshot_id)
                result = self.access.open(connection, peer, payload, now_unix=now_unix)
            elif operation in {'session_status', 'cancel_session'}:
                callback = self.access.status if operation == 'session_status' else self.access.cancel
                result = callback(connection, peer, payload['session_id'], now_unix=now_unix)
            elif operation == 'session_page':
                grant, cached = self.access.prepare_page(connection, peer, payload, now_unix=now_unix)
                if cached is not None:
                    result = cached
                else:
                    result = {'schema_version': 1, 'session_id': payload['session_id'],
                        'sequence': payload['sequence'], 'next_sequence': payload['sequence'] + 1,
                        'page': self.store.page_in_transaction(connection, snapshot_id,
                            start=payload['start'], limit=payload['limit'])}
            elif operation == 'manifest':
                result = self.store._manifest_in_transaction(connection, snapshot_id)
            elif operation == 'page':
                result = self.store.page_in_transaction(connection, snapshot_id,
                    start=payload['start'], limit=payload['limit'])
            else:
                result = self.store.revocation_in_transaction(connection, snapshot_id,
                    payload['event_id'], max_chain=payload['max_chain'])
            body = {'schema_version': 1, 'request_id': fingerprint(envelope),
                    'operation': operation, 'result': result,
                    'scope': 'signed immutable finite snapshot; no scientific or identity validation'}
            expires = min(envelope['expires_unix'], now_unix + 60)
            response = sign_message(body, self.private_key, peer_id=self.peer_id,
                audience=RESPONSE_PREFIX + fingerprint({'peer': peer}), nonce='response-' + fingerprint(envelope),
                issued_unix=now_unix, expires_unix=expires)
            # Response size validation happens before nonce/audit transaction commits.
            response_size = len(canonical_payload(response).encode())
            if operation == 'session_page' and cached is None:
                self.access.commit_page(connection, payload, result, response_bytes=response_size)
            self.database.append_audit(connection, 'federation_read', peer, now_unix,
                {'operation': operation, 'snapshot_id': snapshot_id, 'response_id': fingerprint(response)})
            return response


class FederationGateway:
    """Compose existing registration/discovery/relay with signed federation reads."""
    def __init__(self, federation, registry, relay, *, clock):
        if not isinstance(federation, FederationService) or not callable(clock):
            raise ValueError('Explicit federation service and server clock required')
        if registry.database is not federation.database or relay.database is not federation.database:
            raise ValueError('Gateway services must share one transactional trust database')
        self.federation, self.registry, self.relay = federation, registry, relay
        self.clock = clock
        self.registry_api = RegistryAPI(registry, clock=clock)

    def handle(self, method, target, raw=b''):
        if type(raw) is not bytes or len(raw) > 1000000:
            return 413, {'schema_version': 1, 'error': 'request_too_large'}
        if type(target) is not str or len(target) > 4096:
            return 400, {'schema_version': 1, 'error': 'invalid_target'}
        try:
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or parsed.fragment or parsed.query:
                if method == 'GET' and parsed.path == '/v1/peers' and not parsed.scheme and not parsed.netloc and not parsed.fragment:
                    return self.registry_api.handle(method, target, raw)
                raise ValueError('Invalid gateway request target')
            if parsed.path in {'/v1/registrations', '/v1/peers'}:
                return self.registry_api.handle(method, target, raw)
            if method != 'POST':
                return 405, {'schema_version': 1, 'error': 'method_not_allowed'}
            envelope = load_json(raw.decode('utf-8'))
            if parsed.path == '/v1/federation':
                return 200, self.federation.submit(envelope, now_unix=self.clock())
            if parsed.path == '/v1/relay':
                return 200, self.relay.submit(envelope, now_unix=self.clock())
            return 404, {'schema_version': 1, 'error': 'route_not_found'}
        except PermissionError:
            return 403, {'schema_version': 1, 'error': 'not_authorized'}
        except KeyError:
            return 404, {'schema_version': 1, 'error': 'object_not_found'}
        except (ValueError, TypeError, UnicodeError):
            return 400, {'schema_version': 1, 'error': 'invalid_request'}
