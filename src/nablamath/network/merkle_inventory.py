"""Domain-separated Merkle commitments for finite, sorted event inventories.

A root authenticates a set only when a trusted peer signs it. Membership never
establishes a mathematical result, a timestamp, or absence of a later revision.
The tree shape uses the largest power-of-two split, without duplicated leaves.
"""
from hashlib import sha256
from itertools import islice

from ..core.semantic_contracts import canonical_payload, require_digest, require_fields
from ..core.semantic_ir import fingerprint

PROFILE = 'Nabla-event-inventory-v1'
MAX_ITEMS = 10000
EMPTY_ROOT = sha256((PROFILE + ':empty').encode()).hexdigest()


def _integer(value, name, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError('Invalid ' + name)
    return value


def _leaf(identifier):
    require_digest(identifier)
    return sha256((PROFILE + ':leaf:').encode() + bytes.fromhex(identifier)).hexdigest()


def _node(left, right):
    return sha256((PROFILE + ':node:').encode() + bytes.fromhex(left) + bytes.fromhex(right)).hexdigest()


def _split(size):
    return 1 << ((size - 1).bit_length() - 1)


def _root(values):
    if not values:
        return EMPTY_ROOT
    if len(values) == 1:
        return _leaf(values[0])
    cut = _split(len(values))
    return _node(_root(values[:cut]), _root(values[cut:]))


def normalize_inventory(identifiers):
    """Consume bounded inputs, reject duplicates instead of silently dropping them."""
    try:
        values = tuple(islice(iter(identifiers), MAX_ITEMS + 1))
    except TypeError as exc:
        raise ValueError('An iterable inventory is required') from exc
    if len(values) > MAX_ITEMS:
        raise ValueError('Inventory item budget exceeded')
    for value in values:
        require_digest(value)
    if len(set(values)) != len(values):
        raise ValueError('Duplicate inventory identifiers')
    return tuple(sorted(values))


class MerkleInventory:
    """Immutable finite inventory; paths contain at most fourteen sibling hashes."""
    def __init__(self, identifiers):
        self.identifiers = normalize_inventory(identifiers)
        self.count = len(self.identifiers)
        self._subtrees = {}
        self.root = self._subroot(0, self.count)

    def _subroot(self, start, stop):
        key = (start, stop)
        if key not in self._subtrees:
            size = stop - start
            if size == 0:
                value = EMPTY_ROOT
            elif size == 1:
                value = _leaf(self.identifiers[start])
            else:
                cut = start + _split(size)
                value = _node(self._subroot(start, cut), self._subroot(cut, stop))
            self._subtrees[key] = value
        return self._subtrees[key]

    @property
    def manifest(self):
        body = {'schema_version': 1, 'profile': PROFILE,
                'root': self.root, 'count': self.count}
        return {**body, 'snapshot_id': fingerprint(body)}

    def proof(self, index):
        _integer(index, 'leaf position', 0, self.count - 1)
        path = []

        def descend(start, stop, position):
            if stop - start == 1:
                return
            cut = start + _split(stop - start)
            if position < cut:
                descend(start, cut, position)
                path.append({'side': 'right', 'hash': self._subroot(cut, stop)})
            else:
                descend(cut, stop, position)
                path.append({'side': 'left', 'hash': self._subroot(start, cut)})

        descend(0, self.count, index)
        return {'schema_version': 1, 'snapshot_id': self.manifest['snapshot_id'],
                'index': index, 'identifier': self.identifiers[index], 'siblings': path}

    def page(self, start=0, limit=100):
        _integer(start, 'page start', 0, self.count)
        _integer(limit, 'page size', 1, 100)
        stop = min(self.count, start + limit)
        return {'schema_version': 1, 'manifest': self.manifest, 'start': start,
                'proofs': [self.proof(i) for i in range(start, stop)],
                'next_position': stop if stop < self.count else None}


def validate_manifest(manifest):
    require_fields(manifest, {'schema_version', 'profile', 'root', 'count', 'snapshot_id'})
    if type(manifest['schema_version']) is not int or manifest['schema_version'] != 1 or manifest['profile'] != PROFILE:
        raise ValueError('Unsupported inventory profile')
    require_digest(manifest['root'])
    require_digest(manifest['snapshot_id'])
    _integer(manifest['count'], 'inventory count', 0, MAX_ITEMS)
    body = {k: v for k, v in manifest.items() if k != 'snapshot_id'}
    if fingerprint(body) != manifest['snapshot_id']:
        raise ValueError('Manifest content identifier mismatch')
    if manifest['count'] == 0 and manifest['root'] != EMPTY_ROOT:
        raise ValueError('Invalid empty inventory root')
    return manifest


def _expected_sides(count, index):
    if count == 1:
        return []
    cut = _split(count)
    if index < cut:
        return _expected_sides(cut, index) + ['right']
    return _expected_sides(count - cut, index - cut) + ['left']


def verify_membership(manifest, proof):
    """Validate tree shape as well as hashes, index, count and snapshot binding."""
    validate_manifest(manifest)
    require_fields(proof, {'schema_version', 'snapshot_id', 'index', 'identifier', 'siblings'})
    if type(proof['schema_version']) is not int or proof['schema_version'] != 1:
        raise ValueError('Unsupported membership proof')
    if proof['snapshot_id'] != manifest['snapshot_id']:
        raise ValueError('Membership proof belongs to another snapshot')
    index = _integer(proof['index'], 'leaf position', 0, manifest['count'] - 1)
    identifier = require_digest(proof['identifier'])
    siblings = proof['siblings']
    if type(siblings) is not list or len(siblings) > 14:
        raise ValueError('Membership path exceeds budget')
    sides = _expected_sides(manifest['count'], index)
    if len(sides) != len(siblings):
        raise ValueError('Incorrect membership tree shape')
    current = _leaf(identifier)
    for expected, sibling in zip(sides, siblings):
        require_fields(sibling, {'side', 'hash'})
        if sibling['side'] != expected:
            raise ValueError('Incorrect membership sibling direction')
        other = require_digest(sibling['hash'])
        current = _node(other, current) if expected == 'left' else _node(current, other)
    if current != manifest['root']:
        raise ValueError('Membership root mismatch')
    return identifier


def verify_page(page, *, manifest=None, expected_start=None):
    canonical_payload(page)
    require_fields(page, {'schema_version', 'manifest', 'start', 'proofs', 'next_position'})
    if type(page['schema_version']) is not int or page['schema_version'] != 1:
        raise ValueError('Unsupported inventory page')
    actual = validate_manifest(page['manifest'])
    if manifest is not None and canonical_payload(actual) != canonical_payload(validate_manifest(manifest)):
        raise ValueError('Page snapshot changed during transfer')
    start = _integer(page['start'], 'page start', 0, actual['count'])
    if expected_start is not None and start != expected_start:
        raise ValueError('Noncontiguous inventory page')
    proofs = page['proofs']
    if type(proofs) is not list or len(proofs) > 100:
        raise ValueError('Page proof budget exceeded')
    if not proofs and start < actual['count']:
        raise ValueError('Empty nonterminal page')
    identifiers = []
    for position, proof in enumerate(proofs, start):
        identifier = verify_membership(actual, proof)
        if proof['index'] != position:
            raise ValueError('Noncontiguous membership positions')
        identifiers.append(identifier)
    if identifiers != sorted(set(identifiers)):
        raise ValueError('Inventory page is not strictly sorted')
    stop = start + len(identifiers)
    expected_next = stop if stop < actual['count'] else None
    if page['next_position'] != expected_next or (page['next_position'] is not None and type(page['next_position']) is not int):
        raise ValueError('Invalid pagination checkpoint')
    return identifiers
