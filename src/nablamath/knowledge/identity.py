"""Ed25519 snapshot envelopes with caller-pinned peer keys and explicit revocation.

Key pinning authenticates the configured key, not the real-world identity,
expertise or independence of a researcher. Private keys are never serialized here.
"""
from dataclasses import dataclass
from ..core.semantic_ir import canonical_json, fingerprint


def _crypto():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
        from cryptography.hazmat.primitives import serialization
    except ImportError as exc:
        raise ImportError('Instale nablamath[federation] para assinaturas Ed25519') from exc
    return Ed25519PrivateKey, Ed25519PublicKey, serialization


def generate_signing_key():
    private, _, _ = _crypto()
    return private.generate()


def public_key_hex(private_key):
    _, _, serialization = _crypto()
    return private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def sign_snapshot(snapshot, private_key):
    from .federation import verify_snapshot
    if not verify_snapshot(snapshot, allow_unsigned=True)['valid']:
        raise ValueError('Snapshot inválido ou já autenticado por outro protocolo')
    payload = {'schema_version': 1, 'algorithm': 'Ed25519', 'public_key': public_key_hex(private_key),
               'snapshot': snapshot}
    # Independent JSON copy prevents caller mutations of the signed payload.
    import json
    envelope = json.loads(canonical_json(payload))
    envelope['signature'] = private_key.sign(canonical_json(payload).encode('utf-8')).hex()
    return envelope


@dataclass(frozen=True)
class PeerKey:
    peer_id: str
    public_key: str
    revoked: bool = False

    def __post_init__(self):
        if not isinstance(self.peer_id, str) or not self.peer_id.strip() or type(self.revoked) is not bool:
            raise ValueError('Contrato de identidade inválido')
        if not isinstance(self.public_key, str) or len(self.public_key) != 64:
            raise ValueError('Chave pública Ed25519 inválida')
        try:
            if len(bytes.fromhex(self.public_key)) != 32:
                raise ValueError('Comprimento de chave inválido')
        except ValueError as exc:
            raise ValueError('Chave pública Ed25519 inválida') from exc
        object.__setattr__(self, 'public_key', self.public_key.lower())


class PeerTrust:
    """Explicit pin/rotate/revoke operations; no trust-on-first-use side effects."""
    def __init__(self, keys=()):
        self._keys = {}
        for key in keys:
            self.pin(key)

    def pin(self, key):
        if not isinstance(key, PeerKey):
            raise ValueError('PeerKey obrigatório')
        existing = self._keys.get((key.peer_id, key.public_key))
        if existing is not None and existing.revoked and not key.revoked:
            raise ValueError('Chave revogada não pode ser reativada')
        self._keys[key.peer_id, key.public_key] = key

    def revoke(self, peer_id, public_key):
        from dataclasses import replace
        key = self._keys[peer_id, public_key.lower()]
        self.pin(replace(key, revoked=True))

    def accepts(self, peer_id, public_key):
        key = self._keys.get((peer_id, public_key))
        return key is not None and not key.revoked

    def to_data(self):
        from dataclasses import asdict
        return {'schema_version': 1, 'keys': [asdict(key) for _, key in sorted(self._keys.items())]}

    @classmethod
    def from_data(cls, data):
        if set(data) != {'schema_version', 'keys'} or data['schema_version'] != 1 or len(data['keys']) > 10000:
            raise ValueError('Trust store inválido')
        return cls(PeerKey(**key) for key in data['keys'])


def verify_signed_snapshot(envelope, trust):
    from .federation import verify_snapshot
    _, public, _ = _crypto()
    from cryptography.exceptions import InvalidSignature
    try:
        if len(canonical_json(envelope).encode()) > 32*1024*1024:
            raise ValueError('Envelope excede limite')
        if set(envelope) != {'schema_version', 'algorithm', 'public_key', 'snapshot', 'signature'}:
            raise ValueError('Contrato de envelope inválido')
        if envelope['schema_version'] != 1 or envelope['algorithm'] != 'Ed25519':
            raise ValueError('Algoritmo não suportado')
        peer = envelope['snapshot']['peer_id']
        key = envelope['public_key']
        if not trust.accepts(peer, key):
            raise ValueError('Chave desconhecida ou revogada para este par')
        payload = {k:v for k,v in envelope.items() if k != 'signature'}
        public.from_public_bytes(bytes.fromhex(key)).verify(bytes.fromhex(envelope['signature']),
                                                            canonical_json(payload).encode('utf-8'))
        report = verify_snapshot(envelope['snapshot'], allow_unsigned=True)
        return {**report, 'authenticated': report['valid'], 'authentication': 'Ed25519-pinned-peer-key',
                'public_key': key, 'envelope_id': fingerprint(envelope),
                'real_world_identity_verified': False}
    except (ValueError, TypeError, KeyError, InvalidSignature) as exc:
        return {'valid': False, 'authenticated': False, 'reason': str(exc) or 'Assinatura inválida'}
