"""Versioned local API and explicit loopback-only HTTP adapter.

No external listener is created by imports. TLS, internet authentication, reverse
proxies and rate limits belong to the deployment boundary; this adapter is for
local integration and tests. Administrative pin/revoke APIs are never exposed.
"""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import BoundedSemaphore, Thread
from urllib.parse import parse_qs, urlsplit

from nablamath.core.semantic_contracts import canonical_payload, load_json


class RegistryAPI:
    def __init__(self, registry, *, clock):
        if not callable(clock):
            raise ValueError('Explicit server clock required')
        self.registry, self.clock = registry, clock

    def handle(self, method, target, raw=b''):
        """Return (HTTP status, JSON-native response); never leak exception details."""
        if type(raw) is not bytes or len(raw) > 1000000:
            return 413, {'schema_version': 1, 'error': 'request_too_large'}
        if not isinstance(target, str) or len(target) > 4096:
            return 400, {'schema_version': 1, 'error': 'invalid_target'}
        try:
            parsed = urlsplit(target)
        except ValueError:
            return 400, {'schema_version': 1, 'error': 'invalid_target'}
        if parsed.scheme or parsed.netloc or parsed.fragment:
            return 400, {'schema_version': 1, 'error': 'invalid_target'}
        try:
            if method == 'POST' and parsed.path == '/v1/registrations' and not parsed.query:
                return 200, self.registry.submit(load_json(raw.decode('utf-8')), now_unix=self.clock())
            if method == 'GET' and parsed.path == '/v1/peers' and not raw:
                query = parse_qs(parsed.query, strict_parsing=True, max_num_fields=3, keep_blank_values=True)
                if set(query) - {'capability', 'after', 'limit'} or any(len(values) != 1 for values in query.values()):
                    raise ValueError('Invalid query fields')
                return 200, self.registry.discover(now_unix=self.clock(),
                    capability=query.get('capability', [None])[0], after=query.get('after', [''])[0],
                    limit=int(query.get('limit', ['100'])[0]))
            return 404, {'schema_version': 1, 'error': 'route_not_found'}
        except PermissionError:
            return 403, {'schema_version': 1, 'error': 'not_authorized'}
        except (ValueError, TypeError, UnicodeError):
            return 400, {'schema_version': 1, 'error': 'invalid_request'}


@contextmanager
def loopback_http(api, *, port=0):
    """Start one opt-in local server; stop and join it on context exit."""
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError('Invalid loopback port')

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.0'

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *_):
            # Do not print request paths, signed bodies or peer identifiers.
            pass

        def do_GET(self):
            self._dispatch()

        def do_POST(self):
            self._dispatch()

        def _dispatch(self):
            self.connection.settimeout(5)
            try:
                if self.headers.get('Transfer-Encoding') is not None:
                    raise ValueError('Chunked requests unsupported')
                lengths = self.headers.get_all('Content-Length', [])
                if len(lengths) > 1:
                    raise ValueError('Ambiguous content length')
                if lengths and (not lengths[0] or any(c not in '0123456789' for c in lengths[0])):
                    raise ValueError('Content length must contain ASCII decimal digits')
                length = int(lengths[0]) if lengths else 0
                if not 0 <= length <= 1000000:
                    self._send(413, {'schema_version': 1, 'error': 'request_too_large'})
                    return
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError('Truncated request')
                status, body = api.handle(self.command, self.path, raw)
            except (ValueError, OSError):
                status, body = 400, {'schema_version': 1, 'error': 'invalid_request'}
            self._send(status, body)

        def _send(self, status, body):
            encoded = canonical_payload(body).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(encoded)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            try:
                self.wfile.write(encoded)
            except OSError:
                pass

    class BoundedServer(ThreadingHTTPServer):
        def __init__(self, *args, **kwargs):
            self.slots = BoundedSemaphore(8)
            super().__init__(*args, **kwargs)

        def process_request(self, request, client_address):
            if not self.slots.acquire(blocking=False):
                self.shutdown_request(request)
                return
            try:
                super().process_request(request, client_address)
            except BaseException:
                self.slots.release()
                raise

        def process_request_thread(self, request, client_address):
            try:
                super().process_request_thread(request, client_address)
            finally:
                self.slots.release()

    server = BoundedServer(('127.0.0.1', port), Handler)
    # Join bounded handlers on close; no request can outlive this context.
    server.daemon_threads = False
    thread = Thread(target=server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:' + str(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        if thread.is_alive():
            raise RuntimeError('Loopback server did not stop')
