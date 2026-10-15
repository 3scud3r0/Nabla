"""Dependency-free client for the bounded coordinator JSON API."""
import ipaddress
import json
import math
import re
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError


class CoordinatorError(RuntimeError):
    """HTTP or protocol failure; credentials and response bodies are excluded."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _digest(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Invalid content digest')
    return value


def _fields(value, names):
    if not isinstance(value, dict) or set(value) != set(names):
        raise ValueError('Invalid response fields')


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError('Invalid expiration')


def _seconds(value):
    if type(value) is not int or not 1 <= value <= 3600:
        raise ValueError('Invalid lease duration')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


class CoordinatorClient:
    def __init__(self, endpoint, participant, token, *, timeout=5, max_response_bytes=65536):
        parsed = urlsplit(endpoint)
        try:
            local = parsed.hostname == 'localhost' or ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            local = False
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or
                (parsed.scheme == 'http' and not local) or parsed.username or parsed.password or
                parsed.path not in {'', '/'} or parsed.query or parsed.fragment):
            raise ValueError('Explicit HTTPS or loopback HTTP origin required')
        parsed.port  # Reject malformed ports before sending a request.
        if any(not isinstance(v, str) or not v or len(v) > limit or any(ord(c) < 32 or ord(c) > 126 for c in v)
               for v, limit in ((participant, 128), (token, 4096))):
            raise ValueError('Invalid credentials')
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise ValueError('Invalid timeout')
        if type(max_response_bytes) is not int or not 1 <= max_response_bytes <= 1048576:
            raise ValueError('Invalid response bound')
        self.endpoint, self.participant, self._token = endpoint.rstrip('/'), participant, token
        self.timeout, self.max_response_bytes = timeout, max_response_bytes
        self._opener = build_opener(_NoRedirect())  # Default HTTPS certificate verification.

    def _request(self, method, path, payload=None):
        data = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        if data is not None and len(data) > 65536:
            raise ValueError('Request exceeds server limit')
        request = Request(self.endpoint+path, data=data, method=method, headers={
            'Authorization': 'Bearer '+self._token, 'X-Nabla-Participant': self.participant,
            'Content-Type': 'application/json', 'Accept': 'application/json'})
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                if response.status != 200 or response.headers.get_content_type() != 'application/json':
                    raise CoordinatorError('Unexpected HTTP response')
                body = response.read(self.max_response_bytes+1)
                if len(body) > self.max_response_bytes:
                    raise CoordinatorError('Response exceeds configured bound')
            return json.loads(body.decode('utf-8'), object_pairs_hook=_pairs,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
        except HTTPError as exc:
            exc.close()
            raise CoordinatorError(f'Coordinator HTTP status {exc.code}') from None
        except (ValueError, UnicodeError, OSError) as exc:
            raise CoordinatorError('Invalid coordinator response or transport failure') from None

    def create_task(self, expression, values):
        if not isinstance(expression, str) or not expression or not isinstance(values, dict):
            raise ValueError('Expression and rational bindings required')
        result = self._request('POST', '/tasks', {'expression': expression, 'values': values})
        try:
            _fields(result, {'task_id'}); return _digest(result['task_id'])
        except ValueError:
            raise CoordinatorError('Invalid create response') from None

    def status(self, task_id):
        result = self._request('GET', '/tasks/'+_digest(task_id))
        try:
            _fields(result, {'task_id', 'status'})
            if result['task_id'] != task_id or result['status'] not in {'pending', 'verified', 'cancelled'}:
                raise ValueError()
            return result['status']
        except (ValueError, TypeError):
            raise CoordinatorError('Invalid status response') from None

    def lease(self, seconds=60):
        _seconds(seconds)
        result = self._request('POST', '/leases', {'seconds': seconds})
        try:
            _fields(result, {'lease'}); lease = result['lease']
            if lease is None:
                return None
            _fields(lease, {'task_id', 'expression', 'values', 'lease_expires_unix'})
            _digest(lease['task_id']); _number(lease['lease_expires_unix'])
            if (not isinstance(lease['expression'], str) or not 1 <= len(lease['expression']) <= 65536
                    or not isinstance(lease['values'], dict) or len(lease['values']) > 128
                    or any(not isinstance(k, str) or not k or len(k) > 128 or not isinstance(v, str)
                           or not re.fullmatch(r'-?\d+(?:/\d+)?', v) or ('/' in v and int(v.split('/')[1]) == 0)
                           for k, v in lease['values'].items())):
                raise ValueError()
            return lease
        except (ValueError, TypeError):
            raise CoordinatorError('Invalid lease response') from None

    def heartbeat(self, task_id, seconds=60):
        _seconds(seconds)
        result = self._request('POST', '/tasks/'+_digest(task_id)+'/heartbeat', {'seconds': seconds})
        try:
            _fields(result, {'lease_expires_unix'}); _number(result['lease_expires_unix'])
            return result['lease_expires_unix']
        except ValueError:
            raise CoordinatorError('Invalid heartbeat response') from None

    def submit(self, task_id, result_id):
        return self._status_action(task_id, 'submit', {'result_id': _digest(result_id)}, {'awaiting_second_worker', 'verified'})

    def cancel(self, task_id):
        return self._status_action(task_id, 'cancel', {}, {'cancelled'})

    def _status_action(self, task_id, action, payload, statuses):
        result = self._request('POST', '/tasks/'+_digest(task_id)+'/'+action, payload)
        try:
            _fields(result, {'status'})
            if result['status'] not in statuses:
                raise ValueError()
            return result['status']
        except (ValueError, TypeError):
            raise CoordinatorError('Invalid action response') from None
