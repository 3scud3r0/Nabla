"""Declared groups cap key multiplicity; no real-world Sybil prevention claim."""
import pytest
from nablamath.p2p.resilient_peers import Anchor,ResilientPeers


def test_one_thousand_keys_do_not_create_operator_diversity():
    anchors=[Anchor(f'{i:064x}','same-operator','https://example.invalid') for i in range(1000)]
    policy=ResilientPeers(anchors)
    result=policy.select(now=0)
    assert not result['ready'] and not result['peers']
    assert not result['sybil_resistance_established']


def test_unpinned_injected_peer_is_rejected():
    peers=ResilientPeers([Anchor('a'*64,'A','https://a.invalid')],minimum_groups=1)
    with pytest.raises(ValueError,match='Unknown'):
        peers.observe('b'*64,success=True,now=1)
