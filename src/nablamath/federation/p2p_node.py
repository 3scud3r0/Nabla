"""Explicit token-authenticated HTTP exchange of pinned-key signed receipts.

No discovery, unsolicited publication or automatic trust. Use TLS for remote peers.
"""
import hmac
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, build_opener

from ..calc.receipt import verify_receipt
from ..core.semantic_ir import canonical_json
from .ipfs_storage import NoRedirect

MAX_BYTES = 16*1024*1024


def _id(identifier):
    if not isinstance(identifier,str) or len(identifier) != 64 or any(c not in '0123456789abcdef' for c in identifier):
        raise ValueError('Expected a SHA-256 content ID')
    return identifier


class P2PNode:
    def __init__(self, directory, *, trust, token):
        if not isinstance(token,str) or not token.isascii() or len(token) < 32:
            raise ValueError('An explicit ASCII bearer token of at least 32 characters is required')
        self.directory = Path(directory)
        self.directory.mkdir(parents=True,exist_ok=True)
        self.trust, self.token = trust,token
        self._lock = threading.RLock()

    def put(self, envelope):
        if not self.trust.verify(envelope) or not verify_receipt(envelope['payload']):
            raise ValueError('Only trusted signed calculation/observation receipts are accepted')
        raw = canonical_json(envelope).encode()
        if len(raw) > MAX_BYTES:
            raise ValueError('Envelope exceeds budget')
        identifier = _id(envelope['content_id'])
        with self._lock:
            path = self.directory/identifier
            if path.exists():
                self.get(identifier)
            else:
                descriptor, temporary = tempfile.mkstemp(prefix='.receipt-',dir=self.directory)
                try:
                    with os.fdopen(descriptor,'wb') as stream:
                        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
                    try:
                        os.link(temporary,path)
                    except FileExistsError:
                        self.get(identifier)
                finally:
                    Path(temporary).unlink(missing_ok=True)
        return identifier

    def get(self, identifier):
        with (self.directory/_id(identifier)).open('rb') as stream:
            raw = stream.read(MAX_BYTES+1)
        if len(raw) > MAX_BYTES:
            raise ValueError('Stored envelope exceeds budget')
        envelope = json.loads(raw)
        if envelope['content_id'] != identifier or not self.trust.verify(envelope) or not verify_receipt(envelope['payload']):
            raise ValueError('Stored receipt integrity or trust failed')
        return envelope

    def make_server(self, *, host='127.0.0.1', port=0):
        node = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _authorized(self):
                supplied = self.headers.get('Authorization','')
                if not hmac.compare_digest(supplied.encode(),('Bearer '+node.token).encode()):
                    self.send_error(401)
                    return False
                self.connection.settimeout(10)
                return True

            def _reply(self, value):
                raw = canonical_json(value).encode()
                self.send_response(200); self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)

            def do_GET(self):
                if not self._authorized():
                    return
                try:
                    if not self.path.startswith('/receipts/'):
                        self.send_error(404); return
                    self._reply(node.get(self.path.removeprefix('/receipts/')))
                except FileNotFoundError:
                    self.send_error(404)
                except (ValueError,KeyError,TypeError):
                    self.send_error(400)

            def do_POST(self):
                if not self._authorized():
                    return
                if self.path != '/receipts':
                    self.send_error(404); return
                try:
                    length = int(self.headers.get('Content-Length','0'))
                    if not 0 < length <= MAX_BYTES or self.headers.get('Transfer-Encoding'):
                        raise ValueError('Invalid length')
                    raw = self.rfile.read(length)
                    if len(raw) != length:
                        raise ValueError('Truncated request')
                    self._reply({'content_id':node.put(json.loads(raw))})
                except (ValueError,KeyError,TypeError,TimeoutError):
                    self.send_error(400)
        return ThreadingHTTPServer((host,port),Handler)

    def fetch(self, endpoint, identifier, *, token, timeout=10):
        parsed = urlparse(endpoint)
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Explicit HTTP(S) peer endpoint required')
        if not 0 < timeout <= 60:
            raise ValueError('Invalid timeout')
        request = Request(endpoint.rstrip('/')+'/receipts/'+_id(identifier),headers={'Authorization':'Bearer '+token})
        with build_opener(NoRedirect()).open(request,timeout=timeout) as response:
            raw = response.read(MAX_BYTES+1)
        if len(raw) > MAX_BYTES:
            raise ValueError('Peer response exceeds budget')
        envelope = json.loads(raw)
        if envelope.get('content_id') != identifier:
            raise ValueError('Peer returned the wrong receipt')
        self.put(envelope)
        return envelope
