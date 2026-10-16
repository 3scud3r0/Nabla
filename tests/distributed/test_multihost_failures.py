"""Real loopback TCP + separate processes; independent multihost remains unverified.

This tests crash/restart and delayed causal delivery over sockets. It does not
claim WAN latency/loss, TLS interoperability or distinct-machine acceptance.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import pytest
from nablamath.core.semantic_ir import fingerprint
from nablamath.knowledge.identity import generate_signing_key,public_key_hex
from nablamath.knowledge.distributed_provenance import provenance_event

SERVER=r'''
import json,socket,sys
from pathlib import Path
from nablamath.knowledge.identity import PeerTrust,PeerKey
from nablamath.knowledge.distributed_provenance import ProvenanceLog
from services.federation.reconciliation import Reconciler
root=Path(sys.argv[1]);key=sys.argv[2]
log=ProvenanceLog(root/'events.db',PeerTrust([PeerKey('A',key)]))
service=Reconciler(root/'inbox.db',log)
with socket.create_server(('127.0.0.1',0)) as server:
    (root/'port').write_text(str(server.getsockname()[1]))
    connection,_=server.accept()
    with connection:
        connection.settimeout(3)
        header=b''
        while len(header)<4:
            chunk=connection.recv(4-len(header))
            if not chunk:raise ValueError('Truncated header')
            header+=chunk
        length=int.from_bytes(header,'big')
        if not 0<length<=65536:raise ValueError('Bounded packet required')
        packet=b''
        while len(packet)<length:
            chunk=connection.recv(length-len(packet))
            if not chunk:raise ValueError('Truncated packet')
            packet+=chunk
        report=service.receive(json.loads(packet),now_unix=2)
        connection.sendall(json.dumps(report).encode())
service.close();log.close()
'''


def start_receiver(tmp_path,key):
    port_file=tmp_path/'port'
    port_file.unlink(missing_ok=True)
    root=Path(__file__).resolve().parents[2]
    env={**os.environ,'PYTHONPATH':str(root/'src')+os.pathsep+str(root)}
    process=subprocess.Popen([sys.executable,'-c',SERVER,str(tmp_path),key],cwd=root,
                             env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    deadline=time.monotonic()+5
    while not port_file.exists() and process.poll() is None and time.monotonic()<deadline:
        time.sleep(.01)
    if not port_file.exists():
        process.kill();out,err=process.communicate(timeout=2)
        pytest.fail('Receiver failed to start: '+err)
    return process,int(port_file.read_text())


def deliver(port,envelopes):
    raw=json.dumps(envelopes).encode()
    with socket.create_connection(('127.0.0.1',port),timeout=3) as connection:
        connection.sendall(len(raw).to_bytes(4,'big')+raw)
        received=b''
        while True:
            chunk=connection.recv(65536)
            if not chunk:break
            received+=chunk
            assert len(received)<1048576
    return json.loads(received)


def test_separate_process_restart_preserves_pending_partition_delivery(tmp_path):
    pytest.importorskip('cryptography')
    key=generate_signing_key()
    root=provenance_event(key,operator='A',artifact='a'*64,action='publish',nonce='root',issued_unix=1,expires_unix=100)
    child=provenance_event(key,operator='A',artifact='a'*64,action='endorse',previous=fingerprint(root),nonce='child',issued_unix=1,expires_unix=100)
    process,port=start_receiver(tmp_path,public_key_hex(key))
    try:
        report=deliver(port,[child])
        assert {r['state'] for r in report['events']}=={'pending'}
        assert process.wait(timeout=5)==0,process.stderr.read()
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=2)
    process,port=start_receiver(tmp_path,public_key_hex(key))
    try:
        report=deliver(port,[root])
        assert {r['state'] for r in report['events']}=={'accepted'}
        assert process.wait(timeout=5)==0,process.stderr.read()
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=2)


def test_tcp_frame_bound_rejects_oversized_admission(tmp_path):
    pytest.importorskip('cryptography')
    key=generate_signing_key();process,port=start_receiver(tmp_path,public_key_hex(key))
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=3) as connection:
            connection.sendall((65537).to_bytes(4,'big'))
        assert process.wait(timeout=5)!=0
        assert 'Bounded packet' in process.stderr.read()
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=2)
