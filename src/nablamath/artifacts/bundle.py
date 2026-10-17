"""Canonical JSON bundles of receipts, datasets and proof evidence."""
import json
from pathlib import Path
from ..core.semantic_ir import canonical_json, fingerprint
from ..calc.receipt import verify_receipt


def create_bundle(receipts, *, datasets=None, proofs=None):
    receipts = list(receipts)
    if len(receipts) > 1000 or not all(verify_receipt(r) for r in receipts):
        raise ValueError('Invalid receipts or bundle budget')
    body = {'schema_version':1,'kind':'nabla_artifact_bundle','receipts':receipts,
            'datasets':datasets or {},'proofs':proofs or {},
            'limitations':'Proof attachments are evidence bytes; their validity is not established by hashing.'}
    raw = canonical_json(body)
    if len(raw.encode()) > 16*1024*1024:
        raise ValueError('Bundle exceeds 16 MiB')
    return {**json.loads(raw),'content_id':fingerprint(body)}


def verify_bundle(bundle):
    try:
        rebuilt = create_bundle(bundle['receipts'],datasets=bundle['datasets'],proofs=bundle['proofs'])
        return rebuilt == bundle
    except (ValueError,TypeError,KeyError,RecursionError):
        return False


def save_bundle(bundle, path):
    if not verify_bundle(bundle):
        raise ValueError('Invalid bundle')
    # Exclusive creation protects user artifacts against accidental replacement.
    with Path(path).open('x',encoding='utf-8') as stream:
        stream.write(canonical_json(bundle)+'\n')


def load_bundle(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(16*1024*1024+1)
    if len(raw) > 16*1024*1024:
        raise ValueError('Bundle exceeds 16 MiB')
    def unique(pairs):
        result = {}
        for key,value in pairs:
            if key in result:
                raise ValueError('Duplicate bundle field')
            result[key] = value
        return result
    bundle = json.loads(raw,object_pairs_hook=unique)
    if not verify_bundle(bundle):
        raise ValueError('Bundle integrity failed')
    return bundle
