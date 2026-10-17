"""ECDSA P-256 receipt signatures with caller-pinned laboratory keys.

Keys authenticate a configured signer, never expertise or mathematical truth.
Existing Ed25519 network envelopes keep their separate established protocol.
"""
import json
from ..core.semantic_ir import canonical_json, fingerprint

CONTEXT = 'Nabla-signed-evidence-v1'


def _crypto():
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes, serialization
    except ImportError as exc:
        raise ImportError('Install nablamath[federation] for ECDSA signatures') from exc
    return ec, hashes, serialization


def generate_key():
    ec, _, _ = _crypto()
    return ec.generate_private_key(ec.SECP256R1())


def public_key_hex(key):
    _, _, serialization = _crypto()
    public = key.public_key() if hasattr(key,'public_key') else key
    return public.public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo).hex()


def sign(payload, private_key, *, signer):
    ec, hashes, _ = _crypto()
    if not isinstance(signer,str) or not signer.strip() or len(signer) > 256 or not isinstance(private_key.curve,ec.SECP256R1):
        raise ValueError('A signer name and ECDSA P-256 private key are required')
    body = {'schema_version':1,'context':CONTEXT,'algorithm':'ECDSA-P256-SHA256',
            'signer':signer,'public_key':public_key_hex(private_key),'payload':payload}
    raw = canonical_json(body)
    if len(raw.encode()) > 16*1024*1024:
        raise ValueError('Signed payload exceeds budget')
    signature = private_key.sign(raw.encode(),ec.ECDSA(hashes.SHA256())).hex()
    return {**json.loads(raw),'signature':signature,'content_id':fingerprint(body)}


class CryptoRegistry:
    def __init__(self):
        self._keys = {}
        self._revoked = set()

    def pin(self, signer, public_key):
        ec, _, serialization = _crypto()
        if not isinstance(signer,str) or not signer.strip() or len(signer) > 256 or not isinstance(public_key,str) or len(public_key) > 512:
            raise ValueError('Invalid signer/key')
        key = serialization.load_der_public_key(bytes.fromhex(public_key))
        if not isinstance(key,ec.EllipticCurvePublicKey) or not isinstance(key.curve,ec.SECP256R1):
            raise ValueError('ECDSA P-256 public key required')
        normalized = public_key_hex(key)
        if normalized != public_key or (signer,normalized) in self._revoked:
            raise ValueError('Noncanonical or revoked key')
        self._keys[signer,normalized] = key

    def revoke(self, signer, public_key):
        if (signer,public_key) not in self._keys:
            raise KeyError('Unknown signer/key')
        self._revoked.add((signer,public_key))

    def verify(self, envelope):
        ec, hashes, _ = _crypto()
        from cryptography.exceptions import InvalidSignature
        try:
            fields = {'schema_version','context','algorithm','signer','public_key','payload','signature','content_id'}
            if not isinstance(envelope,dict) or set(envelope) != fields or len(canonical_json(envelope).encode()) > 16*1024*1024:
                return False
            if type(envelope['schema_version']) is not int or envelope['schema_version'] != 1 or envelope['context'] != CONTEXT or envelope['algorithm'] != 'ECDSA-P256-SHA256':
                return False
            identity = envelope['signer'],envelope['public_key']
            if identity in self._revoked or identity not in self._keys:
                return False
            if not isinstance(envelope['signature'],str) or len(envelope['signature']) > 160:
                return False
            body = {k:v for k,v in envelope.items() if k not in {'signature','content_id'}}
            if fingerprint(body) != envelope['content_id']:
                return False
            self._keys[identity].verify(bytes.fromhex(envelope['signature']),canonical_json(body).encode(),ec.ECDSA(hashes.SHA256()))
            return True
        except (ValueError,TypeError,KeyError,InvalidSignature):
            return False
