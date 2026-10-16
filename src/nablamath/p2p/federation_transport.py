"""Authenticated immutable-snapshot HTTP client with bounded resumable transfer.

HTTPS uses the platform certificate verifier. Plain HTTP is accepted only for
explicit loopback origins. Responses require pinned Ed25519 keys, freshness and
exact request binding independently of transport TLS. No listener starts here.
"""
import ipaddress
import math
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from ..core.semantic_contracts import canonical_payload, load_json, require_fields, require_digest
from ..core.semantic_ir import fingerprint
from ..network.signatures import MessageVerifier, sign_message
from ..network.merkle_inventory import validate_manifest
from .transport import _NoRedirect

REQUEST_AUDIENCE = 'Nabla-federation-request-v1'
RESPONSE_PREFIX = 'Nabla-federation-response-v1:'


class FederationTransportError(RuntimeError):
    """Redacted transport/protocol failure; signed payloads never appear in text."""


class FederationClient:
    def __init__(self, endpoint, private_key, trust, *, peer_id, remote_peer, clock,
                 timeout=5, max_response_bytes=1000000):
        if type(endpoint) is not str:
            raise ValueError('Explicit HTTP origin required')
        parsed = urlsplit(endpoint)
        try:
            loopback = parsed.hostname == 'localhost' or ipaddress.ip_address(parsed.hostname).is_loopback
        except (ValueError, TypeError):
            loopback = False
        if (parsed.scheme not in {'https', 'http'} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {'', '/'} or (parsed.scheme == 'http' and not loopback)):
            raise ValueError('Verified HTTPS or explicit loopback HTTP origin required')
        parsed.port
        for value in (peer_id, remote_peer):
            if type(value) is not str or not value.strip() or len(value) > 200:
                raise ValueError('Explicit bounded local and remote peer identities required')
        if not callable(clock):
            raise ValueError('Explicit client clock required')
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise ValueError('Invalid HTTP timeout')
        if type(max_response_bytes) is not int or not 1 <= max_response_bytes <= 1000000:
            raise ValueError('Invalid response byte budget')
        self.endpoint = endpoint.rstrip('/')
        self.private_key = private_key
        self.peer_id = peer_id
        self.remote_peer = remote_peer
        self.clock = clock
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self._opener = build_opener(_NoRedirect())
        self._verifier = MessageVerifier(trust, RESPONSE_PREFIX + fingerprint({'peer': peer_id}))
        self.requests = 0
        self.response_bytes = 0

    def _now(self):
        now = self.clock()
        if type(now) is not int or now < 0:
            raise ValueError('Clock must return nonnegative integer seconds')
        return now

    def _exchange(self, request):
        raw = canonical_payload(request).encode()
        http_request = Request(self.endpoint + '/v1/federation', data=raw,
            method='POST', headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
        try:
            with self._opener.open(http_request, timeout=self.timeout) as response:
                if response.status != 200 or response.headers.get_content_type() != 'application/json':
                    raise FederationTransportError('Unexpected federation HTTP response')
                encodings = response.headers.get_all('Content-Encoding', [])
                if encodings and encodings != ['identity']:
                    raise FederationTransportError('Compressed federation responses unsupported')
                lengths = response.headers.get_all('Content-Length', [])
                if len(lengths) != 1 or not lengths[0] or any(c not in '0123456789' for c in lengths[0]):
                    raise FederationTransportError('Ambiguous federation response framing')
                if int(lengths[0]) > self.max_response_bytes:
                    raise FederationTransportError('Federation response exceeds byte budget')
                raw_response = response.read(self.max_response_bytes + 1)
                if len(raw_response) > self.max_response_bytes or len(raw_response) != int(lengths[0]):
                    raise FederationTransportError('Truncated or oversized federation response')
            decoded = load_json(raw_response.decode('utf-8'))
            self.requests += 1
            self.response_bytes += len(raw_response)
            return decoded
        except HTTPError as exc:
            status = exc.code
            exc.close()
            raise FederationTransportError('Federation HTTP status ' + str(status)) from None
        except (URLError, OSError, UnicodeError, ValueError):
            raise FederationTransportError('Invalid federation transport response') from None

    def request(self, payload):
        return self.request_evidence(payload)['response']['payload']['result']

    def request_evidence(self, payload):
        """Return both signed envelopes for independently replayable live evidence."""
        now = self._now()
        request = sign_message(payload, self.private_key, peer_id=self.peer_id,
            audience=REQUEST_AUDIENCE, nonce=uuid.uuid4().hex,
            issued_unix=now, expires_unix=now + 60)
        response = self._exchange(request)
        result = self._verifier.verify(response, now_unix=self._now())
        if not result['valid'] or result.get('peer_id') != self.remote_peer:
            raise FederationTransportError('Untrusted federation response signature')
        body = result['payload']
        try:
            require_fields(body, {'schema_version', 'request_id', 'operation', 'result', 'scope'})
            if (type(body['schema_version']) is not int or body['schema_version'] != 1
                    or body['request_id'] != fingerprint(request)
                    or body['operation'] != payload['operation']):
                raise ValueError('Federation response request binding mismatch')
            canonical_payload(body)
        except (ValueError, TypeError, KeyError):
            raise FederationTransportError('Invalid federation response contract') from None
        return {'schema_version': 1, 'request': request, 'response': response}

    def manifest(self, snapshot_id):
        require_digest(snapshot_id)
        result = self.request({'schema_version': 1, 'operation': 'manifest', 'snapshot_id': snapshot_id})
        try:
            validate_manifest(result)
            if result['snapshot_id'] != snapshot_id:
                raise ValueError('Manifest request binding mismatch')
        except (ValueError, TypeError, KeyError):
            raise FederationTransportError('Invalid authenticated snapshot manifest') from None
        return result

    def page(self, snapshot_id, *, start=0, limit=20):
        require_digest(snapshot_id)
        if type(start) is not int or not 0 <= start <= 10000 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Invalid requested snapshot page')
        result = self.request({'schema_version': 1, 'operation': 'page',
            'snapshot_id': snapshot_id, 'start': start, 'limit': limit})
        from services.federation.checkpoints import TransferJournal
        try:
            TransferJournal.validate_batch(result, expected_start=start)
            if result['inventory_page']['manifest']['snapshot_id'] != snapshot_id or len(result['events']) > limit:
                raise ValueError('Snapshot page does not match request')
        except (ValueError, TypeError, KeyError):
            raise FederationTransportError('Invalid authenticated snapshot page') from None
        return result

    def revocation(self, snapshot_id, event_id, *, max_chain=100):
        require_digest(snapshot_id)
        require_digest(event_id)
        if type(max_chain) is not int or not 1 <= max_chain <= 100:
            raise ValueError('Invalid requested revocation chain budget')
        return self.request({'schema_version': 1, 'operation': 'revocation',
            'snapshot_id': snapshot_id, 'event_id': event_id, 'max_chain': max_chain})

    def sync_snapshot(self, snapshot_id, journal, reconciler, *, session_id=None,
                      page_size=20, max_pages=1000):
        from services.federation.checkpoints import TransferJournal
        from services.federation.reconciliation import Reconciler
        if not isinstance(journal, TransferJournal) or not isinstance(reconciler, Reconciler):
            raise ValueError('Durable transfer journal and reconciler required')
        if type(max_pages) is not int or not 1 <= max_pages <= 10000:
            raise ValueError('Explicit bounded transfer page budget required')
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError('Invalid transfer page size')
        manifest = self.manifest(snapshot_id)
        if session_id is None:
            session_id = journal.begin(self.remote_peer, manifest, now_unix=self._now())
        state = journal.status(session_id)
        if state['peer'] != self.remote_peer or state['manifest'] != manifest:
            raise ValueError('Resume session belongs to another peer or snapshot')
        if state['status'] == 'active':
            journal.resume_prepared(session_id, reconciler, now_unix=self._now())
        for _ in range(max_pages):
            state = journal.status(session_id)
            if state['status'] == 'complete':
                return state
            if state['status'] != 'active':
                raise ValueError('Cannot resume inactive or failed transfer')
            batch = self.page(snapshot_id, start=state['next_position'], limit=page_size)
            journal.accept(session_id, batch, reconciler,
                authenticated_peer=self.remote_peer, now_unix=self._now())
        # Exhausting one caller budget is a checkpoint, not a failed transfer.
        return journal.status(session_id)

    def metrics(self):
        return {'requests': self.requests, 'response_bytes': self.response_bytes,
                'scope': 'received bounded HTTP bytes; no WAN latency or throughput certification'}

    def _validate_access(self, result, *, session_id=None, snapshot_id=None):
        require_fields(result, {'schema_version', 'session_id', 'peer', 'snapshot_id',
            'issued_unix', 'expires_unix', 'state', 'next_sequence', 'next_position',
            'max_pages', 'max_response_bytes', 'used_response_bytes', 'scope'})
        if (type(result['schema_version']) is not int or result['schema_version'] != 1
                or result['peer'] != self.peer_id or result['state'] not in {'active', 'expired', 'cancelled'}):
            raise FederationTransportError('Invalid access-session contract')
        value = result['session_id']
        if type(value) is not str or len(value) != 32 or any(c not in '0123456789abcdef' for c in value):
            raise FederationTransportError('Invalid access-session identifier')
        require_digest(result['snapshot_id'])
        if session_id is not None and value != session_id:
            raise FederationTransportError('Access-session identifier mismatch')
        if snapshot_id is not None and result['snapshot_id'] != snapshot_id:
            raise FederationTransportError('Access-session snapshot mismatch')
        for name in ('issued_unix', 'expires_unix', 'next_sequence', 'next_position',
                     'max_pages', 'max_response_bytes', 'used_response_bytes'):
            if type(result[name]) is not int or result[name] < 0:
                raise FederationTransportError('Invalid access-session resource accounting')
        if (not 0 < result['expires_unix'] - result['issued_unix'] <= 3600
                or not 1 <= result['max_pages'] <= 10000
                or not 1 <= result['max_response_bytes'] <= 64 * 1024 * 1024
                or result['next_sequence'] > result['max_pages']
                or result['next_position'] > 10000
                or result['used_response_bytes'] > result['max_response_bytes']):
            raise FederationTransportError('Invalid access-session limits')
        return result

    def open_session(self, snapshot_id, *, ttl_seconds=300, max_pages=1000,
                     max_response_bytes=16 * 1024 * 1024):
        require_digest(snapshot_id)
        for value, upper in ((ttl_seconds, 3600), (max_pages, 10000),
                             (max_response_bytes, 64 * 1024 * 1024)):
            if type(value) is not int or not 1 <= value <= upper:
                raise ValueError('Invalid requested access-session budget')
        result = self.request({'schema_version': 1, 'operation': 'open_session',
            'snapshot_id': snapshot_id, 'ttl_seconds': ttl_seconds,
            'max_pages': max_pages, 'max_response_bytes': max_response_bytes})
        result = self._validate_access(result, snapshot_id=snapshot_id)
        if (result['state'] != 'active' or result['next_sequence'] != 0
                or result['next_position'] != 0 or result['used_response_bytes'] != 0
                or result['expires_unix'] <= self._now()
                or result['max_pages'] != max_pages or result['max_response_bytes'] != max_response_bytes):
            raise FederationTransportError('Invalid newly issued access grant')
        return result

    def session_status(self, session_id):
        result = self.request({'schema_version': 1, 'operation': 'session_status', 'session_id': session_id})
        return self._validate_access(result, session_id=session_id)

    def cancel_session(self, session_id):
        result = self.request({'schema_version': 1, 'operation': 'cancel_session', 'session_id': session_id})
        result = self._validate_access(result, session_id=session_id)
        if result['state'] not in {'cancelled', 'expired'}:
            raise FederationTransportError('Cancellation response did not revoke access')
        return result

    def session_page(self, session_id, snapshot_id, *, sequence, start=0, limit=20):
        require_digest(snapshot_id)
        if (type(sequence) is not int or not 0 <= sequence < 10000
                or type(start) is not int or not 0 <= start <= 10000
                or type(limit) is not int or not 1 <= limit <= 100):
            raise ValueError('Invalid requested session sequence or page')
        result = self.request({'schema_version': 1, 'operation': 'session_page',
            'session_id': session_id, 'snapshot_id': snapshot_id, 'sequence': sequence,
            'start': start, 'limit': limit})
        try:
            require_fields(result, {'schema_version', 'session_id', 'sequence', 'next_sequence', 'page'})
            if (type(result['schema_version']) is not int or result['schema_version'] != 1
                    or result['session_id'] != session_id or result['sequence'] != sequence
                    or type(result['sequence']) is not int or type(result['next_sequence']) is not int
                    or result['next_sequence'] != sequence + 1):
                raise ValueError('Session page does not match access grant')
            from services.federation.checkpoints import TransferJournal
            TransferJournal.validate_batch(result['page'], expected_start=start)
            page = result['page']
            if page['inventory_page']['manifest']['snapshot_id'] != snapshot_id or len(page['events']) > limit:
                raise ValueError('Session page does not match requested snapshot')
        except (ValueError, TypeError, KeyError):
            raise FederationTransportError('Invalid authenticated access-session page') from None
        return result

    def sync_session(self, access_id, journal, reconciler, *, transfer_id=None,
                     page_size=20, max_pages=1000):
        """Resume an expiring remote grant and a separate durable local checkpoint.

        If the server advanced before the local acknowledgement, the exact prior
        sequence is replayed from its durable cache. No events are regenerated.
        """
        from services.federation.checkpoints import TransferJournal
        from services.federation.reconciliation import Reconciler
        if not isinstance(journal, TransferJournal) or not isinstance(reconciler, Reconciler):
            raise ValueError('Durable journal and reconciler required')
        if type(max_pages) is not int or not 1 <= max_pages <= 10000:
            raise ValueError('Bounded local page budget required')
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError('Invalid requested page size')
        access = self.session_status(access_id)
        if access['state'] != 'active':
            raise ValueError('Remote read grant is expired or cancelled')
        manifest = self.manifest(access['snapshot_id'])
        if transfer_id is None:
            if access['next_sequence'] != 0:
                raise ValueError('An advanced access grant requires its original local transfer')
            transfer_id = journal.begin(self.remote_peer, manifest, now_unix=self._now())
        state = journal.status(transfer_id)
        if state['peer'] != self.remote_peer or state['manifest'] != manifest:
            raise ValueError('Remote grant does not match local transfer')
        journal.bind_access(transfer_id, access_id)
        if state['status'] == 'active':
            journal.resume_prepared(transfer_id, reconciler, now_unix=self._now())
        for _ in range(max_pages):
            state = journal.status(transfer_id)
            if state['status'] == 'complete':
                return state
            if state['status'] != 'active':
                raise ValueError('Local transfer is no longer active')
            outgoing = journal.prepare_access_request(transfer_id, access_id, page_size=page_size)
            response = self.session_page(**outgoing)
            journal.accept(transfer_id, response['page'], reconciler,
                           authenticated_peer=self.remote_peer, now_unix=self._now())
        return journal.status(transfer_id)
