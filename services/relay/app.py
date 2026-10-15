"""Durable authenticated store-and-forward queue with leases and graceful stop.

Every successful request commits nonce, quota, queue and audit state atomically.
Messages are delivered at least once until explicitly acknowledged, expired or
cancelled. Processing exactly once requires idempotency in the recipient itself.
No internet sockets are opened; call this service from a trusted deployment layer.
"""
import uuid

from nablamath.core.semantic_contracts import canonical_payload, load_json
from nablamath.core.semantic_ir import fingerprint
from services.registry.db import RegistryDB
from .abuse import RelayLimits, charge_operation, check_queue_admission
from .protocol import AUDIENCE, validate_request


class Relay:
    def __init__(self, database, *, limits=None):
        if not isinstance(database, RegistryDB):
            raise ValueError('RegistryDB required')
        if limits is not None and not isinstance(limits, RelayLimits):
            raise ValueError('RelayLimits required')
        self.database = database
        self.limits = limits or RelayLimits()
        with database.transaction() as connection:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS relay_messages (
                    message_id TEXT PRIMARY KEY,
                    sender TEXT NOT NULL, recipient TEXT NOT NULL,
                    body TEXT NOT NULL, body_bytes INTEGER NOT NULL,
                    created INTEGER NOT NULL, expires INTEGER NOT NULL,
                    lease_until INTEGER NOT NULL DEFAULT 0,
                    lease_token TEXT
                );
                CREATE INDEX IF NOT EXISTS relay_recipient ON relay_messages(recipient,created,message_id);
                CREATE TABLE IF NOT EXISTS relay_usage (
                    peer_id TEXT NOT NULL, window INTEGER NOT NULL,
                    operations INTEGER NOT NULL, sends INTEGER NOT NULL,
                    PRIMARY KEY(peer_id,window)
                );
                INSERT OR IGNORE INTO configuration VALUES ('relay_state','active');
            ''')

    def _expire(self, connection, now_unix):
        count = connection.execute('DELETE FROM relay_messages WHERE expires<=?', (now_unix,)).rowcount
        if count:
            self.database.append_audit(connection, 'relay_expired', None, now_unix, {'count': count})
        return count

    def submit(self, envelope, *, now_unix):
        envelope = load_json(canonical_payload(envelope))
        with self.database.transaction() as connection:
            peer_id, payload = self.database.authenticate(connection, envelope, audience=AUDIENCE, now_unix=now_unix)
            operation = validate_request(payload, max_body_bytes=self.limits.max_body_bytes,
                                         max_message_ttl=self.limits.max_message_ttl)
            if not self.database.active_peer(connection, peer_id, now_unix=now_unix, capability='relay'):
                raise PermissionError('Active opt-in relay capability required')
            state = self.database.get_setting(connection, 'relay_state')
            if state == 'stopped' or state == 'draining' and operation == 'send':
                raise PermissionError('Relay is shutting down')
            self._expire(connection, now_unix)
            charge_operation(connection, peer_id, now_unix=now_unix,
                             sending=operation == 'send', limits=self.limits)
            if operation == 'send':
                return self._send(connection, peer_id, payload, envelope['nonce'], now_unix)
            if operation == 'poll':
                return self._poll(connection, peer_id, payload, now_unix)
            if operation == 'ack':
                return self._ack(connection, peer_id, payload, now_unix)
            return self._cancel(connection, peer_id, payload, now_unix)

    def _send(self, connection, sender, payload, nonce, now_unix):
        recipient = payload['recipient']
        if not self.database.active_peer(connection, recipient, now_unix=now_unix, capability='relay'):
            raise PermissionError('Recipient has no active relay consent')
        body = canonical_payload(payload['body'])
        check_queue_admission(connection, sender, len(body.encode()), limits=self.limits)
        expires = now_unix + payload['ttl_seconds']
        # Replay nonces can be reused after their signed envelope expires while
        # an older queued message remains alive. Distinguish those admissions.
        message_id = fingerprint({'sender': sender, 'nonce': nonce, 'recipient': recipient,
                                  'body': payload['body'], 'created_unix': now_unix,
                                  'expires_unix': expires})
        # Admission must guarantee at least one bounded response can carry it.
        canonical_payload({'schema_version': 1, 'messages': [{
            'message_id': message_id, 'sender': sender, 'body': payload['body'],
            'expires_unix': expires, 'lease_token': '0' * 32,
            'lease_until_unix': expires}]})
        connection.execute('INSERT INTO relay_messages(message_id,sender,recipient,body,body_bytes,created,expires) VALUES (?,?,?,?,?,?,?)',
                           (message_id, sender, recipient, body, len(body.encode()), now_unix, expires))
        self.database.append_audit(connection, 'relay_enqueued', sender, now_unix, {'message_id': message_id})
        return {'schema_version': 1, 'message_id': message_id, 'expires_unix': expires}

    def _poll(self, connection, recipient, payload, now_unix):
        rows = connection.execute('SELECT * FROM relay_messages WHERE recipient=? AND lease_until<=? ORDER BY created,message_id LIMIT ?',
                                  (recipient, now_unix, payload['limit'])).fetchall()
        messages = []
        response_bytes = 0
        for row in rows:
            # Keep the whole response inside the shared JSON transport budget.
            if response_bytes + row['body_bytes'] + 1024 > 800000:
                break
            token = uuid.uuid4().hex
            lease_until = min(row['expires'], now_unix + self.limits.lease_seconds)
            candidate = {'message_id': row['message_id'], 'sender': row['sender'],
                         'body': load_json(row['body']), 'expires_unix': row['expires'],
                         'lease_token': token, 'lease_until_unix': lease_until}
            try:
                canonical_payload({'schema_version': 1, 'messages': messages + [candidate]})
            except ValueError:
                # Leave unreturned messages unleased for a later bounded poll.
                break
            connection.execute('UPDATE relay_messages SET lease_token=?,lease_until=? WHERE message_id=?',
                               (token, lease_until, row['message_id']))
            messages.append(candidate)
            response_bytes += row['body_bytes'] + 1024
        self.database.append_audit(connection, 'relay_polled', recipient, now_unix, {'count': len(messages)})
        return {'schema_version': 1, 'messages': messages}

    def _ack(self, connection, peer_id, payload, now_unix):
        row = connection.execute('SELECT recipient,lease_token,lease_until FROM relay_messages WHERE message_id=?',
                                 (payload['message_id'],)).fetchone()
        if (row is None or row['recipient'] != peer_id or row['lease_token'] != payload['lease_token']
                or row['lease_until'] <= now_unix):
            raise PermissionError('Missing or stale recipient lease')
        connection.execute('DELETE FROM relay_messages WHERE message_id=?', (payload['message_id'],))
        self.database.append_audit(connection, 'relay_acknowledged', peer_id, now_unix,
                                   {'message_id': payload['message_id']})
        return {'schema_version': 1, 'acknowledged': True}

    def _cancel(self, connection, peer_id, payload, now_unix):
        row = connection.execute('SELECT sender FROM relay_messages WHERE message_id=?',
                                 (payload['message_id'],)).fetchone()
        if row is not None and row['sender'] != peer_id:
            raise PermissionError('Only the sender may cancel a message')
        removed = connection.execute('DELETE FROM relay_messages WHERE message_id=?',
                                     (payload['message_id'],)).rowcount
        self.database.append_audit(connection, 'relay_cancelled', peer_id, now_unix,
                                   {'message_id': payload['message_id'], 'removed': bool(removed)})
        return {'schema_version': 1, 'cancelled': bool(removed)}

    def shutdown(self, *, now_unix, cancel_pending=False):
        """Trusted local control: stop sends, optionally cancel all pending work."""
        if type(cancel_pending) is not bool:
            raise ValueError('Explicit shutdown policy required')
        with self.database.transaction() as connection:
            self.database.check_clock(connection, now_unix)
            self._expire(connection, now_unix)
            if cancel_pending:
                cancelled = connection.execute('DELETE FROM relay_messages').rowcount
                state = 'stopped'
            else:
                cancelled = 0
                count = connection.execute('SELECT count(*) FROM relay_messages').fetchone()[0]
                state = 'draining' if count else 'stopped'
            self.database.set_setting(connection, 'relay_state', state)
            self.database.append_audit(connection, 'relay_shutdown', None, now_unix,
                                       {'state': state, 'cancelled': cancelled})
            return {'state': state, 'cancelled': cancelled}

    def finish_shutdown(self, *, now_unix):
        with self.database.transaction() as connection:
            self.database.check_clock(connection, now_unix)
            self._expire(connection, now_unix)
            state = self.database.get_setting(connection, 'relay_state')
            if state == 'active':
                raise ValueError('Shutdown has not been requested')
            pending = connection.execute('SELECT count(*) FROM relay_messages').fetchone()[0]
            if pending:
                return False
            self.database.set_setting(connection, 'relay_state', 'stopped')
            return True

    def resume(self, *, now_unix):
        """Explicit administrative restart; constructing Relay never restarts it."""
        with self.database.transaction() as connection:
            self.database.check_clock(connection, now_unix)
            self.database.set_setting(connection, 'relay_state', 'active')
            self.database.append_audit(connection, 'relay_resumed', None, now_unix)

    def status(self, *, now_unix):
        """Privileged local operational aggregate; never returns payloads or IDs."""
        with self.database.transaction() as connection:
            self.database.check_clock(connection, now_unix)
            row = connection.execute('SELECT count(*) AS messages,coalesce(sum(body_bytes),0) AS bytes FROM relay_messages WHERE expires>?',
                                     (now_unix,)).fetchone()
            return {'schema_version': 1, 'state': self.database.get_setting(connection, 'relay_state'),
                    'pending_messages': row['messages'], 'pending_bytes': row['bytes']}
