"""Bounded IPFS raw-block storage with independently verified SHA-256 CIDv1."""
import base64
import hashlib
import json
from urllib.parse import urlparse, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

MAX_BYTES = 16*1024*1024


def raw_cid(data):
    return 'b'+base64.b32encode(b'\x01\x55\x12\x20'+hashlib.sha256(data).digest()).decode().lower().rstrip('=')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class IPFSStorage:
    def __init__(self, endpoint='http://127.0.0.1:5001', *, timeout=10):
        parsed = urlparse(endpoint)
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('An explicit HTTP(S) IPFS API endpoint is required')
        if not 0 < timeout <= 60:
            raise ValueError('Invalid timeout')
        self.endpoint, self.timeout = endpoint.rstrip('/'),timeout
        self.opener = build_opener(NoRedirect())

    def _post(self, method, *, query=None, data=b'', content_type=None):
        url = self.endpoint+'/api/v0/'+method+('?' + urlencode(query) if query else '')
        headers = {} if content_type is None else {'Content-Type':content_type}
        request = Request(url,data=data,headers=headers,method='POST')
        with self.opener.open(request,timeout=self.timeout) as response:
            body = response.read(MAX_BYTES+1)
        if len(body) > MAX_BYTES:
            raise ValueError('IPFS response exceeds budget')
        return body

    def put(self, data):
        if not isinstance(data,bytes) or len(data) > MAX_BYTES:
            raise ValueError('IPFS accepts up to 16 MiB of bytes per raw block')
        # Content-derived boundary cannot appear in its own base64-free framing accidentally.
        import secrets
        boundary = 'nabla-'+secrets.token_hex(24)
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="artifact"\r\n'
                'Content-Type: application/octet-stream\r\n\r\n').encode()+data+f'\r\n--{boundary}--\r\n'.encode()
        response = json.loads(self._post('block/put',query={'format':'raw','mhtype':'sha2-256','pin':'true'},
                               data=body,content_type='multipart/form-data; boundary='+boundary))
        identifier = raw_cid(data)
        if response.get('Key') != identifier:
            raise ValueError('IPFS returned a CID that does not match uploaded content')
        return identifier

    def get(self, cid):
        if not isinstance(cid,str) or len(cid) != 59 or not cid.startswith('bafkrei') or any(c not in 'abcdefghijklmnopqrstuvwxyz234567' for c in cid[1:]):
            raise ValueError('Only canonical raw SHA-256 CIDv1 blocks are supported')
        data = self._post('block/get',query={'arg':cid})
        if raw_cid(data) != cid:
            raise ValueError('IPFS block integrity failed')
        return data
