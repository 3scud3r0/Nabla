"""Transactional per-pinned-peer quotas and queue admission policies.

A pinned key is not a distinct person. These quotas constrain local consumption;
resistance to Sybil, eclipse attacks and compromised operator pinning is outside
this service's guarantees. Payload authenticity does not establish correctness.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class RelayLimits:
    max_messages: int = 1000
    max_peer_messages: int = 100
    max_body_bytes: int = 65536
    max_total_bytes: int = 16 * 1024 * 1024
    messages_per_window: int = 60
    operations_per_window: int = 240
    window_seconds: int = 60
    max_message_ttl: int = 3600
    lease_seconds: int = 30

    def __post_init__(self):
        bounds = {
            'max_messages': (1, 100000), 'max_peer_messages': (1, 10000),
            'max_body_bytes': (1, 131072), 'max_total_bytes': (1, 1024 ** 3),
            'messages_per_window': (1, 10000), 'operations_per_window': (1, 100000),
            'window_seconds': (1, 86400), 'max_message_ttl': (1, 86400),
            'lease_seconds': (1, 3600),
        }
        for name, (minimum, maximum) in bounds.items():
            value = getattr(self, name)
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError('Invalid relay limit: ' + name)
        if self.max_peer_messages > self.max_messages:
            raise ValueError('Per-peer queue cannot exceed total queue')
        if self.max_body_bytes > self.max_total_bytes:
            raise ValueError('Message body cannot exceed global byte budget')


def charge_operation(connection, peer_id, *, now_unix, sending, limits):
    """Fixed-window counters persisted in the same transaction as the operation."""
    window = now_unix // limits.window_seconds
    # Retain only currently useful windows; trusted clock cannot move backwards.
    connection.execute('DELETE FROM relay_usage WHERE window<?', (window,))
    row = connection.execute('SELECT operations,sends FROM relay_usage WHERE peer_id=? AND window=?',
                             (peer_id, window)).fetchone()
    operations, sends = (0, 0) if row is None else (row['operations'], row['sends'])
    if operations >= limits.operations_per_window:
        raise PermissionError('Relay operation rate exhausted')
    if sending and sends >= limits.messages_per_window:
        raise PermissionError('Relay sending rate exhausted')
    connection.execute('INSERT OR REPLACE INTO relay_usage VALUES (?,?,?,?)',
                       (peer_id, window, operations + 1, sends + int(sending)))


def check_queue_admission(connection, peer_id, body_bytes, *, limits):
    row = connection.execute('SELECT count(*) AS count,coalesce(sum(body_bytes),0) AS bytes FROM relay_messages').fetchone()
    if row['count'] >= limits.max_messages or row['bytes'] + body_bytes > limits.max_total_bytes:
        raise ValueError('Relay global queue capacity exhausted')
    count = connection.execute('SELECT count(*) FROM relay_messages WHERE sender=?', (peer_id,)).fetchone()[0]
    if count >= limits.max_peer_messages:
        raise ValueError('Relay per-peer queue capacity exhausted')
