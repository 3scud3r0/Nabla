"""Signed per-artifact publication plans with local revocation and dry-run receipts.

This module never submits data. A plan authorizes one destination and exact bytes;
key trust and rights declarations are supplied explicitly by the operator.
"""
from hashlib import sha256
from ..core.semantic_ir import fingerprint
from ..network.signatures import sign_message, MessageVerifier


def publication_plan(artifacts, *, destination, reviewer, license_id):
    if type(artifacts) is not dict or not 1<=len(artifacts)<=100:
        raise ValueError('1..100 named artifact byte strings required')
    for text in (destination,reviewer,license_id):
        if not isinstance(text,str) or not text.strip() or len(text)>256:
            raise ValueError('Destination, reviewer and license required')
    if any(not isinstance(name, str) for name in artifacts):
        raise ValueError('Artifact names must be strings')
    if sum(len(raw) for raw in artifacts.values() if type(raw) is bytes)>64*1024*1024:
        raise ValueError('Aggregate artifact byte budget exceeded')
    entries=[]
    for name, raw in sorted(artifacts.items()):
        if not isinstance(name,str) or not name or '/' in name or '\\' in name or name in {'.','..'} or len(name)>256 or any(ord(c)<32 for c in name):
            raise ValueError('Artifact names must be flat relative names')
        if type(raw) is not bytes or len(raw)>16*1024*1024:
            raise ValueError('Bounded artifact bytes required')
        entries.append(dict(name=name,sha256=sha256(raw).hexdigest(),size=len(raw)))
    body=dict(schema_version=1,destination=destination,reviewer=reviewer,license_id=license_id,artifacts=entries)
    return {**body,'plan_id':fingerprint(body)}


def authorize_plan(plan, private_key, *, peer_id, now_unix, expires_unix, redistributable=False):
    if redistributable is not True:
        raise ValueError('Per-plan redistribution declaration required')
    return sign_message(dict(plan=plan,redistributable=True),private_key,peer_id=peer_id,
        audience='nabla-publication',nonce=plan['plan_id'],issued_unix=now_unix,expires_unix=expires_unix)


class PublicationReview:
    def __init__(self, trust):
        self.verifier=MessageVerifier(trust,'nabla-publication')
        self.revoked=set()
        self.receipts={}
        self.last_time=-1

    def revoke(self, plan_id):
        self.revoked.add(plan_id)

    def dry_run(self, artifacts, envelope, *, destination, reviewer, license_id, now_unix):
        if type(now_unix) is not int or now_unix < self.last_time:
            raise ValueError('Invalid or regressing review clock')
        self.last_time=now_unix
        plan=publication_plan(artifacts,destination=destination,reviewer=reviewer,license_id=license_id)
        identifier=plan['plan_id']
        if identifier in self.revoked:
            raise ValueError('Publication authorization revoked')
        # Idempotency is restricted to the identical signed authorization and bytes.
        authorization_id=fingerprint(envelope)
        if identifier in self.receipts:
            previous=self.receipts[identifier]
            if previous['authorization_id']!=authorization_id or not envelope['issued_unix']<=now_unix<envelope['expires_unix']:
                raise ValueError('Conflicting or expired authorization')
            # Check pin revocation even for a previously reviewed request.
            if not self.verifier.trust.accepts(envelope['peer_id'],envelope['public_key']):
                raise ValueError('Signing key revoked')
            return dict(previous)
        verified=self.verifier.verify(envelope,now_unix=now_unix)
        if not verified['valid'] or verified['payload']!={'plan':plan,'redistributable':True}:
            raise ValueError('Signature or exact artifact authorization mismatch')
        receipt=dict(plan_id=identifier,authorization_id=authorization_id,status='dry_run_validated',
                     submitted=False,destination=destination,rights='operator_declared_not_legally_adjudicated')
        self.receipts[identifier]=receipt
        return dict(receipt)
