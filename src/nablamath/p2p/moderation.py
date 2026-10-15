"""Local moderation gate composing authentication, abuse limits and quarantine.

No automatic rehabilitation or deletion: records retain the original rationale.
Operators own appeals and durable audit storage outside this bounded component.
"""
from hashlib import sha256
from threading import RLock

from .reputation import Reputation


class ModerationGate:
    def __init__(self, verifier, quarantine, *, reputation=None, max_decisions=10000):
        if type(max_decisions) is not int or max_decisions < 1:
            raise ValueError('Invalid audit limit')
        self.verifier, self.quarantine = verifier, quarantine
        self.reputation = reputation if reputation is not None else Reputation()
        self.max_decisions = max_decisions
        self._audit = []
        self._lock = RLock()

    def receive(self, raw, *, source, now_unix):
        """Only authenticated accepted messages reach the caller as payload.

        The transport source is an opaque local label. Unauthenticated claimed
        peer IDs cannot penalize pinned identities.
        """
        import json
        with self._lock:
            if not isinstance(raw, bytes) or not raw or len(raw) > self.quarantine.max_item_bytes:
                raise ValueError('Payload outside quarantine limits')
            if not isinstance(source, str) or not source.strip() or len(source) > 512:
                raise ValueError('Invalid source')
            if len(self._audit) >= self.max_decisions:
                raise ValueError('Audit capacity exhausted')
            digest = sha256(raw).hexdigest()
            try:
                envelope = json.loads(raw)
            except (ValueError, UnicodeError):
                result = {'valid': False, 'reason': 'Malformed JSON'}
            else:
                result = self.verifier.verify(envelope, now_unix=now_unix)
            peer = result.get('peer_id') if result['valid'] else None
            reason = result.get('reason', 'Accepted')
            accepted = bool(result['valid'])
            if accepted and self.reputation.report(peer)['blocked']:
                accepted, reason = False, 'Local abuse policy blocked peer'
            quarantine_id = None
            if not accepted:
                quarantine_id = self.quarantine.add(raw, reason=reason, source=source)
            decision = dict(schema_version=1, digest=digest, source=source, peer_id=peer,
                            accepted=accepted, reason=reason, quarantine_id=quarantine_id)
            self._audit.append(decision)
            return {**decision, **({'payload': result['payload']} if accepted else {})}

    def audit(self):
        with self._lock:
            return tuple(dict(event) for event in self._audit)
