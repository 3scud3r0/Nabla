"""In-memory local identity with explicit consent and destructive key recovery."""
from dataclasses import dataclass

from ..knowledge.identity import generate_signing_key, public_key_hex
from ..network.signatures import sign_message


@dataclass(frozen=True)
class IdentityPolicy:
    allow_signing: bool = False
    allow_rotation: bool = False
    allow_recovery: bool = False

    def __post_init__(self):
        if any(type(value) is not bool for value in (self.allow_signing, self.allow_rotation, self.allow_recovery)):
            raise ValueError('Identity consent flags must be booleans')


class LocalIdentity:
    """Private keys stay in memory; recovery revokes old authentication continuity.

    Administrators must distribute the newly pinned key through their own trusted
    channel. This class does not claim real-world identity verification.
    """
    def __init__(self, peer_id, policy=None):
        if not isinstance(peer_id, str) or not peer_id.strip():
            raise ValueError('Invalid peer identity')
        self.peer_id = peer_id
        self.policy = policy or IdentityPolicy()
        self._key = None
        self.revoked_keys = set()

    @property
    def public_key(self):
        return None if self._key is None else public_key_hex(self._key)

    def activate(self):
        if not self.policy.allow_signing:
            raise PermissionError('Signing consent required')
        if self._key is None:
            self._key = generate_signing_key()
        return self.public_key

    def sign(self, payload, **metadata):
        if not self.policy.allow_signing or self._key is None:
            raise PermissionError('Active signing consent required')
        return sign_message(payload, self._key, peer_id=self.peer_id, **metadata)

    def rotate(self, *, recovery=False):
        if not self.policy.allow_signing or not (self.policy.allow_recovery if recovery else self.policy.allow_rotation):
            raise PermissionError('Explicit rotation/recovery consent required')
        new_key = generate_signing_key()
        if self.public_key is not None:
            self.revoked_keys.add(self.public_key)
        self._key = new_key
        return self.public_key

    def revoke(self):
        if self.public_key is not None:
            self.revoked_keys.add(self.public_key)
        self._key = None
        self.policy = IdentityPolicy()
