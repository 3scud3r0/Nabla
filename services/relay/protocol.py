"""Strict application relay operations carried by signed Nabla envelopes.

The audience prevents cross-protocol signature reuse. This is a store-and-forward
application protocol, not TCP forwarding, NAT punching, or encrypted messaging.
Server operators can read payloads; use application-layer encryption separately
when confidentiality is required.
"""
from nablamath.core.semantic_contracts import canonical_payload, require_fields, require_text

AUDIENCE = 'Nabla-relay-v1'
OPERATIONS = {
    'send': {'schema_version', 'operation', 'recipient', 'body', 'ttl_seconds'},
    'poll': {'schema_version', 'operation', 'limit'},
    'ack': {'schema_version', 'operation', 'message_id', 'lease_token'},
    'cancel': {'schema_version', 'operation', 'message_id'},
}


def validate_request(payload, *, max_body_bytes, max_message_ttl):
    if type(payload) is not dict or type(payload.get('schema_version')) is not int or payload.get('schema_version') != 1:
        raise ValueError('Unsupported relay schema')
    operation = payload.get('operation')
    if type(operation) is not str or operation not in OPERATIONS:
        raise ValueError('Unsupported relay operation')
    require_fields(payload, OPERATIONS[operation])
    if operation == 'send':
        require_text(payload['recipient'], 'recipient', limit=256)
        encoded = canonical_payload(payload['body'])
        if len(encoded.encode()) > max_body_bytes:
            raise ValueError('Relay body exceeds configured bound')
        ttl = payload['ttl_seconds']
        if type(ttl) is not int or not 1 <= ttl <= max_message_ttl:
            raise ValueError('Relay message TTL outside policy')
    elif operation == 'poll':
        if type(payload['limit']) is not int or not 1 <= payload['limit'] <= 50:
            raise ValueError('Poll limit must be between 1 and 50')
    else:
        identifier = payload['message_id']
        if type(identifier) is not str or len(identifier) != 64 or any(c not in '0123456789abcdef' for c in identifier):
            raise ValueError('Invalid message digest')
        if operation == 'ack':
            token = payload['lease_token']
            if type(token) is not str or len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
                raise ValueError('Invalid lease token')
    return operation
