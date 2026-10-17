"""Real local transport, signed evidence, counterexamples and content-address checks."""
from copy import deepcopy
import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import pytest
from nablamath.calc import CalculationSession
from nablamath.calc.receipt import receipt
from nablamath.artifacts.bundle import create_bundle,save_bundle,load_bundle,verify_bundle
from nablamath.federation.ipfs_storage import IPFSStorage,raw_cid


def trust_pair():
    pytest.importorskip('cryptography')
    from nablamath.federation.crypto_registry import CryptoRegistry,generate_key,public_key_hex
    keys = {name:generate_key() for name in ('A','B')}
    registry = CryptoRegistry()
    for name,key in keys.items():
        registry.pin(name,public_key_hex(key))
    return keys,registry


def test_signatures_tamper_and_irreversible_revocation():
    keys,registry = trust_pair()
    from nablamath.federation.crypto_registry import sign,public_key_hex
    record = sign(receipt('sum',[1,2],3),keys['A'],signer='A')
    assert registry.verify(record)
    changed = deepcopy(record); changed['payload']['result'] = 4
    assert not registry.verify(changed)
    registry.revoke('A',public_key_hex(keys['A']))
    assert not registry.verify(record)
    with pytest.raises(ValueError):
        registry.pin('A',public_key_hex(keys['A']))


def test_refutation_replays_exact_statement_and_author_withdrawal():
    from nablamath.formal.statement import FormalStatement
    from nablamath.federation.claims import ClaimRegistry,claim_event,refutation_event,withdrawal_event
    keys,trust = trust_pair(); registry = ClaimRegistry(trust)
    identifier = registry.append(claim_event(FormalStatement.equality('x+1','x'),keys['A'],signer='A'))
    with pytest.raises(ValueError):
        registry.append(refutation_event(identifier,{'wrong':'0'},keys['B'],signer='B'))
    registry.append(refutation_event(identifier,{'x':'0'},keys['B'],signer='B'))
    assert registry.status(identifier)['status'] == 'refuted'
    with pytest.raises(ValueError):
        registry.append(withdrawal_event(identifier,'withdraw',keys['B'],signer='B'))
    registry.append(withdrawal_event(identifier,'model corrected',keys['A'],signer='A'))
    assert registry.status(identifier)['status'] == 'withdrawn'
    assert ClaimRegistry.from_data(registry.to_data(),trust).status(identifier) == registry.status(identifier)
    true_id = registry.append(claim_event(FormalStatement.equality('x','x'),keys['A'],signer='A'))
    with pytest.raises(ValueError):
        registry.append(refutation_event(true_id,{'x':'1'},keys['B'],signer='B'))


def test_bundle_replay_tamper_and_exclusive_creation(tmp_path):
    calc = CalculationSession().execute('beta_binomial',successes=2,trials=3).to_data()
    bundle = create_bundle([calc,receipt('external',[1],1)],datasets={'measurements':[1,2]})
    path = tmp_path/'artifact.json'; save_bundle(bundle,path)
    assert load_bundle(path) == bundle
    with pytest.raises(FileExistsError):
        save_bundle(bundle,path)
    bundle['datasets']['measurements'][0] = 4
    assert not verify_bundle(bundle)


def test_two_real_http_nodes_authentication_and_integrity(tmp_path):
    keys,trust = trust_pair()
    from nablamath.federation.p2p_node import P2PNode
    from nablamath.federation.crypto_registry import sign
    token = 'a'*32
    first = P2PNode(tmp_path/'first',trust=trust,token=token)
    second = P2PNode(tmp_path/'second',trust=trust,token='b'*32)
    envelope = sign(receipt('sum',[1,2],3),keys['A'],signer='A')
    identifier = first.put(envelope)
    server = first.make_server(); thread = Thread(target=server.serve_forever,daemon=True); thread.start()
    endpoint = 'http://127.0.0.1:'+str(server.server_port)
    try:
        assert second.fetch(endpoint,identifier,token=token) == envelope
        assert second.get(identifier) == envelope
        with pytest.raises(HTTPError) as error:
            urlopen(endpoint+'/receipts/'+identifier,timeout=2)
        assert error.value.code == 401
        request = Request(endpoint+'/receipts',data=json.dumps(envelope).encode(),headers={'Authorization':'Bearer '+token},method='POST')
        with urlopen(request,timeout=2) as response:
            assert json.load(response)['content_id'] == identifier
        with pytest.raises(ValueError):
            second.get('../escape')
    finally:
        server.shutdown(); thread.join(); server.server_close()


def test_ipfs_raw_cid_and_corrupt_transport(monkeypatch):
    # Known SHA-256 empty block digest encoded as CIDv1/raw.
    data = b''
    cid = raw_cid(data)
    assert cid == 'bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku'
    storage = IPFSStorage()
    monkeypatch.setattr(storage,'_post',lambda method,**kwargs: data)
    assert storage.get(cid) == data
    monkeypatch.setattr(storage,'_post',lambda method,**kwargs: b'corrupt')
    with pytest.raises(ValueError,match='integrity'):
        storage.get(cid)
    monkeypatch.setattr(storage,'_post',lambda method,**kwargs: json.dumps({'Key':cid}).encode())
    assert storage.put(data) == cid
    with pytest.raises(ValueError):
        storage.put(b'other bytes')
