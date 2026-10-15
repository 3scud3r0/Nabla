"""Domain-bound Ed25519 messages. Trust is explicit and replay state is local.

These signatures authenticate pinned keys, not scientific truth or human identity.
Replay state must survive restarts in applications that need durable replay defence.
"""
import json
from threading import RLock

from ..core.semantic_contracts import canonical_payload
from ..knowledge.identity import PeerKey, PeerTrust, _crypto, public_key_hex

CONTEXT = 'Nabla-network-message-v1'


class ProtocolTrust(PeerTrust):
    """Administrative rotation revokes every previously pinned key for a peer."""
    def __init__(self, keys=()):
        self._rotation_lock = RLock()
        super().__init__(keys)

    def rotate(self, peer_id, new_public_key):
        replacement = PeerKey(peer_id, new_public_key)
        with self._rotation_lock:
            old = [key for key in self._keys.values() if key.peer_id == peer_id]
            if any(key.public_key == replacement.public_key for key in old):
                raise ValueError('Rotation requires a new key')
            self.pin(replacement)
            for key in old:
                self.revoke(peer_id, key.public_key)


def sign_message(payload, private_key, *, peer_id, audience, nonce, issued_unix, expires_unix):
    body = dict(schema_version=1, context=CONTEXT, peer_id=peer_id,
                public_key=public_key_hex(private_key), audience=audience, nonce=nonce,
                issued_unix=issued_unix, expires_unix=expires_unix, payload=payload)
    encoded = _validate(body)
    # Decode only after structural validation; detach caller-owned collections.
    body = json.loads(encoded)
    body['signature'] = private_key.sign(encoded.encode()).hex()
    canonical_payload(body)
    return body


def _validate(body):
    encoded = canonical_payload(body)
    fields = {'schema_version', 'context', 'peer_id', 'public_key', 'audience', 'nonce',
              'issued_unix', 'expires_unix', 'payload'}
    if set(body) != fields or type(body['schema_version']) is not int or body['schema_version'] != 1 or body['context'] != CONTEXT:
        raise ValueError('Invalid protocol envelope')
    for name in ('peer_id', 'audience', 'nonce'):
        if not isinstance(body[name], str) or not body[name].strip() or len(body[name]) > 256:
            raise ValueError('Invalid message identity')
    if any(type(body[name]) is not int or body[name] < 0 for name in ('issued_unix', 'expires_unix')):
        raise ValueError('Invalid time')
    if not 0 < body['expires_unix'] - body['issued_unix'] <= 86400:
        raise ValueError('Invalid message lifetime')
    PeerKey(body['peer_id'], body['public_key'])
    return encoded


class MessageVerifier:
    def __init__(self, trust, audience, *, max_pending=10000):
        if not isinstance(audience, str) or not audience.strip() or type(max_pending) is not int or max_pending < 1:
            raise ValueError('Invalid verifier configuration')
        self.trust, self.audience = trust, audience
        self.max_pending = max_pending
        self._seen = {}
        self._lock = RLock()
        self._last_time = -1

    def verify(self, envelope, *, now_unix):
        """Fail closed, including unavailable optional cryptography and clock rollback."""
        with self._lock:
            try:
                if type(now_unix) is not int or now_unix < self._last_time or now_unix < 0:
                    raise ValueError('Invalid or regressing clock')
                self._last_time = now_unix
                if type(envelope) is not dict:
                    raise ValueError('Invalid protocol envelope')
                signature = envelope.get('signature')
                if (type(signature) is not str or len(signature) != 128
                        or any(c not in '0123456789abcdef' for c in signature)):
                    raise ValueError('Expected lowercase Ed25519 signature')
                # Bound the entire envelope before copying or decoding any hex.
                body = json.loads(canonical_payload(envelope))
                body.pop('signature')
                encoded = _validate(body)
                if body['audience'] != self.audience or not body['issued_unix'] <= now_unix < body['expires_unix']:
                    raise ValueError('Wrong audience or expired/future message')
                if not self.trust.accepts(body['peer_id'], body['public_key']):
                    raise ValueError('Unknown or revoked peer key')
                _, public, _ = _crypto()
                public.from_public_bytes(bytes.fromhex(body['public_key'])).verify(bytes.fromhex(signature), encoded.encode())
                self._seen = {key: expiry for key, expiry in self._seen.items() if expiry > now_unix}
                replay_key = (body['peer_id'], body['nonce'])
                if replay_key in self._seen or len(self._seen) >= self.max_pending:
                    raise ValueError('Replay or replay capacity exhausted')
                self._seen[replay_key] = body['expires_unix']
                return {'valid': True, 'peer_id': body['peer_id'], 'payload': body['payload']}
            except (ValueError, TypeError, KeyError, ImportError, AttributeError) as exc:
                return {'valid': False, 'reason': str(exc) or 'Invalid signature'}
            except Exception as exc:
                # cryptography InvalidSignature is intentionally normalized.
                from cryptography.exceptions import InvalidSignature
                if isinstance(exc, InvalidSignature):
                    return {'valid': False, 'reason': 'Invalid signature'}
                raise
