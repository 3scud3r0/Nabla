"""Version-one bounded canonical frames over caller-authenticated byte streams.

Framing supplies integrity and resource bounds, not peer authentication or truth.
Existing object-v1 bytes remain nested unchanged; unknown versions fail closed.
"""
import hashlib
import json
from ..core.semantic_contracts import canonical_payload

MAGIC=b'NBL1'
MAX_FRAME=1048576
KINDS=frozenset({'objects','inventory','provenance','receipts'})


def encode_frame(payload,*,kind):
    if type(kind) is not str or kind not in KINDS:
        raise ValueError('Unsupported frame kind')
    body=canonical_payload(payload).encode()
    envelope={'schema_version':1,'kind':kind,'payload':payload,
              'payload_sha256':hashlib.sha256(body).hexdigest()}
    encoded=canonical_payload(envelope).encode()
    if not 0<len(encoded)<=MAX_FRAME:
        raise ValueError('Frame exceeds protocol limit')
    return MAGIC+len(encoded).to_bytes(4,'big')+encoded


def _pairs(items):
    result={}
    for name,value in items:
        if name in result:raise ValueError('Duplicate JSON key')
        result[name]=value
    return result


def decode_frame(raw):
    if type(raw) is not bytes or len(raw)<8 or len(raw)>MAX_FRAME+8 or raw[:4]!=MAGIC:
        raise ValueError('Unsupported or invalid frame')
    length=int.from_bytes(raw[4:8],'big')
    if length!=len(raw)-8 or not 0<length<=MAX_FRAME:
        raise ValueError('Invalid frame length')
    value=json.loads(raw[8:],object_pairs_hook=_pairs)
    if type(value) is not dict or set(value)!={'schema_version','kind','payload','payload_sha256'}:
        raise ValueError('Invalid frame fields')
    if type(value['schema_version']) is not int or value['schema_version']!=1 or type(value['kind']) is not str or value['kind'] not in KINDS:
        raise ValueError('Unsupported frame version or kind')
    if canonical_payload(value).encode()!=raw[8:]:
        raise ValueError('Noncanonical wire encoding')
    expected=hashlib.sha256(canonical_payload(value['payload']).encode()).hexdigest()
    if value['payload_sha256']!=expected:
        raise ValueError('Payload digest mismatch')
    return value


def _read_exact(stream,size):
    chunks=[];remaining=size
    while remaining:
        chunk=stream.recv(remaining)
        if not chunk:raise ConnectionError('Truncated frame')
        chunks.append(chunk);remaining-=len(chunk)
    return b''.join(chunks)


def receive_frame(stream,*,max_bytes=MAX_FRAME,timeout=5):
    if type(max_bytes) is not int or not 1<=max_bytes<=MAX_FRAME:
        raise ValueError('Invalid local frame bound')
    if type(timeout) not in (int,float) or not 0<timeout<=60:
        raise ValueError('Invalid receive timeout')
    stream.settimeout(timeout)
    header=_read_exact(stream,8)
    if header[:4]!=MAGIC:
        raise ValueError('Unsupported frame version')
    length=int.from_bytes(header[4:],'big')
    if not 0<length<=max_bytes:
        raise ValueError('Frame exceeds local bound')
    return decode_frame(header+_read_exact(stream,length))
