"""Signed opt-in registration and consent withdrawal over a versioned contract."""
from nablamath.core.semantic_contracts import canonical_payload, load_json, require_fields, require_text

from .db import RegistryDB

CAPABILITIES = frozenset({'exact_verification', 'simulation', 'dataset_exchange', 'relay'})
AUDIENCE = 'Nabla-registry-v1'


class Registry:
    def __init__(self, database, *, max_ttl=86400):
        if not isinstance(database, RegistryDB):
            raise ValueError('RegistryDB required')
        if type(max_ttl) is not int or not 1 <= max_ttl <= 86400:
            raise ValueError('Invalid registration TTL bound')
        self.database = database
        self.max_ttl = max_ttl

    def submit(self, envelope, *, now_unix):
        """Only previously pinned keys may opt in, renew or withdraw themselves."""
        with self.database.transaction() as connection:
            peer_id, payload = self.database.authenticate(connection, envelope,
                                                          audience=AUDIENCE, now_unix=now_unix)
            if type(payload) is not dict or payload.get('schema_version') != 1 or type(payload.get('schema_version')) is not int:
                raise ValueError('Unsupported registry request schema')
            operation = payload.get('operation')
            if operation == 'register':
                require_fields(payload, {'schema_version', 'operation', 'capabilities', 'ttl_seconds', 'visible', 'consent'})
                if payload['consent'] is not True or type(payload['visible']) is not bool:
                    raise PermissionError('Explicit registration and discovery consent required')
                capabilities = payload['capabilities']
                if (type(capabilities) is not list or not 1 <= len(capabilities) <= len(CAPABILITIES)
                        or any(type(item) is not str or item not in CAPABILITIES for item in capabilities)
                        or len(set(capabilities)) != len(capabilities)):
                    raise ValueError('Unknown, duplicate or empty capabilities')
                ttl = payload['ttl_seconds']
                if type(ttl) is not int or not 1 <= ttl <= self.max_ttl:
                    raise ValueError('Registration TTL outside policy')
                existing = connection.execute('SELECT 1 FROM peers WHERE peer_id=?', (peer_id,)).fetchone()
                if not existing and connection.execute('SELECT count(*) FROM peers').fetchone()[0] >= self.database.max_peers:
                    raise ValueError('Registry peer capacity exhausted')
                expires = now_unix + ttl
                connection.execute('INSERT OR REPLACE INTO peers VALUES (?,?,?,?)',
                                   (peer_id, canonical_payload(sorted(capabilities)), expires, int(payload['visible'])))
                self.database.append_audit(connection, 'registered', peer_id, now_unix,
                                           {'capabilities': sorted(capabilities), 'visible': payload['visible'], 'expires': expires})
                return {'schema_version': 1, 'registered': True, 'expires_unix': expires}
            if operation == 'withdraw':
                require_fields(payload, {'schema_version', 'operation'})
                changed = connection.execute('DELETE FROM peers WHERE peer_id=?', (peer_id,)).rowcount
                self.database.append_audit(connection, 'withdrawn', peer_id, now_unix)
                return {'schema_version': 1, 'registered': False, 'removed': bool(changed)}
            raise ValueError('Unsupported registry operation')

    def discover(self, *, now_unix, capability=None, after='', limit=100):
        """Return only explicit public entries, no keys, addresses or private fields."""
        if capability is not None and capability not in CAPABILITIES:
            raise ValueError('Unknown discovery capability')
        if type(after) is not str or len(after) > 256 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Invalid discovery page')
        peers = []
        with self.database.transaction() as connection:
            self.database.check_clock(connection, now_unix)
            # Scan a bounded registry in key order; output pages never exceed limit.
            rows = connection.execute('SELECT peer_id,capabilities,expires FROM peers WHERE visible=1 AND expires>? AND peer_id>? ORDER BY peer_id',
                                      (now_unix, after))
            for row in rows:
                if not self.database.active_peer(connection, row['peer_id'], now_unix=now_unix, capability=capability):
                    continue
                peers.append({'peer_id': row['peer_id'], 'capabilities': load_json(row['capabilities']),
                              'expires_unix': row['expires']})
                if len(peers) == limit:
                    break
        return {'schema_version': 1, 'peers': peers,
                'next_after': peers[-1]['peer_id'] if len(peers) == limit else None}
