"""Issuer-pinned, expiring competence declarations; no automatic real-world identity.

An operator must independently verify and pin each issuer. Signatures establish
who made a declaration, never whether a competence or affiliation is true.
"""
from ..core.semantic_contracts import canonical_payload
from ..core.semantic_ir import fingerprint
from ..network.signatures import sign_message, MessageVerifier

CONTEXT = 'institutional-attestation-v1'


def issue_attestation(private_key, *, issuer, subject, institution, competencies,
                      issued_unix, expires_unix, serial):
    payload = {'kind': CONTEXT, 'subject': subject, 'institution': institution,
               'competencies': list(competencies), 'serial': serial}
    _payload(payload)
    return sign_message(payload, private_key, peer_id=issuer, audience=CONTEXT,
                        nonce=serial, issued_unix=issued_unix, expires_unix=expires_unix)


def _payload(payload):
    if type(payload) is not dict or set(payload) != {'kind','subject','institution','competencies','serial'}:
        raise ValueError('Invalid attestation fields')
    if payload['kind'] != CONTEXT:
        raise ValueError('Wrong attestation context')
    for name in ('subject','institution','serial'):
        value = payload[name]
        if type(value) is not str or not value.strip() or len(value) > 256:
            raise ValueError('Invalid attestation label')
    values = payload['competencies']
    if (type(values) is not list or not 1 <= len(values) <= 64
            or any(type(x) is not str or not x.strip() or len(x)>128 for x in values)
            or len(set(values)) != len(values)):
        raise ValueError('Invalid competence declarations')
    canonical_payload(payload)


class AttestationVerifier:
    def __init__(self, trust, *, revoked=()):
        self.trust = trust
        self.revoked = set(revoked)

    def revoke(self, issuer, serial):
        self.revoked.add((issuer, serial))

    def verify(self, envelope, *, now_unix):
        # Credentials may be presented repeatedly. This is not a message inbox.
        result = MessageVerifier(self.trust, CONTEXT).verify(envelope, now_unix=now_unix)
        if not result['valid']:
            return result
        try:
            payload = result['payload']
            _payload(payload)
            if envelope['nonce'] != payload['serial']:
                raise ValueError('Serial binding mismatch')
            if (result['peer_id'], payload['serial']) in self.revoked:
                raise ValueError('Revoked attestation')
            return {**result, 'attestation_id': fingerprint(envelope),
                    'real_world_identity_verified': False,
                    'competence_independently_verified': False}
        except (ValueError, KeyError, TypeError) as exc:
            return {'valid': False, 'reason': str(exc)}
